//! The focus timer's decisions (P4 group 6): the rules of controller.py's focus block, with expected
//! values worked out from them and from the desktop tests' names (desktop/tests/focus, planner, week, day).

use flexweek_app::session::focus;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-28";
const STOPPED: &str = "Schedule restored. The previous focus timer was stopped because \
its session no longer exists.";

/// A work phase of 30 minutes started at 0 on a block of the open week, and on a homework when `homework`.
fn work_timer(homework: bool) -> Value {
    json!({
        "weekStart": WEEK,
        "blockId": "b1",
        "assignmentId": if homework { json!("a1") } else { Value::Null },
        "day": 0,
        "start": "09:00",
        "title": "Essay",
        "phase": "work",
        "cycles": 0,
        "running": true,
        "endsAt": 1_800_000,
        "remainingMs": 1_800_000,
        "workMin": 30,
    })
}

fn elapsed(state: &Value, week: &str, now_ms: i64) -> Value {
    let args = json!({ "focus": state, "week_start": week, "prefs": {}, "now_ms": now_ms });
    focus::elapsed_min(&args).unwrap()
}

#[test]
fn elapsed_minutes_are_whole_minutes_rounded_down() {
    let state = work_timer(true);
    assert_eq!(elapsed(&state, WEEK, 659_999), json!(10));
    assert_eq!(elapsed(&state, WEEK, 660_000), json!(11));
}

#[test]
fn a_session_ended_before_one_whole_minute_credits_nothing() {
    let state = work_timer(true);
    assert_eq!(elapsed(&state, WEEK, 59_999), json!(0));
    assert_eq!(elapsed(&state, WEEK, 0), json!(0));
}

#[test]
fn ending_during_a_break_credits_nothing_more() {
    let mut resting = work_timer(true);
    resting["phase"] = json!("break");
    resting["endsAt"] = json!(900_000);
    resting["remainingMs"] = json!(900_000);
    assert_eq!(elapsed(&resting, WEEK, 600_000), json!(0));
    assert_eq!(elapsed(&Value::Null, WEEK, 600_000), json!(0));
}

#[test]
fn a_block_is_credited_only_from_its_own_week_and_a_homework_from_any() {
    assert_eq!(elapsed(&work_timer(false), "2026-10-05", 600_000), json!(0));
    assert_eq!(elapsed(&work_timer(false), WEEK, 600_000), json!(10));
    assert_eq!(elapsed(&work_timer(true), "2026-10-05", 600_000), json!(10));
}

#[test]
fn a_paused_work_phase_counts_the_time_it_had_run() {
    let mut paused = work_timer(true);
    paused["running"] = json!(false);
    paused["remainingMs"] = json!(1_200_000);
    assert_eq!(elapsed(&paused, WEEK, 5_000_000), json!(10));
}

fn decision(running: &Value, target: &Value, replace: bool) -> Value {
    let args = json!({ "focus": running, "target": target, "replace": replace });
    focus::start_decision(&args).unwrap()
}

fn homework_target(id: &str) -> Value {
    json!({ "weekStart": WEEK, "blockId": null, "assignmentId": id, "title": "Essay" })
}

#[test]
fn the_same_running_homework_is_the_same_timer() {
    let running = json!({ "phase": "work", "assignmentId": "a1", "blockId": null });
    assert_eq!(decision(&running, &homework_target("a1"), false), "same");
}

#[test]
fn another_homework_asks_to_replace_and_replace_begins() {
    let running = json!({ "phase": "work", "assignmentId": "a1", "blockId": null });
    assert_eq!(decision(&running, &homework_target("a2"), false), "ask");
    assert_eq!(decision(&running, &homework_target("a2"), true), "begin");
    assert_eq!(
        decision(&Value::Null, &homework_target("a2"), false),
        "begin"
    );
}

#[test]
fn the_same_running_block_is_the_same_timer_and_another_asks() {
    let running = json!({ "phase": "break", "assignmentId": null, "blockId": "b1" });
    let same = json!({ "blockId": "b1", "assignmentId": null });
    let other = json!({ "blockId": "b2", "assignmentId": null });
    assert_eq!(decision(&running, &same, false), "same");
    assert_eq!(decision(&running, &other, false), "ask");
}

#[test]
fn an_ended_timer_is_never_the_same_timer() {
    let running = json!({ "phase": "ended", "assignmentId": "a1", "blockId": "b1" });
    assert_eq!(decision(&running, &homework_target("a1"), false), "ask");
    let block = json!({ "blockId": "b1", "assignmentId": null });
    assert_eq!(decision(&running, &block, false), "ask");
}

