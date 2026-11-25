//! The session's block and repeat edit decisions (P4 slice 4B): the rules of controller.py's
//! `add_block`, `hand_move`, `delete_block`, `setup_repeats` and `change_repeats`, with the words a
//! student reads. Expected values come from those rules and the desktop tests they keep green.

use flexweek_app::session::block_edits::{
    BlockDeleteInput, BlockEditInput, HandMoveInput, RepeatEditInput, apply_block_edit,
    apply_hand_move, delete_block, repeat_edit, setup_standing,
};
use serde_json::{Value, json};

const WEEK: &str = "2026-09-21";
const TODAY: &str = "2026-09-23";

fn school(days: Vec<i64>, start: &str) -> Value {
    json!({
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": days,
        "start": start,
        "category": "class",
    })
}

fn activity(id: &str, days: Vec<i64>) -> Value {
    json!({
        "id": id,
        "title": "Job",
        "kind": "locked",
        "duration_min": 60,
        "days": days,
        "start": "17:00",
        "category": "extra",
    })
}

fn edit_input<'a>(blocks: &'a Value, block: &'a Value, scope: &'a str, day: Option<i64>) -> BlockEditInput<'a> {
    BlockEditInput {
        blocks,
        block,
        scope,
        day,
        new_id: "made-1",
    }
}

fn days_of(block: &Value) -> Vec<i64> {
    block["days"]
        .as_array()
        .map(|days| days.iter().filter_map(Value::as_i64).collect())
        .unwrap_or_default()
}

/// The check writes a block as pydantic's `TimeBlock` dump does: the model's own defaults
/// (`backend/models.py`: priority 3, energy medium, no earliest/latest/course) travel with it.
fn checked_school(days: Vec<i64>, start: &str) -> Value {
    let mut block = school(days, start);
    block["priority"] = json!(3);
    block["energy"] = json!("medium");
    block["earliest"] = Value::Null;
    block["latest"] = Value::Null;
    block["course"] = Value::Null;
    block
}

#[test]
fn adding_a_new_block_appends_it_with_adding_words() {
    let blocks = json!([]);
    let block = school(vec![0, 1, 2, 3, 4], "08:00");
    let edit = apply_block_edit(&edit_input(&blocks, &block, "series", None)).unwrap();
    assert_eq!(edit.blocks, vec![checked_school(vec![0, 1, 2, 3, 4], "08:00")]);
    assert_eq!(edit.label, "adding School");
    assert_eq!(edit.block_id, "school");
}

#[test]
fn editing_a_block_replaces_it_with_editing_words() {
    let blocks = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let block = school(vec![0, 1, 2, 3, 4], "09:00");
    let edit = apply_block_edit(&edit_input(&blocks, &block, "series", None)).unwrap();
    assert_eq!(edit.blocks, vec![checked_school(vec![0, 1, 2, 3, 4], "09:00")]);
    assert_eq!(edit.label, "editing School");
}

#[test]
fn editing_one_occurrence_leaves_the_rest_of_the_series() {
    let blocks = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let block = school(vec![2], "09:00");
    let edit = apply_block_edit(&edit_input(&blocks, &block, "occurrence", Some(2))).unwrap();
    assert_eq!(edit.blocks.len(), 2);
    let by_days: std::collections::BTreeMap<Vec<i64>, &Value> = edit
        .blocks
        .iter()
        .map(|item| (days_of(item), item))
        .collect();
    assert_eq!(by_days[&vec![0, 1, 3, 4]]["start"], json!("08:00"));
    assert_eq!(by_days[&vec![0, 1, 3, 4]]["id"], json!("school"));
    assert_eq!(by_days[&vec![2]]["start"], json!("09:00"));
    assert_eq!(by_days[&vec![2]]["id"], json!("made-1"));
    assert_eq!(edit.label, "editing School");
}

#[test]
fn a_block_that_fails_the_check_is_refused() {
    let blocks = json!([]);
    let block = json!({"id": "school"});
    assert!(apply_block_edit(&edit_input(&blocks, &block, "series", None)).is_err());
}

#[test]
fn a_moved_block_without_a_start_is_placed() {
    let before = json!([{
        "id": "s1", "title": "Essay", "kind": "flexible", "duration_min": 60,
        "days": [0], "assignment_id": "a1", "category": "assignments",
    }]);
    let moved = json!([{
        "id": "s1", "title": "Essay", "kind": "flexible", "duration_min": 60,
        "days": [0], "start": "10:00", "assignment_id": "a1", "category": "assignments",
    }]);
    let answer = json!({"moved": true, "blocks": moved, "block_id": "s1", "beside": Value::Null});
    let input = HandMoveInput {
        blocks: &before,
        answer: &answer,
        block_id: "s1",
    };
    let done = apply_hand_move(&input).unwrap();
    assert!(done.moved);
    assert_eq!(done.blocks, vec![moved[0].clone()]);
    assert_eq!(done.label.as_deref(), Some("placing Essay"));
    assert_eq!(done.block_id.as_deref(), Some("s1"));
    assert_eq!(done.problem, None);
}

