//! Block sheet and paste preview (P5-S1). Expected sentences are the ones the Python sheets and
//! the desktop tests already pin. These tests leave the process on the 24-hour clock.

use flexweek_app::views::sheet_block::{BlockDraft, SheetClock};
use flexweek_app::views::sheet_preview::{NONE_CHOSEN, PreviewDraft, beside_words};
use serde_json::{Value, json};

const WEEK: &str = "2026-11-23";
const NEXT_WEEK: &str = "2026-11-29";

fn clock_with(blocks: Value, repeats: Value) -> SheetClock {
    SheetClock {
        week_start: json!(WEEK),
        blocks,
        preferences: json!({}),
        repeats,
        first_weekday: json!(0),
        today: "2026-11-27".to_string(),
        now_iso: "2026-11-27".to_string(),
        now_minute: 19 * 60,
    }
}

fn clock() -> SheetClock {
    clock_with(json!([]), json!([]))
}

fn locked(
    id: &str,
    title: &str,
    start: &str,
    duration: i64,
    days: &[i64],
    category: &str,
) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "locked",
        "category": category,
        "start": start,
        "duration_min": duration,
        "days": days,
    })
}

fn open_existing(block: Value, occurrence: Option<i64>, clock: &SheetClock) -> BlockDraft {
    let mut spec = json!({ "block": block });
    if let Some(day) = occurrence {
        spec["occurrence_day"] = json!(day);
    }
    BlockDraft::open(&spec, clock).expect("open existing")
}

fn open_new(
    clock: &SheetClock,
    day: i64,
    start: &str,
    category: Option<&str>,
    length: Option<i64>,
) -> BlockDraft {
    let mut spec = json!({
        "id": "fresh-id",
        "day": day,
        "start": start,
        "block": Value::Null,
    });
    if let Some(category) = category {
        spec["category"] = json!(category);
    }
    if let Some(length) = length {
        spec["length"] = json!(length);
    }
    BlockDraft::open(&spec, clock).expect("open new")
}

fn form_of(draft: &BlockDraft, clock: &SheetClock) -> Value {
    draft.form(clock).expect("form")
}

fn text<'a>(value: &'a Value, key: &str) -> &'a str {
    value[key]
        .as_str()
        .unwrap_or_else(|| panic!("{key} is not text"))
}

fn on_days(form: &Value) -> Vec<i64> {
    form["days"]
        .as_array()
        .expect("days")
        .iter()
        .filter(|day| day["on"] == json!(true))
        .map(|day| day["value"].as_i64().expect("day"))
        .collect()
}

fn guitar_repeat(start: &str) -> Value {
    locked("weekly-guitar", "Guitar", start, 60, &[4], "extra")
}

fn open_guitar(week_start: &str, repeat_start: &str) -> (BlockDraft, SheetClock) {
    let clock = clock_with(json!([]), json!([guitar_repeat(repeat_start)]));
    let draft = open_existing(
        locked("weekly-guitar", "Guitar", week_start, 60, &[4], "extra"),
        None,
        &clock,
    );
    (draft, clock)
}

#[test]
fn deleting_a_plain_fixed_time_has_a_red_delete() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport"),
        None,
        &clock,
    );
    let question = draft.delete_question(&clock).expect("delete");
    assert_eq!(text(&question, "title"), "Delete fixed time");
    assert_eq!(question["answers"][1]["kind"], "danger");
}

#[test]
fn a_series_says_changes_apply_to_every_selected_day() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1, 3], "sport"),
        None,
        &clock,
    );
    let form = form_of(&draft, &clock);
    assert_eq!(
        text(&form, "seriesNote"),
        "Changes apply to every selected day in this series."
    );
}

#[test]
fn a_one_day_block_does_not_say_changes_apply_to_every_selected_day() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport"),
        None,
        &clock,
    );
    let form = form_of(&draft, &clock);
    assert_eq!(text(&form, "seriesNote"), "");
}

#[test]
fn a_new_fixed_time_says_to_pick_every_day() {
    let clock = clock();
    let draft = open_new(&clock, 0, "16:00", None, None);
    let form = form_of(&draft, &clock);
    assert_eq!(text(&form, "repeatNote"), "Pick every day it happens.");
}

#[test]
fn the_apply_to_row_is_hidden_for_a_block_that_does_not_repeat() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport"),
        Some(1),
        &clock,
    );
    let form = form_of(&draft, &clock);
    assert_eq!(form["showScope"], json!(false));
}

