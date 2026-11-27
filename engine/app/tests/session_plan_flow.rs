//! Decisions moved from `desktop/native/controller.py` (plan continuation, settle notes, delete guard).
//! Expected values come from those Python rules and the desk tests that already pin settle's words.

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use flexweek_app::session::plan_flow::{
    self, DeleteHomework, PendingStep, PlanFlow, PostPending, SolveCommitInput, SpreadNext,
    SpreadPhase, fail_words, plan_notes, stored_week_rows, touch_settle,
};
use flexweek_app::session::unfinished::ClockNow;
use flexweek_app::session::{Host, Session};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Map, Value, json};

const CLASH_WEEK: &str = "2026-10-19";
const DUE_WEEK: &str = "2026-09-28";

fn object(value: Value) -> Map<String, Value> {
    value.as_object().expect("object").clone()
}

fn clock(today: &str, hour: i64, minute: i64) -> ClockNow<'_> {
    ClockNow::at(today, hour, minute)
}

fn kinds(steps: &[PendingStep]) -> Vec<&str> {
    steps
        .iter()
        .map(|step| match step {
            PendingStep::SayStatus => "say_status",
            PendingStep::Say => "say",
            PendingStep::InvalidateMonths => "invalidate_months",
            PendingStep::SpreadNext { .. } => "spread_next",
            PendingStep::SolveOnly { .. } => "solve_only",
            PendingStep::SolveReplan => "solve_replan",
            PendingStep::SaveFinished => "save_finished",
            PendingStep::RepeatsKept { .. } => "repeats_kept",
            PendingStep::SaveAnswered { .. } => "save_answered",
            PendingStep::EmitPlanned => "emit_planned",
            PendingStep::ClearReminderWeek => "clear_reminder_week",
            PendingStep::LoadDestination { .. } => "load_destination",
            PendingStep::Refollow { .. } => "refollow",
            PendingStep::ReloadOpen => "reload_open",
            PendingStep::RunWaiting => "run_waiting",
        })
        .collect()
}

fn saved(planned: bool) -> PostPending {
    PostPending {
        planned: json!(planned),
        open_week: json!(true),
        destination: Value::Null,
        repeat_notice: Value::Null,
        point_id: json!(""),
        doubled: json!([]),
        refollow: false,
        wrote_open: false,
        first_weekday: 0,
    }
}

#[test]
fn a_sunday_without_stored_parts_names_both_mondays_and_their_revisions() {
    let rows = stored_week_rows(&json!([]), &json!([3, 4]), "2026-11-01").unwrap();
    assert_eq!(
        rows,
        vec![("2026-10-26".to_string(), 3), ("2026-11-02".to_string(), 4),]
    );
}

#[test]
fn stored_parts_win_and_a_monday_with_one_revision_is_one_pair() {
    let parts = json!([
        {"week_start": "2026-10-26", "revision": "4"},
        {"week_start": "2026-11-02", "revision": true},
    ]);
    assert_eq!(
        stored_week_rows(&parts, &json!(9), "2026-11-01").unwrap(),
        vec![("2026-10-26".to_string(), 4), ("2026-11-02".to_string(), 1),]
    );
    assert_eq!(
        stored_week_rows(&json!([]), &json!(5), "2026-10-26").unwrap(),
        vec![("2026-10-26".to_string(), 5)]
    );
}

#[test]
fn a_revision_list_of_the_wrong_length_is_the_zip_error() {
    let short = stored_week_rows(&json!([]), &json!([3]), "2026-11-01").unwrap_err();
    assert_eq!(short.message, "zip() argument 2 is shorter than argument 1");
    let long = stored_week_rows(&json!([]), &json!([3, 4, 5]), "2026-11-01").unwrap_err();
    assert_eq!(long.message, "zip() argument 2 is longer than argument 1");
}

#[test]
fn an_unreachable_plan_says_nothing_was_planned_and_any_other_failure_keeps_its_message() {
    assert_eq!(
        fail_words(true, 0, "timed out"),
        "Can't reach FlexWeek, so nothing was planned. Try again."
    );
    assert_eq!(fail_words(true, 500, "no room"), "no room");
    assert_eq!(fail_words(false, 0, "offline"), "offline");
}

