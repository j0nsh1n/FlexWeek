//! The session's restore point, export and import decisions (P4 group 9): the rules of controller.py's
//! restore, export, import and `import_week_file` methods, with the words a student reads.

use flexweek_app::session::transfer::{
    ImportContext, ImportDecision, create_restore_key, import_key, import_week_decision,
    restore_apply_guard, restore_key, restore_points_after_create, transfer_blocked,
};
use serde_json::{Value, json};

const WEEK: &str = "2026-09-21";
const WEEK_WORDS: &str = "the week of 21 Sep";

fn locked(id: &str, day: i64) -> Value {
    json!({"id": id, "kind": "locked", "days": [day], "start": "16:00", "duration_min": 60})
}

fn context<'a>(
    blocks: &'a Value,
    assignments: &'a Value,
    replace: Option<bool>,
) -> ImportContext<'a> {
    ImportContext {
        week_start: WEEK,
        week_words: WEEK_WORDS,
        target_words: "the week of 28 Sep",
        blocks,
        assignments,
        replace,
    }
}

fn week_file(blocks: Value) -> Value {
    json!({"format": "flexweek-week", "week_start": WEEK, "day": null, "blocks": blocks,
           "assignments": [], "error": null})
}

fn day_file(blocks: Value, day: i64) -> Value {
    json!({"format": "flexweek-day", "week_start": WEEK, "day": day, "blocks": blocks,
           "assignments": [], "error": null})
}

fn applied(decision: ImportDecision) -> (Vec<Value>, Vec<Value>) {
    match decision {
        ImportDecision::Apply { blocks, create } => (blocks, create),
        ImportDecision::Say(words) => panic!("expected an import, it said: {words}"),
    }
}

#[test]
fn another_weeks_file_is_refused_with_words_naming_that_week() {
    let mut file = week_file(json!([locked("a", 0)]));
    file["week_start"] = json!("2026-09-28");
    let none = json!([]);
    let said = import_week_decision(&file, &context(&none, &json!({}), None)).unwrap();
    assert_eq!(
        said,
        ImportDecision::Say(
            "Nothing imported: this file is for the week of 28 Sep. Go to that week, then import again."
                .into()
        )
    );
}

#[test]
fn a_file_the_reader_refused_says_its_own_words() {
    let file = json!({"error": "Empty file."});
    let none = json!([]);
    let said = import_week_decision(&file, &context(&none, &json!({}), None)).unwrap();
    assert_eq!(said, ImportDecision::Say("Empty file.".into()));
}

#[test]
fn a_day_file_merges_into_a_full_week_and_never_asks_for_replace() {
    let held = json!([locked("a", 0)]);
    let file = day_file(json!([locked("b", 2)]), 2);
    let decision = import_week_decision(&file, &context(&held, &json!({}), None)).unwrap();
    let (blocks, create) = applied(decision);
    let ids: Vec<&str> = blocks.iter().filter_map(|b| b["id"].as_str()).collect();
    assert_eq!(ids, ["a", "b"]);
    assert!(create.is_empty());
}

#[test]
fn a_week_file_over_a_week_with_blocks_asks_before_replacing() {
    let held = json!([locked("a", 0)]);
    let file = week_file(json!([locked("b", 1)]));
    let said = import_week_decision(&file, &context(&held, &json!({}), None)).unwrap();
    assert_eq!(
        said,
        ImportDecision::Say(
            "Nothing imported: it would replace everything in the week of 21 Sep. Import again and choose Replace week."
                .into()
        )
    );
}

#[test]
fn replace_swaps_the_week_and_merge_keeps_what_was_there() {
    let held = json!([locked("a", 0)]);
    let file = week_file(json!([locked("b", 1)]));
    let replaced = import_week_decision(&file, &context(&held, &json!({}), Some(true))).unwrap();
    let (blocks, _) = applied(replaced);
    assert_eq!(blocks.len(), 1);
    assert_eq!(blocks[0]["id"], "b");
    let merged = import_week_decision(&file, &context(&held, &json!({}), Some(false))).unwrap();
    let (blocks, _) = applied(merged);
    assert_eq!(blocks.len(), 2);
}

#[test]
fn a_week_file_into_an_empty_week_needs_no_confirmation() {
    let held = json!([]);
    let file = week_file(json!([locked("b", 1)]));
    let (blocks, _) =
        applied(import_week_decision(&file, &context(&held, &json!({}), None)).unwrap());
    assert_eq!(blocks.len(), 1);
}

#[test]
fn a_result_over_the_block_limit_says_so_and_changes_nothing() {
    let held: Vec<Value> = (0..100).map(|n| locked(&format!("e{n}"), 0)).collect();
    let held = Value::Array(held);
    let file = day_file(json!([locked("extra", 2)]), 2);
    let said = import_week_decision(&file, &context(&held, &json!({}), None)).unwrap();
    assert_eq!(
        said,
        ImportDecision::Say(
            "the week of 21 Sep would exceed 100 blocks. Uncheck an item or remove a block first."
                .into()
        )
    );
}

