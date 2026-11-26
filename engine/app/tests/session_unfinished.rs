//! Unfinished work and planner count rules (P4 group 5, slice 5C).
//! Expected values come from the product rules and the desktop parity tests
//! (`test_unfinished_homework_keeps_its_assignment`, `test_plan_left_over_homework`,
//! `test_plan_leftover_sentences`).

use flexweek_app::session::unfinished::{
    ClockNow, HomeworkCountsInput, UnfinishedInput, UnfinishedPlan, UnfinishedPlanInput,
    UnfinishedPreview, UnfinishedPreviewInput, homework_counts, left_unfinished_items,
    plan_unfinished, unfinished_items, unfinished_preview,
};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-09-21"; // Monday
const PREV_WEEK: &str = "2026-09-14"; // Monday before WEEK
const NEXT_WEEK: &str = "2026-09-28"; // Monday after WEEK

fn assignment(id: &str, title: &str, due: &str, estimate_min: i64) -> Value {
    json!({
        "id": id,
        "title": title,
        "due": due,
        "estimate_min": estimate_min,
        "focus_minutes": 0,
        "completed": false,
        "priority": 3,
        "energy": "medium",
        "category": "assignments",
        "session_weeks": [],
    })
}

fn hw_block(
    id: &str,
    assignment_id: &str,
    day: i64,
    start: Option<&str>,
    duration_min: i64,
) -> Value {
    let mut fields = Map::new();
    fields.insert("id".into(), json!(id));
    fields.insert("kind".into(), json!("flexible"));
    fields.insert("assignment_id".into(), json!(assignment_id));
    fields.insert("title".into(), json!(assignment_id));
    fields.insert("days".into(), json!([day]));
    if let Some(start) = start {
        fields.insert("start".into(), json!(start));
    }
    fields.insert("duration_min".into(), json!(duration_min));
    fields.insert("completed".into(), json!(false));
    Value::Object(fields)
}

fn pinned(mut block: Value) -> Value {
    block["pinned"] = json!(true);
    block
}

fn done(mut block: Value) -> Value {
    block["completed"] = json!(true);
    block
}

fn map_of(items: Vec<Value>) -> Map<String, Value> {
    let mut map = Map::new();
    for item in items {
        let id = item["id"].as_str().unwrap().to_string();
        map.insert(id, item);
    }
    map
}

#[test]
fn homework_counts_separates_waiting_uncovered_missed_and_pinned_in_an_ended_week() {
    // Three assignments in PREV_WEEK, viewed from WEEK (PREV_WEEK is over):
    // 1. "missed_hw": 60m unpinned session on Wed 10:00 -> missed (waiting_min=60, missed_min=60, uncovered=0).
    // 2. "pinned_hw": 90m estimate, one 60m pinned session on Wed 15:00 -> pinned_min=60, uncovered=90,
    //    remainder shows only the 30m not covered by the ended-week pin.
    // 3. "capped_hw": 90m estimate, 30m focus (60m still needed), one 30m unpinned missed session +
    //    one 60m pinned past session -> missed_min=30, pinned_min capped to min(60, 60 - 30) = 30.
    let mut capped = assignment("capped_hw", "Capped", "2026-09-20T23:59", 90);
    capped["focus_minutes"] = json!(30);
    let assignments = map_of(vec![
        assignment("missed_hw", "Missed", "2026-09-20T23:59", 60),
        assignment("pinned_hw", "Pinned", "2026-09-20T23:59", 90),
        capped,
    ]);
    let blocks = vec![
        hw_block("b-miss", "missed_hw", 2, Some("10:00"), 60),
        pinned(hw_block("b-pin", "pinned_hw", 2, Some("15:00"), 60)),
        hw_block("b-cap-miss", "capped_hw", 1, Some("10:00"), 30),
        pinned(hw_block("b-cap-pin", "capped_hw", 2, Some("15:00"), 60)),
    ];

    let counts = homework_counts(HomeworkCountsInput {
        week_start: PREV_WEEK,
        first_weekday: 0,
        blocks: &blocks,
        assignments: &assignments,
        assignments_basis: &blocks,
        now: ClockNow::at(WEEK, 9, 0),
    })
    .unwrap();

    assert!(counts.plan_can_place);
    assert_eq!(counts.missed_minutes.get("missed_hw"), Some(&60));
    assert_eq!(counts.missed_minutes.get("capped_hw"), Some(&30));
    assert_eq!(counts.pinned_past_minutes.get("pinned_hw"), Some(&60));
    assert_eq!(counts.pinned_past_minutes.get("capped_hw"), Some(&60));

    let by_id = |id: &str| {
        counts
            .items
            .iter()
            .find(|item| item.assignment_id == id)
            .unwrap()
    };
    let m = by_id("missed_hw");
    assert_eq!((m.minutes, m.waiting_min, m.uncovered_min), (60, 60, 0));
    assert_eq!((m.missed_min, m.pinned_min), (Some(60), None));

    let p = by_id("pinned_hw");
    assert_eq!((p.minutes, p.waiting_min, p.uncovered_min), (90, 0, 90));
    assert_eq!((p.missed_min, p.pinned_min), (None, Some(60)));

    let c = by_id("capped_hw");
    assert_eq!((c.minutes, c.waiting_min, c.uncovered_min), (60, 30, 30));
    assert_eq!((c.missed_min, c.pinned_min), (Some(30), Some(30)));

    // Remainders subtract ended-week pinned minutes: pinned_hw keeps 90 - 60 = 30; capped_hw has 30 <= 60 so omitted.
    assert_eq!(counts.remainders.len(), 1);
    assert_eq!(counts.remainders[0].assignment_id, "pinned_hw");
    assert_eq!(counts.remainders[0].minutes, 30);

    // Every missed and pinned-past block is reported in missed_block_ids.
    for id in ["b-miss", "b-pin", "b-cap-miss", "b-cap-pin"] {
        assert!(counts.missed_block_ids.iter().any(|found| found == id));
    }
}

