//! The repeat-edit preview (spec.md): before a change to School or a Setup activity is saved for later
//! weeks, the app asks which of those weeks have their own edit; nothing is written. A request that is not
//! a list of changes is refused.

use flexweek_service::week_saves::preview_repeat_edits;
use flexweek_service::{Refusal, ServiceError, with_db};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn cases() -> Value {
    serde_json::from_str(include_str!("../../store/tests/fixtures/repeat_cases.json")).unwrap()
}

/// An account whose School and Soccer repeat from 2 November, with its own School times on 23 November.
fn standing(db: &TestDb) -> i64 {
    let ana = db.account("ana");
    let setup = flexweek_engine::repeats::parse_intents(&cases()["setup"]).unwrap();
    with_db(&db.path, |conn| {
        flexweek_store::apply_repeat_intents(conn, ana, &setup).unwrap();
        let own = json!([{ "id": "school", "title": "School", "kind": "locked", "duration_min": 300,
                           "days": [0, 1, 2, 3, 4], "start": "08:30", "category": "class" }]);
        flexweek_store::save_week(conn, ana, "2026-11-23", &own.to_string(), 0)?;
        Ok(())
    })
    .unwrap();
    ana
}

fn refused(result: Result<Value, ServiceError>) -> String {
    match result {
        Err(ServiceError::Refused(Refusal::Invalid(words))) => words,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn a_later_week_with_its_own_edit_is_named_and_nothing_is_written() {
    let db = TestDb::new("repeat-preview");
    let ana = standing(&db);
    let before = std::fs::read(&db.path).unwrap();
    let change = json!({ "repeats": [{ "id": "school", "scope": "from", "from_date": "2026-11-16",
                                       "set": { "duration_min": 360 } }] });
    let found = preview_repeat_edits(&db.path, ana, &change).unwrap();
    assert_eq!(found["weeks"], json!(["2026-11-23"]));
    assert_eq!(
        found["line"],
        "The week of 23 November has its own School times."
    );
    assert_eq!(
        std::fs::read(&db.path).unwrap(),
        before,
        "the preview wrote"
    );
    assert_eq!(
        preview_repeat_edits(&db.path, ana, &json!({ "repeats": [] })).unwrap(),
        json!({ "line": null, "weeks": [] })
    );
}

#[test]
fn a_request_that_is_not_a_list_of_changes_is_refused() {
    let db = TestDb::new("repeat-refused");
    let ana = db.account("ana");
    let general = flexweek_service::accounts::INVALID_INPUT;
    let too_many: Vec<Value> = (0..401)
        .map(|at| json!({ "id": format!("r{at}"), "scope": "from", "from_date": "2026-11-16" }))
        .collect();
    for body in [
        json!({ "repeats": [1] }),
        json!({ "repeats": [], "x": 1 }),
        json!({}),
        json!([]),
        json!({ "repeats": too_many }),
    ] {
        assert_eq!(
            refused(preview_repeat_edits(&db.path, ana, &body)),
            general,
            "{body}"
        );
    }
    let db = TestDb::new("repeat-no-day");
    let ana = standing(&db);
    let no_day = json!({ "repeats": [{ "id": "activity-1", "scope": "from", "from_date": "2026-11-09",
                                        "remove_days": [1, 3] }] });
    assert_eq!(
        refused(preview_repeat_edits(&db.path, ana, &no_day)),
        "That change leaves no day, so nothing changed. Use stop to take it off the calendar."
    );
}
