//! The Add and Edit homework sheet (P5-S2), pinned to the desktop sheet tests: what a student sees
//! and what saving keeps. Expected values come from the requirement, never from running the code.
//!
//! The clock reads Thursday 2026-11-26 19:00 and the open week starts on Monday 2026-11-23, as the
//! desktop fixtures build it, unless a test says otherwise.

use std::cell::Cell;

use flexweek_app::views::sheet_homework::{
    Env, HomeworkDraft, OpenOptions, TITLE_PROBLEM, quarter_hours,
};
use flexweek_app::views::sheet_rules::{DUE_PASSED, ESTIMATE_LONG, ESTIMATE_SHORT, SLOT_HINT};
use flexweek_engine::EngineResult;
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

const THURSDAY: &str = "2026-11-26T19:00";
const WEEK: &str = "2026-11-23";
const PAST: &str = "That time has passed. Choose 7:00 PM or later today, or another day.";

struct World {
    week: Option<String>,
    blocks: Vec<Value>,
    prefs: Value,
    selected: String,
}

fn world() -> World {
    World {
        week: Some(WEEK.to_string()),
        blocks: Vec::new(),
        prefs: json!({"drag_step_min": 15}),
        selected: String::new(),
    }
}

impl World {
    fn env(&self) -> Env<'_> {
        Env {
            week_start: self.week.as_deref(),
            blocks: &self.blocks,
            preferences: &self.prefs,
            selected_day: &self.selected,
            done_minutes_for: None,
        }
    }
}

fn new_sheet(world: &World) -> HomeworkDraft {
    set_clock_24h(false);
    HomeworkDraft::open(
        &world.env(),
        THURSDAY,
        "new-1",
        None,
        &OpenOptions::default(),
    )
    .unwrap()
}

fn essay(due: &str, estimate: i64) -> Value {
    json!({
        "id": "essay",
        "title": "History essay",
        "due": due,
        "estimate_min": estimate,
        "category": "assignments",
        "revision": 0,
    })
}

fn session(id: &str, day: i64, start: &str, pinned: bool) -> Value {
    json!({
        "id": id,
        "assignment_id": "essay",
        "kind": "flexible",
        "category": "assignments",
        "start": start,
        "days": [day],
        "duration_min": 60,
        "pinned": pinned,
    })
}

fn edit(world: &World, assignment: &Value) -> HomeworkDraft {
    set_clock_24h(false);
    HomeworkDraft::open(
        &world.env(),
        THURSDAY,
        "unused",
        Some(assignment),
        &OpenOptions::default(),
    )
    .unwrap()
}

fn shown(draft: &HomeworkDraft, world: &World) -> Value {
    draft.form(&world.env()).unwrap()
}

fn put(draft: &mut HomeworkDraft, world: &World, name: &str, value: Value) {
    draft.set(&world.env(), name, &value).unwrap();
}

fn text(form: &Value, key: &str) -> String {
    form[key].as_str().unwrap().to_string()
}

fn offered(form: &Value) -> Vec<String> {
    form["pinnedTimeOptions"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["value"].as_str().unwrap().to_string())
        .collect()
}

fn typed(draft: &mut HomeworkDraft, world: &World, title: &str) {
    put(draft, world, "title", json!(title));
}

// What a new sheet opens with ------------------------------------------------------------------

#[test]
fn a_new_sheet_opens_on_what_with_tomorrow_as_the_due_and_an_hour_of_work() {
    let world = world();
    let draft = new_sheet(&world);
    let form = shown(&draft, &world);
    assert_eq!(form["kind"], "homework");
    assert_eq!(form["mode"], "add");
    assert_eq!(form["heading"], "Add homework");
    assert_eq!(form["step"], 0);
    assert_eq!(form["prompt"], "What is it?");
    assert_eq!(form["title"], "");
    assert_eq!(form["dueDate"], "2026-11-27");
    assert_eq!(form["dueTime"], "");
    assert_eq!(form["estimate"], "60");
    assert_eq!(form["estimateLabel"], "1 h");
    assert_eq!(form["when"], "plan");
    assert_eq!(form["primary"], "Next");
    assert_eq!(form["last"], false);
    assert_eq!(form["canBack"], false);
    assert_eq!(form["showDetails"], false);
    assert_eq!(form["canDelete"], false);
    let labels: Vec<String> = form["crumbs"]
        .as_array()
        .unwrap()
        .iter()
        .map(|crumb| text(crumb, "label"))
        .collect();
    assert_eq!(labels, ["1. What", "2. When", "3. How long"]);
    assert_eq!(form["crumbs"][0]["on"], true);
    assert_eq!(form["crumbs"][1]["on"], false);
    assert_eq!(form["crumbs"][0]["done"], false);
}

#[test]
fn the_new_homework_takes_the_id_the_caller_drew() {
    let world = world();
    let draft = new_sheet(&world);
    assert_eq!(draft.field("original").unwrap()["id"], "new-1");
    assert_eq!(draft.field("original").unwrap()["category"], "assignments");
}

#[test]
fn a_study_sheet_keeps_its_category_and_anything_else_is_homework() {
    let world = world();
    let study = OpenOptions {
        category: Some("study".into()),
        ..OpenOptions::default()
    };
    let draft = HomeworkDraft::open(&world.env(), THURSDAY, "a", None, &study).unwrap();
    assert_eq!(draft.field("original").unwrap()["category"], "study");
    let other = OpenOptions {
        category: Some("exercise".into()),
        ..OpenOptions::default()
    };
    let draft = HomeworkDraft::open(&world.env(), THURSDAY, "a", None, &other).unwrap();
    assert_eq!(draft.field("original").unwrap()["category"], "assignments");
}

#[test]
fn a_new_sheet_pins_to_today_at_the_next_quarter_hour_when_the_week_has_today() {
    let world = world();
    let draft = new_sheet(&world);
    // Thursday is the fourth day of the week; 19:00 rounds up to 19:15.
    assert_eq!(draft.field("when_day").unwrap(), 3);
    assert_eq!(draft.field("when_time").unwrap(), "19:15");
}

#[test]
fn a_new_sheet_pins_to_the_first_day_at_four_when_the_week_has_no_today() {
    let mut world = world();
    world.week = Some("2026-11-30".to_string());
    let draft = new_sheet(&world);
    assert_eq!(draft.field("when_day").unwrap(), 0);
    assert_eq!(draft.field("when_time").unwrap(), "16:00");
}

#[test]
fn with_no_week_open_today_is_found_from_its_weekday() {
    let mut world = world();
    world.week = None;
    let draft = new_sheet(&world);
    assert_eq!(draft.field("when_day").unwrap(), 3);
    let form = shown(&draft, &world);
    assert_eq!(form["dayOptions"][0]["label"], "Mon");
    assert_eq!(form["dayOptions"][6]["label"], "Sun");
}

#[test]
fn a_time_drawn_on_the_grid_opens_pinned_with_its_length_and_the_weeks_end_as_the_due() {
    let world = world();
    let drawn = OpenOptions {
        day: Some(2),
        start_min: Some(600),
        end_min: Some(690),
        ..OpenOptions::default()
    };
    let draft = HomeworkDraft::open(&world.env(), THURSDAY, "g", None, &drawn).unwrap();
    let form = shown(&draft, &world);
    assert_eq!(form["when"], "fixed");
    assert_eq!(form["whenDay"], 2);
    assert_eq!(form["whenTime"], "10:00");
    assert_eq!(form["estimate"], "90");
    assert_eq!(form["dueDate"], "2026-11-29");
    assert_eq!(
        form["whenNote"],
        "Pinned to Wed at 10:00 AM. Plan won't move it."
    );
    assert_eq!(form["dayOptions"][2]["label"], "Wed 25");
}