#[test]
fn a_quick_timer_is_not_the_same_as_another_quick_timer() {
    let running = json!({ "phase": "work", "assignmentId": null, "blockId": null });
    let quick = json!({ "blockId": null, "assignmentId": null, "title": "Quick focus" });
    assert_eq!(decision(&running, &quick, false), "ask");
}

fn target_args(block_id: Value, day: Value) -> Value {
    json!({
        "block_id": block_id,
        "day": day,
        "quick": false,
        "week_start": WEEK,
        "assignments": { "a1": { "title": "Essay" } },
        "blocks": [
            { "id": "b1", "title": "Write", "assignment_id": "a1", "days": [2], "start": "09:00" },
            { "id": "b2", "title": "Read", "assignment_id": "a1", "days": [3], "start": null },
            { "id": "b3", "title": "Done", "assignment_id": "a1", "days": [1], "start": "08:00",
              "completed": true },
            { "id": "b4", "title": "Rest", "days": [1], "start": "08:00", "pomodoro_role": "break" },
        ],
        "trace": { "placed": [
            { "id": "b2", "days": [3], "start": "10:00" },
            { "id": "b2", "days": [4], "start": "11:00" },
        ]},
        "overdue": [],
    })
}

const NOTHING_TO_START: &str = "Place a work block that isn't finished before starting focus.";

#[test]
fn a_quick_start_times_nothing_in_particular() {
    let mut args = target_args(Value::Null, Value::Null);
    args["quick"] = json!(true);
    let planned = focus::start_target(&args).unwrap();
    assert_eq!(
        planned["target"],
        json!({ "weekStart": WEEK, "blockId": null, "assignmentId": null, "day": null,
            "start": null, "title": "Quick focus" })
    );
}

#[test]
fn a_homework_is_timed_on_its_own_and_says_when_it_is_overdue() {
    let args = target_args(json!("a1"), Value::Null);
    let planned = focus::start_target(&args).unwrap();
    assert_eq!(planned["target"]["assignmentId"], "a1");
    assert_eq!(planned["target"]["blockId"], Value::Null);
    assert_eq!(planned["target"]["title"], "Essay");
    let mut late = args;
    late["overdue"] = json!(["a1"]);
    let planned = focus::start_target(&late).unwrap();
    assert_eq!(planned["target"]["title"], "Essay, overdue");
}

#[test]
fn a_placed_block_is_timed_on_its_first_day() {
    let planned = focus::start_target(&target_args(json!("b1"), Value::Null)).unwrap();
    assert_eq!(
        planned["target"],
        json!({ "weekStart": WEEK, "blockId": "b1", "assignmentId": "a1", "day": 2,
            "start": "09:00", "title": "Write" })
    );
}

#[test]
fn a_block_placed_only_in_the_plan_takes_the_day_asked_for() {
    let planned = focus::start_target(&target_args(json!("b2"), json!(4))).unwrap();
    assert_eq!(planned["target"]["day"], 4);
    assert_eq!(planned["target"]["start"], "11:00");
    let planned = focus::start_target(&target_args(json!("b2"), Value::Null)).unwrap();
    assert_eq!(planned["target"]["day"], 3);
    assert_eq!(planned["target"]["start"], "10:00");
}

#[test]
fn nothing_starts_on_a_missing_finished_break_or_unplaced_block() {
    for (id, day) in [
        (json!("nope"), Value::Null),
        (json!("b3"), Value::Null),
        (json!("b4"), Value::Null),
        (json!("b2"), json!(5)),
    ] {
        let planned = focus::start_target(&target_args(id.clone(), day)).unwrap();
        assert_eq!(planned["refuse"], NOTHING_TO_START, "{id}");
        assert!(planned.get("target").is_none(), "{id}");
    }
    let mut untraced = target_args(json!("b2"), Value::Null);
    untraced["trace"] = Value::Null;
    let planned = focus::start_target(&untraced).unwrap();
    assert_eq!(planned["refuse"], NOTHING_TO_START);
}

#[test]
fn a_homework_asked_for_on_a_day_is_looked_up_as_a_block() {
    let planned = focus::start_target(&target_args(json!("a1"), json!(2))).unwrap();
    assert_eq!(planned["refuse"], NOTHING_TO_START);
}

