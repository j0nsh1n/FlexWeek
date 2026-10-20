//! A write reaches the sync ledger. `add_homework` of "Essay", due
//! 2026-10-23T21:00, estimate 90 stores that homework and one session in the
//! week of Monday 2026-10-19. `flexweek_sync::scan` on a copy then has a
//! `sync_record` for the assignment and for `"<week>/<id>"` with deleted = 0.
//! `export_since` from this computer and `apply_batch` on a second database
//! keep the title, the estimate, and that block.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path};
use flexweek_store::{initialize, insert_preferences, insert_user, open_connection, open_session};
use flexweek_sync::{apply_batch, export_since, migrate, scan, set_account, set_device};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const WEEK: &str = "2026-10-19";
const ACCOUNT: &str = "mcp-ledger-account";
const NOW_MS: i64 = NOW_UNIX * 1000;

struct World {
    data_arg: String,
    database_arg: String,
    user: i64,
}

fn signed_in(name: &str) -> World {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database_arg = dir.join("flexweek.db").to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), WEEK).expect("schema");
    let conn = open_connection(Path::new(&database_arg)).expect("open");
    let user = insert_user(&conn, "ada", "hash").expect("user");
    insert_preferences(&conn, user, 1).expect("preferences");
    open_session(&conn, TOKEN, user, NOW_UNIX, true).expect("session");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let session = session_path(&data_arg, &database_arg);
    if let Some(parent) = session.parent() {
        std::fs::create_dir_all(parent).expect("signed-in directory");
    }
    std::fs::write(&session, format!("{{\"token\":\"{TOKEN}\"}}")).expect("session file");
    std::fs::set_permissions(&session, std::fs::Permissions::from_mode(0o600)).expect("mode");
    World {
        data_arg,
        database_arg,
        user,
    }
}

fn is_error(response: &Value) -> Option<bool> {
    response.pointer("/result/isError").and_then(Value::as_bool)
}

fn body_of(response: &Value) -> Value {
    let text = response
        .pointer("/result/content/0/text")
        .and_then(Value::as_str)
        .unwrap_or("");
    serde_json::from_str(text).unwrap_or(Value::Null)
}

fn ledger_deleted(
    conn: &flexweek_store::Connection,
    user: i64,
    entity: &str,
    key: &str,
) -> Option<i64> {
    conn.query_row(
        "SELECT deleted FROM sync_record WHERE user_id = ?1 AND entity = ?2 AND key = ?3",
        (user, entity, key),
        |row| row.get(0),
    )
    .ok()
}

fn json_row(conn: &flexweek_store::Connection, sql: &str, params: (&str, i64)) -> Option<Value> {
    let text: String = conn.query_row(sql, params, |row| row.get(0)).ok()?;
    serde_json::from_str(&text).ok()
}

fn block_named(blocks: &Value, id: &str) -> Option<Value> {
    blocks.as_array().and_then(|items| {
        items
            .iter()
            .find(|block| block.get("id").and_then(Value::as_str) == Some(id))
            .cloned()
    })
}

