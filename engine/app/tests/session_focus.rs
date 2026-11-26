//! The focus timer's decisions (P4 group 6): the rules of controller.py's focus block, with expected
//! values worked out from them and from the desktop tests' names (desktop/tests/focus, planner, week, day).

use flexweek_app::session::focus;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-28";
const STOPPED: &str =
    "Schedule restored. The focus timer stopped because its homework session no longer exists.";

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

const NOTHING_TO_START: &str = "Give an unfinished homework session a time before starting focus.";

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

const NEXT_WEEK: &str = "2026-10-05";
const BREAK_ENDED: &str = "The break ended while FlexWeek was closed. Press Resume to focus again.";
const SPOTIFY_MISSING: &str = "Focus started without Spotify. Add a link under Settings > Alerts.";
const SPOTIFY_FAILED: &str = "Focus started without Spotify because the app didn't open.";
const MORE_TIME: &str = "Choose how much more time it needs.";

fn call(decide: fn(&Value) -> flexweek_engine::EngineResult<Value>, args: Value) -> Value {
    decide(&args).unwrap()
}

fn shown_blocks() -> Value {
    json!([
        {"id": "locked", "kind": "locked", "start": null, "days": [0]},
        {"id": "flex", "kind": "flexible", "start": "09:00", "days": [0], "title": "Essay"},
        {"id": "open", "kind": "flexible", "start": null, "days": [1]},
        {"id": "blank", "kind": "flexible", "start": "", "days": [2]}
    ])
}

#[test]
fn scheduled_blocks_without_a_trace_keep_locked_and_timed_flexible_blocks() {
    let blocks = shown_blocks();
    let kept = json!([
        {"id": "locked", "kind": "locked", "start": null, "days": [0]},
        {"id": "flex", "kind": "flexible", "start": "09:00", "days": [0], "title": "Essay"}
    ]);
    for trace in [Value::Null, json!({}), json!(false)] {
        assert_eq!(
            call(
                focus::scheduled_blocks,
                json!({ "blocks": blocks, "trace": trace })
            ),
            kept
        );
    }
}

#[test]
fn a_trace_overlays_each_placed_row_and_the_last_block_with_an_id_wins() {
    let blocks = json!([
        {"id": "b", "kind": "flexible", "start": "09:00", "days": [0], "title": "First"},
        {"id": "b", "kind": "locked", "start": null, "days": [3], "title": "Second"},
        {"id": "open", "kind": "flexible", "start": "08:00", "days": [1], "title": "Open"}
    ]);
    let trace = json!({
        "placed": [
            {"id": "b", "days": [1, 2], "start": "10:00"},
            {"id": "gone", "days": [0], "start": "11:00", "title": "Extra"},
            {"id": "open"}
        ]
    });
    assert_eq!(
        call(
            focus::scheduled_blocks,
            json!({ "blocks": blocks, "trace": trace })
        ),
        json!([
            {"id": "b", "kind": "locked", "start": "10:00", "days": [1, 2], "title": "Second"},
            {"id": "gone", "days": [0], "start": "11:00", "title": "Extra"},
            {"id": "open", "kind": "flexible", "start": null, "days": [1], "title": "Open"}
        ])
    );
}

#[test]
fn a_trace_with_nothing_placed_shows_nothing_and_empty_days_fall_through() {
    let blocks = json!([{"id": "flex", "kind": "flexible", "start": "09:00", "days": [4]}]);
    assert_eq!(
        call(
            focus::scheduled_blocks,
            json!({ "blocks": blocks, "trace": {"placed": []} })
        ),
        json!([])
    );
    let overlaid = call(
        focus::scheduled_blocks,
        json!({
            "blocks": blocks,
            "trace": {"placed": [{"id": "flex", "days": [], "start": "12:00"}]}
        }),
    );
    assert_eq!(overlaid[0]["days"], json!([4]));
    assert_eq!(overlaid[0]["start"], "12:00");
    let missing_days = call(
        focus::scheduled_blocks,
        json!({
            "blocks": [{"id": "flex", "kind": "flexible"}],
            "trace": {"placed": [{"id": "flex", "start": "12:00"}]}
        }),
    );
    assert_eq!(missing_days[0]["days"], json!([]));
}

#[test]
fn days_that_are_not_a_list_are_refused() {
    let err = focus::scheduled_blocks(&json!({
        "blocks": [{"id": "flex", "days": [0]}],
        "trace": {"placed": [{"id": "flex", "days": "01"}]}
    }))
    .unwrap_err();
    assert_eq!(err, flexweek_engine::EngineError::value("days is a list"));
}