fn tick(state: &Value, waiting: bool, busy: bool, now_ms: i64) -> Value {
    let args =
        json!({ "focus": state, "credits_waiting": waiting, "busy": busy, "now_ms": now_ms });
    focus::tick_step(&args).unwrap()
}

#[test]
fn a_tick_credits_waiting_sessions_only_when_no_save_is_going() {
    assert_eq!(tick(&Value::Null, true, false, 0)["credit"], true);
    assert_eq!(tick(&Value::Null, true, true, 0)["credit"], false);
    assert_eq!(tick(&Value::Null, false, false, 0)["credit"], false);
}

#[test]
fn a_tick_means_ended_changed_or_nothing() {
    let running = work_timer(true);
    assert_eq!(tick(&running, false, false, 1_799_999)["action"], "changed");
    assert_eq!(tick(&running, false, false, 1_800_000)["action"], "ended");
    assert_eq!(tick(&running, false, false, 2_000_000)["action"], "ended");
    let mut paused = running;
    paused["running"] = json!(false);
    assert_eq!(tick(&paused, false, false, 2_000_000)["action"], "none");
    assert_eq!(tick(&Value::Null, false, false, 0)["action"], "none");
}

fn begin(state: &Value, busy: bool, completed: bool) -> Value {
    focus::advance_begin(&json!({ "focus": state, "focus_busy": busy, "completed": completed }))
        .unwrap()
}

#[test]
fn advancing_credits_only_a_completed_work_phase() {
    let work = work_timer(true);
    assert_eq!(
        begin(&work, false, true),
        json!({ "go": true, "credit": true })
    );
    assert_eq!(
        begin(&work, false, false),
        json!({ "go": true, "credit": false })
    );
    let mut resting = work_timer(true);
    resting["phase"] = json!("break");
    assert_eq!(
        begin(&resting, false, true),
        json!({ "go": true, "credit": false })
    );
}

#[test]
fn advancing_does_nothing_without_a_timer_while_busy_or_once_ended() {
    let go = |state: &Value, busy: bool| begin(state, busy, true)["go"].clone();
    assert_eq!(go(&Value::Null, false), false);
    assert_eq!(go(&work_timer(true), true), false);
    let mut ended = work_timer(true);
    ended["phase"] = json!("ended");
    assert_eq!(go(&ended, false), false);
}

fn plan(state: &Value, completed: bool, known: bool, prefs: &Value) -> Value {
    let args = json!({
        "focus": state,
        "completed": completed,
        "assignment_known": known,
        "prefs": prefs,
        "now_ms": 1_000,
    });
    focus::advance_plan(&args).unwrap()
}

#[test]
fn a_finished_work_phase_counts_a_cycle_and_goes_to_a_short_break() {
    let planned = plan(&work_timer(false), true, false, &json!({}));
    assert_eq!(planned["cycles"], 1);
    assert_eq!(planned["state"]["cycles"], 1);
    assert_eq!(planned["state"]["phase"], "break");
    assert_eq!(planned["state"]["running"], true);
    assert_eq!(planned["state"]["remainingMs"], 15 * 60_000);
    assert_eq!(planned["state"]["endsAt"], 1_000 + 15 * 60_000);
    assert_eq!(
        planned["alert"],
        json!({ "title": "Break", "body": "Essay", "kind": "focus", "tone": "soft" })
    );
    assert_eq!(planned["alert_first"], true);
}

#[test]
fn every_fourth_cycle_is_followed_by_a_long_break() {
    let mut third = work_timer(false);
    third["cycles"] = json!(3);
    let planned = plan(&third, true, false, &json!({}));
    assert_eq!(planned["state"]["phase"], "long_break");
    assert_eq!(planned["state"]["remainingMs"], 30 * 60_000);
    assert_eq!(planned["alert"]["title"], "Long break");
}

#[test]
fn skipping_a_work_phase_counts_no_cycle() {
    let planned = plan(&work_timer(false), false, false, &json!({}));
    assert_eq!(planned["cycles"], 0);
    assert_eq!(planned["state"]["phase"], "break");
}

#[test]
fn a_break_ends_into_a_bright_work_phase_with_the_current_length() {
    let mut resting = work_timer(false);
    resting["phase"] = json!("break");
    resting["cycles"] = json!(1);
    let planned = plan(&resting, true, false, &json!({ "timer_work_min": 25 }));
    assert_eq!(planned["state"]["phase"], "work");
    assert_eq!(planned["state"]["workMin"], 25);
    assert_eq!(planned["state"]["remainingMs"], 25 * 60_000);
    assert_eq!(
        planned["alert"],
        json!({ "title": "Focus session", "body": "Essay", "kind": "focus", "tone": "bright" })
    );
    assert!(
        planned.get("cycles").is_none(),
        "a break leaves the cycles alone"
    );
    assert_eq!(planned["state"]["cycles"], 1);
}

