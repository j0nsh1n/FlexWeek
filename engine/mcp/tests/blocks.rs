//! Block writes. `move_block` calls `hand_move` and returns its words.
//! A start before now on 2026-10-21 (minute 720) is
//! "That time has passed. Choose 12:00 or later today, or another day."
//! (`grid.rs` `past_problem`). `delete_block` follows `controller.py` 1538-1559:
//! a series goes, one day of a repeating block stays on the other days, and
//! school or an activity taken out of this week stays there missed on every day.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_engine::snapshot::canonical;
use flexweek_store::{
    initialize, insert_preferences, insert_user, open_connection, open_session, save_week,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const REACHES: &str = "when FlexWeek is open on this computer with a phone paired";
const OPERATION_CONFLICT: &str = "This operation was already used with different data.";
const PAST: &str = "That time has passed. Choose 12:00 or later today, or another day.";

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
    boot_at(world, NOW_ISO)
}

fn boot_at(world: &World, now: &str) -> Server {
    Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        now,
    ])
}

#[test]
fn move_block_uses_offset_clock_minute_for_past_check() {
    let world = signed_in("move-offset-past");
    seed_week(&world, json!([study(&[2], "16:00")]));
    let mut server = boot_at(&world, "2026-10-21T08:00:00+09:00");
    server.handshake();
    let response = server.call(
        "move_block",
        json!({
            "operation_id": "op-offset-past",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "study",
            "day": 2,
            "start": "07:00",
            "end": "08:00"
        }),
        2,
    );
    let error = tool_error_text(&response).unwrap_or_default();
    assert!(error.contains("That time has passed"), "got {response}");
}

fn is_error(response: &Value) -> Option<bool> {
    response.pointer("/result/isError").and_then(Value::as_bool)
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
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

fn find_block(blocks: &Value, id: &str) -> Value {
    blocks
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|block| block.get("id").and_then(Value::as_str) == Some(id))
                .cloned()
        })
        .unwrap_or(Value::Null)
}

fn club(days: &[i64], start: &str) -> Value {
    json!({
        "id": "club",
        "title": "Club",
        "kind": "locked",
        "duration_min": 60,
        "days": days,
        "start": start,
        "priority": 3,
        "energy": "medium"
    })
}

fn study(days: &[i64], start: &str) -> Value {
    json!({
        "id": "study",
        "title": "Study",
        "kind": "flexible",
        "duration_min": 60,
        "days": days,
        "start": start,
        "priority": 3,
        "energy": "medium"
    })
}

fn seed_week(world: &World, blocks: Value) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        (world.user, "2026-10-19", blocks.to_string()),
    )
    .expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn setup_ids() -> Vec<&'static str> {
    vec!["school", "sport", "activity-piano"]
}

fn setup_blocks() -> Value {
    json!([
        club(&[2], "16:00"),
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 60,
            "days": [0],
            "start": "09:00",
            "priority": 3,
            "energy": "medium"
        },
        {
            "id": "sport",
            "title": "Sport",
            "kind": "locked",
            "duration_min": 60,
            "days": [1],
            "start": "15:00",
            "priority": 3,
            "energy": "medium"
        },
        {
            "id": "activity-piano",
            "title": "Piano",
            "kind": "locked",
            "duration_min": 30,
            "days": [3],
            "start": "17:00",
            "priority": 3,
            "energy": "medium"
        }
    ])
}