#[test]
fn a_start_moved_late_ends_at_the_end_of_the_day() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "17:00", Some("extra"), None);
    draft.set("start", &json!("23:30")).expect("start");
    let form = form_of(&draft, &clock);
    assert_eq!(form["end"], json!(24 * 60));
    assert_eq!(
        text(&form, "durationLine"),
        "End moved to the end of the day (24:00). It's now 30 min, not 1 h."
    );
}

#[test]
fn an_end_set_by_hand_stays_when_the_start_moves() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "15:00", Some("extra"), None);
    draft.set("end", &json!(20 * 60)).expect("end");
    draft.set("start", &json!("16:00")).expect("start");
    let form = form_of(&draft, &clock);
    assert_eq!(form["end"], json!(20 * 60));
    assert_eq!(text(&form, "durationLine"), "4 h");
}

#[test]
fn a_block_ending_at_the_end_of_the_day_reopens_at_the_end() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "23:00", 60, &[1], "sport"),
        None,
        &clock,
    );
    let form = form_of(&draft, &clock);
    assert_eq!(form["end"], json!(24 * 60));
    assert_eq!(text(&form, "durationLine"), "1 h");
}

#[test]
fn the_missed_switch_is_offered_for_one_day_of_a_block() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1, 3], "sport"),
        Some(1),
        &clock,
    );
    let form = form_of(&draft, &clock);
    assert_eq!(form["showMissed"], json!(true));
    assert_eq!(text(&form, "missedLabel"), "I missed it on Tuesday");
}

#[test]
fn unticking_i_missed_it_removes_the_day() {
    let clock = clock();
    let mut block = locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport");
    block["missed_days"] = json!([1]);
    let mut draft = open_existing(block, Some(1), &clock);
    draft.set("missed", &json!(false)).expect("missed");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let missed = made["missed_days"].as_array().expect("missed days");
    assert!(missed.iter().all(|day| day != &json!(1)));
}

#[test]
fn an_edit_builds_the_repeat_from_the_repeat_not_the_week_copy() {
    let (mut draft, clock) = open_guitar("18:00", "17:00");
    draft.set("category", &json!("sport")).expect("category");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let plan = draft.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "ask");
    assert_eq!(plan["changed"], json!(["category"]));
    assert_eq!(plan["repeat"]["start"], "17:00");
    assert_eq!(plan["repeat"]["category"], "sport");
}

#[test]
fn only_until_changed_is_later() {
    let (mut draft, clock) = open_guitar("17:00", "17:00");
    draft.set("until", &json!("2027-12-01")).expect("until");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let plan = draft.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "later");
    assert_eq!(plan["changed"], json!(["until"]));
    assert_eq!(plan["repeat"]["start"], "17:00");
    assert_eq!(plan["repeat"]["until"], "2027-12-01");
}

#[test]
fn a_new_sheet_is_clean_until_the_title_changes() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "16:00", Some("extra"), None);
    assert!(!draft.dirty());
    draft.set("title", &json!("Piano")).expect("title");
    assert!(draft.dirty());
    let again = BlockDraft::from_value(&draft.to_value()).expect("state");
    assert!(again.dirty());
    assert_eq!(text(&form_of(&again, &clock), "title"), "Piano");
}

#[test]
fn an_untouched_sheet_adopts_the_new_weeks_days() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "16:00", Some("extra"), None);
    let mut next = clock;
    next.week_start = json!(NEXT_WEEK);
    draft.follow_week(&[json!(6)], &next).expect("follow");
    let form = form_of(&draft, &next);
    assert_eq!(on_days(&form), vec![6]);
    assert_eq!(text(&form, "movedNote"), "");
}

#[test]
fn a_drawn_day_turns_onto_the_same_weekday() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "16:00", Some("extra"), Some(60));
    let mut next = clock;
    next.week_start = json!(NEXT_WEEK);
    draft.follow_week(&[json!(6)], &next).expect("follow");
    let form = form_of(&draft, &next);
    assert_eq!(on_days(&form), vec![1]);
    assert_eq!(
        text(&form, "movedNote"),
        "Monday 23 isn't in this week any more, so it moved to Monday 30."
    );
}

#[test]
fn an_end_before_the_start_names_the_start() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "15:00", Some("extra"), None);
    draft.set("end", &json!(15 * 60)).expect("end");
    let form = form_of(&draft, &clock);
    assert_eq!(form["durationIsProblem"], json!(true));
    assert_eq!(
        text(&form, "durationLine"),
        "End needs to be later than Start (15:00)."
    );
}

