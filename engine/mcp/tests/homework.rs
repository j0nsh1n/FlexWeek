//! Homework and block writes. Expected values are the desktop rules and spec.md:
//! an estimate of 90 is one open session of 90 minutes (spec.md, a session is the
//! homework's planned time); 100 is refused because an estimate is a positive
//! multiple of 15. `controller.py` `add_homework` 1001-1015 creates that session,
//! 974-991 resizes the one session that still matches the old estimate,
//! `complete_homework` 1571-1578 then the finish cascade 1016-1028 mark it done.
//! `set_block_done` follows `agenda.rs` 359-366. Deletes remove the sessions in
//! every week (`assignments.rs` `delete_assignment`).

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_store::{
    initialize, insert_assignment, insert_preferences, insert_user, open_connection, open_session,
    save_assignment,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const REACHES: &str = "when FlexWeek is open on this computer with a phone paired";
const OPERATION_CONFLICT: &str = "This operation was already used with different data.";

struct World {
    data_arg: String,
    database_arg: String,
    user: i64,
}

fn signed_in(name: &str) -> World {
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
    World {
        data_arg,
        database_arg,
        user,
    }
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

fn is_error(response: &Value) -> Option<bool> {
    response.pointer("/result/isError").and_then(Value::as_bool)
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
}

fn count_assignments(database: &str, user: i64) -> i64 {
    let conn = open_connection(Path::new(database)).expect("open");
    conn.query_row(
        "SELECT COUNT(*) FROM assignments WHERE user_id = ?1",
        [user],
        |row| row.get(0),
    )
    .expect("count")
}

fn assignment_row(database: &str, user: i64, id: &str) -> Option<(String, i64)> {
    let conn = open_connection(Path::new(database)).expect("open");
    let mut stmt = conn
        .prepare("SELECT body, revision FROM assignments WHERE user_id = ?1 AND id = ?2")
        .expect("prepare");
    let mut rows = stmt.query((user, id)).expect("query");
    let row = rows.next().expect("row")?;
    Some((row.get(0).expect("body"), row.get(1).expect("revision")))
}

fn week_row(database: &str, user: i64, week: &str) -> Option<(Value, i64)> {
    let conn = open_connection(Path::new(database)).expect("open");
    let mut stmt = conn
        .prepare("SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2")
        .expect("prepare");
    let mut rows = stmt.query((user, week)).expect("query");
    let row = rows.next().expect("row")?;
    let text: String = row.get(0).expect("blocks");
    let revision: i64 = row.get(1).expect("revision");
    let blocks = serde_json::from_str(&text).unwrap_or(Value::Null);
    Some((blocks, revision))
}

fn blocks_with_assignment(blocks: &Value, id: &str) -> Vec<Value> {
    let Some(items) = blocks.as_array() else {
        return Vec::new();
    };
    items
        .iter()
        .filter(|block| block.get("assignment_id").and_then(Value::as_str) == Some(id))
        .cloned()
        .collect()
}

fn seed_essay(world: &World, weeks: &[(&str, i64, Value)]) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let body = json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-23T21:00",
        "estimate_min": 90,
        "priority": 3,
        "energy": "medium",
        "completed": false,
        "focus_minutes": 0,
        "focus_sessions": 0
    })
    .to_string();
    insert_assignment(&conn, world.user, "essay", &body).expect("assignment");
    for (week, revision, blocks) in weeks {
        conn.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, ?4)",
            (world.user, week, blocks.to_string(), revision),
        )
        .expect("week");
    }
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn essay_session(id: &str, days: &[i64], start: Option<&str>) -> Value {
    let mut block = json!({
        "id": id,
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": days,
        "priority": 3,
        "energy": "medium",
        "assignment_id": "essay"
    });
    if let Some(start) = start
        && let Some(map) = block.as_object_mut()
    {
        map.insert("start".into(), json!(start));
    }
    block
}