fn saved_timer(phase: &str, ends_at: i64) -> Value {
    json!({
        "assignmentId": null,
        "sessionId": "b1",
        "weekStart": WEEK,
        "day": 0,
        "start": "09:00",
        "phase": phase,
        "cycles": 0,
        "endsAt": ends_at,
        "remainingMs": 4000
    })
}

fn restored(saved: Value, now_ms: i64) -> Value {
    call(
        focus::restore_decision,
        json!({
            "saved": saved,
            "assignments": {},
            "blocks": [{"id": "b1", "title": "Essay"}],
            "prefs": null,
            "now_ms": now_ms
        }),
    )
}

#[test]
fn a_saved_timer_that_is_still_running_comes_back_active() {
    let decision = restored(saved_timer("work", 5000), 1000);
    assert_eq!(decision["action"], "active");
    assert_eq!(
        decision["state"],
        json!({
            "weekStart": WEEK,
            "blockId": "b1",
            "assignmentId": null,
            "day": 0,
            "start": "09:00",
            "title": "Essay",
            "phase": "work",
            "cycles": 0,
            "running": true,
            "endsAt": 5000,
            "remainingMs": 4000
        })
    );
}

#[test]
fn a_saved_work_phase_that_ran_out_is_advanced() {
    let decision = restored(saved_timer("work", 500), 1000);
    assert_eq!(decision["action"], "advance_work");
    assert_eq!(decision["state"]["phase"], "work");
    assert_eq!(decision["state"]["running"], false);
    assert_eq!(decision["state"]["remainingMs"], 0);
    assert!(decision["state"].get("expired").is_none());
}

#[test]
fn a_saved_break_that_ran_out_pauses_on_work_and_says_so() {
    let decision = restored(saved_timer("break", 500), 1000);
    assert_eq!(decision["action"], "paused_work");
    assert_eq!(decision["say"], BREAK_ENDED);
    assert_eq!(decision["state"]["phase"], "break");
    assert_eq!(decision["state"]["running"], false);
    assert_eq!(decision["state"]["remainingMs"], 0);
    assert!(decision["state"].get("expired").is_none());
    assert_eq!(decision["paused"]["phase"], "work");
    assert_eq!(decision["paused"]["running"], false);
    assert_eq!(decision["paused"]["remainingMs"], 1_800_000);
    assert_eq!(decision["paused"]["endsAt"], 1_801_000);
    assert_eq!(decision["paused"]["workMin"], 30);
    assert_eq!(decision["paused"]["title"], "Essay");
}

#[test]
fn a_save_that_is_not_a_timer_is_dropped() {
    assert_eq!(restored(Value::Null, 1000), json!({ "action": "drop" }));
    assert_eq!(restored(json!({}), 1000), json!({ "action": "drop" }));
}

#[test]
fn spotify_opens_only_for_the_focus_sound_and_only_with_a_link() {
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": {}, "link": "spotify:track:1" })
        ),
        json!({ "action": "skip" })
    );
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": null, "link": "spotify:track:1" })
        ),
        json!({ "action": "skip" })
    );
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": {"focus_audio": "rain"}, "link": "spotify:track:1" })
        ),
        json!({ "action": "skip" })
    );
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": {"focus_audio": "spotify"}, "link": "" })
        ),
        json!({ "action": "say", "say": SPOTIFY_MISSING })
    );
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": {"focus_audio": "spotify"}, "link": null })
        ),
        json!({ "action": "say", "say": SPOTIFY_MISSING })
    );
    assert_eq!(
        call(
            focus::focus_spotify_decision,
            json!({ "prefs": {"focus_audio": "spotify"}, "link": "spotify:track:1" })
        ),
        json!({ "action": "open", "link": "spotify:track:1" })
    );
    assert_eq!(
        call(focus::focus_spotify_open_failed, json!({})),
        json!(SPOTIFY_FAILED)
    );
}

#[test]
fn a_start_needs_a_signed_in_session_that_is_not_busy() {
    let allowed = |signed_in, busy, focus_busy| {
        call(
            focus::start_allowed,
            json!({ "signed_in": signed_in, "busy": busy, "focus_busy": focus_busy }),
        )
    };
    assert_eq!(allowed(true, false, false), json!(true));
    assert_eq!(allowed(false, false, false), json!(false));
    assert_eq!(allowed(true, true, false), json!(false));
    assert_eq!(allowed(true, false, true), json!(false));
}

