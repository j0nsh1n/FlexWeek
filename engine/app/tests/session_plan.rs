//! Plan, Replan, Place now and Find a new time decisions (P4 group 5A).
//! Expected values come from the planning rules in `spec.md` and the desktop parity tests listed in
//! `DRAFT-245.md` row 5A.

use flexweek_app::session::plan::{
    PlanAnswerInput, PlanClock, PlanInput, PlanPreparation, WEEK_OVER, apply_auto_split,
    apply_plan_answer, first_placed, left_sentence, place_now_sentence, plan_sentence,
    prepare_plan,
};
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-09-21"; // Monday
const LAST_WEEK: &str = "2026-09-14";

fn clock(today_iso: &str, hour: i64, minute: i64) -> PlanClock<'_> {
    PlanClock {
        today_iso,
        hour,
        minute,
        second: 0,
        microsecond: 0,
    }
}

fn homework(id: &str, title: &str, due: &str, estimate_min: i64) -> Value {
    json!({
        "id": id,
        "title": title,
        "due": due,
        "estimate_min": estimate_min,
        "priority": 3,
        "energy": "medium",
        "spread": "one",
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": false,
        "planned_min": estimate_min,
        "unplanned_min": 0,
        "done_min": 0,
    })
}

fn flex_block(
    id: &str,
    assignment_id: &str,
    title: &str,
    duration_min: i64,
    days: &[i64],
) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "flexible",
        "duration_min": duration_min,
        "days": days,
        "priority": 3,
        "energy": "medium",
        "completed": false,
        "assignment_id": assignment_id,
    })
}

fn locked_block(id: &str, title: &str, start: &str, duration_min: i64, days: &[i64]) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "locked",
        "start": start,
        "duration_min": duration_min,
        "days": days,
        "priority": 1,
        "energy": "medium",
        "category": "class",
        "completed": false,
        "missed_days": [],
    })
}

fn map_of(pairs: &[(&str, Value)]) -> Map<String, Value> {
    pairs
        .iter()
        .map(|(k, v)| ((*k).to_string(), v.clone()))
        .collect()
}

fn base_plan_input<'a>(
    week_start: &'a str,
    blocks: &'a [Value],
    assignments: &'a Map<String, Value>,
    basis: &'a [Value],
    saved_weeks: &'a [String],
    split_whole: &'a [String],
    now: PlanClock<'a>,
) -> PlanInput<'a> {
    PlanInput {
        planning: false,
        conflict: false,
        pending_save: false,
        week_start,
        blocks,
        assignments,
        assignments_basis: basis,
        preferences: None,
        saved_weeks,
        split_whole,
        clock: now,
        everything: false,
        only: None,
        earliest_first: false,
        prepared_weeks: None,
        overdue: None,
    }
}

fn counter_ids() -> impl FnMut() -> String {
    let mut n = 0usize;
    move || {
        n += 1;
        format!("chunk-{n}")
    }
}

#[test]
fn a_week_that_is_over_is_refused_before_earlier_week_fetches_or_solving() {
    // Parity: test_plan_on_a_week_that_is_over_does_not_ask_the_solver.
    // Even with saved earlier weeks present, a past week must stop with WEEK_OVER before fetching.
    let assignments = map_of(&[("old", homework("old", "Old worksheet", "2026-09-20", 60))]);
    let blocks = vec![flex_block(
        "b1",
        "old",
        "Old worksheet",
        60,
        &[0, 1, 2, 3, 4, 5, 6],
    )];
    let saved_weeks = vec!["2026-09-07".to_string(), LAST_WEEK.to_string()];
    let split_whole: Vec<String> = Vec::new();
    let input = base_plan_input(
        LAST_WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-24", 10, 0), // Thursday of the following week
    );
    assert_eq!(
        prepare_plan(input).unwrap(),
        PlanPreparation::WeekOver {
            message: WEEK_OVER.to_string(),
        }
    );

    // Sunday 23:50 rounds up to midnight -> day 7 -> also over.
    let sunday_late = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-27", 23, 50),
    );
    assert_eq!(
        prepare_plan(sunday_late).unwrap(),
        PlanPreparation::WeekOver {
            message: WEEK_OVER.to_string(),
        }
    );
}

#[test]
fn planning_conflict_and_pending_save_block_before_solving() {
    let assignments = Map::new();
    let blocks: Vec<Value> = Vec::new();
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();
    let now = clock("2026-09-24", 10, 0);

    let mut planning = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    planning.planning = true;
    assert_eq!(
        prepare_plan(planning).unwrap(),
        PlanPreparation::Blocked {
            message: "Planning\u{2026} one moment.".into(),
            replan_after_save: false,
        }
    );

    let mut conflict = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    conflict.conflict = true;
    assert_eq!(
        prepare_plan(conflict).unwrap(),
        PlanPreparation::Blocked {
            message: "This week changed in another window. Choose More > Reload this week, then try again.".into(),
            replan_after_save: false,
        }
    );

    let mut pending_plain = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    pending_plain.pending_save = true;
    assert_eq!(
        prepare_plan(pending_plain).unwrap(),
        PlanPreparation::Blocked {
            message: "Saving your last change\u{2026} Plan will work in a moment.".into(),
            replan_after_save: false,
        }
    );

    let mut pending_replan = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    pending_replan.pending_save = true;
    pending_replan.everything = true;
    assert_eq!(
        prepare_plan(pending_replan).unwrap(),
        PlanPreparation::Blocked {
            message: "Saving your last change\u{2026} Plan will work in a moment.".into(),
            replan_after_save: true,
        }
    );
}

