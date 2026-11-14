//! Fixed time the assistant adds or changes, with the rules of the desktop's block editor
//! (`widgets.py` `BlockDialog.accept`): the end comes after the start ("End needs to be later
//! than Start (18:00)."), a new day or a moved start may not be in the past
//! (`grid.rs` `past_problem`; now is Wednesday 2026-10-21 12:00), and landing beside another block
//! is allowed and named (`span_clash`). School and Setup's activities may now change too, as the
//! desktop changes them: this week only, or from this week on (`every_week`), and one day may be
//! skipped (missed) or deleted.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_engine::repeats::edit_intent;
use flexweek_store::{
    apply_repeat_intents, initialize, insert_preferences, insert_user, open_connection,
    open_session,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const WEEK: &str = "2026-10-19";
const NEXT: &str = "2026-10-26";

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
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
    ]);
    server.handshake();
    server
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

/// School Monday to Friday 08:00-15:00, standing from this week, as Setup leaves it.
fn school_stands(world: &World) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let intent = edit_intent("school", WEEK, None, Some(&school)).expect("new");
    apply_repeat_intents(&conn, world.user, &[intent]).expect("school stands");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn club(days: &[i64], start: &str) -> Value {
    json!({
        "id": "club", "title": "Club", "kind": "locked", "duration_min": 60,
        "days": days, "start": start, "priority": 3, "energy": "medium"
    })
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
}

fn stored(world: &World, week: &str) -> (Value, i64) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
        (world.user, week),
        |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
    )
    .map(|(text, revision)| (serde_json::from_str(&text).unwrap_or(Value::Null), revision))
    .unwrap_or((Value::Null, -1))
}

fn point_count(world: &World) -> i64 {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT COUNT(*) FROM restore_points WHERE user_id = ?1",
        (world.user,),
        |row| row.get::<_, i64>(0),
    )
    .unwrap_or(-1)
}

fn seen(server: &mut Server, week: &str, id: i64) -> Value {
    body_of(&server.call("get_week", json!({"week_start": week}), id))["blocks"].clone()
}

fn by_id<'a>(blocks: &'a Value, id: &str) -> &'a Value {
    blocks
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|block| block.get("id").and_then(Value::as_str) == Some(id))
        })
        .unwrap_or(&Value::Null)
}

fn titled<'a>(blocks: &'a Value, title: &str) -> Vec<&'a Value> {
    blocks
        .as_array()
        .into_iter()
        .flatten()
        .filter(|block| block.get("title").and_then(Value::as_str) == Some(title))
        .collect()
}

fn add(server: &mut Server, operation_id: &str, extra: Value, id: i64) -> Value {
    let mut arguments = json!({
        "operation_id": operation_id,
        "week_start": WEEK,
        "title": "Dinner",
        "category": "meals",
        "days": [3, 4],
        "start": "18:00",
        "end": "18:30"
    });
    if let (Some(base), Some(more)) = (arguments.as_object_mut(), extra.as_object()) {
        for (key, value) in more {
            base.insert(key.clone(), value.clone());
        }
    }
    server.call("add_block", arguments, id)
}

#[test]
fn add_block_puts_fixed_time_on_the_days_asked() {
    let world = signed_in("add-dinner");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let response = add(&mut server, "op-add-dinner", json!({}), 2);
    let body = body_of(&response);
    assert_eq!(body["ok"], json!(true), "the block lands, got {response}");
    assert_eq!(
        body["revision"],
        json!(5),
        "adding bumps the week, got {body}"
    );
    let id = body["result"]["block_id"]
        .as_str()
        .unwrap_or("")
        .to_string();
    assert!(
        !id.is_empty() && id != "club",
        "the reply names the new block, got {body}"
    );
    let (blocks, revision) = stored(&world, WEEK);
    assert_eq!(revision, 5);
    let dinner = by_id(&blocks, &id);
    assert_eq!(dinner["title"], json!("Dinner"), "got {blocks}");
    assert_eq!(
        dinner["kind"],
        json!("locked"),
        "fixed time is a locked block"
    );
    assert_eq!(dinner["category"], json!("meals"));
    assert_eq!(
        dinner["days"],
        json!([3, 4]),
        "it repeats on the days asked"
    );
    assert_eq!(dinner["start"], json!("18:00"));
    assert_eq!(
        dinner["duration_min"],
        json!(30),
        "the length is end minus start"
    );
    assert_eq!(
        by_id(&blocks, "club")["start"],
        json!("16:00"),
        "the rest stays"
    );
    let again = add(&mut server, "op-add-dinner", json!({}), 3);
    assert_eq!(body_of(&again), body, "a retry returns the first answer");
    assert_eq!(stored(&world, WEEK).1, 5, "a retry adds nothing");
}

#[test]
fn add_block_to_a_week_nobody_saved_starts_it() {
    let world = signed_in("add-unsaved-week");
    let mut server = boot(&world);
    let response = add(
        &mut server,
        "op-add-next-week",
        json!({"week_start": NEXT, "days": [0]}),
        2,
    );
    assert_eq!(body_of(&response)["ok"], json!(true), "got {response}");
    let (blocks, revision) = stored(&world, NEXT);
    assert_eq!(revision, 1, "the first save of a week is revision 1");
    assert_eq!(titled(&blocks, "Dinner").len(), 1, "got {blocks}");
}

#[test]
fn add_block_beside_school_is_allowed_and_named() {
    let world = signed_in("add-beside-school");
    school_stands(&world);
    let mut server = boot(&world);
    let response = add(
        &mut server,
        "op-add-dentist",
        json!({"title": "Dentist", "category": "extra", "days": [3], "start": "10:00", "end": "11:00"}),
        2,
    );
    let body = body_of(&response);
    assert_eq!(
        body["ok"],
        json!(true),
        "landing on school is allowed, got {response}"
    );
    assert_eq!(
        body["result"]["beside"],
        json!("School"),
        "the reply names the block it sits beside, got {body}"
    );
    let week = seen(&mut server, WEEK, 3);
    assert_eq!(titled(&week, "Dentist").len(), 1, "got {week}");
    assert_eq!(titled(&week, "School").len(), 1, "school stays, got {week}");
}

#[test]
fn add_block_accepts_a_start_that_has_already_passed() {
    // Now is Wednesday 2026-10-21 12:00: 09:00 today and any time on Monday are behind us.
    let world = signed_in("add-in-the-past");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let today = add(
        &mut server,
        "op-add-past-today",
        json!({"title": "Breakfast", "days": [2], "start": "09:00", "end": "10:00"}),
        2,
    );
    assert_eq!(
        body_of(&today)["ok"],
        json!(true),
        "a fixed time earlier today is accepted, got {today}"
    );
    let earlier_day = add(
        &mut server,
        "op-add-past-day",
        json!({"title": "Practice", "days": [0], "start": "18:00", "end": "19:00"}),
        3,
    );
    assert_eq!(
        body_of(&earlier_day)["ok"],
        json!(true),
        "a fixed time on an earlier day is accepted, got {earlier_day}"
    );
    let week = seen(&mut server, WEEK, 4);
    assert_eq!(titled(&week, "Breakfast").len(), 1, "got {week}");
    assert_eq!(titled(&week, "Practice").len(), 1, "got {week}");
}