fn ended_homework() -> Value {
    let mut state = work_timer(true);
    state["phase"] = json!("ended");
    state["running"] = json!(false);
    state["remainingMs"] = json!(0);
    state
}

#[test]
fn pause_toggles_a_running_timer_and_ignores_one_that_has_ended() {
    let paused = call(
        focus::toggle_pause_decision,
        json!({ "focus": work_timer(true), "focus_busy": false, "busy": false, "now_ms": 600_000 }),
    );
    assert_eq!(paused["action"], "apply");
    let mut expected = work_timer(true);
    expected["running"] = json!(false);
    expected["remainingMs"] = json!(1_200_000);
    assert_eq!(paused["state"], expected);
    assert_eq!(
        call(
            focus::toggle_pause_decision,
            json!({ "focus": ended_homework(), "focus_busy": false, "busy": false, "now_ms": 0 })
        ),
        json!({ "action": "ignore" })
    );
    assert_eq!(
        call(
            focus::toggle_pause_decision,
            json!({ "focus": work_timer(true), "focus_busy": true, "busy": false, "now_ms": 0 })
        )["action"],
        "ignore"
    );
    assert_eq!(
        call(
            focus::toggle_pause_decision,
            json!({ "focus": null, "focus_busy": false, "busy": false, "now_ms": 0 })
        )["action"],
        "ignore"
    );
}

#[test]
fn ending_early_credits_only_a_whole_minute_already_worked() {
    assert_eq!(
        call(
            focus::end_early_decision,
            json!({ "focus": work_timer(true), "week_start": WEEK, "prefs": {}, "now_ms": 600_000 })
        ),
        json!({ "credit": true, "minutes": 10 })
    );
    assert_eq!(
        call(
            focus::end_early_decision,
            json!({ "focus": work_timer(true), "week_start": WEEK, "prefs": {}, "now_ms": 0 })
        ),
        json!({ "credit": false, "minutes": 0 })
    );
    let mut resting = work_timer(true);
    resting["phase"] = json!("break");
    assert_eq!(
        call(
            focus::end_early_decision,
            json!({ "focus": resting, "week_start": WEEK, "prefs": {}, "now_ms": 600_000 })
        ),
        json!({ "credit": false, "minutes": 0 })
    );
}

fn credit_of(state: Value, minutes: Value, finished: bool, busy: bool) -> Value {
    call(
        focus::credit_enqueue_decision,
        json!({
            "focus": state,
            "prefs": {},
            "minutes": minutes,
            "finished": finished,
            "busy": busy
        }),
    )
}

#[test]
fn a_credit_waits_while_a_save_is_busy_and_is_ignored_with_nothing_to_credit() {
    let waiting = credit_of(work_timer(true), Value::Null, true, true);
    assert_eq!(waiting["action"], "enqueue");
    assert_eq!(waiting["credit"]["work_min"], 30);
    assert_eq!(waiting["credit"]["finished"], true);
    assert_eq!(waiting["credit"]["state"]["assignmentId"], "a1");
    let now = credit_of(work_timer(true), json!(12), false, false);
    assert_eq!(now["action"], "apply");
    assert_eq!(now["credit"]["work_min"], 12);
    assert_eq!(now["credit"]["finished"], false);
    assert_eq!(
        credit_of(Value::Null, Value::Null, true, false)["action"],
        "ignore"
    );
    let mut quick = work_timer(false);
    quick["blockId"] = Value::Null;
    assert_eq!(
        credit_of(quick, Value::Null, true, false)["action"],
        "ignore"
    );
}

#[test]
fn applying_a_credit_replaces_the_homework_or_every_block_with_that_id() {
    let updated = json!({"id": "b1", "title": "Essay", "focus_minutes": 30});
    assert_eq!(
        call(
            focus::apply_credit_blocks,
            json!({ "to": "assignment", "updated": updated, "blocks": [] })
        ),
        json!({ "homework": updated, "blocks": null })
    );
    let blocks = json!([
        {"id": "b1", "title": "Old"},
        {"id": "b2", "title": "Other"},
        {"id": "b1", "title": "Also old"}
    ]);
    assert_eq!(
        call(
            focus::apply_credit_blocks,
            json!({ "to": "block", "updated": updated, "blocks": blocks })
        ),
        json!({
            "homework": null,
            "blocks": [updated, {"id": "b2", "title": "Other"}, updated]
        })
    );
}

