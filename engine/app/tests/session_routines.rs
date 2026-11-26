//! Routine save, delete and apply decisions: the words, keys, paths and bodies of
//! `desktop/native/controller.py`. Expected text is the sentence and the encoding the window uses today.

use flexweek_app::session::routines::{
    ApplyRoutine, DeleteRoutine, RoutineRows, SaveRoutine, SavedRoutine,
    apply_routine_rows_decision, delete_routine_path, prepare_apply_routine,
    prepare_delete_routine, prepare_save_routine, quote_component, routines_from_reply,
    save_routine_reply, save_routine_request,
};
use flexweek_engine::ErrorKind;
use serde_json::{Map, Value, json};

const MONDAY: &str = "2026-11-16";
const WEDNESDAY: &str = "2026-11-04";
const SOCCER_FINGERPRINT: &str = concat!(
    r#"[{"block": {"category": "exercise", "days": [0, 2], "duration_min": 60, "id": "soccer", "#,
    r#""kind": "locked", "start": "16:00", "title": "Soccer"}, "scope": "block", "source_day": 0}]"#
);

fn soccer() -> Value {
    json!({
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0, 2],
        "start": "16:00",
        "category": "exercise",
    })
}

fn essay() -> Value {
    json!({
        "id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "estimate_min": 90,
        "days": [1],
        "assignment_id": "essay",
    })
}

fn pomodoro() -> Value {
    json!({
        "id": "focus",
        "title": "Focus",
        "kind": "locked",
        "duration_min": 25,
        "days": [1],
        "start": "09:00",
        "pomodoro_role": "work",
    })
}

fn save(
    account: Option<i64>,
    week: &str,
    blocks: &[Value],
    name: &str,
    block_ids: Option<&[Value]>,
    ids: &[&str],
) -> SaveRoutine {
    let ids: Vec<String> = ids.iter().map(|id| (*id).to_string()).collect();
    prepare_save_routine(account, week, blocks, name, block_ids, &ids).expect("save decision")
}

fn routine(id: &str, name: &str, revision: i64, days: &[i64]) -> Value {
    json!({
        "id": id,
        "name": name,
        "revision": revision,
        "blocks": [{
            "template_id": "t1",
            "title": "Club",
            "days": days,
            "start": "16:00",
            "duration_min": 60,
            "category": "exercise",
        }],
    })
}

fn routines(items: &[Value]) -> Value {
    let mut map = Map::new();
    for item in items {
        map.insert(item["id"].as_str().expect("id").to_string(), item.clone());
    }
    Value::Object(map)
}

fn ready_save(decision: SaveRoutine) -> (String, String, Vec<Value>, Value) {
    match decision {
        SaveRoutine::Ready {
            key,
            title,
            templates,
            body_without_id,
        } => (key, title, templates, body_without_id),
        other => panic!("expected a save, got {other:?}"),
    }
}

#[test]
fn quote_leaves_tilde_and_encodes_space_slash_and_unicode() {
    let samples = [
        (" ", "%20"),
        ("/", "%2F"),
        ("~", "~"),
        ("a b/c~", "a%20b%2Fc~"),
        ("café", "caf%C3%A9"),
        ("中", "%E4%B8%AD"),
        ("week 1/2 ~ café", "week%201%2F2%20~%20caf%C3%A9"),
        ("AZaz09_.-~", "AZaz09_.-~"),
        ("", ""),
        ("r-op/1 ~ é", "r-op%2F1%20~%20%C3%A9"),
    ];
    for (raw, encoded) in samples {
        assert_eq!(quote_component(raw), encoded, "{raw:?}");
    }
}

#[test]
fn a_blank_name_or_no_fixed_time_is_refused_with_the_same_sentence() {
    let blocks = [soccer()];
    assert_eq!(
        save(Some(7), MONDAY, &blocks, "   ", None, &[]),
        SaveRoutine::Say("Name the routine and select at least one fixed time.".into())
    );
    assert_eq!(
        save(Some(7), MONDAY, &blocks, "\u{1c}\u{1d}", None, &[]),
        SaveRoutine::Say("Name the routine and select at least one fixed time.".into())
    );
    assert_eq!(
        save(Some(7), MONDAY, &[], "Sports", None, &[]),
        SaveRoutine::Say("Name the routine and select at least one fixed time.".into())
    );
    let only_other = [json!("other")];
    assert_eq!(
        save(Some(7), MONDAY, &blocks, "Sports", Some(&only_other), &[]),
        SaveRoutine::Say("Name the routine and select at least one fixed time.".into())
    );
}