#[test]
fn add_homework_saves_one_open_session_of_the_estimate() {
    let world = signed_in("add-essay");
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "add_homework",
        json!({
            "operation_id": "op-add-essay",
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
    assert_eq!(
        body.get("ok"),
        Some(&json!(true)),
        "add returns ok, got {body}"
    );
    assert_eq!(
        body.get("revision"),
        Some(&json!(1)),
        "a new homework is saved at revision 1, got {body}"
    );
    assert_eq!(
        body.pointer("/result/assignment/title"),
        Some(&json!("Essay")),
        "the saved homework keeps the title, got {body}"
    );
    assert_eq!(
        body.pointer("/result/assignment/estimate_min"),
        Some(&json!(90)),
        "the saved homework keeps the 90 minute estimate, got {body}"
    );
    assert_eq!(
        body.get("reaches_phone"),
        Some(&json!(REACHES)),
        "a write tells the assistant when a paired phone hears it, got {body}"
    );
    let ids = body
        .pointer("/result/session_ids")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    assert_eq!(ids.len(), 1, "one session is planned, got {body}");
    let (blocks, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 1, "the current week is saved at revision 1");
    let sessions = blocks_with_assignment(
        &blocks,
        body.pointer("/result/assignment/id")
            .and_then(Value::as_str)
            .unwrap_or(""),
    );
    assert_eq!(
        sessions.len(),
        1,
        "the week holds one session, got {blocks}"
    );
    assert_eq!(
        sessions[0].get("duration_min"),
        Some(&json!(90)),
        "controller.py 1007 sets duration_min from the estimate, got {sessions:?}"
    );
    assert_eq!(
        sessions[0].get("days"),
        Some(&json!([0, 1, 2, 3, 4])),
        "a new session uses the days through Friday 2026-10-23, got {sessions:?}"
    );
    assert_ne!(
        sessions[0].get("completed"),
        Some(&json!(true)),
        "the new session is open"
    );
    assert!(
        assignment_row(
            &world.database_arg,
            world.user,
            body.pointer("/result/assignment/id")
                .and_then(Value::as_str)
                .unwrap_or("")
        )
        .is_some_and(|(_, stored)| stored == 1),
        "the assignment row is revision 1"
    );
}

#[test]
fn an_estimate_of_100_is_refused_and_writes_nothing() {
    let world = signed_in("add-100");
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "add_homework",
        json!({
            "operation_id": "op-estimate",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 100
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&response),
        Some("estimate_min must be a positive multiple of 15"),
        "spec refuses an estimate that is not a multiple of 15, got {response}"
    );
    assert_eq!(
        count_assignments(&world.database_arg, world.user),
        0,
        "a refused estimate writes no assignment"
    );
    assert!(
        week_row(&world.database_arg, world.user, "2026-10-19").is_none(),
        "a refused estimate writes no week"
    );
}

#[test]
fn operation_id_must_be_8_to_80_characters() {
    let world = signed_in("op-len");
    let mut server = boot(&world);
    server.handshake();
    let short = server.call(
        "add_homework",
        json!({
            "operation_id": "short",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&short),
        Some("String should have at least 8 characters"),
        "operation_id shorter than 8 is refused, got {short}"
    );
    let long_id = "x".repeat(81);
    let long = server.call(
        "add_homework",
        json!({
            "operation_id": long_id,
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        3,
    );
    assert_eq!(
        tool_error_text(&long),
        Some("String should have at most 80 characters"),
        "operation_id longer than 80 is refused, got {long}"
    );
    assert_eq!(
        count_assignments(&world.database_arg, world.user),
        0,
        "a bad operation id writes nothing"
    );
}

#[test]
fn the_same_operation_returns_the_first_answer_and_a_different_payload_conflicts() {
    let world = signed_in("retry-add");
    let mut server = boot(&world);
    server.handshake();
    let args = json!({
        "operation_id": "op-retry-1",
        "title": "Essay",
        "due": "2026-10-23T21:00",
        "estimate_min": 90
    });
    let first = server.call("add_homework", args.clone(), 2);
    assert_eq!(
        is_error(&first),
        Some(false),
        "add_homework must succeed, got {first}"
    );
    let second = server.call("add_homework", args, 3);
    assert_eq!(
        body_of(&first),
        body_of(&second),
        "the same operation id and arguments return the first answer"
    );
    assert_eq!(
        count_assignments(&world.database_arg, world.user),
        1,
        "a retry writes nothing"
    );
    let conflict = server.call(
        "add_homework",
        json!({
            "operation_id": "op-retry-1",
            "title": "Other",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        4,
    );
    assert_eq!(
        tool_error_text(&conflict),
        Some(OPERATION_CONFLICT),
        "the same operation id with different arguments is an error, got {conflict}"
    );
    assert_eq!(
        count_assignments(&world.database_arg, world.user),
        1,
        "a conflicting retry writes nothing"
    );
}

#[test]
fn edit_homework_resizes_the_one_session() {
    let world = signed_in("edit-one");
    seed_essay(
        &world,
        &[(
            "2026-10-19",
            4,
            json!([essay_session("sess-essay", &[2], None)]),
        )],
    );
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-edit-one",
            "id": "essay",
            "expected_revision": 1,
            "estimate_min": 45
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "edit_homework must succeed, got {response}"
    );
    let body = body_of(&response);
    assert_eq!(
        body.pointer("/result/assignment/estimate_min"),
        Some(&json!(45)),
        "the homework keeps the new estimate, got {body}"
    );
    assert_eq!(
        body.get("revision"),
        Some(&json!(2)),
        "an edit bumps the assignment revision, got {body}"
    );
    let (blocks, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    let sessions = blocks_with_assignment(&blocks, "essay");
    assert_eq!(sessions.len(), 1, "the one session stays, got {blocks}");
    assert_eq!(
        sessions[0].get("duration_min"),
        Some(&json!(45)),
        "controller.py 974-991 resizes the session that still matched the old estimate, got {sessions:?}"
    );
    assert_eq!(revision, 5, "the week revision bumps once");
    let again = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-edit-one",
            "id": "essay",
            "expected_revision": 1,
            "estimate_min": 45
        }),
        3,
    );
    assert_eq!(
        body_of(&response),
        body_of(&again),
        "retrying the edit returns the first answer"
    );
    let (_, revision_after) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision_after, 5, "a retry does not bump the week again");
}

#[test]
fn a_stale_expected_revision_writes_nothing() {
    let world = signed_in("stale-edit");
    seed_essay(
        &world,
        &[(
            "2026-10-19",
            4,
            json!([essay_session("sess-essay", &[2], None)]),
        )],
    );
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let changed = json!({
        "id": "essay",
        "title": "Kept",
        "due": "2026-10-23T21:00",
        "estimate_min": 90,
        "priority": 3,
        "energy": "medium",
        "completed": false,
        "focus_minutes": 0,
        "focus_sessions": 0
    });
    let encoded = flexweek_engine::snapshot::canonical(&changed);
    save_assignment(&conn, world.user, "essay", &encoded, 1, 1000).expect("bump");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-stale-ed",
            "id": "essay",
            "expected_revision": 1,
            "title": "Replaced"
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "a stale write returns the conflict object, got {response}"
    );
    assert_eq!(
        body_of(&response),
        json!({"error": "conflict", "current_revision": 2}),
        "a stale expected_revision returns the current revision and writes nothing"
    );
    let (stored, revision) =
        assignment_row(&world.database_arg, world.user, "essay").unwrap_or_default();
    assert_eq!(
        revision, 2,
        "the assignment revision stays at the intervening save"
    );
    assert!(
        stored.contains("Kept"),
        "the edit's title was not written, got {stored}"
    );
    let (blocks, week_revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(week_revision, 4, "the week was not written");
    let sessions = blocks_with_assignment(&blocks, "essay");
    assert_eq!(
        sessions.first().and_then(|block| block.get("duration_min")),
        Some(&json!(90)),
        "the session was not resized"
    );
}

#[test]
fn delete_homework_removes_the_sessions_in_both_weeks() {
    let world = signed_in("delete-two");
    seed_essay(
        &world,
        &[
            (
                "2026-10-12",
                1,
                json!([essay_session("sess-old", &[2], Some("16:00"))]),
            ),
            (
                "2026-10-19",
                4,
                json!([
                    essay_session("sess-new", &[2], Some("16:00")),
                    {
                        "id": "club",
                        "title": "Club",
                        "kind": "flexible",
                        "duration_min": 60,
                        "days": [1],
                        "start": "15:00"
                    }
                ]),
            ),
        ],
    );
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "delete_homework",
        json!({
            "operation_id": "op-delete-1",
            "id": "essay",
            "expected_revision": 1
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "delete_homework must succeed, got {response}"
    );
    let body = body_of(&response);
    assert_eq!(
        body.get("ok"),
        Some(&json!(true)),
        "delete returns ok, got {body}"
    );
    let changed = body
        .pointer("/result/changed_weeks")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    assert_eq!(
        changed.len(),
        2,
        "both weeks that held a session bump, got {body}"
    );
    assert_eq!(
        changed[0].get("week_start"),
        Some(&json!("2026-10-12")),
        "the earlier week is listed first, got {changed:?}"
    );
    assert_eq!(
        changed[0].get("revision"),
        Some(&json!(2)),
        "the earlier week bumps from 1 to 2, got {changed:?}"
    );
    assert_eq!(
        changed[1].get("week_start"),
        Some(&json!("2026-10-19")),
        "the current week is listed second, got {changed:?}"
    );
    assert_eq!(
        changed[1].get("revision"),
        Some(&json!(5)),
        "the current week bumps from 4 to 5, got {changed:?}"
    );
    for week in ["2026-10-12", "2026-10-19"] {
        let (blocks, _) =
            week_row(&world.database_arg, world.user, week).unwrap_or((Value::Null, -1));
        let left = blocks_with_assignment(&blocks, "essay");
        assert!(
            left.is_empty(),
            "{week} still has a session for the deleted homework, got {blocks}"
        );
    }
    let (kept, _) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    let club = kept.as_array().and_then(|items| {
        items
            .iter()
            .find(|block| block.get("id").and_then(Value::as_str) == Some("club"))
    });
    assert!(club.is_some(), "a block that is not this homework stays");
    assert!(
        assignment_row(&world.database_arg, world.user, "essay").is_none(),
        "the assignment row is gone"
    );
    let again = server.call(
        "delete_homework",
        json!({
            "operation_id": "op-delete-1",
            "id": "essay",
            "expected_revision": 1
        }),
        3,
    );
    assert_eq!(
        body_of(&response),
        body_of(&again),
        "retrying the delete returns the first answer"
    );
}

#[test]
fn set_homework_done_finishes_the_assignment_and_its_session() {
    let world = signed_in("done-hw");
    seed_essay(
        &world,
        &[(
            "2026-10-19",
            4,
            json!([essay_session("sess-essay", &[2], Some("16:00"))]),
        )],
    );
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "set_homework_done",
        json!({
            "operation_id": "op-done-hw1",
            "id": "essay",
            "done": true
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "set_homework_done must succeed, got {response}"
    );
    let body = body_of(&response);
    assert_eq!(
        body.pointer("/result/assignment/completed"),
        Some(&json!(true)),
        "complete_homework 1571 marks the homework done, got {body}"
    );
    assert_eq!(
        body.pointer("/result/assignment/completed_at"),
        Some(&json!("2026-10-21T12:00")),
        "completing with no stamp uses the clock minute, got {body}"
    );
    let (blocks, _) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    let sessions = blocks_with_assignment(&blocks, "essay");
    assert_eq!(sessions.len(), 1, "the session stays, got {blocks}");
    assert_eq!(
        sessions[0].get("completed"),
        Some(&json!(true)),
        "the finish cascade 1016-1028 marks the session done, got {sessions:?}"
    );
    assert_eq!(
        sessions[0].get("completed_day"),
        Some(&json!(2)),
        "a one-day session with a start records completed_day, got {sessions:?}"
    );
    let again = server.call(
        "set_homework_done",
        json!({
            "operation_id": "op-done-hw1",
            "id": "essay",
            "done": true
        }),
        3,
    );
    assert_eq!(
        body_of(&response),
        body_of(&again),
        "retrying set_homework_done returns the first answer"
    );
}

#[test]
fn set_block_done_sets_completed_and_completed_day() {
    let world = signed_in("done-block");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let blocks = json!([{
        "id": "club",
        "title": "Club",
        "kind": "flexible",
        "duration_min": 60,
        "days": [2],
        "start": "16:00",
        "priority": 3,
        "energy": "medium"
    }]);
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        (world.user, "2026-10-19", blocks.to_string()),
    )
    .expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-blk",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 2,
            "done": true
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "set_block_done must succeed, got {response}"
    );
    let body = body_of(&response);
    assert_eq!(
        body.get("revision"),
        Some(&json!(5)),
        "marking a block done bumps the week, got {body}"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the stored week revision is 5");
    let club = stored.as_array().and_then(|items| {
        items
            .iter()
            .find(|block| block.get("id").and_then(Value::as_str) == Some("club"))
    });
    let club = club.cloned().unwrap_or(Value::Null);
    assert_eq!(
        club.get("completed"),
        Some(&json!(true)),
        "agenda.rs 362 sets completed, got {club}"
    );
    assert_eq!(
        club.get("completed_day"),
        Some(&json!(2)),
        "agenda.rs 364 sets completed_day when the day is one of the block's days, got {club}"
    );
    let again = server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-blk",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 2,
            "done": true
        }),
        3,
    );
    assert_eq!(
        body_of(&response),
        body_of(&again),
        "retrying set_block_done returns the first answer"
    );
    let (_, after) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(after, 5, "a retry does not bump the week again");
}

#[test]
fn set_block_done_refuses_a_foreign_day_and_marks_school() {
    let world = signed_in("refuse-block");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let blocks = json!([
        {
            "id": "club",
            "title": "Club",
            "kind": "flexible",
            "duration_min": 60,
            "days": [2],
            "start": "16:00"
        },
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 60,
            "days": [0],
            "start": "09:00"
        },
        {
            "id": "sport",
            "title": "Sport",
            "kind": "locked",
            "duration_min": 60,
            "days": [1],
            "start": "15:00"
        },
        {
            "id": "activity-piano",
            "title": "Piano",
            "kind": "locked",
            "duration_min": 30,
            "days": [3],
            "start": "17:00"
        }
    ]);
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        (world.user, "2026-10-19", blocks.to_string()),
    )
    .expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let foreign = server.call(
        "set_block_done",
        json!({
            "operation_id": "op-foreign1",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 0,
            "done": true
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&foreign),
        Some("day is not one of the block's days"),
        "agenda.rs 359 refuses a day the block does not have, got {foreign}"
    );
    let (_, refused) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(refused, 4, "a refusal writes nothing");
    // School and Setup's activities may be marked done now, each on a day it is on.
    let setup = [("school", 0), ("sport", 1), ("activity-piano", 3)];
    for (offset, (id, day)) in setup.iter().enumerate() {
        let response = server.call(
            "set_block_done",
            json!({
                "operation_id": format!("op-setup-{offset}{id}"),
                "week_start": "2026-10-19",
                "block_id": id,
                "day": day,
                "done": true
            }),
            3 + offset as i64,
        );
        assert!(
            tool_ok_text(&response).is_some(),
            "{id} can be marked done through MCP, got {response}"
        );
    }
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 7, "each mark is one change");
    for (id, _) in setup {
        let block = stored
            .as_array()
            .and_then(|items| items.iter().find(|block| block["id"] == id))
            .cloned()
            .unwrap_or(Value::Null);
        assert_eq!(block["completed"], json!(true), "{id} is done, got {block}");
    }
}