#[test]
fn a_new_sheet_asked_for_a_due_and_a_length_keeps_both() {
    let world = world();
    let asked = OpenOptions {
        due: Some("2026-11-28T08:30".into()),
        estimate_min: Some(45),
        ..OpenOptions::default()
    };
    let draft = HomeworkDraft::open(&world.env(), THURSDAY, "g", None, &asked).unwrap();
    let form = shown(&draft, &world);
    assert_eq!(form["dueDate"], "2026-11-28");
    assert_eq!(form["dueTime"], "08:30");
    assert_eq!(form["estimate"], "45");
}

// The due time ----------------------------------------------------------------------------------

#[test]
fn a_stored_due_time_shows_when_the_homework_is_opened_and_saving_keeps_it() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-27T17:30", 60));
    let form = shown(&draft, &world);
    assert_eq!(form["dueDate"], "2026-11-27");
    assert_eq!(form["dueTime"], "17:30");
    typed(&mut draft, &world, "History essay, final");
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["due"], "2026-11-27T17:30");
}

#[test]
fn no_time_means_the_end_of_the_day() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-27T17:30", 60));
    put(&mut draft, &world, "dueTime", json!(""));
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["due"], "2026-11-27T23:59");
}

#[test]
fn an_old_end_of_day_deadline_stays_as_stored_until_the_deadline_is_changed() {
    for stored in ["2026-11-27", "2026-11-27T23:59"] {
        let world = world();
        let mut draft = edit(&world, &essay(stored, 60));
        assert_eq!(
            shown(&draft, &world)["dueTime"],
            "",
            "an old end of day shows as End of day"
        );
        typed(&mut draft, &world, "History essay, final");
        let made = draft.candidate(&world.env()).unwrap().unwrap();
        assert_eq!(made["due"], stored);
        put(&mut draft, &world, "dueDate", json!("2026-11-28"));
        let changed = draft.candidate(&world.env()).unwrap().unwrap();
        assert_eq!(changed["due"], "2026-11-28T23:59");
    }
}

#[test]
fn homework_due_today_with_no_time_is_accepted() {
    // Thursday 19:00 is now, and the end of Thursday has not come.
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Quick quiz");
    assert!(!draft.advance(&world.env()).unwrap());
    put(&mut draft, &world, "dueDate", json!("2026-11-26"));
    assert!(!draft.advance(&world.env()).unwrap());
    let form = shown(&draft, &world);
    assert_eq!(form["dueProblem"], "");
    assert_eq!(form["step"], 2);
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["due"], "2026-11-26T23:59");
}

#[test]
fn old_overdue_homework_can_be_saved_while_its_deadline_is_untouched() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-23T10:00", 60));
    assert_eq!(shown(&draft, &world)["dueProblem"], "");
    typed(&mut draft, &world, "History essay, late");
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["title"], "History essay, late");
    assert_eq!(made["due"], "2026-11-23T10:00");
}

#[test]
fn a_changed_deadline_that_has_passed_is_refused() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-23T10:00", 60));
    put(&mut draft, &world, "dueDate", json!("2026-11-24"));
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    assert_eq!(shown(&draft, &world)["dueProblem"], DUE_PASSED);
}

#[test]
fn a_deadline_that_passed_earlier_today_is_refused_by_the_clock() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-30T10:00", 60));
    put(&mut draft, &world, "dueDate", json!("2026-11-26"));
    put(&mut draft, &world, "dueTime", json!("18:59"));
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    put(&mut draft, &world, "dueTime", json!("19:00"));
    assert!(draft.candidate(&world.env()).unwrap().is_some());
}

#[test]
fn finished_homework_is_never_told_its_deadline_has_passed() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-30T10:00", 60));
    put(&mut draft, &world, "dueDate", json!("2026-11-20"));
    put(&mut draft, &world, "completed", json!(true));
    assert!(draft.candidate(&world.env()).unwrap().is_some());
}

#[test]
fn a_new_sheet_refuses_a_passed_due_on_the_when_step() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Quiz");
    draft.advance(&world.env()).unwrap();
    put(&mut draft, &world, "dueDate", json!("2026-11-25"));
    assert!(!draft.advance(&world.env()).unwrap());
    let form = shown(&draft, &world);
    assert_eq!(form["dueProblem"], DUE_PASSED);
    assert_eq!(form["step"], 1);
    // Choosing another day takes the words away.
    put(&mut draft, &world, "dueDate", json!("2026-11-28"));
    assert_eq!(shown(&draft, &world)["dueProblem"], "");
}

// Spread over days ------------------------------------------------------------------------------

fn at_length(world: &World, minutes: &str) -> HomeworkDraft {
    let mut draft = new_sheet(world);
    typed(&mut draft, world, "Project");
    put(&mut draft, world, "dueDate", json!("2026-11-29"));
    put(&mut draft, world, "estimate", json!(minutes));
    draft
}

#[test]
fn spreading_is_offered_only_from_sixty_minutes() {
    let world = world();
    for (minutes, offered) in [("45", false), ("60", true), ("120", true)] {
        let draft = at_length(&world, minutes);
        assert_eq!(
            shown(&draft, &world)["spreadShown"],
            offered,
            "{minutes} min"
        );
    }
}

#[test]
fn spreading_is_not_offered_with_a_pinned_time() {
    let world = world();
    let mut draft = at_length(&world, "120");
    assert_eq!(shown(&draft, &world)["spreadShown"], true);
    put(&mut draft, &world, "when", json!("fixed"));
    assert_eq!(shown(&draft, &world)["spreadShown"], false);
    put(&mut draft, &world, "when", json!("plan"));
    assert_eq!(shown(&draft, &world)["spreadShown"], true);
}

#[test]
fn spreading_is_not_offered_when_the_homework_already_has_sessions() {
    // A homework already spread over two sessions is not offered the choice again, whatever its length.
    let mut world = world();
    world.blocks = vec![
        session("essay-1", 3, "18:45", false),
        session("essay-2", 4, "17:00", false),
    ];
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "estimate", json!("120"));
    let form = shown(&draft, &world);
    assert_eq!(form["spreadShown"], false);
    assert_eq!(form["whenShown"], false);
}

#[test]
fn one_session_does_not_hide_the_spread_choice() {
    let mut world = world();
    world.blocks = vec![session("essay-1", 3, "18:45", false)];
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "estimate", json!("120"));
    assert_eq!(shown(&draft, &world)["spreadShown"], true);
}

#[test]
fn a_spread_makes_hour_long_sessions_that_add_up_to_the_estimate() {
    let world = world();
    let draft = at_length(&world, "120");
    let (session_min, from_date, sessions) = draft.spread_figures(&world.env()).unwrap();
    assert_eq!(session_min, 60);
    assert_eq!(from_date, "2026-11-26");
    let total: i64 = sessions
        .iter()
        .map(|item| item["duration_min"].as_i64().unwrap())
        .sum();
    assert_eq!(total, 120);
}

#[test]
fn a_spread_leaves_out_the_time_already_ticked_done() {
    let world = world();
    let draft = at_length(&world, "120");
    let asked = Cell::new(0);
    let done = |id: &Value| -> EngineResult<i64> {
        assert_eq!(id, "new-1");
        asked.set(asked.get() + 1);
        Ok(60)
    };
    let env = Env {
        done_minutes_for: Some(&done),
        ..world.env()
    };
    let (session_min, _from, sessions) = draft.spread_figures(&env).unwrap();
    let total: i64 = sessions
        .iter()
        .map(|item| item["duration_min"].as_i64().unwrap())
        .sum();
    assert_eq!((session_min, total), (60, 60));
    assert_eq!(asked.get(), 1);
}