#[test]
fn a_completed_homework_session_ends_the_timer_and_tells_after_keeping_it() {
    let planned = plan(&work_timer(true), true, true, &json!({}));
    assert_eq!(planned["state"]["phase"], "ended");
    assert_eq!(planned["state"]["running"], false);
    assert_eq!(planned["state"]["remainingMs"], 0);
    assert_eq!(planned["state"]["cycles"], 1);
    assert_eq!(
        planned["alert"],
        json!({ "title": "Focus session finished", "body": "Essay", "kind": "focus", "tone": "soft" })
    );
    assert_eq!(planned["alert_first"], false);
}

#[test]
fn a_homework_that_is_not_loaded_or_a_skip_goes_on_to_a_break() {
    assert_eq!(
        plan(&work_timer(true), true, false, &json!({}))["state"]["phase"],
        "break"
    );
    assert_eq!(
        plan(&work_timer(true), false, true, &json!({}))["state"]["phase"],
        "break"
    );
}

#[test]
fn entering_a_phase_names_its_notice() {
    let args =
        json!({ "state": work_timer(false), "phase": "long_break", "prefs": {}, "now_ms": 0 });
    let entered = focus::enter_phase(&args).unwrap();
    assert_eq!(entered["state"]["phase"], "long_break");
    assert_eq!(entered["alert"]["title"], "Long break");
    assert_eq!(entered["alert"]["tone"], "soft");
}

fn credit(state: &Value, assignments: Value, blocks: Value, work_min: i64) -> Value {
    let args = json!({
        "state": state,
        "week_start": WEEK,
        "assignments": assignments,
        "blocks": blocks,
        "work_min": work_min,
    });
    focus::credit_plan(&args).unwrap()
}

#[test]
fn a_credit_goes_to_the_homework_whichever_week_is_open() {
    let mut state = work_timer(true);
    state["weekStart"] = json!("2026-09-21");
    let homework = json!({ "a1": { "id": "a1", "focus_sessions": 2, "focus_minutes": 50 } });
    let planned = credit(&state, homework, json!([]), 30);
    assert_eq!(planned["to"], "assignment");
    assert_eq!(planned["updated"]["focus_sessions"], 3);
    assert_eq!(planned["updated"]["focus_minutes"], 80);
}

#[test]
fn a_credit_to_a_homework_that_did_not_load_says_so() {
    let planned = credit(&work_timer(true), json!({}), json!([]), 30);
    assert_eq!(
        planned["say"],
        "This homework did not load, so the focus time was not counted. \
Reload the week and try again."
    );
}

#[test]
fn a_credit_goes_to_the_block_only_from_its_own_week() {
    let blocks = json!([{ "id": "b1", "title": "Write" }]);
    let planned = credit(&work_timer(false), json!({}), blocks.clone(), 25);
    assert_eq!(planned["to"], "block");
    assert_eq!(planned["updated"]["id"], "b1");
    assert_eq!(planned["updated"]["focus_sessions"], 1);
    assert_eq!(planned["updated"]["focus_minutes"], 25);
    let mut elsewhere = work_timer(false);
    elsewhere["weekStart"] = json!("2026-09-21");
    assert_eq!(
        credit(&elsewhere, json!({}), blocks, 25),
        json!({ "skip": true })
    );
}

#[test]
fn a_credit_to_a_block_that_is_gone_is_skipped_without_words() {
    let planned = credit(&work_timer(false), json!({}), json!([]), 25);
    assert_eq!(planned, json!({ "skip": true }));
}

fn blocks_of_a_homework() -> Value {
    json!([
        { "id": "b1", "kind": "flexible", "days": [0], "start": "09:00", "assignment_id": "a1" },
        { "id": "b2", "kind": "flexible", "days": [1], "start": "10:00", "assignment_id": "a1" },
    ])
}

fn auto(state: &Value, blocks: Value, assignments: Value, material: bool, wanted: bool) -> Value {
    let args = json!({
        "state": state,
        "prefs": { "focus_auto_complete": wanted },
        "material_owns": material,
        "week_start": WEEK,
        "assignments": assignments,
        "blocks": blocks,
    });
    focus::auto_complete_plan(&args).unwrap()
}

