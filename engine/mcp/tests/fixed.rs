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
use flexweek_store::{
    initialize, insert_preferences, insert_user, open_connection, open_session, set_standing,
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
    set_standing(&conn, world.user, WEEK, &json!([school]).to_string()).expect("school stands");
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

fn piano_stands(world: &World, until: Option<&str>) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut piano = json!({
        "id": "weekly-piano", "title": "Piano", "kind": "locked", "duration_min": 60,
        "days": [1, 3], "start": "16:00", "category": "extra"
    });
    if let Some(until) = until {
        piano["until"] = json!(until);
    }
    set_standing(&conn, world.user, WEEK, &json!([piano]).to_string()).expect("piano stands");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

#[test]
fn a_weekly_fixed_time_edited_every_week_stands_from_this_week_on_and_keeps_its_until() {
    let world = signed_in("weekly-every-week");
    // Mon 26 Oct is the next week; Until Wed 28 Oct keeps Tuesday and drops Thursday there.
    piano_stands(&world, Some("2026-10-28"));
    let mut server = boot(&world);
    let edited = server.call(
        "edit_block",
        json!({"operation_id": "op-piano-later", "week_start": WEEK, "expected_revision": 0,
            "block_id": "weekly-piano", "start": "17:00", "end": "18:00", "every_week": true}),
        2,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    let next = seen(&mut server, NEXT, 3);
    let piano = by_id(&next, "weekly-piano");
    assert_eq!(piano["start"], json!("17:00"), "got {next}");
    assert_eq!(
        piano["days"],
        json!([1]),
        "Until still cuts Thursday, got {next}"
    );
    assert_eq!(piano["until"], json!("2026-10-28"));
}

#[test]
fn every_week_on_an_ordinary_block_is_refused_with_the_sentence_that_names_weekly_times() {
    let world = signed_in("ordinary-every-week");
    seed_week(&world, json!([club(&[1], "16:00")]));
    let mut server = boot(&world);
    let refused = server.call(
        "edit_block",
        json!({"operation_id": "op-club-later", "week_start": WEEK,
            "expected_revision": stored(&world, WEEK).1,
            "block_id": "club", "start": "17:00", "end": "18:00", "every_week": true}),
        2,
    );
    assert!(
        tool_error_text(&refused).is_some_and(|text| text.contains("weekly fixed times")),
        "got {refused}"
    );
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