#[test]
fn two_flexible_sessions_in_one_slot_keep_the_earlier_id_and_explain_the_other() {
    let blocks = vec![
        json!({"id": "s-essay", "title": "Essay", "kind": "flexible", "duration_min": 90, "days": [2], "start": "16:00"}),
        json!({"id": "s-math", "title": "Math", "kind": "flexible", "duration_min": 30, "days": [2], "start": "16:00"}),
        json!({"id": "choir", "title": "Choir", "kind": "locked", "duration_min": 60, "days": [2], "start": "18:00", "pinned": true}),
        json!({"id": "band", "title": "Band", "kind": "flexible", "duration_min": 30, "days": [0, 1], "start": "09:00", "pinned": true}),
        json!({"id": "reading", "title": "Reading", "kind": "flexible", "duration_min": 30, "days": [1]}),
    ];
    let mut notes = Map::new();
    notes.insert("reading".into(), json!("still waiting"));
    notes.insert("s-math".into(), json!("old"));
    notes.insert("choir".into(), json!("should drop"));
    let settled = touch_settle(
        &blocks,
        &Map::new(),
        &[],
        CLASH_WEEK,
        &[],
        Some("choir"),
        &clock("2026-10-21", 12, 0),
        &notes,
    )
    .unwrap();
    assert_eq!(
        settled.lost[0]["message"],
        json!("Math no longer fits Wednesday at 16:00: Essay is there now.")
    );
    assert!(
        settled
            .blocks
            .iter()
            .any(|block| block["id"] == "s-essay" && block["start"] == "16:00")
    );
    assert!(
        settled
            .blocks
            .iter()
            .any(|block| block["id"] == "s-math" && block.get("start").is_none())
    );
    assert!(
        settled
            .blocks
            .iter()
            .any(|block| block["id"] == "choir" && block["pinned"] == true)
    );
    assert!(
        settled
            .blocks
            .iter()
            .any(|block| block["id"] == "band" && block.get("pinned").is_none())
    );
    assert_eq!(
        settled.needs_time,
        object(json!({
            "reading": "still waiting",
            "s-math": "Math no longer fits Wednesday at 16:00: Essay is there now.",
        }))
    );
    assert!(!settled.clear_selection);
}

#[test]
fn a_placed_overdue_session_keeps_its_time() {
    let blocks = vec![json!({
        "id": "s-eng",
        "title": "English essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": [0],
        "start": "15:45",
        "assignment_id": "eng",
    })];
    let assignments = object(json!({
        "eng": {"id": "eng", "title": "English essay", "due": "2026-09-28T16:00"},
    }));
    let settled = touch_settle(
        &blocks,
        &assignments,
        &[],
        DUE_WEEK,
        &[],
        None,
        &clock("2026-09-28", 16, 0),
        &Map::new(),
    )
    .unwrap();
    assert!(settled.lost.is_empty(), "{:?}", settled.lost);
    assert_eq!(settled.blocks[0]["start"], json!("15:45"));
    assert!(
        settled.clear_selection,
        "nothing selected is not one of the block ids"
    );
}

#[test]
fn plan_notes_prefer_a_trace_and_otherwise_list_the_lost_times_in_order() {
    assert!(plan_notes(None, &Map::new()).is_none());
    let trace = json!({"placed": ["a"], "explanations": []});
    assert_eq!(plan_notes(Some(&trace), &Map::new()), Some(trace));
    let mut notes = Map::new();
    notes.insert("reading".into(), json!("still waiting"));
    notes.insert(
        "s-math".into(),
        json!("Math no longer fits Wednesday at 16:00: Essay is there now."),
    );
    assert_eq!(
        plan_notes(None, &notes),
        Some(json!({
            "placed": [],
            "explanations": [
                {"block_id": "reading", "message": "still waiting"},
                {"block_id": "s-math", "message": "Math no longer fits Wednesday at 16:00: Essay is there now."},
            ],
        }))
    );
}

