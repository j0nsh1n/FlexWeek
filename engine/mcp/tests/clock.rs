//! The helper reads the clock on every call. Started without `--now` it is one long-lived process whose
//! session expiry, "today", restore-point time, past-time checks and planning all follow the time as
//! it moves, not the minute it started. `--now` stays a fixed clock.
//!
//! A test cannot wait days, so it moves a running helper's clock through the debug-build-only
//! `FLEXWEEK_MCP_TEST_CLOCK_FILE` (a file holding an RFC 3339 time, read on every call; see
//! `src/host.rs`). The first test uses no seam and the real clock.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use common::{
    KEPT_FOR, NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text,
};
use flexweek_store::{
    initialize, insert_preferences, insert_user, open_connection, open_session, set_standing,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const WEEK: &str = "2026-10-19";
const SESSION_ENDED: &str = "Your session ended. Sign in again.";
const CLOCK_VARIABLE: &str = "FLEXWEEK_MCP_TEST_CLOCK_FILE";

struct World {
    data_arg: String,
    database_arg: String,
    clock_file: PathBuf,
    user: i64,
}

/// A signed-in account whose session was opened at `opened_at` (unix seconds).
fn signed_in(name: &str, opened_at: i64) -> World {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database_arg = dir.join("flexweek.db").to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), WEEK).expect("schema");
    let conn = open_connection(Path::new(&database_arg)).expect("open");
    let user = insert_user(&conn, "ada", "hash").expect("user");
    insert_preferences(&conn, user, 1).expect("preferences");
    open_session(&conn, TOKEN, user, opened_at, true).expect("session");
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
        clock_file: dir.join("test-clock.txt"),
        user,
    }
}

fn set_clock(world: &World, stamp: &str) {
    std::fs::write(&world.clock_file, stamp).expect("clock file");
}

/// One long-lived helper with no `--now`, its clock moved through the file.
fn boot_live(world: &World, start: &str) -> Server {
    set_clock(world, start);
    let file = world.clock_file.to_string_lossy().into_owned();
    let mut server = Server::spawn_with_env(
        &[
            "--data-dir",
            &world.data_arg,
            "--database",
            &world.database_arg,
        ],
        &[(CLOCK_VARIABLE, &file)],
    );
    server.handshake();
    server
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
}

fn restore_labels(world: &World) -> Vec<String> {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut stmt = conn
        .prepare("SELECT label FROM restore_points WHERE user_id = ?1 ORDER BY seq")
        .expect("prepare");
    stmt.query_map((world.user,), |row| row.get::<_, String>(0))
        .expect("query")
        .map(|row| row.expect("row"))
        .collect()
}

fn fixed_block(id: &str, title: &str, start: &str, end: &str) -> Value {
    json!({
        "operation_id": id,
        "week_start": WEEK,
        "title": title,
        "days": [2],
        "start": start,
        "end": end
    })
}

fn real_unix() -> i64 {
    i64::try_from(
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("after 1970")
            .as_secs(),
    )
    .expect("fits")
}

fn local_date() -> String {
    let out = std::process::Command::new("date")
        .arg("+%F")
        .output()
        .expect("date runs");
    String::from_utf8_lossy(&out.stdout).trim().to_string()
}

#[test]
fn started_without_now_the_helper_reads_the_real_clock() {
    let world = signed_in("clock-real", real_unix());
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
    ]);
    server.handshake();
    let before = local_date();
    let today = body_of(&server.call("get_today", json!({}), 2));
    let after = local_date();
    let date = today["date"].as_str().unwrap_or("").to_string();
    assert!(
        date == before || date == after,
        "with no --now, today is the real date ({before}), got {today}"
    );
    let whoami = body_of(&server.call("whoami", json!({}), 3));
    let expires = whoami["session_expires"].as_i64().unwrap_or(0);
    assert!(
        (expires - (real_unix() + KEPT_FOR)).abs() < 120,
        "a kept session is renewed from the real time, got {whoami}"
    );
}

#[test]
fn a_session_that_runs_out_while_the_helper_is_open_is_refused() {
    let world = signed_in("clock-expiry", NOW_UNIX);
    let mut server = boot_live(&world, NOW_ISO);
    let first = body_of(&server.call("whoami", json!({}), 2));
    assert_eq!(
        first["username"],
        json!("ada"),
        "signed in at first, got {first}"
    );
    // The kept session lasts thirty days from the call above; this is thirty-one.
    set_clock(&world, "2026-11-21T12:00:00Z");
    let later = server.call("whoami", json!({}), 3);
    assert_eq!(
        tool_error_text(&later),
        Some(SESSION_ENDED),
        "past its expiry a read is refused, got {later}"
    );
}