#[test]
fn add_block_refuses_what_the_block_editor_refuses() {
    let world = signed_in("add-refusals");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let cases = [
        (
            json!({"start": "18:00", "end": "18:00"}),
            Some("End needs to be later than Start (18:00)."),
        ),
        (
            json!({"start": "19:00", "end": "18:00"}),
            Some("End needs to be later than Start (19:00)."),
        ),
        (
            json!({"category": "assignments"}),
            Some("Use the homework editor for flexible work."),
        ),
        (json!({"category": "party"}), None),
        (json!({"title": ""}), None),
        (json!({"days": []}), None),
        (json!({"days": [7]}), None),
        (json!({"end": "24:30"}), None),
    ];
    for (offset, (extra, words)) in cases.iter().enumerate() {
        let response = add(
            &mut server,
            &format!("op-refuse-{offset:02}"),
            extra.clone(),
            10 + offset as i64,
        );
        let error = tool_error_text(&response);
        assert!(error.is_some(), "{extra} must be refused, got {response}");
        if let Some(words) = words {
            assert_eq!(
                error,
                Some(*words),
                "{extra} is refused in the editor's words"
            );
        }
    }
    assert_eq!(stored(&world, WEEK).1, 4, "a refused add writes nothing");
    assert_eq!(
        point_count(&world),
        0,
        "a refused add saves no restore point"
    );
}

#[test]
fn edit_block_changes_the_title_and_time() {
    let world = signed_in("edit-club");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let response = server.call(
        "edit_block",
        json!({
            "operation_id": "op-edit-club",
            "week_start": WEEK,
            "expected_revision": 4,
            "block_id": "club",
            "title": "Chess club",
            "start": "17:00",
            "end": "18:30"
        }),
        2,
    );
    assert_eq!(body_of(&response)["ok"], json!(true), "got {response}");
    let (blocks, revision) = stored(&world, WEEK);
    assert_eq!(revision, 5);
    let edited = by_id(&blocks, "club");
    assert_eq!(edited["title"], json!("Chess club"), "got {edited}");
    assert_eq!(edited["start"], json!("17:00"));
    assert_eq!(edited["duration_min"], json!(90));
    assert_eq!(edited["days"], json!([2]), "the days stay as they were");
    let renamed = server.call(
        "edit_block",
        json!({
            "operation_id": "op-edit-club-title",
            "week_start": WEEK,
            "expected_revision": 5,
            "block_id": "club",
            "title": "Chess"
        }),
        3,
    );
    assert_eq!(
        body_of(&renamed)["ok"],
        json!(true),
        "a title alone is enough, got {renamed}"
    );
    let (blocks, _) = stored(&world, WEEK);
    assert_eq!(
        by_id(&blocks, "club")["start"],
        json!("17:00"),
        "the time stays"
    );
    assert_eq!(by_id(&blocks, "club")["duration_min"], json!(90));
}

#[test]
fn edit_block_with_a_stale_revision_writes_nothing() {
    let world = signed_in("edit-stale");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let response = server.call(
        "edit_block",
        json!({
            "operation_id": "op-edit-stale",
            "week_start": WEEK,
            "expected_revision": 3,
            "block_id": "club",
            "title": "Chess club"
        }),
        2,
    );
    let body = body_of(&response);
    assert_eq!(body["error"], json!("conflict"), "got {response}");
    assert_eq!(body["current_revision"], json!(4));
    let (blocks, revision) = stored(&world, WEEK);
    assert_eq!(revision, 4, "nothing was written");
    assert_eq!(by_id(&blocks, "club")["title"], json!("Club"));
    assert_eq!(
        point_count(&world),
        0,
        "a refused change leaves no restore point behind"
    );
}

#[test]
fn edit_block_of_one_day_splits_it_off_the_series() {
    let world = signed_in("edit-one-day");
    seed_week(&world, json!([club(&[2, 3, 4], "16:00")]));
    let mut server = boot(&world);
    let response = server.call(
        "edit_block",
        json!({
            "operation_id": "op-edit-thursday",
            "week_start": WEEK,
            "expected_revision": 4,
            "block_id": "club",
            "scope": "occurrence",
            "day": 3,
            "start": "18:00",
            "end": "19:00"
        }),
        2,
    );
    assert_eq!(body_of(&response)["ok"], json!(true), "got {response}");
    let (blocks, _) = stored(&world, WEEK);
    assert_eq!(
        by_id(&blocks, "club")["days"],
        json!([2, 4]),
        "the series keeps its other days"
    );
    assert_eq!(by_id(&blocks, "club")["start"], json!("16:00"));
    let thursday: Vec<_> = titled(&blocks, "Club")
        .into_iter()
        .filter(|block| block["days"] == json!([3]))
        .collect();
    assert_eq!(
        thursday.len(),
        1,
        "Thursday is a block of its own, got {blocks}"
    );
    assert_eq!(thursday[0]["start"], json!("18:00"));
    assert_eq!(thursday[0]["duration_min"], json!(60));
}

#[test]
fn edit_block_may_move_a_fixed_time_to_a_start_that_has_passed() {
    // Now is Wednesday 2026-10-21 12:00.
    let world = signed_in("edit-into-the-past");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let response = server.call(
        "edit_block",
        json!({"operation_id": "op-edit-club-past", "week_start": WEEK, "expected_revision": 4,
            "block_id": "club", "start": "10:00", "end": "11:00"}),
        2,
    );
    assert_eq!(
        body_of(&response)["ok"],
        json!(true),
        "an earlier start today is accepted, got {response}"
    );
    let (blocks, _) = stored(&world, WEEK);
    assert_eq!(by_id(&blocks, "club")["start"], json!("10:00"));
}