#[test]
fn earlier_saved_weeks_are_requested_unless_targeted_or_already_fetched() {
    let assignments = map_of(&[("math", homework("math", "Math", "2026-09-27", 60))]);
    let blocks = vec![flex_block("m1", "math", "Math", 60, &[0, 1, 2, 3, 4, 5, 6])];
    let saved_weeks = vec![
        LAST_WEEK.to_string(),
        WEEK.to_string(),
        "2026-09-28".to_string(),
    ];
    let split_whole: Vec<String> = Vec::new();
    let now = clock("2026-09-24", 10, 0);

    let input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    assert_eq!(
        prepare_plan(input).unwrap(),
        PlanPreparation::FetchEarlier {
            weeks: vec![LAST_WEEK.to_string()],
        }
    );

    // Targeted solve (`only`) never fetches earlier weeks.
    let only = vec!["m1".to_string()];
    let mut targeted = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    targeted.only = Some(&only);
    match prepare_plan(targeted).unwrap() {
        PlanPreparation::Ready { targets, .. } => assert_eq!(targets, vec!["m1"]),
        other => panic!("expected Ready, got {other:?}"),
    }

    // Already fetched (`prepared_weeks: Some(...)`) proceeds to Ready.
    let empty_fetched = Map::new();
    let mut fetched = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        now,
    );
    fetched.prepared_weeks = Some(&empty_fetched);
    match prepare_plan(fetched).unwrap() {
        PlanPreparation::Ready { targets, body, .. } => {
            assert_eq!(targets, vec!["m1"]);
            assert_eq!(body["week_start"], WEEK);
            assert_eq!(body["now_floor"], json!([3, 600])); // Thursday 10:00
        }
        other => panic!("expected Ready, got {other:?}"),
    }
}