fn club_week(world: &World) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let blocks = json!([
        essay_session("sess-essay", &[2], None),
        {
            "id": "club",
            "title": "Club",
            "kind": "flexible",
            "duration_min": 60,
            "days": [2],
            "start": "16:00",
            "priority": 3,
            "energy": "medium"
        }
    ]);
    conn.execute(
        "UPDATE weeks SET blocks = ?1 WHERE user_id = ?2 AND week_start = '2026-10-19'",
        (blocks.to_string(), world.user),
    )
    .expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn add_args(operation_id: &str, title: &str) -> Value {
    json!({
        "operation_id": operation_id,
        "title": title,
        "due": "2026-10-23T21:00",
        "estimate_min": 30
    })
}

#[test]
fn four_adds_sent_without_waiting_all_apply() {
    let world = signed_in("batch-adds");
    let mut server = boot(&world);
    server.handshake();
    let titles = ["Essay", "Lab report", "Reading", "Worksheet"];
    for (index, title) in titles.iter().enumerate() {
        server.send_call(
            "add_homework",
            add_args(&format!("op-batch-add-{index}"), title),
            10 + index as i64,
        );
    }
    let answers = server.answers(&[10, 11, 12, 13]);
    for answer in &answers {
        assert_eq!(
            body_of(answer).get("ok"),
            Some(&json!(true)),
            "every add sent at once applies, got {answer}"
        );
    }
    assert_eq!(count_assignments(&world.database_arg, world.user), 4);
    let (blocks, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    let sessions = blocks
        .as_array()
        .map(|items| {
            items
                .iter()
                .filter(|block| block.get("assignment_id").is_some())
                .count()
        })
        .unwrap_or(0);
    assert_eq!(
        sessions, 4,
        "each add left its session in this week, got {blocks}"
    );
    assert_eq!(revision, 4, "four saves of a new week reach revision 4");
}

#[test]
fn mixed_writes_sent_without_waiting_all_apply() {
    let world = signed_in("batch-mixed");
    seed_essay(&world, &[("2026-10-19", 4, json!([]))]);
    club_week(&world);
    let mut server = boot(&world);
    server.handshake();
    server.send_call("add_homework", add_args("op-mixed-add-1", "Lab report"), 10);
    server.send_call(
        "set_block_done",
        json!({
            "operation_id": "op-mixed-club",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 2,
            "done": true
        }),
        11,
    );
    server.send_call(
        "edit_homework",
        json!({
            "operation_id": "op-mixed-edit",
            "id": "essay",
            "expected_revision": 1,
            "title": "Essay draft"
        }),
        12,
    );
    server.send_call("add_homework", add_args("op-mixed-add-2", "Reading"), 13);
    let answers = server.answers(&[10, 11, 12, 13]);
    for answer in &answers {
        assert_eq!(
            body_of(answer).get("ok"),
            Some(&json!(true)),
            "independent writes sent at once all apply, got {answer}"
        );
    }
    assert_eq!(count_assignments(&world.database_arg, world.user), 3);
    let (stored, _) = assignment_row(&world.database_arg, world.user, "essay").unwrap_or_default();
    assert!(
        stored.contains("Essay draft"),
        "the edit landed, got {stored}"
    );
    let (blocks, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    let club = blocks
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|block| block.get("id").and_then(Value::as_str) == Some("club"))
        })
        .cloned()
        .unwrap_or(Value::Null);
    assert_eq!(
        club.get("completed"),
        Some(&json!(true)),
        "club is done, got {club}"
    );
    assert_eq!(revision, 8, "four saves of the week from revision 4");
}