#[test]
fn a_moved_series_says_it_moved_on_one_day() {
    let before = json!([school(vec![0, 1, 2], "08:00")]);
    let answer = json!({
        "moved": true,
        "blocks": [school(vec![1, 2], "08:00")],
        "block_id": "made-2",
        "beside": Value::Null,
    });
    let input = HandMoveInput {
        blocks: &before,
        answer: &answer,
        block_id: "school",
    };
    let done = apply_hand_move(&input).unwrap();
    assert_eq!(done.label.as_deref(), Some("moving School on one day"));
    assert_eq!(done.block_id.as_deref(), Some("made-2"));
}

#[test]
fn a_refused_hand_move_says_why_and_keeps_the_week() {
    let before = json!([school(vec![0, 1, 2], "08:00")]);
    let answer = json!({"moved": false, "problem": "That hour is past."});
    let input = HandMoveInput {
        blocks: &before,
        answer: &answer,
        block_id: "school",
    };
    let done = apply_hand_move(&input).unwrap();
    assert!(!done.moved);
    assert_eq!(done.problem.as_deref(), Some("That hour is past."));
    assert_eq!(done.blocks, vec![school(vec![0, 1, 2], "08:00")]);
    assert_eq!(done.label, None);
}

#[test]
fn deleting_homework_takes_the_whole_block() {
    let session = json!({
        "id": "s1", "title": "Essay", "kind": "flexible", "duration_min": 60,
        "days": [0], "start": "10:00", "assignment_id": "a1", "category": "assignments",
    });
    let blocks = json!([session]);
    let repeats = json!([]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "s1",
        scope: "occurrence",
        day: Some(0),
        every_week: false,
        selected_id: None,
        label: None,
    };
    let gone = delete_block(&input).unwrap().expect("the block is there");
    assert!(gone.blocks.is_empty());
    assert_eq!(gone.label, "deleting Essay");
    assert!(!gone.clear_selection);
}

#[test]
fn deleting_a_school_seam_takes_every_piece_and_marks_it_missed_this_week() {
    let blocks = json!([
        school(vec![0, 1, 2, 3, 4], "08:00"),
        {
            "id": "school@20260921-1", "title": "School", "kind": "locked", "duration_min": 390,
            "days": [0, 1], "start": "08:00", "category": "class",
        },
    ]);
    let repeats = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "school",
        scope: "series",
        day: None,
        every_week: false,
        selected_id: Some("school"),
        label: None,
    };
    let gone = delete_block(&input).unwrap().expect("the block is there");
    assert_eq!(gone.blocks.len(), 2);
    for item in &gone.blocks {
        assert_eq!(
            item["missed_days"],
            item["days"],
            "this week keeps it missed on every day"
        );
    }
    assert_eq!(gone.repeats, vec![school(vec![0, 1, 2, 3, 4], "08:00")]);
    assert!(gone.clear_selection);
    assert_eq!(gone.label, "deleting School");
}

#[test]
fn deleting_a_standing_block_every_week_prunes_the_repeats() {
    let blocks = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let repeats = json!([
        school(vec![0, 1, 2, 3, 4], "08:00"),
        activity("activity-1", vec![1]),
    ]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "school",
        scope: "series",
        day: None,
        every_week: true,
        selected_id: None,
        label: Some("clearing the week"),
    };
    let gone = delete_block(&input).unwrap().expect("the block is there");
    assert!(gone.blocks.is_empty());
    assert_eq!(gone.repeats, vec![activity("activity-1", vec![1])]);
    assert_eq!(gone.label, "clearing the week");
}

#[test]
fn deleting_one_occurrence_strips_that_day_but_keeps_the_series() {
    let blocks = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let repeats = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "school",
        scope: "occurrence",
        day: Some(2),
        every_week: false,
        selected_id: None,
        label: None,
    };
    let gone = delete_block(&input).unwrap().expect("the block is there");
    // The grid always writes the days it keeps beside the miss list (`grid.rs`).
    let mut stripped = school(vec![0, 1, 3, 4], "08:00");
    stripped["missed_days"] = json!([]);
    assert_eq!(gone.blocks, vec![stripped]);
    assert_eq!(gone.repeats, vec![school(vec![0, 1, 2, 3, 4], "08:00")]);
}