#[test]
fn delete_waits_while_a_save_is_unfinished_and_names_the_revision_it_will_send() {
    let item = json!({"id": "essay", "revision": 3});
    let account = json!(7);
    assert_eq!(
        plan_flow::delete_homework_guard(
            Some(&account),
            "essay",
            Some(&item),
            false,
            false,
            false,
            &Value::Null
        )
        .unwrap(),
        DeleteHomework::Ready {
            key: "delete-homework|7|essay|3".to_string()
        }
    );
    let missing = json!({"id": "essay"});
    assert_eq!(
        plan_flow::delete_homework_guard(
            Some(&account),
            "essay",
            Some(&missing),
            false,
            false,
            false,
            &Value::Null
        )
        .unwrap(),
        DeleteHomework::Ready {
            key: "delete-homework|7|essay|0".to_string()
        }
    );
    assert_eq!(
        plan_flow::delete_homework_guard(
            Some(&account),
            "essay",
            Some(&item),
            true,
            true,
            false,
            &Value::Null
        )
        .unwrap(),
        DeleteHomework::Absent
    );
    assert_eq!(
        plan_flow::delete_homework_guard(
            Some(&account),
            "essay",
            Some(&item),
            false,
            true,
            false,
            &Value::Null
        )
        .unwrap(),
        DeleteHomework::Wait
    );
    assert_eq!(
        plan_flow::delete_homework_guard(
            Some(&account),
            "essay",
            Some(&item),
            false,
            false,
            false,
            &json!({})
        )
        .unwrap(),
        DeleteHomework::Wait
    );
    assert_eq!(
        plan_flow::delete_homework_guard(
            None,
            "essay",
            Some(&item),
            false,
            false,
            false,
            &Value::Null
        )
        .unwrap(),
        DeleteHomework::Absent
    );
}

#[test]
fn a_plans_words_are_toasted_before_its_undo_again() {
    let mut flow = PlanFlow {
        plan_after_save: vec!["s-math".into()],
        split_whole: vec!["s-math".into(), "s-essay".into()],
        split_planned: vec!["s-math".into()],
        ..PlanFlow::default()
    };
    let steps = flow.post_pending_ok(&saved(true)).unwrap();
    assert_eq!(
        kinds(&steps),
        vec![
            "say_status",
            "invalidate_months",
            "solve_only",
            "save_finished",
            "emit_planned",
            "run_waiting",
        ]
    );
    match &steps[2] {
        PendingStep::SolveOnly { ids } => assert_eq!(ids, &vec!["s-math".to_string()]),
        other => panic!("expected the waiting plan, got {other:?}"),
    }
    assert!(flow.plan_after_save.is_empty());
    assert_eq!(flow.split_whole, vec!["s-essay".to_string()]);
    assert!(flow.split_planned.is_empty());
    assert!(!kinds(&flow.post_pending_ok(&saved(false)).unwrap()).contains(&"say_status"));
}

#[test]
fn a_save_that_opens_another_week_plans_after_that_read_and_a_destination_plans_now() {
    let mut flow = PlanFlow {
        plan_after_save: vec!["s-math".into()],
        replan_after_save: true,
        spread_after_save: Some(SpreadNext {
            assignment_id: "essay".into(),
            session_min: 25,
            from_date: "2026-10-21".into(),
        }),
        ..PlanFlow::default()
    };
    let mut input = saved(true);
    input.open_week = json!(false);
    input.refollow = true;
    input.wrote_open = true;
    input.first_weekday = 1;
    input.repeat_notice = json!("Repeats kept");
    input.point_id = json!("point-1");
    input.doubled = json!(["2026-11-02"]);
    let steps = flow.post_pending_ok(&input).unwrap();
    assert_eq!(
        kinds(&steps),
        vec![
            "say_status",
            "invalidate_months",
            "spread_next",
            "save_finished",
            "repeats_kept",
            "save_answered",
            "emit_planned",
            "clear_reminder_week",
            "refollow",
        ]
    );
    assert_eq!(flow.plan_after_load, vec!["s-math".to_string()]);
    assert!(flow.replan_after_load);
    assert!(flow.spread_after_save.is_none());
    match &steps[8] {
        PendingStep::Refollow { then } => assert_eq!(kinds(then), vec!["reload_open"]),
        other => panic!("expected refollow, got {other:?}"),
    }

    let mut flow = PlanFlow {
        plan_after_save: vec!["s-math".into()],
        replan_after_save: true,
        ..PlanFlow::default()
    };
    let mut input = saved(false);
    input.destination = json!("");
    input.refollow = true;
    let steps = flow.post_pending_ok(&input).unwrap();
    assert!(kinds(&steps).contains(&"solve_only"));
    assert!(kinds(&steps).contains(&"solve_replan"));
    assert_eq!(
        steps.last(),
        Some(&PendingStep::LoadDestination {
            week: String::new()
        })
    );
    assert!(!flow.replan_after_load);
    assert!(flow.plan_after_load.is_empty());
}