#[test]
fn edit_block_refuses_homework() {
    let world = signed_in("edit-refusals");
    seed_week(
        &world,
        json!([
            club(&[2], "16:00"),
            {"id": "reading", "title": "Reading", "kind": "flexible", "duration_min": 30,
             "days": [3], "priority": 3, "energy": "medium"},
            {"id": "gym", "title": "Gym", "kind": "locked", "duration_min": 60,
             "days": [0], "start": "07:00", "priority": 3, "energy": "medium"}
        ]),
    );
    let mut server = boot(&world);
    let flexible = server.call(
        "edit_block",
        json!({"operation_id": "op-edit-reading", "week_start": WEEK, "expected_revision": 4,
            "block_id": "reading", "title": "More reading"}),
        2,
    );
    assert_eq!(
        tool_error_text(&flexible),
        Some("Use the homework editor for flexible work."),
        "got {flexible}"
    );
    let missing = server.call(
        "edit_block",
        json!({"operation_id": "op-edit-nope", "week_start": WEEK, "expected_revision": 4,
            "block_id": "nope", "title": "Nope"}),
        4,
    );
    assert!(
        tool_error_text(&missing).is_some(),
        "a missing block is refused, got {missing}"
    );
    assert_eq!(stored(&world, WEEK).1, 4, "refusals write nothing");
    let renamed = server.call(
        "edit_block",
        json!({"operation_id": "op-edit-gym", "week_start": WEEK, "expected_revision": 4,
            "block_id": "gym", "title": "Morning gym"}),
        5,
    );
    assert_eq!(
        body_of(&renamed)["ok"],
        json!(true),
        "a block on an earlier day keeps its start, so its title may change, got {renamed}"
    );
}

#[test]
fn skip_block_day_marks_one_day_missed_and_back() {
    let world = signed_in("skip-club");
    seed_week(&world, json!([club(&[2, 3], "16:00")]));
    let mut server = boot(&world);
    let skipped = server.call(
        "skip_block_day",
        json!({"operation_id": "op-skip-thursday", "week_start": WEEK, "expected_revision": 4,
            "block_id": "club", "day": 3}),
        2,
    );
    assert_eq!(body_of(&skipped)["ok"], json!(true), "got {skipped}");
    let (blocks, _) = stored(&world, WEEK);
    assert_eq!(
        by_id(&blocks, "club")["missed_days"],
        json!([3]),
        "got {blocks}"
    );
    assert_eq!(
        by_id(&blocks, "club")["days"],
        json!([2, 3]),
        "the day stays, only missed"
    );
    let back = server.call(
        "skip_block_day",
        json!({"operation_id": "op-unskip-thursday", "week_start": WEEK, "expected_revision": 5,
            "block_id": "club", "day": 3, "skipped": false}),
        3,
    );
    assert_eq!(body_of(&back)["ok"], json!(true), "got {back}");
    let (blocks, _) = stored(&world, WEEK);
    assert!(
        by_id(&blocks, "club")
            .get("missed_days")
            .is_none_or(|days| days == &json!([])),
        "the day is back, got {blocks}"
    );
    let off_day = server.call(
        "skip_block_day",
        json!({"operation_id": "op-skip-friday", "week_start": WEEK, "expected_revision": 6,
            "block_id": "club", "day": 4}),
        4,
    );
    assert!(
        tool_error_text(&off_day).is_some(),
        "a day the block is not on cannot be skipped, got {off_day}"
    );
}

#[test]
fn school_moved_on_one_day_changes_this_week_only() {
    let world = signed_in("school-move-thursday");
    school_stands(&world);
    let mut server = boot(&world);
    let moved = server.call(
        "move_block",
        json!({"operation_id": "op-school-thursday", "week_start": WEEK, "expected_revision": 0,
            "block_id": "school", "day": 3, "start": "09:00", "end": "15:00"}),
        2,
    );
    assert_eq!(
        body_of(&moved)["ok"],
        json!(true),
        "school may move now, got {moved}"
    );
    let week = seen(&mut server, WEEK, 3);
    let schools = titled(&week, "School");
    assert!(
        schools
            .iter()
            .any(|block| block["days"] == json!([3]) && block["start"] == json!("09:00")),
        "Thursday's school starts at 09:00 this week, got {week}"
    );
    assert!(
        schools
            .iter()
            .any(|block| block["days"] == json!([0, 1, 2, 4]) && block["start"] == json!("08:00")),
        "the other days keep 08:00, got {week}"
    );
    let next = seen(&mut server, NEXT, 4);
    assert_eq!(
        by_id(&next, "school")["start"],
        json!("08:00"),
        "next week keeps school, got {next}"
    );
    assert_eq!(by_id(&next, "school")["days"], json!([0, 1, 2, 3, 4]));
}