#[test]
fn homework_counts_omits_ended_week_tags_on_current_week_and_respects_first_weekday() {
    // Parity with test_overdue_homework_still_asks_for_the_hour_that_never_had_a_time:
    // Essay estimate 120, pinned 60m on Wed 15:00, due Fri 23:59, viewed Saturday 10:00 of the same week.
    let assignments = map_of(vec![assignment("essay", "Essay", "2026-09-25T23:59", 120)]);
    let blocks = vec![pinned(hw_block("b-essay", "essay", 2, Some("15:00"), 60))];

    let counts = homework_counts(HomeworkCountsInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &blocks,
        assignments: &assignments,
        assignments_basis: &blocks,
        now: ClockNow::at("2026-09-26", 10, 0),
    })
    .unwrap();

    assert_eq!(
        counts.to_json()["needed"],
        json!([{"assignment_id": "essay", "title": "Essay", "minutes": 120, "period": "this_week"}])
    );
    assert!(counts.missed_minutes.is_empty());
    assert!(counts.pinned_past_minutes.is_empty());
    // Not an ended week, so all 120 uncovered minutes show as a remainder.
    assert_eq!(counts.remainders.len(), 1);
    assert_eq!(counts.remainders[0].minutes, 120);

    // Non-Monday week starting Wednesday 2026-09-23 (first_weekday = 2):
    // Tuesday 2026-09-29 is still inside the shown week -> no ended-week tags;
    // Wednesday 2026-09-30 starts the next shown week -> ended-week pinned_min appears.
    let wed_start = "2026-09-23";
    let wed_blocks = vec![pinned(hw_block("b-wed", "essay", 0, Some("15:00"), 60))];
    let still_current = homework_counts(HomeworkCountsInput {
        week_start: wed_start,
        first_weekday: 2,
        blocks: &wed_blocks,
        assignments: &assignments,
        assignments_basis: &wed_blocks,
        now: ClockNow::at("2026-09-29", 18, 0),
    })
    .unwrap();
    assert_eq!(still_current.items[0].pinned_min, None);

    let now_over = homework_counts(HomeworkCountsInput {
        week_start: wed_start,
        first_weekday: 2,
        blocks: &wed_blocks,
        assignments: &assignments,
        assignments_basis: &wed_blocks,
        now: ClockNow::at("2026-09-30", 8, 0),
    })
    .unwrap();
    assert_eq!(now_over.items[0].pinned_min, Some(60));
}

#[test]
fn homework_counts_reuses_one_done_time_rule_and_handles_under_grid_and_completed() {
    // Parity with test_a_focus_timer_shortens_what_is_still_needed and test_a_finished_homework_has_no_minutes_left.
    let mut timer = assignment("timer", "Timer", "2026-09-27T23:59", 60);
    timer["focus_minutes"] = json!(25);

    let mut ticked_higher = assignment("ticked", "Ticked", "2026-09-27T23:59", 60);
    ticked_higher["focus_minutes"] = json!(15);

    let mut short = assignment("short", "Short", "2026-09-27T23:59", 60);
    short["focus_minutes"] = json!(50);

    let mut done_hw = assignment("done", "Done", "2026-09-27T23:59", 60);
    done_hw["completed"] = json!(true);

    let assignments = map_of(vec![timer, ticked_higher, short, done_hw]);
    let blocks = vec![done(hw_block("b-tick", "ticked", 0, Some("09:00"), 30))];

    let counts = homework_counts(HomeworkCountsInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &blocks,
        assignments: &assignments,
        assignments_basis: &blocks,
        now: ClockNow::at(WEEK, 8, 0),
    })
    .unwrap();

    // Timer: focus 25, done sessions 0 -> done_time 25, uncovered 35, plannable 30 (two quarter hours).
    let t = counts.per_assignment["timer"];
    assert_eq!(
        (
            t.done_sessions_min,
            t.done_time_min,
            t.uncovered_min,
            t.remaining_min
        ),
        (0, 25, 35, 30)
    );

    // Ticked: focus 15, done sessions 30 -> done_time max(15, 30) = 30 (never sum 45!), uncovered 30.
    let tk = counts.per_assignment["ticked"];
    assert_eq!(
        (
            tk.done_sessions_min,
            tk.done_time_min,
            tk.uncovered_min,
            tk.remaining_min
        ),
        (30, 30, 30, 30)
    );

    // Short: 10 min left, under the 15-min grid -> uncovered 10, remaining 0.
    let sh = counts.per_assignment["short"];
    assert_eq!(
        (
            sh.done_sessions_min,
            sh.done_time_min,
            sh.uncovered_min,
            sh.remaining_min
        ),
        (0, 50, 10, 0)
    );

    // Completed homework needs nothing.
    let dn = counts.per_assignment["done"];
    assert_eq!(
        (dn.uncovered_min, dn.remaining_min, dn.overdue),
        (0, 0, false)
    );
    assert!(!counts.items.iter().any(|item| item.assignment_id == "done"));
    assert!(!counts.remainders.iter().any(|r| r.assignment_id == "done"));

    // Only an under-grid homework with no waiting sessions -> plan_can_place is false.
    let only_short = map_of(vec![{
        let mut a = assignment("short", "Short", "2026-09-27T23:59", 60);
        a["focus_minutes"] = json!(50);
        a
    }]);
    let short_counts = homework_counts(HomeworkCountsInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &only_short,
        assignments_basis: &[],
        now: ClockNow::at(WEEK, 8, 0),
    })
    .unwrap();
    assert!(!short_counts.plan_can_place);
}

