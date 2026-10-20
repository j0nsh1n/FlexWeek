//! The kept session file, checked on every tool call.
//! A loop over the tool list asserts the list is not empty first.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use common::{
    KEPT_FOR, NOW_ISO, NOW_UNIX, Server, read_arguments, scratch, session_path, tool_error_text,
    tool_names, tool_ok_text,
};
use flexweek_store::{
    digest, initialize, insert_assignment, insert_preferences, insert_user, open_connection,
    open_session,
};
use serde_json::{Value, json};

const PLEASE_SIGN_IN: &str = "Please sign in";
const NOT_A_SESSION: &str = "That is not a FlexWeek session.";
const SESSION_ENDED: &str = "Your session ended. Sign in again.";
const READABLE_BY_OTHERS: &str = "This session file is readable by other people.";
const ACCOUNT_CHANGED: &str = "Account changed. Please sign in again.";

const ADA: &str = "abcdefghijklmnopqrstuvwxyz012345";
const BEA: &str = "zyxwvutsrqponmlkjihgfedcba543210";

struct World {
    data_arg: String,
    database_arg: String,
    session: PathBuf,
}

fn world(name: &str) -> World {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database = dir.join("flexweek.db");
    let database_arg = database.to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), "2026-10-19").expect("schema");
    let session = session_path(&data_arg, &database_arg);
    World {
        data_arg,
        database_arg,
        session,
    }
}

fn sign_in(world: &World, username: &str, token: &str) -> i64 {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let user = insert_user(&conn, username, "hash").expect("user");
    insert_preferences(&conn, user, 1).expect("preferences");
    open_session(&conn, token, user, NOW_UNIX, true).expect("session");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    user
}

fn put_session(path: &Path, body: &str, mode: u32) {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).expect("signed-in directory");
    }
    std::fs::write(path, body).expect("session file");
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode)).expect("mode");
}

fn put_token(path: &Path, token: &str, mode: u32) {
    put_session(path, &format!("{{\"token\":\"{token}\"}}"), mode);
}

fn mode_bits(path: &Path) -> u32 {
    std::fs::metadata(path)
        .expect("session file still exists")
        .permissions()
        .mode()
        & 0o777
}

fn boot(world: &World) -> Server {
    Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
    ])
}

fn refuse_every(server: &mut Server, sentence: &str) {
    let listed = server.request("tools/list", json!({}), 2);
    let names = tool_names(&listed);
    assert!(!names.is_empty(), "tools/list must not be empty");
    for (offset, name) in names.iter().enumerate() {
        let response = server.call(name, read_arguments(name), 10 + offset as i64);
        assert_eq!(
            tool_error_text(&response),
            Some(sentence),
            "{name} must refuse with the session sentence, got {response}"
        );
    }
}

fn bytes(path: &str) -> Vec<u8> {
    std::fs::read(path).expect("database file")
}

fn counts(path: &str) -> Vec<(String, i64)> {
    let conn = open_connection(Path::new(path)).expect("open");
    [
        "users",
        "sessions",
        "weeks",
        "assignments",
        "routines",
        "restore_points",
    ]
    .into_iter()
    .map(|table| {
        let sql = format!("SELECT COUNT(*) FROM {table}");
        let count: i64 = conn.query_row(&sql, (), |row| row.get(0)).expect("count");
        (table.to_string(), count)
    })
    .collect()
}

fn assignment(id: &str, title: &str) -> String {
    json!({
        "id": id,
        "title": title,
        "due": "2026-10-21T21:00",
        "estimate_min": 30,
        "focus_minutes": 0,
        "completed": false,
    })
    .to_string()
}

#[test]
fn a_missing_session_file_refuses_every_tool() {
    let world = world("missing");
    let before_bytes = bytes(&world.database_arg);
    let before_counts = counts(&world.database_arg);
    let mut server = boot(&world);
    server.handshake();
    refuse_every(&mut server, PLEASE_SIGN_IN);
    assert_eq!(
        bytes(&world.database_arg),
        before_bytes,
        "a missing session must not change the database file"
    );
    assert_eq!(
        counts(&world.database_arg),
        before_counts,
        "a missing session must not change row counts"
    );
}

