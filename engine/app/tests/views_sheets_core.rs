//! Sheet lifecycle, save and delete flows, alarms and the notice bar (P5-S4). Expected sentences and
//! step orders are the ones the Python `SheetsBridge` produced and the desktop tests pin.

use flexweek_app::views::sheets_core::{
    DELETED_ALARM, NOTICE_MS, SAVED_ALARM, UNDO_ALSO, WAIT_DELETE, WAIT_SAVE, doubled_words, plan,
    words,
};
use flexweek_engine::ErrorKind;
use serde_json::{Value, json};

fn run(op: &str, facts: Value) -> Value {
    plan(op, &facts).unwrap_or_else(|error| panic!("{op}: {error:?}"))
}

/// `on.call` of each step, in order.
fn calls(steps: &Value) -> Vec<String> {
    steps
        .as_array()
        .expect("a list of steps")
        .iter()
        .map(|step| {
            format!(
                "{}.{}",
                step["on"].as_str().unwrap(),
                step["call"].as_str().unwrap()
            )
        })
        .collect()
}

fn say(words: &str, undo: bool) -> Value {
    let kwargs = if undo {
        json!({"undo": true})
    } else {
        json!({})
    };
    json!({"on": "bridge", "call": "_say", "args": [words], "kwargs": kwargs})
}

fn bridge(call: &str) -> Value {
    json!({"on": "bridge", "call": call, "args": [], "kwargs": {}})
}

fn set(name: &str, value: Value) -> Value {
    json!({"on": "bridge", "call": "__setattr__", "args": [name, value], "kwargs": {}})
}

fn weeks(list: &[&str]) -> Vec<String> {
    list.iter().map(ToString::to_string).collect()
}

// Words ---------------------------------------------------------------------------------------

#[test]
fn the_words_python_exports_keep_their_old_values() {
    let all = words();
    assert_eq!(all["nothing_unfinished"], "None left");
    assert_eq!(all["notice_ms"], 10000);
    assert_eq!(
        all["wait_save"],
        "Saving your last change… Try Save again in a moment."
    );
    assert_eq!(
        all["wait_delete"],
        "Saving your last change… Try Delete again in a moment."
    );
    assert_eq!(
        all["undo_also"],
        "Undo also takes back anything changed after it."
    );
    assert_eq!(all["max_named_weeks"], 3);
    assert_eq!(all["discard"]["title"], "Discard your changes?");
    assert_eq!(all["discard"]["body"], "Your changes will be lost.");
    assert_eq!(
        all["discard"]["answers"],
        json!([
            {"id": "keep", "label": "Keep editing", "kind": "text"},
            {"id": "discard", "label": "Discard", "kind": "danger"},
        ])
    );
}

#[test]
fn one_doubled_week_is_named_with_its_day_and_month() {
    let said = doubled_words("Guitar", &weeks(&["2026-11-09"]), "2026-11-05").unwrap();
    assert_eq!(
        said,
        "Guitar also sits on its own in the week of 9 Nov, so it shows twice there. \
         Delete the extra one in that week if you don't want both."
    );
}

#[test]
fn two_and_three_doubled_weeks_are_listed_with_and() {
    let two = doubled_words(
        "Guitar",
        &weeks(&["2026-11-09", "2026-11-16"]),
        "2026-11-05",
    )
    .unwrap();
    assert!(two.contains("in the weeks of 9 Nov and 16 Nov, so it shows twice"));
    assert!(two.ends_with("Delete the extra one in those weeks if you don't want both."));
    let three = doubled_words(
        "Guitar",
        &weeks(&["2026-11-09", "2026-11-16", "2026-11-23"]),
        "2026-11-05",
    )
    .unwrap();
    assert!(three.contains("weeks of 9 Nov, 16 Nov and 23 Nov, so"));
}

#[test]
fn more_than_three_doubled_weeks_name_three_and_count_the_rest() {
    let said = doubled_words(
        "Guitar",
        &weeks(&[
            "2026-11-09",
            "2026-11-16",
            "2026-11-23",
            "2026-11-30",
            "2026-12-07",
        ]),
        "2026-11-05",
    )
    .unwrap();
    assert!(said.contains("weeks of 9 Nov, 16 Nov, 23 Nov and 2 more, so"));
}

#[test]
fn a_fourth_doubled_week_is_counted_not_named() {
    let said = doubled_words(
        "Guitar",
        &weeks(&["2026-11-09", "2026-11-16", "2026-11-23", "2026-11-30"]),
        "2026-11-05",
    )
    .unwrap();
    assert!(said.contains("weeks of 9 Nov, 16 Nov, 23 Nov and 1 more, so"));
}

#[test]
fn a_doubled_week_in_another_year_carries_its_year() {
    let said = doubled_words("Guitar", &weeks(&["2027-01-04"]), "2026-11-05").unwrap();
    assert!(said.contains("week of 4 Jan 2027, so"));
}

#[test]
fn a_doubled_week_that_is_not_a_date_is_refused() {
    let error = doubled_words("Guitar", &weeks(&["soon"]), "2026-11-05").unwrap_err();
    assert_eq!(error.kind, ErrorKind::Value);
    let none = doubled_words("Guitar", &[], "2026-11-05").unwrap_err();
    assert_eq!(none.kind, ErrorKind::Index);
}

// Refusals ------------------------------------------------------------------------------------

#[test]
fn an_unknown_plan_and_wrong_shaped_facts_are_refused() {
    assert_eq!(
        plan("nothing", &json!({})).unwrap_err().kind,
        ErrorKind::Value
    );
    assert_eq!(plan("hold", &json!({})).unwrap_err().kind, ErrorKind::Value);
    assert_eq!(plan("hold", &json!([])).unwrap_err().kind, ErrorKind::Type);
    let wrong = plan("hold", &json!({"can_save": "yes", "words": "w"})).unwrap_err();
    assert_eq!(wrong.kind, ErrorKind::Type);
    let wrong = plan("open_homework_at", &json!({
        "account": true, "armed": null, "week_start": null, "day": 0, "start_min": true, "end_min": 60,
    }))
    .unwrap_err();
    assert_eq!(wrong.kind, ErrorKind::Type);
}

// Saving held ---------------------------------------------------------------------------------

#[test]
fn a_write_in_flight_turns_save_off() {
    let free = |no_session, busy, pending, conflict| {
        run(
            "can_save",
            json!({"no_session": no_session, "busy": busy, "pending_save": pending, "conflict": conflict}),
        )
    };
    assert_eq!(free(false, false, false, false), json!(true));
    assert_eq!(free(true, false, false, false), json!(false));
    assert_eq!(free(false, true, false, false), json!(false));
    assert_eq!(free(false, false, true, false), json!(false));
    assert_eq!(free(false, false, false, true), json!(false));
}

#[test]
fn a_held_write_says_the_wait_words_and_republishes() {
    assert_eq!(
        run("hold", json!({"can_save": true, "words": WAIT_SAVE})),
        Value::Null
    );
    let held = run("hold", json!({"can_save": false, "words": WAIT_DELETE}));
    assert_eq!(held, json!([say(WAIT_DELETE, false), bridge("_publish")]));
}

#[test]
fn the_sheet_is_active_when_anything_is_open() {
    let active = |kind, more, ask_open, drag| {
        run(
            "active",
            json!({"kind": kind, "more": more, "ask_open": ask_open, "drag": drag}),
        )
    };
    assert_eq!(active("", false, false, false), json!(false));
    assert_eq!(active("block", false, false, false), json!(true));
    assert_eq!(active("", true, false, false), json!(true));
    assert_eq!(active("", false, true, false), json!(true));
    assert_eq!(active("", false, false, true), json!(true));
}

// Opening -------------------------------------------------------------------------------------

#[test]
fn add_homework_needs_an_account_and_a_flex_category_or_falls_back() {
    let open =
        |account, armed: Value| run("open_homework", json!({"account": account, "armed": armed}));
    assert_eq!(open(false, json!("study")), Value::Null);
    assert_eq!(open(true, json!("study")), json!({"category": "study"}));
    assert_eq!(
        open(true, json!("assignments")),
        json!({"category": "assignments"})
    );
    assert_eq!(
        open(true, json!("class")),
        json!({"category": "assignments"})
    );
    assert_eq!(open(true, Value::Null), json!({"category": "assignments"}));
}

fn at(start: i64, end: i64, week: Value) -> Value {
    run(
        "open_homework_at",
        json!({
            "account": true, "armed": "study", "week_start": week, "day": 2,
            "start_min": start, "end_min": end,
        }),
    )
}

#[test]
fn a_drawn_homework_time_runs_start_to_end_whichever_way_it_was_drawn() {
    let forward = at(9 * 60 + 5, 10 * 60, json!("2026-11-23"));
    assert_eq!(forward["start"], "09:05");
    assert_eq!(forward["duration"], 55);
    assert_eq!(forward["day"], 2);
    assert_eq!(forward["category"], "study");
    assert_eq!(at(10 * 60, 9 * 60 + 5, json!("2026-11-23")), forward);
}