#[test]
fn the_done_time_is_asked_for_only_when_a_spread_needs_it() {
    let world = world();
    let mut draft = at_length(&world, "120");
    let asked = Cell::new(0);
    let done = |_id: &Value| -> EngineResult<i64> {
        asked.set(asked.get() + 1);
        Ok(0)
    };
    let env = Env {
        done_minutes_for: Some(&done),
        ..world.env()
    };
    draft.form(&env).unwrap();
    assert_eq!(asked.get(), 0, "spreading is not chosen");
    draft.set(&env, "spread", &json!("spread")).unwrap();
    draft.form(&env).unwrap();
    assert_eq!(asked.get(), 1);
}

#[test]
fn a_spread_line_names_the_sessions_under_the_choice() {
    let world = world();
    let mut draft = at_length(&world, "120");
    put(&mut draft, &world, "spread", json!("spread"));
    let form = shown(&draft, &world);
    assert_eq!(form["spread"], "spread");
    assert_eq!(
        form["spreadLine"],
        "2 \u{d7} 60 min on different days before it's due Sun 29 Nov."
    );
    assert!(draft.spread_requested());
}

#[test]
fn a_spread_is_requested_only_while_it_is_offered() {
    let world = world();
    let mut draft = at_length(&world, "120");
    put(&mut draft, &world, "spread", json!("spread"));
    assert!(draft.spread_requested());
    put(&mut draft, &world, "when", json!("fixed"));
    assert!(!draft.spread_requested());
    let mut short = at_length(&world, "45");
    put(&mut short, &world, "spread", json!("spread"));
    assert!(!short.spread_requested());
}

#[test]
fn a_spread_that_is_not_offered_is_saved_as_one_go() {
    let world = world();
    let mut draft = at_length(&world, "45");
    put(&mut draft, &world, "spread", json!("spread"));
    assert_eq!(
        draft.candidate(&world.env()).unwrap().unwrap()["spread"],
        "one"
    );
    let mut long = at_length(&world, "120");
    put(&mut long, &world, "spread", json!("spread"));
    assert_eq!(
        long.candidate(&world.env()).unwrap().unwrap()["spread"],
        "spread"
    );
}

#[test]
fn the_spread_plan_starts_on_the_selected_day_when_it_is_later_than_today() {
    let mut world = world();
    world.selected = "2026-11-28".to_string();
    let draft = at_length(&world, "120");
    let plan = draft.spread_plan(&world.env()).unwrap();
    assert_eq!(plan, json!({"session_min": 60, "from_date": "2026-11-28"}));
}

#[test]
fn the_spread_plan_starts_no_later_than_the_due_day() {
    let mut world = world();
    world.selected = "2026-12-05".to_string();
    let draft = at_length(&world, "120");
    assert_eq!(
        draft.spread_plan(&world.env()).unwrap()["from_date"],
        "2026-11-29"
    );
}

// Length ------------------------------------------------------------------------------------------

#[test]
fn a_length_that_cannot_be_planned_is_refused_on_the_how_long_step() {
    let world = world();
    let cases = [
        ("10", ESTIMATE_SHORT),
        ("", ESTIMATE_SHORT),
        ("abc", ESTIMATE_SHORT),
        ("1441", ESTIMATE_LONG),
        ("50", SLOT_HINT),
    ];
    for (minutes, words) in cases {
        let mut draft = at_length(&world, minutes);
        typed(&mut draft, &world, "Project");
        assert!(
            draft.candidate(&world.env()).unwrap().is_none(),
            "{minutes}"
        );
        let form = shown(&draft, &world);
        assert_eq!(form["estimateProblem"], words, "{minutes}");
        assert_eq!(form["step"], 2, "{minutes}");
    }
}

#[test]
fn the_longest_allowed_length_is_a_whole_day() {
    let world = world();
    let mut draft = at_length(&world, "1440");
    assert!(draft.candidate(&world.env()).unwrap().is_some());
    assert_eq!(draft.estimate(), 1440);
}

#[test]
fn a_length_problem_follows_what_is_typed_once_it_has_been_shown() {
    let world = world();
    let mut draft = at_length(&world, "10");
    draft.candidate(&world.env()).unwrap();
    put(&mut draft, &world, "estimate", json!("20"));
    assert_eq!(shown(&draft, &world)["estimateProblem"], SLOT_HINT);
    put(&mut draft, &world, "estimate", json!("30"));
    assert_eq!(shown(&draft, &world)["estimateProblem"], "");
}

#[test]
fn a_length_problem_is_not_shown_while_the_student_is_still_typing() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "estimate", json!("1"));
    assert_eq!(shown(&draft, &world)["estimateProblem"], "");
}

#[test]
fn the_length_is_the_digits_typed_and_nothing_else_counts() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "estimate", json!(" 90 "));
    assert_eq!(draft.estimate(), 90);
    assert_eq!(shown(&draft, &world)["estimateLabel"], "1 h 30 min");
    put(&mut draft, &world, "estimate", json!("9x"));
    assert_eq!(draft.estimate(), 0);
    assert_eq!(shown(&draft, &world)["estimateLabel"], "");
    put(&mut draft, &world, "estimate", json!(75));
    assert_eq!(draft.estimate(), 75);
}

#[test]
fn the_quick_lengths_are_offered_in_minutes() {
    let world = world();
    let form = shown(&new_sheet(&world), &world);
    let values: Vec<String> = form["quickLengths"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| text(item, "value"))
        .collect();
    assert_eq!(values, ["15", "30", "45", "60", "90"]);
    assert_eq!(form["quickLengths"][4]["label"], "90 min");
}

// Steps -------------------------------------------------------------------------------------------

#[test]
fn next_on_a_blank_title_stays_and_says_to_give_one() {
    let world = world();
    let mut draft = new_sheet(&world);
    assert!(!draft.advance(&world.env()).unwrap());
    let form = shown(&draft, &world);
    assert_eq!(form["step"], 0);
    assert_eq!(form["titleProblem"], TITLE_PROBLEM);
    put(&mut draft, &world, "title", json!("   "));
    assert!(!draft.advance(&world.env()).unwrap());
    assert_eq!(shown(&draft, &world)["step"], 0);
}

#[test]
fn typing_a_title_takes_the_words_about_it_away() {
    let world = world();
    let mut draft = new_sheet(&world);
    draft.advance(&world.env()).unwrap();
    typed(&mut draft, &world, "Essay");
    assert_eq!(shown(&draft, &world)["titleProblem"], "");
}

#[test]
fn next_goes_through_the_steps_and_save_is_the_last() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    assert!(!draft.advance(&world.env()).unwrap());
    let when = shown(&draft, &world);
    assert_eq!(when["step"], 1);
    assert_eq!(when["prompt"], "When is it due?");
    assert_eq!(when["canBack"], true);
    assert_eq!(when["crumbs"][0]["label"], "\u{2713} What");
    assert_eq!(when["crumbs"][0]["done"], true);
    assert_eq!(when["crumbs"][0]["summary"], "Essay");
    assert_eq!(when["crumbs"][1]["on"], true);
    assert!(!draft.advance(&world.env()).unwrap());
    let last = shown(&draft, &world);
    assert_eq!(last["step"], 2);
    assert_eq!(last["prompt"], "How long will it take?");
    assert_eq!(last["primary"], "Save");
    assert_eq!(last["last"], true);
    assert_eq!(last["showDetails"], true);
    assert_eq!(
        last["crumbs"][1]["summary"],
        "due Fri 27 Nov, FlexWeek picks"
    );
    assert!(draft.advance(&world.env()).unwrap(), "Save is next");
}

#[test]
fn a_pinned_when_is_named_in_the_summary() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    put(&mut draft, &world, "dueTime", json!("17:30"));
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenTime", json!("20:00"));
    draft.advance(&world.env()).unwrap();
    draft.advance(&world.env()).unwrap();
    assert_eq!(
        shown(&draft, &world)["crumbs"][1]["summary"],
        "due Fri 27 Nov, 5:30 PM, pinned"
    );
}

