//! A block is keyed by (account, week, id): the weeks table's key is (user_id, week_start), and a week whose
//! block list repeats an id is refused, so the full key stays unique. The same id may repeat across weeks and
//! accounts (Setup's School is always "school"). The Rust twins of
//! backend/tests/regress184/test_regress_extra_block_keys.py (Sammy's finding 6); the store's own check is in
//! engine/store/tests/test_regress_extra_block_keys.rs.

use flexweek_engine::validate::week_request;
use flexweek_service::accounts::{self, Asker, SignedIn};
use flexweek_service::transfer::{export_account, import_preview};
use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const WEEK: &str = "2026-10-05";
const NEXT: &str = "2026-10-12";
const NOW: &str = "2026-11-05T19:00";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn register(db: &TestDb, name: &str, seed: u64) -> SignedIn {
    accounts::register(
        &db.path,
        at(),
        &mut Counting(seed),
        name,
        PASSWORD,
        false,
        "",
    )
    .unwrap()
}

fn school(title: &str) -> Value {
    json!({ "id": "school", "title": title, "kind": "locked", "category": "class", "start": "08:30",
            "duration_min": 405, "days": [0, 1, 2, 3, 4] })
}

fn put(
    db: &TestDb,
    user: i64,
    week: &str,
    blocks: Value,
    revision: i64,
) -> Result<Value, ServiceError> {
    save_week(
        &db.path,
        user,
        &json!({ "week_start": week, "blocks": blocks, "revision": revision }),
    )
}

fn rows_for(db: &TestDb, week: &str) -> i64 {
    db.sql()
        .query_row(
            "SELECT COUNT(*) FROM weeks WHERE week_start = ?1",
            [week],
            |row| row.get(0),
        )
        .unwrap()
}

fn first_title(db: &TestDb, user: i64, week: &str) -> Value {
    weeks::read_week(&db.path, user, week).unwrap()["blocks"][0]["title"].clone()
}

#[test]
fn the_weeks_table_key_is_user_and_week_start() {
    let db = TestDb::new("keys-table");
    let conn = db.sql();
    let mut stmt = conn.prepare("PRAGMA table_info(weeks)").unwrap();
    let mut key: Vec<(i64, String)> = stmt
        .query_map([], |row| {
            Ok((row.get::<_, i64>(5)?, row.get::<_, String>(1)?))
        })
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap()
        .into_iter()
        .filter(|(pk, _)| *pk > 0)
        .collect();
    key.sort();
    let names: Vec<&str> = key.iter().map(|(_, name)| name.as_str()).collect();
    assert_eq!(names, ["user_id", "week_start"]);
}

#[test]
fn a_week_that_repeats_a_block_id_is_refused_and_nothing_is_stored() {
    let db = TestDb::new("keys-repeat");
    let ann = register(&db, "keys_ann", 0).account.id;
    assert!(matches!(
        put(
            &db,
            ann,
            WEEK,
            json!([school("School"), school("School copy")]),
            0
        ),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
    let stored = weeks::read_week(&db.path, ann, WEEK).unwrap();
    assert_eq!(
        (&stored["blocks"], &stored["revision"]),
        (&json!([]), &json!(0))
    );
}

#[test]
fn the_week_check_names_the_repeated_id_rule() {
    let refused = week_request(&json!({ "blocks": [school("School"), school("School copy")] }))
        .err()
        .unwrap();
    assert!(refused.contains("block ids must be unique"), "{refused}");
}

#[test]
fn saving_a_week_again_upserts_it_in_place() {
    let db = TestDb::new("keys-upsert");
    let ann = register(&db, "keys_ann", 0).account.id;
    put(&db, ann, WEEK, json!([school("School")]), 0).unwrap();
    let second = put(&db, ann, WEEK, json!([school("School 9-3")]), 1).unwrap();
    assert_eq!(second["revision"], 2);
    assert_eq!(rows_for(&db, WEEK), 1);
    let titles: Vec<Value> = weeks::read_week(&db.path, ann, WEEK).unwrap()["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["title"].clone())
        .collect();
    assert_eq!(titles, [json!("School 9-3")]);
}

#[test]
fn a_stale_second_insert_of_the_same_week_is_a_conflict_not_a_second_row() {
    let db = TestDb::new("keys-stale");
    let ann = register(&db, "keys_ann", 0).account.id;
    put(&db, ann, WEEK, json!([school("School")]), 0).unwrap();
    assert!(matches!(
        put(&db, ann, WEEK, json!([school("Other")]), 0),
        Err(ServiceError::Refused(Refusal::Conflict(ref words))) if words == WEEK_CONFLICT
    ));
    assert_eq!(rows_for(&db, WEEK), 1);
}

#[test]
fn the_same_id_may_repeat_across_weeks_and_accounts() {
    let db = TestDb::new("keys-across");
    let ann = register(&db, "keys_ann", 0).account.id;
    put(&db, ann, WEEK, json!([school("School")]), 0).unwrap();
    put(&db, ann, NEXT, json!([school("School next")]), 0).unwrap();
    assert_eq!(first_title(&db, ann, WEEK), "School");
    let ben = register(&db, "keys_ben", 100).account.id;
    put(&db, ben, WEEK, json!([school("Ben school")]), 0).unwrap();
    assert_eq!(first_title(&db, ben, WEEK), "Ben school");
    assert_eq!(first_title(&db, ann, WEEK), "School");
}

#[test]
fn an_import_refuses_a_file_week_that_repeats_a_block_id() {
    let db = TestDb::new("keys-import");
    let ann = register(&db, "keys_ann", 0);
    put(&db, ann.account.id, WEEK, json!([school("School")]), 0).unwrap();
    let mut snapshot = export_account(
        &db.path,
        at(),
        &ann.account,
        &json!({ "password": PASSWORD }),
        NOW,
    )
    .unwrap();
    snapshot["weeks"][0]["blocks"]
        .as_array_mut()
        .unwrap()
        .push(school("School twin"));
    assert!(matches!(
        import_preview(&db.path, ann.account.id, &json!({ "snapshot": snapshot })),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}