#[test]
fn auto_complete_marks_only_the_one_block_and_does_nothing_without_one() {
    assert_eq!(
        call(
            focus::apply_auto_complete_blocks,
            json!({ "blocks": [], "done": null })
        ),
        json!({ "changed": false, "blocks": null })
    );
    let blocks = json!([
        {"id": "b1", "start": "09:00", "completed": false, "title": "Essay"},
        {"id": "b2", "start": "10:00", "completed": false}
    ]);
    assert_eq!(
        call(
            focus::apply_auto_complete_blocks,
            json!({ "blocks": blocks, "done": {"id": "b1", "start": "16:00", "completed_day": 0} })
        ),
        json!({
            "changed": true,
            "blocks": [
                {"id": "b1", "start": "16:00", "completed": true, "completed_day": 0, "title": "Essay"},
                {"id": "b2", "start": "10:00", "completed": false}
            ]
        })
    );
}

fn split(kinds_and_bodies: Value, phase: &str, material: bool) -> Value {
    let mut focus = work_timer(false);
    focus["phase"] = json!(phase);
    call(
        focus::split_held,
        json!({
            "notices": kinds_and_bodies,
            "focus": focus,
            "prefs": {},
            "material_owns": material
        }),
    )
}

#[test]
fn focus_holds_back_notices_that_are_not_about_focus() {
    let notices = json!([
        {"kind": "reminder", "title": "Due"},
        {"kind": "focus", "title": "Break"},
        {"kind": "alarm", "title": "Bell"},
        {"title": "No kind"}
    ]);
    let held = split(notices.clone(), "work", true);
    assert_eq!(held["show"], json!([{"kind": "focus", "title": "Break"}]));
    assert_eq!(
        held["hold"],
        json!([
            {"kind": "reminder", "title": "Due"},
            {"kind": "alarm", "title": "Bell"},
            {"title": "No kind"}
        ])
    );
    let shown = split(notices, "break", true);
    assert_eq!(shown["hold"], json!([]));
    assert_eq!(shown["show"].as_array().unwrap().len(), 4);
}

#[test]
fn held_notices_are_released_only_when_focus_is_not_muting() {
    let mut work = work_timer(false);
    let args = |held: Value, state: &Value| json!({ "held": held, "focus": state, "prefs": {}, "material_owns": true });
    assert_eq!(
        call(focus::release_held, args(json!([]), &work)),
        json!(false)
    );
    assert_eq!(
        call(
            focus::release_held,
            args(json!([{"kind": "reminder"}]), &work)
        ),
        json!(false)
    );
    work["phase"] = json!("break");
    assert_eq!(
        call(
            focus::release_held,
            args(json!([{"kind": "reminder"}]), &work)
        ),
        json!(true)
    );
}

fn essay_blocks() -> Value {
    json!([
        {"id": "b1", "kind": "flexible", "days": [0], "start": "09:00", "title": "Essay"},
        {"id": "b2", "kind": "locked", "days": [1], "start": "10:00"}
    ])
}

fn essay_assignments() -> Value {
    json!({ "a1": {"id": "a1", "title": "Essay", "estimate_min": 60} })
}

fn finish_args(state: Value, week: &str, busy: bool) -> Value {
    json!({
        "focus": state,
        "busy": busy,
        "focus_busy": false,
        "week_start": week,
        "blocks": essay_blocks(),
        "assignments": essay_assignments()
    })
}

#[test]
fn mark_finished_on_the_open_week_writes_the_session_it_ran() {
    let mut state = ended_homework();
    state["start"] = json!("16:00");
    let plan = call(focus::finish_focused_plan, finish_args(state, WEEK, false));
    assert_eq!(plan["action"], "finish");
    assert_eq!(plan["assignment_id"], "a1");
    assert_eq!(
        plan["blocks"][0],
        json!({
            "id": "b1",
            "kind": "flexible",
            "days": [0],
            "start": "16:00",
            "title": "Essay",
            "completed": true,
            "completed_day": 0
        })
    );
    assert_eq!(plan["blocks"][1]["id"], "b2");
    assert_eq!(plan["blocks"][1].get("completed"), None);
}

