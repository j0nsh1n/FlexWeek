//! A save, delete, rename or import by one account leaves the rows of another account with the same ids
//! untouched. The Rust twins of backend/tests/test_one_accounts_writes_leave_the_other_alone.py (its limit
//! test moved to homework_saves.rs in P1).

use flexweek_engine::plan::parse_moment;
use flexweek_engine::validate::routine;
use flexweek_service::accounts::{self, Asker, SignedIn};
use flexweek_service::homework_saves::save_homework;
use flexweek_service::records::{delete_homework, save_routine};
use flexweek_service::transfer::{export_account, import_account, import_preview};
use flexweek_service::week_saves::save_week;
use flexweek_service::{views, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const WEEK_A: &str = "2026-09-07";
const WEEK_B: &str = "2026-09-14";
const WEEK_C: &str = "2026-09-21";
const NOW: &str = "2026-11-05T19:00";
/// Every table an account owns rows in.
const OWNED: [&str; 7] = [
    "weeks",
    "assignments",
    "routines",
    "restore_points",
    "operations",
    "preferences",
    "recovery_codes",
];

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn two(db: &TestDb) -> (SignedIn, SignedIn) {
    let mut entropy = Counting(0);
    let ana =
        accounts::register(&db.path, at(), &mut entropy, "alice", PASSWORD, false, "").unwrap();
    let ben = accounts::register(&db.path, at(), &mut entropy, "bob", PASSWORD, false, "").unwrap();
    (ana, ben)
}

fn assignment(changes: Value) -> Value {
    let mut body = json!({
        "id": "hw-essay", "title": "Essay", "course": null, "category": null, "priority": 2, "energy": "low",
        "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    });
    for (key, value) in changes.as_object().unwrap() {
        body[key] = value.clone();
    }
    body
}

fn routine_body(name: &str, revision: i64) -> Value {
    let mut body = routine(&json!({
        "id": "r1", "name": "Morning", "revision": 0,
        "blocks": [{ "template_id": "t1", "title": "Block", "days": [0, 1], "start": "08:00", "duration_min": 60 }],
    }))
    .unwrap()
    .to_value();
    body["name"] = json!(name);
    body["revision"] = json!(revision);
    body
}

fn session(id: &str) -> Value {
    json!({ "id": id, "title": "stale title", "kind": "flexible", "duration_min": 60, "days": [0], "priority": 3,
            "energy": "medium", "assignment_id": "hw-essay" })
}

fn school(id: &str) -> Value {
    json!({ "id": id, "title": "School", "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
            "priority": 1, "energy": "medium", "start": "08:00", "category": "School" })
}

fn put_week(db: &TestDb, user: i64, week_start: &str, blocks: Value) {
    save_week(
        &db.path,
        user,
        &json!({ "week_start": week_start, "blocks": blocks, "revision": 0 }),
    )
    .unwrap();
}

/// Every row one account owns, as stored, to compare before and after the other one acts.
fn account_rows(db: &TestDb, user: i64) -> Vec<(String, Vec<Vec<rusqlite::types::Value>>)> {
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    OWNED
        .iter()
        .map(|table| {
            let mut stmt = conn
                .prepare(&format!(
                    "SELECT * FROM {table} WHERE user_id = ?1 ORDER BY rowid"
                ))
                .unwrap();
            let columns = stmt.column_count();
            let rows = stmt
                .query_map([user], |row| {
                    (0..columns)
                        .map(|i| row.get::<_, rusqlite::types::Value>(i))
                        .collect()
                })
                .unwrap()
                .collect::<Result<Vec<Vec<_>>, _>>()
                .unwrap();
            ((*table).to_string(), rows)
        })
        .collect()
}

fn ids(blocks: &Value) -> Vec<&str> {
    blocks
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["id"].as_str().unwrap())
        .collect()
}

#[test]
fn deleting_homework_leaves_the_other_accounts_rows_with_the_same_id_alone() {
    let db = TestDb::new("writes-delete");
    let (ana, ben) = two(&db);
    let (a, b) = (ana.account.id, ben.account.id);
    save_homework(&db.path, a, "hw-essay", &assignment(json!({}))).unwrap();
    save_homework(
        &db.path,
        b,
        "hw-essay",
        &assignment(json!({ "title": "Bob's essay" })),
    )
    .unwrap();
    put_week(&db, a, WEEK_B, json!([session("a1"), school("school")]));
    put_week(&db, b, WEEK_B, json!([session("b1"), school("bob-keep")]));
    put_week(&db, b, WEEK_C, json!([session("b2")]));
    let before = account_rows(&db, b);
    let deleted = delete_homework(&db.path, a, "hw-essay", Some(1)).unwrap();
    assert_eq!(
        deleted["changed_weeks"],
        json!([{ "week_start": WEEK_B, "revision": 2 }])
    );
    assert_eq!(ids(&deleted["removed_sessions"][WEEK_B]), ["a1"]);
    assert_eq!(
        deleted["removed_sessions"]
            .as_object()
            .unwrap()
            .keys()
            .collect::<Vec<_>>(),
        [WEEK_B]
    );
    assert_eq!(
        ids(&weeks::read_week(&db.path, a, WEEK_B).unwrap()["blocks"]),
        ["school"]
    );
    assert_eq!(account_rows(&db, b), before);
}

#[test]
fn saving_and_renaming_homework_leaves_the_other_accounts_same_id_alone() {
    let db = TestDb::new("writes-rename");
    let (ana, ben) = two(&db);
    let (a, b) = (ana.account.id, ben.account.id);
    save_homework(
        &db.path,
        b,
        "hw-essay",
        &assignment(json!({ "title": "Bob's essay" })),
    )
    .unwrap();
    let before = account_rows(&db, b);
    assert_eq!(
        save_homework(&db.path, a, "hw-essay", &assignment(json!({}))).unwrap()["revision"],
        1
    );
    let renamed = save_homework(
        &db.path,
        a,
        "hw-essay",
        &assignment(json!({ "title": "Renamed", "revision": 1 })),
    )
    .unwrap();
    assert_eq!(renamed["revision"], 2);
    assert_eq!(account_rows(&db, b), before);
    let now = parse_moment(NOW).unwrap();
    let bobs: Vec<(Value, Value, Value)> = views::homework(&db.path, b, WEEK_A, false, now)
        .unwrap()["assignments"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| {
            (
                item["id"].clone(),
                item["title"].clone(),
                item["revision"].clone(),
            )
        })
        .collect();
    assert_eq!(bobs, [(json!("hw-essay"), json!("Bob's essay"), json!(1))]);
}

#[test]
fn a_deadline_one_account_turned_into_homework_is_still_made_for_the_other() {
    let db = TestDb::new("writes-deadline");
    let (ana, ben) = two(&db);
    let legacy = json!({ "id": "essay", "title": "Draft title", "kind": "flexible", "duration_min": 90,
                         "days": [0, 1, 2, 3, 4], "priority": 2, "energy": "low", "course": "History",
                         "latest": "Thursday 21:00" });
    for user in [ben.account.id, ana.account.id] {
        put_week(&db, user, WEEK_A, json!([legacy]));
    }
    let now = parse_moment(NOW).unwrap();
    let mine =
        views::homework(&db.path, ana.account.id, WEEK_A, false, now).unwrap()["assignments"]
            .clone();
    assert_eq!(mine.as_array().unwrap().len(), 1);
    let session = &weeks::read_week(&db.path, ana.account.id, WEEK_A).unwrap()["blocks"][0];
    assert_eq!(mine[0]["id"], session["assignment_id"]);
}

#[test]
fn renaming_a_routine_leaves_the_other_accounts_same_id_routine_alone() {
    let db = TestDb::new("writes-routine");
    let (ana, ben) = two(&db);
    let (a, b) = (ana.account.id, ben.account.id);
    save_routine(&db.path, a, "r1", &routine_body("Morning", 0), NOW).unwrap();
    save_routine(&db.path, b, "r1", &routine_body("Bob's", 0), NOW).unwrap();
    let before = account_rows(&db, b);
    let renamed = save_routine(&db.path, a, "r1", &routine_body("Evening", 1), NOW).unwrap();
    assert_eq!(
        (&renamed["name"], &renamed["revision"]),
        (&json!("Evening"), &json!(2))
    );
    assert_eq!(account_rows(&db, b), before);
    assert_eq!(
        views::routines(&db.path, b).unwrap()["routines"][0]["name"],
        "Bob's"
    );
}

#[test]
fn importing_into_one_account_leaves_the_other_accounts_rows_alone() {
    let db = TestDb::new("writes-import");
    let (ana, ben) = two(&db);
    let (a, b) = (ana.account.id, ben.account.id);
    save_routine(&db.path, a, "r1", &routine_body("Morning", 0), NOW).unwrap();
    save_routine(&db.path, b, "r1", &routine_body("Bob's", 0), NOW).unwrap();
    save_homework(&db.path, a, "hw-essay", &assignment(json!({}))).unwrap();
    save_homework(
        &db.path,
        b,
        "hw-essay",
        &assignment(json!({ "title": "Bob's essay" })),
    )
    .unwrap();
    put_week(&db, b, WEEK_B, json!([session("b1")]));
    let before = account_rows(&db, b);
    let mut snapshot = export_account(
        &db.path,
        at(),
        &ana.account,
        &json!({ "password": PASSWORD }),
        NOW,
    )
    .unwrap();
    snapshot["routines"][0]["name"] = json!("Evening");
    snapshot["assignments"][0]["body"]["title"] = json!("Renamed");
    let preview = import_preview(&db.path, a, &json!({ "snapshot": snapshot })).unwrap();
    import_account(
        &db.path,
        a,
        &json!({ "snapshot": snapshot, "state_token": preview["state_token"], "operation_id": "op-import" }),
        "0123456789abcdef",
        NOW,
    )
    .unwrap();
    assert_eq!(
        views::routines(&db.path, a).unwrap()["routines"][0]["name"],
        "Evening"
    );
    assert_eq!(account_rows(&db, b), before);
}