#[test]
fn school_edited_every_week_stands_from_this_week_on() {
    let world = signed_in("school-every-week");
    school_stands(&world);
    let mut server = boot(&world);
    let edited = server.call(
        "edit_block",
        json!({"operation_id": "op-school-later", "week_start": WEEK, "expected_revision": 0,
            "block_id": "school", "start": "08:30", "end": "15:30", "every_week": true}),
        2,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    let week = seen(&mut server, WEEK, 3);
    assert_eq!(
        by_id(&week, "school")["start"],
        json!("08:30"),
        "got {week}"
    );
    let next = seen(&mut server, NEXT, 4);
    assert_eq!(
        by_id(&next, "school")["start"],
        json!("08:30"),
        "later weeks change too, got {next}"
    );
    assert_eq!(by_id(&next, "school")["duration_min"], json!(420));
    let this_week_only = server.call(
        "edit_block",
        json!({"operation_id": "op-school-this-week", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1,
            "block_id": "school", "start": "09:00", "end": "15:30"}),
        5,
    );
    assert_eq!(
        body_of(&this_week_only)["ok"],
        json!(true),
        "got {this_week_only}"
    );
    let next = seen(&mut server, NEXT, 6);
    assert_eq!(
        by_id(&next, "school")["start"],
        json!("08:30"),
        "without every_week next week stays"
    );
}

/// Design study item 8 (P1 and P4 through the assistant): an `every_week` change names only what it
/// changes, measured against the repeat, so this week's deleted Friday and one-week name stay this
/// week's and the later weeks keep Friday and the name School.
#[test]
fn every_week_changes_only_the_named_fields_and_leaves_this_weeks_own_changes_here() {
    let world = signed_in("school-every-week-own");
    school_stands(&world);
    let mut server = boot(&world);
    let deleted = server.call(
        "delete_block",
        json!({"operation_id": "op-own-fri", "week_start": WEEK, "expected_revision": 0,
            "block_id": "school", "scope": "occurrence", "day": 4}),
        2,
    );
    assert_eq!(body_of(&deleted)["ok"], json!(true), "got {deleted}");
    let renamed = server.call(
        "edit_block",
        json!({"operation_id": "op-own-trip", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1, "block_id": "school", "title": "School trip"}),
        3,
    );
    assert_eq!(body_of(&renamed)["ok"], json!(true), "got {renamed}");
    let later = server.call(
        "edit_block",
        json!({"operation_id": "op-own-end", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1, "block_id": "school", "end": "14:00",
            "every_week": true}),
        4,
    );
    assert_eq!(body_of(&later)["ok"], json!(true), "got {later}");
    let week = seen(&mut server, WEEK, 5);
    let school = by_id(&week, "school");
    assert_eq!(
        (&school["title"], &school["days"], &school["duration_min"]),
        (&json!("School trip"), &json!([0, 1, 2, 3]), &json!(360)),
        "got {week}"
    );
    let next = seen(&mut server, NEXT, 6);
    let school = by_id(&next, "school");
    assert_eq!(
        (
            &school["title"],
            &school["days"],
            &school["start"],
            &school["duration_min"]
        ),
        (
            &json!("School"),
            &json!([0, 1, 2, 3, 4]),
            &json!("08:00"),
            &json!(360)
        ),
        "got {next}"
    );
}

#[test]
fn school_day_off_skips_or_deletes_one_day_this_week() {
    let world = signed_in("school-day-off");
    school_stands(&world);
    let mut server = boot(&world);
    let skipped = server.call(
        "skip_block_day",
        json!({"operation_id": "op-school-skip-thu", "week_start": WEEK, "expected_revision": 0,
            "block_id": "school", "day": 3}),
        2,
    );
    assert_eq!(
        body_of(&skipped)["ok"],
        json!(true),
        "school may be skipped, got {skipped}"
    );
    let week = seen(&mut server, WEEK, 3);
    assert_eq!(
        by_id(&week, "school")["missed_days"],
        json!([3]),
        "got {week}"
    );
    let deleted = server.call(
        "delete_block",
        json!({"operation_id": "op-school-del-fri", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1,
            "block_id": "school", "scope": "occurrence", "day": 4}),
        4,
    );
    assert_eq!(body_of(&deleted)["ok"], json!(true), "got {deleted}");
    let week = seen(&mut server, WEEK, 5);
    assert_eq!(
        by_id(&week, "school")["days"],
        json!([0, 1, 2, 3]),
        "Friday is gone, got {week}"
    );
    let next = seen(&mut server, NEXT, 6);
    assert_eq!(
        by_id(&next, "school")["days"],
        json!([0, 1, 2, 3, 4]),
        "next week is whole"
    );
    assert!(
        by_id(&next, "school")
            .get("missed_days")
            .is_none_or(|days| days == &json!([])),
        "a missed day belongs to one week, got {next}"
    );
    let done = server.call(
        "set_block_done",
        json!({"operation_id": "op-school-done", "week_start": WEEK, "block_id": "school",
            "day": 2, "done": true}),
        7,
    );
    assert_eq!(
        body_of(&done)["ok"],
        json!(true),
        "school may be marked done now, got {done}"
    );
}

#[test]
fn school_deleted_this_week_stays_missed_and_every_week_stops_it() {
    let world = signed_in("school-delete");
    school_stands(&world);
    let mut server = boot(&world);
    let this_week = server.call(
        "delete_block",
        json!({"operation_id": "op-school-del-week", "week_start": WEEK, "expected_revision": 0,
            "block_id": "school", "scope": "series"}),
        2,
    );
    assert_eq!(body_of(&this_week)["ok"], json!(true), "got {this_week}");
    let week = seen(&mut server, WEEK, 3);
    assert_eq!(
        by_id(&week, "school")["missed_days"],
        json!([0, 1, 2, 3, 4]),
        "this week keeps school missed on every day, or the standing week brings it back, got {week}"
    );
    let next = seen(&mut server, NEXT, 4);
    assert_eq!(
        by_id(&next, "school")["days"],
        json!([0, 1, 2, 3, 4]),
        "next week keeps school"
    );
    let every = server.call(
        "delete_block",
        json!({"operation_id": "op-school-del-every", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1,
            "block_id": "school", "scope": "series", "every_week": true}),
        5,
    );
    assert_eq!(body_of(&every)["ok"], json!(true), "got {every}");
    let week = seen(&mut server, WEEK, 6);
    assert_eq!(
        by_id(&week, "school"),
        &Value::Null,
        "school is gone this week, got {week}"
    );
    let next = seen(&mut server, NEXT, 7);
    assert_eq!(
        by_id(&next, "school"),
        &Value::Null,
        "and from this week on, got {next}"
    );
}

#[test]
fn one_day_of_school_cannot_be_deleted_from_every_week() {
    // The app asks "this week or every week" only when the whole block goes; one day of School
    // is this week only, and every_week on it must not stop School in later weeks.
    let world = signed_in("school-one-day-every-week");
    school_stands(&world);
    let mut server = boot(&world);
    let refused = server.call(
        "delete_block",
        json!({"operation_id": "op-school-friday-every", "week_start": WEEK,
            "expected_revision": 0, "block_id": "school", "scope": "occurrence", "day": 4,
            "every_week": true}),
        2,
    );
    assert!(tool_error_text(&refused).is_some(), "got {refused}");
    let next = seen(&mut server, NEXT, 3);
    assert_eq!(
        by_id(&next, "school")["days"],
        json!([0, 1, 2, 3, 4]),
        "later weeks keep school"
    );
    assert_eq!(stored(&world, WEEK).1, -1, "nothing was written");
}

#[test]
fn fixed_time_and_a_plan_sent_without_waiting_all_apply() {
    // An assistant planning a day sends its blocks and the plan at once. Each write reads and saves
    // under the one database lock, so none is refused for a revision another one moved.
    let world = signed_in("fixed-at-once");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);
    let titles = ["Lunch", "Walk", "Dinner", "Call"];
    for (offset, title) in titles.iter().enumerate() {
        server.send_call(
            "add_block",
            json!({
                "operation_id": format!("op-at-once-{offset}"),
                "week_start": WEEK,
                "title": title,
                "category": "free",
                "days": [3 + (offset as i64 % 3)],
                "start": format!("{:02}:00", 12 + offset),
                "end": format!("{:02}:30", 12 + offset)
            }),
            10 + offset as i64,
        );
    }
    server.send_call(
        "plan_homework",
        json!({"operation_id": "op-at-once-plan", "week_start": WEEK}),
        20,
    );
    let answers = server.answers(&[10, 11, 12, 13, 20]);
    for answer in &answers {
        let body = body_of(answer);
        assert_eq!(body["ok"], json!(true), "every write lands, got {answer}");
    }
    let (blocks, revision) = stored(&world, WEEK);
    for title in titles {
        assert_eq!(
            titled(&blocks, title).len(),
            1,
            "{title} is saved, got {blocks}"
        );
    }
    assert_eq!(revision, 8, "four adds are four changes to the week");
    assert_eq!(
        point_count(&world),
        4,
        "one restore point per change; a plan with nothing to place saves none"
    );
}