fn open_homework() -> Value {
    json!({ "a1": { "id": "a1", "completed": false } })
}

#[test]
fn auto_complete_marks_the_worked_block_done_and_leaves_a_homework_with_sessions_open() {
    let planned = auto(
        &work_timer(true),
        blocks_of_a_homework(),
        open_homework(),
        true,
        true,
    );
    assert_eq!(
        planned["block"],
        json!({ "id": "b1", "start": "09:00", "completed_day": 0 })
    );
    assert_eq!(planned["complete_homework"], Value::Null);
}

#[test]
fn auto_complete_finishes_the_homework_with_its_last_unfinished_session() {
    let mut blocks = blocks_of_a_homework();
    blocks[1]["completed"] = json!(true);
    let planned = auto(
        &work_timer(true),
        blocks.clone(),
        open_homework(),
        true,
        true,
    );
    assert_eq!(planned["block"]["id"], "b1");
    assert_eq!(planned["complete_homework"], "a1");
    // A break block of the homework is not a work session.
    blocks[1]["completed"] = json!(false);
    blocks[1]["pomodoro_role"] = json!("break");
    let planned = auto(&work_timer(true), blocks, open_homework(), true, true);
    assert_eq!(planned["complete_homework"], "a1");
}

#[test]
fn auto_complete_leaves_a_finished_homework_alone() {
    let mut blocks = blocks_of_a_homework();
    blocks[1]["completed"] = json!(true);
    let done = json!({ "a1": { "id": "a1", "completed": true } });
    let planned = auto(&work_timer(true), blocks, done, true, true);
    assert_eq!(planned["block"]["id"], "b1");
    assert_eq!(planned["complete_homework"], Value::Null);
}

#[test]
fn a_quick_timer_never_auto_completes() {
    let mut quick = work_timer(false);
    quick["blockId"] = Value::Null;
    quick["day"] = Value::Null;
    quick["start"] = Value::Null;
    let planned = auto(&quick, blocks_of_a_homework(), open_homework(), true, true);
    assert_eq!(planned, json!({ "block": null, "complete_homework": null }));
}

#[test]
fn auto_complete_needs_the_setting_and_the_material_screens() {
    let nothing = json!({ "block": null, "complete_homework": null });
    let state = work_timer(true);
    assert_eq!(
        auto(&state, blocks_of_a_homework(), open_homework(), true, false),
        nothing
    );
    assert_eq!(
        auto(&state, blocks_of_a_homework(), open_homework(), false, true),
        nothing
    );
}

#[test]
fn a_block_off_its_day_is_not_marked_but_its_homework_is_still_checked() {
    let mut state = work_timer(true);
    state["day"] = json!(5);
    let mut blocks = blocks_of_a_homework();
    blocks[0]["completed"] = json!(true);
    blocks[1]["completed"] = json!(true);
    let planned = auto(&state, blocks, open_homework(), true, true);
    assert_eq!(planned["block"], Value::Null);
    assert_eq!(planned["complete_homework"], "a1");
}

#[test]
fn an_open_block_is_not_marked_on_a_day_it_is_not_on() {
    // The timer says Saturday; the block is still open but is only on Monday.
    let mut state = work_timer(true);
    state["day"] = json!(5);
    let planned = auto(&state, blocks_of_a_homework(), open_homework(), true, true);
    assert_eq!(planned["block"], Value::Null);
}

fn held(kinds: Value, state: &Value, prefs: Value, material: bool) -> Value {
    let args = json!({ "kinds": kinds, "focus": state, "prefs": prefs, "material_owns": material });
    focus::hold_alerts(&args).unwrap()["hold"].clone()
}

#[test]
fn a_hold_keeps_only_notices_that_are_not_about_focus() {
    let kinds = json!(["reminder", "focus", "alarm", null]);
    let work = work_timer(false);
    assert_eq!(
        held(kinds.clone(), &work, json!({}), true),
        json!([true, false, true, true])
    );
    assert_eq!(
        held(
            kinds.clone(),
            &work,
            json!({ "focus_auto_mute": false }),
            true
        ),
        json!([false, false, false, false])
    );
    let mut resting = work.clone();
    resting["phase"] = json!("break");
    assert_eq!(
        held(kinds.clone(), &resting, json!({}), true),
        json!([false, false, false, false])
    );
    assert_eq!(
        held(kinds.clone(), &Value::Null, json!({}), true),
        json!([false, false, false, false])
    );
    assert_eq!(
        held(kinds, &work, json!({}), false),
        json!([false, false, false, false])
    );
}