#[test]
fn two_edits_of_one_revision_sent_at_once_keep_one_and_refuse_the_other() {
    let world = signed_in("batch-real-conflict");
    seed_essay(
        &world,
        &[(
            "2026-10-19",
            4,
            json!([essay_session("sess-essay", &[2], None)]),
        )],
    );
    let mut server = boot(&world);
    server.handshake();
    for (id, title) in [(10, "First"), (11, "Second")] {
        server.send_call(
            "edit_homework",
            json!({
                "operation_id": format!("op-real-conflict-{id}"),
                "id": "essay",
                "expected_revision": 1,
                "title": title
            }),
            id,
        );
    }
    let bodies: Vec<Value> = server.answers(&[10, 11]).iter().map(body_of).collect();
    let kept = bodies
        .iter()
        .filter(|body| body.get("ok") == Some(&json!(true)))
        .count();
    let refused: Vec<&Value> = bodies
        .iter()
        .filter(|body| body.get("error") == Some(&json!("conflict")))
        .collect();
    assert_eq!(kept, 1, "one edit of revision 1 is kept, got {bodies:?}");
    assert_eq!(
        refused,
        vec![&json!({"error": "conflict", "current_revision": 2})],
        "the other was made against a revision that has changed, got {bodies:?}"
    );
}

