//! The session's restore point, export and import decisions (P4 group 9): the rules of controller.py's
//! restore, export, import and `import_week_file` methods, with the words a student reads.

use flexweek_app::session::transfer::{
    ApplyImport, ApplyRestore, CreateRestore, ExportAccount, ImportContext, ImportDecision,
    PreviewImport, PreviewRestore, create_restore_key, finish_apply_import_err,
    finish_apply_import_ok, finish_apply_restore_err, finish_apply_restore_ok,
    finish_create_restore, finish_preview_import, import_key, import_week_decision,
    prepare_apply_import, prepare_apply_restore, prepare_create_restore, prepare_export_account,
    prepare_preview_import, prepare_preview_restore, restore_apply_guard, restore_key,
    restore_points_after_create, restore_points_from_reply, transfer_blocked,
};
use flexweek_engine::ErrorKind;
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
    let file = json!({"error": "Nothing imported: the file is empty. Choose a FlexWeek week or day file."});
    let none = json!([]);
    let said = import_week_decision(&file, &context(&none, &json!({}), None)).unwrap();
    assert_eq!(
        said,
        ImportDecision::Say(
            "Nothing imported: the file is empty. Choose a FlexWeek week or day file.".into()
        )
    );
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
    let words = Some("Preview the saved copy first.");
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

const SAVE_FIRST_EXPORT: &str = "Save your last change first (More > Retry save), then export.";
const SAVE_FIRST_IMPORT: &str = "Save your last change first (More > Retry save), then import.";
const PREVIEW_FIRST: &str = "Preview the saved copy first.";

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

#[test]
fn a_blank_or_whitespace_name_is_refused_and_a_missing_id_is_not_asked_yet() {
    let blank = prepare_create_restore(true, None, "   ").unwrap();
    assert_eq!(blank, CreateRestore::Say("Name the saved copy.".into()));
    // U+001C is space to Python's strip and not to Rust's, so a name of only that is still blank.
    let control = prepare_create_restore(true, None, "\u{1c}").unwrap();
    assert_eq!(control, CreateRestore::Say("Name the saved copy.".into()));
    let signed_out = prepare_create_restore(false, None, "Before exams").unwrap();
    assert_eq!(
        signed_out,
        CreateRestore::Say("Name the saved copy.".into())
    );
}

#[test]
fn a_usable_name_with_no_account_id_is_a_missing_key() {
    let err = prepare_create_restore(true, None, "Before exams").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "id");
}

#[test]
fn the_create_request_strips_the_name_and_saves_under_that_key() {
    let ready = prepare_create_restore(true, Some(7), "  Before exams  ").unwrap();
    assert_eq!(
        ready,
        CreateRestore::Ready {
            key: "create-restore|7|Before exams".into(),
            method: "POST",
            path: "/api/restore-points".into(),
            body: json!({ "label": "Before exams" }),
            progress: "Saving a copy\u{2026}",
        }
    );
}

#[test]
fn the_saved_copy_sentence_uses_the_reply_label() {
    let reply = json!({"id": "p", "label": "Before term 2"});
    let finished = finish_create_restore(&[], &reply, "  Before exams  ").unwrap();
    assert_eq!(finished.words, "Saved copy Before term 2.");
    assert_eq!(finished.points, vec![reply]);
}

#[test]
fn a_point_with_no_label_keeps_the_name_that_was_typed_spaces_included() {
    let reply = json!({"id": "p"});
    let finished = finish_create_restore(&[], &reply, "  Before exams  ").unwrap();
    assert_eq!(finished.words, "Saved copy   Before exams  .");
}

#[test]
fn an_empty_label_on_the_point_is_not_replaced_by_the_typed_name() {
    let reply = json!({"id": "p", "label": ""});
    let finished = finish_create_restore(&[], &reply, "Before exams").unwrap();
    assert_eq!(finished.words, "Saved copy .");
}

#[test]
fn a_label_that_is_not_text_cannot_be_said() {
    let reply = json!({"id": "p", "label": 1});
    let err = finish_create_restore(&[], &reply, "Before exams").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Type);
    assert_eq!(err.message, "can only concatenate str (not \"int\") to str");
}

#[test]
fn a_wrapped_restore_point_is_the_one_that_is_stored() {
    let reply = json!({
        "restore_point": {"id": "p2", "label": "two again"},
        "label": "not this",
    });
    let current = [
        json!({"id": "p2", "label": "two"}),
        json!({"id": "p1", "label": "one"}),
    ];
    let finished = finish_create_restore(&current, &reply, "typed").unwrap();
    assert_eq!(finished.words, "Saved copy two again.");
    assert_eq!(
        finished.points,
        vec![
            json!({"id": "p2", "label": "two again"}),
            json!({"id": "p1", "label": "one"}),
        ]
    );
}