#[test]
fn back_and_a_crumb_return_to_an_earlier_step_only() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    draft.advance(&world.env()).unwrap();
    draft.advance(&world.env()).unwrap();
    draft.goto(2);
    assert_eq!(
        draft.field("step").unwrap(),
        2,
        "the step already on is not a way back"
    );
    draft.goto(5);
    assert_eq!(draft.field("step").unwrap(), 2);
    draft.goto(0);
    assert_eq!(draft.field("step").unwrap(), 0);
    draft.back();
    assert_eq!(
        draft.field("step").unwrap(),
        0,
        "the first step has no way back"
    );
    draft.advance(&world.env()).unwrap();
    draft.back();
    assert_eq!(draft.field("step").unwrap(), 0);
}

#[test]
fn an_edit_is_one_page_with_no_steps() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    let form = shown(&draft, &world);
    assert_eq!(form["mode"], "edit");
    assert_eq!(form["heading"], "Edit homework");
    assert_eq!(form["step"], -1);
    assert_eq!(form["crumbs"], json!([]));
    assert_eq!(form["prompt"], "");
    assert_eq!(form["primary"], "Save");
    assert_eq!(form["canBack"], false);
    assert_eq!(form["canDelete"], true);
    assert_eq!(form["showDetails"], true);
    assert_eq!(form["showFinished"], true);
    assert!(draft.advance(&world.env()).unwrap());
    draft.back();
    draft.goto(0);
    assert_eq!(draft.field("step").unwrap(), Value::Null);
}

#[test]
fn a_pinned_time_in_the_past_stops_next_on_the_when_step() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    draft.advance(&world.env()).unwrap();
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(3));
    put(&mut draft, &world, "whenTime", json!("18:30"));
    assert!(!draft.advance(&world.env()).unwrap());
    let form = shown(&draft, &world);
    assert_eq!(form["step"], 1);
    assert_eq!(form["whenProblem"], PAST);
}

#[test]
fn a_pinned_time_that_ends_after_the_due_stops_next_without_the_stayed_words() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    draft.advance(&world.env()).unwrap();
    put(&mut draft, &world, "dueDate", json!("2026-11-26"));
    put(&mut draft, &world, "dueTime", json!("20:00"));
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenTime", json!("19:30"));
    assert!(!draft.advance(&world.env()).unwrap());
    assert_eq!(
        shown(&draft, &world)["whenProblem"],
        "That ends after it's due."
    );
}

// Pinned times -----------------------------------------------------------------------------------

fn pinned(world: &World, day: i64, time: &str) -> HomeworkDraft {
    let mut draft = edit(world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, world, "when", json!("fixed"));
    put(&mut draft, world, "whenDay", json!(day));
    put(&mut draft, world, "whenTime", json!(time));
    draft
}

fn with_essay_at(start: &str, pinned_there: bool) -> World {
    let mut world = world();
    world.blocks = vec![session("essay-1", 3, start, pinned_there)];
    world
}

#[test]
fn a_pinned_time_already_past_today_is_refused_and_nothing_is_saved() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "18:30");
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    assert_eq!(shown(&draft, &world)["whenProblem"], PAST);
    assert_eq!(
        draft.field("step").unwrap(),
        Value::Null,
        "an edit has no step to go back to"
    );
}

#[test]
fn a_pinned_time_still_ahead_today_saves() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "19:30");
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["fixed_at"], json!({"day": 3, "start": "19:30"}));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn the_field_says_the_time_has_passed_as_soon_as_it_is_picked() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "18:30");
    assert_eq!(shown(&draft, &world)["whenProblem"], PAST);
    put(&mut draft, &world, "whenTime", json!("19:30"));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn the_refusal_names_the_next_time_on_the_students_step() {
    for (step, next) in [(5, "7:05 PM"), (15, "7:15 PM")] {
        let mut world = with_essay_at("18:45", false);
        world.prefs = json!({"drag_step_min": step});
        let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
        draft.read_clock("2026-11-26T19:02").unwrap();
        put(&mut draft, &world, "when", json!("fixed"));
        put(&mut draft, &world, "whenDay", json!(3));
        put(&mut draft, &world, "whenTime", json!("18:30"));
        assert_eq!(
            shown(&draft, &world)["whenProblem"],
            format!("That time has passed. Choose {next} or later today, or another day.")
        );
    }
}

#[test]
fn a_step_that_is_not_five_or_fifteen_counts_as_fifteen() {
    let mut world = with_essay_at("18:45", false);
    world.prefs = json!({"drag_step_min": 7});
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(4));
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
    world.prefs = json!({"drag_step_min": true});
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
    world.prefs = Value::Null;
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
    world.prefs = json!({"drag_step_min": 5});
    assert_eq!(offered(&shown(&draft, &world)).len(), 288);
}

#[test]
fn a_pinned_time_on_a_day_ahead_is_not_told_it_has_passed() {
    let world = with_essay_at("18:45", false);
    let ahead = pinned(&world, 4, "18:30");
    assert_eq!(shown(&ahead, &world)["whenProblem"], "");
}

#[test]
fn a_pinned_time_on_a_day_already_over_says_the_day_is_over() {
    let world = with_essay_at("18:45", false);
    let gone = pinned(&world, 2, "18:30");
    assert_eq!(
        shown(&gone, &world)["whenProblem"],
        "That time has passed. The day is over, so choose another day."
    );
}

#[test]
fn finished_homework_is_not_told_its_pinned_time_has_passed() {
    let world = with_essay_at("18:45", false);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "completed", json!(true));
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(3));
    put(&mut draft, &world, "whenTime", json!("18:30"));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn ticking_finished_clears_the_message_about_a_time_that_has_passed() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "18:30");
    assert_eq!(shown(&draft, &world)["whenProblem"], PAST);
    put(&mut draft, &world, "completed", json!(true));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn a_pin_the_homework_already_had_is_left_alone_when_opened() {
    // The essay sits at 18:45 and the clock is 19:00: opening and saving it is not the student's mistake.
    let world = with_essay_at("18:45", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    let form = shown(&draft, &world);
    assert_eq!(form["when"], "fixed");
    assert_eq!(form["whenProblem"], "");
    assert!(draft.candidate(&world.env()).unwrap().is_some());
}

#[test]
fn changing_the_time_of_a_pin_already_past_is_refused() {
    let world = with_essay_at("20:00", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(
        shown(&draft, &world)["whenProblem"],
        "",
        "opening it changes nothing"
    );
    put(&mut draft, &world, "whenTime", json!("18:30"));
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    assert_eq!(shown(&draft, &world)["whenProblem"], PAST);
}

#[test]
fn switching_away_from_and_back_to_the_same_pin_is_not_a_mistake() {
    let world = with_essay_at("18:45", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "when", json!("plan"));
    put(&mut draft, &world, "when", json!("fixed"));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn a_plan_choice_over_a_pinned_session_saves_the_pin_as_removed() {
    let world = with_essay_at("18:45", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "when", json!("plan"));
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["fixed_at"], Value::Null);
    let mut untouched = edit(&world, &essay("2026-11-29T23:59", 60));
    let kept = untouched.candidate(&world.env()).unwrap().unwrap();
    assert!(kept.get("fixed_at").is_none());
}

#[test]
fn the_time_list_for_today_starts_at_the_earliest_time_allowed() {
    // The clock reads 19:00, so the note says "Today from 7:00 PM onward." and the list starts there.
    let world = with_essay_at("18:45", false);
    let draft = pinned(&world, 3, "19:30");
    let form = shown(&draft, &world);
    assert_eq!(form["whenFrom"], "Today from 7:00 PM onward.");
    let wanted: Vec<String> = (19 * 60..24 * 60)
        .step_by(15)
        .map(|minute| format!("{:02}:{:02}", minute / 60, minute % 60))
        .collect();
    assert_eq!(offered(&form), wanted);
}

#[test]
fn the_time_list_keeps_every_time_on_a_day_ahead_and_on_a_day_gone() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 4, "18:30");
    let ahead = offered(&shown(&draft, &world));
    assert_eq!(ahead.len(), 96);
    assert_eq!(ahead[0], "00:00");
    assert_eq!(shown(&draft, &world)["whenFrom"], "");
    put(&mut draft, &world, "whenDay", json!(2));
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
}

