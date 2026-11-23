//! Changes to School and Setup's activities through the app's multi-week save, checked by what each week
//! shows. The cases and their answers are the ones the assistant's save runs too
//! (`engine/store/tests/fixtures/repeat_cases.json`), worked out by hand from the owner's rules, so the two
//! save handlers cannot drift apart unnoticed. The Rust twins of backend/tests/test_repeat_intents_api.py.

use flexweek_service::changes::apply_changes;
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn cases() -> Value {
    serde_json::from_str(include_str!("../../store/tests/fixtures/repeat_cases.json")).unwrap()
}

fn changes(db: &TestDb, user: i64, given: Value) -> Result<Value, ServiceError> {
    apply_changes(
        &db.path,
        user,
        &given,
        "0123456789abcdef",
        "2026-11-05T19:00",
    )
}

fn week(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

/// What a week shows, as the case file writes it.
fn summary(blocks: &Value) -> Value {
    let mut out = serde_json::Map::new();
    for block in blocks.as_array().unwrap() {
        let missed = match &block["missed_days"] {
            Value::Null => json!([]),
            days => days.clone(),
        };
        out.insert(
            block["id"].as_str().unwrap().to_string(),
            json!([
                block["title"],
                block["start"],
                block["duration_min"],
                block["days"],
                missed
            ]),
        );
    }
    Value::Object(out)
}

fn set_clock(db: &TestDb, user: i64, clock_24h: bool) {
    let mut preferences = read_preferences(&db.path, user).unwrap();
    preferences["clock_24h"] = json!(clock_24h);
    write_preferences(&db.path, user, &preferences).unwrap();
}

#[test]
fn every_shared_case_gives_the_answer_worked_out_for_both_save_handlers() {
    let cases = cases();
    let resolve = |block: &Value| match block.as_str() {
        Some(name) => cases[name].clone(),
        None => block.clone(),
    };
    for (n, case) in cases["cases"].as_array().unwrap().iter().enumerate() {
        let name = case["name"].as_str().unwrap();
        let db = TestDb::new(&format!("repeats-case-{n}"));
        let ana = db.account("ana");
        set_clock(&db, ana, case["clock_24h"] == json!(true));
        changes(&db, ana, json!({ "weeks": [], "repeats": cases["setup"] })).unwrap();
        let mut last = Value::Null;
        for step in case["steps"].as_array().unwrap() {
            let weeks: Vec<Value> = step
                .get("weeks")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .map(|entry| {
                    let week_start = entry["week_start"].as_str().unwrap();
                    let blocks: Vec<Value> = entry["blocks"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(resolve)
                        .collect();
                    json!({ "week_start": week_start, "blocks": blocks,
                            "revision": week(&db, ana, week_start)["revision"] })
                })
                .collect();
            let mut given = json!({ "weeks": weeks });
            if let Some(repeats) = step.get("repeats") {
                given["repeats"] = repeats.clone();
            }
            last = changes(&db, ana, given).unwrap();
        }
        assert_eq!(last["repeats"], case["answer_repeats"], "{name}");
        for (week_start, expected) in case["shown"].as_object().unwrap() {
            assert_eq!(
                summary(&week(&db, ana, week_start)["blocks"]),
                *expected,
                "{name}: week of {week_start}"
            );
        }
    }
}

#[test]
fn the_week_names_the_repeats_as_they_stand_in_it() {
    let cases = cases();
    let db = TestDb::new("repeats-named");
    let ana = db.account("ana");
    changes(&db, ana, json!({ "weeks": [], "repeats": cases["setup"] })).unwrap();
    let hours = json!([{ "id": "school", "scope": "from", "from_date": "2026-11-16", "set": { "duration_min": 360 } }]);
    changes(&db, ana, json!({ "repeats": hours })).unwrap();
    assert!(week(&db, ana, "2026-10-26").get("repeats").is_none());
    assert_eq!(
        week(&db, ana, "2026-11-09")["repeats"],
        json!([cases["school"], cases["soccer"]])
    );
    let mut shorter = cases["school"].clone();
    shorter["duration_min"] = json!(360);
    assert_eq!(
        week(&db, ana, "2026-11-16")["repeats"],
        json!([shorter, cases["soccer"]])
    );
}

#[test]
fn a_change_that_is_not_one_is_refused_with_its_sentence_and_saves_nothing() {
    let cases = cases();
    let db = TestDb::new("repeats-empty");
    let ana = db.account("ana");
    changes(&db, ana, json!({ "weeks": [], "repeats": cases["setup"] })).unwrap();
    let empties = json!({ "id": "activity-1", "scope": "from", "from_date": "2026-11-09", "remove_days": [1, 3] });
    let given = json!({
        "weeks": [{ "week_start": "2026-11-09", "blocks": [cases["school"]], "revision": 0 }],
        "repeats": [empties],
    });
    match changes(&db, ana, given) {
        Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(
            words,
            "That change leaves no day, so nothing changed. Use stop to take it off the calendar."
        ),
        other => panic!("not refused in words: {other:?}"),
    }
    let shown = week(&db, ana, "2026-11-09");
    assert_eq!(shown["revision"], 0);
    let ids: Vec<&str> = shown["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, ["school", "activity-1"]);
}

#[test]
fn a_batch_sent_again_gets_its_first_answer() {
    let cases = cases();
    let db = TestDb::new("repeats-replay");
    let ana = db.account("ana");
    changes(&db, ana, json!({ "weeks": [], "repeats": cases["setup"] })).unwrap();
    let mut later = cases["school"].clone();
    later["days"] = json!([0, 1, 3, 4]);
    changes(
        &db,
        ana,
        json!({ "weeks": [{ "week_start": "2026-11-16", "blocks": [later, cases["soccer"]], "revision": 0 }] }),
    )
    .unwrap();
    let given = json!({
        "weeks": [],
        "operation_id": "op-school-hours",
        "repeats": [{ "id": "school", "scope": "from", "from_date": "2026-11-09", "set": { "duration_min": 360 } }],
    });
    let first = changes(&db, ana, given.clone()).unwrap();
    let revision = week(&db, ana, "2026-11-16")["revision"].clone();
    assert_eq!(changes(&db, ana, given).unwrap(), first);
    assert_eq!(
        week(&db, ana, "2026-11-16")["revision"],
        revision,
        "the batch ran twice"
    );
}
