//! "Spread it out" on a homework: the preview of sessions over several days writes nothing, belongs to one
//! account's open homework, and gives a free day its share before a day that already holds a session. The
//! Rust twins of backend/tests/test_spread_assignment_api.py.

use flexweek_engine::plan::parse_moment;
use flexweek_service::homework_saves::{SPREAD_DONE, save_homework, spread_preview};
use flexweek_service::records::HOMEWORK_UNKNOWN;
use flexweek_service::week_saves::save_week;
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-14";

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

fn spread(db: &TestDb, user: i64) -> Result<Value, ServiceError> {
    spread_preview(
        &db.path,
        user,
        "hw-essay",
        &json!({ "session_min": 60, "from_date": "2026-09-14" }),
    )
}

/// A 30-minute session of the essay already timed on Monday.
fn held_on_monday(db: &TestDb, user: i64) {
    let placed = json!({ "id": "hw-essay-held", "title": "Essay", "kind": "flexible", "duration_min": 30,
                         "days": [0], "start": "16:00", "priority": 2, "energy": "low", "assignment_id": "hw-essay" });
    save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK, "blocks": [placed], "revision": 0 }),
    )
    .unwrap();
}

fn shares(preview: &Value) -> Vec<(String, i64)> {
    preview["sessions"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| {
            (
                item["date"].as_str().unwrap().to_string(),
                item["duration_min"].as_i64().unwrap(),
            )
        })
        .collect()
}

fn share(date: &str, minutes: i64) -> (String, i64) {
    (date.to_string(), minutes)
}

#[test]
fn the_preview_writes_nothing_and_stays_on_one_homework() {
    let db = TestDb::new("spread-preview");
    let ana = db.account("ana");
    save_homework(&db.path, ana, "hw-essay", &assignment(json!({}))).unwrap();
    assert_eq!(
        spread(&db, ana).unwrap(),
        json!({
            "assignment_id": "hw-essay", "session_min": 60, "remaining_min": 0,
            "sessions": [
                { "week_start": "2026-09-14", "date": "2026-09-14", "days": [0], "duration_min": 60 },
                { "week_start": "2026-09-14", "date": "2026-09-15", "days": [1], "duration_min": 60 },
            ],
        })
    );
    let now = parse_moment("2026-09-14T08:00").unwrap();
    let listed =
        views::homework(&db.path, ana, WEEK, false, now).unwrap()["assignments"][0].clone();
    assert_eq!(listed["id"], "hw-essay");
    assert!(listed.get("pomodoro_parent_id").is_none());
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap(),
        json!({ "week_start": WEEK, "blocks": [], "revision": 0 })
    );
}

#[test]
fn another_accounts_homework_is_not_found() {
    let db = TestDb::new("spread-other");
    let ana = db.account("ana");
    let ben = db.account("ben");
    save_homework(&db.path, ana, "hw-essay", &assignment(json!({}))).unwrap();
    assert!(matches!(
        spread(&db, ben),
        Err(ServiceError::Refused(Refusal::NotFound(ref words))) if words == HOMEWORK_UNKNOWN
    ));
}

#[test]
fn finished_homework_cannot_be_spread() {
    let db = TestDb::new("spread-done");
    let ana = db.account("ana");
    let done = assignment(json!({ "completed": true, "completed_at": "2026-09-14T16:00" }));
    save_homework(&db.path, ana, "hw-essay", &done).unwrap();
    assert!(matches!(
        spread(&db, ana),
        Err(ServiceError::Refused(Refusal::Invalid(ref words))) if words == SPREAD_DONE
    ));
}

/// 120 minutes due Tuesday with 30 already timed on Monday: 90 uncovered, as shares of 60 and 30. Monday and
/// Tuesday are the only days, so the 60 takes Tuesday (no session there) and the 30 takes Monday, the held
/// day, once Tuesday has its share.
#[test]
fn the_day_of_a_placed_session_gets_its_share_last() {
    let db = TestDb::new("spread-held-last");
    let ana = db.account("ana");
    save_homework(&db.path, ana, "hw-essay", &assignment(json!({}))).unwrap();
    held_on_monday(&db, ana);
    assert_eq!(
        shares(&spread(&db, ana).unwrap()),
        [share("2026-09-15", 60), share("2026-09-14", 30)]
    );
}

/// Due Wednesday: three days. The held session is on Monday, so the two shares take Tuesday and Wednesday,
/// not Monday and Tuesday.
#[test]
fn a_free_day_gets_its_share_before_a_day_with_a_placed_session() {
    let db = TestDb::new("spread-free-first");
    let ana = db.account("ana");
    save_homework(
        &db.path,
        ana,
        "hw-essay",
        &assignment(json!({ "due": "2026-09-16T23:59", "estimate_min": 150 })),
    )
    .unwrap();
    held_on_monday(&db, ana);
    assert_eq!(
        shares(&spread(&db, ana).unwrap()),
        [share("2026-09-15", 60), share("2026-09-16", 60)]
    );
}