#[test]
fn a_past_time_already_saved_stays_in_the_list_on_its_own_day_only() {
    // The essay is pinned at 18:45 and the clock is 19:00: that time stays, the other past ones go.
    let world = with_essay_at("18:45", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    let times = offered(&shown(&draft, &world));
    assert!(times.contains(&"18:45".to_string()));
    assert!(!times.contains(&"18:30".to_string()));
    assert!(times.contains(&"19:00".to_string()));
    put(&mut draft, &world, "whenDay", json!(4));
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
    put(&mut draft, &world, "whenDay", json!(3));
    assert!(offered(&shown(&draft, &world)).contains(&"18:45".to_string()));
}

#[test]
fn finished_homework_keeps_the_whole_time_list() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "19:30");
    put(&mut draft, &world, "completed", json!(true));
    assert_eq!(offered(&shown(&draft, &world)).len(), 96);
}

#[test]
fn a_time_off_the_step_is_listed_in_order_so_the_field_can_show_it() {
    let world = with_essay_at("10:07", true);
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    // Thursday is today and 10:07 is over, but it is the time the homework already had: it stays, first.
    let today = shown(&draft, &world);
    let times = offered(&today);
    assert_eq!(times[0], "10:07");
    assert_eq!(times[1], "19:00");
    assert_eq!(today["pinnedTimeOptions"][0]["label"], "10:07 AM");
    // On a day ahead the whole day is listed and the off-step time sits between its neighbours.
    put(&mut draft, &world, "whenDay", json!(4));
    let ahead = shown(&draft, &world);
    let times = offered(&ahead);
    let at = times.iter().position(|time| time == "10:07").unwrap();
    assert_eq!(times[at - 1], "10:00");
    assert_eq!(times[at + 1], "10:15");
    assert_eq!(ahead["pinnedTimeOptions"][at]["label"], "10:07 AM");
}

#[test]
fn a_time_off_the_step_the_student_typed_is_listed_too() {
    let world = with_essay_at("18:45", false);
    let draft = pinned(&world, 4, "10:07");
    let times = offered(&shown(&draft, &world));
    assert_eq!(times.len(), 97);
    assert!(times.contains(&"10:07".to_string()));
}

#[test]
fn the_due_time_choices_start_with_end_of_day() {
    let world = world();
    let form = shown(&new_sheet(&world), &world);
    let options = form["timeOptions"].as_array().unwrap();
    assert_eq!(options.len(), 97);
    assert_eq!(options[0], json!({"value": "", "label": "End of day"}));
    assert_eq!(options[1], json!({"value": "00:00", "label": "12:00 AM"}));
    assert_eq!(options[96], json!({"value": "23:45", "label": "11:45 PM"}));
}

#[test]
fn quarter_hours_lists_every_mark_of_the_step() {
    let fifteen = quarter_hours(15).unwrap();
    assert_eq!(fifteen.as_array().unwrap().len(), 96);
    assert_eq!(fifteen[0], json!({"value": "00:00", "label": "12:00 AM"}));
    assert_eq!(fifteen[67], json!({"value": "16:45", "label": "4:45 PM"}));
    assert_eq!(quarter_hours(5).unwrap().as_array().unwrap().len(), 288);
    assert!(quarter_hours(0).is_err());
}

// What the sheet shows ---------------------------------------------------------------------------

#[test]
fn the_due_choices_are_four_weeks_from_today() {
    let world = world();
    let form = shown(&new_sheet(&world), &world);
    let options = form["dueOptions"].as_array().unwrap();
    assert_eq!(options.len(), 28);
    assert_eq!(
        options[0],
        json!({"value": "2026-11-26", "label": "Today \u{b7} Thu 26 Nov"})
    );
    assert_eq!(
        options[1],
        json!({"value": "2026-11-27", "label": "Tomorrow \u{b7} Fri 27 Nov"})
    );
    assert_eq!(
        options[2],
        json!({"value": "2026-11-28", "label": "Sat 28 Nov"})
    );
    assert_eq!(
        options[5],
        json!({"value": "2026-12-01", "label": "Tue 1 Dec"})
    );
    assert_eq!(options[27]["value"], "2026-12-23");
}

#[test]
fn a_due_outside_the_four_weeks_is_listed_first() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "dueDate", json!("2026-12-30"));
    let options = shown(&draft, &world)["dueOptions"]
        .as_array()
        .unwrap()
        .clone();
    assert_eq!(options.len(), 29);
    assert_eq!(
        options[0],
        json!({"value": "2026-12-30", "label": "Wed 30 Dec"})
    );
    assert_eq!(options[1]["label"], "Today \u{b7} Thu 26 Nov");
    put(&mut draft, &world, "dueDate", json!("2026-11-28"));
    assert_eq!(
        shown(&draft, &world)["dueOptions"]
            .as_array()
            .unwrap()
            .len(),
        28
    );
}

#[test]
fn the_days_are_named_from_the_week_on_screen() {
    let mut world = world();
    world.week = Some("2026-11-25".to_string());
    let form = shown(&new_sheet(&world), &world);
    let labels: Vec<String> = form["dayOptions"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| text(item, "label"))
        .collect();
    assert_eq!(
        labels,
        [
            "Wed 25", "Thu 26", "Fri 27", "Sat 28", "Sun 29", "Mon 30", "Tue 1"
        ]
    );
    assert_eq!(form["dayOptions"][3]["value"], 3);
}

#[test]
fn an_edit_says_where_the_sessions_are_planned() {
    let mut world = world();
    world.blocks = vec![
        session("essay-2", 4, "09:00", false),
        session("essay-1", 3, "18:45", false),
    ];
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(
        shown(&draft, &world)["placedLine"],
        "Planned Thu 26 and Fri 27 \u{b7} due Sun 29 \u{b7} 2 times"
    );
    world.blocks = vec![session("essay-1", 3, "18:45", false)];
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(
        shown(&draft, &world)["placedLine"],
        "Planned Thu 26 \u{b7} due Sun 29"
    );
    world.blocks = Vec::new();
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(shown(&draft, &world)["placedLine"], "");
}

#[test]
fn three_sessions_are_listed_with_commas_and_an_and() {
    let mut world = world();
    world.blocks = vec![
        session("a", 0, "09:00", false),
        session("b", 2, "09:00", false),
        session("c", 3, "09:00", false),
    ];
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(
        shown(&draft, &world)["placedLine"],
        "Planned Mon 23, Wed 25 and Thu 26 \u{b7} due Sun 29 \u{b7} 3 times"
    );
}

#[test]
fn a_finished_session_is_not_an_open_one() {
    let mut world = world();
    let mut done = session("essay-1", 3, "18:45", true);
    done["completed"] = json!(true);
    world.blocks = vec![done];
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    let form = shown(&draft, &world);
    assert_eq!(form["when"], "plan");
    assert_eq!(form["placedLine"], "");
    assert_eq!(form["canUnpin"], false);
}

#[test]
fn another_homeworks_session_is_not_this_ones() {
    let mut world = world();
    let mut other = session("x", 3, "18:45", true);
    other["assignment_id"] = json!("other");
    world.blocks = vec![other];
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    assert_eq!(shown(&draft, &world)["when"], "plan");
}