#[test]
fn an_empty_restore_point_field_falls_back_to_the_whole_reply() {
    let reply = json!({"restore_point": {}, "id": "p", "label": "whole"});
    let finished = finish_create_restore(&[], &reply, "typed").unwrap();
    assert_eq!(finished.words, "Saved copy whole.");
    assert_eq!(finished.points, vec![reply]);
}

#[test]
fn finish_create_still_keeps_only_the_newest_twenty() {
    let current: Vec<Value> = (0..20).map(|n| json!({"id": format!("old{n}")})).collect();
    let reply = json!({"id": "new", "label": "new"});
    let finished = finish_create_restore(&current, &reply, "new").unwrap();
    assert_eq!(finished.points.len(), 20);
    assert_eq!(finished.points[0]["id"], "new");
    assert_eq!(finished.points[19]["id"], "old18");
}

#[test]
fn the_listed_points_prefer_restore_points_and_an_empty_list_falls_through() {
    let listed = restore_points_from_reply(&json!({"restore_points": [{"id": "a"}]})).unwrap();
    assert_eq!(listed, vec![json!({"id": "a"})]);
    let fallback = restore_points_from_reply(&json!({
        "restore_points": [],
        "points": [{"id": "b"}],
    }))
    .unwrap();
    assert_eq!(fallback, vec![json!({"id": "b"})]);
    let neither = restore_points_from_reply(&json!({})).unwrap();
    assert!(neither.is_empty());
}

#[test]
fn a_restore_point_count_instead_of_a_list_is_not_iterable() {
    let err = restore_points_from_reply(&json!({"restore_points": 1})).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Type);
    assert_eq!(err.message, "'int' object is not iterable");
}

#[test]
fn a_reply_that_is_not_an_object_has_no_get() {
    let err = restore_points_from_reply(&json!([{"id": "a"}])).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Attribute);
    assert_eq!(err.message, "'list' object has no attribute 'get'");
}

#[test]
fn a_signed_out_preview_sends_nothing() {
    assert_eq!(prepare_preview_restore(false, "p1"), PreviewRestore::Absent);
}

#[test]
fn a_preview_path_encodes_the_point_id_the_way_the_window_quoted_it() {
    assert_eq!(
        prepare_preview_restore(true, "a/b c"),
        PreviewRestore::Ready {
            method: "GET",
            path: "/api/restore-points/a%2Fb%20c/preview".into(),
        }
    );
    assert_eq!(
        prepare_preview_restore(true, "café~"),
        PreviewRestore::Ready {
            method: "GET",
            path: "/api/restore-points/caf%C3%A9~/preview".into(),
        }
    );
}

#[test]
fn applying_still_needs_the_preview_of_that_point() {
    let preview = json!({"id": "p1", "state_token": "t"});
    let refused = prepare_apply_restore(true, Some(7), Some(&preview), "p2").unwrap();
    assert_eq!(refused, ApplyRestore::Say(PREVIEW_FIRST.into()));
    let signed_out = prepare_apply_restore(false, None, Some(&preview), "p1").unwrap();
    assert_eq!(signed_out, ApplyRestore::Say(PREVIEW_FIRST.into()));
    let missing = prepare_apply_restore(true, Some(7), None, "p1").unwrap();
    assert_eq!(missing, ApplyRestore::Say(PREVIEW_FIRST.into()));
}

#[test]
fn a_ready_restore_posts_the_quoted_path_and_the_preview_token() {
    let preview = json!({"id": "a/b", "state_token": "tok"});
    let ready = prepare_apply_restore(true, Some(7), Some(&preview), "a/b").unwrap();
    assert_eq!(
        ready,
        ApplyRestore::Ready {
            key: "restore|7|a/b".into(),
            method: "POST",
            path: "/api/restore-points/a%2Fb/restore".into(),
            body: json!({ "state_token": "tok" }),
            progress: "Restoring\u{2026}",
        }
    );
}

#[test]
fn a_preview_without_its_token_is_a_missing_key() {
    let preview = json!({"id": "p1"});
    let err = prepare_apply_restore(true, Some(7), Some(&preview), "p1").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "state_token");
}

#[test]
fn only_a_conflict_clears_the_preview_after_a_failed_restore_or_import() {
    assert_eq!(finish_apply_restore_err(409)["clear_preview"], true);
    assert_eq!(finish_apply_restore_err(400)["clear_preview"], false);
    assert_eq!(finish_apply_restore_err(500)["clear_preview"], false);
    assert_eq!(finish_apply_import_err(409)["clear_preview"], true);
    assert_eq!(finish_apply_import_err(404)["clear_preview"], false);
}