#[test]
fn focus_mutes_alerts_in_a_paused_work_phase_too() {
    let mut paused = work_timer(false);
    paused["running"] = json!(false);
    let args = json!({ "focus": paused, "prefs": null, "material_owns": true });
    assert_eq!(focus::mutes_alerts(&args).unwrap(), true);
    let args = json!({ "focus": paused, "prefs": null, "material_owns": false });
    assert_eq!(focus::mutes_alerts(&args).unwrap(), false);
}

fn dropped(state: &Value, week: &str, blocks: Value, announce: bool) -> Value {
    let args =
        json!({ "focus": state, "week_start": week, "blocks": blocks, "announce": announce });
    focus::drop_missing(&args).unwrap()
}

#[test]
fn a_timer_whose_block_is_gone_after_a_reload_is_dropped_with_the_words() {
    let gone = dropped(&work_timer(false), WEEK, json!([{ "id": "b9" }]), true);
    assert_eq!(gone, json!({ "drop": true, "say": STOPPED }));
    let quiet = dropped(&work_timer(false), WEEK, json!([]), false);
    assert_eq!(quiet, json!({ "drop": true, "say": null }));
}

#[test]
fn a_timer_whose_block_is_still_there_survives() {
    let blocks = json!([{ "id": "b1", "assignment_id": "a1" }]);
    let kept = json!({ "drop": false, "say": null });
    assert_eq!(dropped(&work_timer(true), WEEK, blocks.clone(), true), kept);
    assert_eq!(dropped(&work_timer(false), WEEK, blocks, true), kept);
}

#[test]
fn a_block_that_now_belongs_to_another_homework_does_not_keep_the_timer() {
    let blocks = json!([{ "id": "b1", "assignment_id": "a2" }]);
    assert_eq!(
        dropped(&work_timer(true), WEEK, blocks, false)["drop"],
        true
    );
}

#[test]
fn a_homework_or_quick_timer_or_another_week_is_left_alone() {
    let kept = json!({ "drop": false, "say": null });
    let mut homework = work_timer(true);
    homework["blockId"] = Value::Null;
    assert_eq!(dropped(&homework, WEEK, json!([]), true), kept);
    assert_eq!(dropped(&Value::Null, WEEK, json!([]), true), kept);
    assert_eq!(
        dropped(&work_timer(false), "2026-10-05", json!([]), true),
        kept
    );
}

fn on_wednesday() -> Value {
    let mut timer = work_timer(true);
    timer["day"] = json!(2);
    timer
}

fn rebased(state: &Value, first_weekday: u32) -> Value {
    focus::rebase(&json!({ "focus": state, "first_weekday": first_weekday })).unwrap()["state"]
        .clone()
}

#[test]
fn a_new_first_day_moves_the_timer_to_the_same_date_in_its_new_week() {
    // The timer points at Wednesday 2026-09-30 (day 2 of the week from Monday 2026-09-28).
    let wednesday = on_wednesday();
    let from_sunday = rebased(&wednesday, 6);
    assert_eq!(from_sunday["weekStart"], "2026-09-27");
    assert_eq!(from_sunday["day"], 3);
    let from_wednesday = rebased(&wednesday, 2);
    assert_eq!(from_wednesday["weekStart"], "2026-09-30");
    assert_eq!(from_wednesday["day"], 0);
    let from_monday = rebased(&wednesday, 0);
    assert_eq!(from_monday["weekStart"], WEEK);
    assert_eq!(from_monday["day"], 2);
}

#[test]
fn a_rebased_timer_keeps_everything_else() {
    let moved = rebased(&on_wednesday(), 6);
    let mut expected = on_wednesday();
    expected["weekStart"] = json!("2026-09-27");
    expected["day"] = json!(3);
    assert_eq!(moved, expected);
}

#[test]
fn a_timer_with_no_day_keeps_no_day_and_one_with_no_week_is_not_moved() {
    let mut quick = work_timer(false);
    quick["day"] = Value::Null;
    let moved = rebased(&quick, 6);
    assert_eq!(moved["weekStart"], "2026-09-27");
    assert_eq!(moved["day"], Value::Null);
    assert_eq!(rebased(&Value::Null, 6), Value::Null);
    let mut weekless = work_timer(false);
    weekless["weekStart"] = Value::Null;
    assert_eq!(rebased(&weekless, 6), Value::Null);
}