#[test]
fn a_pinned_session_lets_the_student_unpin_it() {
    let world = with_essay_at("18:45", true);
    let draft = edit(&world, &essay("2026-11-29T23:59", 60));
    let form = shown(&draft, &world);
    assert_eq!(form["canUnpin"], true);
    assert_eq!(
        form["whenNote"],
        "Pinned to Thu at 6:45 PM. Plan won't move it."
    );
    assert_eq!(form["whenFrom"], "Today from 7:00 PM onward.");
}

#[test]
fn the_details_open_when_there_is_something_in_them() {
    let world = world();
    assert_eq!(shown(&new_sheet(&world), &world)["detailsOpen"], false);
    let mut with_notes = essay("2026-11-29T23:59", 60);
    with_notes["notes"] = json!("Use the library copy");
    let draft = edit(&world, &with_notes);
    let form = shown(&draft, &world);
    assert_eq!(form["detailsOpen"], true);
    assert_eq!(form["notes"], "Use the library copy");
    let mut with_course = essay("2026-11-29T23:59", 60);
    with_course["course"] = json!("History");
    assert_eq!(
        shown(&edit(&world, &with_course), &world)["course"],
        "History"
    );
}

#[test]
fn the_fixed_choices_carry_their_words() {
    let world = world();
    let form = shown(&new_sheet(&world), &world);
    assert_eq!(
        form["whenChoices"],
        json!([
            {"value": "plan", "label": "FlexWeek picks the time"},
            {"value": "fixed", "label": "Choose a time myself"}
        ])
    );
    assert_eq!(
        form["spreadChoices"],
        json!([
            {"value": "one", "label": "In one go"},
            {"value": "spread", "label": "Spread over days"}
        ])
    );
    assert_eq!(
        form["typeOptions"][0],
        json!({"value": 1, "label": "Test prep"})
    );
    assert_eq!(
        form["typeOptions"][3],
        json!({"value": 4, "label": "Reading"})
    );
    assert_eq!(
        form["energyOptions"][2],
        json!({"value": "low", "label": "Evening"})
    );
    assert_eq!(form["energy"], "medium");
    assert_eq!(form["priority"], 3);
    assert_eq!(form["estimateSuffix"], "min");
}

// Edits -------------------------------------------------------------------------------------------

#[test]
fn a_change_takes_the_error_words_away() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "title", json!(""));
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    assert_eq!(draft.field("title_problem").unwrap(), TITLE_PROBLEM);
    typed(&mut draft, &world, "Essay");
    assert_eq!(draft.field("title_problem").unwrap(), "");
}

#[test]
fn a_changed_date_takes_the_due_and_pinned_words_away() {
    let world = with_essay_at("18:45", false);
    let mut draft = pinned(&world, 3, "18:30");
    assert_eq!(shown(&draft, &world)["whenProblem"], PAST);
    put(&mut draft, &world, "dueDate", json!("2026-11-28"));
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
}

#[test]
fn a_field_that_is_not_known_changes_nothing_but_the_error() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "nothing", json!("x"));
    assert!(draft.field("error").unwrap() == "");
}

#[test]
fn the_other_fields_take_what_they_are_given() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "course", json!("History"));
    put(&mut draft, &world, "priority", json!(4));
    put(&mut draft, &world, "energy", json!("low"));
    put(&mut draft, &world, "notes", json!("Chapter 3"));
    put(&mut draft, &world, "detailsOpen", json!(true));
    put(&mut draft, &world, "spread", json!("anything"));
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["course"], "History");
    assert_eq!(made["priority"], 4);
    assert_eq!(made["energy"], "low");
    assert_eq!(made["notes"], "Chapter 3");
    assert_eq!(made["spread"], "one");
    let form = shown(&draft, &world);
    assert_eq!(form["spread"], "one", "anything but spread is one go");
    assert_eq!(form["detailsOpen"], true);
    put(&mut draft, &world, "course", json!(""));
    assert_eq!(
        draft.candidate(&world.env()).unwrap().unwrap()["course"],
        Value::Null
    );
}

#[test]
fn a_whole_number_comes_from_text_a_float_or_a_flag() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "whenDay", json!("2"));
    assert_eq!(draft.field("when_day").unwrap(), 2);
    put(&mut draft, &world, "whenDay", json!(4.9));
    assert_eq!(draft.field("when_day").unwrap(), 4);
    assert!(draft.set(&world.env(), "whenDay", &json!("soon")).is_err());
    assert!(draft.set(&world.env(), "priority", &Value::Null).is_err());
}

#[test]
fn a_picked_time_pins_the_sheet_and_keeps_the_typed_words() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    put(&mut draft, &world, "estimate", json!("90"));
    draft.use_picked(&world.env(), 4, "09:30").unwrap();
    let form = shown(&draft, &world);
    assert_eq!(form["when"], "fixed");
    assert_eq!(form["whenDay"], 4);
    assert_eq!(form["whenTime"], "09:30");
    assert_eq!(form["title"], "Essay");
    assert_eq!(form["estimate"], "90");
}

#[test]
fn a_sheet_kept_while_away_judges_a_picked_time_by_the_clock_when_it_opens_again() {
    let world = world();
    let mut draft = new_sheet(&world);
    draft.use_picked(&world.env(), 3, "19:30").unwrap();
    assert_eq!(shown(&draft, &world)["whenProblem"], "");
    draft.read_clock("2026-11-26T20:00").unwrap();
    put(&mut draft, &world, "whenTime", json!("19:30"));
    assert_eq!(
        shown(&draft, &world)["whenProblem"],
        "That time has passed. Choose 8:00 PM or later today, or another day."
    );
    assert_eq!(draft.field("today").unwrap(), "2026-11-26");
}

#[test]
fn the_clock_reading_must_be_a_date_and_a_minute() {
    let world = world();
    let mut draft = new_sheet(&world);
    assert!(draft.read_clock("tonight").is_err());
    assert!(
        HomeworkDraft::open(&world.env(), "later", "x", None, &OpenOptions::default()).is_err()
    );
}

// Dirty ---------------------------------------------------------------------------------------------

#[test]
fn closing_loses_only_what_was_typed_after_opening() {
    let world = world();
    let mut draft = new_sheet(&world);
    assert!(!draft.dirty().unwrap());
    typed(&mut draft, &world, "Essay");
    assert!(draft.dirty().unwrap());
    typed(&mut draft, &world, "");
    assert!(
        !draft.dirty().unwrap(),
        "typed and erased is the same as not typed"
    );
}

#[test]
fn every_kept_field_counts_as_typed_work() {
    let world = world();
    let changes = [
        ("dueDate", json!("2026-11-28")),
        ("dueTime", json!("10:00")),
        ("estimate", json!("30")),
        ("when", json!("fixed")),
        ("whenDay", json!(4)),
        ("whenTime", json!("22:00")),
        ("spread", json!("spread")),
        ("course", json!("Art")),
        ("priority", json!(1)),
        ("energy", json!("high")),
        ("notes", json!("x")),
        ("completed", json!(true)),
    ];
    for (name, value) in changes {
        let mut draft = new_sheet(&world);
        put(&mut draft, &world, name, value);
        assert!(draft.dirty().unwrap(), "{name}");
    }
}

#[test]
fn a_link_and_a_step_count_as_typed_work() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "linkLabel", json!("Notes"));
    put(&mut draft, &world, "linkUrl", json!("https://example.org"));
    assert!(
        !draft.dirty().unwrap(),
        "the unsent link fields are not part of the homework"
    );
    draft.add_link();
    assert!(draft.dirty().unwrap());
    draft.remove_link(0);
    assert!(!draft.dirty().unwrap());
    put(&mut draft, &world, "checkText", json!("Read"));
    draft.add_check("c1");
    assert!(draft.dirty().unwrap());
    draft.toggle_check(0);
    draft.remove_check(0);
    assert!(!draft.dirty().unwrap());
}