#[test]
fn set_homework_done_with_a_stale_expected_revision_writes_nothing() {
    let world = signed_in("done-hw-stale");
    seed_essay(
        &world,
        &[(
            "2026-10-19",
            4,
            json!([essay_session("sess-essay", &[2], Some("16:00"))]),
        )],
    );
    let mut server = boot(&world);
    server.handshake();
    let stale = server.call(
        "set_homework_done",
        json!({
            "operation_id": "op-done-stale",
            "id": "essay",
            "done": true,
            "expected_revision": 0
        }),
        2,
    );
    assert_eq!(
        body_of(&stale),
        json!({"error": "conflict", "current_revision": 1}),
        "a stale revision is refused with the current one, got {stale}"
    );
    let (stored, revision) =
        assignment_row(&world.database_arg, world.user, "essay").unwrap_or_default();
    assert_eq!(revision, 1, "the homework was not written");
    assert!(
        stored.contains("\"completed\":false"),
        "still not done, got {stored}"
    );
    let (_, week_revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(week_revision, 4, "the week was not written");
    let current = server.call(
        "set_homework_done",
        json!({
            "operation_id": "op-done-current",
            "id": "essay",
            "done": true,
            "expected_revision": 1
        }),
        3,
    );
    assert_eq!(
        body_of(&current).pointer("/result/assignment/completed"),
        Some(&json!(true)),
        "the current revision is accepted, got {current}"
    );
}

#[test]
fn set_block_done_with_a_stale_expected_revision_writes_nothing() {
    let world = signed_in("done-block-stale");
    seed_essay(&world, &[("2026-10-19", 4, json!([]))]);
    club_week(&world);
    let mut server = boot(&world);
    server.handshake();
    let stale = server.call(
        "set_block_done",
        json!({
            "operation_id": "op-block-stale",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 2,
            "done": true,
            "expected_revision": 3
        }),
        2,
    );
    assert_eq!(
        body_of(&stale),
        json!({"error": "conflict", "current_revision": 4}),
        "a stale week revision is refused with the current one, got {stale}"
    );
    let (_, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 4, "the week was not written");
    let current = server.call(
        "set_block_done",
        json!({
            "operation_id": "op-block-current",
            "week_start": "2026-10-19",
            "block_id": "club",
            "day": 2,
            "done": true,
            "expected_revision": 4
        }),
        3,
    );
    assert_eq!(
        body_of(&current).get("revision"),
        Some(&json!(5)),
        "the current revision is accepted, got {current}"
    );
    assert_eq!(
        body_of(&current)["result"]["week_starts_on"],
        json!("monday")
    );
}

#[test]
fn set_block_done_and_delete_homework_say_week_start_across_sunday_wednesday_and_month_end() {
    let world = signed_in("done-shown-weeks");
    seed_essay(
        &world,
        &[
            (
                "2026-10-19",
                4,
                json!([essay_session("sess-wed", &[2], Some("16:00"))]),
            ),
            (
                "2026-10-26",
                2,
                json!([essay_session("sess-mon2", &[0], Some("16:00"))]),
            ),
            (
                "2026-11-02",
                1,
                json!([essay_session("sess-nov", &[1], Some("16:00"))]),
            ),
            (
                "2026-11-23",
                1,
                json!([essay_session("sess-nov29", &[6], Some("16:00"))]),
            ),
        ],
    );
    let mut server = boot(&world);
    server.handshake();

    // Switch live to Wednesday.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    // In 2026-10-21 (Wed): sess-wed is on day 0 (first day 2), sess-mon2 is on day 5 (second day 0).
    let args = json!({
        "operation_id": "op-done-wed-mon2",
        "week_start": "2026-10-21",
        "block_id": "sess-mon2",
        "day": 5,
        "done": true,
        "expected_revision": [4, 2]
    });
    let done_second = body_of(&server.call("set_block_done", args.clone(), 2));
    assert_eq!(done_second["ok"], json!(true), "got {done_second}");
    assert_eq!(done_second["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(done_second["revision"], json!([4, 3]));
    assert_eq!(
        week_row(&world.database_arg, world.user, "2026-10-19")
            .unwrap()
            .1,
        4,
        "first untouched"
    );
    let (sec_blocks, sec_rev) = week_row(&world.database_arg, world.user, "2026-10-26").unwrap();
    assert_eq!(sec_rev, 3);
    assert_eq!(sec_blocks[0]["completed"], json!(true));
    assert_eq!(sec_blocks[0]["completed_day"], json!(0));
    let retry = body_of(&server.call("set_block_done", args, 3));
    assert_eq!(retry, done_second);

    // Stale expected_revision pair returns conflict.
    let stale = body_of(&server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-wed-stale",
            "week_start": "2026-10-21",
            "block_id": "sess-wed",
            "day": 0,
            "done": true,
            "expected_revision": [4, 2]
        }),
        4,
    ));
    assert_eq!(
        stale,
        json!({"error": "conflict", "current_revision": [4, 3]})
    );

    // Month-end crossing Wednesday 2026-10-28: sess-nov is Tue Nov 3 (day 6 -> 2026-11-02 day 1).
    let cross_wed = body_of(&server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-cross-wed",
            "week_start": "2026-10-28",
            "block_id": "sess-nov",
            "day": 6,
            "done": true
        }),
        5,
    ));
    assert_eq!(cross_wed["ok"], json!(true), "got {cross_wed}");
    assert_eq!(cross_wed["result"]["week_starts_on"], json!("wednesday"));
    let (nov_blocks, nov_rev) = week_row(&world.database_arg, world.user, "2026-11-02").unwrap();
    assert_eq!(nov_rev, 2);
    assert_eq!(nov_blocks[0]["completed_day"], json!(1));

    // Old client Monday compatibility.
    let compat = body_of(&server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-mon-compat",
            "week_start": "2026-10-19",
            "block_id": "sess-wed",
            "day": 2,
            "done": true
        }),
        6,
    ));
    assert_eq!(compat["ok"], json!(true));
    assert_eq!(compat["result"]["week_starts_on"], json!("monday"));
    assert_eq!(compat["revision"], json!(5));

    // Switch live to Sunday: month-end crossing 2026-11-29 day 0 -> 2026-11-23 day 6.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");
    let sun_done = body_of(&server.call(
        "set_block_done",
        json!({
            "operation_id": "op-done-sun-cross",
            "week_start": "2026-11-29",
            "block_id": "sess-nov29",
            "day": 0,
            "done": true
        }),
        7,
    ));
    assert_eq!(sun_done["ok"], json!(true), "got {sun_done}");
    assert_eq!(sun_done["result"]["week_starts_on"], json!("sunday"));
    let (nov23, _) = week_row(&world.database_arg, world.user, "2026-11-23").unwrap();
    assert_eq!(nov23[0]["completed"], json!(true));

    // delete_homework names week_starts_on on each changed_weeks item.
    let del_hw = body_of(&server.call(
        "delete_homework",
        json!({
            "operation_id": "op-del-hw-shown",
            "id": "essay",
            "expected_revision": 1
        }),
        8,
    ));
    let changed = del_hw["result"]["changed_weeks"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert!(!changed.is_empty());
    for entry in &changed {
        assert_eq!(entry["week_starts_on"], json!("monday"));
    }
}