/// A week on screen that does not start on Monday leaves School in two pieces in a stored week when a
/// change there reaches some of its days: `school` and `school@20261021`. The assistant changes or
/// stops School from either piece.
#[test]
fn a_piece_of_school_changes_and_stops_school_every_week() {
    let world = signed_in("school-piece");
    school_stands(&world);
    seed_week(
        &world,
        json!([
            {"id": "school", "title": "School", "kind": "locked", "duration_min": 420,
             "days": [0, 1], "start": "08:00", "category": "class"},
            {"id": "school@20261021", "title": "School", "kind": "locked", "duration_min": 420,
             "days": [2, 3, 4], "start": "10:00", "category": "class"}
        ]),
    );
    let mut server = boot(&world);
    let edited = server.call(
        "edit_block",
        json!({"operation_id": "op-piece-later", "week_start": WEEK, "expected_revision": 4,
            "block_id": "school@20261021", "title": "Classes", "every_week": true}),
        2,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    let week = seen(&mut server, WEEK, 3);
    assert_eq!(
        by_id(&week, "school")["title"],
        json!("Classes"),
        "got {week}"
    );
    assert_eq!(by_id(&week, "school@20261021")["title"], json!("Classes"));
    let next = seen(&mut server, NEXT, 4);
    assert_eq!(
        by_id(&next, "school")["title"],
        json!("Classes"),
        "got {next}"
    );
    let stopped = server.call(
        "delete_block",
        json!({"operation_id": "op-piece-stop", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1,
            "block_id": "school@20261021", "scope": "series", "every_week": true}),
        5,
    );
    assert_eq!(body_of(&stopped)["ok"], json!(true), "got {stopped}");
    let week = seen(&mut server, WEEK, 6);
    assert!(titled(&week, "Classes").is_empty(), "got {week}");
    let next = seen(&mut server, NEXT, 7);
    assert!(titled(&next, "Classes").is_empty(), "got {next}");
}

#[test]
fn fixed_tools_follow_monday_sunday_wednesday_and_month_end_crossing_weeks() {
    let world = signed_in("fixed-shown-weeks");
    school_stands(&world);
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);

    // 1. Monday start keeps week_starts_on: "monday" and integer revision.
    let mon_add = body_of(&add(
        &mut server,
        "op-mon-add",
        json!({"title": "MonBreak", "days": [3], "start": "17:00", "end": "17:30"}),
        2,
    ));
    assert_eq!(mon_add["result"]["week_starts_on"], json!("monday"));
    assert_eq!(mon_add["revision"], json!(5));

    // 2. Switch week-start.json live to Wednesday while the server runs.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed file");

    // Wednesday 2026-10-21 covers 2026-10-19 (rev 5) and 2026-10-26 (rev 0).
    // Day 1 = Thu Oct 22 (first day 3), Day 5 = Mon Oct 26 (second day 0).
    let wed_add = add(
        &mut server,
        "op-wed-add",
        json!({
            "week_start": "2026-10-21",
            "title": "Practice",
            "category": "extra",
            "days": [1, 5],
            "start": "09:00",
            "end": "10:00"
        }),
        3,
    );
    let wed_body = body_of(&wed_add);
    assert_eq!(wed_body["ok"], json!(true), "got {wed_add}");
    assert_eq!(wed_body["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(wed_body["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(wed_body["revision"], json!([6, 1]));
    // Mon Oct 26 at 09:00 overlaps standing School 08:00-15:00 -> beside: "School".
    assert_eq!(wed_body["result"]["beside"], json!("School"));
    let again = body_of(&add(
        &mut server,
        "op-wed-add",
        json!({
            "week_start": "2026-10-21",
            "title": "Practice",
            "category": "extra",
            "days": [1, 5],
            "start": "09:00",
            "end": "10:00"
        }),
        4,
    ));
    assert_eq!(again, wed_body, "retry returns first answer");
    let pid = wed_body["result"]["block_id"].as_str().unwrap_or("");
    assert_eq!(
        by_id(&stored(&world, WEEK).0, pid)["days"],
        json!([3]),
        "Thu Oct 22 stored on first"
    );
    assert_eq!(
        by_id(&stored(&world, NEXT).0, pid)["days"],
        json!([0]),
        "Mon Oct 26 stored on second"
    );

    // Stale pair expected_revision returns conflict with current [6, 1].
    let stale = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-wed-stale",
            "week_start": "2026-10-21",
            "expected_revision": [5, 1],
            "block_id": pid,
            "title": "Nope"
        }),
        5,
    ));
    assert_eq!(
        stale,
        json!({"error": "conflict", "current_revision": [6, 1]})
    );

    // Occurrence edit on day 5 (Mon Oct 26) modifies only second (rev 1 -> 2), leaving first at 6.
    let occ = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-wed-occ",
            "week_start": "2026-10-21",
            "expected_revision": [6, 1],
            "block_id": pid,
            "scope": "occurrence",
            "day": 5,
            "start": "17:00",
            "end": "18:00"
        }),
        6,
    ));
    assert_eq!(occ["ok"], json!(true));
    assert_eq!(occ["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(occ["revision"], json!([6, 2]));
    assert_ne!(occ["result"]["block_id"], json!(pid));
    assert_eq!(stored(&world, WEEK).1, 6, "first unchanged");
    assert_eq!(stored(&world, NEXT).1, 2, "second bumped");

    // every_week edit of School on Wednesday 2026-10-21 with shown days [0, 5] (Wed, Mon -> Mon/Wed [0, 2]).
    let every = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-wed-school-every",
            "week_start": "2026-10-21",
            "expected_revision": [6, 2],
            "block_id": "school",
            "days": [0, 5],
            "start": "08:30",
            "end": "14:30",
            "every_week": true
        }),
        7,
    ));
    assert_eq!(every["ok"], json!(true), "every_week lands, got {every}");
    assert_eq!(every["result"]["week_starts_on"], json!("wednesday"));
    // First keeps Mon/Tue [0, 1] at 08:00; Wed [2] becomes 08:30.
    let first_stored = stored(&world, WEEK).0;
    let first_schools = titled(&first_stored, "School");
    assert!(
        first_schools
            .iter()
            .any(|b| b["days"] == json!([0, 1]) && b["start"] == json!("08:00")),
        "Mon/Tue keep old school, got {first_schools:?}"
    );
    assert!(
        first_schools
            .iter()
            .any(|b| b["days"] == json!([2]) && b["start"] == json!("08:30")),
        "Wed gets new school, got {first_schools:?}"
    );
    // Later weeks get Mon/Wed [0, 2] stored, shown as [0, 5] on Wednesday week 2026-11-04.
    let week3 = seen(&mut server, "2026-11-04", 8);
    let s3 = by_id(&week3, "school");
    assert_eq!(s3["start"], json!("08:30"));
    assert_eq!(s3["days"], json!([0, 5]));
    assert_eq!(
        by_id(&seen(&mut server, "2026-11-02", 18), "school")["days"],
        json!([0, 2])
    );

    // skip_block_day on day 5 (Mon Oct 26, second) bumps only second.
    let cur_revs =
        body_of(&server.call("get_week", json!({"week_start": "2026-10-21"}), 9))["revision"]
            .clone();
    let skip = body_of(&server.call(
        "skip_block_day",
        json!({
            "operation_id": "op-wed-skip",
            "week_start": "2026-10-21",
            "expected_revision": cur_revs,
            "block_id": "school",
            "day": 5
        }),
        10,
    ));
    assert_eq!(skip["ok"], json!(true), "got {skip}");
    assert_eq!(skip["result"]["week_starts_on"], json!("wednesday"));
    let second_stored = stored(&world, NEXT).0;
    let second_schools = titled(&second_stored, "School");
    assert_eq!(second_schools[0]["missed_days"], json!([0]));
    // Unskip day 5.
    let unskip = body_of(&server.call(
        "skip_block_day",
        json!({
            "operation_id": "op-wed-unskip",
            "week_start": "2026-10-21",
            "expected_revision": skip["revision"],
            "block_id": "school",
            "day": 5,
            "skipped": false
        }),
        11,
    ));
    assert_eq!(unskip["ok"], json!(true));

    // 3. Old client passing Monday 2026-10-19 while week_starts_on is wednesday still works.
    let compat = body_of(&server.call(
        "add_block",
        json!({
            "operation_id": "op-mon-compat-fixed",
            "week_start": WEEK,
            "title": "Compat",
            "days": [4],
            "start": "18:00",
            "end": "18:30"
        }),
        12,
    ));
    assert_eq!(compat["ok"], json!(true));
    assert_eq!(compat["result"]["week_starts_on"], json!("monday"));
    assert!(compat["revision"].is_i64(), "plain int rev: {compat}");

    // 4. Month-end crossing Wednesday 2026-10-28..2026-11-03 stores Oct 30 in 2026-10-26 and Nov 3 in 2026-11-02.
    let cross_wed = body_of(&add(
        &mut server,
        "op-wed-monthend",
        json!({
            "week_start": "2026-10-28",
            "title": "CrossWed",
            "days": [2, 6],
            "start": "19:00",
            "end": "19:30"
        }),
        13,
    ));
    assert_eq!(cross_wed["ok"], json!(true), "got {cross_wed}");
    assert_eq!(cross_wed["result"]["week_starts_on"], json!("wednesday"));
    let cwid = cross_wed["result"]["block_id"].as_str().unwrap_or("");
    assert_eq!(
        by_id(&stored(&world, "2026-10-26").0, cwid)["days"],
        json!([4])
    );
    assert_eq!(
        by_id(&stored(&world, "2026-11-02").0, cwid)["days"],
        json!([1])
    );

    // 5. Switch live to Sunday: test 2026-10-25 (Sun..Sat) and month-end crossing 2026-11-29 (Sun..Dec 5).
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun file");
    let sun_add = body_of(&add(
        &mut server,
        "op-sun-add",
        json!({
            "week_start": "2026-10-25",
            "title": "SunCross",
            "days": [0, 6],
            "start": "20:00",
            "end": "20:30"
        }),
        14,
    ));
    assert_eq!(sun_add["ok"], json!(true), "got {sun_add}");
    assert_eq!(sun_add["result"]["week_starts_on"], json!("sunday"));
    let sid = sun_add["result"]["block_id"].as_str().unwrap_or("");
    assert_eq!(
        by_id(&stored(&world, "2026-10-19").0, sid)["days"],
        json!([6])
    );
    assert_eq!(
        by_id(&stored(&world, "2026-10-26").0, sid)["days"],
        json!([5])
    );

    let cross_sun = body_of(&add(
        &mut server,
        "op-sun-monthend",
        json!({
            "week_start": "2026-11-29",
            "title": "DecCross",
            "days": [0, 4],
            "start": "18:00",
            "end": "18:30"
        }),
        15,
    ));
    assert_eq!(cross_sun["ok"], json!(true), "got {cross_sun}");
    assert_eq!(cross_sun["result"]["week_starts_on"], json!("sunday"));
    let dsid = cross_sun["result"]["block_id"].as_str().unwrap_or("");
    assert_eq!(
        by_id(&stored(&world, "2026-11-23").0, dsid)["days"],
        json!([6])
    );
    assert_eq!(
        by_id(&stored(&world, "2026-11-30").0, dsid)["days"],
        json!([3])
    );
}