#[test]
fn a_write_reaches_the_sync_ledger() {
    let world = signed_in("sync-ledger");
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
    ]);
    server.handshake();
    let response = server.call(
        "add_homework",
        json!({
            "operation_id": "op-sync-essay",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "add_homework must succeed, got {response}"
    );
    let body = body_of(&response);
    let assignment_id = body
        .pointer("/result/assignment/id")
        .and_then(Value::as_str)
        .unwrap_or("");
    assert!(
        !assignment_id.is_empty(),
        "add_homework names the assignment, got {body}"
    );
    let session_ids = body
        .pointer("/result/session_ids")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    assert!(
        !session_ids.is_empty(),
        "add_homework plans a session, got {body}"
    );
    let session_id = session_ids[0].as_str().unwrap_or("");
    assert!(
        !session_id.is_empty(),
        "the session id is text, got {session_ids:?}"
    );
    let block_key = format!("{WEEK}/{session_id}");

    let source = open_connection(Path::new(&world.database_arg)).expect("open source");
    source
        .execute_batch("PRAGMA wal_checkpoint(TRUNCATE)")
        .expect("checkpoint");
    drop(source);
    let copy_path = Path::new(&world.database_arg).with_file_name("ledger-copy.db");
    std::fs::copy(&world.database_arg, &copy_path).expect("copy the database");
    let mut copy = open_connection(&copy_path).expect("open copy");
    let migrated = migrate(&copy);
    assert!(
        migrated.is_ok(),
        "the copy accepts the sync schema, got {migrated:?}"
    );
    let device = set_device(&copy, "desktop", "desktop");
    assert!(device.is_ok(), "the copy is this computer, got {device:?}");
    let account = set_account(&copy, world.user, ACCOUNT);
    assert!(
        account.is_ok(),
        "the copy keeps ada's account, got {account:?}"
    );
    let scanned = scan(&mut copy, world.user, NOW_MS);
    assert!(
        scanned.is_ok(),
        "scan of the signed-in account failed, got {scanned:?}"
    );
    assert_eq!(
        ledger_deleted(&copy, world.user, "assignment", assignment_id),
        Some(0),
        "the assignment {assignment_id} is on the sync ledger with deleted = 0"
    );
    assert_eq!(
        ledger_deleted(&copy, world.user, "block", &block_key),
        Some(0),
        "the block {block_key} is on the sync ledger with deleted = 0"
    );

    let exported = export_since(&copy, world.user, 0, "phone", 500);
    assert!(
        exported.is_ok(),
        "export_since from this computer failed, got {exported:?}"
    );
    let exported = exported.unwrap_or_else(|_| unreachable!());
    let phone_path = Path::new(&world.database_arg).with_file_name("phone.db");
    initialize(&phone_path, WEEK).expect("phone schema");
    let mut phone = open_connection(&phone_path).expect("open phone");
    let phone_schema = migrate(&phone);
    assert!(
        phone_schema.is_ok(),
        "the phone accepts the sync schema, got {phone_schema:?}"
    );
    let phone_device = set_device(&phone, "phone", "phone");
    assert!(
        phone_device.is_ok(),
        "the second database is the phone, got {phone_device:?}"
    );
    let applied = apply_batch(&mut phone, &exported, NOW_MS);
    assert!(applied.is_ok(), "apply_batch failed, got {applied:?}");
    let applied = applied.unwrap_or_else(|_| unreachable!());
    assert!(
        applied.applied > 0,
        "the phone applies the batch, got {applied:?}"
    );
    assert_eq!(
        applied.quarantined, 0,
        "the batch is not quarantined, got {applied:?}"
    );

    let phone_user: Option<i64> = phone
        .query_row("SELECT id FROM users WHERE username = 'ada'", [], |row| {
            row.get(0)
        })
        .ok();
    assert!(phone_user.is_some(), "the phone receives the account ada");
    let phone_user = phone_user.unwrap_or(0);
    let phone_assignment = json_row(
        &phone,
        "SELECT body FROM assignments WHERE id = ?1 AND user_id = ?2",
        (assignment_id, phone_user),
    );
    assert!(
        phone_assignment.is_some(),
        "the phone has assignment {assignment_id}"
    );
    let phone_assignment = phone_assignment.unwrap_or(Value::Null);
    assert_eq!(
        phone_assignment.get("title"),
        Some(&json!("Essay")),
        "the phone keeps the title, got {phone_assignment}"
    );
    assert_eq!(
        phone_assignment.get("estimate_min"),
        Some(&json!(90)),
        "the phone keeps the 90 minute estimate, got {phone_assignment}"
    );
    let phone_week = json_row(
        &phone,
        "SELECT blocks FROM weeks WHERE week_start = ?1 AND user_id = ?2",
        (WEEK, phone_user),
    )
    .unwrap_or(Value::Null);
    assert!(
        phone_week.as_array().is_some(),
        "the phone has the week {WEEK}, got {phone_week}"
    );
    let phone_block = block_named(&phone_week, session_id);
    assert!(
        phone_block.is_some(),
        "the phone has block {block_key}, got {phone_week}"
    );
    let phone_block = phone_block.unwrap_or(Value::Null);
    assert_eq!(
        phone_block.get("title"),
        Some(&json!("Essay")),
        "the phone block keeps the title, got {phone_block}"
    );
    assert_eq!(
        phone_block.get("duration_min"),
        Some(&json!(90)),
        "the phone block keeps the 90 minute estimate, got {phone_block}"
    );
    assert_eq!(
        phone_block.get("days"),
        Some(&json!([0, 1, 2, 3, 4])),
        "the session covers the days through Friday 2026-10-23, got {phone_block}"
    );
    let source = open_connection(Path::new(&world.database_arg)).expect("reopen source");
    let source_week = json_row(
        &source,
        "SELECT blocks FROM weeks WHERE week_start = ?1 AND user_id = ?2",
        (WEEK, world.user),
    )
    .unwrap_or(Value::Null);
    assert!(
        source_week.as_array().is_some(),
        "the signed-in week {WEEK} was saved, got {source_week}"
    );
    let source_block = block_named(&source_week, session_id);
    assert!(
        source_block.is_some(),
        "the signed-in week holds {session_id}"
    );
    assert_eq!(
        phone_block,
        source_block.unwrap_or(Value::Null),
        "the phone block matches the block this computer saved"
    );
}