#[test]
fn a_step_is_ticked_and_unticked() {
    let world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "checkText", json!("Read"));
    draft.add_check("c1");
    draft.toggle_check(0);
    assert_eq!(draft.field("checklist").unwrap()[0]["done"], true);
    assert!(draft.dirty().unwrap());
    draft.toggle_check(0);
    assert_eq!(draft.field("checklist").unwrap()[0]["done"], false);
}

// Links and the checklist ------------------------------------------------------------------------

#[test]
fn a_link_needs_a_name_and_an_address() {
    let world = world();
    let mut draft = new_sheet(&world);
    draft.add_link();
    let words = "Give the link a name and an address that starts with http:// or https://.";
    assert_eq!(shown(&draft, &world)["detailsError"], words);
    put(&mut draft, &world, "linkLabel", json!("  Notes "));
    draft.add_link();
    assert_eq!(shown(&draft, &world)["detailsError"], words);
    put(
        &mut draft,
        &world,
        "linkUrl",
        json!(" https://example.org/a "),
    );
    draft.add_link();
    let form = shown(&draft, &world);
    assert_eq!(form["detailsError"], "");
    assert_eq!(
        form["links"],
        json!([{"label": "Notes", "url": "https://example.org/a"}])
    );
    assert_eq!(form["linkLabel"], "");
    assert_eq!(form["linkUrl"], "");
}

#[test]
fn a_homework_holds_twenty_links() {
    let world = world();
    let mut draft = new_sheet(&world);
    for number in 0..20 {
        put(
            &mut draft,
            &world,
            "linkLabel",
            json!(format!("Link {number}")),
        );
        put(&mut draft, &world, "linkUrl", json!("https://example.org"));
        draft.add_link();
        assert_eq!(draft.field("details_error").unwrap(), "");
    }
    put(&mut draft, &world, "linkLabel", json!("One more"));
    put(&mut draft, &world, "linkUrl", json!("https://example.org"));
    draft.add_link();
    assert_eq!(draft.field("details_error").unwrap(), "Up to 20 links.");
    assert_eq!(draft.field("links").unwrap().as_array().unwrap().len(), 20);
    assert_eq!(
        draft.field("link_label").unwrap(),
        "One more",
        "what was typed is kept"
    );
}

#[test]
fn a_link_is_removed_by_its_place_and_a_place_that_is_not_there_changes_nothing() {
    let world = world();
    let mut draft = new_sheet(&world);
    for label in ["A", "B", "C"] {
        put(&mut draft, &world, "linkLabel", json!(label));
        put(&mut draft, &world, "linkUrl", json!("https://example.org"));
        draft.add_link();
    }
    draft.remove_link(3);
    draft.remove_link(-1);
    assert_eq!(draft.field("links").unwrap().as_array().unwrap().len(), 3);
    draft.remove_link(1);
    let labels: Vec<Value> = draft
        .field("links")
        .unwrap()
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["label"].clone())
        .collect();
    assert_eq!(labels, [json!("A"), json!("C")]);
}

#[test]
fn a_checklist_step_needs_text_and_takes_the_id_it_is_given() {
    let world = world();
    let mut draft = new_sheet(&world);
    draft.add_check("id-1");
    assert_eq!(
        shown(&draft, &world)["detailsError"],
        "A checklist step needs text."
    );
    put(&mut draft, &world, "checkText", json!("  Read chapter 3 "));
    draft.add_check("id-2");
    let form = shown(&draft, &world);
    assert_eq!(form["detailsError"], "");
    assert_eq!(
        form["checklist"],
        json!([{"text": "Read chapter 3", "done": false}])
    );
    assert_eq!(form["checkText"], "");
    assert_eq!(draft.field("checklist").unwrap()[0]["id"], "id-2");
}

#[test]
fn a_homework_holds_forty_steps() {
    let world = world();
    let mut draft = new_sheet(&world);
    for number in 0..40 {
        put(
            &mut draft,
            &world,
            "checkText",
            json!(format!("Step {number}")),
        );
        draft.add_check(&format!("id-{number}"));
    }
    put(&mut draft, &world, "checkText", json!("One more"));
    draft.add_check("id-40");
    assert_eq!(draft.field("details_error").unwrap(), "Up to 40 steps.");
    assert_eq!(
        draft.field("checklist").unwrap().as_array().unwrap().len(),
        40
    );
}

#[test]
fn a_step_is_ticked_and_removed_by_its_place() {
    let world = world();
    let mut draft = new_sheet(&world);
    for label in ["A", "B"] {
        put(&mut draft, &world, "checkText", json!(label));
        draft.add_check(label);
    }
    draft.toggle_check(1);
    draft.toggle_check(2);
    draft.toggle_check(-1);
    let form = shown(&draft, &world);
    assert_eq!(
        form["checklist"],
        json!([{"text": "A", "done": false}, {"text": "B", "done": true}])
    );
    draft.remove_check(0);
    draft.remove_check(5);
    assert_eq!(
        shown(&draft, &world)["checklist"],
        json!([{"text": "B", "done": true}])
    );
}

#[test]
fn the_links_and_steps_go_with_the_saved_homework() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    put(&mut draft, &world, "linkLabel", json!("Notes"));
    put(&mut draft, &world, "linkUrl", json!("https://example.org"));
    draft.add_link();
    put(&mut draft, &world, "checkText", json!("Read"));
    draft.add_check("step-1");
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(
        made["links"],
        json!([{"label": "Notes", "url": "https://example.org"}])
    );
    assert_eq!(
        made["checklist"],
        json!([{"id": "step-1", "text": "Read", "done": false}])
    );
}

// The answer -------------------------------------------------------------------------------------

#[test]
fn a_new_homework_is_saved_as_typed_with_the_fields_the_engine_expects() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "  Essay  ");
    put(&mut draft, &world, "estimate", json!("90"));
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["id"], "new-1");
    assert_eq!(made["title"], "Essay");
    assert_eq!(made["due"], "2026-11-27T23:59");
    assert_eq!(made["estimate_min"], 90);
    assert_eq!(made["spread"], "one");
    assert_eq!(made["course"], Value::Null);
    assert_eq!(made["priority"], 3);
    assert_eq!(made["energy"], "medium");
    assert_eq!(made["completed"], false);
    assert_eq!(made["completed_at"], Value::Null);
    assert_eq!(made["revision"], 0);
    assert!(made.get("fixed_at").is_none());
}

#[test]
fn a_new_homework_pinned_to_a_time_carries_it() {
    let world = world();
    let mut draft = new_sheet(&world);
    typed(&mut draft, &world, "Essay");
    draft.use_picked(&world.env(), 4, "09:30").unwrap();
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["fixed_at"], json!({"day": 4, "start": "09:30"}));
}

#[test]
fn a_blank_title_on_a_new_sheet_takes_the_student_back_to_what() {
    let world = world();
    let mut draft = new_sheet(&world);
    draft.advance(&world.env()).unwrap();
    put(&mut draft, &world, "title", json!("x"));
    draft.advance(&world.env()).unwrap();
    draft.advance(&world.env()).unwrap();
    put(&mut draft, &world, "title", json!(" "));
    assert!(draft.candidate(&world.env()).unwrap().is_none());
    let form = shown(&draft, &world);
    assert_eq!(form["step"], 0);
    assert_eq!(form["titleProblem"], TITLE_PROBLEM);
}