#[test]
fn a_drawn_homework_time_under_fifteen_minutes_opens_nothing() {
    assert_eq!(at(540, 554, json!("2026-11-23")), Value::Null);
    assert_eq!(at(540, 555, json!("2026-11-23"))["duration"], 15);
}

#[test]
fn a_drawn_homework_is_due_that_weeks_sunday_night() {
    assert_eq!(at(540, 600, json!("2026-11-23"))["due"], "2026-11-29T23:59");
    assert_eq!(at(540, 600, Value::Null)["due"], Value::Null);
    assert_eq!(at(540, 600, json!(""))["due"], Value::Null);
}

fn block_at(start: i64, end: i64, preferences: Value, armed: Value) -> Value {
    run(
        "open_block_at",
        json!({
            "account": true, "armed": armed, "preferences": preferences, "day": 3,
            "start_min": start, "end_min": end,
        }),
    )
}

#[test]
fn a_fixed_time_for_a_flex_category_has_no_category_of_its_own() {
    assert_eq!(
        run("open_block", json!({"account": true, "armed": "study"}))["category"],
        Value::Null
    );
    assert_eq!(
        run("open_block", json!({"account": true, "armed": "class"}))["category"],
        "class"
    );
    assert_eq!(
        run("open_block", json!({"account": true, "armed": null}))["category"],
        Value::Null
    );
    assert_eq!(
        run("open_block", json!({"account": false, "armed": "class"})),
        Value::Null
    );
}

#[test]
fn a_drawn_fixed_time_is_at_least_one_drag_step_long() {
    let got = block_at(960, 1020, json!({}), json!("class"));
    assert_eq!(
        got,
        json!({"category": "class", "day": 3, "start": "16:00", "length": 60})
    );
    assert_eq!(
        block_at(1020, 960, Value::Null, Value::Null)["start"],
        "16:00"
    );
    assert_eq!(block_at(960, 970, json!({}), Value::Null), Value::Null);
    assert_eq!(
        block_at(960, 970, json!({"drag_step_min": 5}), Value::Null)["length"],
        10
    );
    assert_eq!(
        block_at(960, 965, json!({"drag_step_min": 5}), Value::Null)["length"],
        5
    );
}

#[test]
fn a_drag_step_that_is_not_a_whole_number_choice_is_the_default() {
    assert_eq!(
        block_at(960, 970, json!({"drag_step_min": true}), Value::Null),
        Value::Null
    );
    assert_eq!(
        block_at(960, 970, json!({"drag_step_min": 7}), Value::Null),
        Value::Null
    );
    assert_eq!(
        block_at(960, 970, json!({"drag_step_min": 5.0}), Value::Null),
        Value::Null
    );
}

#[test]
fn a_new_fixed_time_starts_at_the_next_quarter_hour_still_ahead_today() {
    let values = |column: Value, minute: i64| {
        run(
            "new_event_values",
            json!({"today_column": column, "minute": minute}),
        )
    };
    assert_eq!(values(json!(2), 17 * 60 + 1), json!([2, "17:15"]));
    assert_eq!(values(json!(2), 17 * 60), json!([2, "17:00"]));
}

#[test]
fn a_new_fixed_time_falls_back_to_sixteen_hundred_on_another_week_or_past_the_end() {
    let values = |column: Value, minute: i64| {
        run(
            "new_event_values",
            json!({"today_column": column, "minute": minute}),
        )
    };
    assert_eq!(values(Value::Null, 600), json!([0, "16:00"]));
    // After 23:45 nothing is left today, so it is the first slot tomorrow, unless that is off the week.
    assert_eq!(values(json!(3), 23 * 60 + 50), json!([4, "00:00"]));
    assert_eq!(values(json!(6), 23 * 60 + 50), json!([0, "16:00"]));
    assert_eq!(values(json!(6), 23 * 60 + 45), json!([6, "23:45"]));
}

fn blocks() -> Value {
    json!([
        {"id": "soccer", "kind": "locked", "title": "Soccer", "days": [1]},
        {"id": "essay-1", "kind": "flex", "assignment_id": "essay", "title": "Essay"},
        {"id": "ghost-1", "kind": "flex", "assignment_id": "gone", "title": "Ghost"},
        {"id": "gym", "kind": "locked", "title": "Gym", "assignment_id": ""},
        {"id": "nap", "kind": "free", "title": "Nap"},
    ])
}

fn edit(block_id: &str, day: i64) -> Value {
    run(
        "edit_block",
        json!({"blocks": blocks(), "assignment_ids": ["essay"], "block_id": block_id, "day": day}),
    )
}

#[test]
fn a_homework_block_opens_edit_homework() {
    let steps = edit("essay-1", 2);
    assert_eq!(
        steps,
        json!([{"on": "bridge", "call": "editHomework", "args": ["essay"], "kwargs": {}}])
    );
}

#[test]
fn a_fixed_time_opens_edit_fixed_time_for_the_day_clicked() {
    let steps = edit("soccer", 1);
    assert_eq!(calls(&steps), ["bridge._edit_block_draft"]);
    assert_eq!(steps[0]["args"][0]["title"], "Soccer");
    assert_eq!(steps[0]["args"][1], 1);
    assert_eq!(edit("soccer", -1)[0]["args"][1], Value::Null);
    assert_eq!(edit("gym", 0)[0]["args"][1], 0);
}

#[test]
fn other_blocks_and_unknown_ids_open_nothing() {
    assert_eq!(edit("ghost-1", 0), json!([]));
    assert_eq!(edit("nap", 0), json!([]));
    assert_eq!(edit("missing", 0), json!([]));
    let none = run(
        "edit_block",
        json!({"blocks": null, "assignment_ids": [], "block_id": "soccer", "day": 0}),
    );
    assert_eq!(none, json!([]));
}

#[test]
fn the_block_menu_asks_to_delete_only_a_plain_fixed_time() {
    let ask = |id: &str, day: i64| {
        run(
            "ask_delete_block",
            json!({"blocks": blocks(), "block_id": id, "day": day}),
        )
    };
    let steps = ask("soccer", 1);
    assert_eq!(calls(&steps), ["bridge._ask_delete_draft"]);
    assert_eq!(steps[0]["args"][1], 1);
    assert_eq!(ask("soccer", -1)[0]["args"][1], Value::Null);
    assert_eq!(ask("essay-1", 0), json!([]));
    assert_eq!(ask("nap", 0), json!([]));
    assert_eq!(ask("missing", 0), json!([]));
    let linked = json!([{"id": "x", "kind": "locked", "assignment_id": "essay"}]);
    assert_eq!(
        run(
            "ask_delete_block",
            json!({"blocks": linked, "block_id": "x", "day": 0})
        ),
        json!([])
    );
}

// Closing -------------------------------------------------------------------------------------

#[test]
fn closing_an_update_sheet_finishes_the_update_and_a_late_one_clears_its_preview() {
    let plain = run("close", json!({"kind": "block", "late_preview": true}));
    assert_eq!(plain, json!({"before": [], "clear": []}));
    let update = run("close", json!({"kind": "update", "late_preview": false}));
    assert_eq!(update["before"], json!([bridge("_finish_update")]));
    assert_eq!(update["clear"], json!([]));
    let late = run("close", json!({"kind": "late", "late_preview": true}));
    assert_eq!(
        late["clear"],
        json!([
            {"on": "session", "call": "__setattr__", "args": ["late_preview", null], "kwargs": {}},
            {"on": "session", "call": "_say", "args": [""], "kwargs": {}},
        ])
    );
    assert_eq!(
        run("close", json!({"kind": "late", "late_preview": false}))["clear"],
        json!([])
    );
}

fn close_facts() -> Value {
    json!({
        "drag_active": false, "ask": {}, "kind": "homework", "done": false, "handlers": [],
        "homework_dirty": false, "block_dirty": false, "alarm_dirty": false,
    })
}

fn close_with(changes: Value) -> Value {
    let mut facts = close_facts();
    for (key, value) in changes.as_object().unwrap() {
        facts[key] = value.clone();
    }
    run("close_sheet", facts)
}

#[test]
fn esc_with_a_range_being_drawn_cancels_the_drawing_first() {
    let steps =
        close_with(json!({"drag_active": true, "ask": {"id": "discard"}, "homework_dirty": true}));
    assert_eq!(steps, json!([bridge("_cancel_drag")]));
}

#[test]
fn esc_on_the_edited_weeks_question_answers_it_with_nothing() {
    let ask = json!({"id": "edited-weeks"});
    let with_callback = close_with(json!({"ask": ask, "done": true}));
    assert_eq!(with_callback[0]["args"], json!(["done"]));
    assert_eq!(with_callback[0]["call"], "_dismiss_ask");
    let handlers = json!(["keep", "dismiss"]);
    let without = close_with(json!({"ask": ask, "done": false, "handlers": handlers}));
    assert_eq!(without[0]["args"], json!(["dismiss"]));
}