#[test]
fn every_week_shown_edit_measures_each_half_against_its_own_standing_version() {
    // Part A: first ("School") and second ("Next school") differ, plus a later stop at 2026-11-02
    // and a real per-week override on Thursday in 2026-10-19.
    let world = signed_in("every-week-changed-versions");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let v1 = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let v2 = json!({
        "id": "school", "title": "Next school", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let stop_later =
        json!({"id": "school", "scope": "from", "from_date": "2026-11-02", "stop": true});
    let i1 = edit_intent("school", "2026-10-19", None, Some(&v1)).expect("v1");
    let i2 = edit_intent("school", "2026-10-26", Some(&v1), Some(&v2)).expect("v2");
    apply_repeat_intents(&conn, world.user, &[i1, i2]).expect("standing");
    flexweek_store::apply_repeat_intents(
        &conn,
        world.user,
        &[flexweek_engine::repeats::parse_intent(&stop_later).expect("stop")],
    )
    .expect("stop");
    // Seed a real per-week override on Thursday (day 3 of 2026-10-19) -> "Field trip"
    // while Wed/Fri (days 2, 4) and Mon/Tue (days 0, 1) stay "School".
    let first_seed = json!([
        {"id": "school", "title": "School", "kind": "locked", "duration_min": 420,
         "days": [0, 1, 2, 4], "start": "08:00", "category": "class"},
        {"id": "school@20261021", "title": "Field trip", "kind": "locked", "duration_min": 420,
         "days": [3], "start": "08:00", "category": "class"}
    ]);
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, '2026-10-19', ?2, 1)",
        (world.user, first_seed.to_string()),
    )
    .expect("seed first");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let mut server = boot(&world);
    let edited = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-changed-every",
            "week_start": "2026-10-21",
            "expected_revision": [1, 0],
            "block_id": "school",
            "title": "Classes",
            "every_week": true
        }),
        2,
    ));
    assert_eq!(edited["ok"], json!(true), "got {edited}");
    let shown = seen(&mut server, "2026-10-21", 3);
    // Wed/Fri (shown days 0, 2) and Mon/Tue (shown days 5, 6) all become "Classes"; Thursday (shown day 1) keeps override "Field trip".
    let classes_blocks = titled(&shown, "Classes");
    let classes_days: Vec<i64> = classes_blocks
        .iter()
        .flat_map(|b| {
            b["days"]
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(Value::as_i64)
        })
        .collect();
    assert_eq!(classes_days, vec![0, 2, 5, 6], "shown={shown}");
    assert_eq!(
        titled(&shown, "Field trip").len(),
        1,
        "override kept: {shown}"
    );
    assert!(
        titled(&shown, "School").is_empty(),
        "old standing replaced: {shown}"
    );
    assert!(
        titled(&shown, "Next school").is_empty(),
        "second standing replaced: {shown}"
    );

    // Hidden Mon/Tue of 2026-10-19 stay "School".
    let first_stored = stored(&world, "2026-10-19").0;
    assert!(
        titled(&first_stored, "School")
            .iter()
            .any(|b| b["days"] == json!([0, 1])),
        "hidden Mon/Tue stay School: {first_stored}"
    );
    // Later stop at 2026-11-02 is preserved.
    let nov = seen(&mut server, "2026-11-02", 4);
    assert!(titled(&nov, "Classes").is_empty(), "later stop kept: {nov}");
}