#[test]
fn signed_out_save_says_nothing_even_when_the_name_is_blank() {
    assert_eq!(
        save(None, MONDAY, &[soccer()], "", None, &[]),
        SaveRoutine::Absent
    );
}

#[test]
fn homework_and_a_focus_chunk_are_not_saved_as_a_routine() {
    let blocks = [soccer(), essay(), pomodoro()];
    let (_key, title, templates, _body) = ready_save(save(
        Some(7),
        MONDAY,
        &blocks,
        "Sports",
        None,
        &["tmpl-1", "unused"],
    ));
    assert_eq!(title, "Sports");
    assert_eq!(templates.len(), 1);
    assert_eq!(templates[0]["title"], "Soccer");
    assert_eq!(templates[0]["template_id"], "tmpl-1");
}

#[test]
fn save_key_templates_and_body_match_the_window() {
    let blocks = [soccer()];
    let (key, title, templates, body) = ready_save(save(
        Some(7),
        MONDAY,
        &blocks,
        "  Soccer  ",
        None,
        &["tmpl-1"],
    ));
    assert_eq!(title, "Soccer");
    assert_eq!(key, format!("create-routine|7|Soccer|{SOCCER_FINGERPRINT}"));
    assert_eq!(
        templates,
        vec![json!({
            "template_id": "tmpl-1",
            "title": "Soccer",
            "days": [0, 2],
            "start": "16:00",
            "duration_min": 60,
            "category": "exercise",
        })]
    );
    assert_eq!(
        body,
        json!({
            "name": "Soccer",
            "blocks": templates,
            "revision": 0,
        })
    );
}

#[test]
fn a_chosen_id_drops_the_other_fixed_time() {
    let second = json!({
        "id": "piano",
        "title": "Piano",
        "kind": "locked",
        "duration_min": 30,
        "days": [1],
        "start": "18:00",
        "category": "hobby",
    });
    let kept = [json!("piano")];
    let (_key, _title, templates, _body) = ready_save(save(
        Some(7),
        MONDAY,
        &[soccer(), second],
        "Music",
        Some(&kept),
        &["tmpl-piano"],
    ));
    assert_eq!(templates.len(), 1);
    assert_eq!(templates[0]["title"], "Piano");
    assert_eq!(templates[0]["template_id"], "tmpl-piano");
}

#[test]
fn a_wednesday_week_saves_the_fixed_time_on_its_weekday() {
    // Day 5 of the week from Wednesday 4 November 2026 is Monday, weekday 0.
    let club = json!({
        "id": "club",
        "title": "Club",
        "kind": "locked",
        "duration_min": 60,
        "days": [5],
        "start": "16:00",
        "category": "hobby",
    });
    let (_key, _title, templates, _body) = ready_save(save(
        Some(7),
        WEDNESDAY,
        &[club],
        "Clubs",
        None,
        &["tmpl-club"],
    ));
    assert_eq!(templates[0]["days"], json!([0]));
}

#[test]
fn a_fixed_time_with_no_id_cannot_be_filtered() {
    let block = json!({
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "16:00",
    });
    let allowed = [json!("soccer")];
    let error = prepare_save_routine(Some(7), MONDAY, &[block], "Sports", Some(&allowed), &[])
        .expect_err("missing id");
    assert_eq!(error.kind, ErrorKind::Key);
    assert_eq!(error.message, "id");
}

#[test]
fn the_save_request_prefixes_r_quotes_the_id_and_says_it_is_saving() {
    let templates = vec![json!({"template_id": "tmpl-1", "title": "Soccer"})];
    let request = save_routine_request("op/1 ~ é", "Soccer", &templates);
    assert_eq!(request.routine_id, "r-op/1 ~ é");
    assert_eq!(request.method, "PUT");
    assert_eq!(request.path, "/api/routines/r-op%2F1%20~%20%C3%A9");
    assert_eq!(request.progress, "Saving routine\u{2026}");
    assert_eq!(
        request.body,
        json!({
            "id": "r-op/1 ~ é",
            "name": "Soccer",
            "blocks": templates,
            "revision": 0,
        })
    );
}