#[test]
fn a_finished_restore_reloads_the_week_and_says_restored() {
    assert_eq!(
        finish_apply_restore_ok(),
        json!({
            "clear_preview": true,
            "clear_history": true,
            "focus_after_restore": true,
            "words": "Restored.",
            "reload": true,
            "fetch_points": true,
        })
    );
}

#[test]
fn export_waits_when_signed_out_or_dirty_and_otherwise_posts_the_password() {
    assert_eq!(
        prepare_export_account(false, false, 0, "secret"),
        ExportAccount::Say(SAVE_FIRST_EXPORT.into())
    );
    assert_eq!(
        prepare_export_account(true, false, 2, "secret"),
        ExportAccount::Say(SAVE_FIRST_EXPORT.into())
    );
    assert_eq!(
        prepare_export_account(true, false, 0, ""),
        ExportAccount::Ready {
            method: "POST",
            path: "/api/account-export".into(),
            body: json!({ "password": "" }),
        }
    );
}

#[test]
fn an_import_preview_posts_the_file_unless_something_is_unsaved() {
    let file = json!({"format": 3, "username": "ada"});
    assert_eq!(
        prepare_preview_import(false, false, 0, &file),
        PreviewImport::Say(SAVE_FIRST_IMPORT.into())
    );
    assert_eq!(
        prepare_preview_import(true, true, 0, &file),
        PreviewImport::Say(SAVE_FIRST_IMPORT.into())
    );
    assert_eq!(
        prepare_preview_import(true, false, 0, &file),
        PreviewImport::Ready {
            method: "POST",
            path: "/api/account-import/preview".into(),
            body: json!({ "snapshot": file }),
        }
    );
}

#[test]
fn the_kept_import_preview_starts_from_the_file_and_the_reply_overwrites_it() {
    let file = json!({"format": 3, "username": "ada"});
    let reply = json!({"state_token": "t", "source_username": "ada", "changes": []});
    let merged = finish_preview_import(&file, &reply).unwrap();
    assert_eq!(
        merged,
        json!({
            "snapshot": {"format": 3, "username": "ada"},
            "state_token": "t",
            "source_username": "ada",
            "changes": [],
        })
    );
    let replaced = json!({"snapshot": {"format": 3, "username": "bea"}, "state_token": "t"});
    let merged = finish_preview_import(&file, &replaced).unwrap();
    assert_eq!(merged["snapshot"]["username"], "bea");
    let keys: Vec<&String> = merged.as_object().unwrap().keys().collect();
    assert_eq!(keys, ["snapshot", "state_token"]);
}

#[test]
fn a_preview_reply_that_is_not_an_object_is_not_a_mapping() {
    let err = finish_preview_import(&json!({}), &json!([1])).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Type);
    assert_eq!(err.message, "'list' object is not a mapping");
}

#[test]
fn an_import_with_no_account_or_no_preview_does_nothing() {
    let preview = json!({"snapshot": {}, "state_token": "t"});
    assert_eq!(
        prepare_apply_import(None, Some(&preview), false, 0).unwrap(),
        ApplyImport::Absent
    );
    assert_eq!(
        prepare_apply_import(Some(7), None, false, 0).unwrap(),
        ApplyImport::Absent
    );
}

#[test]
fn unsaved_work_is_refused_before_a_bad_import_preview_is_read() {
    let preview = json!([1, 2]);
    let refused = prepare_apply_import(Some(7), Some(&preview), true, 0).unwrap();
    assert_eq!(refused, ApplyImport::Say(SAVE_FIRST_IMPORT.into()));
    let err = prepare_apply_import(Some(7), Some(&preview), false, 0).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Attribute);
    assert_eq!(err.message, "'list' object has no attribute 'get'");
}

#[test]
fn a_ready_import_posts_the_snapshot_and_names_a_missing_token_none() {
    let preview = json!({"snapshot": {"format": 3}, "state_token": null});
    let ready = prepare_apply_import(Some(7), Some(&preview), false, 0).unwrap();
    assert_eq!(
        ready,
        ApplyImport::Ready {
            key: "import|7|None".into(),
            method: "POST",
            path: "/api/account-import".into(),
            body: json!({ "snapshot": {"format": 3}, "state_token": null }),
        }
    );
}

#[test]
fn a_missing_snapshot_on_the_import_preview_is_a_missing_key() {
    let preview = json!({"state_token": "t"});
    let err = prepare_apply_import(Some(7), Some(&preview), false, 0).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "snapshot");
}

#[test]
fn a_finished_import_discards_the_open_week_and_says_it_imported() {
    assert_eq!(
        finish_apply_import_ok(),
        json!({
            "clear_preview": true,
            "clear_history": true,
            "words": "Imported account data.",
            "reload_discard": true,
            "fetch_points": true,
        })
    );
}
