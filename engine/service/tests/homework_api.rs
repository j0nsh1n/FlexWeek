//! The Homework list and its sessions on the Week screen, as docs/stage1-contract.md describes them: saving
//! and listing homework, the minutes planned, unplanned and done, deleting homework with its sessions, and
//! the batch saves that must keep all or nothing. Expected values are from the contract. The Rust twins of
//! backend/tests/test_homework_api.py (its request-header check goes with the server in P2).

use flexweek_engine::plan::parse_moment;
use flexweek_service::changes::apply_changes;
use flexweek_service::homework_saves::{ASSIGNMENT_CONFLICT, save_homework};
use flexweek_service::records::{HOMEWORK_UNKNOWN, delete_homework};
use flexweek_service::week_saves::{
    ASSIGNMENT_LIMIT, ASSIGNMENT_UNKNOWN, WEEK_CONFLICT, save_week,
};
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Map, Value, json};

const WEEK_ONE: &str = "2026-09-07";
const WEEK_TWO: &str = "2026-09-14";

/// A homework as the app sends it, with `revision`; `changes` replace single fields.
fn assignment(id: &str, changes: Value) -> Value {
    let mut body = json!({
        "id": id, "title": "Essay", "course": "History", "category": null, "priority": 2, "energy": "low",
        "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    });
    merge(&mut body, changes);
    body
}

/// The same homework as a batch carries it: the revision beside it, not inside.
fn content(id: &str, changes: Value) -> Value {
    let mut body = assignment(id, changes);
    body.as_object_mut().unwrap().shift_remove("revision");
    body
}

fn session(id: &str, homework: &str, changes: Value) -> Value {
    let mut block = json!({
        "id": id, "title": "stale title", "kind": "flexible", "duration_min": 60, "days": [0],
        "priority": 3, "energy": "medium", "assignment_id": homework,
    });
    merge(&mut block, changes);
    block
}

fn merge(into: &mut Value, changes: Value) {
    let fields: &mut Map<String, Value> = into.as_object_mut().unwrap();
    for (key, value) in changes.as_object().unwrap() {
        fields.insert(key.clone(), value.clone());
    }
}

fn put(db: &TestDb, user: i64, body: &Value) -> Result<Value, ServiceError> {
    save_homework(&db.path, user, body["id"].as_str().unwrap(), body)
}

fn week(
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

fn listed(db: &TestDb, user: i64, week_start: &str, include_completed: bool) -> Vec<Value> {
    let now = parse_moment("2026-09-07T08:00").unwrap();
    views::homework(&db.path, user, week_start, include_completed, now).unwrap()["assignments"]
        .as_array()
        .unwrap()
        .clone()
}

fn ids(items: &[Value]) -> Vec<&str> {
    items
        .iter()
        .map(|item| item["id"].as_str().unwrap())
        .collect()
}

fn read(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

fn batch(db: &TestDb, user: i64, given: Value) -> Result<Value, ServiceError> {
    apply_changes(
        &db.path,
        user,
        &given,
        "0123456789abcdef",
        "2026-09-07T08:00",
    )
}

fn refused<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn conflict(words: &str) -> Refusal {
    Refusal::Conflict(words.to_string())
}

/// A session as the week answers it: written out in full, with its homework's title, course and colours.
fn rewritten(id: &str, days: Value) -> Value {
    json!({
        "id": id, "title": "Essay", "kind": "flexible", "duration_min": 60, "days": days, "priority": 2,
        "energy": "low", "earliest": null, "latest": null, "start": null, "course": "History",
        "assignment_id": "hw-essay",
    })
}

#[test]
fn a_new_homework_is_revision_1_and_saving_it_again_unchanged_keeps_that() {
    let db = TestDb::new("hw-create");
    let ana = db.account("ana");
    let one = assignment("hw-essay", json!({ "revision": 1 }));
    assert_eq!(
        put(&db, ana, &assignment("hw-essay", json!({}))).unwrap(),
        one
    );
    assert_eq!(
        put(&db, ana, &assignment("hw-essay", json!({}))).unwrap(),
        one
    );
    assert_eq!(
        put(&db, ana, &assignment("hw-essay", json!({ "revision": 0 }))).unwrap(),
        one
    );
    let mut item = one;
    merge(
        &mut item,
        json!({ "planned_min": 0, "unplanned_min": 120, "done_min": 0, "session_weeks": [] }),
    );
    assert_eq!(listed(&db, ana, WEEK_ONE, false), [item]);
}

#[test]
fn a_change_saved_from_an_old_revision_is_refused_and_keeps_the_homework() {
    let db = TestDb::new("hw-stale");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    assert_eq!(
        refused(put(
            &db,
            ana,
            &assignment("hw-essay", json!({ "title": "New title" }))
        )),
        conflict(ASSIGNMENT_CONFLICT)
    );
    assert_eq!(listed(&db, ana, WEEK_ONE, false)[0]["title"], "Essay");
}

#[test]
fn open_homework_is_listed_by_due_and_finished_homework_only_when_asked_for() {
    let db = TestDb::new("hw-order");
    let ana = db.account("ana");
    put(
        &db,
        ana,
        &assignment(
            "later",
            json!({ "title": "Later", "due": "2026-09-16T12:00" }),
        ),
    )
    .unwrap();
    put(
        &db,
        ana,
        &assignment(
            "sooner",
            json!({ "title": "Sooner", "due": "2026-09-14T08:00" }),
        ),
    )
    .unwrap();
    let done = json!({
        "title": "Done", "due": "2026-09-08T09:00", "completed": true, "completed_at": "2026-09-08T10:00",
    });
    put(&db, ana, &assignment("done", done)).unwrap();
    assert_eq!(ids(&listed(&db, ana, WEEK_ONE, false)), ["sooner", "later"]);
    assert_eq!(
        ids(&listed(&db, ana, WEEK_ONE, true)),
        ["done", "sooner", "later"]
    );
}

#[test]
fn a_due_with_no_time_sorts_after_a_timed_due_on_the_same_day() {
    let db = TestDb::new("hw-allday");
    let ana = db.account("ana");
    put(
        &db,
        ana,
        &assignment("allday", json!({ "title": "All day", "due": "2026-09-15" })),
    )
    .unwrap();
    put(
        &db,
        ana,
        &assignment(
            "morning",
            json!({ "title": "Morning", "due": "2026-09-15T09:00" }),
        ),
    )
    .unwrap();
    assert_eq!(
        ids(&listed(&db, ana, WEEK_ONE, false)),
        ["morning", "allday"]
    );
}

#[test]
fn planned_minutes_count_open_sessions_in_the_week_shown_and_later_ones() {
    let db = TestDb::new("hw-planned");
    let ana = db.account("ana");
    put(
        &db,
        ana,
        &assignment("hw-essay", json!({ "estimate_min": 180 })),
    )
    .unwrap();
    let first = session("w1", "hw-essay", json!({ "duration_min": 60, "days": [6] }));
    let second = session("w2", "hw-essay", json!({ "duration_min": 45, "days": [0] }));
    week(&db, ana, WEEK_ONE, json!([first]), 0).unwrap();
    week(&db, ana, WEEK_TWO, json!([second]), 0).unwrap();
    let one = &listed(&db, ana, WEEK_ONE, false)[0];
    let two = &listed(&db, ana, WEEK_TWO, false)[0];
    assert_eq!(
        (&one["planned_min"], &one["unplanned_min"]),
        (&json!(105), &json!(75))
    );
    assert_eq!(
        (&two["planned_min"], &two["unplanned_min"]),
        (&json!(45), &json!(135))
    );
}

#[test]
fn done_minutes_count_sessions_ticked_done_in_every_saved_week() {
    let db = TestDb::new("hw-done");
    let ana = db.account("ana");
    put(
        &db,
        ana,
        &assignment("hw-essay", json!({ "estimate_min": 180 })),
    )
    .unwrap();
    let ticked = |id: &str, minutes: i64, day: i64| {
        session(
            id,
            "hw-essay",
            json!({ "duration_min": minutes, "days": [day], "start": "09:00", "completed": true }),
        )
    };
    week(&db, ana, WEEK_ONE, json!([ticked("w1", 60, 0)]), 0).unwrap();
    week(&db, ana, WEEK_TWO, json!([ticked("w2", 45, 0)]), 0).unwrap();
    for week_start in [WEEK_ONE, WEEK_TWO] {
        let item = &listed(&db, ana, week_start, false)[0];
        assert_eq!(item["done_min"], 105, "{week_start}");
        assert_eq!(item["planned_min"], 0, "{week_start}");
    }
}

#[test]
fn a_homework_lists_the_weeks_that_hold_its_sessions() {
    let db = TestDb::new("hw-weeks");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    week(
        &db,
        ana,
        WEEK_ONE,
        json!([session("w1", "hw-essay", json!({}))]),
        0,
    )
    .unwrap();
    assert_eq!(
        listed(&db, ana, WEEK_TWO, false)[0]["session_weeks"],
        json!([WEEK_ONE])
    );
}

#[test]
fn a_saved_session_takes_its_homeworks_fields_and_another_account_cannot_name_it() {
    let db = TestDb::new("hw-rewrite");
    let ana = db.account("ana");
    let ben = db.account("ben");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    let saved = week(
        &db,
        ana,
        WEEK_ONE,
        json!([session("w1", "hw-essay", json!({ "days": [6] }))]),
        0,
    )
    .unwrap();
    let expected =
        json!({ "week_start": WEEK_ONE, "blocks": [rewritten("w1", json!([6]))], "revision": 1 });
    assert_eq!(saved, expected);
    assert_eq!(read(&db, ana, WEEK_ONE), expected);
    put(
        &db,
        ana,
        &assignment(
            "hw-essay",
            json!({ "title": "Renamed essay", "revision": 1 }),
        ),
    )
    .unwrap();
    let loaded = read(&db, ana, WEEK_ONE);
    assert_eq!(
        loaded["revision"], 1,
        "renaming the homework rewrote the week"
    );
    assert_eq!(loaded["blocks"][0]["title"], "Renamed essay");
    assert_eq!(
        refused(week(
            &db,
            ben,
            WEEK_ONE,
            json!([session("w1", "hw-essay", json!({}))]),
            0
        )),
        Refusal::Invalid(ASSIGNMENT_UNKNOWN.to_string())
    );
    assert_eq!(
        read(&db, ben, WEEK_ONE),
        json!({ "week_start": WEEK_ONE, "blocks": [], "revision": 0 })
    );
}

/// Two saved weeks, each with one session of the essay; answers the delete.
fn essay_in_two_weeks(db: &TestDb, user: i64) -> Value {
    put(db, user, &assignment("hw-essay", json!({}))).unwrap();
    week(
        db,
        user,
        WEEK_ONE,
        json!([session("w1", "hw-essay", json!({ "days": [6] }))]),
        0,
    )
    .unwrap();
    week(
        db,
        user,
        WEEK_TWO,
        json!([session("w2", "hw-essay", json!({ "days": [0] }))]),
        0,
    )
    .unwrap();
    delete_homework(&db.path, user, "hw-essay", Some(1)).unwrap()
}

#[test]
fn deleting_a_homework_removes_its_sessions_in_every_week_and_moves_those_weeks_on() {
    let db = TestDb::new("hw-delete");
    let ana = db.account("ana");
    let deleted = essay_in_two_weeks(&db, ana);
    assert_eq!(
        deleted["changed_weeks"],
        json!([{ "week_start": WEEK_ONE, "revision": 2 }, { "week_start": WEEK_TWO, "revision": 2 }])
    );
    assert_eq!(
        deleted["removed_sessions"][WEEK_ONE],
        json!([rewritten("w1", json!([6]))])
    );
    for week_start in [WEEK_ONE, WEEK_TWO] {
        assert_eq!(
            read(&db, ana, week_start),
            json!({ "week_start": week_start, "blocks": [], "revision": 2 })
        );
    }
    assert!(listed(&db, ana, WEEK_ONE, false).is_empty());
    assert_eq!(
        refused(delete_homework(&db.path, ana, "hw-essay", Some(1))),
        Refusal::NotFound(HOMEWORK_UNKNOWN.to_string())
    );
}

#[test]
fn a_delete_from_an_old_revision_is_refused_and_keeps_the_homework() {
    let db = TestDb::new("hw-delete-stale");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    assert_eq!(
        refused(delete_homework(&db.path, ana, "hw-essay", Some(0))),
        conflict(ASSIGNMENT_CONFLICT)
    );
    assert_eq!(ids(&listed(&db, ana, WEEK_ONE, false)), ["hw-essay"]);
}

#[test]
fn a_batch_with_one_stale_homework_saves_none_of_them() {
    let db = TestDb::new("hw-batch-stale");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    put(
        &db,
        ana,
        &assignment(
            "other",
            json!({ "title": "Other", "due": "2026-09-16T12:00" }),
        ),
    )
    .unwrap();
    let given = json!({ "weeks": [], "assignments": [
        { "id": "hw-essay", "assignment": content("hw-essay", json!({ "title": "Moved" })), "revision": 1 },
        { "id": "other", "assignment": content("other", json!({ "title": "Nope" })), "revision": 0 },
    ] });
    assert_eq!(
        refused(batch(&db, ana, given)),
        conflict(ASSIGNMENT_CONFLICT)
    );
    let titles: Vec<(String, String)> = listed(&db, ana, WEEK_ONE, false)
        .iter()
        .map(|item| {
            (
                item["id"].as_str().unwrap().into(),
                item["title"].as_str().unwrap().into(),
            )
        })
        .collect();
    assert_eq!(
        titles,
        [
            ("hw-essay".into(), "Essay".into()),
            ("other".into(), "Other".into())
        ]
    );
}

#[test]
fn a_batch_that_deletes_a_homework_but_keeps_its_session_saves_nothing() {
    let db = TestDb::new("hw-batch-orphan");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    let kept = session("w1", "hw-essay", json!({ "days": [6] }));
    week(&db, ana, WEEK_ONE, json!([kept]), 0).unwrap();
    let given = json!({
        "weeks": [{ "week_start": WEEK_ONE, "blocks": [kept], "revision": 1 }],
        "assignments": [{ "id": "hw-essay", "assignment": null, "revision": 1 }],
    });
    assert_eq!(
        refused(batch(&db, ana, given)),
        Refusal::Invalid(ASSIGNMENT_UNKNOWN.to_string())
    );
    assert_eq!(ids(&listed(&db, ana, WEEK_ONE, false)), ["hw-essay"]);
    let saved = read(&db, ana, WEEK_ONE);
    assert_eq!(saved["revision"], 1);
    assert_eq!(
        (
            &saved["blocks"][0]["id"],
            &saved["blocks"][0]["assignment_id"]
        ),
        (&json!("w1"), &json!("hw-essay"))
    );
}

#[test]
fn saving_back_the_week_read_after_a_delete_keeps_its_revision() {
    let db = TestDb::new("hw-resave");
    let ana = db.account("ana");
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
        "priority": 1, "energy": "medium", "start": "08:00",
    });
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    week(
        &db,
        ana,
        WEEK_ONE,
        json!([school, session("w1", "hw-essay", json!({ "days": [6] }))]),
        0,
    )
    .unwrap();
    delete_homework(&db.path, ana, "hw-essay", Some(1)).unwrap();
    let loaded = read(&db, ana, WEEK_ONE);
    assert_eq!(loaded["revision"], 2);
    assert_eq!(ids(loaded["blocks"].as_array().unwrap()), ["school"]);
    let again = week(&db, ana, WEEK_ONE, loaded["blocks"].clone(), 2).unwrap();
    assert_eq!(
        again["revision"], 2,
        "saving the same week made a new revision"
    );
    assert_eq!(read(&db, ana, WEEK_ONE)["revision"], 2);
}

#[test]
fn a_batch_with_a_good_homework_and_a_stale_week_saves_neither() {
    let db = TestDb::new("hw-batch-week-stale");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    week(
        &db,
        ana,
        WEEK_ONE,
        json!([session("w1", "hw-essay", json!({ "days": [6] }))]),
        0,
    )
    .unwrap();
    let given = json!({
        "weeks": [{ "week_start": WEEK_ONE, "blocks": [session("w1", "hw-essay", json!({ "days": [0] }))],
                    "revision": 0 }],
        "assignments": [{ "id": "hw-essay", "assignment": content("hw-essay", json!({ "title": "Moved" })),
                          "revision": 1 }],
    });
    assert_eq!(refused(batch(&db, ana, given)), conflict(WEEK_CONFLICT));
    assert_eq!(listed(&db, ana, WEEK_ONE, false)[0]["title"], "Essay");
    let saved = read(&db, ana, WEEK_ONE);
    assert_eq!(
        (&saved["revision"], &saved["blocks"][0]["days"]),
        (&json!(1), &json!([6]))
    );
}

/// Undo of a delete: the homework and every session it took away come back in one batch.
#[test]
fn a_batch_puts_back_a_deleted_homework_with_every_session_it_removed() {
    let db = TestDb::new("hw-undo");
    let ana = db.account("ana");
    let deleted = essay_in_two_weeks(&db, ana);
    let weeks: Vec<Value> = deleted["changed_weeks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| {
            let start = item["week_start"].as_str().unwrap();
            json!({ "week_start": start, "blocks": deleted["removed_sessions"][start], "revision": item["revision"] })
        })
        .collect();
    let given = json!({
        "weeks": weeks,
        "assignments": [{ "id": "hw-essay", "assignment": content("hw-essay", json!({})), "revision": 0 }],
    });
    batch(&db, ana, given).unwrap();
    for (week_start, id) in [(WEEK_ONE, "w1"), (WEEK_TWO, "w2")] {
        let saved = read(&db, ana, week_start);
        assert_eq!(ids(saved["blocks"].as_array().unwrap()), [id]);
        assert_eq!(saved["blocks"][0]["assignment_id"], "hw-essay");
    }
    let item = &listed(&db, ana, WEEK_ONE, false)[0];
    assert_eq!(
        (&item["id"], &item["revision"]),
        (&json!("hw-essay"), &json!(1))
    );
}

#[test]
fn an_account_holds_at_most_one_thousand_homework() {
    let db = TestDb::new("hw-limit");
    let ana = db.account("ana");
    put(&db, ana, &assignment("hw-essay", json!({}))).unwrap();
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    for index in 0..999 {
        let body = content(
            &format!("seed-{index}"),
            json!({ "title": format!("Seed {index}"), "due": "2026-09-20T12:00" }),
        );
        conn.execute(
            "INSERT INTO assignments(user_id, id, body, revision) VALUES (?1, ?2, ?3, 1)",
            rusqlite::params![ana, body["id"].as_str().unwrap(), body.to_string()],
        )
        .unwrap();
    }
    drop(conn);
    let over = assignment(
        "one-too-many",
        json!({ "title": "Overflow", "due": "2026-09-21T12:00" }),
    );
    assert_eq!(
        refused(put(&db, ana, &over)),
        Refusal::Invalid(ASSIGNMENT_LIMIT.to_string())
    );
    assert_eq!(listed(&db, ana, WEEK_ONE, false).len(), 1000);
}
