//! Restore points (the "Undo" safety net and Settings > Restore points): making one, previewing and
//! restoring it, a save that makes one first, the 20-point cap, and that each belongs to one account. The
//! Rust twins of backend/tests/test_restore_points.py (its "restore point routes need a session" is the
//! sign-in check and goes with the server in P2).

use std::cell::Cell;

use flexweek_engine::plan::parse_moment;
use flexweek_service::changes::apply_changes;
use flexweek_service::homework_saves::save_homework;
use flexweek_service::records::{
    OPERATION_CONFLICT, RESTORE_STALE, RESTORE_UNKNOWN, create_restore_point, restore,
    restore_preview,
};
use flexweek_service::week_saves::{ASSIGNMENT_UNKNOWN, WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-14";
const NOW: &str = "2026-11-05T19:00";

/// Hands out a new restore-point name per call, as the app's random names would be.
struct Names(Cell<u64>);

impl Names {
    fn new() -> Self {
        Names(Cell::new(0))
    }
    fn next(&self) -> String {
        self.0.set(self.0.get() + 1);
        format!("{:016x}", self.0.get())
    }
}

fn school() -> Value {
    json!({ "id": "school", "title": "School", "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
            "priority": 1, "energy": "medium", "start": "08:00", "category": "School" })
}

fn assignment(title: &str, revision: i64) -> Value {
    json!({ "id": "hw-essay", "title": title, "course": null, "category": "Homework", "priority": 3,
            "energy": "medium", "spotify_url": null, "due": "2026-09-16T23:59", "estimate_min": 120,
            "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
            "revision": revision })
}

fn week(db: &TestDb, user: i64, blocks: Value, revision: i64) {
    save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK, "blocks": blocks, "revision": revision }),
    )
    .unwrap();
}

fn point(db: &TestDb, user: i64, names: &Names, label: &str, operation_id: &str) -> Value {
    create_restore_point(
        &db.path,
        user,
        &json!({ "label": label, "operation_id": operation_id }),
        &names.next(),
        NOW,
    )
    .unwrap()
}

fn points(db: &TestDb, user: i64) -> Vec<Value> {
    views::restore_points(&db.path, user).unwrap()["restore_points"]
        .as_array()
        .unwrap()
        .clone()
}

fn restore_with(
    db: &TestDb,
    user: i64,
    names: &Names,
    point_id: &str,
    token: &Value,
    operation_id: &str,
) -> Result<Value, ServiceError> {
    restore(
        &db.path,
        user,
        point_id,
        &json!({ "state_token": token, "operation_id": operation_id }),
        &names.next(),
        NOW,
    )
}

fn ids(blocks: &Value) -> Vec<String> {
    blocks
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["id"].as_str().unwrap().to_string())
        .collect()
}

fn refused<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn batch(db: &TestDb, user: i64, names: &Names, given: Value) -> Result<Value, ServiceError> {
    apply_changes(&db.path, user, &given, &names.next(), NOW)
}

#[test]
fn a_new_account_has_no_restore_points() {
    let db = TestDb::new("points-none");
    let ana = db.account("ana");
    assert_eq!(
        views::restore_points(&db.path, ana).unwrap(),
        json!({ "restore_points": [] })
    );
}

#[test]
fn a_restore_point_holds_the_weeks_and_homework_and_a_retry_gets_the_same_point() {
    let db = TestDb::new("points-make");
    let ana = db.account("ana");
    let names = Names::new();
    save_homework(&db.path, ana, "hw-essay", &assignment("Essay", 0)).unwrap();
    week(&db, ana, json!([school()]), 0);
    let made = point(&db, ana, &names, "Before finals week", "op-rp-1");
    assert_eq!(made["created_at"], NOW);
    assert_eq!(made["label"], "Before finals week");
    assert_eq!(
        (&made["weeks"], &made["assignments"]),
        (&json!(1), &json!(1))
    );
    assert!(made["id"].as_str().unwrap().starts_with("rp-"));
    assert_eq!(points(&db, ana), std::slice::from_ref(&made));
    assert_eq!(
        point(&db, ana, &names, "Before finals week", "op-rp-1"),
        made
    );
}

