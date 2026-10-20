//! stdout is protocol only. stderr names the tool and the outcome, and nothing about the person.
//! The server opens no socket. The tool list is the allow-list: reads stay read-only, and
//! delete_homework is destructive.

mod common;

use std::collections::BTreeSet;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_names};
use flexweek_store::{initialize, insert_preferences, insert_user, open_connection, open_session};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const READ_ONLY: &[&str] = &[
    "get_month",
    "get_today",
    "get_week",
    "list_homework",
    "list_restore_points",
    "list_routines",
    "whoami",
];
const ALLOWED: &[&str] = &[
    "add_homework",
    "delete_homework",
    "edit_homework",
    "get_month",
    "get_today",
    "get_week",
    "list_homework",
    "list_restore_points",
    "list_routines",
    "set_block_done",
    "set_homework_done",
    "whoami",
];

fn signed_in(name: &str) -> (String, String) {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database_arg = dir.join("flexweek.db").to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), "2026-10-19").expect("schema");
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
    (data_arg, database_arg)
}

fn boot(data_arg: &str, database_arg: &str) -> Server {
    Server::spawn(&[
        "--data-dir",
        data_arg,
        "--database",
        database_arg,
        "--now",
        NOW_ISO,
    ])
}

#[test]
fn tools_list_is_the_read_allow_list() {
    let (data_arg, database_arg) = signed_in("allow");
    let mut server = boot(&data_arg, &database_arg);
    server.handshake();
    let listed = server.request("tools/list", json!({}), 2);
    let names = tool_names(&listed);
    assert!(
        !names.is_empty(),
        "tools/list must not be empty, got {listed}"
    );
    assert_eq!(
        names.iter().map(String::as_str).collect::<BTreeSet<_>>(),
        ALLOWED.iter().copied().collect::<BTreeSet<_>>(),
        "tools/list must be exactly the allow-list"
    );
    let empty = Vec::new();
    let tools = listed
        .get("result")
        .and_then(|result| result.get("tools"))
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    assert!(!tools.is_empty(), "tools/list must not be empty");
    for tool in tools {
        let name = tool.get("name").and_then(Value::as_str).unwrap_or("");
        let read_only = READ_ONLY.contains(&name);
        assert_eq!(
            tool.get("annotations")
                .and_then(|notes| notes.get("readOnlyHint"))
                .and_then(Value::as_bool),
            Some(read_only),
            "{name} readOnlyHint must be {read_only}"
        );
        let destructive = tool
            .get("annotations")
            .and_then(|notes| notes.get("destructiveHint"))
            .and_then(Value::as_bool);
        if name == "delete_homework" {
            assert_eq!(
                destructive,
                Some(true),
                "delete_homework must be marked destructiveHint"
            );
        } else if !read_only {
            assert_eq!(
                destructive,
                Some(false),
                "{name} must not be marked destructiveHint"
            );
        }
        let lower = name.to_lowercase();
        for banned in ["password", "recover", "export", "account", "pair"] {
            assert!(!lower.contains(banned), "{name} must stay off this server");
        }
    }
}

#[test]
fn stderr_names_the_call_and_omits_the_token_username_and_title() {
    let (data_arg, database_arg) = signed_in("quiet");
    let mut server = boot(&data_arg, &database_arg);
    server.handshake();
    let _ = server.call("whoami", json!({"title": "DistinctTitleZz"}), 2);
    let err = server.stderr();
    assert!(
        err.contains("whoami ok") || err.contains("whoami error"),
        "each call is one stderr line naming the tool and ok or error, got {err}"
    );
    assert!(
        !err.contains(TOKEN),
        "stderr must not contain the token, got {err}"
    );
    assert!(
        !err.contains("ada"),
        "stderr must not contain the username, got {err}"
    );
    assert!(
        !err.contains("DistinctTitleZz"),
        "stderr must not contain a title sent in the call, got {err}"
    );
    let lines = server.stdout_lines();
    assert!(!lines.is_empty(), "the server must answer on stdout");
    for line in &lines {
        assert!(
            serde_json::from_str::<Value>(line).is_ok(),
            "stdout must be JSON-RPC lines, got {line}"
        );
        assert!(!line.contains(TOKEN), "stdout must not carry the token");
        assert!(
            !line.contains("DistinctTitleZz"),
            "stdout must not echo a title that was not stored"
        );
    }
}

#[test]
fn the_server_opens_no_socket() {
    let (data_arg, database_arg) = signed_in("socket");
    let mut server = boot(&data_arg, &database_arg);
    server.handshake();
    let _ = server.call("whoami", json!({}), 2);
    let fd_dir = format!("/proc/{}/fd", server.pid());
    let entries = std::fs::read_dir(&fd_dir).expect("proc fd");
    for entry in entries {
        let entry = entry.expect("fd entry");
        let target = std::fs::read_link(entry.path())
            .map(|path| path.to_string_lossy().into_owned())
            .unwrap_or_default();
        assert!(
            !target.contains("socket:"),
            "the server must not open a socket, got {target}"
        );
    }
}