#[test]
fn a_malformed_session_file_is_not_a_session() {
    let broken = world("malformed");
    put_session(&broken.session, "{", 0o600);
    let before_bytes = bytes(&broken.database_arg);
    let before_counts = counts(&broken.database_arg);
    let mut server = boot(&broken);
    server.handshake();
    refuse_every(&mut server, NOT_A_SESSION);
    assert_eq!(
        bytes(&broken.database_arg),
        before_bytes,
        "a malformed session must not change the database file"
    );
    assert_eq!(
        counts(&broken.database_arg),
        before_counts,
        "a malformed session must not change row counts"
    );

    let short = world("short-token");
    put_token(&short.session, "too-short", 0o600);
    let mut server = boot(&short);
    server.handshake();
    refuse_every(&mut server, NOT_A_SESSION);
}

#[test]
fn a_wrong_token_asks_the_student_to_sign_in() {
    let world = world("wrong-token");
    sign_in(&world, "ada", ADA);
    put_token(&world.session, BEA, 0o600);
    let before_bytes = bytes(&world.database_arg);
    let before_counts = counts(&world.database_arg);
    let mut server = boot(&world);
    server.handshake();
    refuse_every(&mut server, PLEASE_SIGN_IN);
    assert_eq!(
        bytes(&world.database_arg),
        before_bytes,
        "an unknown token must not change the database file"
    );
    assert_eq!(
        counts(&world.database_arg),
        before_counts,
        "an unknown token must not change row counts"
    );
}

#[test]
fn an_expired_session_row_ends_the_session() {
    let world = world("expired");
    sign_in(&world, "ada", ADA);
    put_token(&world.session, ADA, 0o600);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute(
        "UPDATE sessions SET expires = 1 WHERE token_hash = ?1",
        [digest(ADA)],
    )
    .expect("expire the row");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let before_bytes = bytes(&world.database_arg);
    let before_counts = counts(&world.database_arg);
    let mut server = boot(&world);
    server.handshake();
    refuse_every(&mut server, SESSION_ENDED);
    assert_eq!(
        bytes(&world.database_arg),
        before_bytes,
        "an expired session must not change the database file"
    );
    assert_eq!(
        counts(&world.database_arg),
        before_counts,
        "an expired session must not change row counts"
    );
}

#[test]
fn a_session_file_others_can_read_is_refused() {
    let world = world("readable");
    sign_in(&world, "ada", ADA);
    put_token(&world.session, ADA, 0o644);
    let before_bytes = bytes(&world.database_arg);
    let before_counts = counts(&world.database_arg);
    let mut server = boot(&world);
    server.handshake();
    refuse_every(&mut server, READABLE_BY_OTHERS);
    assert_eq!(
        mode_bits(&world.session),
        0o644,
        "a refusal must not chmod the session file"
    );
    assert_eq!(
        bytes(&world.database_arg),
        before_bytes,
        "a readable session must not change the database file"
    );
    assert_eq!(
        counts(&world.database_arg),
        before_counts,
        "a readable session must not change row counts"
    );
}

#[test]
fn a_private_session_is_accepted_and_its_mode_stays() {
    let world = world("private");
    sign_in(&world, "ada", ADA);
    put_token(&world.session, ADA, 0o600);
    let mut server = boot(&world);
    server.handshake();
    let response = server.call("whoami", json!({}), 2);
    let text = tool_ok_text(&response).unwrap_or("");
    let body: Value = serde_json::from_str(text).unwrap_or(Value::Null);
    assert_eq!(
        body.get("username").and_then(Value::as_str),
        Some("ada"),
        "whoami names the signed-in account, got {response}"
    );
    assert_eq!(
        body.get("session_expires").and_then(Value::as_i64),
        Some(NOW_UNIX + KEPT_FOR),
        "a kept session is renewed for thirty days"
    );
    let folder = Path::new(&world.data_arg)
        .file_name()
        .expect("data folder")
        .to_string_lossy();
    assert_eq!(
        body.get("data_folder_name").and_then(Value::as_str),
        Some(folder.as_ref()),
        "data_folder_name is the folder name"
    );
    assert!(
        body.get("token").is_none(),
        "whoami must not return the token"
    );
    assert!(!text.contains(ADA), "whoami must not return the token");
    assert_eq!(
        mode_bits(&world.session),
        0o600,
        "the server must not change a private session file"
    );
}

