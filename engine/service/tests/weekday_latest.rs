//! An old-style block saved with a weekday deadline ("latest": "Thursday 21:00") becomes homework with one
//! session; a block ticked done gets its finish time, midnight included. Dues are worked from the calendar:
//! the week of 2026-09-07 has its Thursday on 2026-09-10. The Rust twins of
//! backend/tests/test_week_save_with_weekday_latest.py.

use flexweek_engine::plan::{completed_at_for_block, parse_moment};
use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-07";
const AID: &str = "a-4c3275a3fa104726ed3f39fbfb7dcdbf";

fn flex_with_latest(changes: Value) -> Value {
    let mut block = json!({ "id": "essay", "title": "Draft title", "kind": "flexible", "duration_min": 90,
                            "days": [0, 1, 2, 3, 4], "priority": 2, "energy": "low", "course": "History",
                            "latest": "Thursday 21:00" });
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

fn save(
    db: &TestDb,
    user: i64,
    week_start: &str,
    blocks: Value,
    revision: i64,
) -> Result<Value, ServiceError> {
    save_week(
        &db.path,
        user,
        &json!({ "week_start": week_start, "blocks": blocks, "revision": revision }),
    )
}

fn listed(db: &TestDb, user: i64, week_start: &str) -> Vec<Value> {
    let now = parse_moment("2026-11-05T19:00").unwrap();
    views::homework(&db.path, user, week_start, true, now).unwrap()["assignments"]
        .as_array()
        .unwrap()
        .clone()
}

fn titled<'a>(items: &'a [Value], title: &str) -> &'a Value {
    items.iter().find(|item| item["title"] == title).unwrap()
}

#[test]
fn a_weekday_deadline_makes_the_homework_if_missing_and_stores_a_session() {
    let db = TestDb::new("latest-create");
    let ana = db.account("ana");
    let session = json!({ "id": "essay", "title": "Draft title", "kind": "flexible", "duration_min": 90,
                          "days": [0, 1, 2, 3, 4], "priority": 2, "energy": "low", "earliest": null, "latest": null,
                          "start": null, "course": "History", "assignment_id": AID });
    assert_eq!(
        save(&db, ana, WEEK, json!([flex_with_latest(json!({}))]), 0).unwrap(),
        json!({ "week_start": WEEK, "blocks": [session], "revision": 1 })
    );
    assert_eq!(
        listed(&db, ana, WEEK),
        [json!({
            "id": AID, "title": "Draft title", "course": "History", "category": null, "priority": 2, "energy": "low",
            "spotify_url": null, "due": "2026-09-10T21:00", "estimate_min": 90, "focus_minutes": 0,
            "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 1, "planned_min": 90,
            "unplanned_min": 0, "done_min": 0, "session_weeks": [WEEK],
        })]
    );
}

#[test]
fn saving_it_again_does_not_change_the_homework_it_made() {
    let db = TestDb::new("latest-again");
    let ana = db.account("ana");
    save(&db, ana, WEEK, json!([flex_with_latest(json!({}))]), 0).unwrap();
    let again = save(
        &db,
        ana,
        WEEK,
        json!([flex_with_latest(
            json!({ "title": "Changed on the block", "duration_min": 45 })
        )]),
        1,
    )
    .unwrap();
    let block = &again["blocks"][0];
    assert_eq!(
        (
            &block["title"],
            &block["duration_min"],
            &block["assignment_id"]
        ),
        (&json!("Draft title"), &json!(45), &json!(AID))
    );
    let homework = &listed(&db, ana, WEEK)[0];
    assert_eq!(
        (
            &homework["title"],
            &homework["estimate_min"],
            &homework["due"],
            &homework["revision"]
        ),
        (
            &json!("Draft title"),
            &json!(90),
            &json!("2026-09-10T21:00"),
            &json!(1)
        )
    );
}