#[test]
fn restoring_after_a_preview_puts_the_account_back_and_keeps_a_point_from_before() {
    let db = TestDb::new("points-restore");
    let ana = db.account("ana");
    let names = Names::new();
    save_homework(&db.path, ana, "hw-essay", &assignment("Essay", 0)).unwrap();
    week(&db, ana, json!([school()]), 0);
    let point_id = point(&db, ana, &names, "School week", "op-rp-school")["id"]
        .as_str()
        .unwrap()
        .to_string();
    save_homework(&db.path, ana, "hw-essay", &assignment("Rewrite", 1)).unwrap();
    week(&db, ana, json!([]), 1);
    let preview = restore_preview(&db.path, ana, &point_id).unwrap();
    assert_eq!(preview["id"], point_id.as_str());
    assert_eq!(
        preview["changes"],
        json!({
            "weeks": { "added": [], "changed": [WEEK], "removed": [] },
            "assignments": { "added": [], "changed": [{ "id": "hw-essay", "title": "Essay" }], "removed": [] },
        })
    );
    let token = preview["state_token"].clone();
    let restored = restore_with(&db, ana, &names, &point_id, &token, "op-restore-1").unwrap();
    assert_eq!(
        ids(&weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"]),
        ["school"]
    );
    let now = parse_moment(NOW).unwrap();
    let homework = views::homework(&db.path, ana, WEEK, false, now).unwrap();
    assert_eq!(homework["assignments"][0]["title"], "Essay");
    let listed = points(&db, ana);
    assert!(
        listed[0]["label"]
            .as_str()
            .unwrap()
            .starts_with("Before restore — "),
        "{}",
        listed[0]
    );
    assert!(listed.iter().any(|item| item["id"] == point_id.as_str()));
    assert_eq!(
        restore_with(&db, ana, &names, &point_id, &token, "op-restore-1").unwrap(),
        restored
    );
}

#[test]
fn restoring_from_a_preview_that_is_out_of_date_is_refused_and_changes_nothing() {
    let db = TestDb::new("points-stale");
    let ana = db.account("ana");
    let names = Names::new();
    week(&db, ana, json!([school()]), 0);
    let point_id = point(&db, ana, &names, "School", "op-rp-stale")["id"]
        .as_str()
        .unwrap()
        .to_string();
    let token = restore_preview(&db.path, ana, &point_id).unwrap()["state_token"].clone();
    week(&db, ana, json!([]), 1);
    assert_eq!(
        refused(restore_with(
            &db,
            ana,
            &names,
            &point_id,
            &token,
            "op-restore-stale"
        )),
        Refusal::Conflict(RESTORE_STALE.to_string())
    );
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"],
        json!([])
    );
    assert_eq!(points(&db, ana)[0]["id"], point_id.as_str());
}