#[test]
fn deleting_a_missing_block_changes_nothing() {
    let blocks = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let repeats = json!([]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "nope",
        scope: "series",
        day: None,
        every_week: false,
        selected_id: None,
        label: None,
    };
    assert_eq!(delete_block(&input).unwrap(), None);
}

#[allow(clippy::too_many_arguments)]
#[test]
fn a_replace_change_rewrites_the_week_and_stamps_replace() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let after = json!([school(vec![0, 1, 2, 3, 4], "08:30")]);
    let input = repeat_input(&week, &before, &after, &before, None, WEEK, "replace", TODAY);
    let edit = repeat_edit(&input).unwrap().expect("the start moved");
    assert!(!edit.leaves_week);
    assert_eq!(edit.blocks, vec![school(vec![0, 1, 2, 3, 4], "08:30")]);
    assert_eq!(edit.repeats, vec![after[0].clone()]);
    assert_eq!(edit.stamped[0]["edited"], json!("replace"));
    assert_eq!(edit.stamped[0].get("today"), None);
}

#[test]
fn a_stop_takes_the_repeat_off_the_week() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00"), activity("activity-1", vec![1])]);
    let before = week.clone();
    let after = json!([activity("activity-1", vec![1])]);
    let input = repeat_input(&week, &before, &after, &before, None, WEEK, "replace", TODAY);
    let edit = repeat_edit(&input).unwrap().expect("school stops");
    assert!(!edit.leaves_week);
    assert_eq!(edit.stamped[0]["stop"], json!(true));
    assert_eq!(edit.blocks, vec![activity("activity-1", vec![1])]);
    assert_eq!(edit.repeats, vec![activity("activity-1", vec![1])]);
}

