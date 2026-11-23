//! A homework's notes, links and checklist (the homework sheet): saved, returned, left off the answer when
//! empty, and refused when unsafe. The Rust twins of backend/tests/test_assignment_notes_api.py.

use flexweek_engine::plan::parse_moment;
use flexweek_engine::validate::assignment_content;
use flexweek_service::homework_saves::save_homework;
use flexweek_service::{Refusal, ServiceError, views};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn assignment(changes: Value) -> Value {
    let mut body = json!({
        "id": "hw-essay", "title": "Essay", "course": "History", "category": null, "priority": 2, "energy": "low",
        "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    });
    for (key, value) in changes.as_object().unwrap() {
        body[key] = value.clone();
    }
    body
}

fn base(changes: Value) -> Value {
    let mut body = json!({ "id": "hw-essay", "title": "Essay", "due": "2026-09-15T23:59", "estimate_min": 120 });
    for (key, value) in changes.as_object().unwrap() {
        body[key] = value.clone();
    }
    body
}

#[test]
fn notes_links_and_a_checklist_are_saved_and_listed_and_an_unsafe_link_is_refused() {
    let db = TestDb::new("notes-round-trip");
    let ana = db.account("ana");
    let notes = json!({
        "notes": "Bring the outline.",
        "links": [{ "label": "Prompt", "url": "https://example.edu/essay" }],
        "checklist": [{ "id": "draft", "text": "First draft", "done": true }],
    });
    let saved = save_homework(&db.path, ana, "hw-essay", &assignment(notes.clone())).unwrap();
    let now = parse_moment("2026-09-14T08:00").unwrap();
    let loaded =
        views::homework(&db.path, ana, "2026-09-14", false, now).unwrap()["assignments"][0].clone();
    for answer in [&saved, &loaded] {
        for key in ["notes", "links", "checklist"] {
            assert_eq!(answer[key], notes[key], "{key}");
        }
    }
    let bad = assignment(
        json!({ "revision": 1, "links": [{ "label": "Bad", "url": "javascript:alert(1)" }] }),
    );
    assert!(matches!(
        save_homework(&db.path, ana, "hw-essay", &bad),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

#[test]
fn empty_notes_links_and_checklist_are_left_off_and_filled_ones_are_kept() {
    let empty = assignment_content(&base(json!({}))).unwrap().to_value();
    for key in ["notes", "links", "checklist"] {
        assert!(empty.get(key).is_none(), "{key} in {empty}");
    }
    let filled = json!({
        "notes": "Use the primary sources from week 3.",
        "links": [{ "label": "Prompt", "url": "https://example.edu/prompt" }],
        "checklist": [{ "id": "outline", "text": "Outline", "done": false }],
    });
    let kept = assignment_content(&base(filled.clone()))
        .unwrap()
        .to_value();
    for key in ["notes", "links", "checklist"] {
        assert_eq!(kept[key], filled[key], "{key}");
    }
}

#[test]
fn a_javascript_link_and_two_checklist_items_with_one_id_are_refused() {
    assert!(
        assignment_content(&base(
            json!({ "links": [{ "label": "Bad", "url": "javascript:alert(1)" }] })
        ))
        .is_err()
    );
    let twice = json!({ "checklist": [{ "id": "one", "text": "First" }, { "id": "one", "text": "Again" }] });
    assert!(assignment_content(&base(twice)).is_err());
}