#[test]
fn shown_set_block_done_reply_failure_rolls_back_atomically() {
    let world = signed_in("set-block-done-fault");
    seed_essay(
        &world,
        &[(
            "2026-10-26",
            2,
            json!([essay_session("sess-mon2", &[0], Some("16:00"))]),
        )],
    );
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute_batch(
        "CREATE TRIGGER fail_reply_update BEFORE UPDATE OF response ON operations \
         BEGIN SELECT RAISE(FAIL, 'review injected reply failure'); END;",
    )
    .expect("trigger");
    drop(conn);

    let mut server = boot(&world);
    server.handshake();

    let args = json!({
        "operation_id": "op-fault-done",
        "week_start": "2026-10-21",
        "block_id": "sess-mon2",
        "day": 5,
        "done": true,
        "expected_revision": [0, 2]
    });
    let fail = server.call("set_block_done", args.clone(), 2);
    assert!(
        tool_error_text(&fail).is_some(),
        "fault must fail set_block_done, got {fail}"
    );
    let (blocks, rev) = week_row(&world.database_arg, world.user, "2026-10-26").unwrap();
    assert_eq!(rev, 2, "second week rev must roll back");
    assert!(
        blocks[0].get("completed").is_none(),
        "completed must roll back: {blocks}"
    );

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute_batch("DROP TRIGGER fail_reply_update;")
        .expect("drop");
    drop(conn);

    let ok = body_of(&server.call("set_block_done", args, 3));
    assert_eq!(ok["ok"], json!(true), "retry succeeds: {ok}");
    assert_eq!(ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(ok["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(ok["revision"], json!([0, 3]));
}