#[test]
fn a_refused_save_drops_the_waiting_plan_and_keeps_the_split_promise() {
    let mut flow = PlanFlow {
        plan_after_save: vec!["s-math".into()],
        split_whole: vec!["s-essay".into()],
        split_planned: vec!["s-math".into()],
        replan_after_save: true,
        spread_after_save: Some(SpreadNext {
            assignment_id: "essay".into(),
            session_min: 25,
            from_date: "2026-10-21".into(),
        }),
        allow_split_pending: Some("essay".into()),
        ..PlanFlow::default()
    };
    flow.post_pending_err();
    assert!(flow.plan_after_save.is_empty());
    assert!(flow.split_planned.is_empty());
    assert!(!flow.replan_after_save);
    assert!(flow.spread_after_save.is_none());
    assert!(flow.allow_split_pending.is_none());
    assert_eq!(flow.split_whole, vec!["s-essay".to_string()]);
}

#[test]
fn homework_without_a_time_is_planned_once_its_save_lands() {
    let mut flow = PlanFlow {
        plan_after_save: vec!["already".into()],
        ..PlanFlow::default()
    };
    let blocks = vec![
        json!({"id": "placed", "assignment_id": "essay", "start": "10:00", "completed": false}),
        json!({"id": "done", "assignment_id": "essay", "completed": true}),
        json!({"id": "waiting", "assignment_id": "essay"}),
        json!({"id": "other", "assignment_id": "math"}),
    ];
    flow.plan_after_save(&blocks, "essay").unwrap();
    assert_eq!(
        flow.plan_after_save,
        vec!["already".to_string(), "waiting".to_string()]
    );
}

#[test]
fn a_plan_that_changed_nothing_says_so_without_promising_the_split() {
    let mut flow = PlanFlow {
        split_whole: vec!["s-essay".into()],
        split_planned: vec!["kept".into()],
        ..PlanFlow::default()
    };
    let commit = flow
        .solve_apply_commit(&SolveCommitInput {
            needs_time: json!({"reading": "still waiting"}),
            split_note: json!(""),
            changed: false,
            placed_note: "Nothing new to place.".into(),
            placed_where: json!(""),
            dirty: false,
            dirty_assignments: &[],
            prior_updates: json!([]),
            targets: &["s-essay".into()],
            join: false,
            only_is_some: false,
            step_id: "step-1".into(),
        })
        .unwrap();
    assert!(commit.say);
    assert!(!commit.save);
    assert!(commit.split_planned.is_none());
    assert_eq!(flow.split_planned, vec!["kept".to_string()]);
    assert!(flow.fresh_plan);
    assert_eq!(
        flow.needs_time.get("reading"),
        Some(&json!("still waiting"))
    );
    assert!(!commit.clear_plan_step_id);
    assert!(commit.history_label.is_none());
}

#[test]
fn a_focus_split_note_dirties_the_record_and_is_saved_when_nothing_else_changed() {
    let mut flow = PlanFlow::default();
    let commit = flow
        .solve_apply_commit(&SolveCommitInput {
            needs_time: json!({}),
            split_note: json!("Split into 25 minute focuses."),
            changed: false,
            placed_note: "Placed the focus.".into(),
            placed_where: json!("Placed Math on Thu 5:45 PM."),
            dirty: false,
            dirty_assignments: &[],
            prior_updates: json!([]),
            targets: &[],
            join: true,
            only_is_some: true,
            step_id: "step-1".into(),
        })
        .unwrap();
    // apply_plan writes the dirty flag before the window reads it, so this note is saved.
    assert!(!commit.say);
    assert!(commit.save);
    assert!(commit.dirty);
    assert!(commit.clear_plan_step_id);
    assert_eq!(commit.history_label.as_deref(), Some("the focus split"));
    assert_eq!(
        commit.placed_where.as_deref(),
        Some("Placed Math on Thu 5:45 PM.")
    );
    assert_eq!(commit.split_planned, Some(Vec::new()));
    assert!(!commit.plan);
    assert!(flow.split_planned.is_empty());
}