#[test]
fn overdue_check_matches_23_59_end_of_day_boundary() {
    let mut done_past = assignment("done", "Done", "2026-09-20T10:00", 60);
    done_past["completed"] = json!(true);
    let assignments = map_of(vec![
        assignment("eod", "End of day", "2026-09-26T23:59", 60),
        assignment("date_only", "Date only", "2026-09-26", 60),
        assignment("exact", "Exact", "2026-09-26T23:59", 60),
        assignment("earlier", "Earlier", "2026-09-26T10:00", 60),
        done_past,
    ]);

    // At 23:59 on 2026-09-26, 23:59 and date-only due stamps are 1440 > 1439, so not yet overdue.
    let at_2359 = homework_counts(HomeworkCountsInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        now: ClockNow::at("2026-09-26", 23, 59),
    })
    .unwrap();
    assert_eq!(at_2359.overdue_assignment_ids, vec!["earlier"]);

    // One minute later (2026-09-27 00:00), all three become overdue; completed stays excluded.
    let next_day = homework_counts(HomeworkCountsInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        now: ClockNow::at("2026-09-27", 0, 0),
    })
    .unwrap();
    assert_eq!(
        next_day.overdue_assignment_ids,
        vec!["eod", "date_only", "exact", "earlier"]
    );
}

#[test]
fn unfinished_items_keeps_prior_week_only_on_today_week_and_lists_overdue_elsewhere() {
    let mut carried = assignment("lab", "Lab", "2026-09-26T21:00", 60);
    carried["session_weeks"] = json!([PREV_WEEK]);
    let overdue = assignment("late", "Late essay", "2026-09-20T21:00", 60);
    let assignments = map_of(vec![carried, overdue]);
    let saved_weeks = vec![PREV_WEEK.to_string(), WEEK.to_string()];

    // On the week holding today: both overdue and left_from_last_week show.
    let on_today = unfinished_items(UnfinishedInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        saved_weeks: &saved_weeks,
        stored_parts: &[],
        now: ClockNow::at(WEEK, 7, 0),
    })
    .unwrap();
    let pairs: Vec<(&str, &str)> = on_today
        .iter()
        .map(|i| {
            (
                i["id"].as_str().unwrap(),
                i["left_over_state"].as_str().unwrap(),
            )
        })
        .collect();
    assert_eq!(
        pairs,
        vec![("lab", "left_from_last_week"), ("late", "overdue")]
    );

    let left_only = left_unfinished_items(UnfinishedInput {
        week_start: WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        saved_weeks: &saved_weeks,
        stored_parts: &[],
        now: ClockNow::at(WEEK, 7, 0),
    })
    .unwrap();
    assert_eq!(left_only.len(), 1);
    assert_eq!(left_only[0]["id"], "lab");

    // On a later week (NEXT_WEEK) and an earlier week (PREV_WEEK): only overdue shows.
    for other_week in [NEXT_WEEK, PREV_WEEK] {
        let items = unfinished_items(UnfinishedInput {
            week_start: other_week,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            saved_weeks: &saved_weeks,
            stored_parts: &[],
            now: ClockNow::at(WEEK, 7, 0),
        })
        .unwrap();
        assert_eq!(items.len(), 1);
        assert_eq!(items[0]["id"], "late");
        assert_eq!(items[0]["left_over_state"], "overdue");
    }

    // Non-Monday week (Wednesday 2026-09-23, first_weekday=2): stored_parts[0] is Monday 2026-09-21.
    // A session on day 0 (Mon) is before Wednesday (< offset 2) -> left_from_last_week;
    // one on day 3 (Thu, >= offset 2) is already in this shown week -> not left_from_last_week.
    let mut before_cut = assignment("early", "Early", "2026-09-29T21:00", 60);
    before_cut["session_weeks"] = json!([WEEK]);
    let mut after_cut = assignment("in_shown", "In shown", "2026-09-29T21:00", 60);
    after_cut["session_weeks"] = json!([WEEK]);
    let split_assignments = map_of(vec![before_cut, after_cut]);
    let stored_parts = vec![
        json!({
            "week_start": WEEK,
            "blocks": [
                hw_block("b-early", "early", 0, Some("10:00"), 60),
                hw_block("b-shown", "in_shown", 3, None, 60),
            ]
        }),
        json!({"week_start": NEXT_WEEK, "blocks": []}),
    ];
    let split_items = unfinished_items(UnfinishedInput {
        week_start: "2026-09-23",
        first_weekday: 2,
        blocks: &[],
        assignments: &split_assignments,
        assignments_basis: &[],
        saved_weeks: &[WEEK.to_string()],
        stored_parts: &stored_parts,
        now: ClockNow::at("2026-09-23", 9, 0),
    })
    .unwrap();
    assert_eq!(split_items.len(), 1);
    assert_eq!(split_items[0]["id"], "early");
    assert_eq!(split_items[0]["left_over_state"], "left_from_last_week");
}

