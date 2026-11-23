//! A week that repeats a block id is refused wherever it comes from: a backup file being imported, or a
//! restore point being restored. The account stays as it was. The Rust twins of the two route tests left in
//! backend/tests/test_week_repeated_block_id.py (its store-level test moved to week_saves.rs and
//! transfer.rs earlier).

use flexweek_service::accounts::{self, Asker};
use flexweek_service::records::{restore, restore_preview};
use flexweek_service::transfer::{export_account, import_account, import_preview};
use flexweek_service::{Refusal, ServiceError, views, week_saves, weeks, with_db};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const WEEK: &str = "2026-09-14";
const NOW: &str = "2026-11-05T19:00";
const DOUBLED: &str =
    r#"Two blocks in this week share the id "school". Each block needs its own id."#;

fn school(title: &str) -> Value {
    json!({ "id": "school", "title": title, "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
            "priority": 1, "energy": "medium", "start": "08:00", "category": "School" })
}

/// Every week row and restore point of every account, as stored.
fn everything(db: &TestDb) -> (Vec<(i64, String, String, i64)>, i64) {
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    let mut stmt = conn
        .prepare("SELECT user_id, week_start, blocks, revision FROM weeks ORDER BY rowid")
        .unwrap();
    let weeks = stmt
        .query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();
    let points: i64 = conn
        .query_row("SELECT count(*) FROM restore_points", [], |row| row.get(0))
        .unwrap();
    (weeks, points)
}

#[test]
fn a_backup_file_with_a_doubled_id_is_refused_and_the_account_stays_as_it_was() {
    let db = TestDb::new("doubled-import");
    let at = Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    };
    let ana =
        accounts::register(&db.path, at, &mut Counting(0), "ana", PASSWORD, false, "").unwrap();
    let user = ana.account.id;
    week_saves::save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK, "blocks": [school("School")], "revision": 0 }),
    )
    .unwrap();
    let mut snapshot = export_account(
        &db.path,
        at,
        &ana.account,
        &json!({ "password": PASSWORD }),
        NOW,
    )
    .unwrap();
    let preview = import_preview(&db.path, user, &json!({ "snapshot": snapshot })).unwrap();
    let before = everything(&db);
    snapshot["weeks"][0]["blocks"] = json!([school("School"), school("School again")]);
    let refused_preview = import_preview(&db.path, user, &json!({ "snapshot": snapshot }));
    let refused_apply = import_account(
        &db.path,
        user,
        &json!({ "snapshot": snapshot, "state_token": preview["state_token"], "operation_id": "op-doubled" }),
        "0123456789abcdef",
        NOW,
    );
    for refused in [refused_preview, refused_apply] {
        match refused {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => {
                assert!(words.starts_with("Invalid input."), "{words}")
            }
            other => panic!("not refused: {other:?}"),
        }
    }
    assert_eq!(everything(&db), before);
    assert_eq!(
        weeks::read_week(&db.path, user, WEEK).unwrap()["blocks"][0]["title"],
        "School"
    );
}

#[test]
fn a_restore_point_with_a_doubled_id_is_refused_and_changes_nothing() {
    let db = TestDb::new("doubled-restore");
    let user = db.account("ana");
    week_saves::save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK, "blocks": [school("School")], "revision": 0 }),
    )
    .unwrap();
    let body = json!({ "weeks": [{ "week_start": WEEK, "blocks": [school("School"), school("School again")], "revision": 1 }],
                       "assignments": [] });
    with_db(&db.path, |conn| {
        Ok(flexweek_store::insert_restore_point(
            conn,
            user,
            "planted",
            "Planted",
            "2026-09-14T08:00:00",
            1,
            0,
            &body.to_string(),
            &[],
            20,
        )?)
    })
    .unwrap();
    let before = everything(&db);
    let listed_before = views::restore_points(&db.path, user).unwrap();
    let preview = restore_preview(&db.path, user, "planted").unwrap();
    let refused = restore(
        &db.path,
        user,
        "planted",
        &json!({ "state_token": preview["state_token"], "operation_id": "op-restore" }),
        "0123456789abcdef",
        NOW,
    );
    match refused {
        Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(words, DOUBLED),
        other => panic!("not refused in words: {other:?}"),
    }
    assert_eq!(everything(&db), before);
    assert_eq!(
        views::restore_points(&db.path, user).unwrap(),
        listed_before
    );
}