#[test]
fn esc_on_any_other_question_runs_its_dismiss_handler_when_it_has_one() {
    let ask = json!({"id": "restore-point"});
    let handlers = json!(["restore", "dismiss"]);
    assert_eq!(
        close_with(json!({"ask": ask, "handlers": handlers}))[0]["args"],
        json!(["dismiss"])
    );
    assert_eq!(
        close_with(json!({"ask": ask, "handlers": ["restore"]}))[0]["args"],
        json!(["none"])
    );
    // A callback for the edited-weeks question is only its answer when the question is that one.
    let stray = close_with(json!({"ask": ask, "done": true}));
    assert_eq!(stray[0]["args"], json!(["none"]));
}

#[test]
fn a_sheet_with_typed_work_asks_before_it_closes() {
    let discard = json!([set("_ask", words()["discard"].clone()), bridge("_publish")]);
    assert_eq!(close_with(json!({"homework_dirty": true})), discard);
    assert_eq!(
        close_with(json!({"kind": "block", "block_dirty": true})),
        discard
    );
    assert_eq!(
        close_with(json!({"kind": "alarm", "alarm_dirty": true})),
        discard
    );
}

#[test]
fn a_sheet_with_nothing_typed_closes_and_other_sheets_never_ask() {
    assert_eq!(close_with(json!({})), json!([bridge("_close")]));
    assert_eq!(
        close_with(json!({"kind": "alarm"})),
        json!([bridge("_close")])
    );
    // Only the open sheet's own draft counts.
    assert_eq!(
        close_with(json!({"kind": "block", "homework_dirty": true})),
        json!([bridge("_close")])
    );
    assert_eq!(
        close_with(json!({"kind": "late", "homework_dirty": true, "block_dirty": true})),
        json!([bridge("_close")])
    );
}

fn escape(changes: Value) -> Value {
    let mut facts = json!({
        "has_draft": true, "existing": false, "dirty": true, "drag_active": false, "ask": {},
        "kind": "homework",
    });
    for (key, value) in changes.as_object().unwrap() {
        facts[key] = value.clone();
    }
    run("escape_sheet", facts)
}

#[test]
fn esc_on_a_new_sheet_with_typed_work_keeps_it_for_the_next_add() {
    assert_eq!(
        escape(json!({})),
        json!([bridge("_keep_homework"), bridge("_close")])
    );
    assert_eq!(
        escape(json!({"kind": "block"})),
        json!([bridge("_keep_block"), bridge("_close")])
    );
}

#[test]
fn esc_goes_through_close_sheet_when_nothing_is_to_be_kept() {
    let through = json!([bridge("closeSheet")]);
    assert_eq!(escape(json!({"existing": true})), through);
    assert_eq!(escape(json!({"dirty": false})), through);
    assert_eq!(escape(json!({"has_draft": false})), through);
    assert_eq!(escape(json!({"drag_active": true})), through);
    assert_eq!(escape(json!({"ask": {"id": "discard"}})), through);
}

#[test]
fn next_saves_when_the_last_step_is_done_and_republishes_otherwise() {
    assert_eq!(
        run("after_advance", json!({"done": true})),
        json!([bridge("save")])
    );
    assert_eq!(
        run("after_advance", json!({"done": false})),
        json!([bridge("_publish")])
    );
}

#[test]
fn save_goes_to_the_sheet_that_is_open() {
    assert_eq!(
        run("save", json!({"kind": "homework"})),
        json!([bridge("_save_homework")])
    );
    assert_eq!(
        run("save", json!({"kind": "block"})),
        json!([bridge("_save_block")])
    );
    assert_eq!(run("save", json!({"kind": "late"})), json!([]));
}

// Saving homework -----------------------------------------------------------------------------

fn homework(made: Value, known: Value, spread: bool, style: Value) -> Value {
    run(
        "save_homework",
        json!({"made": made, "known": known, "spread": spread, "preferences": {"planning_style": style}}),
    )
}

fn session_call(call: &str, args: Value, kwargs: Value) -> Value {
    json!({"on": "session", "call": call, "args": args, "kwargs": kwargs})
}

#[test]
fn new_homework_is_added_saved_and_announced_with_undo() {
    let made = json!({"id": "h1", "title": "Essay"});
    let steps = homework(made.clone(), Value::Null, false, Value::Null);
    assert_eq!(
        steps,
        json!([
            session_call("add_homework", json!([made]), json!({})),
            session_call("save", json!([]), json!({})),
            bridge("_close"),
            say("Added Essay", true),
        ])
    );
}

#[test]
fn saving_known_homework_says_saved() {
    let made = json!({"id": "h1", "title": "Essay"});
    let known = json!({"id": "h1", "title": "Old"});
    let steps = homework(made, known, false, json!("auto"));
    assert_eq!(
        steps[steps.as_array().unwrap().len() - 1],
        say("Saved Essay", true)
    );
    assert!(!calls(&steps).contains(&"session.plan_after_save".to_string()));
}

#[test]
fn finishing_homework_says_finished_only_when_it_was_not_finished_before() {
    let made = json!({"id": "h1", "title": "Essay", "completed": true});
    let fresh = homework(made.clone(), Value::Null, false, Value::Null);
    assert_eq!(fresh[3], say("Finished Essay.", true));
    let open = homework(made.clone(), json!({"id": "h1"}), false, Value::Null);
    assert_eq!(open[3], say("Finished Essay.", true));
    let done = homework(
        made,
        json!({"id": "h1", "completed": true}),
        false,
        Value::Null,
    );
    assert_eq!(done[3], say("Saved Essay", true));
}

#[test]
fn homework_with_no_title_is_called_homework() {
    let steps = homework(
        json!({"id": "h1", "title": ""}),
        Value::Null,
        false,
        Value::Null,
    );
    assert_eq!(steps[3], say("Added Homework", true));
    let steps = homework(json!({"id": "h1"}), json!({}), false, Value::Null);
    assert_eq!(steps[3], say("Saved Homework", true));
}

#[test]
fn new_homework_is_planned_when_the_student_plans_automatically() {
    let made = json!({"id": "h1", "title": "Essay"});
    let steps = homework(made.clone(), Value::Null, false, json!("auto"));
    assert_eq!(
        calls(&steps),
        [
            "session.add_homework",
            "session.plan_after_save",
            "session.save",
            "bridge._close",
            "bridge._say"
        ]
    );
    assert_eq!(steps[1]["args"], json!(["h1"]));
    let manual = homework(made.clone(), Value::Null, false, json!("manual"));
    assert!(!calls(&manual).contains(&"session.plan_after_save".to_string()));
    let finished = json!({"id": "h1", "title": "Essay", "completed": true});
    let steps = homework(finished, Value::Null, false, json!("auto"));
    assert!(!calls(&steps).contains(&"session.plan_after_save".to_string()));
    let steps = homework(made, json!({"id": "h1"}), false, json!("auto"));
    assert!(!calls(&steps).contains(&"session.plan_after_save".to_string()));
}

#[test]
fn spread_homework_takes_its_figures_before_it_is_added() {
    let made = json!({"id": "h1", "title": "Essay"});
    let steps = homework(made.clone(), Value::Null, true, json!("auto"));
    assert_eq!(
        calls(&steps),
        [
            "bridge._take_spread_plan",
            "session.add_homework",
            "bridge._spread_after_save",
            "session.save",
            "bridge._close",
            "bridge._say",
        ]
    );
    assert_eq!(steps[1]["kwargs"], json!({"spread": true}));
    assert_eq!(steps[2]["args"], json!(["h1"]));
}

// Saving a fixed time -------------------------------------------------------------------------

#[test]
fn a_saved_fixed_time_goes_to_the_question_the_repeat_or_this_weeks_copy() {
    let route = |kind: &str| run("save_block_route", json!({"kind": kind}));
    assert_eq!(route("ask"), json!("ask"));
    assert_eq!(route("plain"), json!("copy"));
    for kind in ["add", "make", "later", "stop"] {
        assert_eq!(route(kind), json!("repeat"));
    }
    assert_eq!(
        run("answer_save_route", json!({"choice": "later"})),
        json!("repeat")
    );
    assert_eq!(
        run("answer_save_route", json!({"choice": "week"})),
        json!("copy")
    );
}

fn repeats() -> Value {
    json!([{"id": "club", "title": "Club"}, {"id": "gym", "title": "Gym"}])
}

fn before(kind: &str, body: Value, family: &str) -> Value {
    run(
        "repeat_before",
        json!({"kind": kind, "repeat": body, "title": "Club", "repeats": repeats(), "family": family}),
    )
}

#[test]
fn a_new_weekly_time_is_added_to_the_repeats() {
    let body = json!({"id": "new", "title": "New"});
    for kind in ["add", "make"] {
        let got = before(kind, body.clone(), "club");
        assert_eq!(got["after"], json!([repeats()[0], repeats()[1], body]));
        assert_eq!(got["label"], "changing Club");
        assert_eq!(got["stop"], false);
    }
}

#[test]
fn a_changed_weekly_time_replaces_the_repeat_with_its_id() {
    let body = json!({"id": "gym", "title": "Gym later"});
    for kind in ["later", "ask"] {
        assert_eq!(
            before(kind, body.clone(), "gym")["after"],
            json!([repeats()[0], body])
        );
    }
    let error = plan(
        "repeat_before",
        &json!({"kind": "later", "repeat": null, "title": "T", "repeats": [], "family": "x"}),
    )
    .unwrap_err();
    assert_eq!(error.kind, ErrorKind::Type);
}