#[test]
fn a_deleted_session_row_refuses_the_next_call() {
    let world = world("revoked");
    sign_in(&world, "ada", ADA);
    put_token(&world.session, ADA, 0o600);
    let mut server = boot(&world);
    server.handshake();
    let first = server.call("whoami", json!({}), 2);
    let first_body: Value =
        serde_json::from_str(tool_ok_text(&first).unwrap_or("")).unwrap_or(Value::Null);
    assert_eq!(
        first_body.get("username").and_then(Value::as_str),
        Some("ada"),
        "the session works until the row is deleted, got {first}"
    );
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute("DELETE FROM sessions", ())
        .expect("delete the session");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let before_bytes = bytes(&world.database_arg);
    let before_counts = counts(&world.database_arg);
    let second = server.call("whoami", json!({}), 3);
    assert_eq!(
        tool_error_text(&second),
        Some(PLEASE_SIGN_IN),
        "a deleted session row is not signed in, got {second}"
    );
    assert_eq!(
        bytes(&world.database_arg),
        before_bytes,
        "the refusal must not change the database file"
    );
    assert_eq!(
        counts(&world.database_arg),
        before_counts,
        "the refusal must not change row counts"
    );
}

#[test]
fn a_session_for_another_database_and_sibling_files_are_not_the_session() {
    let world = world("siblings");
    sign_in(&world, "ada", ADA);
    let other = session_path(&world.data_arg, &format!("{}-other", world.database_arg));
    put_token(&other, ADA, 0o600);
    let stem = world
        .session
        .file_stem()
        .expect("stem")
        .to_string_lossy()
        .into_owned();
    let parent = world.session.parent().expect("parent");
    put_token(&parent.join(format!("{stem}.seen")), ADA, 0o600);
    put_token(&parent.join(format!("{stem}.look.json")), ADA, 0o600);
    let mut server = boot(&world);
    server.handshake();
    refuse_every(&mut server, PLEASE_SIGN_IN);
}

#[test]
fn a_second_user_is_the_only_account_the_tools_read() {
    let world = world("second-user");
    let ada = sign_in(&world, "ada", ADA);
    let bea = sign_in(&world, "bea", BEA);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        ada,
        "ada-secret",
        &assignment("ada-secret", "AdaSecret"),
    )
    .expect("ada work");
    insert_assignment(
        &conn,
        bea,
        "bea-essay",
        &assignment("bea-essay", "BeaEssay"),
    )
    .expect("bea work");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    put_token(&world.session, BEA, 0o600);
    let mut server = boot(&world);
    server.handshake();
    let who = server.call("whoami", json!({}), 2);
    let body: Value = serde_json::from_str(tool_ok_text(&who).unwrap_or("")).unwrap_or(Value::Null);
    assert_eq!(
        body.get("username").and_then(Value::as_str),
        Some("bea"),
        "whoami is the session's account, not the first row, got {who}"
    );
    let homework = server.call("list_homework", json!({"week_start": "2026-10-19"}), 3);
    let text = tool_ok_text(&homework).unwrap_or("");
    let listed: Value = serde_json::from_str(text).unwrap_or(Value::Null);
    let items = listed.get("assignments").and_then(Value::as_array);
    assert!(
        items.is_some_and(|rows| !rows.is_empty()),
        "the second user's homework must not be empty, got {homework}"
    );
    let items = items.expect("asserted");
    let ids: Vec<&str> = items
        .iter()
        .filter_map(|item| item.get("id").and_then(Value::as_str))
        .collect();
    assert_eq!(
        ids,
        vec!["bea-essay"],
        "the session reads only that account's homework"
    );
    assert!(
        !text.contains("AdaSecret"),
        "the first user's homework is not reachable"
    );
}

#[test]
fn a_changed_account_is_refused() {
    let world = world("changed");
    sign_in(&world, "ada", ADA);
    sign_in(&world, "bea", BEA);
    put_token(&world.session, BEA, 0o600);
    let mut server = boot(&world);
    server.handshake();
    let first = server.call("whoami", json!({}), 2);
    let first_body: Value =
        serde_json::from_str(tool_ok_text(&first).unwrap_or("")).unwrap_or(Value::Null);
    assert_eq!(
        first_body.get("username").and_then(Value::as_str),
        Some("bea"),
        "the call starts as the account that was signed in, got {first}"
    );
    put_token(&world.session, ADA, 0o600);
    let second = server.call("whoami", json!({}), 3);
    assert_eq!(
        tool_error_text(&second),
        Some(ACCOUNT_CHANGED),
        "a different account than at start is refused, got {second}"
    );
    let text = tool_error_text(&second).unwrap_or("");
    assert!(
        !text.contains("ada"),
        "the refusal must not name the other account"
    );
}