#[test]
fn every_week_shown_edit_works_when_second_week_is_stopped() {
    let world = signed_in("every-week-second-stopped");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let v1 = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let i1 = edit_intent("school", "2026-10-19", None, Some(&v1)).expect("v1");
    apply_repeat_intents(&conn, world.user, &[i1]).expect("standing");
    let stop = flexweek_engine::repeats::parse_intent(&json!({
        "id": "school", "scope": "from", "from_date": "2026-10-26", "stop": true
    }))
    .expect("stop");
    apply_repeat_intents(&conn, world.user, &[stop]).expect("stop second");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let mut server = boot(&world);
    let edited = server.call(
        "edit_block",
        json!({
            "operation_id": "op-stopped-every",
            "week_start": "2026-10-21",
            "expected_revision": [0, 0],
            "block_id": "school",
            "title": "Classes",
            "every_week": true
        }),
        2,
    );
    assert_eq!(
        body_of(&edited)["ok"],
        json!(true),
        "must succeed when second week stopped, got {edited}"
    );
    let shown = seen(&mut server, "2026-10-21", 3);
    assert_eq!(
        titled(&shown, "Classes").len(),
        1,
        "Wed-Fri become Classes: {shown}"
    );
    assert_eq!(titled(&shown, "Classes")[0]["days"], json!([0, 1, 2]));
    // First stored week preserves Mon/Tue as School and Wed-Fri as Classes.
    let first_stored = stored(&world, "2026-10-19").0;
    assert!(
        titled(&first_stored, "School")
            .iter()
            .any(|b| b["days"] == json!([0, 1]))
    );
    assert!(
        titled(&first_stored, "Classes")
            .iter()
            .any(|b| b["days"] == json!([2, 3, 4]))
    );
    // Second week remains stopped.
    let second_seen = seen(&mut server, "2026-10-26", 4);
    assert!(
        titled(&second_seen, "Classes").is_empty(),
        "second week stays stopped: {second_seen}"
    );
}

#[test]
fn monday_validation_keeps_monday_and_sunday_wording_while_shown_uses_first_day() {
    let world = signed_in("monday-days-wording");
    seed_week(&world, json!([club(&[2], "16:00")]));
    let mut server = boot(&world);

    let mon_add = server.call(
        "add_block",
        json!({
            "operation_id": "op-bad-days-mon",
            "week_start": "2026-10-19",
            "title": "Bad",
            "days": [],
            "start": "17:00",
            "end": "18:00"
        }),
        2,
    );
    assert_eq!(
        tool_error_text(&mon_add),
        Some("days must name at least one day, 0 (Monday) to 6 (Sunday), once each"),
        "got {mon_add}"
    );
    let mon_edit = server.call(
        "edit_block",
        json!({
            "operation_id": "op-bad-edit-mon",
            "week_start": "2026-10-19",
            "expected_revision": 4,
            "block_id": "club",
            "days": []
        }),
        3,
    );
    assert_eq!(
        tool_error_text(&mon_edit),
        Some("days must name at least one day, 0 (Monday) to 6 (Sunday), once each"),
        "got {mon_edit}"
    );

    // Switch live to Wednesday: Monday week_start still uses Monday/Sunday wording; Wednesday week_start uses shown wording.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let compat_add = server.call(
        "add_block",
        json!({
            "operation_id": "op-bad-days-compat",
            "week_start": "2026-10-19",
            "title": "Bad",
            "days": [],
            "start": "17:00",
            "end": "18:00"
        }),
        4,
    );
    assert_eq!(
        tool_error_text(&compat_add),
        Some("days must name at least one day, 0 (Monday) to 6 (Sunday), once each"),
        "got {compat_add}"
    );

    let wed_add = server.call(
        "add_block",
        json!({
            "operation_id": "op-bad-days-wed",
            "week_start": "2026-10-21",
            "title": "Bad",
            "days": [],
            "start": "17:00",
            "end": "18:00"
        }),
        5,
    );
    assert_eq!(
        tool_error_text(&wed_add),
        Some(
            "days must name at least one day, 0 (the week's first day) to 6 (its last), once each"
        ),
        "got {wed_add}"
    );
    let wed_edit = server.call(
        "edit_block",
        json!({
            "operation_id": "op-bad-edit-wed",
            "week_start": "2026-10-21",
            "expected_revision": [4, 0],
            "block_id": "club",
            "days": []
        }),
        6,
    );
    assert_eq!(
        tool_error_text(&wed_edit),
        Some(
            "days must name at least one day, 0 (the week's first day) to 6 (its last), once each"
        ),
        "got {wed_edit}"
    );
}