#[test]
fn mark_finished_on_another_week_waits_and_finishes_once_that_week_loads() {
    let plan = call(
        focus::finish_focused_plan,
        finish_args(ended_homework(), NEXT_WEEK, false),
    );
    assert_eq!(plan, json!({ "action": "load_then_finish", "week": WEEK }));
    let mut state = ended_homework();
    state["start"] = json!("16:00");
    let mut args = finish_args(state, WEEK, false);
    args["waiting"] = json!(true);
    args["pending"] = json!(WEEK);
    args["load_ok"] = json!(true);
    let landed = call(focus::finish_after_load, args);
    assert_eq!(landed["action"], "finish");
    assert_eq!(landed["assignment_id"], "a1");
    assert_eq!(landed["blocks"][0]["completed"], true);
    assert_eq!(landed["blocks"][0]["completed_day"], 0);
    assert_eq!(landed["blocks"][0]["start"], "16:00");
}

#[test]
fn a_failed_load_or_a_different_week_finishes_nothing() {
    let mut args = finish_args(ended_homework(), NEXT_WEEK, false);
    args["waiting"] = json!(true);
    args["pending"] = json!(WEEK);
    args["load_ok"] = json!(false);
    assert_eq!(
        call(focus::finish_after_load, args.clone())["action"],
        "drop"
    );
    args["load_ok"] = json!(true);
    args["week_start"] = json!(NEXT_WEEK);
    assert_eq!(
        call(focus::finish_after_load, args.clone())["action"],
        "drop"
    );
    args["waiting"] = json!(false);
    assert_eq!(call(focus::finish_after_load, args)["action"], "none");
    assert_eq!(
        call(
            focus::finish_intent_on_request,
            json!({ "waiting": true, "pending": WEEK, "requested": NEXT_WEEK })
        ),
        json!("drop")
    );
    assert_eq!(
        call(
            focus::finish_intent_on_request,
            json!({ "waiting": true, "pending": WEEK, "requested": WEEK })
        ),
        json!("keep")
    );
    assert_eq!(
        call(
            focus::finish_intent_on_request,
            json!({ "waiting": false, "pending": null, "requested": NEXT_WEEK })
        ),
        json!("keep")
    );
}

#[test]
fn mark_finished_does_nothing_when_it_cannot_and_clears_a_flexible_block_without_a_day() {
    assert_eq!(
        call(
            focus::finish_focused_plan,
            finish_args(work_timer(true), WEEK, false)
        )["action"],
        "ignore"
    );
    assert_eq!(
        call(
            focus::finish_focused_plan,
            finish_args(ended_homework(), WEEK, true)
        )["action"],
        "ignore"
    );
    let mut unknown = ended_homework();
    unknown["assignmentId"] = json!("missing");
    assert_eq!(
        call(
            focus::finish_focused_plan,
            finish_args(unknown, WEEK, false)
        )["action"],
        "ignore"
    );
    let mut state = ended_homework();
    state["start"] = Value::Null;
    let plan = call(focus::finish_focused_plan, finish_args(state, WEEK, false));
    assert_eq!(plan["action"], "finish");
    assert_eq!(plan["blocks"][0]["start"], Value::Null);
    assert_eq!(plan["blocks"][0].get("completed"), None);
    let mut kept = essay_blocks();
    kept[0]["completed_day"] = json!(2);
    let mut state = ended_homework();
    state["start"] = Value::Null;
    let plan = call(
        focus::finish_focused_plan,
        json!({
            "focus": state,
            "busy": false,
            "focus_busy": false,
            "week_start": WEEK,
            "blocks": kept,
            "assignments": essay_assignments()
        }),
    );
    assert_eq!(plan["blocks"][0]["start"], "09:00");
    assert_eq!(plan["blocks"][0]["completed_day"], 2);
}

#[test]
fn a_bool_day_counts_as_a_whole_day_the_way_python_does() {
    let mut state = ended_homework();
    state["day"] = json!(true);
    state["start"] = json!("16:00");
    let mut blocks = essay_blocks();
    blocks[0]["days"] = json!([1]);
    let plan = call(
        focus::finish_focused_plan,
        json!({
            "focus": state,
            "busy": false,
            "focus_busy": false,
            "week_start": WEEK,
            "blocks": blocks,
            "assignments": essay_assignments()
        }),
    );
    assert_eq!(plan["blocks"][0]["completed"], true);
    assert_eq!(plan["blocks"][0]["completed_day"], true);
    assert_eq!(plan["blocks"][0]["start"], "16:00");
}

