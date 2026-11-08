//! Every assistant write saves a restore point first, and `restore_point` brings one back in one
//! step, the way the desktop's Restore does (`backend/app.py` restore route): the whole account is
//! replaced by the point, after a "Before restore" point of its own so the restore can be undone.
//! The app keeps 20 points (`MAX_RESTORE_POINTS`); the assistant keeps at most 10 of its own, and
//! fewer when the student's leave less room under the 20, so it never pushes out the student's. A
//! refused write changes no point.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_store::{
    create_restore_point, initialize, insert_preferences, insert_user, open_connection,
    open_session,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const WEEK: &str = "2026-10-19";

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

fn club() -> Value {
    json!({
        "id": "club",
        "title": "Club",
        "kind": "locked",
        "duration_min": 60,
        "days": [2],
        "start": "16:00",
        "priority": 3,
        "energy": "medium"
    })
}

fn seed_week(world: &World, blocks: Value) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        (world.user, WEEK, blocks.to_string()),
    )
    .expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
}

/// `(id, label, body)` of every restore point, oldest first.
fn points(world: &World) -> Vec<(String, String, Value)> {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut stmt = conn
        .prepare("SELECT id, label, body FROM restore_points WHERE user_id = ?1 ORDER BY seq")
        .expect("prepare");
    stmt.query_map((world.user,), |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
        ))
    })
    .expect("query")
    .map(|row| {
        let (id, label, body) = row.expect("row");
        (
            id,
            label,
            serde_json::from_str(&body).unwrap_or(Value::Null),
        )
    })
    .collect()
}

fn week_row(world: &World) -> (Value, i64) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
        (world.user, WEEK),
        |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
    )
    .map(|(text, revision)| (serde_json::from_str(&text).unwrap_or(Value::Null), revision))
    .unwrap_or((Value::Null, -1))
}

fn assignment_revision(world: &World, id: &str) -> i64 {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT revision FROM assignments WHERE user_id = ?1 AND id = ?2",
        (world.user, id),
        |row| row.get::<_, i64>(0),
    )
    .unwrap_or(-1)
}

fn assignment_count(world: &World) -> i64 {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT COUNT(*) FROM assignments WHERE user_id = ?1",
        (world.user,),
        |row| row.get::<_, i64>(0),
    )
    .unwrap_or(-1)
}

fn ids_in(blocks: &Value) -> Vec<String> {
    let mut ids: Vec<String> = blocks
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|block| block.get("id").and_then(Value::as_str).map(str::to_string))
        .collect();
    ids.sort();
    ids
}

fn find<'a>(blocks: &'a Value, id: &str) -> &'a Value {
    blocks
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|block| block.get("id").and_then(Value::as_str) == Some(id))
        })
        .unwrap_or(&Value::Null)
}