#[test]
fn a_plan_that_moved_homework_records_the_step_and_the_split_it_included() {
    let mut flow = PlanFlow {
        split_whole: vec!["s-essay".into(), "s-math".into()],
        ..PlanFlow::default()
    };
    let commit = flow
        .solve_apply_commit(&SolveCommitInput {
            needs_time: json!({}),
            split_note: Value::Null,
            changed: true,
            placed_note: "Placed Math.".into(),
            placed_where: Value::Null,
            dirty: false,
            dirty_assignments: &[],
            prior_updates: json!([{"week_start": "2026-10-19"}]),
            targets: &["s-math".into(), "s-read".into()],
            join: true,
            only_is_some: true,
            step_id: "step-9".into(),
        })
        .unwrap();
    assert!(!commit.say);
    assert!(commit.save);
    assert!(
        !commit.plan,
        "joining one homework's plan is not its own undo step"
    );
    assert_eq!(commit.history_label.as_deref(), Some("planning the week"));
    assert_eq!(commit.step_id.as_deref(), Some("step-9"));
    assert_eq!(
        commit.prior_updates,
        Some(json!([{"week_start": "2026-10-19"}]))
    );
    assert_eq!(commit.split_planned, Some(vec!["s-math".to_string()]));
    assert_eq!(flow.split_planned, vec!["s-math".to_string()]);
}

#[test]
fn an_empty_prior_list_is_not_a_step_and_a_dead_left_set_does_not_clear_notes() {
    let mut flow = PlanFlow::default();
    let commit = flow
        .solve_apply_commit(&SolveCommitInput {
            needs_time: json!({}),
            split_note: Value::Null,
            changed: true,
            placed_note: "Placed.".into(),
            placed_where: Value::Null,
            dirty: true,
            dirty_assignments: &["essay".into()],
            prior_updates: json!([]),
            targets: &[],
            join: false,
            only_is_some: false,
            step_id: "step-2".into(),
        })
        .unwrap();
    assert!(commit.step_id.is_none());
    assert!(commit.clear_plan_step_id);
    assert!(commit.plan);

    flow.needs_time
        .insert("reading".into(), json!("still waiting"));
    let skipped = flow.solve_err_rollback(&[], None, &json!(false)).unwrap();
    assert!(!skipped.rollback);
    assert_eq!(
        flow.needs_time.get("reading"),
        Some(&json!("still waiting"))
    );
    let reading = json!({"id": "reading", "kind": "flexible", "days": [1]});
    let added = json!({"id": "s-new", "kind": "flexible", "days": [1], "start": "10:00"});
    let rolled = flow
        .solve_err_rollback(&[reading, added], Some(&["s-new".into()]), &json!(true))
        .unwrap();
    assert!(rolled.rollback);
    assert_eq!(rolled.blocks.len(), 1);
    assert_eq!(rolled.dirty, json!(true));
    assert_eq!(
        flow.needs_time.get("reading"),
        Some(&json!("still waiting"))
    );
}

#[test]
fn a_fresh_plan_is_read_once_and_an_unseen_week_shows_its_unfinished_work_once() {
    let mut flow = PlanFlow {
        fresh_plan: true,
        ..PlanFlow::default()
    };
    let trace = json!({"placed": []});
    assert_eq!(flow.consume_plan_review(Some(&trace)), Some(trace));
    assert!(!flow.fresh_plan);
    assert!(flow.consume_plan_review(Some(&json!({}))).is_none());

    let mut flow = PlanFlow {
        fresh_plan: true,
        ..PlanFlow::default()
    };
    assert!(flow.consume_plan_review(None).is_none());
    assert!(!flow.fresh_plan);

    let items = vec![json!({"id": "essay"})];
    let mut flow = PlanFlow::default();
    assert!(flow.consume_unfinished("2026-10-19", &[]).is_empty());
    assert!(flow.seen_unfinished.is_empty());
    assert_eq!(flow.consume_unfinished("2026-10-19", &items), items);
    assert!(flow.consume_unfinished("2026-10-19", &items).is_empty());
    assert_eq!(flow.consume_unfinished("2026-10-26", &items), items);
}

#[test]
fn mark_finished_names_only_homework_that_exists_and_keeps_duplicates() {
    let assignments = object(json!({"essay": {"id": "essay"}, "math": {"id": "math"}}));
    assert_eq!(
        plan_flow::did_these_ids(
            &assignments,
            &[
                "missing".into(),
                "essay".into(),
                "essay".into(),
                "math".into()
            ]
        ),
        vec!["essay".to_string(), "essay".to_string(), "math".to_string()]
    );
}