#[test]
fn unfinished_preview_builds_row_or_says_too_short_or_already_planned() {
    // Parity with test_unfinished_homework_keeps_the_same_assignment and
    // test_what_is_too_short_for_plan_is_said_in_minutes.
    let assignments = map_of(vec![
        assignment("lab", "Lab", "2026-09-25T21:00", 60),
        assignment("essay", "History essay", "2026-09-27T23:59", 60),
    ]);
    let blocks = vec![pinned(hw_block("b-essay", "essay", 4, Some("15:00"), 50))];

    // Lab has 60m uncovered -> single preview row keeping assignment_id "lab".
    let preview = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: WEEK,
            blocks: &blocks,
            assignments: &assignments,
            assignments_basis: &blocks,
            assignment_id: "lab",
            now: ClockNow::at(WEEK, 7, 0),
            plannable_today: WEEK,
        },
        "new-lab-1",
    )
    .unwrap();
    match preview {
        UnfinishedPreview::Rows(rows) => {
            assert_eq!(rows.len(), 1);
            assert_eq!(rows[0]["week_start"], WEEK);
            assert_eq!(rows[0]["day"], 0);
            assert_eq!(rows[0]["fixed"], false);
            assert_eq!(rows[0]["group_id"], "new-lab-1");
            assert_eq!(rows[0]["checked"], true);
            assert_eq!(rows[0]["invalid"], "");
            assert_eq!(rows[0]["original_duration"], 60);
            assert_eq!(rows[0]["block"]["assignment_id"], "lab");
            assert_eq!(rows[0]["block"]["days"], json!([0, 1, 2, 3, 4]));
        }
        UnfinishedPreview::Say(words) => panic!("expected rows, got: {words}"),
    }

    // The session clock says Monday; the wall clock (candidate days) says Wednesday: the row starts
    // on Wednesday and runs through the Friday deadline.
    let later = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: WEEK,
            blocks: &blocks,
            assignments: &assignments,
            assignments_basis: &blocks,
            assignment_id: "lab",
            now: ClockNow::at(WEEK, 7, 0),
            plannable_today: "2026-09-23",
        },
        "new-lab-2",
    )
    .unwrap();
    match later {
        UnfinishedPreview::Rows(rows) => {
            assert_eq!(rows[0]["day"], 2);
            assert_eq!(rows[0]["block"]["days"], json!([2, 3, 4]));
        }
        UnfinishedPreview::Say(words) => panic!("expected rows, got: {words}"),
    }

    // Essay has 10m uncovered -> too short sentence in minutes.
    let short = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: WEEK,
            blocks: &blocks,
            assignments: &assignments,
            assignments_basis: &blocks,
            assignment_id: "essay",
            now: ClockNow::at(WEEK, 7, 0),
            plannable_today: WEEK,
        },
        "unused",
    )
    .unwrap();
    assert_eq!(
        short,
        UnfinishedPreview::Say(
            "History essay has 10 min left. Plan needs at least 15 minutes.".to_string()
        )
    );

    // Essay at full 60m -> already fully planned.
    let full_blocks = vec![pinned(hw_block("b-essay", "essay", 4, Some("15:00"), 60))];
    let full = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: WEEK,
            blocks: &full_blocks,
            assignments: &assignments,
            assignments_basis: &full_blocks,
            assignment_id: "essay",
            now: ClockNow::at(WEEK, 7, 0),
            plannable_today: WEEK,
        },
        "unused",
    )
    .unwrap();
    assert_eq!(
        full,
        UnfinishedPreview::Say("There's no time left to plan for this homework.".to_string())
    );
}