#[test]
fn move_block_puts_the_block_at_the_new_time() {
    let world = signed_in("move-club");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let args = json!({
        "operation_id": "op-move-club",
        "week_start": "2026-10-19",
        "expected_revision": 4,
        "block_id": "club",
        "day": 2,
        "start": "17:00",
        "end": "18:00"
    });
    let response = server.call("move_block", args.clone(), 2);
    assert_eq!(
        is_error(&response),
        Some(false),
        "move_block must succeed, got {response}"
    );
    let body = body_of(&response);
    assert_eq!(
        body.get("ok"),
        Some(&json!(true)),
        "move returns ok, got {body}"
    );
    assert_eq!(
        body.get("revision"),
        Some(&json!(5)),
        "moving a block bumps the week, got {body}"
    );
    assert_eq!(
        body.get("reaches_phone"),
        Some(&json!(REACHES)),
        "a write tells the assistant when a paired phone hears it, got {body}"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the stored week revision is 5");
    let moved = find_block(&stored, "club");
    assert_eq!(
        moved.get("start"),
        Some(&json!("17:00")),
        "hand_move sets the start the block was let go at, got {moved}"
    );
    assert_eq!(
        moved.get("duration_min"),
        Some(&json!(60)),
        "the length is the end minus the start, got {moved}"
    );
    assert_eq!(
        moved.get("days"),
        Some(&json!([2])),
        "the block stays on Wednesday, got {moved}"
    );
    let again = server.call("move_block", args, 3);
    assert_eq!(
        body_of(&response),
        body_of(&again),
        "the same operation returns the first answer"
    );
    let (_, after) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(after, 5, "a retry does not bump the week again");
    let conflict = server.call(
        "move_block",
        json!({
            "operation_id": "op-move-club",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "day": 2,
            "start": "18:00",
            "end": "19:00"
        }),
        4,
    );
    assert_eq!(
        tool_error_text(&conflict),
        Some(OPERATION_CONFLICT),
        "the same operation id with different arguments is an error, got {conflict}"
    );
    let (kept, kept_revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(kept_revision, 5, "a conflicting retry writes nothing");
    assert_eq!(
        find_block(&kept, "club").get("start"),
        Some(&json!("17:00")),
        "the second time was not written"
    );
}

#[test]
fn move_block_of_homework_to_a_past_time_is_refused_in_hand_moves_words() {
    let world = signed_in("move-past");
    seed_week(&world, json!([study(&[2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "move_block",
        json!({
            "operation_id": "op-move-past",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "study",
            "day": 2,
            "start": "11:00",
            "end": "12:00"
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&response),
        Some(PAST),
        "a start before now is refused in hand_move's words, got {response}"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 4, "a refused move writes nothing");
    assert_eq!(
        find_block(&stored, "study").get("start"),
        Some(&json!("16:00")),
        "the homework stays at 16:00"
    );
}

#[test]
fn move_block_of_a_fixed_time_to_a_past_time_today_is_accepted() {
    let world = signed_in("move-fixed-past");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "move_block",
        json!({
            "operation_id": "op-move-fixed-past",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "day": 2,
            "start": "11:00",
            "end": "12:00"
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&response),
        None,
        "a fixed time may move to a start before now, got {response}"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the move was saved");
    assert_eq!(
        find_block(&stored, "club").get("start"),
        Some(&json!("11:00")),
        "the fixed time moved to 11:00"
    );
}

#[test]
fn a_stale_week_revision_writes_nothing() {
    let world = signed_in("move-stale");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut kept = club(&[2], "16:00");
    if let Some(map) = kept.as_object_mut() {
        map.insert("title".into(), json!("Kept"));
    }
    let saved = save_week(
        &conn,
        world.user,
        "2026-10-19",
        &canonical(&json!([kept])),
        4,
    )
    .expect("bump");
    assert_eq!(
        saved,
        flexweek_store::WeekSave::Ready(5),
        "the intervening save bumps the week to 5"
    );
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "move_block",
        json!({
            "operation_id": "op-move-stale",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "day": 2,
            "start": "17:00",
            "end": "18:00"
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
        json!({"error": "conflict", "current_revision": 5}),
        "a stale expected_revision returns the current revision and writes nothing"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the week stays at the intervening save");
    let block = find_block(&stored, "club");
    assert_eq!(
        block.get("title"),
        Some(&json!("Kept")),
        "the move was not written, got {block}"
    );
    assert_eq!(
        block.get("start"),
        Some(&json!("16:00")),
        "the start stays at the intervening save, got {block}"
    );
}

#[test]
fn delete_block_removes_a_series_and_one_day() {
    let world = signed_in("delete-series");
    seed_week(&world, json!([club(&[0, 2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let one_day = server.call(
        "delete_block",
        json!({
            "operation_id": "op-delete-day",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "scope": "occurrence",
            "day": 2
        }),
        2,
    );
    assert_eq!(
        is_error(&one_day),
        Some(false),
        "delete_block must succeed, got {one_day}"
    );
    let body = body_of(&one_day);
    assert_eq!(
        body.get("revision"),
        Some(&json!(5)),
        "deleting one day bumps the week, got {body}"
    );
    assert_eq!(
        body.get("reaches_phone"),
        Some(&json!(REACHES)),
        "a write tells the assistant when a paired phone hears it, got {body}"
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the stored week revision is 5");
    assert_eq!(
        find_block(&stored, "club").get("days"),
        Some(&json!([0])),
        "controller.py 1550 keeps the other days, got {stored}"
    );
    let again = server.call(
        "delete_block",
        json!({
            "operation_id": "op-delete-day",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "scope": "occurrence",
            "day": 2
        }),
        3,
    );
    assert_eq!(
        body_of(&one_day),
        body_of(&again),
        "the same operation returns the first answer"
    );
    let (_, after) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(after, 5, "a retry does not bump the week again");

    let world = signed_in("delete-whole");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let response = server.call(
        "delete_block",
        json!({
            "operation_id": "op-delete-all",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "scope": "series"
        }),
        2,
    );
    assert_eq!(
        is_error(&response),
        Some(false),
        "delete_block must succeed, got {response}"
    );
    assert_eq!(
        body_of(&response).get("revision"),
        Some(&json!(5)),
        "deleting the series bumps the week, got {}",
        body_of(&response)
    );
    let (stored, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 5, "the stored week revision is 5");
    assert!(
        find_block(&stored, "club").is_null(),
        "controller.py 1547 removes the whole block, got {stored}"
    );
}

#[test]
fn move_and_delete_change_school_and_activities_this_week() {
    let ids = setup_ids();
    assert!(!ids.is_empty(), "school and activities must be listed");
    let world = signed_in("setup-this-week");
    seed_week(&world, setup_blocks());
    let mut server = boot(&world);
    server.handshake();
    let mut revision = 4;
    for (offset, id) in ids.iter().enumerate() {
        let moved = server.call(
            "move_block",
            json!({
                "operation_id": format!("op-move-{id}"),
                "week_start": "2026-10-19",
                "expected_revision": revision,
                "block_id": id,
                "day": 4,
                "start": "17:00",
                "end": "18:00"
            }),
            10 + offset as i64,
        );
        assert_eq!(
            body_of(&moved).get("ok"),
            Some(&json!(true)),
            "{id} can be moved through the assistant, got {moved}"
        );
        revision += 1;
        let (stored, _) =
            week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
        let block = find_block(&stored, id);
        assert_eq!(
            (block.get("days"), block.get("start")),
            (Some(&json!([4])), Some(&json!("17:00"))),
            "{id} is on Friday at 17:00, got {block}"
        );
        let deleted = server.call(
            "delete_block",
            json!({
                "operation_id": format!("op-del-{id}"),
                "week_start": "2026-10-19",
                "expected_revision": revision,
                "block_id": id,
                "scope": "series"
            }),
            20 + offset as i64,
        );
        assert_eq!(
            body_of(&deleted).get("ok"),
            Some(&json!(true)),
            "{id} can be deleted through the assistant, got {deleted}"
        );
        revision += 1;
        let (stored, _) =
            week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
        assert_eq!(
            find_block(&stored, id).get("missed_days"),
            Some(&json!([4])),
            "{id} taken out of this week stays missed on its days, so the standing week does \
             not bring it back (controller.py delete_block)"
        );
    }
    let (_, stored_revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(stored_revision, revision, "each change is one save");
}

#[test]
fn delete_block_of_a_missing_id_keeps_its_answer() {
    let world = signed_in("delete-missing");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    server.handshake();
    let args = json!({
        "operation_id": "op-miss-ghost",
        "week_start": "2026-10-19",
        "expected_revision": 4,
        "block_id": "ghost",
        "scope": "series"
    });
    let first = server.call("delete_block", args.clone(), 2);
    assert_eq!(
        is_error(&first),
        Some(false),
        "an id that is not in the week is refused without an error, got {first}"
    );
    let first_body = body_of(&first);
    assert_eq!(
        first_body.get("revision"),
        Some(&json!(4)),
        "a missing id leaves the stored revision, got {first_body}"
    );
    let (before, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 4, "the week was not saved again");
    assert!(
        !find_block(&before, "club").is_null(),
        "the block that was there stays, got {before}"
    );
    let planted = json!([
        club(&[2], "16:00"),
        {
            "id": "ghost",
            "title": "Ghost",
            "kind": "locked",
            "duration_min": 30,
            "days": [2],
            "start": "18:00",
            "priority": 3,
            "energy": "medium"
        }
    ]);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute(
        "UPDATE weeks SET blocks = ?1 WHERE user_id = ?2 AND week_start = '2026-10-19'",
        (planted.to_string(), world.user),
    )
    .expect("plant");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let again = server.call("delete_block", args, 3);
    assert_eq!(
        body_of(&again),
        first_body,
        "a retry with the same operation id gives the same answer, got {again}"
    );
    let (after, revision) =
        week_row(&world.database_arg, world.user, "2026-10-19").unwrap_or((Value::Null, -1));
    assert_eq!(revision, 4, "the retry does not save the week");
    assert!(
        !find_block(&after, "ghost").is_null(),
        "the retry does not delete the block that appeared later, got {after}"
    );
}

#[test]
fn move_and_delete_follow_monday_sunday_wednesday_and_month_end_crossing_weeks() {
    let world = signed_in("blocks-shown-weeks");
    seed_week(&world, json!([club(&[3], "16:00"), study(&[2], "17:00")]));
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let intent = flexweek_engine::repeats::edit_intent("school", "2026-10-19", None, Some(&school))
        .expect("intent");
    flexweek_store::apply_repeat_intents(&conn, world.user, &[intent]).expect("standing");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    server.handshake();

    // 1. Monday start keeps week_starts_on: "monday" and integer revision.
    let mon_move = body_of(&server.call(
        "move_block",
        json!({
            "operation_id": "op-mon-move",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "day": 4,
            "start": "16:30",
            "end": "17:30"
        }),
        2,
    ));
    assert_eq!(mon_move["ok"], json!(true), "got {mon_move}");
    assert_eq!(mon_move["result"]["week_starts_on"], json!("monday"));
    assert_eq!(mon_move["revision"], json!(5));

    // 2. Switch week-start.json live to Wednesday.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    // In Wednesday 2026-10-21: Club is on Friday Oct 23 (shown day 2). Move across seam to Monday Oct 26 (shown day 5).
    let wed_move_args = json!({
        "operation_id": "op-wed-move",
        "week_start": "2026-10-21",
        "expected_revision": [5, 0],
        "block_id": "club",
        "day": 5,
        "start": "18:00",
        "end": "19:00"
    });
    let wed_move = body_of(&server.call("move_block", wed_move_args.clone(), 3));
    assert_eq!(wed_move["ok"], json!(true), "got {wed_move}");
    assert_eq!(wed_move["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(wed_move["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(wed_move["revision"], json!([6, 1]));
    let again = body_of(&server.call("move_block", wed_move_args, 4));
    assert_eq!(again, wed_move, "retry keeps exact answer");
    assert!(
        find_block(
            &week_row(&world.database_arg, world.user, "2026-10-19")
                .unwrap()
                .0,
            "club"
        )
        .is_null(),
        "club moved out of first"
    );
    let moved_second = find_block(
        &week_row(&world.database_arg, world.user, "2026-10-26")
            .unwrap()
            .0,
        "club",
    );
    assert_eq!(moved_second["days"], json!([0]));
    assert_eq!(moved_second["start"], json!("18:00"));

    // Stale revision on move returns conflict [6, 1].
    let stale = body_of(&server.call(
        "move_block",
        json!({
            "operation_id": "op-wed-move-stale",
            "week_start": "2026-10-21",
            "expected_revision": [5, 1],
            "block_id": "club",
            "day": 5,
            "start": "19:00",
            "end": "20:00"
        }),
        5,
    ));
    assert_eq!(
        stale,
        json!({"error": "conflict", "current_revision": [6, 1]})
    );

    // Past check on Wednesday 2026-10-21 (day 0 at 11:00 when now is 12:00) refuses homework.
    let past_wed = server.call(
        "move_block",
        json!({
            "operation_id": "op-wed-move-past",
            "week_start": "2026-10-21",
            "expected_revision": [6, 1],
            "block_id": "study",
            "day": 0,
            "start": "11:00",
            "end": "12:00"
        }),
        6,
    );
    assert_eq!(tool_error_text(&past_wed), Some(PAST), "got {past_wed}");

    // delete_block every_week: true on school from Wednesday 2026-10-21 keeps Mon/Tue in 2026-10-19 and stops from 2026-10-26.
    let del_school = body_of(&server.call(
        "delete_block",
        json!({
            "operation_id": "op-wed-del-school",
            "week_start": "2026-10-21",
            "expected_revision": [6, 1],
            "block_id": "school",
            "scope": "series",
            "every_week": true
        }),
        7,
    ));
    assert_eq!(del_school["ok"], json!(true), "got {del_school}");
    assert_eq!(del_school["result"]["week_starts_on"], json!("wednesday"));
    let first_blocks = week_row(&world.database_arg, world.user, "2026-10-19")
        .unwrap()
        .0;
    assert_eq!(find_block(&first_blocks, "school")["days"], json!([0, 1]));
    let second_blocks = week_row(&world.database_arg, world.user, "2026-10-26")
        .unwrap()
        .0;
    assert!(find_block(&second_blocks, "school").is_null());

    // Old client Monday compatibility.
    let compat = body_of(&server.call(
        "delete_block",
        json!({
            "operation_id": "op-mon-compat-del",
            "week_start": "2026-10-19",
            "expected_revision": 7,
            "block_id": "study",
            "scope": "series"
        }),
        8,
    ));
    assert_eq!(compat["ok"], json!(true), "got {compat}");
    assert_eq!(compat["result"]["week_starts_on"], json!("monday"));
    assert_eq!(compat["revision"], json!(8));

    // 3. Switch live to Sunday and check month-end crossing 2026-10-28 (Wed) / 2026-11-29 (Sun).
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");
    let sun_add = body_of(&server.call(
        "add_block",
        json!({
            "operation_id": "op-sun-club",
            "week_start": "2026-11-29",
            "title": "SunMove",
            "days": [0],
            "start": "16:00",
            "end": "17:00"
        }),
        9,
    ));
    let sun_id = sun_add["result"]["block_id"].as_str().unwrap_or("");
    let sun_move = body_of(&server.call(
        "move_block",
        json!({
            "operation_id": "op-sun-move-cross",
            "week_start": "2026-11-29",
            "expected_revision": sun_add["revision"],
            "block_id": sun_id,
            "day": 4,
            "start": "18:00",
            "end": "19:00"
        }),
        10,
    ));
    assert_eq!(sun_move["ok"], json!(true), "got {sun_move}");
    assert_eq!(sun_move["result"]["week_starts_on"], json!("sunday"));
    assert!(
        find_block(
            &week_row(&world.database_arg, world.user, "2026-11-23")
                .unwrap()
                .0,
            sun_id
        )
        .is_null()
    );
    assert_eq!(
        find_block(
            &week_row(&world.database_arg, world.user, "2026-11-30")
                .unwrap()
                .0,
            sun_id
        )["days"],
        json!([3])
    );
    let sun_del = body_of(&server.call(
        "delete_block",
        json!({
            "operation_id": "op-sun-del-cross",
            "week_start": "2026-11-29",
            "expected_revision": sun_move["revision"],
            "block_id": sun_id,
            "scope": "series"
        }),
        11,
    ));
    assert_eq!(sun_del["ok"], json!(true));
    assert_eq!(sun_del["result"]["week_starts_on"], json!("sunday"));
    assert!(
        find_block(
            &week_row(&world.database_arg, world.user, "2026-11-30")
                .unwrap()
                .0,
            sun_id
        )
        .is_null()
    );
}

#[test]
fn shown_move_and_delete_reply_failure_rolls_back_atomically() {
    let world = signed_in("blocks-reply-fault");
    seed_week(&world, json!([club(&[3], "16:00")]));
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let install_trigger = |db: &str| {
        let conn = open_connection(Path::new(db)).expect("open");
        conn.execute_batch(
            "CREATE TRIGGER fail_reply_update BEFORE UPDATE OF response ON operations \
             BEGIN SELECT RAISE(FAIL, 'review injected reply failure'); END;",
        )
        .expect("trigger");
    };
    let drop_trigger = |db: &str| {
        let conn = open_connection(Path::new(db)).expect("open");
        conn.execute_batch("DROP TRIGGER fail_reply_update;")
            .expect("drop");
    };

    let mut server = boot(&world);
    server.handshake();

    // 1. move_block across seam (day 5 = Mon Oct 26 in second week).
    install_trigger(&world.database_arg);
    let move_args = json!({
        "operation_id": "op-fault-move",
        "week_start": "2026-10-21",
        "expected_revision": [4, 0],
        "block_id": "club",
        "day": 5,
        "start": "18:00",
        "end": "19:00"
    });
    let move_fail = server.call("move_block", move_args.clone(), 2);
    assert!(
        tool_error_text(&move_fail).is_some(),
        "fault must fail move_block, got {move_fail}"
    );
    assert_eq!(
        week_row(&world.database_arg, world.user, "2026-10-19")
            .unwrap()
            .1,
        4
    );
    assert!(week_row(&world.database_arg, world.user, "2026-10-26").is_none());

    drop_trigger(&world.database_arg);
    let move_ok = body_of(&server.call("move_block", move_args, 3));
    assert_eq!(move_ok["ok"], json!(true), "got {move_ok}");
    assert_eq!(move_ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(move_ok["revision"], json!([5, 1]));

    // 2. delete_block on non-empty week (label.is_some()).
    install_trigger(&world.database_arg);
    let del_args = json!({
        "operation_id": "op-fault-del",
        "week_start": "2026-10-21",
        "expected_revision": [5, 1],
        "block_id": "club",
        "scope": "series"
    });
    let del_fail = server.call("delete_block", del_args.clone(), 4);
    assert!(
        tool_error_text(&del_fail).is_some(),
        "fault must fail delete_block, got {del_fail}"
    );
    assert_eq!(
        week_row(&world.database_arg, world.user, "2026-10-26")
            .unwrap()
            .1,
        1
    );

    drop_trigger(&world.database_arg);
    let del_ok = body_of(&server.call("delete_block", del_args, 5));
    assert_eq!(del_ok["ok"], json!(true), "got {del_ok}");
    assert_eq!(del_ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(del_ok["revision"], json!([5, 2]));
}