#[test]
fn a_session_moved_in_from_last_week_gets_the_same_fair_share() {
    // Parity: test_a_session_moved_in_from_last_week_gets_the_same_share.
    // 120 min "spread" homework due Wednesday of week after next (16 days after Monday 2026-09-21 = 2026-10-07).
    // Its one session was saved with no time last week (2026-09-14). Server read this week with 0 planned here
    // (planned_min=120 in last week, saved_week=[] -> this_weeks_part = 120).
    // On Saturday 07:00 (day 5): Sat+Sun = 2 of 2 + 7 + 3 = 12 plannable days.
    // 120 * 2 / 12 = 20 -> rounded up to quarter hour = 30 min this week, 90 min waiting.
    let mut sci = homework("sci", "Science project", "2026-10-07T23:59", 120);
    sci["spread"] = json!("spread");
    sci["planned_min"] = json!(0);
    sci["unplanned_min"] = json!(120);
    let assignments = map_of(&[("sci", sci)]);
    let blocks: Vec<Value> = Vec::new();
    let saved_weeks = vec![LAST_WEEK.to_string()];
    let split_whole: Vec<String> = Vec::new();
    let prior_session = flex_block(
        "sci-1",
        "sci",
        "Science project",
        120,
        &[0, 1, 2, 3, 4, 5, 6],
    );
    let prepared_weeks = map_of(&[(
        LAST_WEEK,
        json!({
            "blocks": [prior_session],
            "revision": 1,
        }),
    )]);

    let mut input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks, // server basis for this week is empty
        &saved_weeks,
        &split_whole,
        clock("2026-09-26", 7, 0), // Saturday 07:00
    );
    input.prepared_weeks = Some(&prepared_weeks);

    let (body, targets, prior_updates, shares, week) = match prepare_plan(input).unwrap() {
        PlanPreparation::Ready {
            body,
            targets,
            prior_updates,
            shares,
            week,
        } => (body, targets, prior_updates, shares, week),
        other => panic!("expected Ready, got {other:?}"),
    };
    assert_eq!(targets, vec!["sci-1"]);
    assert_eq!(prior_updates.len(), 1);
    assert_eq!(prior_updates[0]["week_start"], LAST_WEEK);
    assert_eq!(prior_updates[0]["after"], json!([]));
    assert_eq!(shares.len(), 1);
    assert_eq!(shares[0]["this_week_min"], 30);
    assert_eq!(shares[0]["left_min"], 90);

    // The prepared week has the 30-min trimmed target and a 90-min rest session.
    let mut durations: Vec<(String, i64)> = week
        .iter()
        .map(|b| {
            (
                b["id"].as_str().unwrap().to_string(),
                b["duration_min"].as_i64().unwrap(),
            )
        })
        .collect();
    durations.sort();
    assert_eq!(
        durations,
        vec![("sci-1".to_string(), 30), (format!("sci-rest-{WEEK}"), 90),]
    );
    // Solver body asks for the 30-min block with earliest Saturday 07:00.
    let sent = body["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == "sci-1")
        .unwrap();
    assert_eq!(sent["duration_min"], 30);
    assert_eq!(sent["earliest"], "Saturday 07:00");

    // Apply solver placing sci-1 on Saturday 07:00 -> share updated with placed_days=[5], this_week_min=30, left_min=90.
    let trace = json!({
        "placed": [{
            "id": "sci-1",
            "assignment_id": "sci",
            "title": "Science project",
            "kind": "flexible",
            "duration_min": 30,
            "days": [5],
            "start": "07:00",
        }],
        "unplaced": [],
        "explanations": [],
        "complete": true,
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &shares,
            needs_time: &empty_needs,
            clock: clock("2026-09-26", 7, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(answer.changed);
    assert_eq!(answer.trace["shares"][0]["this_week_min"], 30);
    assert_eq!(answer.trace["shares"][0]["left_min"], 90);
    assert_eq!(answer.trace["shares"][0]["placed_days"], json!([5]));
    assert_eq!(answer.plan_first, Some((5, 7 * 60)));
}

#[test]
fn replan_all_keeps_begun_and_pinned_sessions_and_moves_unpinned_future_or_missed() {
    // Thursday 10:00 (day 3, 600 min).
    // - "begun": Thursday 09:30 for 60 min (started before 10:00, ends at 10:30 -> still on -> kept!)
    // - "pinned": Friday 15:00 for 60 min, pinned=true -> kept!
    // - "movable": Friday 17:00 for 60 min, unpinned -> replanned!
    // - "missed": Tuesday 15:00 for 60 min, unpinned -> ended before now -> replanned!
    let assignments = map_of(&[
        ("a", homework("a", "Begun", "2026-09-27", 60)),
        ("b", homework("b", "Pinned", "2026-09-27", 60)),
        ("c", homework("c", "Movable", "2026-09-27", 60)),
        ("d", homework("d", "Missed", "2026-09-27", 60)),
    ]);
    let mut b_begun = flex_block("b-begun", "a", "Begun", 60, &[3]);
    b_begun["start"] = json!("09:30");
    let mut b_pinned = flex_block("b-pinned", "b", "Pinned", 60, &[4]);
    b_pinned["start"] = json!("15:00");
    b_pinned["pinned"] = json!(true);
    let mut b_movable = flex_block("b-movable", "c", "Movable", 60, &[4]);
    b_movable["start"] = json!("17:00");
    let mut b_missed = flex_block("b-missed", "d", "Missed", 60, &[1]);
    b_missed["start"] = json!("15:00");
    let blocks = vec![b_begun, b_pinned, b_movable, b_missed];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();

    let mut input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-24", 10, 0),
    );
    input.everything = true;

    let (body, targets) = match prepare_plan(input).unwrap() {
        PlanPreparation::Ready { body, targets, .. } => (body, targets),
        other => panic!("expected Ready, got {other:?}"),
    };
    assert_eq!(targets, vec!["b-movable", "b-missed"]);
    // Kept sessions are sent to the solver as locked obstacles so nothing lands on them.
    let sent = body["blocks"].as_array().unwrap();
    let begun_sent = sent.iter().find(|b| b["id"] == "b-begun").unwrap();
    let pinned_sent = sent.iter().find(|b| b["id"] == "b-pinned").unwrap();
    assert_eq!(begun_sent["kind"], "locked");
    assert_eq!(pinned_sent["kind"], "locked");
}

#[test]
fn empty_plan_returns_empty_when_everything_is_already_placed() {
    let assignments = map_of(&[("a", homework("a", "Math", "2026-09-27", 60))]);
    let mut placed = flex_block("b1", "a", "Math", 60, &[4]);
    placed["start"] = json!("16:00");
    let blocks = vec![placed];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();
    let input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-24", 10, 0),
    );
    assert_eq!(prepare_plan(input).unwrap(), PlanPreparation::Empty);
}

#[test]
fn place_now_marks_prefer_earliest_and_formats_placed_where_or_no_room() {
    // Parity: test_place_now_takes_the_first_free_gap_from_now_and_says_where
    // and test_place_now_with_no_room_this_week_says_so_and_offers_no_undo.
    set_clock_24h(true);
    let assignments = map_of(&[(
        "sheet",
        homework("sheet", "Math worksheet", "2026-09-27", 30),
    )]);
    let blocks = vec![flex_block(
        "b-sheet",
        "sheet",
        "Math worksheet",
        30,
        &[3, 4, 5, 6],
    )];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();
    let only = vec!["b-sheet".to_string()];

    let mut input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-24", 19, 0),
    );
    input.only = Some(&only);
    input.earliest_first = true;

    let (body, targets, shares, week) = match prepare_plan(input).unwrap() {
        PlanPreparation::Ready {
            body,
            targets,
            shares,
            week,
            ..
        } => (body, targets, shares, week),
        other => panic!("expected Ready, got {other:?}"),
    };
    assert_eq!(targets, vec!["b-sheet"]);
    assert_eq!(body["blocks"][0]["prefer_earliest"], true);
    // Source week stays clean (no prefer_earliest leaked onto saved blocks).
    assert!(week[0].get("prefer_earliest").is_none());

    let placed_trace = json!({
        "placed": [{
            "id": "b-sheet",
            "title": "Math worksheet",
            "kind": "flexible",
            "duration_min": 30,
            "days": [3],
            "start": "20:00",
            "assignment_id": "sheet",
        }],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let placed_answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &placed_trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &shares,
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 19, 0),
            earliest_first: true,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(placed_answer.changed);
    assert_eq!(
        placed_answer.placed_note,
        "Placed Math worksheet on Thu 20:00."
    );
    assert_eq!(
        placed_answer.placed_where,
        "Placed Math worksheet on Thu 20:00."
    );
    assert!(placed_answer.blocks[0].get("prefer_earliest").is_none());

    // When solver cannot place it: says no free time, placed_where stays empty, changed is false.
    let unplaced_trace = json!({
        "placed": [],
        "unplaced": [blocks[0]],
        "explanations": [{"block_id": "b-sheet", "reason": "NO_SLOT_LEFT", "message": "No room left."}],
    });
    let unplaced_answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &unplaced_trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &shares,
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 19, 0),
            earliest_first: true,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(!unplaced_answer.changed);
    assert_eq!(
        unplaced_answer.placed_note,
        "No free time this week for Math worksheet."
    );
    assert_eq!(unplaced_answer.placed_where, "");
    assert_eq!(
        unplaced_answer.needs_time.get("b-sheet"),
        Some(&json!("No room left."))
    );
}