#[test]
fn a_save_that_asks_for_a_point_makes_none_when_its_week_is_out_of_date() {
    let db = TestDb::new("points-batch-stale");
    let ana = db.account("ana");
    let names = Names::new();
    week(&db, ana, json!([school()]), 0);
    let given = json!({ "operation_id": "op-clear-1", "snapshot_label": "Before clear week",
                        "weeks": [{ "week_start": WEEK, "blocks": [], "revision": 0 }], "assignments": [] });
    assert_eq!(
        refused(batch(&db, ana, &names, given)),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
    assert!(points(&db, ana).is_empty());
    assert_eq!(
        ids(&weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"]),
        ["school"]
    );
}

#[test]
fn a_save_that_asks_for_a_point_makes_it_then_writes_and_names_it_for_undo() {
    let db = TestDb::new("points-batch");
    let ana = db.account("ana");
    let names = Names::new();
    week(&db, ana, json!([school()]), 0);
    let given = json!({ "operation_id": "op-clear-2", "snapshot_label": "Before clear week",
                        "weeks": [{ "week_start": WEEK, "blocks": [], "revision": 1 }], "assignments": [] });
    let cleared = batch(&db, ana, &names, given.clone()).unwrap();
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"],
        json!([])
    );
    let listed = points(&db, ana);
    assert_eq!(
        (&listed[0]["label"], &listed[0]["weeks"]),
        (&json!("Before clear week"), &json!(1))
    );
    // The answer names the point it made, so the save's Undo can put it back.
    assert_eq!(cleared["restore_point"]["id"], listed[0]["id"]);
    assert_eq!(batch(&db, ana, &names, given).unwrap(), cleared);
    assert_eq!(points(&db, ana).len(), 1);
}

#[test]
fn an_operation_used_again_with_a_different_save_is_refused() {
    let db = TestDb::new("points-op-reuse");
    let ana = db.account("ana");
    let names = Names::new();
    batch(
        &db,
        ana,
        &names,
        json!({ "operation_id": "op-same", "weeks": [], "assignments": [] }),
    )
    .unwrap();
    let clash = json!({ "operation_id": "op-same", "weeks": [{ "week_start": WEEK, "blocks": [], "revision": 0 }],
                        "assignments": [] });
    assert_eq!(
        refused(batch(&db, ana, &names, clash)),
        Refusal::Conflict(OPERATION_CONFLICT.to_string())
    );
}

#[test]
fn only_the_newest_20_restore_points_are_kept() {
    let db = TestDb::new("points-cap");
    let ana = db.account("ana");
    let names = Names::new();
    let made: Vec<String> = (0..20)
        .map(|n| {
            point(
                &db,
                ana,
                &names,
                &format!("Point {n}"),
                &format!("op-cap-{n}"),
            )["id"]
                .as_str()
                .unwrap()
                .to_string()
        })
        .collect();
    let extra = point(&db, ana, &names, "Point 20", "op-cap-20")["id"]
        .as_str()
        .unwrap()
        .to_string();
    let remaining: Vec<String> = points(&db, ana)
        .iter()
        .map(|item| item["id"].as_str().unwrap().to_string())
        .collect();
    assert!(!remaining.contains(&made[0]));
    assert!(remaining.contains(&extra));
    assert_eq!(remaining.len(), 20);
}

#[test]
fn restoring_the_oldest_point_does_not_delete_it() {
    let db = TestDb::new("points-oldest");
    let ana = db.account("ana");
    let names = Names::new();
    let made: Vec<String> = (0..20)
        .map(|n| {
            point(
                &db,
                ana,
                &names,
                &format!("Point {n}"),
                &format!("op-keep-{n}"),
            )["id"]
                .as_str()
                .unwrap()
                .to_string()
        })
        .collect();
    let oldest = &made[0];
    let token = restore_preview(&db.path, ana, oldest).unwrap()["state_token"].clone();
    restore_with(&db, ana, &names, oldest, &token, "op-keep-oldest").unwrap();
    let remaining: Vec<String> = points(&db, ana)
        .iter()
        .map(|item| item["id"].as_str().unwrap().to_string())
        .collect();
    assert!(remaining.contains(oldest));
    assert_eq!(remaining.len(), 20);
}

#[test]
fn the_same_operation_in_two_accounts_makes_two_points() {
    let db = TestDb::new("points-two-accounts");
    let ana = db.account("ana");
    let ben = db.account("ben");
    let names = Names::new();
    let hers = point(&db, ana, &names, "Alice secret", "shared-op");
    let his = point(&db, ben, &names, "Bob point", "shared-op");
    assert_eq!(his["label"], "Bob point");
    assert_ne!(his["id"], hers["id"]);
    assert_eq!(points(&db, ana)[0]["label"], "Alice secret");
    assert_eq!(points(&db, ben)[0]["label"], "Bob point");
}

#[test]
fn a_save_that_asks_for_a_point_makes_none_when_it_names_unknown_homework() {
    let db = TestDb::new("points-batch-unknown");
    let ana = db.account("ana");
    let names = Names::new();
    let session = json!({ "id": "w1", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                          "priority": 3, "energy": "medium", "assignment_id": "missing" });
    let given = json!({ "snapshot_label": "Before bad write",
                        "weeks": [{ "week_start": WEEK, "blocks": [session], "revision": 0 }], "assignments": [] });
    assert_eq!(
        refused(batch(&db, ana, &names, given)),
        Refusal::Invalid(ASSIGNMENT_UNKNOWN.to_string())
    );
    assert!(points(&db, ana).is_empty());
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"],
        json!([])
    );
}