#[test]
fn the_steps_refuse_a_blank_title_and_then_finish() {
    let clock = clock();
    let mut draft = open_new(&clock, 1, "16:00", Some("extra"), None);
    draft.set("title", &json!("   ")).expect("title");
    assert!(!draft.advance(&clock).expect("advance"));
    assert_eq!(
        text(&form_of(&draft, &clock), "titleProblem"),
        "Give it a title."
    );
    draft.set("title", &json!("Piano")).expect("title");
    assert!(!draft.advance(&clock).expect("when"));
    assert_eq!(form_of(&draft, &clock)["step"], json!(1));
    draft.toggle_day(&json!(1)).expect("day");
    assert!(!draft.advance(&clock).expect("empty days"));
    assert_eq!(
        text(&form_of(&draft, &clock), "daysProblem"),
        "Tick at least one day."
    );
    draft.toggle_day(&json!(1)).expect("day back");
    assert!(!draft.advance(&clock).expect("category"));
    assert_eq!(text(&form_of(&draft, &clock), "primary"), "Add");
    assert!(draft.advance(&clock).expect("done"));
}

#[test]
fn scope_keeps_the_series_days_and_comes_back() {
    let clock = clock();
    let mut draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1, 3], "sport"),
        Some(1),
        &clock,
    );
    assert_eq!(on_days(&form_of(&draft, &clock)), vec![1]);
    draft.set("scope", &json!("series")).expect("series");
    assert_eq!(on_days(&form_of(&draft, &clock)), vec![1, 3]);
    draft.set("scope", &json!("occurrence")).expect("day");
    assert_eq!(on_days(&form_of(&draft, &clock)), vec![1]);
}

#[test]
fn an_empty_stored_series_list_falls_back_to_the_blocks_days() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1, 3], "sport"),
        Some(1),
        &clock,
    );
    let mut state = draft.to_value();
    state["series_days"] = json!([]);
    let mut draft = BlockDraft::from_value(&state).expect("state");
    draft.set("scope", &json!("series")).expect("series");
    assert_eq!(on_days(&form_of(&draft, &clock)), vec![1, 3]);
}

#[test]
fn a_neighbor_at_the_same_time_is_allowed_to_overlap() {
    let neighbor = locked("piano", "Piano", "16:00", 60, &[1], "extra");
    let clock = clock_with(json!([neighbor]), json!([]));
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport"),
        None,
        &clock,
    );
    assert_eq!(
        text(&form_of(&draft, &clock), "clash"),
        "Piano is at that time too. Both will stay visible and overlap slightly."
    );
}

#[test]
fn a_candidate_strips_the_title_and_refuses_homework() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "16:00", Some("extra"), None);
    draft.set("title", &json!("  Piano  ")).expect("title");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    assert_eq!(made["title"], "Piano");
    assert_eq!(made["kind"], "locked");

    let mut homework = locked("hw", "Essay", "16:00", 60, &[0], "assignments");
    homework["kind"] = json!("flex");
    let mut draft = open_existing(homework, None, &clock);
    assert!(draft.candidate(&clock).expect("candidate").is_none());
    assert_eq!(
        text(&form_of(&draft, &clock), "error"),
        "Use the homework editor for homework sessions."
    );
}

#[test]
fn ticking_a_removed_day_puts_it_back_on_the_block() {
    let clock = clock();
    let mut block = locked(
        "weekly-soccer",
        "Soccer practice",
        "16:00",
        90,
        &[1, 3],
        "sport",
    );
    block["removed_days"] = json!([1]);
    let mut draft = open_existing(block, None, &clock);
    assert_eq!(on_days(&form_of(&draft, &clock)), vec![3]);
    draft.toggle_day(&json!(1)).expect("day");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    assert!(made.get("removed_days").is_none());
    assert_eq!(made["days"], json!([1, 3]));
}

#[test]
fn save_plan_names_each_kind_of_change() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "18:30", Some("extra"), None);
    draft.set("title", &json!("Piano")).expect("title");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let plan = draft.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "plain");

    draft.set("repeat", &json!(true)).expect("repeat");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let plan = draft.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "add");
    assert_eq!(plan["repeat"]["id"], "weekly-fresh-id");
    assert_eq!(plan["repeat"]["start"], "18:30");

    let (mut weekly, clock) = open_guitar("17:00", "17:00");
    weekly.set("repeat", &json!(false)).expect("repeat");
    let made = weekly.candidate(&clock).expect("candidate").expect("made");
    let plan = weekly.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "stop");

    let mut one_off = open_existing(
        locked("guitar-1", "Guitar", "17:00", 60, &[4], "extra"),
        None,
        &clock,
    );
    one_off.set("repeat", &json!(true)).expect("repeat");
    let made = one_off.candidate(&clock).expect("candidate").expect("made");
    let plan = one_off.save_plan(&made, &clock, "fresh-id").expect("plan");
    assert_eq!(text(&plan, "kind"), "make");
    assert_eq!(plan["repeat"]["id"], "weekly-guitar-1");
}