#[test]
fn a_replaced_week_shown_from_wednesday_turns_the_days() {
    let shown = vec![5, 6, 0, 1, 2];
    let week = json!([school(shown, "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let after = json!([school(vec![0, 1, 2, 3, 4], "08:30")]);
    let input = repeat_input(&week, &before, &after, &before, None, "2026-09-23", "replace", TODAY);
    let edit = repeat_edit(&input).unwrap().expect("the start moved");
    assert!(!edit.leaves_week);
    // Monday days come back to the week starting Wednesday, earliest first.
    assert_eq!(edit.blocks, vec![school(vec![0, 1, 2, 5, 6], "08:30")]);
    assert_eq!(edit.repeats, vec![after[0].clone()]);
}

#[test]
fn a_from_today_change_applies_on_a_later_week() {
    let shown = vec![5, 6, 0, 1, 2];
    let week = json!([school(shown, "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let after = json!([school(vec![0, 1, 2, 3, 4], "08:30")]);
    let mut input = repeat_input(
        &week,
        &before,
        &after,
        &before,
        None,
        "2026-09-30",
        "from_today",
        TODAY,
    );
    input.first_weekday = 3;
    let edit = repeat_edit(&input).unwrap().expect("the start moved");
    assert!(!edit.leaves_week);
    assert_eq!(edit.stamped[0]["edited"], json!("from_today"));
    assert_eq!(edit.stamped[0]["today"], json!(TODAY));
    assert_eq!(edit.stamped[0]["first_weekday"], json!(3));
    assert_eq!(edit.blocks, vec![school(vec![0, 1, 2, 5, 6], "08:30")]);
    assert_eq!(edit.repeats, vec![after[0].clone()]);
}

#[test]
fn deleting_the_last_occurrence_of_a_standing_block_marks_it_missed() {
    let blocks = json!([school(vec![2], "08:00")]);
    let repeats = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let input = BlockDeleteInput {
        blocks: &blocks,
        repeats: &repeats,
        block_id: "school",
        scope: "occurrence",
        day: Some(2),
        every_week: false,
        selected_id: None,
        label: None,
    };
    let gone = delete_block(&input).unwrap().expect("the block is there");
    let mut missed = school(vec![2], "08:00");
    missed["missed_days"] = json!([2]);
    assert_eq!(gone.blocks, vec![missed]);
    assert_eq!(gone.repeats, vec![school(vec![0, 1, 2, 3, 4], "08:00")]);
}

#[allow(clippy::too_many_arguments)]
fn repeat_input<'a>(
    blocks: &'a Value,
    repeats: &'a Value,
    after: &'a Value,
    saved: &'a Value,
    send: Option<&'a Value>,
    week_start: &'a str,
    edited: &'a str,
    today: &'a str,
) -> RepeatEditInput<'a> {
    RepeatEditInput {
        blocks,
        repeats,
        after,
        saved_repeats: saved,
        send,
        week_start,
        edited,
        today,
        first_weekday: 0,
    }
}

#[test]
fn no_repeat_change_is_nothing_to_send() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let standing = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let input = repeat_input(&week, &standing, &standing, &standing, None, WEEK, "keep", TODAY);
    assert_eq!(repeat_edit(&input).unwrap(), None);
}

#[test]
fn a_kept_change_rewrites_the_open_week_and_sends_it_unstamped() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let mut late = school(vec![0, 1, 2, 3, 4], "08:30");
    late["duration_min"] = json!(360);
    let after = json!([late]);
    let input = repeat_input(&week, &before, &after, &before, None, WEEK, "keep", TODAY);
    let edit = repeat_edit(&input).unwrap().expect("the start moved");
    assert!(!edit.leaves_week);
    assert_eq!(edit.repeats, vec![after[0].clone()]);
    assert_eq!(edit.preview.len(), 1);
    assert_eq!(edit.preview[0]["id"], json!("school"));
    assert!(
        edit.preview[0].get("edited").is_none(),
        "keep stays as the form built it"
    );
    assert_eq!(edit.stamped, edit.preview);
    let changed: Vec<&Value> = edit
        .blocks
        .iter()
        .filter(|item| item["id"] == json!("school"))
        .collect();
    assert_eq!(changed.len(), 1);
    assert_eq!(changed[0]["start"], json!("08:30"));
    assert_eq!(changed[0]["duration_min"], json!(360));
}

#[test]
fn a_rebased_change_carries_both_intents() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:30")]);
    let saved = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let mut after = school(vec![0, 1, 3, 4], "08:30");
    after["duration_min"] = json!(360);
    let after = json!([after]);
    let send = json!([{"id": "school", "scope": "from", "from_date": WEEK,
        "set": {"start": "08:30"}, "add_days": [], "remove_days": [], "stop": false}]);
    let input = repeat_input(&week, &before, &after, &saved, Some(&send), WEEK, "keep", TODAY);
    let edit = repeat_edit(&input).unwrap().expect("a day went");
    assert_eq!(edit.stamped.len(), 1, "one intent carries both changes");
    assert_eq!(edit.stamped[0]["set"]["start"], json!("08:30"));
    assert!(
        edit.stamped[0]["remove_days"]
            .as_array()
            .is_some_and(|days| days.contains(&json!(2))),
        "Wednesday goes too"
    );
}

#[test]
fn a_from_today_change_leaves_an_earlier_week_alone() {
    let week = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let before = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let after = json!([school(vec![0, 1, 2, 3, 4], "08:30")]);
    let input = repeat_input(
        &week,
        &before,
        &after,
        &before,
        None,
        "2026-09-14",
        "from_today",
        TODAY,
    );
    let edit = repeat_edit(&input).unwrap().expect("the start moved");
    assert!(edit.leaves_week);
    assert_eq!(edit.blocks, vec![school(vec![0, 1, 2, 3, 4], "08:00")]);
    assert_eq!(edit.repeats, vec![school(vec![0, 1, 2, 3, 4], "08:00")]);
    assert_eq!(edit.stamped[0]["edited"], json!("from_today"));
    assert_eq!(edit.stamped[0]["today"], json!(TODAY));
    assert_eq!(edit.preview[0].get("edited"), None);
}

#[test]
fn setup_run_again_keeps_a_weekly_time() {
    let setup = json!([school(vec![0, 1, 2, 3, 4], "08:00")]);
    let repeats = json!([
        school(vec![0, 1, 2, 3, 4], "07:00"),
        {"id": "weekly-1", "title": "Gym", "kind": "locked", "duration_min": 60,
         "days": [1, 3], "start": "18:00", "category": "exercise"},
        activity("activity-9", vec![5]),
    ]);
    let standing = setup_standing(&setup, &repeats).unwrap();
    let ids: Vec<&str> = standing
        .iter()
        .filter_map(|item| item["id"].as_str())
        .collect();
    assert_eq!(ids, vec!["school", "weekly-1"]);
    assert_eq!(standing[0]["start"], json!("08:00"));
    assert_eq!(standing[1]["days"], json!([1, 3]));
}

#[test]
fn setup_refuses_a_block_the_check_refuses() {
    let setup = json!([{"id": "school"}]);
    let repeats = json!([]);
    assert!(setup_standing(&setup, &repeats).is_err());
}