#[test]
fn latest_unplaced_reason_replaces_stale_no_longer_fits_note_and_clears_when_placed() {
    // Parity: test_the_reason_homework_has_no_time_is_the_latest_one.
    let assignments = map_of(&[("math", homework("math", "Math", "2026-09-21T23:59", 60))]);
    let blocks = vec![flex_block("b-math", "math", "Math", 60, &[0])];
    let targets = vec!["b-math".to_string()];
    let stale_needs = map_of(&[(
        "b-math",
        json!("Math no longer fits Monday at 15:15: Club is there now."),
    )]);

    let unplaced_trace = json!({
        "placed": [],
        "unplaced": [blocks[0]],
        "explanations": [{
            "block_id": "b-math",
            "reason": "DEADLINE_MISS",
            "message": "No room on Monday before the deadline.",
        }],
    });
    let after_miss = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &blocks,
            trace: &unplaced_trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &[],
            needs_time: &stale_needs,
            clock: clock("2026-09-21", 8, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert_eq!(
        after_miss.needs_time.get("b-math"),
        Some(&json!("No room on Monday before the deadline."))
    );

    // Once placed, the reason is removed from needs_time.
    let placed_trace = json!({
        "placed": [{
            "id": "b-math",
            "title": "Math",
            "kind": "flexible",
            "duration_min": 60,
            "days": [0],
            "start": "16:00",
            "assignment_id": "math",
        }],
        "unplaced": [],
        "explanations": [],
    });
    let after_place = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &blocks,
            trace: &placed_trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &[],
            needs_time: &after_miss.needs_time,
            clock: clock("2026-09-21", 8, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(after_place.needs_time.is_empty());
}

#[test]
fn overdue_blocks_unlink_for_solve_and_restore_assignment_identity_or_rollback_on_failure() {
    let assignments = map_of(&[
        (
            "late1",
            homework("late1", "Late existing", "2026-09-20", 60),
        ),
        ("late2", homework("late2", "Late new", "2026-09-20", 45)),
        ("late3", homework("late3", "Late placed", "2026-09-20", 30)),
    ]);
    let mut existing_late = flex_block("b-existing", "late1", "Late existing", 60, &[0]);
    existing_late["start"] = json!("16:00");
    existing_late["pinned"] = json!(true);
    let new_late = flex_block("b-new", "late2", "Late new", 45, &[3, 4, 5, 6]);
    let placed_late = flex_block("b-ok", "late3", "Late placed", 30, &[3, 4, 5, 6]);
    let blocks = vec![existing_late.clone(), new_late.clone(), placed_late.clone()];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();
    let only = vec![
        "b-existing".to_string(),
        "b-new".to_string(),
        "b-ok".to_string(),
    ];
    let overdue = vec![
        "b-existing".to_string(),
        "b-new".to_string(),
        "b-ok".to_string(),
    ];

    let mut input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-24", 10, 0), // Thursday = day 3
    );
    input.only = Some(&only);
    input.overdue = Some(&overdue);

    let (body, targets, week) = match prepare_plan(input).unwrap() {
        PlanPreparation::Ready {
            body,
            targets,
            week,
            ..
        } => (body, targets, week),
        other => panic!("expected Ready, got {other:?}"),
    };
    // Solve payload strips assignment_id/latest/earliest/pinned and sets prefer_earliest + days 3..7.
    for sent in body["blocks"].as_array().unwrap() {
        assert_eq!(sent["assignment_id"], Value::Null);
        assert_eq!(sent["latest"], Value::Null);
        assert_eq!(sent["earliest"], Value::Null);
        assert_eq!(sent["pinned"], false);
        assert_eq!(sent["prefer_earliest"], true);
        assert_eq!(sent["days"], json!([3, 4, 5, 6]));
    }
    // Source week keeps assignment_id intact.
    assert_eq!(week[2]["assignment_id"], "late3");

    // Solver places only b-ok (without assignment_id because payload stripped it); b-existing & b-new fail.
    let trace = json!({
        "placed": [{
            "id": "b-ok",
            "title": "Late placed",
            "kind": "flexible",
            "duration_min": 30,
            "days": [3],
            "start": "11:00",
            "assignment_id": null,
        }],
        "unplaced": [
            {"id": "b-existing", "duration_min": 60, "days": [3, 4, 5, 6]},
            {"id": "b-new", "duration_min": 45, "days": [3, 4, 5, 6]},
        ],
        "explanations": [],
    });
    let new_left = vec!["b-new".to_string()];
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &[],
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 10, 0),
            earliest_first: false,
            overdue: Some(&overdue),
            new_left: Some(&new_left),
        },
        counter_ids(),
    )
    .unwrap();
    // b-new was newly created and failed -> dropped.
    let ids: Vec<&str> = answer
        .blocks
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, vec!["b-existing", "b-ok"]);
    // b-existing failed -> restored from original_blocks (keeps start, pinned=true and days=[0]).
    assert_eq!(answer.blocks[0]["start"], "16:00");
    assert_eq!(answer.blocks[0]["pinned"], true);
    assert_eq!(answer.blocks[0]["days"], json!([0]));
    // b-ok placed -> keeps assignment_id="late3" on BOTH blocks and trace["placed"]!
    assert_eq!(answer.blocks[1]["assignment_id"], "late3");
    assert_eq!(answer.blocks[1]["start"], "11:00");
    assert_eq!(answer.trace["placed"][0]["assignment_id"], "late3");
}