#[test]
fn the_save_reply_prefers_the_routine_object_and_names_it() {
    let inner = json!({"id": "r-9", "name": "Clubs"});
    let saved = save_routine_reply(&json!({"routine": inner, "id": "outer"})).expect("reply");
    assert_eq!(
        saved,
        SavedRoutine {
            id: json!("r-9"),
            routine: inner,
            say: "Saved Clubs.".into(),
        }
    );
}

#[test]
fn a_reply_without_a_routine_object_is_stored_whole() {
    let data = json!({"id": "r-1", "name": "Soccer"});
    let saved = save_routine_reply(&data).expect("reply");
    assert_eq!(saved.routine, data);
    assert_eq!(saved.say, "Saved Soccer.");

    let empty = json!({"routine": {}, "id": "r-1", "name": "Soccer"});
    let saved = save_routine_reply(&empty).expect("empty routine is the answer itself");
    assert_eq!(saved.routine, empty);
    assert_eq!(saved.id, json!("r-1"));
}

#[test]
fn a_reply_whose_name_is_not_text_is_refused() {
    let error = save_routine_reply(&json!({"id": "r-1", "name": 1})).expect_err("number name");
    assert_eq!(error.kind, ErrorKind::Type);
    assert_eq!(
        error.message,
        "can only concatenate str (not \"int\") to str"
    );
}

#[test]
fn deleting_a_missing_routine_or_while_signed_out_says_nothing() {
    let held = routines(&[routine("r-1", "Clubs", 4, &[0])]);
    assert_eq!(
        prepare_delete_routine(None, &held, "r-1").expect("signed out"),
        DeleteRoutine::Absent
    );
    assert_eq!(
        prepare_delete_routine(Some(7), &held, "missing").expect("missing"),
        DeleteRoutine::Absent
    );
}

#[test]
fn delete_key_sentence_and_path_match_the_window() {
    let held = routines(&[routine("r 1/2~é", "Clubs", 4, &[0])]);
    let DeleteRoutine::Ready { key, revision, say } =
        prepare_delete_routine(Some(7), &held, "r 1/2~é").expect("delete")
    else {
        panic!("expected a delete");
    };
    assert_eq!(key, "delete-routine|7|r 1/2~é|4");
    assert_eq!(revision, json!(4));
    assert_eq!(say, "Deleted Clubs.");
    assert_eq!(
        delete_routine_path("r 1/2~é", &revision, "op 1/2~é").expect("path"),
        "/api/routines/r%201%2F2~%C3%A9?revision=4&operation_id=op%201%2F2~%C3%A9"
    );
}

#[test]
fn a_missing_routine_or_no_ticked_day_asks_for_a_weekday() {
    let held = routines(&[routine("r-1", "Clubs", 1, &[0])]);
    assert_eq!(
        apply_routine_rows_decision(&held, "missing", MONDAY, &[json!(0)]).expect("rows"),
        RoutineRows::Say("Choose at least one weekday to copy.")
    );
    assert_eq!(
        apply_routine_rows_decision(&held, "r-1", MONDAY, &[]).expect("rows"),
        RoutineRows::Say("Choose at least one weekday to copy.")
    );
}

#[test]
fn applying_rows_keeps_monday_as_day_five_of_a_wednesday_week() {
    let held = routines(&[routine("r-1", "Clubs", 1, &[0])]);
    let RoutineRows::Rows(rows) =
        apply_routine_rows_decision(&held, "r-1", "2026-11-11", &[json!(5)]).expect("rows")
    else {
        panic!("expected rows");
    };
    assert_eq!(
        rows.iter()
            .map(|row| (row["week_start"].as_str(), row["day"].as_i64()))
            .collect::<Vec<_>>(),
        vec![(Some("2026-11-11"), Some(5))]
    );
    let RoutineRows::Rows(rows) =
        apply_routine_rows_decision(&held, "r-1", MONDAY, &[json!(0)]).expect("rows")
    else {
        panic!("expected rows");
    };
    assert_eq!(
        rows.iter()
            .map(|row| (row["week_start"].as_str(), row["day"].as_i64()))
            .collect::<Vec<_>>(),
        vec![(Some(MONDAY), Some(0))]
    );
}