#[test]
fn restart_begins_the_same_homework_again() {
    let plan = call(
        focus::restart_finished_plan,
        json!({
            "focus": ended_homework(),
            "busy": false,
            "focus_busy": false,
            "prefs": {},
            "now_ms": 0
        }),
    );
    assert_eq!(plan["action"], "begin");
    assert_eq!(
        plan["state"],
        json!({
            "weekStart": WEEK,
            "blockId": "b1",
            "assignmentId": "a1",
            "day": 0,
            "start": "09:00",
            "title": "Essay",
            "phase": "work",
            "cycles": 0,
            "running": true,
            "remainingMs": 1_800_000,
            "endsAt": 1_800_000,
            "workMin": 30
        })
    );
    assert_eq!(
        call(
            focus::restart_finished_plan,
            json!({
                "focus": ended_homework(),
                "busy": true,
                "focus_busy": false,
                "prefs": {},
                "now_ms": 0
            })
        )["action"],
        "ignore"
    );
}

fn more_time(minutes: i64, assignment: Value, busy: bool) -> flexweek_engine::EngineResult<Value> {
    let mut state = ended_homework();
    state["assignmentId"] = json!("a1");
    focus::add_focus_time_plan(&json!({
        "focus": state,
        "busy": busy,
        "focus_busy": false,
        "assignments": {"a1": assignment},
        "minutes": minutes,
        "prefs": {},
        "now_ms": 0
    }))
}

#[test]
fn more_time_adds_a_choice_and_starts_a_break() {
    let plan = more_time(
        15,
        json!({"id": "a1", "title": "Essay", "estimate_min": 60}),
        false,
    )
    .unwrap();
    assert_eq!(plan["action"], "apply");
    assert_eq!(plan["homework"]["estimate_min"], 75);
    assert_eq!(plan["homework"]["title"], "Essay");
    assert_eq!(plan["history_label"], "adding time to Essay");
    assert_eq!(plan["state"]["phase"], "break");
    assert_eq!(plan["state"]["running"], true);
    assert_eq!(plan["state"]["remainingMs"], 900_000);
    assert_eq!(plan["state"]["endsAt"], 900_000);
    assert_eq!(plan["state"]["workMin"], 30);
    assert_eq!(
        plan["alert"],
        json!({ "title": "Break", "body": "Essay", "kind": "focus", "tone": "soft" })
    );
    assert_eq!(
        more_time(
            10,
            json!({"id": "a1", "title": "Essay", "estimate_min": 60}),
            false
        )
        .unwrap(),
        json!({ "action": "refuse", "say": MORE_TIME })
    );
    assert_eq!(
        more_time(
            15,
            json!({"id": "a1", "title": "Essay", "estimate_min": 1440}),
            false
        )
        .unwrap()["action"],
        "refuse"
    );
    assert_eq!(
        more_time(
            15,
            json!({"id": "a1", "title": "Essay", "estimate_min": 60}),
            true
        )
        .unwrap()["action"],
        "ignore"
    );
}

#[test]
fn more_time_keeps_the_key_error_when_the_estimate_or_the_title_is_not_there() {
    let missing = more_time(15, json!({"id": "a1", "title": "Essay"}), false).unwrap_err();
    assert_eq!(missing, flexweek_engine::EngineError::key("estimate_min"));
    let title = more_time(
        15,
        json!({"id": "a1", "title": 1, "estimate_min": 60}),
        false,
    )
    .unwrap_err();
    assert_eq!(title, flexweek_engine::EngineError::key("title"));
}

#[test]
fn a_break_after_a_finished_timer_does_not_care_that_a_save_is_busy() {
    let mut state = ended_homework();
    state["cycles"] = json!(4);
    let plan = call(
        focus::take_break_plan,
        json!({
            "focus": state,
            "busy": true,
            "focus_busy": false,
            "prefs": {},
            "now_ms": 0
        }),
    );
    assert_eq!(plan["action"], "apply");
    assert_eq!(plan["state"]["phase"], "long_break");
    assert_eq!(plan["state"]["remainingMs"], 1_800_000);
    assert_eq!(plan["state"]["endsAt"], 1_800_000);
    assert_eq!(
        plan["alert"],
        json!({ "title": "Long break", "body": "Essay", "kind": "focus", "tone": "soft" })
    );
    assert_eq!(
        call(
            focus::take_break_plan,
            json!({ "focus": work_timer(true), "focus_busy": false, "prefs": {}, "now_ms": 0 })
        )["action"],
        "ignore"
    );
    assert_eq!(
        call(
            focus::take_break_plan,
            json!({ "focus": ended_homework(), "focus_busy": true, "prefs": {}, "now_ms": 0 })
        )["action"],
        "ignore"
    );
}