#[test]
fn every_week_start_only_edit_on_shown_week_preserves_each_standing_duration() {
    let world = signed_in("every-week-start-only-shown");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let first_school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let second_school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 300,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let intent1 = edit_intent("school", WEEK, None, Some(&first_school)).expect("intent1");
    let intent2 =
        edit_intent("school", NEXT, Some(&first_school), Some(&second_school)).expect("intent2");
    apply_repeat_intents(&conn, world.user, &[intent1.clone(), intent2.clone()]).expect("standing");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    let initial = body_of(&server.call("get_week", json!({"week_start": "2026-10-21"}), 2));
    assert_eq!(
        by_id(&initial["blocks"], "school")["duration_min"],
        json!(420)
    );

    let edited = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-start-only-every-week",
            "week_start": "2026-10-21",
            "expected_revision": initial["revision"],
            "block_id": "school",
            "start": "09:00",
            "every_week": true
        }),
        3,
    ));
    assert_eq!(edited["ok"], json!(true), "got {edited}");

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let standing_first = Value::Array(
        flexweek_store::standing_blocks(&conn, world.user, WEEK).expect("standing first"),
    );
    let standing_second = Value::Array(
        flexweek_store::standing_blocks(&conn, world.user, NEXT).expect("standing second"),
    );
    let standing_third = Value::Array(
        flexweek_store::standing_blocks(&conn, world.user, "2026-11-02").expect("standing third"),
    );
    drop(conn);

    let first_saved = stored(&world, WEEK).0;
    let wed_fri = first_saved
        .as_array()
        .into_iter()
        .flatten()
        .find(|b| b["days"] == json!([2, 3, 4]))
        .expect("wed-fri block in first week");
    assert_eq!(wed_fri["start"], json!("09:00"));
    assert_eq!(
        wed_fri["duration_min"],
        json!(420),
        "first week Wed-Fri keeps its 420-min span: {first_saved}"
    );
    assert_eq!(by_id(&standing_first, "school")["start"], json!("08:00"));
    assert_eq!(by_id(&standing_first, "school")["duration_min"], json!(420));
    assert_eq!(by_id(&standing_second, "school")["start"], json!("09:00"));
    assert_eq!(
        by_id(&standing_second, "school")["duration_min"],
        json!(300),
        "second standing version keeps its 300-min span on start-only edit: {standing_second}"
    );
    assert_eq!(
        by_id(&standing_third, "school")["duration_min"],
        json!(300),
        "later weeks inherit second's 300-min span: {standing_third}"
    );

    // Explicit end sets the span on both versions.
    let explicit = body_of(&server.call(
        "edit_block",
        json!({
            "operation_id": "op-explicit-end-every-week",
            "week_start": "2026-10-21",
            "expected_revision": edited["revision"],
            "block_id": "school",
            "start": "09:30",
            "end": "11:30",
            "every_week": true
        }),
        4,
    ));
    assert_eq!(explicit["ok"], json!(true), "got {explicit}");

    let first_saved_explicit = stored(&world, WEEK).0;
    let wed_fri_explicit = first_saved_explicit
        .as_array()
        .into_iter()
        .flatten()
        .find(|b| b["days"] == json!([2, 3, 4]))
        .expect("wed-fri block in first week");
    assert_eq!(wed_fri_explicit["duration_min"], json!(120));

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let standing_second_after = Value::Array(
        flexweek_store::standing_blocks(&conn, world.user, NEXT).expect("standing second"),
    );
    assert_eq!(
        by_id(&standing_second_after, "school")["duration_min"],
        json!(120)
    );
    drop(conn);
    drop(server);

    // Symmetric check: start-only edit targeting the second block (300m) keeps first week's Wed-Fri 420m span.
    let sym = signed_in("every-week-start-only-shown-sym");
    std::fs::write(
        Path::new(&sym.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&sym.database_arg)).expect("open");
    apply_repeat_intents(&conn, sym.user, &[intent1, intent2]).expect("standing");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut sym_server = boot(&sym);
    let sym_initial = body_of(&sym_server.call("get_week", json!({"week_start": "2026-10-21"}), 2));
    let edited_second = body_of(&sym_server.call(
        "edit_block",
        json!({
            "operation_id": "op-start-only-every-week-second",
            "week_start": "2026-10-21",
            "expected_revision": sym_initial["revision"],
            "block_id": "school@20261021",
            "start": "10:00",
            "every_week": true
        }),
        3,
    ));
    assert_eq!(edited_second["ok"], json!(true), "got {edited_second}");
    let first_saved_after_second = stored(&sym, WEEK).0;
    let wed_fri_after_second = first_saved_after_second
        .as_array()
        .into_iter()
        .flatten()
        .find(|b| b["days"] == json!([2, 3, 4]))
        .expect("wed-fri block in first week");
    assert_eq!(wed_fri_after_second["start"], json!("10:00"));
    assert_eq!(
        wed_fri_after_second["duration_min"],
        json!(420),
        "first week Wed-Fri keeps its 420-min span when editing second block: {first_saved_after_second}"
    );
}

#[test]
fn shown_fixed_reply_failure_rolls_back_both_weeks_atomically() {
    let world = signed_in("fixed-reply-fault");
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
            .expect("drop trigger");
    };

    let mut server = boot(&world);

    // 1. add_block across seam (Wed day 1 = Thu Oct 22 in first, day 5 = Mon Oct 26 in second).
    install_trigger(&world.database_arg);
    let add_args = json!({
        "operation_id": "op-fault-add",
        "week_start": "2026-10-21",
        "title": "Practice",
        "days": [1, 5],
        "start": "17:00",
        "end": "18:00",
        "expected_revision": [0, 0]
    });
    let add_fail = server.call("add_block", add_args.clone(), 2);
    assert!(
        tool_error_text(&add_fail).is_some(),
        "fault must fail add_block, got {add_fail}"
    );
    assert_eq!(
        stored(&world, WEEK).1,
        -1,
        "first week must roll back completely"
    );
    assert_eq!(
        stored(&world, NEXT).1,
        -1,
        "second week must roll back completely"
    );
    assert_eq!(point_count(&world), 0, "restore point must roll back too");

    drop_trigger(&world.database_arg);
    let add_ok = body_of(&server.call("add_block", add_args, 3));
    assert_eq!(
        add_ok["ok"],
        json!(true),
        "retry after rollback succeeds: {add_ok}"
    );
    assert_eq!(add_ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(add_ok["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(add_ok["revision"], json!([1, 1]));
    let pid = add_ok["result"]["block_id"]
        .as_str()
        .unwrap_or("")
        .to_string();

    // 2. edit_block across seam.
    install_trigger(&world.database_arg);
    let edit_args = json!({
        "operation_id": "op-fault-edit",
        "week_start": "2026-10-21",
        "expected_revision": [1, 1],
        "block_id": pid,
        "title": "Rehearsal"
    });
    let edit_fail = server.call("edit_block", edit_args.clone(), 4);
    assert!(
        tool_error_text(&edit_fail).is_some(),
        "fault must fail edit_block, got {edit_fail}"
    );
    assert_eq!(
        stored(&world, WEEK).1,
        1,
        "first rev unchanged after edit rollback"
    );
    assert_eq!(
        stored(&world, NEXT).1,
        1,
        "second rev unchanged after edit rollback"
    );

    drop_trigger(&world.database_arg);
    let edit_ok = body_of(&server.call("edit_block", edit_args, 5));
    assert_eq!(edit_ok["ok"], json!(true), "edit retry succeeds: {edit_ok}");
    assert_eq!(edit_ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(edit_ok["revision"], json!([2, 2]));

    // 3. skip_block_day on day 5 (in second week).
    install_trigger(&world.database_arg);
    let skip_args = json!({
        "operation_id": "op-fault-skip",
        "week_start": "2026-10-21",
        "expected_revision": [2, 2],
        "block_id": pid,
        "day": 5
    });
    let skip_fail = server.call("skip_block_day", skip_args.clone(), 6);
    assert!(
        tool_error_text(&skip_fail).is_some(),
        "fault must fail skip_block_day, got {skip_fail}"
    );
    assert_eq!(
        stored(&world, NEXT).1,
        2,
        "second rev unchanged after skip rollback"
    );

    drop_trigger(&world.database_arg);
    let skip_ok = body_of(&server.call("skip_block_day", skip_args, 7));
    assert_eq!(skip_ok["ok"], json!(true), "skip retry succeeds: {skip_ok}");
    assert_eq!(skip_ok["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(skip_ok["revision"], json!([2, 3]));
}