fn add_essay(server: &mut Server, operation_id: &str, id: i64) -> Value {
    server.call(
        "add_homework",
        json!({
            "operation_id": operation_id,
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        id,
    )
}

#[test]
fn a_write_saves_the_week_as_it_was_before_it() {
    let world = signed_in("restore-before-move");
    seed_week(&world, json!([club()]));
    let mut server = boot(&world);
    server.handshake();
    let moved = server.call(
        "move_block",
        json!({
            "operation_id": "op-move-club",
            "week_start": WEEK,
            "expected_revision": 4,
            "block_id": "club",
            "day": 2,
            "start": "17:00",
            "end": "18:00"
        }),
        2,
    );
    assert_eq!(
        body_of(&moved)["ok"],
        json!(true),
        "the move lands, got {moved}"
    );
    let saved = points(&world);
    assert_eq!(
        saved.len(),
        1,
        "one write makes one restore point, got {saved:?}"
    );
    let (id, label, body) = &saved[0];
    assert!(
        id.starts_with("rp-"),
        "the point is named as the app names them, got {id}"
    );
    assert!(
        label.starts_with("Before assistant move_block"),
        "the label says the assistant's move made it, got {label}"
    );
    let before = body["weeks"]
        .as_array()
        .and_then(|weeks| weeks.iter().find(|week| week["week_start"] == WEEK))
        .map(|week| week["blocks"].clone())
        .unwrap_or(Value::Null);
    assert_eq!(
        find(&before, "club")["start"],
        json!("16:00"),
        "the point holds the club where it was before the move, got {body}"
    );
    let (now, _) = week_row(&world);
    assert_eq!(
        find(&now, "club")["start"],
        json!("17:00"),
        "the move itself landed"
    );
    let listed = body_of(&server.call("list_restore_points", json!({}), 3));
    assert_eq!(
        listed["restore_points"][0]["id"],
        json!(id),
        "list_restore_points shows the point, got {listed}"
    );
}

#[test]
fn a_retried_write_makes_no_second_restore_point() {
    let world = signed_in("restore-retry");
    let mut server = boot(&world);
    server.handshake();
    let first = add_essay(&mut server, "op-essay-once", 2);
    assert_eq!(
        body_of(&first)["ok"],
        json!(true),
        "the add lands, got {first}"
    );
    let again = add_essay(&mut server, "op-essay-once", 3);
    assert_eq!(
        body_of(&first),
        body_of(&again),
        "a retry returns the first answer"
    );
    assert_eq!(
        points(&world).len(),
        1,
        "a retry saves no second restore point"
    );
}

#[test]
fn every_write_tool_saves_a_restore_point_and_the_assistant_keeps_ten() {
    let world = signed_in("restore-every-tool");
    seed_week(&world, json!([club()]));
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    create_restore_point(
        &conn,
        world.user,
        "student",
        "Before import — 2026-10-20T09:00",
        "2026-10-20T09:00",
        &[],
        20,
    )
    .expect("the student's own point");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let mut calls: Vec<(&str, Arguments)> = Vec::new();
    calls.push((
        "add_homework",
        Box::new(|_| {
            json!({"operation_id": "op-every-01", "title": "Essay", "due": "2026-10-23T21:00",
                "estimate_min": 90})
        }),
    ));
    calls.push((
        "plan_homework",
        Box::new(|_| json!({"operation_id": "op-every-02", "week_start": WEEK})),
    ));
    calls.push((
        "edit_homework",
        Box::new(|world| {
            json!({"operation_id": "op-every-03", "id": essay_id(world),
                "expected_revision": assignment_revision(world, &essay_id(world)),
                "title": "Long essay"})
        }),
    ));
    calls.push((
        "set_homework_done",
        Box::new(
            |world| json!({"operation_id": "op-every-04", "id": essay_id(world), "done": true}),
        ),
    ));
    calls.push((
        "move_block",
        Box::new(|world| {
            json!({"operation_id": "op-every-06", "week_start": WEEK,
                "expected_revision": week_row(world).1, "block_id": "club", "day": 3,
                "start": "17:00", "end": "18:00"})
        }),
    ));
    calls.push((
        "set_block_done",
        Box::new(|_| {
            json!({"operation_id": "op-every-05", "week_start": WEEK, "block_id": "club",
                "day": 3, "done": true})
        }),
    ));
    calls.push((
        "add_block",
        Box::new(|_| {
            json!({"operation_id": "op-every-07", "week_start": WEEK, "title": "Dinner",
                "category": "meals", "days": [4], "start": "18:00", "end": "18:30"})
        }),
    ));
    calls.push((
        "edit_block",
        Box::new(|world| {
            json!({"operation_id": "op-every-08", "week_start": WEEK,
                "expected_revision": week_row(world).1, "block_id": dinner_id(world),
                "title": "Family dinner"})
        }),
    ));
    calls.push((
        "skip_block_day",
        Box::new(|world| {
            json!({"operation_id": "op-every-09", "week_start": WEEK,
                "expected_revision": week_row(world).1, "block_id": "club", "day": 3})
        }),
    ));
    calls.push((
        "delete_block",
        Box::new(|world| {
            json!({"operation_id": "op-every-10", "week_start": WEEK,
                "expected_revision": week_row(world).1, "block_id": dinner_id(world),
                "scope": "series"})
        }),
    ));
    calls.push((
        "delete_homework",
        Box::new(|world| {
            json!({"operation_id": "op-every-11", "id": essay_id(world),
                "expected_revision": assignment_revision(world, &essay_id(world))})
        }),
    ));
    for (index, (tool, arguments)) in calls.iter().enumerate() {
        let response = server.call(tool, arguments(&world), 10 + index as i64);
        let body = body_of(&response);
        assert_eq!(body["ok"], json!(true), "{tool} must land, got {response}");
        let after = points(&world);
        let assistant: Vec<_> = after
            .iter()
            .filter(|(_, label, _)| label.starts_with("Before assistant"))
            .collect();
        assert_eq!(
            assistant.len(),
            (index + 1).min(10),
            "{tool}: each write adds one point and the assistant keeps ten, got {after:?}"
        );
        let newest = after
            .last()
            .map(|(_, label, _)| label.clone())
            .unwrap_or_default();
        assert!(
            newest.starts_with(&format!("Before assistant {tool}")),
            "{tool}: the newest point names the tool, got {newest}"
        );
        assert!(
            after.iter().any(|(id, _, _)| id == "rp-student"),
            "{tool}: the student's own point is never pushed out, got {after:?}"
        );
    }
}

/// A tool's arguments, worked out from the database just before the call.
type Arguments = Box<dyn Fn(&World) -> Value>;

fn essay_id(world: &World) -> String {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT id FROM assignments WHERE user_id = ?1",
        (world.user,),
        |row| row.get::<_, String>(0),
    )
    .unwrap_or_default()
}

fn dinner_id(world: &World) -> String {
    let (blocks, _) = week_row(world);
    blocks
        .as_array()
        .into_iter()
        .flatten()
        .find(|block| {
            block["title"]
                .as_str()
                .is_some_and(|title| title.contains("dinner") || title == "Dinner")
        })
        .and_then(|block| block["id"].as_str().map(str::to_string))
        .unwrap_or_default()
}

#[test]
fn restore_point_undoes_the_assistants_whole_change_and_can_be_undone() {
    let world = signed_in("restore-undo");
    seed_week(&world, json!([club()]));
    let mut server = boot(&world);
    server.handshake();
    let added = add_essay(&mut server, "op-undo-essay", 2);
    assert_eq!(
        body_of(&added)["ok"],
        json!(true),
        "the add lands, got {added}"
    );
    let block = server.call(
        "add_block",
        json!({
            "operation_id": "op-undo-dinner",
            "week_start": WEEK,
            "title": "Dinner",
            "category": "meals",
            "days": [3],
            "start": "18:00",
            "end": "18:30"
        }),
        3,
    );
    assert_eq!(
        body_of(&block)["ok"],
        json!(true),
        "the block lands, got {block}"
    );
    let (changed, _) = week_row(&world);
    let changed_ids = ids_in(&changed);
    assert_eq!(assignment_count(&world), 1, "the essay is saved");
    let first = points(&world)
        .first()
        .map(|(id, _, _)| id.clone())
        .unwrap_or_default();
    let restored = server.call(
        "restore_point",
        json!({"operation_id": "op-undo-restore", "id": first}),
        4,
    );
    let body = body_of(&restored);
    assert_eq!(body["ok"], json!(true), "the restore lands, got {restored}");
    let (week, revision) = week_row(&world);
    assert_eq!(
        ids_in(&week),
        vec!["club".to_string()],
        "the week is as it was before the assistant's first change, got {week}"
    );
    assert_eq!(revision, 4, "the week's saved revision comes back with it");
    assert_eq!(
        assignment_count(&world),
        0,
        "the essay the assistant added is gone"
    );
    let after = points(&world);
    let (undo_id, undo_label, _) = after.last().cloned().unwrap_or_default();
    assert!(
        undo_label.starts_with("Before restore — "),
        "the restore saved a point of its own first, as the app does, got {undo_label}"
    );
    assert_eq!(
        body["result"]["recovery_id"],
        json!(undo_id),
        "the reply names the point that undoes the restore, got {body}"
    );
    let again = server.call(
        "restore_point",
        json!({"operation_id": "op-undo-restore", "id": first}),
        5,
    );
    assert_eq!(
        body_of(&again),
        body,
        "a retried restore returns the first answer"
    );
    assert_eq!(
        points(&world).len(),
        after.len(),
        "a retried restore saves no point"
    );
    let redo = server.call(
        "restore_point",
        json!({"operation_id": "op-undo-redo", "id": undo_id}),
        6,
    );
    assert_eq!(
        body_of(&redo)["ok"],
        json!(true),
        "restoring the undo point lands, got {redo}"
    );
    let (back, _) = week_row(&world);
    assert_eq!(ids_in(&back), changed_ids, "the assistant's change is back");
    assert_eq!(assignment_count(&world), 1, "the essay is back");
}

#[test]
fn restore_point_of_an_unknown_id_is_refused_and_writes_nothing() {
    let world = signed_in("restore-unknown");
    seed_week(&world, json!([club()]));
    let mut server = boot(&world);
    server.handshake();
    let refused = server.call(
        "restore_point",
        json!({"operation_id": "op-restore-nope", "id": "rp-nope"}),
        2,
    );
    assert_eq!(
        tool_error_text(&refused),
        Some("Restore point not found"),
        "the app's words for a missing point, got {refused}"
    );
    assert!(
        points(&world).is_empty(),
        "a refused restore saves no point"
    );
    assert_eq!(week_row(&world).1, 4, "a refused restore changes nothing");
}

#[test]
fn restore_point_brings_back_school_as_it_stood() {
    let world = signed_in("restore-standing");
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    flexweek_store::set_standing(&conn, world.user, WEEK, &json!([school]).to_string())
        .expect("school stands");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let deleted = server.call(
        "delete_block",
        json!({
            "operation_id": "op-school-gone",
            "week_start": WEEK,
            "expected_revision": 0,
            "block_id": "school",
            "scope": "series",
            "every_week": true
        }),
        2,
    );
    assert_eq!(
        body_of(&deleted)["ok"],
        json!(true),
        "school goes, got {deleted}"
    );
    let later = body_of(&server.call("get_week", json!({"week_start": "2026-10-26"}), 3));
    assert!(
        !later.to_string().contains("\"school\""),
        "school no longer stands in a later week, got {later}"
    );
    let first = points(&world)
        .first()
        .map(|(id, _, _)| id.clone())
        .unwrap_or_default();
    let restored = server.call(
        "restore_point",
        json!({"operation_id": "op-school-back", "id": first}),
        4,
    );
    assert_eq!(
        body_of(&restored)["ok"],
        json!(true),
        "the restore lands, got {restored}"
    );
    let back = body_of(&server.call("get_week", json!({"week_start": "2026-10-26"}), 5));
    assert!(
        back.to_string().contains("\"school\""),
        "the restore brings school back to later weeks, got {back}"
    );
}

fn student_points(world: &World, count: usize) -> Vec<String> {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let ids: Vec<String> = (0..count).map(|n| format!("student{n:02}")).collect();
    for token in &ids {
        create_restore_point(
            &conn,
            world.user,
            token,
            "Before import — 2026-10-20T09:00",
            "2026-10-20T09:00",
            &[],
            20,
        )
        .expect("the student's own point");
    }
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    ids.iter().map(|token| format!("rp-{token}")).collect()
}

#[test]
fn the_assistant_never_pushes_out_the_students_points() {
    let world = signed_in("restore-student-kept");
    let students = student_points(&world, 15);
    let mut server = boot(&world);
    server.handshake();
    for n in 0..10 {
        let added = add_essay(&mut server, &format!("op-keep-student-{n:02}"), 2 + n);
        assert_eq!(
            body_of(&added)["ok"],
            json!(true),
            "write {n} lands, got {added}"
        );
        let after = points(&world);
        let ids: Vec<&str> = after.iter().map(|(id, _, _)| id.as_str()).collect();
        for student in &students {
            assert!(
                ids.contains(&student.as_str()),
                "write {n}: the student's point {student} is still there, got {ids:?}"
            );
        }
        assert!(
            after.len() <= 20,
            "write {n}: the app's 20 points are still the most kept, got {}",
            after.len()
        );
        assert!(
            after
                .last()
                .is_some_and(|(_, label, _)| label.starts_with("Before assistant add_homework")),
            "write {n}: the newest point is this write's, got {after:?}"
        );
    }
}

#[test]
fn a_refused_write_keeps_every_restore_point() {
    let world = signed_in("restore-refused");
    seed_week(&world, json!([club()]));
    let mut server = boot(&world);
    server.handshake();
    for n in 0..10 {
        let added = add_essay(&mut server, &format!("op-refused-fill-{n:02}"), 2 + n);
        assert_eq!(
            body_of(&added)["ok"],
            json!(true),
            "write {n} lands, got {added}"
        );
    }
    let before = points(&world);
    assert_eq!(before.len(), 10, "the assistant keeps ten, got {before:?}");
    let week_before = week_row(&world);
    let stale = server.call(
        "move_block",
        json!({
            "operation_id": "op-refused-move",
            "week_start": WEEK,
            "expected_revision": 1,
            "block_id": "club",
            "day": 2,
            "start": "17:00",
            "end": "18:00"
        }),
        20,
    );
    assert_eq!(
        body_of(&stale)["error"],
        json!("conflict"),
        "a stale revision is refused, got {stale}"
    );
    let ids = |list: &[(String, String, Value)]| -> Vec<String> {
        list.iter().map(|(id, _, _)| id.clone()).collect()
    };
    assert_eq!(
        ids(&points(&world)),
        ids(&before),
        "a refused write keeps every restore point"
    );
    assert_eq!(
        week_row(&world),
        week_before,
        "a refused write changes nothing"
    );
}