#[test]
fn today_with_no_date_follows_the_day_changing_in_the_same_process() {
    let world = signed_in("clock-today", NOW_UNIX);
    let mut server = boot_live(&world, NOW_ISO);
    let wednesday = body_of(&server.call("get_today", json!({}), 2));
    assert_eq!(wednesday["date"], json!("2026-10-21"), "got {wednesday}");
    set_clock(&world, "2026-10-22T09:00:00Z");
    let next = body_of(&server.call("get_today", json!({}), 3));
    assert_eq!(
        next["date"],
        json!("2026-10-22"),
        "the next day is today after midnight, got {next}"
    );
}

#[test]
fn a_restore_point_carries_the_time_of_its_change() {
    let world = signed_in("clock-restore", NOW_UNIX);
    let mut server = boot_live(&world, NOW_ISO);
    set_clock(&world, "2026-10-21T15:47:00Z");
    let added = server.call(
        "add_block",
        fixed_block("op-late-dinner", "Dinner", "18:00", "18:30"),
        2,
    );
    assert_eq!(
        body_of(&added)["ok"],
        json!(true),
        "the add lands, got {added}"
    );
    let labels = restore_labels(&world);
    assert_eq!(labels.len(), 1, "one write, one point, got {labels:?}");
    assert!(
        labels[0].ends_with("2026-10-21T15:47"),
        "the point is stamped with the time of the change, not the 12:00 start, got {labels:?}"
    );
}

#[test]
fn the_past_time_check_uses_the_time_now() {
    let world = signed_in("clock-past", NOW_UNIX);
    {
        let conn = open_connection(Path::new(&world.database_arg)).expect("open");
        let study = json!({
            "id": "study", "title": "Study", "kind": "flexible", "duration_min": 30,
            "days": [2], "start": "20:00", "priority": 3, "energy": "medium"
        });
        conn.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
            (world.user, WEEK, json!([study]).to_string()),
        )
        .expect("week");
        if !conn.is_autocommit() {
            conn.execute_batch("COMMIT").expect("commit");
        }
    }
    let mut server = boot_live(&world, NOW_ISO);
    let moved_to = |server: &mut Server, id: &str, (start, end): (&str, &str), revision: i64| {
        server.call(
            "move_block",
            json!({
                "operation_id": id, "week_start": WEEK, "expected_revision": revision,
                "block_id": "study", "day": 2, "start": start, "end": end
            }),
            revision - 2,
        )
    };
    let open = moved_to(&mut server, "op-five-pm", ("17:00", "17:30"), 4);
    assert_eq!(
        tool_error_text(&open),
        None,
        "17:00 is still ahead at noon, got {open}"
    );
    set_clock(&world, "2026-10-21T18:00:00Z");
    let late = moved_to(&mut server, "op-four-pm", ("16:00", "16:30"), 5);
    let words = tool_error_text(&late).unwrap_or("");
    assert!(
        words.starts_with("That time has passed.") && words.contains("18:00"),
        "at 18:00 a 16:00 homework start has passed, got {late}"
    );
}

#[test]
fn planning_never_places_homework_before_the_time_now() {
    let world = signed_in("clock-plan", NOW_UNIX);
    {
        let conn = open_connection(Path::new(&world.database_arg)).expect("open");
        let school = json!({
            "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
            "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
        });
        set_standing(&conn, world.user, WEEK, &json!([school]).to_string()).expect("standing");
        if !conn.is_autocommit() {
            conn.execute_batch("COMMIT").expect("commit");
        }
    }
    let mut server = boot_live(&world, NOW_ISO);
    let added = server.call(
        "add_homework",
        json!({
            "operation_id": "op-clock-essay",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        2,
    );
    assert_eq!(
        body_of(&added)["ok"],
        json!(true),
        "the essay is added, got {added}"
    );
    // Wednesday after school ends at 15:00; at 23:30 only half an hour is left, and 90 minutes
    // do not fit in it.
    set_clock(&world, "2026-10-21T23:30:00Z");
    let planned = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-clock-plan", "week_start": WEEK, "day": 2}),
        3,
    ));
    assert_eq!(
        planned["result"]["placed"],
        json!([]),
        "Wednesday's hours before 23:30 are over, got {planned}"
    );
}

#[test]
fn now_is_still_a_fixed_clock_whatever_the_test_file_says() {
    let world = signed_in("clock-fixed", NOW_UNIX);
    set_clock(&world, "2026-12-25T12:00:00Z");
    let file = world.clock_file.to_string_lossy().into_owned();
    let mut server = Server::spawn_with_env(
        &[
            "--data-dir",
            &world.data_arg,
            "--database",
            &world.database_arg,
            "--now",
            NOW_ISO,
        ],
        &[(CLOCK_VARIABLE, &file)],
    );
    server.handshake();
    let today = body_of(&server.call("get_today", json!({}), 2));
    assert_eq!(
        today["date"],
        json!("2026-10-21"),
        "--now holds the time, got {today}"
    );
}