#[test]
fn plan_unfinished_separates_ordinary_and_overdue_targets_and_omits_pinned_past() {
    // Parity with test_plan_overdue_leaves_the_pinned_session_and_adds_a_new_one and
    // test_plan_overdue_moves_a_future_session.
    // Clock: Saturday 2026-09-26 10:00 (day 5).
    // 1. "bio" (overdue, due Fri 23:59, 60m): pinned session on Wed 15:15 (passed).
    //    Pinned past session must stay out of targets; a fresh 60m block is made for Sat..Sun ([5, 6]).
    // 2. "bio_future" (overdue, due Fri 23:59, 60m): unpinned future session on Sat 14:00.
    //    No new block needed; existing session goes into overdue_targets.
    // 3. "math" (not overdue, due Sun 23:59, 120m): one 30m missed session on Wed 10:00, one 30m
    //    future session on Sun 10:00, and 60m uncovered -> missed session + new 60m block go into
    //    ordinary_targets; future session stays untouched.
    let assignments = map_of(vec![
        assignment("bio", "Bio reading", "2026-09-25T23:59", 60),
        assignment("bio_future", "Bio future", "2026-09-25T23:59", 60),
        assignment("math", "Math", "2026-09-27T23:59", 120),
    ]);
    let blocks = vec![
        pinned(hw_block("b-bio-pin", "bio", 2, Some("15:15"), 60)),
        hw_block("b-bio-fut", "bio_future", 5, Some("14:00"), 60),
        hw_block("b-math-miss", "math", 2, Some("10:00"), 30),
        hw_block("b-math-fut", "math", 6, Some("10:00"), 30),
    ];

    let mut ids = ["fresh-1", "fresh-2", "fresh-3"]
        .into_iter()
        .map(str::to_string);
    let plan = plan_unfinished(
        UnfinishedPlanInput {
            week_start: WEEK,
            blocks: &blocks,
            assignments: &assignments,
            assignments_basis: &blocks,
            assignment_ids: &[
                "bio".to_string(),
                "bio_future".to_string(),
                "math".to_string(),
            ],
            now: ClockNow::at("2026-09-26", 10, 0),
        },
        &mut ids,
    )
    .unwrap();

    match plan {
        UnfinishedPlan::Ready {
            blocks: out_blocks,
            made,
            ordinary_targets,
            overdue_targets,
        } => {
            assert_eq!(made, vec!["fresh-1", "fresh-2"]);
            assert_eq!(ordinary_targets, vec!["b-math-miss", "fresh-2"]);
            assert_eq!(overdue_targets, vec!["fresh-1", "b-bio-fut"]);
            assert!(!overdue_targets.iter().any(|id| id == "b-bio-pin"));
            assert!(!ordinary_targets.iter().any(|id| id == "b-bio-pin"));
            assert!(!ordinary_targets.iter().any(|id| id == "b-math-fut"));

            // Pinned Wednesday block stays intact in out_blocks.
            let kept = out_blocks.iter().find(|b| b["id"] == "b-bio-pin").unwrap();
            assert_eq!(kept["start"], "15:15");
            assert_eq!(kept["pinned"], true);

            let fresh_bio = out_blocks.iter().find(|b| b["id"] == "fresh-1").unwrap();
            assert_eq!(fresh_bio["assignment_id"], "bio");
            assert_eq!(fresh_bio["duration_min"], 60);
            assert_eq!(fresh_bio["days"], json!([5, 6]));

            let fresh_math = out_blocks.iter().find(|b| b["id"] == "fresh-2").unwrap();
            assert_eq!(fresh_math["assignment_id"], "math");
            assert_eq!(fresh_math["duration_min"], 60);
            assert_eq!(fresh_math["days"], json!([5, 6]));
        }
        UnfinishedPlan::Say(words) => panic!("expected Ready plan, got: {words}"),
    }
}

#[test]
fn plan_unfinished_handles_week_over_under_grid_already_has_time_and_duplicate_ids() {
    let assignments = map_of(vec![
        assignment("essay", "History essay", "2026-09-27T23:59", 60),
        assignment("bio", "Bio", "2026-09-25T23:59", 60),
    ]);

    // 1. Week is over (including Sunday 23:45:01 rounding up past midnight into day 7). An id is on hand,
    // so a guard that let the week through would build a block instead of failing on a missing id.
    let mut ids = ["unused-1"].into_iter().map(str::to_string);
    let over = plan_unfinished(
        UnfinishedPlanInput {
            week_start: WEEK,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_ids: &["bio".to_string()],
            now: ClockNow {
                today: "2026-09-27",
                hour: 23,
                minute: 45,
                second: 1,
                microsecond: 0,
            },
        },
        &mut ids,
    )
    .unwrap();
    assert_eq!(
        over,
        UnfinishedPlan::Say(
            "That week is over. Open this week or a later one, then plan again.".to_string()
        )
    );

    // 2. Under-grid work (10 min left, no waiting session).
    let short_blocks = vec![pinned(hw_block("b-essay", "essay", 4, Some("15:00"), 50))];
    let mut ids = std::iter::empty();
    let under = plan_unfinished(
        UnfinishedPlanInput {
            week_start: WEEK,
            blocks: &short_blocks,
            assignments: &assignments,
            assignments_basis: &short_blocks,
            assignment_ids: &["essay".to_string()],
            now: ClockNow::at(WEEK, 8, 0),
        },
        &mut ids,
    )
    .unwrap();
    assert_eq!(
        under,
        UnfinishedPlan::Say(
            "History essay has 10 min left. Plan needs at least 15 minutes.".to_string()
        )
    );

    // 3. Fully planned future session -> already has a time.
    let full_blocks = vec![pinned(hw_block("b-essay", "essay", 4, Some("15:00"), 60))];
    let mut ids = std::iter::empty();
    let already = plan_unfinished(
        UnfinishedPlanInput {
            week_start: WEEK,
            blocks: &full_blocks,
            assignments: &assignments,
            assignments_basis: &full_blocks,
            assignment_ids: &["essay".to_string()],
            now: ClockNow::at(WEEK, 8, 0),
        },
        &mut ids,
    )
    .unwrap();
    assert_eq!(
        already,
        UnfinishedPlan::Say("There's no time left to plan for this homework.".to_string())
    );

    // 4. Duplicate assignment IDs in one call never create a duplicate block.
    let mut ids = ["once-1", "once-2"].into_iter().map(str::to_string);
    let dup = plan_unfinished(
        UnfinishedPlanInput {
            week_start: WEEK,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_ids: &["bio".to_string(), "bio".to_string()],
            now: ClockNow::at("2026-09-26", 10, 0),
        },
        &mut ids,
    )
    .unwrap();
    match dup {
        UnfinishedPlan::Ready {
            blocks,
            made,
            ordinary_targets,
            overdue_targets,
        } => {
            assert_eq!(blocks.len(), 1);
            assert_eq!(made, vec!["once-1"]);
            assert!(ordinary_targets.is_empty());
            assert_eq!(overdue_targets, vec!["once-1"]);
        }
        UnfinishedPlan::Say(words) => panic!("expected Ready, got: {words}"),
    }
}