#[test]
fn a_refusal_the_engine_words_about_another_field_shows_as_the_sheets_error() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "notes", json!("n".repeat(100_000)));
    let refused = draft.candidate(&world.env()).unwrap();
    assert!(refused.is_none());
    let form = shown(&draft, &world);
    assert_ne!(form["error"], "");
    put(&mut draft, &world, "notes", json!("short"));
    assert_eq!(shown(&draft, &world)["error"], "");
}

#[test]
fn finished_homework_is_stamped_with_the_time_it_was_ticked() {
    let world = world();
    let mut draft = edit(&world, &essay("2026-11-29T23:59", 60));
    put(&mut draft, &world, "completed", json!(true));
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["completed"], true);
    assert_eq!(made["completed_at"], "2026-11-26T19:00");
}

#[test]
fn finished_homework_keeps_the_time_it_was_first_finished() {
    let world = world();
    let mut done = essay("2026-11-29T23:59", 60);
    done["completed"] = json!(true);
    done["completed_at"] = json!("2026-11-20T08:00");
    let mut draft = edit(&world, &done);
    assert_eq!(
        draft.candidate(&world.env()).unwrap().unwrap()["completed_at"],
        "2026-11-20T08:00"
    );
    put(&mut draft, &world, "completed", json!(false));
    let again = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(again["completed"], false);
    assert_eq!(again["completed_at"], Value::Null);
}

#[test]
fn saving_keeps_what_the_sheet_does_not_show() {
    let world = world();
    let mut kept = essay("2026-11-29T23:59", 60);
    kept["focus_minutes"] = json!(25);
    kept["revision"] = json!(7);
    let mut draft = edit(&world, &kept);
    let made = draft.candidate(&world.env()).unwrap().unwrap();
    assert_eq!(made["focus_minutes"], 25);
    assert_eq!(made["revision"], 7);
    assert_eq!(made["id"], "essay");
}

#[test]
fn a_stored_spread_choice_is_kept_by_an_edit_that_shows_it() {
    let world = world();
    let mut stored = essay("2026-11-29T23:59", 120);
    stored["spread"] = json!("spread");
    let draft = edit(&world, &stored);
    let form = shown(&draft, &world);
    assert_eq!(form["spread"], "spread");
    assert_eq!(form["spreadShown"], true);
}

// A sheet kept across weeks ----------------------------------------------------------------------

#[test]
fn a_kept_sheet_opened_in_a_week_that_starts_on_another_day_picks_the_day_again() {
    let mut world = world();
    let mut draft = new_sheet(&world);
    assert_eq!(draft.field("when_day").unwrap(), 3);
    world.week = Some("2026-11-25".to_string());
    draft.follow_week(&world.env(), 1).unwrap();
    let form = shown(&draft, &world);
    assert_eq!(form["whenDay"], 1);
    assert_eq!(form["whenMovedNote"], "");
    assert!(
        !draft.dirty().unwrap(),
        "the day as the app put it is not typed work"
    );
}

#[test]
fn a_day_the_student_picked_keeps_its_weekday_in_the_new_week() {
    let mut world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(4));
    world.week = Some("2026-11-25".to_string());
    draft.follow_week(&world.env(), 0).unwrap();
    // Friday the 27th is the third day of a week from Wednesday the 25th.
    assert_eq!(draft.field("when_day").unwrap(), 2);
    assert_eq!(
        shown(&draft, &world)["whenMovedNote"],
        "",
        "the date did not change"
    );
}

#[test]
fn a_pin_whose_date_changed_is_named_until_another_day_is_picked() {
    let mut world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(3));
    world.week = Some("2026-12-02".to_string());
    draft.follow_week(&world.env(), 0).unwrap();
    // Thursday 26 November is not in the week from Wednesday 2 December: the pin went to Thursday 3 December.
    let form = shown(&draft, &world);
    assert_eq!(form["whenDay"], 1);
    assert_eq!(
        form["whenMovedNote"],
        "Thursday 26 November isn't in this week any more, so it moved to Thursday 3 December."
    );
    assert_eq!(
        form["whenDayAccess"],
        "Day, moved from Thursday 26 November to Thursday 3 December"
    );
    put(&mut draft, &world, "when", json!("plan"));
    let plan = shown(&draft, &world);
    assert_eq!(
        plan["whenMovedNote"], "",
        "a move is named only while pinned"
    );
    assert_eq!(plan["whenDayAccess"], "");
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(2));
    let picked = shown(&draft, &world);
    assert_eq!(picked["whenMovedNote"], "");
    assert_eq!(picked["whenDayAccess"], "");
}

#[test]
fn a_move_inside_one_month_names_the_weekday_and_the_date_only() {
    let mut world = world();
    world.week = Some("2026-11-02".to_string());
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "when", json!("fixed"));
    put(&mut draft, &world, "whenDay", json!(0));
    world.week = Some("2026-11-04".to_string());
    draft.follow_week(&world.env(), 0).unwrap();
    // Monday 2 November is not in the week from Wednesday 4 November: the pin went to Monday 9 November.
    let form = shown(&draft, &world);
    assert_eq!(form["whenDay"], 5);
    assert_eq!(
        form["whenMovedNote"],
        "Monday 2 isn't in this week any more, so it moved to Monday 9."
    );
    assert_eq!(form["whenDayAccess"], "Day, moved from Monday 2");
}

#[test]
fn a_sheet_opened_for_a_given_day_keeps_it_even_if_the_week_starts_elsewhere() {
    let mut world = world();
    let given = OpenOptions {
        when_day: Some(4),
        ..OpenOptions::default()
    };
    let mut draft = HomeworkDraft::open(&world.env(), THURSDAY, "g", None, &given).unwrap();
    world.week = Some("2026-11-25".to_string());
    draft.follow_week(&world.env(), 0).unwrap();
    assert_eq!(draft.field("when_day").unwrap(), 2);
}

#[test]
fn a_kept_sheet_in_a_week_with_the_same_first_day_changes_nothing() {
    let mut world = world();
    let mut draft = new_sheet(&world);
    put(&mut draft, &world, "whenDay", json!(4));
    world.week = Some("2026-11-30".to_string());
    draft.follow_week(&world.env(), 0).unwrap();
    assert_eq!(draft.field("when_day").unwrap(), 4);
}

// What the Python reads --------------------------------------------------------------------------

#[test]
fn a_state_field_is_read_by_its_name_and_an_unknown_name_is_refused() {
    let world = world();
    let draft = new_sheet(&world);
    for name in [
        "existing",
        "original",
        "step",
        "title",
        "due_date",
        "due_time",
        "estimate_text",
        "spread",
        "completed",
        "course",
        "priority",
        "energy",
        "notes",
        "links",
        "checklist",
        "link_label",
        "link_url",
        "check_text",
        "details_open",
        "placed",
        "spread_out",
        "when",
        "when_day",
        "when_time",
        "pinned_session",
        "title_problem",
        "due_problem",
        "when_problem",
        "estimate_problem",
        "error",
        "details_error",
        "today",
        "stamp",
    ] {
        assert!(draft.field(name).is_ok(), "{name}");
    }
    assert_eq!(draft.field("stamp").unwrap(), THURSDAY);
    assert_eq!(draft.field("existing").unwrap(), false);
    assert_eq!(draft.field("estimate_text").unwrap(), "60");
    assert_eq!(draft.field("placed").unwrap(), Value::Null);
    assert!(draft.field("nothing").is_err());
}

#[test]
fn a_sheet_for_a_malformed_assignment_is_refused() {
    let world = world();
    let bad = json!({"id": "x"});
    assert!(
        HomeworkDraft::open(
            &world.env(),
            THURSDAY,
            "x",
            Some(&bad),
            &OpenOptions::default()
        )
        .is_err()
    );
    assert!(
        HomeworkDraft::open(
            &world.env(),
            THURSDAY,
            "x",
            Some(&json!([])),
            &OpenOptions::default()
        )
        .is_err()
    );
}