#[test]
fn stopping_a_weekly_time_drops_the_prefix_and_the_end() {
    let (mut draft, clock) = open_guitar("17:00", "17:00");
    let made = draft.candidate(&clock).expect("candidate").expect("made");
    let alone = draft.stopped_one_off(&made).expect("stop").expect("block");
    assert_eq!(alone["id"], "guitar");
    assert!(alone.get("until").is_none());
}

#[test]
fn delete_and_save_questions_keep_their_sentences() {
    let clock = clock();
    let draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1, 3], "sport"),
        None,
        &clock,
    );
    let question = draft.delete_question(&clock).expect("delete");
    assert_eq!(
        text(&question, "body"),
        "Delete Soccer practice on every Tue and Thu this week? You can undo this."
    );
    assert!(question.get("cards").is_none());

    let mut block = locked(
        "weekly-soccer",
        "Soccer practice",
        "16:00",
        90,
        &[1, 3],
        "sport",
    );
    block["days"] = json!([1, 3]);
    let draft = open_existing(block, Some(1), &clock);
    let question = draft.delete_question(&clock).expect("delete standing");
    assert_eq!(text(&question, "title"), "Delete Soccer practice?");
    assert_eq!(text(&question, "body"), "");
    assert_eq!(question["cards"][0]["title"], "Just Tuesday 24 Nov");
    assert_eq!(
        question["cards"][0]["line"],
        "Other days this week and other weeks keep Soccer practice. You can undo this."
    );
    assert_eq!(question["cards"][1]["title"], "This week only");
    assert_eq!(
        question["cards"][2]["line"],
        "Earlier weeks keep Soccer practice. Undo also takes back anything changed after it."
    );

    let (mut draft, _) = open_guitar("17:00", "17:00");
    draft
        .set("title", &json!("  Guitar lesson  "))
        .expect("title");
    let question = draft.save_question().expect("save");
    assert_eq!(text(&question, "title"), "Change Guitar lesson?");
    assert_eq!(question["confirm"], "Save");
    assert_eq!(
        question["cards"][0]["line"],
        "Other weeks keep Guitar lesson as it was."
    );
}

#[test]
fn recover_missed_is_only_for_a_day_that_was_not_missed() {
    let clock = clock();
    let mut missed = locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport");
    missed["missed_days"] = json!([1]);
    let mut draft = open_existing(missed, Some(1), &clock);
    assert!(!draft.recover_missed().expect("already"));
    draft.set("missed", &json!(false)).expect("clear");
    assert!(!draft.recover_missed().expect("unticked"));

    let mut draft = open_existing(
        locked("soccer", "Soccer practice", "16:00", 90, &[1], "sport"),
        Some(1),
        &clock,
    );
    assert!(!draft.recover_missed().expect("not ticked"));
    draft.set("missed", &json!(true)).expect("tick");
    assert!(draft.recover_missed().expect("new miss"));
}

#[test]
fn a_start_with_no_category_guesses_one_and_a_hand_picked_one_stays() {
    let clock = clock();
    let meals = open_new(&clock, 0, "07:30", None, None);
    assert_eq!(text(&form_of(&meals, &clock), "category"), "meals");
    let class_time = open_new(&clock, 0, "09:00", None, None);
    assert_eq!(text(&form_of(&class_time, &clock), "category"), "class");
    let evening = open_new(&clock, 0, "21:00", None, None);
    assert_eq!(text(&form_of(&evening, &clock), "category"), "extra");

    let mut picked = open_new(&clock, 0, "09:00", Some("extra"), None);
    picked.set("start", &json!("07:30")).expect("start");
    assert_eq!(text(&form_of(&picked, &clock), "category"), "extra");
}

#[test]
fn a_class_preset_uses_school_hours_and_a_drawn_length_wins() {
    let clock = clock();
    let class_sheet = open_new(&clock, 0, "16:00", Some("class"), None);
    let form = form_of(&class_sheet, &clock);
    assert_eq!(text(&form, "title"), "School");
    assert_eq!(text(&form, "start"), "08:00");
    assert_eq!(on_days(&form), vec![0, 1, 2, 3, 4]);
    assert_eq!(text(&form, "durationLine"), "6 h 30 min");

    let drawn = open_new(&clock, 3, "10:15", Some("class"), Some(0));
    let form = form_of(&drawn, &clock);
    assert_eq!(text(&form, "start"), "10:15");
    assert_eq!(on_days(&form), vec![3]);
    assert_eq!(form["end"], json!(10 * 60 + 15));
}