#[test]
fn another_account_can_not_list_preview_or_restore_my_points() {
    let db = TestDb::new("points-private");
    let ana = db.account("ana");
    let ben = db.account("ben");
    let names = Names::new();
    week(&db, ana, json!([school()]), 0);
    let point_id = point(&db, ana, &names, "Alice only", "op-alice")["id"]
        .as_str()
        .unwrap()
        .to_string();
    assert!(points(&db, ben).is_empty());
    assert_eq!(
        refused(restore_preview(&db.path, ben, &point_id)),
        Refusal::NotFound(RESTORE_UNKNOWN.to_string())
    );
    assert_eq!(
        refused(restore_with(
            &db,
            ben,
            &names,
            &point_id,
            &json!("nope"),
            "op-bob"
        )),
        Refusal::NotFound(RESTORE_UNKNOWN.to_string())
    );
    assert_eq!(points(&db, ana)[0]["id"], point_id.as_str());
}

#[test]
fn restore_points_with_the_same_id_stay_with_their_account() {
    let db = TestDb::new("points-same-id");
    let ana = db.account("ana");
    let ben = db.account("ben");
    let names = Names::new();
    let titled = |title: &str| {
        let mut block = school();
        block["title"] = json!(title);
        json!([block])
    };
    week(&db, ana, titled("Alice school"), 0);
    week(&db, ben, titled("Bob school"), 0);
    let hers = point(&db, ana, &names, "Alice", "op-1");
    let shared_id = hers["id"].as_str().unwrap().to_string();
    // Ben's point has the same id as Ana's but a different label, and it holds no weeks at all.
    rusqlite::Connection::open(&db.path)
        .unwrap()
        .execute(
            "INSERT INTO restore_points(user_id, id, label, created_at, weeks_count, assignments_count, body)
             VALUES (?1, ?2, 'Bob', '2026-09-14T08:00', 0, 0, '{\"weeks\":[],\"assignments\":[]}')",
            rusqlite::params![ben, shared_id],
        )
        .unwrap();
    let mine: Vec<(Value, Value)> = points(&db, ana)
        .iter()
        .map(|item| (item["id"].clone(), item["label"].clone()))
        .collect();
    assert_eq!(mine, [(json!(shared_id), json!("Alice"))]);
    assert_eq!(
        points(&db, ben),
        [
            json!({ "id": shared_id, "label": "Bob", "created_at": "2026-09-14T08:00", "weeks": 0, "assignments": 0 })
        ]
    );
    let preview = restore_preview(&db.path, ben, &shared_id).unwrap();
    assert_eq!(preview["id"], shared_id.as_str());
    // Ben's point holds no weeks, so his one week would go; Ana's point would only change hers.
    assert_eq!(
        preview["changes"],
        json!({ "weeks": { "added": [], "changed": [], "removed": [WEEK] },
                "assignments": { "added": [], "changed": [], "removed": [] } })
    );
    restore_with(
        &db,
        ben,
        &names,
        &shared_id,
        &preview["state_token"],
        "op-bob",
    )
    .unwrap();
    assert_eq!(
        weeks::read_week(&db.path, ben, WEEK).unwrap(),
        json!({ "week_start": WEEK, "blocks": [], "revision": 0 })
    );
    assert_eq!(
        weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"][0]["title"],
        "Alice school"
    );
    assert_eq!(
        refused(restore_preview(&db.path, ana, "rp-nothing")),
        Refusal::NotFound(RESTORE_UNKNOWN.to_string())
    );
}