#[test]
fn a_spread_stages_its_promise_before_the_preview_confirms_and_a_refusal_takes_it_back() {
    let mut flow = PlanFlow {
        plan_after_save: vec!["older".into()],
        split_whole: vec!["made-old".into(), "kept".into()],
        allow_split_pending: Some("essay".into()),
        ..PlanFlow::default()
    };
    let made = vec!["made-old".into(), "made-new".into()];
    let plan_ids = vec!["made-new".into()];
    flow.confirm_spread_transition(&made, &plan_ids, SpreadPhase::Stage);
    assert_eq!(
        flow.plan_after_save,
        vec!["older".to_string(), "made-new".to_string()]
    );
    assert_eq!(
        flow.split_whole,
        vec!["kept".to_string(), "made-new".to_string()]
    );
    assert_eq!(flow.allow_split_pending.as_deref(), Some("essay"));
    flow.confirm_spread_transition(&made, &plan_ids, SpreadPhase::Finish { ok: false });
    assert_eq!(flow.plan_after_save, vec!["older".to_string()]);
    assert_eq!(flow.split_whole, vec!["kept".to_string()]);
    assert!(flow.allow_split_pending.is_none());

    flow.allow_split_pending = Some("essay".into());
    flow.confirm_spread_transition(&made, &plan_ids, SpreadPhase::Stage);
    flow.confirm_spread_transition(&made, &plan_ids, SpreadPhase::Finish { ok: true });
    assert_eq!(
        flow.plan_after_save,
        vec!["older".to_string(), "made-new".to_string()]
    );
    assert_eq!(
        flow.split_whole,
        vec!["kept".to_string(), "made-new".to_string()]
    );
    assert!(flow.allow_split_pending.is_none());
}

#[test]
fn a_finished_homework_or_a_missing_one_does_not_spread() {
    let mut flow = PlanFlow {
        allow_split_pending: Some("essay".into()),
        ..PlanFlow::default()
    };
    assert!(flow.preview_spread_stop(None).unwrap());
    assert!(flow.allow_split_pending.is_none());
    flow.allow_split_pending = Some("essay".into());
    assert!(
        flow.preview_spread_stop(Some(&json!({"completed": true})))
            .unwrap()
    );
    assert!(flow.allow_split_pending.is_none());
    flow.allow_split_pending = Some("essay".into());
    assert!(
        !flow
            .preview_spread_stop(Some(&json!({"completed": false})))
            .unwrap()
    );
    assert_eq!(flow.allow_split_pending.as_deref(), Some("essay"));
}

#[test]
fn a_load_waiting_on_a_plan_runs_that_plan_once() {
    let mut flow = PlanFlow {
        plan_after_load: vec!["s-math".into()],
        replan_after_load: true,
        ..PlanFlow::default()
    };
    let steps = flow.plan_waiting_for_load();
    assert_eq!(kinds(&steps), vec!["solve_only", "solve_replan"]);
    assert!(flow.plan_waiting_for_load().is_empty());
}

#[derive(Default)]
struct Clock(AtomicU64);

impl Host for Clock {
    fn steady_ms(&self) -> i64 {
        1000
    }

    fn request_clock(&self) -> (i64, String) {
        (1_793_905_200, "2026-11-05T19:00".into())
    }

    fn restore_token(&self) -> String {
        format!("{:016x}", self.0.fetch_add(1, Ordering::Relaxed))
    }

    fn entropy(&self) -> Box<dyn Entropy + Send> {
        Box::new(Counting(self.0.fetch_add(1000, Ordering::Relaxed)))
    }

    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

#[test]
fn the_drafts_view_names_the_stored_weeks_of_a_sunday() {
    let db = TestDb::new("plan-flow-stored-weeks");
    let mut session = Session::new(db.path.clone(), Arc::new(Clock::default()), Arc::new(|| {}));
    session.frame().answer_inline();
    let answer: Value = serde_json::from_str(
        &session.send(
            &json!({
                "cmd": "drafts_set",
                "fields": {
                    "week_start": "2026-11-01",
                    "stored_parts": [],
                    "revision": [3, 4],
                },
            })
            .to_string(),
        ),
    )
    .unwrap();
    assert_eq!(answer["ok"], true, "{answer}");
    let view: Value = serde_json::from_str(&session.view("drafts.stored_weeks")).unwrap();
    assert_eq!(view, json!([["2026-10-26", 3], ["2026-11-02", 4]]));
}