#[test]
fn stopping_a_weekly_time_drops_its_family_and_asks_for_the_one_off() {
    let got = before("stop", Value::Null, "club");
    assert_eq!(got["after"], json!([repeats()[1]]));
    assert_eq!(got["stop"], true);
    assert_eq!(before("stop", Value::Null, "other")["after"], repeats());
}

fn after(kind: &str, ok: bool, alone: Value) -> Value {
    run(
        "repeat_after",
        json!({
            "ok": ok, "kind": kind, "title": "Club", "label": "changing Club", "alone": alone,
            "original_id": "club-1",
        }),
    )
}

#[test]
fn a_refused_standing_question_changes_nothing() {
    assert_eq!(
        after("add", false, Value::Null),
        json!({"ticked": false, "then": []})
    );
    assert_eq!(
        after("later", false, Value::Null),
        json!({"ticked": false, "then": []})
    );
}

#[test]
fn a_weekly_change_saves_with_a_restore_point_and_keeps_its_words_for_the_answer() {
    let said = |kind: &str| {
        let then = after(kind, true, Value::Null)["then"].clone();
        let step = then
            .as_array()
            .unwrap()
            .iter()
            .find(|step| step["args"][0] == "_saving_repeat")
            .unwrap()
            .clone();
        step["args"][1].clone()
    };
    assert_eq!(
        said("add"),
        json!(format!(
            "Club repeats every week from this week on. {UNDO_ALSO}"
        ))
    );
    assert_eq!(
        said("make"),
        json!(format!(
            "Club repeats every week from this week on. {UNDO_ALSO}"
        ))
    );
    assert_eq!(
        said("stop"),
        json!(format!("Club stops repeating after this week. {UNDO_ALSO}"))
    );
    assert_eq!(
        said("later"),
        json!(format!("Changed Club from this week on. {UNDO_ALSO}"))
    );
    assert_eq!(
        said("ask"),
        json!(format!("Changed Club from this week on. {UNDO_ALSO}"))
    );
    let steps = after("add", true, Value::Null)["then"].clone();
    assert_eq!(
        steps,
        json!([
            set(
                "_saving_repeat",
                json!(format!(
                    "Club repeats every week from this week on. {UNDO_ALSO}"
                ))
            ),
            set("_doubled_name", json!("Club")),
            session_call(
                "save",
                json!([]),
                json!({"snapshot_label": "Before changing Club"})
            ),
        ])
    );
}

#[test]
fn a_one_off_made_a_repeat_is_deleted_in_the_same_undo_step() {
    let steps = after("make", true, Value::Null)["then"].clone();
    assert_eq!(
        steps[0],
        session_call(
            "delete_block",
            json!(["club-1"]),
            json!({"scope": "series", "label": "changing Club"})
        )
    );
    assert_eq!(steps.as_array().unwrap().len(), 4);
}