#[test]
fn auto_split_inflates_for_solve_uses_preinflation_work_lengths_and_keeps_sibling_state() {
    // Parity: test_the_solver_is_asked_to_reserve_the_breaks_as_well and
    // test_auto_split_keeps_a_sibling_sessions_solver_start_and_cleared_pin.
    let prefs = json!({
        "auto_split_pomodoro": true,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
    });
    let assignments = map_of(&[
        ("essay", homework("essay", "Essay", "2026-09-27", 90)),
        ("quiz", homework("quiz", "Quiz", "2026-09-27", 30)),
    ]);
    let school = locked_block("school", "School", "08:00", 360, &[0]);
    let essay = flex_block("b-essay", "essay", "Essay", 90, &[0, 1, 2, 3, 4, 5, 6]);
    let quiz = flex_block("b-quiz", "quiz", "Quiz", 30, &[0, 1, 2, 3, 4, 5, 6]);
    let blocks = vec![school.clone(), essay.clone(), quiz.clone()];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole: Vec<String> = Vec::new();

    let mut prep_input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-21", 7, 0),
    );
    prep_input.preferences = Some(&prefs);

    let (body, targets, week) = match prepare_plan(prep_input).unwrap() {
        PlanPreparation::Ready {
            body,
            targets,
            week,
            ..
        } => (body, targets, week),
        other => panic!("expected Ready, got {other:?}"),
    };
    // 90 min work + two 15-min breaks = 120 min sent to solver; source `week` stays 90 min.
    let sent_essay = body["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == "b-essay")
        .unwrap();
    assert_eq!(sent_essay["duration_min"], 120);
    let source_essay = week.iter().find(|b| b["id"] == "b-essay").unwrap();
    assert_eq!(source_essay["duration_min"], 90);

    // Solver places quiz (30 min) at Tue 15:30 and inflated essay (120 min) at Tue 16:00.
    let placed_trace = json!({
        "placed": [
            {"id": "school", "title": "School", "kind": "locked", "start": "08:00", "days": [0], "duration_min": 360},
            {"id": "b-quiz", "title": "Quiz", "kind": "flexible", "start": "15:30", "days": [1], "duration_min": 30, "assignment_id": "quiz"},
            {"id": "b-essay", "title": "Essay", "kind": "flexible", "start": "16:00", "days": [1], "duration_min": 120, "assignment_id": "essay"},
        ],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &placed_trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: Some(&prefs),
            shares: &[],
            needs_time: &empty_needs,
            clock: clock("2026-09-21", 7, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(answer.changed);
    // Pre-split counts: 2 blocks placed, 0 waiting, first at Tue 15:30.
    assert_eq!(answer.plan_counts, (2, 0));
    assert_eq!(answer.plan_open, 0);
    assert_eq!(answer.plan_first, Some((1, 15 * 60 + 30)));
    assert_eq!(answer.split_count, 1);
    assert_eq!(answer.split_note, " Split 1 into focus chunks.");
    assert_eq!(
        answer.placed_note,
        "Placed 2 homework blocks. Split 1 into focus chunks."
    );

    // Essay split into 3 x 30 min work + 2 x 15 min break; quiz kept start 15:30 on day 1.
    let work: Vec<&Value> = answer
        .blocks
        .iter()
        .filter(|b| b.get("pomodoro_role") == Some(&json!("work")))
        .collect();
    let breaks: Vec<&Value> = answer
        .blocks
        .iter()
        .filter(|b| b.get("pomodoro_role") == Some(&json!("break")))
        .collect();
    assert_eq!(work.len(), 3);
    assert_eq!(breaks.len(), 2);
    assert_eq!(
        work.iter()
            .map(|b| b["duration_min"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![30, 30, 30]
    );
    let kept_quiz = answer.blocks.iter().find(|b| b["id"] == "b-quiz").unwrap();
    assert_eq!(kept_quiz["start"], "15:30");
    assert_eq!(kept_quiz["days"], json!([1]));

    // Direct apply_auto_split with a pinned sibling whose pin was cleared by apply_plan keeps cleared pin.
    let mut pinned_quiz = quiz.clone();
    pinned_quiz["start"] = json!("15:00");
    pinned_quiz["days"] = json!([0]);
    pinned_quiz["pinned"] = json!(true);
    let pinned_sources = vec![school.clone(), essay.clone(), pinned_quiz];
    let mut after_apply_blocks = vec![school, essay, quiz];
    after_apply_blocks[1]["start"] = json!("16:00");
    after_apply_blocks[1]["days"] = json!([1]);
    after_apply_blocks[1]["duration_min"] = json!(120); // inflated by solver
    // quiz lost its start and pin in apply_plan; apply_auto_split must keep it unpinned and unstarted.
    let unplaced_trace = json!({
        "placed": [
            {"id": "school", "start": "08:00", "days": [0], "duration_min": 360},
            {"id": "b-essay", "start": "16:00", "days": [1], "duration_min": 120},
        ],
        "unplaced": [{"id": "b-quiz", "duration_min": 30, "days": [0, 1, 2, 3, 4]}],
    });
    let split = apply_auto_split(
        &after_apply_blocks,
        &unplaced_trace,
        Some(&pinned_sources),
        Some(&prefs),
        counter_ids(),
    )
    .unwrap();
    assert_eq!(split.count, 1);
    let leftover = split.blocks.iter().find(|b| b["id"] == "b-quiz").unwrap();
    assert!(leftover.get("start").is_none());
    assert!(leftover.get("pinned").is_none());
}

#[test]
fn pre_split_counts_name_uncovered_remainders_against_pre_save_basis() {
    // Parity: test_the_plan_notice_names_the_minutes_it_could_not_place (5 min pinned -> 55 needed,
    // Plan places 45, 10 min remainder named; waiting_only = 0).
    let mut essay_hw = homework("essay", "History essay", "2026-09-27", 60);
    essay_hw["planned_min"] = json!(5);
    essay_hw["unplanned_min"] = json!(55);
    let assignments = map_of(&[("essay", essay_hw)]);

    let mut pinned_5 = flex_block("b-pin", "essay", "History essay", 5, &[3]);
    pinned_5["start"] = json!("19:30");
    pinned_5["pinned"] = json!(true);
    let basis = vec![pinned_5.clone()];
    let rest_45 = flex_block(
        "essay-rest-2026-09-21",
        "essay",
        "History essay",
        45,
        &[3, 4, 5, 6],
    );
    let source_week = vec![pinned_5.clone(), rest_45];
    let targets = vec!["essay-rest-2026-09-21".to_string()];
    let trace = json!({
        "placed": [{
            "id": "essay-rest-2026-09-21",
            "title": "History essay",
            "kind": "flexible",
            "duration_min": 45,
            "days": [4],
            "start": "16:00",
            "assignment_id": "essay",
        }],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &basis,
            source_week: &source_week,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &basis,
            week_start: WEEK,
            preferences: None,
            shares: &[],
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 19, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert_eq!(answer.plan_counts, (1, 0));
    assert_eq!(
        answer.plan_remainders,
        vec![("History essay".to_string(), 10)]
    );
    assert_eq!(
        answer.placed_note,
        "Placed 1 homework block. History essay still has 10 min with no time."
    );
}

#[test]
fn the_remainder_is_counted_before_focus_splitting_not_after() {
    // 105 min of homework with one 90-min session. The solver is asked for 120 min (the session
    // plus its breaks), so as this plan left the week the session holds 120 min and no remainder
    // is named. Splitting then makes 3 x 30 min of work and 2 breaks that carry no homework, so
    // counted after splitting only 90 min would be covered and 15 min would wrongly be named.
    let prefs = json!({
        "auto_split_pomodoro": true,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
    });
    let mut hw = homework("essay", "History essay", "2026-09-27", 105);
    hw["planned_min"] = json!(0);
    hw["unplanned_min"] = json!(105);
    let assignments = map_of(&[("essay", hw)]);
    let session = flex_block("b-essay", "essay", "History essay", 90, &[3, 4, 5, 6]);
    let week = vec![session];
    let basis: Vec<Value> = Vec::new();
    let targets = vec!["b-essay".to_string()];
    let trace = json!({
        "placed": [{
            "id": "b-essay", "title": "History essay", "kind": "flexible", "start": "16:00",
            "days": [4], "duration_min": 120, "assignment_id": "essay",
        }],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &basis,
            source_week: &week,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &basis,
            week_start: WEEK,
            preferences: Some(&prefs),
            shares: &[],
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 12, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert_eq!(answer.split_count, 1);
    assert_eq!(answer.plan_remainders, Vec::<(String, i64)>::new());
    assert_eq!(
        answer.placed_note,
        "Placed 1 homework block. Split 1 into focus chunks."
    );
}

#[test]
fn sentences_and_first_placed_match_desktop_rules() {
    assert_eq!(left_sentence(&[]), "");
    let one = vec![("History essay".to_string(), 10)];
    let two = vec![
        ("History essay".to_string(), 10),
        ("Science fair poster".to_string(), 595),
    ];
    let three = vec![
        ("History essay".to_string(), 10),
        ("Science fair poster".to_string(), 595),
        ("Math".to_string(), 5),
    ];
    assert_eq!(
        left_sentence(&one),
        " History essay still has 10 min with no time."
    );
    assert_eq!(
        left_sentence(&two),
        " History essay still has 10 min with no time. Science fair poster still has 9 h 55 min with no time."
    );
    assert_eq!(
        left_sentence(&three),
        " History essay still has 10 min with no time. Science fair poster still has 9 h 55 min with no time. And 1 more."
    );
    assert_eq!(
        plan_sentence(0, 1, &[]),
        "Nothing placed. 1 with no time yet."
    );
    assert_eq!(plan_sentence(1, 0, &[]), "Placed 1 homework block.");
    assert_eq!(
        plan_sentence(2, 1, &one),
        "Placed 2 homework blocks. 1 with no time yet. History essay still has 10 min with no time."
    );

    // first_placed picks earliest (day, minute) among targets only.
    let trace = json!({
        "placed": [
            {"id": "locked", "start": "08:00", "days": [0]},
            {"id": "t2", "start": "18:30", "days": [2]},
            {"id": "t1", "start": "14:15", "days": [2]},
            {"id": "t3", "start": "09:00", "days": [3]},
        ]
    });
    assert_eq!(
        first_placed(&trace, &["t1".into(), "t2".into(), "t3".into()]).unwrap(),
        Some((2, 14 * 60 + 15))
    );
    assert_eq!(first_placed(&trace, &["missing".into()]).unwrap(), None);

    // place_now_sentence respects non-Monday week start and missing title/start fallback.
    set_clock_24h(true);
    let placed_wed_week = json!({"title": "Bio", "start": "17:15", "days": [1]});
    // Week starting Wednesday 2026-09-23: day 0 is Wed, day 1 is Thu.
    assert_eq!(
        place_now_sentence(&placed_wed_week, "2026-09-23").unwrap(),
        "Placed Bio on Thu 17:15."
    );
    assert_eq!(
        place_now_sentence(&json!({}), WEEK).unwrap(),
        "No free time this week for this homework."
    );
}

#[test]
fn split_whole_skips_fair_share_and_locked_blocks_keep_missed_days_in_trace() {
    // Same far-out spread homework as fair-share test, but its session id is in `split_whole`,
    // so `prepare_plan` keeps it whole (120 min) with no share note.
    let mut sci = homework("sci", "Science project", "2026-10-07T23:59", 120);
    sci["spread"] = json!("spread");
    let assignments = map_of(&[("sci", sci)]);
    let mut school = locked_block("school", "School", "08:00", 360, &[0, 1, 2, 3, 4]);
    school["missed_days"] = json!([2]);
    let session = flex_block(
        "sci-1",
        "sci",
        "Science project",
        120,
        &[0, 1, 2, 3, 4, 5, 6],
    );
    let blocks = vec![school.clone(), session];
    let saved_weeks: Vec<String> = Vec::new();
    let split_whole = vec!["sci-1".to_string()];

    let input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &saved_weeks,
        &split_whole,
        clock("2026-09-26", 7, 0),
    );
    let (targets, shares, week) = match prepare_plan(input).unwrap() {
        PlanPreparation::Ready {
            targets,
            shares,
            week,
            ..
        } => (targets, shares, week),
        other => panic!("expected Ready, got {other:?}"),
    };
    assert!(shares.is_empty());
    assert_eq!(targets, vec!["sci-1"]);
    let kept = week.iter().find(|b| b["id"] == "sci-1").unwrap();
    assert_eq!(kept["duration_min"], 120);

    // On apply, solver trace omits missed_days on School; answer restores School from sources.
    let trace = json!({
        "placed": [
            {"id": "school", "title": "School", "kind": "locked", "start": "08:00", "days": [0, 1, 2, 3, 4], "duration_min": 360},
            {"id": "sci-1", "title": "Science project", "kind": "flexible", "start": "09:00", "days": [5], "duration_min": 120, "assignment_id": "sci"},
        ],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &week,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &shares,
            needs_time: &empty_needs,
            clock: clock("2026-09-26", 7, 0),
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    let traced_school = answer.trace["placed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == "school")
        .unwrap();
    assert_eq!(traced_school["missed_days"], json!([2]));
}

#[test]
fn unchanged_validated_blocks_report_changed_false_and_return_originals() {
    // Re-running Place now on an already-placed session that lands at the exact same time reports
    // changed=false (so the window offers no Undo).
    let assignments = map_of(&[(
        "sheet",
        homework("sheet", "Math worksheet", "2026-09-27", 30),
    )]);
    let mut placed = flex_block("b-sheet", "sheet", "Math worksheet", 30, &[3]);
    placed["start"] = json!("20:00");
    let blocks = vec![placed];
    let targets = vec!["b-sheet".to_string()];
    let trace = json!({
        "placed": [{
            "id": "b-sheet",
            "title": "Math worksheet",
            "kind": "flexible",
            "duration_min": 30,
            "days": [3],
            "start": "20:00",
            "assignment_id": "sheet",
        }],
        "unplaced": [],
        "explanations": [],
    });
    let empty_needs = Map::new();
    let answer = apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &blocks,
            trace: &trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares: &[],
            needs_time: &empty_needs,
            clock: clock("2026-09-24", 19, 0),
            earliest_first: true,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
    .unwrap();
    assert!(!answer.changed);
    assert_eq!(answer.blocks, blocks);
}

/// One placed homework session answered by a one-row trace, for the refusal tests below.
fn answer_for(
    trace: &Value,
    shares: &[Value],
    now: PlanClock<'_>,
) -> Result<flexweek_app::session::plan::PlanAnswer, String> {
    let assignments = map_of(&[(
        "sheet",
        homework("sheet", "Math worksheet", "2026-09-27", 30),
    )]);
    let mut placed = flex_block("b-sheet", "sheet", "Math worksheet", 30, &[3]);
    placed["start"] = json!("20:00");
    let blocks = vec![placed];
    let targets = vec!["b-sheet".to_string()];
    let empty_needs = Map::new();
    apply_plan_answer(
        PlanAnswerInput {
            original_blocks: &blocks,
            source_week: &blocks,
            trace,
            targets: &targets,
            assignments: &assignments,
            assignments_basis: &blocks,
            week_start: WEEK,
            preferences: None,
            shares,
            needs_time: &empty_needs,
            clock: now,
            earliest_first: false,
            overdue: None,
            new_left: None,
        },
        counter_ids(),
    )
}

fn placed_row(extra: Value) -> Value {
    let mut row = json!({
        "id": "b-sheet",
        "title": "Math worksheet",
        "kind": "flexible",
        "duration_min": 30,
        "days": [3],
        "start": "20:00",
        "assignment_id": "sheet",
    });
    for (key, value) in extra.as_object().unwrap() {
        row[key] = value.clone();
    }
    row
}

#[test]
fn a_wrong_shaped_trace_row_or_block_is_refused_not_skipped() {
    // A placed row that is not an object, or whose start or days are the wrong kind, is refused;
    // missing and null fields stay supported.
    let targets = vec!["b-sheet".to_string()];
    assert!(first_placed(&json!({"placed": [0]}), &targets).is_err());
    assert!(first_placed(&json!({"placed": ["b-sheet"]}), &targets).is_err());
    let rows = [
        json!({"start": 2000}),
        json!({"days": {"first": 3}}),
        json!({"days": ["Thu"]}),
        json!({"duration_min": "30"}),
    ];
    for extra in rows {
        let trace = json!({"placed": [placed_row(extra)]});
        assert!(first_placed(&trace, &targets).is_err(), "{trace}");
        assert!(
            answer_for(&trace, &[], clock("2026-09-24", 19, 0)).is_err(),
            "{trace}"
        );
    }
    let loose = json!({"placed": [placed_row(json!({"start": null, "days": null}))]});
    assert_eq!(first_placed(&loose, &targets).unwrap(), None);
    let bare = json!({"placed": [{"id": "b-sheet"}]});
    assert_eq!(first_placed(&bare, &targets).unwrap(), None);

    // Place now: a block with a start and an object for days is a refusal, not "no free time".
    let wrong = json!({"title": "Bio", "start": "17:15", "days": {"first": 1}});
    assert!(place_now_sentence(&wrong, WEEK).is_err());
    let wrong_start = json!({"title": "Bio", "start": 1715, "days": [1]});
    assert!(place_now_sentence(&wrong_start, WEEK).is_err());
    let wrong_title = json!({"title": 7, "start": "17:15", "days": [1]});
    assert!(place_now_sentence(&wrong_title, WEEK).is_err());
    let nulls = json!({"title": null, "start": null, "days": null});
    assert_eq!(
        place_now_sentence(&nulls, WEEK).unwrap(),
        "No free time this week for this homework."
    );
}

#[test]
fn clock_fields_outside_a_real_time_of_day_are_refused_before_any_arithmetic() {
    let trace = json!({"placed": [placed_row(json!({}))], "unplaced": [], "explanations": []});
    let huge = PlanClock {
        today_iso: "2026-09-24",
        hour: 4_611_686_018_427_387_904,
        minute: 0,
        second: 0,
        microsecond: 0,
    };
    assert!(answer_for(&trace, &[], huge).is_err());

    let bad = [
        (24, 0, 0, 0),
        (-1, 0, 0, 0),
        (0, 60, 0, 0),
        (0, -1, 0, 0),
        (0, 0, 60, 0),
        (0, 0, -1, 0),
        (0, 0, 0, 1_000_000),
        (0, 0, 0, -1),
    ];
    let assignments = map_of(&[(
        "sheet",
        homework("sheet", "Math worksheet", "2026-09-27", 30),
    )]);
    let blocks = vec![flex_block("b-sheet", "sheet", "Math worksheet", 30, &[3])];
    let none: Vec<String> = Vec::new();
    for (hour, minute, second, microsecond) in bad {
        let now = PlanClock {
            today_iso: "2026-09-24",
            hour,
            minute,
            second,
            microsecond,
        };
        assert!(
            answer_for(&trace, &[], now).is_err(),
            "apply {hour}:{minute}:{second}.{microsecond}"
        );
        let input = base_plan_input(WEEK, &blocks, &assignments, &blocks, &none, &none, now);
        assert!(
            prepare_plan(input).is_err(),
            "prepare {hour}:{minute}:{second}.{microsecond}"
        );
    }

    let last_moment = PlanClock {
        today_iso: "2026-09-24",
        hour: 23,
        minute: 59,
        second: 59,
        microsecond: 999_999,
    };
    assert!(answer_for(&trace, &[], last_moment).is_ok());
    let input = base_plan_input(
        WEEK,
        &blocks,
        &assignments,
        &blocks,
        &none,
        &none,
        last_moment,
    );
    assert!(prepare_plan(input).is_ok());
}

#[test]
fn share_minutes_too_large_to_add_are_refused() {
    let trace = json!({"placed": [placed_row(json!({}))], "unplaced": [], "explanations": []});
    let share = |this_week: i64, left: i64| json!({"assignment_id": "sheet", "this_week_min": this_week, "left_min": left});
    let now = clock("2026-09-24", 19, 0);
    assert!(answer_for(&trace, &[share(i64::MAX, 1)], now).is_err());
    assert!(answer_for(&trace, &[share(i64::MIN, -1)], now).is_err());
    // A sane share still works: 20 + 10 minutes, 30 placed, nothing left.
    let answer = answer_for(&trace, &[share(20, 10)], now).unwrap();
    assert_eq!(answer.trace["shares"][0]["this_week_min"], 30);
    assert_eq!(answer.trace["shares"][0]["left_min"], 0);
    // Placed minutes are summed with the same care.
    let two = json!({"placed": [
        placed_row(json!({"duration_min": i64::MAX})),
        placed_row(json!({"duration_min": 1})),
    ], "unplaced": [], "explanations": []});
    assert!(answer_for(&two, &[share(0, 0)], now).is_err());
}

#[test]
fn every_entry_of_a_day_list_must_be_a_whole_number() {
    // Only the first day is used, but a later entry that is not a day is still a refusal.
    let bad = json!({"title": "Bio", "start": "17:15", "days": [1, {}]});
    assert!(place_now_sentence(&bad, WEEK).is_err());
    let targets = vec!["b-sheet".to_string()];
    let trace = json!({"placed": [placed_row(json!({"days": [3, "Fri"]}))]});
    assert!(first_placed(&trace, &targets).is_err());
    assert!(answer_for(&trace, &[], clock("2026-09-24", 19, 0)).is_err());
    // Missing, null, empty and all-number lists keep working.
    set_clock_24h(true);
    let good = json!({"title": "Bio", "start": "17:15", "days": [1, 2]});
    assert_eq!(
        place_now_sentence(&good, WEEK).unwrap(),
        "Placed Bio on Tue 17:15."
    );
    let empty = json!({"title": "Bio", "start": "17:15", "days": []});
    assert_eq!(
        place_now_sentence(&empty, WEEK).unwrap(),
        "No free time this week for Bio."
    );
}