#[test]
fn moving_the_start_keeps_a_one_hour_block_one_hour() {
    let clock = clock();
    let mut draft = open_new(&clock, 0, "17:00", Some("extra"), None);
    draft.set("start", &json!("18:00")).expect("start");
    let form = form_of(&draft, &clock);
    assert_eq!(form["end"], json!(19 * 60));
    assert_eq!(
        text(&form, "durationLine"),
        "End moved to 19:00 to keep it 1 h."
    );
}

#[test]
fn a_grid_reopen_does_not_say_the_end_moved() {
    let clock = clock();
    let draft = open_new(&clock, 2, "23:30", Some("extra"), Some(60));
    let form = form_of(&draft, &clock);
    assert_eq!(form["end"], json!(24 * 60));
    assert_eq!(text(&form, "durationLine"), "30 min");
    assert_eq!(text(&form, "movedNote"), "");
}

#[test]
fn an_invalid_preview_row_starts_unticked_and_stays_unticked() {
    let existing = json!([]);
    let mut draft = PreviewDraft::open(&json!({
        "title": "Paste",
        "summary": "Two copies",
        "confirm": "Save preview",
        "rows": [{
            "checked": true,
            "invalid": "No unplanned time remains for this homework.",
            "fixed": false,
            "day": 0,
            "block": {"title": "Essay", "duration_min": 30, "days": [0]},
        }],
    }))
    .expect("open");
    assert!(!draft.can_save());
    draft.check(0, true).expect("check");
    assert!(!draft.rows()[0]["checked"].as_bool().expect("checked"));
    let form = draft.form(&existing).expect("form");
    assert_eq!(form["canSave"], json!(false));
    assert_eq!(text(&form, "whyOff"), NONE_CHOSEN);
    assert_eq!(
        form["rows"][0]["detail"],
        "No unplanned time remains for this homework."
    );
}

#[test]
fn a_preview_row_beside_a_saved_block_names_that_block() {
    let existing = json!([locked("piano", "Piano", "16:00", 60, &[0], "extra")]);
    let mut draft = PreviewDraft::open(&json!({
        "title": "Paste",
        "summary": "One copy",
        "confirm": "Save preview",
        "rows": [{
            "checked": true,
            "invalid": "",
            "fixed": true,
            "day": 0,
            "week_start": WEEK,
            "block": {
                "title": "Copied",
                "start": "16:00",
                "duration_min": 60,
                "days": [0],
            },
        }],
    }))
    .expect("open");
    let form = draft.form(&existing).expect("form");
    assert_eq!(form["rows"][0]["detail"], beside_words("Piano"));
    assert_eq!(form["canSave"], json!(true));
    draft.set_start(0, "18:00", &existing).expect("start");
    let form = draft.form(&existing).expect("form");
    assert_eq!(form["rows"][0]["detail"], "1 h · Only this week");
    assert_eq!(draft.rows()[0]["checked"], json!(true));
    draft.set_day(0, 2, &existing).expect("day");
    assert_eq!(draft.rows()[0]["day"], json!(2));
    assert_eq!(draft.rows()[0]["block"]["days"], json!([2]));
    draft
        .set_duration(0, &json!(30), &existing)
        .expect("length");
    assert_eq!(draft.rows()[0]["block"]["duration_min"], json!(30));
}

#[test]
fn a_missing_preview_start_is_written_back_as_midnight() {
    let existing = json!([]);
    let mut draft = PreviewDraft::open(&json!({
        "title": "Paste",
        "summary": "One copy",
        "confirm": "Save preview",
        "rows": [{
            "checked": true,
            "invalid": "",
            "fixed": true,
            "day": 0,
            "block": {"title": "Copied", "duration_min": 60, "days": [0]},
        }],
    }))
    .expect("open");
    let form = draft.form(&existing).expect("form");
    assert_eq!(form["rows"][0]["start"], "00:00");
    assert_eq!(draft.rows()[0]["block"]["start"], "00:00");
    let values: Vec<&str> = form["rows"][0]["durationOptions"]
        .as_array()
        .expect("lengths")
        .iter()
        .map(|item| item["label"].as_str().expect("label"))
        .collect();
    assert_eq!(values, vec!["15", "30", "45", "60"]);
}