#[test]
fn a_stopped_repeat_keeps_its_checked_one_off_for_this_week() {
    let alone = json!({"id": "club-1", "title": "Club"});
    let steps = after("stop", true, alone.clone())["then"].clone();
    assert_eq!(
        steps[0],
        session_call("add_block", json!([alone]), json!({"scope": "series"}))
    );
    assert_eq!(
        after("stop", true, Value::Null)["then"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
}

#[test]
fn a_changed_repeat_ticks_back_the_days_it_restored_before_it_saves() {
    assert_eq!(after("later", true, Value::Null)["ticked"], true);
    assert_eq!(after("ask", true, Value::Null)["ticked"], true);
    for kind in ["add", "make", "stop"] {
        assert_eq!(after(kind, true, Value::Null)["ticked"], false);
    }
}

#[test]
fn the_restore_point_label_is_cut_at_eighty_characters() {
    let name = "x".repeat(90);
    let got = run(
        "repeat_after",
        json!({"ok": true, "kind": "add", "title": name, "label": "l", "alone": null, "original_id": "o"}),
    );
    let label = got["then"][2]["kwargs"]["snapshot_label"]
        .as_str()
        .unwrap()
        .to_string();
    assert_eq!(label.chars().count(), 80);
    assert!(label.ends_with('…'));
}

fn ticked(blocks: Value, original: Value, made: Value) -> Value {
    run(
        "ticked_back",
        json!({
            "blocks": blocks, "family": "club", "label": "changing Club",
            "original_removed": original, "made_removed": made,
        }),
    )
}

#[test]
fn days_ticked_back_on_are_live_in_this_weeks_copy() {
    let blocks = json!([
        {"id": "club", "removed_days": [1, 3]},
        {"id": "club@20261123", "removed_days": [3]},
        {"id": "other", "removed_days": [3]},
        {"id": "club@20261130"},
    ]);
    let steps = ticked(blocks, json!([1, 3]), json!([3]));
    assert_eq!(calls(&steps), ["session._touch"]);
    assert_eq!(steps[0]["args"], json!(["changing Club"]));
    assert_eq!(
        steps[0]["kwargs"]["blocks"],
        json!([
            {"id": "club", "removed_days": [3]},
            {"id": "club@20261123", "removed_days": [3]},
            {"id": "other", "removed_days": [3]},
            {"id": "club@20261130"},
        ])
    );
}

#[test]
fn a_block_with_all_its_removed_days_restored_loses_the_key() {
    let steps = ticked(
        json!([{"id": "club", "removed_days": [1], "title": "Club"}]),
        json!([1]),
        json!([]),
    );
    assert_eq!(
        steps[0]["kwargs"]["blocks"],
        json!([{"id": "club", "title": "Club"}])
    );
}

#[test]
fn nothing_ticked_back_touches_nothing() {
    let blocks = json!([{"id": "club", "removed_days": [3]}]);
    assert_eq!(ticked(blocks.clone(), json!([3]), json!([3])), json!([]));
    assert_eq!(ticked(blocks.clone(), Value::Null, Value::Null), json!([]));
    assert_eq!(ticked(blocks, json!([1]), json!([])), json!([]));
}

#[test]
fn block_ids_come_out_in_order() {
    assert_eq!(
        run("block_ids", json!({"blocks": blocks()})),
        json!(["soccer", "essay-1", "ghost-1", "gym", "nap"])
    );
    assert_eq!(
        plan("block_ids", &json!({"blocks": [{"title": "x"}]}))
            .unwrap_err()
            .kind,
        ErrorKind::Key
    );
}

fn copy(day: Value, recover: bool, now: Value, before: Value) -> Value {
    run(
        "week_copy_after",
        json!({
            "before_ids": before, "blocks": now,
            "made": {"id": "club", "title": "Club", "days": [3], "start": "16:00"},
            "day": day, "recover": recover, "week_start": "2026-11-23",
        }),
    )
}

#[test]
fn a_new_fixed_time_is_saved_and_announced_by_what_it_added() {
    let steps = copy(
        Value::Null,
        false,
        json!([{"id": "club", "days": [3]}]),
        json!([]),
    );
    assert_eq!(
        steps,
        json!([
            session_call("save", json!([]), json!({})),
            bridge("_close"),
            say("Added Club on Thu 16:00.", true),
        ])
    );
}

#[test]
fn an_edited_fixed_time_says_saved() {
    let steps = copy(
        Value::Null,
        false,
        json!([{"id": "club", "days": [3]}]),
        json!(["club"]),
    );
    assert_eq!(steps[2], say("Saved Club", true));
}

#[test]
fn ticking_i_missed_it_marks_the_split_days_new_block_missed() {
    // "This day only" splits the series: the day gets a block with a new id.
    let now = json!([
        {"id": "club", "days": [1, 2]},
        {"id": "club@20261123-2", "days": [3]},
    ]);
    let steps = copy(json!(3), true, now, json!(["club"]));
    assert_eq!(
        steps,
        json!([
            session_call("recover_missed", json!(["club@20261123-2", 3]), json!({})),
            bridge("_close"),
            say("Saved Club", true),
        ])
    );
}

#[test]
fn a_missed_day_is_found_on_the_edited_block_itself() {
    let now = json!([{"id": "club", "days": [3]}]);
    let steps = copy(json!(3), true, now, json!(["club"]));
    assert_eq!(
        steps[0],
        session_call("recover_missed", json!(["club", 3]), json!({}))
    );
}

#[test]
fn a_missed_day_with_no_holder_is_saved_plainly() {
    // The old blocks are not new, and the day sits on none of the new ones.
    let now = json!([{"id": "club", "days": [1]}, {"id": "other", "days": [3]}]);
    let steps = copy(json!(3), true, now, json!(["club", "other"]));
    assert_eq!(
        calls(&steps),
        ["session.save", "bridge._close", "bridge._say"]
    );
}

#[test]
fn a_block_not_marked_missed_or_with_no_day_is_saved_plainly() {
    let now = json!([{"id": "club", "days": [3]}]);
    let steps = copy(json!(3), false, now.clone(), json!(["club"]));
    assert_eq!(
        calls(&steps),
        ["session.save", "bridge._close", "bridge._say"]
    );
    let steps = copy(Value::Null, true, now, json!(["club"]));
    assert_eq!(
        calls(&steps),
        ["session.save", "bridge._close", "bridge._say"]
    );
}

// Unpin, remove and answers -------------------------------------------------------------------

#[test]
fn unpin_works_only_on_homework_that_exists_and_saves_only_when_it_changed() {
    assert_eq!(run("unpin_gate", json!({"existing": true})), json!({}));
    assert_eq!(run("unpin_gate", json!({"existing": false})), Value::Null);
    assert_eq!(
        run("unpin_done", json!({"unpinned": true})),
        json!([
            session_call("save", json!([]), json!({})),
            bridge("_close"),
            say("FlexWeek can move it again.", true)
        ])
    );
    assert_eq!(
        run("unpin_done", json!({"unpinned": false})),
        json!([bridge("_close"), say("FlexWeek can move it again.", true)])
    );
}

fn remove(changes: Value) -> Value {
    let mut facts = json!({
        "homework_existing": false, "homework_title": null, "block_existing": false, "has_session": true,
    });
    for (key, value) in changes.as_object().unwrap() {
        facts[key] = value.clone();
    }
    run("remove", facts)
}

#[test]
fn delete_on_an_edit_homework_sheet_asks_first_with_its_title() {
    let steps = remove(json!({"homework_existing": true, "homework_title": "Essay"}));
    assert_eq!(
        steps,
        json!([
            set(
                "_ask",
                json!({
                    "id": "delete-homework",
                    "title": "Delete homework",
                    "body": "Delete Essay? Its times on the calendar go too, in every week. You can undo this.",
                    "answers": [
                        {"id": "stay", "label": "Cancel", "kind": "text"},
                        {"id": "delete", "label": "Delete", "kind": "danger"},
                    ],
                })
            ),
            bridge("_publish"),
        ])
    );
    let untitled = remove(json!({"homework_existing": true, "homework_title": ""}));
    assert!(
        untitled[0]["args"][1]["body"]
            .as_str()
            .unwrap()
            .starts_with("Delete this homework? ")
    );
}

#[test]
fn delete_on_an_edit_fixed_time_sheet_asks_the_blocks_own_question() {
    let steps = remove(json!({"block_existing": true}));
    assert_eq!(
        steps,
        json!([bridge("_ask_block_delete"), bridge("_publish")])
    );
    assert_eq!(
        remove(json!({"block_existing": true, "has_session": false})),
        json!([])
    );
    assert_eq!(remove(json!({})), json!([]));
    // Homework wins when both are somehow open.
    let both = remove(json!({"homework_existing": true, "block_existing": true}));
    assert_eq!(both[0]["args"][0], "_ask");
}

fn answer(asked: &str, choice: &str, has_handlers: bool) -> Value {
    let ask = if asked.is_empty() {
        json!({})
    } else {
        json!({"id": asked})
    };
    run(
        "answer",
        json!({"ask": ask, "choice": choice, "has_handlers": has_handlers, "pending_delete": "u1"}),
    )
}

fn cleared(next: Value) -> Value {
    json!([set("_ask", json!({})), next])
}

#[test]
fn the_edited_weeks_answer_goes_to_the_window_or_is_cancelled() {
    let step = |said: Value| json!([{"on": "bridge", "call": "_answer_edited", "args": [said], "kwargs": {}}]);
    for choice in ["keep", "replace", "from_today"] {
        assert_eq!(answer("edited-weeks", choice, false), step(json!(choice)));
    }
    assert_eq!(answer("edited-weeks", "stay", false), step(Value::Null));
    assert_eq!(answer("edited-weeks", "keep", true), step(json!("keep")));
}

#[test]
fn a_prompt_with_handlers_runs_the_one_the_answer_names() {
    let handler = |choice: &str| json!({"on": "bridge", "call": "_run_handler", "args": [choice], "kwargs": {}});
    assert_eq!(
        answer("restore-point", "restore", true),
        cleared(handler("restore"))
    );
    assert_eq!(
        answer("discard", "discard", true),
        cleared(handler("discard"))
    );
}

#[test]
fn the_sign_out_prompt_signs_out_only_on_yes() {
    assert_eq!(
        answer("sign-out", "yes", false),
        cleared(bridge("_sign_out_yes"))
    );
    assert_eq!(
        answer("sign-out", "no", false),
        cleared(bridge("_sign_out_no"))
    );
}

#[test]
fn discarding_closes_and_keeping_editing_republishes() {
    assert_eq!(
        answer("discard", "discard", false),
        cleared(bridge("_close"))
    );
    assert_eq!(
        answer("discard", "keep", false),
        cleared(bridge("_publish"))
    );
}

#[test]
fn the_delete_prompts_run_their_delete_only_on_a_delete_answer() {
    let with =
        |call: &str, args: Value| json!({"on": "bridge", "call": call, "args": args, "kwargs": {}});
    assert_eq!(
        answer("delete-homework", "delete", false),
        cleared(bridge("_delete_homework"))
    );
    assert_eq!(
        answer("delete-homework", "stay", false),
        cleared(bridge("_publish"))
    );
    for choice in ["delete", "day", "week", "every"] {
        assert_eq!(
            answer("delete-block", choice, false),
            cleared(with("_delete_block", json!([choice])))
        );
    }
    assert_eq!(
        answer("delete-block", "stay", false),
        cleared(bridge("_publish"))
    );
    assert_eq!(
        answer("delete-alarm", "delete", false),
        cleared(bridge("_delete_alarm"))
    );
    assert_eq!(
        answer("delete-alarm", "stay", false),
        cleared(bridge("_publish"))
    );
    assert_eq!(
        answer("delete-unfinished", "delete", false),
        cleared(with("_delete_unfinished", json!(["u1"])))
    );
    assert_eq!(
        answer("delete-unfinished", "stay", false),
        cleared(bridge("_publish"))
    );
}

#[test]
fn the_change_question_saves_this_week_or_the_repeat() {
    let with =
        |call: &str, args: Value| json!({"on": "bridge", "call": call, "args": args, "kwargs": {}});
    for choice in ["week", "later"] {
        assert_eq!(
            answer("block-save", choice, false),
            cleared(with("_answer_save", json!([choice])))
        );
    }
    assert_eq!(
        answer("block-save", "stay", false),
        cleared(bridge("_publish"))
    );
}

#[test]
fn an_unknown_or_missing_prompt_just_republishes() {
    assert_eq!(
        answer("doubled-weeks", "ok", false),
        cleared(bridge("_publish"))
    );
    assert_eq!(answer("", "ok", false), cleared(bridge("_publish")));
}

// Deleting ------------------------------------------------------------------------------------

#[test]
fn deleted_homework_closes_and_says_so_with_undo() {
    let done = run(
        "delete_homework_done",
        json!({"ok": true, "title": "Essay", "message": "m"}),
    );
    assert_eq!(done, json!([bridge("_close"), say("Deleted Essay.", true)]));
    let untitled = run(
        "delete_homework_done",
        json!({"ok": true, "title": null, "message": "m"}),
    );
    assert_eq!(untitled[1], say("Deleted this homework.", true));
}

#[test]
fn homework_that_could_not_be_deleted_keeps_the_sheet_and_says_why() {
    let kept = run(
        "delete_homework_done",
        json!({"ok": false, "title": "Essay", "message": "Saving…"}),
    );
    assert_eq!(kept, json!([say("Saving…", false), bridge("_publish")]));
}

fn delete(choice: &str, block: Value, scope: &str, day: Value) -> Value {
    run(
        "delete_block",
        json!({
            "choice": choice, "block": block, "scope": scope, "day": day, "repeats": repeats(),
            "week_start": "2026-11-23",
        }),
    )
}

fn club() -> Value {
    json!({"id": "club-9", "title": "Club", "kind": "locked", "days": [3]})
}

#[test]
fn deleting_one_day_deletes_that_occurrence_and_names_the_day() {
    let got = delete("day", club(), "series", json!(2));
    assert_eq!(got["standing"], Value::Null);
    assert_eq!(
        got["steps"],
        json!([
            session_call(
                "delete_block",
                json!(["club-9"]),
                json!({"scope": "occurrence", "day": 2, "every_week": false})
            ),
            session_call("save", json!([]), json!({})),
            bridge("_close"),
            say("Deleted Club on Wednesday from this week.", true),
        ])
    );
}

#[test]
fn deleting_this_week_deletes_the_series_for_the_week() {
    for choice in ["week", "delete"] {
        let scope = if choice == "week" {
            "series"
        } else {
            "occurrence"
        };
        let got = delete(choice, club(), "occurrence", Value::Null);
        assert_eq!(got["steps"][0]["kwargs"]["scope"], scope);
        assert_eq!(got["steps"][3], say("Deleted Club from this week.", true));
    }
}

#[test]
fn a_plain_delete_keeps_the_scope_the_sheet_had() {
    let got = delete("delete", club(), "series", json!(1));
    assert_eq!(
        got["steps"][0]["kwargs"],
        json!({"scope": "series", "day": 1, "every_week": false})
    );
    let got = delete("delete", club(), "occurrence", json!(1));
    assert_eq!(
        got["steps"][3],
        say("Deleted Club on Tuesday from this week.", true)
    );
}

#[test]
fn deleting_every_week_of_a_plain_fixed_time_says_so_without_undo() {
    let got = delete("every", club(), "series", Value::Null);
    assert_eq!(got["standing"], Value::Null);
    assert_eq!(
        got["steps"][0]["kwargs"],
        json!({"scope": "series", "day": null, "every_week": true})
    );
    assert_eq!(
        got["steps"][3],
        say("Deleted Club from this week and every week after.", false)
    );
}

#[test]
fn a_fixed_time_with_no_title_is_called_this_fixed_time() {
    let block = json!({"id": "b", "kind": "locked", "title": ""});
    let got = delete("week", block, "series", Value::Null);
    assert_eq!(
        got["steps"][3],
        say("Deleted this fixed time from this week.", true)
    );
}

#[test]
fn deleting_every_week_of_a_weekly_time_asks_the_window_first() {
    let weekly =
        json!({"id": "weekly-club@20261123", "title": "Club", "kind": "locked", "days": [3]});
    let held = json!([{"id": "weekly-club", "title": "Club"}, {"id": "gym", "title": "Gym"}]);
    let facts = json!({
        "choice": "every", "block": weekly, "scope": "series", "day": null, "repeats": held,
        "week_start": "2026-11-23",
    });
    let got = run("delete_block", facts);
    let standing = &got["standing"];
    assert_eq!(standing["label"], "deleting Club");
    assert_eq!(standing["title"], "Club");
    assert_eq!(standing["after"], json!([{"id": "gym", "title": "Gym"}]));
    assert_eq!(got["steps"], json!([]));
}

#[test]
fn only_every_week_asks_the_window_even_for_a_weekly_time() {
    let weekly =
        json!({"id": "weekly-club@20261123", "title": "Club", "kind": "locked", "days": [3]});
    let got = delete("week", weekly, "series", Value::Null);
    assert_eq!(got["standing"], Value::Null);
    assert_eq!(got["steps"][0]["kwargs"]["every_week"], false);
}

#[test]
fn once_the_window_agrees_a_weekly_delete_saves_with_a_restore_point() {
    let words = format!("Deleted Club from this week and every week after. {UNDO_ALSO}");
    let done = run(
        "delete_block_standing_done",
        json!({"ok": true, "title": "Club"}),
    );
    assert_eq!(
        done,
        json!([
            session_call(
                "save",
                json!([]),
                json!({"snapshot_label": "Before deleting Club"})
            ),
            bridge("_close"),
            say(&words, false),
            set("_restore_words", json!(words)),
        ])
    );
    assert_eq!(
        run(
            "delete_block_standing_done",
            json!({"ok": false, "title": "Club"})
        ),
        json!([])
    );
}

#[test]
fn a_day_outside_the_week_is_refused_in_the_delete_words() {
    let facts = json!({
        "choice": "day", "block": club(), "scope": "series", "day": 9, "repeats": [], "week_start": "2026-11-23",
    });
    assert_eq!(
        plan("delete_block", &facts).unwrap_err().kind,
        ErrorKind::Index
    );
}

// Alarms --------------------------------------------------------------------------------------

fn alarm_facts(account: bool, prefs: Value, id: &str) -> Value {
    json!({"account": account, "preferences": prefs, "alarm_id": id, "max_alarms": 20, "full": "You can have up to 20 alarms."})
}

fn open_alarm(account: bool, prefs: Value, id: &str) -> Value {
    run("open_alarm", alarm_facts(account, prefs, id))
}

#[test]
fn the_alarms_are_the_preferences_alarms_or_none() {
    assert_eq!(run("alarms", json!({"preferences": null})), json!([]));
    assert_eq!(run("alarms", json!({"preferences": {}})), json!([]));
    assert_eq!(
        run("alarms", json!({"preferences": {"alarms": null}})),
        json!([])
    );
    assert_eq!(
        run("alarms", json!({"preferences": {"alarms": [{"id": "a"}]}})),
        json!([{"id": "a"}])
    );
}

#[test]
fn an_alarm_sheet_needs_an_account_and_preferences() {
    assert_eq!(open_alarm(false, json!({}), ""), json!([]));
    assert_eq!(open_alarm(true, Value::Null, ""), json!([]));
}

#[test]
fn a_new_alarm_opens_with_the_tone_and_clock_the_student_chose() {
    let steps = open_alarm(true, json!({"alarm_tone": "bell", "clock_24h": true}), "");
    assert_eq!(
        steps,
        json!([{"on": "bridge", "call": "_open_alarm_sheet", "args": [null, "bell", true], "kwargs": {}}])
    );
    let plain = open_alarm(true, json!({"clock_24h": 1}), "");
    assert_eq!(plain[0]["args"], json!([null, "chime", false]));
    let empty = open_alarm(true, json!({"alarm_tone": ""}), "");
    assert_eq!(empty[0]["args"][1], "chime");
}

#[test]
fn an_existing_alarm_opens_for_editing_and_an_unknown_one_opens_nothing() {
    let prefs = json!({"alarms": [{"id": "a", "name": "Wake"}, {"id": "b"}]});
    let steps = open_alarm(true, prefs.clone(), "b");
    assert_eq!(steps[0]["args"][0], json!({"id": "b"}));
    assert_eq!(open_alarm(true, prefs, "zzz"), json!([]));
}

#[test]
fn the_twentieth_alarm_is_the_last_one_that_can_be_added() {
    let many = |count: usize| {
        let alarms: Vec<Value> = (0..count)
            .map(|number| json!({"id": format!("a{number}")}))
            .collect();
        json!({"alarms": alarms})
    };
    assert_eq!(
        open_alarm(true, many(19), "")[0]["call"],
        "_open_alarm_sheet"
    );
    assert_eq!(
        open_alarm(true, many(20), ""),
        json!([say("You can have up to 20 alarms.", false)])
    );
    // Editing one of twenty is fine.
    assert_eq!(
        open_alarm(true, many(20), "a3")[0]["call"],
        "_open_alarm_sheet"
    );
}

#[test]
fn the_alarm_sheet_saves_only_while_it_is_the_open_sheet() {
    assert_eq!(
        run("save_alarm_gate", json!({"kind": "alarm"})),
        json!({"said": SAVED_ALARM})
    );
    assert_eq!(run("save_alarm_gate", json!({"kind": "late"})), Value::Null);
    assert_eq!(SAVED_ALARM, "Saved the alarm.");
}

#[test]
fn a_twenty_first_alarm_is_refused_on_the_sheet() {
    let facts = |existing: bool, count: usize| {
        let alarms: Vec<Value> = (0..count).map(|number| json!({"id": number})).collect();
        json!({"existing": existing, "alarms": alarms, "max_alarms": 20, "full": "Full."})
    };
    let steps = run("alarm_full", facts(false, 20));
    assert_eq!(
        steps,
        json!([
            {"on": "alarm", "call": "__setattr__", "args": ["error", "Full."], "kwargs": {}},
            bridge("_publish"),
        ])
    );
    assert_eq!(run("alarm_full", facts(false, 19)), Value::Null);
    assert_eq!(run("alarm_full", facts(true, 20)), Value::Null);
}

#[test]
fn a_saved_alarm_closes_and_a_failed_one_shows_why_on_the_sheet() {
    let written = |ok: bool, has_alarm: bool| {
        run(
            "alarm_written",
            json!({"ok": ok, "said": SAVED_ALARM, "has_alarm": has_alarm, "not_saved": "Couldn't save."}),
        )
    };
    assert_eq!(
        written(true, true),
        json!([bridge("_close"), say(SAVED_ALARM, false)])
    );
    let error = json!({"on": "alarm", "call": "__setattr__", "args": ["error", "Couldn't save."], "kwargs": {}});
    assert_eq!(written(false, true), json!([error, bridge("_publish")]));
    assert_eq!(written(false, false), json!([]));
}

#[test]
fn a_refused_alarm_write_shows_the_error_and_republishes() {
    let refused = |accepted: bool, has_alarm: bool| {
        run(
            "alarm_refused",
            json!({"accepted": accepted, "has_alarm": has_alarm, "not_saved": "Couldn't save."}),
        )
    };
    let error = json!({"on": "alarm", "call": "__setattr__", "args": ["error", "Couldn't save."], "kwargs": {}});
    assert_eq!(refused(false, true), json!([error, bridge("_publish")]));
    assert_eq!(refused(false, false), json!([bridge("_publish")]));
    assert_eq!(refused(true, true), json!([]));
}

#[test]
fn deleting_an_alarm_asks_first_by_name() {
    let ask = |existing: bool, name: &str| {
        run("remove_alarm", json!({"existing": existing, "name": name}))
    };
    let steps = ask(true, "  Wake  ");
    assert_eq!(
        steps[0],
        set(
            "_ask",
            json!({
                "id": "delete-alarm",
                "title": "Delete alarm",
                "body": "Delete Wake? It will not ring again.",
                "answers": [
                    {"id": "stay", "label": "Cancel", "kind": "text"},
                    {"id": "delete", "label": "Delete", "kind": "danger"},
                ],
            })
        )
    );
    assert_eq!(steps[1], bridge("_publish"));
    assert_eq!(
        ask(true, "   ")[0]["args"][1]["body"],
        "Delete this alarm? It will not ring again."
    );
    assert_eq!(ask(false, "Wake"), json!([]));
}

#[test]
fn a_deleted_alarm_leaves_the_others_in_order() {
    let got = run(
        "alarms_without",
        json!({"alarms": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "id": "b"}),
    );
    assert_eq!(
        got,
        json!({"alarms": [{"id": "a"}, {"id": "c"}], "said": DELETED_ALARM})
    );
    assert_eq!(DELETED_ALARM, "Deleted the alarm.");
}

// The store answering -------------------------------------------------------------------------

fn saved(changes: Value) -> Value {
    let mut facts = json!({
        "words": "", "stored": true, "said": "", "has_block": true, "kind": "", "waiting": null, "blocks": [],
    });
    for (key, value) in changes.as_object().unwrap() {
        facts[key] = value.clone();
    }
    run("saved", facts)
}

#[test]
fn a_stored_weekly_change_closes_the_sheet_and_waits_for_its_restore_point() {
    let steps = saved(json!({"words": "Club repeats.", "kind": "block"}));
    assert_eq!(
        steps,
        json!([
            bridge("_close"),
            say("Club repeats.", false),
            set("_restore_words", json!("Club repeats.")),
        ])
    );
}

#[test]
fn a_refused_weekly_change_keeps_the_sheet_with_the_stores_sentence() {
    let steps = saved(
        json!({"words": "Club repeats.", "stored": false, "said": "Too many.", "kind": "block"}),
    );
    assert_eq!(
        steps,
        json!([
            session_call("drop_refused_save", json!([]), json!({})),
            {"on": "block", "call": "__setattr__", "args": ["error", "Too many."], "kwargs": {}},
            bridge("_publish"),
            bridge("_publish"),
        ])
    );
    let no_sheet = saved(json!({"words": "Club repeats.", "stored": false, "has_block": false}));
    assert_eq!(no_sheet, json!([]));
}

#[test]
fn an_answered_save_with_no_weekly_words_only_republishes_an_open_add_sheet() {
    assert_eq!(
        saved(json!({"kind": "homework"})),
        json!([bridge("_publish")])
    );
    assert_eq!(saved(json!({"kind": "block"})), json!([bridge("_publish")]));
    assert_eq!(saved(json!({"kind": "late"})), json!([]));
    assert_eq!(saved(json!({"kind": ""})), json!([]));
}

#[test]
fn a_late_move_waits_for_the_save_then_says_it_with_undo_once_the_block_is_there() {
    let waiting = json!(["b1", "Moved it."]);
    let found = saved(json!({"waiting": waiting, "blocks": [{"id": "b1"}]}));
    assert_eq!(
        found,
        json!([
            set("_late_waiting", Value::Null),
            {"on": "bridge", "call": "_say", "args": ["Moved it."], "kwargs": {"undo": true}},
        ])
    );
    assert_eq!(
        saved(json!({"waiting": waiting, "blocks": [{"id": "other"}]})),
        json!([])
    );
    let refused = saved(json!({"waiting": waiting, "stored": false, "blocks": null}));
    assert_eq!(refused, json!([set("_late_waiting", Value::Null)]));
    let short = json!({
        "words": "", "stored": true, "said": "", "has_block": true, "kind": "", "waiting": ["b1"], "blocks": [],
    });
    assert_eq!(plan("saved", &short).unwrap_err().kind, ErrorKind::Value);
    let wrong = json!({
        "words": "", "stored": true, "said": "", "has_block": true, "kind": "", "waiting": "bad", "blocks": [],
    });
    assert_eq!(plan("saved", &wrong).unwrap_err().kind, ErrorKind::Type);
}

#[test]
fn a_busy_session_republishes_an_open_add_sheet_only() {
    assert_eq!(
        run("busy", json!({"kind": "homework"})),
        json!([bridge("_publish")])
    );
    assert_eq!(
        run("busy", json!({"kind": "block"})),
        json!([bridge("_publish")])
    );
    assert_eq!(run("busy", json!({"kind": "alarm"})), json!([]));
}

#[test]
fn a_session_change_republishes_only_the_sheets_that_read_the_session() {
    for kind in [
        "late",
        "unfinished",
        "weekList",
        "routines",
        "account",
        "restore",
        "preview",
    ] {
        assert_eq!(
            run("refresh", json!({"kind": kind})),
            json!([bridge("_publish")]),
            "{kind}"
        );
    }
    for kind in ["", "homework", "block", "alarm", "help", "about", "update"] {
        assert_eq!(run("refresh", json!({"kind": kind})), json!([]), "{kind}");
    }
}

// The paste preview ---------------------------------------------------------------------------

#[test]
fn preview_edits_go_to_the_preview_only_while_it_is_the_open_sheet() {
    let edit = |kind: &str, has: bool, call: &str| {
        run(
            "preview_edit",
            json!({"kind": kind, "has_preview": has, "call": call, "args": [1, true]}),
        )
    };
    assert_eq!(
        edit("preview", true, "check"),
        json!([
            {"on": "preview", "call": "check", "args": [1, true], "kwargs": {}},
            bridge("_publish"),
        ])
    );
    for call in ["set_day", "set_start", "set_duration"] {
        assert_eq!(edit("preview", true, call)[0]["call"], call);
    }
    assert_eq!(edit("block", true, "check"), json!([]));
    assert_eq!(edit("preview", false, "check"), json!([]));
    let error = plan(
        "preview_edit",
        &json!({"kind": "preview", "has_preview": true, "call": "save", "args": []}),
    );
    assert_eq!(error.unwrap_err().kind, ErrorKind::Value);
}

#[test]
fn the_preview_saves_only_when_open_and_ready() {
    let gate = |kind: &str, can: bool| run("preview_gate", json!({"kind": kind, "can_save": can}));
    assert_eq!(gate("preview", true), json!({}));
    assert_eq!(gate("preview", false), Value::Null);
    assert_eq!(gate("block", true), Value::Null);
}

// The notice bar ------------------------------------------------------------------------------

fn timer(call: &str, args: Value) -> Value {
    json!({"on": "timer", "call": call, "args": args, "kwargs": {}})
}

#[test]
fn a_new_notice_starts_the_ten_second_timer_unless_the_pointer_holds_it() {
    assert_eq!(NOTICE_MS, 10000);
    assert_eq!(
        run("say", json!({"text": "Added", "held": false})),
        json!([set("_paused", json!(false)), timer("start", json!([10000]))])
    );
    assert_eq!(
        run("say", json!({"text": "Added", "held": true})),
        json!([set("_paused", json!(true)), timer("stop", json!([]))])
    );
}

#[test]
fn an_empty_notice_stops_the_timer_and_clears_the_pause() {
    let cleared = json!([timer("stop", json!([])), set("_paused", json!(false))]);
    assert_eq!(run("say", json!({"text": "", "held": true})), cleared);
    assert_eq!(run("say", json!({"text": null, "held": false})), cleared);
}

#[test]
fn pausing_a_running_notice_remembers_what_was_left_never_below_zero() {
    let pause =
        |active: bool, left: i64| run("pause", json!({"active": active, "remaining": left}));
    assert_eq!(
        pause(true, 6400),
        json!([set("_remaining_ms", json!(6400)), timer("stop", json!([]))])
    );
    assert_eq!(
        pause(true, -1),
        json!([set("_remaining_ms", json!(0)), timer("stop", json!([]))])
    );
    assert_eq!(pause(false, 6400), json!([]));
}

#[test]
fn resuming_restarts_the_timer_with_at_least_a_second() {
    let resume = |paused: bool, notice: &str, left: i64| {
        run(
            "resume",
            json!({"paused": paused, "notice": notice, "remaining": left}),
        )
    };
    assert_eq!(
        resume(true, "Added", 6400),
        json!([set("_paused", json!(false)), timer("start", json!([6400]))])
    );
    assert_eq!(
        resume(true, "Added", 200),
        json!([set("_paused", json!(false)), timer("start", json!([1000]))])
    );
    assert_eq!(
        resume(true, "", 6400),
        json!([set("_paused", json!(false))])
    );
    assert_eq!(resume(false, "Added", 6400), json!([]));
}

#[test]
fn dismissing_a_notice_clears_it_and_its_undo() {
    assert_eq!(
        run("dismiss", json!({"notice": "Added"})),
        json!([
            set("_notice", json!("")),
            set("_notice_undo", json!(false)),
            set("_notice_restore", json!("")),
            set("_restore_words", json!("")),
            timer("stop", json!([])),
            set("_paused", json!(false)),
            set("_held", json!(false)),
            {"on": "changed", "call": "emit", "args": [], "kwargs": {}},
        ])
    );
    assert_eq!(run("dismiss", json!({"notice": ""})), json!([]));
}

#[test]
fn undo_goes_to_the_restore_point_when_there_is_one_and_always_dismisses() {
    let undo = |can: bool, session: bool, restore: &str| {
        run(
            "undo",
            json!({"undo": can, "has_session": session, "restore": restore}),
        )
    };
    let dismiss = bridge("dismissNotice");
    assert_eq!(
        undo(true, true, "p1"),
        json!([
            session_call("undo_to_restore_point", json!(["p1"]), json!({})),
            dismiss
        ])
    );
    assert_eq!(
        undo(true, true, ""),
        json!([session_call("undo", json!([]), json!({})), dismiss])
    );
    assert_eq!(undo(false, true, "p1"), json!([dismiss]));
    assert_eq!(undo(true, false, "p1"), json!([dismiss]));
}

fn answered(changes: Value) -> Value {
    let mut facts = json!({"point_id": "", "restore_words": "", "notice": "", "doubled": []});
    for (key, value) in changes.as_object().unwrap() {
        facts[key] = value.clone();
    }
    run("save_answered", facts)
}

#[test]
fn a_restore_point_gives_the_waiting_notice_its_undo() {
    let steps = answered(
        json!({"point_id": "p1", "restore_words": "Club repeats.", "notice": "Club repeats."}),
    );
    assert_eq!(
        steps,
        json!([
            set("_notice_restore", json!("p1")),
            set("_notice_undo", json!(true)),
            set("_restore_words", json!("")),
            {"on": "changed", "call": "emit", "args": [], "kwargs": {}},
        ])
    );
}

#[test]
fn a_restore_point_gives_nothing_to_a_notice_that_is_not_the_waiting_one() {
    assert_eq!(
        answered(json!({"point_id": "p1", "restore_words": "Club repeats.", "notice": "Other"})),
        json!([])
    );
    assert_eq!(
        answered(json!({"point_id": "", "restore_words": "A", "notice": "A"})),
        json!([])
    );
    assert_eq!(
        answered(json!({"point_id": "p1", "restore_words": "", "notice": ""})),
        json!([])
    );
}

#[test]
fn doubled_weeks_wait_as_text_until_the_prompt_can_show() {
    let steps = answered(json!({"doubled": ["2026-11-09", 5]}));
    assert_eq!(
        steps,
        json!([
            set("_doubled_waiting", json!(["2026-11-09", "5"])),
            bridge("_show_doubled")
        ])
    );
}

fn doubled(weeks: Value, ask: Value, name: &str) -> Value {
    run(
        "doubled",
        json!({"weeks": weeks, "ask": ask, "name": name, "today": "2026-11-05"}),
    )
}

#[test]
fn the_doubled_weeks_prompt_names_the_fixed_time_and_has_one_ok() {
    let steps = doubled(json!(["2026-11-09"]), json!({}), "Guitar");
    let ask = &steps[1]["args"][1];
    assert_eq!(steps[0], set("_doubled_waiting", Value::Null));
    assert_eq!(ask["id"], "doubled-weeks");
    assert_eq!(ask["title"], "Guitar is already in a later week");
    assert_eq!(
        ask["body"],
        doubled_words("Guitar", &weeks(&["2026-11-09"]), "2026-11-05").unwrap()
    );
    assert_eq!(
        ask["answers"],
        json!([{"id": "ok", "label": "OK", "kind": "tonal"}])
    );
    assert_eq!(
        steps[2],
        json!({"on": "changed", "call": "emit", "args": [], "kwargs": {}})
    );
    let many = doubled(json!(["2026-11-09", "2026-11-16"]), json!({}), "Guitar");
    assert_eq!(
        many[1]["args"][1]["title"],
        "Guitar is already in later weeks"
    );
    let nameless = doubled(json!(["2026-11-09"]), json!({}), "");
    assert_eq!(
        nameless[1]["args"][1]["title"],
        "This fixed time is already in a later week"
    );
}

#[test]
fn the_doubled_weeks_prompt_never_replaces_another_question_and_waits_for_weeks() {
    assert_eq!(
        doubled(json!(["2026-11-09"]), json!({"id": "discard"}), "Guitar"),
        json!([])
    );
    assert_eq!(doubled(Value::Null, json!({}), "Guitar"), json!([]));
}

// What the sheet shows ------------------------------------------------------------------------

#[test]
fn each_kind_of_sheet_has_a_form_and_one_missing_its_draft_has_none() {
    let source = |kind: &str, open: Value| {
        let mut facts = json!({
            "kind": kind, "homework": false, "block": false, "preview": false, "alarm": false, "update": false,
        });
        for (key, value) in open.as_object().unwrap() {
            facts[key] = value.clone();
        }
        run("form_source", facts)
    };
    assert_eq!(
        source("homework", json!({"homework": true})),
        json!("_form_homework")
    );
    assert_eq!(
        source("block", json!({"block": true})),
        json!("_form_block")
    );
    assert_eq!(
        source("preview", json!({"preview": true})),
        json!("_form_preview")
    );
    assert_eq!(
        source("alarm", json!({"alarm": true})),
        json!("_form_alarm")
    );
    assert_eq!(
        source("update", json!({"update": true})),
        json!("_form_update")
    );
    for (kind, name) in [
        ("late", "_form_late"),
        ("unfinished", "_form_unfinished"),
        ("weekList", "_form_week_list"),
        ("routines", "_form_routines"),
        ("help", "_form_help"),
        ("about", "_form_about"),
        ("account", "_form_account"),
        ("restore", "_form_restore"),
    ] {
        assert_eq!(source(kind, json!({})), json!(name), "{kind}");
    }
    for kind in [
        "homework", "block", "preview", "alarm", "update", "", "nothing",
    ] {
        assert_eq!(source(kind, json!({})), json!("_form_none"), "{kind}");
    }
}

fn note(moved: Value, when_moved: Value, noted: Value) -> Value {
    run(
        "note_edge",
        json!({"moved": moved, "when_moved": when_moved, "noted": noted}),
    )
}

#[test]
fn a_moved_day_note_is_announced_when_it_appears_or_changes_in_an_open_sheet() {
    let announce =
        |text: &str| json!({"on": "bridge", "call": "_announce", "args": [text], "kwargs": {}});
    assert_eq!(
        note(json!("Moved to Tue."), Value::Null, json!("")),
        json!([
            announce("Moved to Tue."),
            set("_noted", json!("Moved to Tue."))
        ])
    );
    assert_eq!(
        note(Value::Null, json!("Moved to Wed."), json!("Moved to Tue.")),
        json!([
            announce("Moved to Wed."),
            set("_noted", json!("Moved to Wed."))
        ])
    );
}

#[test]
fn a_sheet_that_opens_with_the_note_or_keeps_it_or_clears_it_says_nothing() {
    assert_eq!(
        note(json!("Same."), Value::Null, Value::Null),
        json!([set("_noted", json!("Same."))])
    );
    assert_eq!(
        note(json!("Same."), Value::Null, json!("Same.")),
        json!([set("_noted", json!("Same."))])
    );
    assert_eq!(
        note(Value::Null, Value::Null, json!("Old.")),
        json!([set("_noted", json!(""))])
    );
    assert_eq!(
        note(json!(""), json!("Wed."), json!("Wed.")),
        json!([set("_noted", json!("Wed."))])
    );
}

#[test]
fn the_moved_note_prefers_the_block_note_over_the_homework_one() {
    let steps = note(json!("A"), json!("B"), json!(""));
    assert_eq!(steps[1], set("_noted", json!("A")));
}

#[test]
fn dragging_a_range_changes_state_only_when_it_changes() {
    let drag = |current: bool, active: bool| {
        run("drag_range", json!({"current": current, "active": active}))
    };
    assert_eq!(
        drag(false, true),
        json!([set("_drag_range_active", json!(true)), {"on": "changed", "call": "emit", "args": [], "kwargs": {}}])
    );
    assert_eq!(drag(true, true), json!([]));
    assert_eq!(drag(false, false), json!([]));
}

#[test]
fn the_more_menu_lists_entries_only_while_it_is_open() {
    assert_eq!(
        run("more_source", json!({"more": true})),
        json!("_more_entries")
    );
    assert_eq!(
        run("more_source", json!({"more": false})),
        json!("_no_entries")
    );
}

#[test]
fn optional_sheet_facts_refuse_values_of_the_wrong_shape() {
    let cases = [
        ("open_block", json!({"account": true, "armed": 42})),
        (
            "open_block_at",
            json!({"account": true, "start_min": 600, "end_min": 660, "preferences": 42, "day": 0, "armed": null}),
        ),
        (
            "answer",
            json!({"ask": "bad", "choice": "keep", "has_handlers": false}),
        ),
        ("alarms", json!({"preferences": 42})),
        (
            "ticked_back",
            json!({"made_removed": 42, "original_removed": [], "family": "club"}),
        ),
        (
            "ticked_back",
            json!({"made_removed": [], "original_removed": 42, "family": "club"}),
        ),
    ];
    for (op, facts) in cases {
        assert_eq!(plan(op, &facts).unwrap_err().kind, ErrorKind::Type, "{op}");
    }
}