#[test]
fn nothing_checked_says_there_is_nothing_to_add() {
    let held = routines(&[routine("r-1", "Clubs", 3, &[0])]);
    let decision = prepare_apply_routine(Some(7), &held, "r-1", MONDAY, &[json!(0)], Some(&[]))
        .expect("apply");
    assert_eq!(
        decision,
        ApplyRoutine::Say(vec!["There's nothing available to add.".into()])
    );
}

#[test]
fn applying_with_no_rows_and_no_days_says_the_weekday_sentence_and_then_nothing_to_add() {
    let held = routines(&[routine("r-1", "Clubs", 3, &[0])]);
    let decision = prepare_apply_routine(Some(7), &held, "r-1", MONDAY, &[], None).expect("apply");
    assert_eq!(
        decision,
        ApplyRoutine::Say(vec![
            "Choose at least one weekday to copy.".into(),
            "There's nothing available to add.".into(),
        ])
    );
}

#[test]
fn a_missing_routine_while_applying_says_nothing() {
    let held = routines(&[routine("r-1", "Clubs", 3, &[0])]);
    assert_eq!(
        prepare_apply_routine(Some(7), &held, "gone", MONDAY, &[], None).expect("apply"),
        ApplyRoutine::Absent
    );
    assert_eq!(
        prepare_apply_routine(None, &held, "r-1", MONDAY, &[json!(0)], None).expect("apply"),
        ApplyRoutine::Absent
    );
}

#[test]
fn apply_key_label_and_restore_point_name_the_routine_and_the_week() {
    let held = routines(&[routine("r-1", "Clubs", 3, &[0])]);
    let row = json!({"week_start": MONDAY, "day": 0, "fixed": true});
    let ApplyRoutine::Ready {
        proposals,
        key,
        label,
        snapshot_label,
    } = prepare_apply_routine(
        Some(7),
        &held,
        "r-1",
        MONDAY,
        &[json!(0), json!(2)],
        Some(std::slice::from_ref(&row)),
    )
    .expect("apply")
    else {
        panic!("expected a ready apply");
    };
    assert_eq!(proposals, vec![row]);
    assert_eq!(key, "routine|7|r-1|3|2026-11-16|0,2");
    assert_eq!(label, "the Clubs routine");
    assert_eq!(snapshot_label, "Before applying Clubs to 2026-11-16");
}

#[test]
fn a_long_restore_point_label_is_cut_to_eighty_characters() {
    let name = "A".repeat(80);
    let held = routines(&[routine("r-1", &name, 3, &[0])]);
    let row = json!({"week_start": MONDAY, "day": 0});
    let ApplyRoutine::Ready { snapshot_label, .. } = prepare_apply_routine(
        Some(7),
        &held,
        "r-1",
        MONDAY,
        &[json!(0)],
        Some(std::slice::from_ref(&row)),
    )
    .expect("apply") else {
        panic!("expected a ready apply");
    };
    // "Before applying " is 16 characters, so 79 characters is that plus 63 of the name, then "…".
    let mut expected = format!("{}{}", "Before applying ", "A".repeat(63));
    expected.push('\u{2026}');
    assert_eq!(snapshot_label, expected);
    assert_eq!(snapshot_label.chars().count(), 80);
}

#[test]
fn the_reply_list_is_a_map_by_id_and_a_later_row_wins() {
    let data = json!({
        "routines": [
            {"id": "r-1", "name": "First"},
            {"id": "r-2", "name": "Second"},
            {"id": "r-1", "name": "Later"},
        ]
    });
    let map = routines_from_reply(&data).expect("map");
    assert_eq!(map.len(), 2);
    assert_eq!(map["r-1"]["name"], "Later");
    assert_eq!(map["r-2"]["name"], "Second");
}

#[test]
fn a_reply_with_no_routines_is_an_empty_map() {
    assert!(routines_from_reply(&json!({})).expect("missing").is_empty());
    assert!(
        routines_from_reply(&json!({"routines": null}))
            .expect("null")
            .is_empty()
    );
    assert!(
        routines_from_reply(&json!({"routines": []}))
            .expect("empty")
            .is_empty()
    );
}

#[test]
fn a_routine_row_without_an_id_is_a_missing_key() {
    let error = routines_from_reply(&json!({"routines": [{"name": "Clubs"}]})).expect_err("id");
    assert_eq!(error.kind, ErrorKind::Key);
    assert_eq!(error.message, "id");
}