#[test]
fn a_save_from_an_old_revision_leaves_no_new_homework() {
    let db = TestDb::new("latest-stale");
    let ana = db.account("ana");
    let school = json!({ "id": "school", "title": "School", "kind": "locked", "duration_min": 390, "days": [0], "start": "08:00" });
    assert_eq!(
        save(&db, ana, WEEK, json!([school]), 0).unwrap()["revision"],
        1
    );
    assert!(matches!(
        save(&db, ana, WEEK, json!([flex_with_latest(json!({}))]), 0),
        Err(ServiceError::Refused(Refusal::Conflict(ref words))) if words == WEEK_CONFLICT
    ));
    assert!(listed(&db, ana, WEEK).is_empty());
    let saved = weeks::read_week(&db.path, ana, WEEK).unwrap();
    assert_eq!(saved["revision"], 1);
    assert_eq!(saved["blocks"].as_array().unwrap().len(), 1);
    assert_eq!(saved["blocks"][0]["id"], "school");
}

#[test]
fn a_homework_session_with_a_weekday_deadline_is_refused() {
    let db = TestDb::new("latest-both");
    let ana = db.account("ana");
    assert!(matches!(
        save(
            &db,
            ana,
            WEEK,
            json!([flex_with_latest(json!({ "assignment_id": AID }))]),
            0
        ),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

/// 23:45 for 15 minutes ends at 24:00. That instant is the next date at 00:00, not T24:00.
#[test]
fn a_done_block_ending_at_midnight_saves_and_reloads() {
    let db = TestDb::new("latest-midnight");
    let ana = db.account("ana");
    let reading = json!({ "id": "night", "title": "Night reading", "kind": "flexible", "duration_min": 15, "days": [0],
                          "start": "23:45", "priority": 3, "energy": "low", "latest": "Monday 23:59",
                          "completed": true, "completed_day": 0 });
    let saved = save(&db, ana, WEEK, json!([reading]), 0).unwrap();
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"][0]["start"],
        "23:45"
    );
    assert_eq!(
        titled(&listed(&db, ana, WEEK), "Night reading")["completed_at"],
        "2026-09-08T00:00"
    );
    let chunk = json!({ "id": "essay-1", "title": "Essay chunk", "kind": "locked", "duration_min": 15, "days": [0],
                        "start": "23:45", "priority": 3, "energy": "medium", "pomodoro_parent_id": "essay",
                        "pomodoro_role": "work", "pomodoro_index": 1, "completed": true });
    save(
        &db,
        ana,
        WEEK,
        json!([chunk]),
        saved["revision"].as_i64().unwrap(),
    )
    .unwrap();
    // The app opening the database again.
    flexweek_store::initialize(&db.path, "2026-11-02").unwrap();
    let items = listed(&db, ana, WEEK);
    let homework = titled(&items, "Essay chunk");
    assert_eq!(homework["completed_at"], "2026-09-08T00:00");
    let block = weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"][0].clone();
    assert_eq!(
        (
            &block["start"],
            &block["completed"],
            &block["assignment_id"]
        ),
        (&json!("23:45"), &json!(true), &homework["id"])
    );
}

#[test]
fn done_at_midnight_on_the_last_day_stays_on_the_last_day() {
    let block = json!({ "start": "23:45", "duration_min": 15, "completed_day": 3 });
    assert_eq!(
        completed_at_for_block("2099-12-28", &block).unwrap(),
        "2099-12-31T23:59"
    );
}

/// 23:45 to 24:00 on 31 December 2099 has no next date. That instant is 23:59 on the last day.
#[test]
fn a_done_block_on_the_last_day_ending_at_midnight_saves() {
    let db = TestDb::new("latest-last-day");
    let ana = db.account("ana");
    let night = json!({ "id": "night", "title": "Night reading", "kind": "flexible", "duration_min": 15, "days": [3],
                        "start": "23:45", "priority": 3, "energy": "low", "latest": "Thursday 23:59",
                        "completed": true, "completed_day": 3 });
    save(&db, ana, "2099-12-28", json!([night]), 0).unwrap();
    assert_eq!(
        titled(&listed(&db, ana, "2099-12-28"), "Night reading")["completed_at"],
        "2099-12-31T23:59"
    );
}