#[test]
fn invalid_clock_stored_parts_or_exhausted_ids_are_refused() {
    let assignments = map_of(vec![assignment("bio", "Bio", "2026-09-25T23:59", 60)]);

    assert!(
        homework_counts(HomeworkCountsInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            now: ClockNow::at("2026-09-26T10:00", 10, 0),
        })
        .is_err()
    );
    assert!(
        homework_counts(HomeworkCountsInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            now: ClockNow::at("2026-09-26", 24, 0),
        })
        .is_err()
    );

    // Stored parts without a blocks array on today's week are refused.
    let bad_parts = vec![
        json!({"week_start": WEEK}),
        json!({"week_start": NEXT_WEEK}),
    ];
    assert!(
        unfinished_items(UnfinishedInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            saved_weeks: &[PREV_WEEK.to_string()],
            stored_parts: &bad_parts,
            now: ClockNow::at(WEEK, 8, 0),
        })
        .is_err()
    );

    // Running out of injected block IDs returns an error instead of panicking.
    let mut empty_ids = std::iter::empty();
    assert!(
        plan_unfinished(
            UnfinishedPlanInput {
                week_start: WEEK,
                blocks: &[],
                assignments: &assignments,
                assignments_basis: &[],
                assignment_ids: &["bio".to_string()],
                now: ClockNow::at("2026-09-26", 10, 0),
            },
            &mut empty_ids,
        )
        .is_err()
    );
}

#[test]
fn a_clock_past_the_last_deadline_year_still_counts_and_plans() {
    // The last supported week (Mon 2099-12-28) is still open on Fri 2100-01-01. Deadlines are limited to
    // 2000..2099, the clock is any real date, so the week spills into January without an error.
    let last_week = "2099-12-28";
    let assignments = map_of(vec![assignment("late", "Late", "2099-12-30T10:00", 60)]);

    let counts = homework_counts(HomeworkCountsInput {
        week_start: last_week,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        now: ClockNow::at("2100-01-01", 9, 0),
    })
    .unwrap();
    assert_eq!(counts.overdue_assignment_ids, vec!["late"]);
    assert!(counts.per_assignment["late"].overdue);
    assert_eq!(counts.per_assignment["late"].uncovered_min, 60);

    let mut ids = ["new-1"].into_iter().map(str::to_string);
    let planned = plan_unfinished(
        UnfinishedPlanInput {
            week_start: last_week,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_ids: &["late".to_string()],
            now: ClockNow::at("2100-01-01", 9, 0),
        },
        &mut ids,
    )
    .unwrap();
    match planned {
        UnfinishedPlan::Ready {
            made,
            overdue_targets,
            ..
        } => {
            assert_eq!(made, vec!["new-1"]);
            assert_eq!(overdue_targets, vec!["new-1"]);
        }
        UnfinishedPlan::Say(words) => panic!("expected Ready, got: {words}"),
    }

    // A deadline past 2099 stays refused.
    let far = map_of(vec![assignment("far", "Far", "2100-01-02", 60)]);
    assert!(
        homework_counts(HomeworkCountsInput {
            week_start: last_week,
            first_weekday: 0,
            blocks: &[],
            assignments: &far,
            assignments_basis: &[],
            now: ClockNow::at("2100-01-01", 9, 0),
        })
        .is_err()
    );
}

#[test]
fn a_block_without_a_text_id_is_refused_before_any_date_branch() {
    // A future week with no homework skips missed-session work, so the id-less row used to pass through
    // into open_week untouched.
    let blocks = vec![json!({})];
    let no_homework = Map::new();
    let counts = homework_counts(HomeworkCountsInput {
        week_start: NEXT_WEEK,
        first_weekday: 0,
        blocks: &blocks,
        assignments: &no_homework,
        assignments_basis: &[],
        now: ClockNow::at(WEEK, 9, 0),
    });
    assert_eq!(counts.unwrap_err(), "block is missing a text id");

    // The saved-week rows are blocks too.
    let basis = vec![json!({"id": 7})];
    let counts = homework_counts(HomeworkCountsInput {
        week_start: NEXT_WEEK,
        first_weekday: 0,
        blocks: &[],
        assignments: &no_homework,
        assignments_basis: &basis,
        now: ClockNow::at(WEEK, 9, 0),
    });
    assert_eq!(counts.unwrap_err(), "block is missing a text id");

    let mut ids = std::iter::empty();
    let plan = plan_unfinished(
        UnfinishedPlanInput {
            week_start: NEXT_WEEK,
            blocks: &blocks,
            assignments: &no_homework,
            assignments_basis: &[],
            assignment_ids: &[],
            now: ClockNow::at(WEEK, 9, 0),
        },
        &mut ids,
    );
    assert_eq!(plan.unwrap_err(), "block is missing a text id");

    let items = unfinished_items(UnfinishedInput {
        week_start: NEXT_WEEK,
        first_weekday: 0,
        blocks: &blocks,
        assignments: &no_homework,
        assignments_basis: &[],
        saved_weeks: &[],
        stored_parts: &[],
        now: ClockNow::at(WEEK, 9, 0),
    });
    assert_eq!(items.unwrap_err(), "block is missing a text id");

    let preview = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: NEXT_WEEK,
            blocks: &blocks,
            assignments: &no_homework,
            assignments_basis: &[],
            assignment_id: "none",
            now: ClockNow::at(WEEK, 9, 0),
            plannable_today: WEEK,
        },
        "new-1",
    );
    assert_eq!(preview.unwrap_err(), "block is missing a text id");
}