#[test]
fn a_merge_the_engine_refuses_is_said_with_nothing_was_imported() {
    let held = json!([{"id": "a", "kind": "flexible", "days": [0, 1], "duration_min": 60}]);
    let file = day_file(
        json!([{"id": "a", "kind": "flexible", "days": [2], "duration_min": 60}]),
        2,
    );
    let said = import_week_decision(&file, &context(&held, &json!({}), None)).unwrap();
    assert_eq!(
        said,
        ImportDecision::Say(
            "Day import cannot merge multi-day task a. Import the full week instead. Nothing was imported."
                .into()
        )
    );
}

#[test]
fn imported_homework_gets_its_own_id_at_revision_zero_and_its_blocks_follow() {
    let mut linked = locked("b", 1);
    linked["assignment_id"] = json!("hw");
    let mut file = week_file(json!([linked]));
    file["assignments"] = json!([{"id": "hw", "title": "Essay", "due": "2026-10-01"}]);
    let held = json!([]);
    let (blocks, create) =
        applied(import_week_decision(&file, &context(&held, &json!({}), None)).unwrap());
    assert_eq!(create.len(), 1);
    let new_id = create[0]["id"].as_str().unwrap();
    assert_ne!(new_id, "hw");
    assert_eq!(create[0]["title"], "Essay");
    assert_eq!(create[0]["revision"], 0);
    assert_eq!(blocks[0]["assignment_id"], new_id);
}

#[test]
fn homework_the_account_already_has_is_not_made_again() {
    let mut linked = locked("b", 1);
    linked["assignment_id"] = json!("hw");
    let mut file = week_file(json!([linked]));
    file["assignments"] = json!([{"id": "hw", "title": "Essay", "due": "2026-10-01"}]);
    let held = json!([]);
    let has = json!({"hw": {"id": "hw", "title": "Essay", "due": "2026-10-01"}});
    let (blocks, create) =
        applied(import_week_decision(&file, &context(&held, &has, None)).unwrap());
    assert!(create.is_empty());
    assert_eq!(blocks[0]["assignment_id"], "hw");
}

#[test]
fn a_new_restore_point_goes_first_and_replaces_one_with_its_id() {
    let current = [
        json!({"id": "p1", "label": "one"}),
        json!({"id": "p2", "label": "two"}),
    ];
    let made = json!({"id": "p2", "label": "two again"});
    let after = restore_points_after_create(&current, &made);
    assert_eq!(after, vec![made, json!({"id": "p1", "label": "one"})]);
}

#[test]
fn the_restore_point_list_holds_at_most_twenty() {
    let current: Vec<Value> = (0..20).map(|n| json!({"id": format!("old{n}")})).collect();
    let after = restore_points_after_create(&current, &json!({"id": "new"}));
    assert_eq!(after.len(), 20);
    assert_eq!(after[0]["id"], "new");
    assert_eq!(after[19]["id"], "old18");
}

#[test]
fn a_restore_needs_the_preview_of_that_point() {
    let preview = json!({"id": "p1", "state_token": "t"});
    assert_eq!(restore_apply_guard(true, Some(&preview), "p1"), None);
    let words = Some("Preview the restore point first.");
    assert_eq!(restore_apply_guard(true, None, "p1"), words);
    assert_eq!(restore_apply_guard(true, Some(&preview), "p2"), words);
    assert_eq!(restore_apply_guard(false, Some(&preview), "p1"), words);
}

#[test]
fn export_and_import_wait_for_the_last_change_to_be_saved() {
    assert_eq!(transfer_blocked(false, 0, "export"), None);
    assert_eq!(
        transfer_blocked(true, 0, "export").as_deref(),
        Some("Save your last change first (More > Retry save), then export.")
    );
    assert_eq!(
        transfer_blocked(false, 2, "import").as_deref(),
        Some("Save your last change first (More > Retry save), then import.")
    );
}

#[test]
fn operation_keys_keep_their_shapes() {
    assert_eq!(
        create_restore_key(7, "before exams"),
        "create-restore|7|before exams"
    );
    assert_eq!(restore_key(7, "p1"), "restore|7|p1");
    assert_eq!(import_key(7, &json!("tok")), "import|7|tok");
    assert_eq!(import_key(7, &Value::Null), "import|7|None");
}

#[test]
fn a_point_with_no_id_replaces_one_whose_id_is_null() {
    // The window compared `item.get("id") != point.get("id")`: a missing id and a null one are the same.
    let current = [
        json!({"id": null, "label": "old"}),
        json!({"id": "p2", "label": "kept"}),
    ];
    let points = restore_points_after_create(&current, &json!({"label": "new"}));
    assert_eq!(
        points,
        vec![
            json!({"label": "new"}),
            json!({"id": "p2", "label": "kept"})
        ]
    );
}