#[test]
fn the_card_list_and_the_solve_check_differ_by_one_minute_at_the_end_of_the_day() {
    // Kept from the old window: at 23:59 on the deadline day the card list already calls an
    // end-of-day deadline overdue, while the solve check (1440 > 1439) does not until midnight.
    let assignments = map_of(vec![assignment(
        "eod",
        "End of day",
        "2026-09-26T23:59",
        60,
    )]);
    let ids_of = |hour, minute| {
        let counts = homework_counts(HomeworkCountsInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            now: ClockNow::at("2026-09-26", hour, minute),
        })
        .unwrap();
        let cards = unfinished_items(UnfinishedInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            saved_weeks: &[],
            stored_parts: &[],
            now: ClockNow::at("2026-09-26", hour, minute),
        })
        .unwrap();
        let overdue_cards: Vec<String> = cards
            .iter()
            .filter(|card| card["left_over_state"] == "overdue")
            .map(|card| card["id"].as_str().unwrap().to_string())
            .collect();
        (counts.overdue_assignment_ids, overdue_cards)
    };

    let (solve, cards) = ids_of(23, 58);
    assert!(solve.is_empty() && cards.is_empty());
    let (solve, cards) = ids_of(23, 59);
    assert!(solve.is_empty());
    assert_eq!(cards, vec!["eod"]);
}

#[test]
fn homework_due_this_very_minute_is_overdue_and_one_minute_before_is_not() {
    let assignments = map_of(vec![assignment("timed", "Timed", "2026-09-26T10:00", 60)]);
    let overdue_at = |hour, minute| {
        homework_counts(HomeworkCountsInput {
            week_start: WEEK,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            now: ClockNow::at("2026-09-26", hour, minute),
        })
        .unwrap()
        .overdue_assignment_ids
    };
    assert!(overdue_at(9, 59).is_empty());
    assert_eq!(overdue_at(10, 0), vec!["timed"]);
}

#[test]
fn the_preview_and_the_card_list_accept_a_january_2100_clock_in_the_last_week() {
    // Week of Mon 2099-12-28 is still on screen on Fri 2100-01-01. Both clocks (session and wall) are
    // real dates; only the deadline is held to 2000..2099.
    let last_week = "2099-12-28";
    let assignments = map_of(vec![assignment("late", "Late", "2099-12-30T10:00", 60)]);

    let preview = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: last_week,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_id: "late",
            now: ClockNow::at("2100-01-01", 9, 0),
            plannable_today: "2100-01-01",
        },
        "new-late-1",
    )
    .unwrap();
    match preview {
        UnfinishedPreview::Rows(rows) => {
            // Due Wednesday (day 2), today is past it: the row sits on the deadline day.
            assert_eq!(rows[0]["day"], 2);
            assert_eq!(rows[0]["block"]["days"], json!([2]));
            assert_eq!(rows[0]["original_duration"], 60);
        }
        UnfinishedPreview::Say(words) => panic!("expected rows, got: {words}"),
    }

    let items = unfinished_items(UnfinishedInput {
        week_start: last_week,
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        saved_weeks: &[],
        stored_parts: &[],
        now: ClockNow::at("2100-01-01", 9, 0),
    })
    .unwrap();
    let pairs: Vec<(&str, &str)> = items
        .iter()
        .map(|i| {
            (
                i["id"].as_str().unwrap(),
                i["left_over_state"].as_str().unwrap(),
            )
        })
        .collect();
    assert_eq!(pairs, vec![("late", "overdue")]);

    // A wall-clock date that is not a real date is still refused.
    let bad = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: last_week,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_id: "late",
            now: ClockNow::at("2100-01-01", 9, 0),
            plannable_today: "2100-02-30",
        },
        "unused",
    );
    assert!(bad.is_err());
}

#[test]
fn unfinished_items_accepts_clocks_whose_week_starts_outside_2000_2099() {
    // On 2000-01-01 (Saturday), Monday-start derives today_week = 1999-12-27.
    let early_hw = map_of(vec![assignment("early", "Early", "2000-01-01T08:00", 60)]);
    let early = unfinished_items(UnfinishedInput {
        week_start: "2000-01-01",
        first_weekday: 0,
        blocks: &[],
        assignments: &early_hw,
        assignments_basis: &[],
        saved_weeks: &[],
        stored_parts: &[],
        now: ClockNow::at("2000-01-01", 9, 0),
    })
    .unwrap();
    assert_eq!(early.len(), 1);
    assert_eq!(early[0]["id"], "early");
    assert_eq!(early[0]["left_over_state"], "overdue");

    // On 2100-01-04 (Monday), today_week = 2100-01-04 while viewing the last supported week 2099-12-28.
    let late_hw = map_of(vec![assignment("late", "Late", "2099-12-30T10:00", 60)]);
    let late = unfinished_items(UnfinishedInput {
        week_start: "2099-12-28",
        first_weekday: 0,
        blocks: &[],
        assignments: &late_hw,
        assignments_basis: &[],
        saved_weeks: &[],
        stored_parts: &[],
        now: ClockNow::at("2100-01-04", 9, 0),
    })
    .unwrap();
    assert_eq!(late.len(), 1);
    assert_eq!(late[0]["id"], "late");
    assert_eq!(late[0]["left_over_state"], "overdue");
}

#[test]
fn unfinished_preview_refuses_week_start_outside_save_range() {
    // The week save accepts `is_week_start`: Mondays from 2000-01-03 through
    // 2099-12-28, and 1999-12-27 (the Monday of the week that holds 2000-01-01).
    // 1999-12-20 and 2100-01-04 are the Mondays just outside that, and the save
    // refuses both. A shown week that is not a Monday stays accepted when it is
    // a calendar date in 2000..2099, the same pair the homework list uses.
    let assignments = map_of(vec![assignment("essay", "Essay", "2000-01-02T12:00", 60)]);
    for unsavable in ["2100-01-04", "1999-12-20"] {
        let refused = unfinished_preview(
            UnfinishedPreviewInput {
                week_start: unsavable,
                blocks: &[],
                assignments: &assignments,
                assignments_basis: &[],
                assignment_id: "essay",
                now: ClockNow::at("2000-01-01", 9, 0),
                plannable_today: "2000-01-01",
            },
            "new-1",
        )
        .unwrap_err();
        assert!(
            refused.contains("week_start"),
            "expected week_start error for {unsavable}, got: {refused}"
        );
        let counts_err = homework_counts(HomeworkCountsInput {
            week_start: unsavable,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            now: ClockNow::at("2000-01-01", 9, 0),
        })
        .unwrap_err();
        assert!(
            counts_err.contains("week_start"),
            "homework_counts should refuse {unsavable}, got: {counts_err}"
        );
        let items_err = unfinished_items(UnfinishedInput {
            week_start: unsavable,
            first_weekday: 0,
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            saved_weeks: &[],
            stored_parts: &[],
            now: ClockNow::at("2000-01-01", 9, 0),
        })
        .unwrap_err();
        assert!(
            items_err.contains("week_start"),
            "unfinished_items should refuse {unsavable}, got: {items_err}"
        );
        let mut ids = ["new-1".to_string()].into_iter();
        let plan_err = plan_unfinished(
            UnfinishedPlanInput {
                week_start: unsavable,
                blocks: &[],
                assignments: &assignments,
                assignments_basis: &[],
                assignment_ids: &["essay".to_string()],
                now: ClockNow::at("2000-01-01", 9, 0),
            },
            &mut ids,
        )
        .unwrap_err();
        assert!(
            plan_err.contains("week_start"),
            "plan_unfinished should refuse {unsavable}, got: {plan_err}"
        );
    }

    // 2000-01-01 is Saturday of the week that starts 1999-12-27, so the first
    // plannable day is 5 and the Sunday due is day 6. Sixty minutes and no
    // session already holding them preview as one row on those two days.
    let preview = unfinished_preview(
        UnfinishedPreviewInput {
            week_start: "1999-12-27",
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_id: "essay",
            now: ClockNow::at("2000-01-01", 9, 0),
            plannable_today: "2000-01-01",
        },
        "new-1",
    )
    .unwrap();
    match preview {
        UnfinishedPreview::Rows(rows) => {
            assert_eq!(rows.len(), 1);
            assert_eq!(rows[0]["week_start"], "1999-12-27");
            assert_eq!(rows[0]["day"], 5);
            assert_eq!(rows[0]["original_duration"], 60);
            assert_eq!(rows[0]["block"]["assignment_id"], "essay");
            assert_eq!(rows[0]["block"]["duration_min"], 60);
            assert_eq!(rows[0]["block"]["days"], json!([5, 6]));
        }
        UnfinishedPreview::Say(words) => {
            panic!("1999-12-27 is a savable week start, got: {words}")
        }
    }

    let counts = homework_counts(HomeworkCountsInput {
        week_start: "1999-12-27",
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        now: ClockNow::at("2000-01-01", 9, 0),
    })
    .unwrap();
    assert!(counts.overdue_assignment_ids.is_empty());
    assert!(counts.plan_can_place);
    assert_eq!(counts.per_assignment["essay"].remaining_min, 60);
    assert!(!counts.per_assignment["essay"].overdue);

    let items = unfinished_items(UnfinishedInput {
        week_start: "1999-12-27",
        first_weekday: 0,
        blocks: &[],
        assignments: &assignments,
        assignments_basis: &[],
        saved_weeks: &[],
        stored_parts: &[],
        now: ClockNow::at("2000-01-01", 9, 0),
    })
    .unwrap();
    assert!(items.is_empty());

    let mut ids = ["new-1".to_string()].into_iter();
    let plan = plan_unfinished(
        UnfinishedPlanInput {
            week_start: "1999-12-27",
            blocks: &[],
            assignments: &assignments,
            assignments_basis: &[],
            assignment_ids: &["essay".to_string()],
            now: ClockNow::at("2000-01-01", 9, 0),
        },
        &mut ids,
    )
    .unwrap();
    match plan {
        UnfinishedPlan::Ready {
            made,
            ordinary_targets,
            overdue_targets,
            blocks,
        } => {
            assert_eq!(made, vec!["new-1"]);
            assert_eq!(ordinary_targets, vec!["new-1"]);
            assert!(overdue_targets.is_empty());
            assert_eq!(blocks.len(), 1);
            assert_eq!(blocks[0]["days"], json!([5, 6]));
            assert_eq!(blocks[0]["duration_min"], 60);
        }
        UnfinishedPlan::Say(words) => {
            panic!("1999-12-27 is a savable week start, got: {words}")
        }
    }
}

#[test]
fn left_over_items_from_reports_week_error_before_clock_error() {
    let err = flexweek_engine::desk::clipboard::left_over_items_from(
        &json!({}),
        &json!([]),
        "bad",
        "bad",
        &json!([]),
        &json!([]),
        &json!([]),
    )
    .unwrap_err();
    assert!(
        err.message.contains("week_start"),
        "expected week_start error first, got: {}",
        err.message
    );
}
