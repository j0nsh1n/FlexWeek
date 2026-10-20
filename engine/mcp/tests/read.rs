//! Read tools return the day, week, month, homework, routines, and restore points.
//! Expected numbers are the same ones the view rules fix: a full day is 96 slots of 15 minutes,
//! this Wednesday holds 7 of them, and a kept session's week revision is the stored one.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_store::{
    RoutineWrite, create_restore_point, initialize, insert_assignment, insert_preferences,
    insert_user, open_connection, open_session, save_routine, set_standing,
};
use serde_json::{Value, json};

const DATE_RULE: &str = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31";
const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";
const MONTH_RULE: &str = "month must be YYYY-MM between 2000-01 and 2099-12";
const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";

struct World {
    data_arg: String,
    database_arg: String,
}

fn fixture(name: &str) -> World {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database_arg = dir.join("flexweek.db").to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), "2026-10-19").expect("schema");
    let conn = open_connection(Path::new(&database_arg)).expect("open");
    let user = insert_user(&conn, "ada", "hash").expect("user");
    insert_preferences(&conn, user, 1).expect("preferences");
    open_session(&conn, TOKEN, user, NOW_UNIX, true).expect("session");
    for (id, title, due, estimate, completed) in [
        ("essay", "Essay", "2026-10-21T21:00", 90, false),
        ("quiz", "Quiz", "2026-10-20", 30, false),
        ("later", "Later", "2026-10-30", 30, false),
        ("old", "Old", "2026-09-15", 30, false),
        ("done", "Done", "2026-10-22", 30, true),
    ] {
        let body = json!({
            "id": id,
            "title": title,
            "due": due,
            "estimate_min": estimate,
            "focus_minutes": 0,
            "completed": completed,
        })
        .to_string();
        insert_assignment(&conn, user, id, &body).expect("assignment");
    }
    let earlier = json!([{
        "id": "s0", "title": "Draft", "kind": "flexible", "duration_min": 30,
        "days": [2], "start": "16:00", "assignment_id": "essay"
    }])
    .to_string();
    let current = json!([
        {
            "id": "s1", "title": "Draft", "kind": "flexible", "duration_min": 45,
            "days": [2], "start": "16:00", "assignment_id": "essay"
        },
        {
            "id": "class-wed", "title": "School", "kind": "locked", "duration_min": 60,
            "days": [2], "start": "09:00", "category": "school"
        }
    ])
    .to_string();
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)",
        (user, "2026-10-12", earlier),
    )
    .expect("earlier week");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        (user, "2026-10-19", current),
    )
    .expect("current week");
    let standing = json!([{
        "id": "school", "title": "School", "kind": "locked", "duration_min": 60,
        "days": [0], "start": "09:00", "category": "school"
    }])
    .to_string();
    set_standing(&conn, user, "2026-09-28", &standing).expect("standing");
    save_routine(
        &conn,
        user,
        RoutineWrite {
            id: "morning",
            name: "Morning",
            body: r#"[{"id":"stretch","title":"Stretch"}]"#,
            revision: 0,
            stamp: "2026-10-21T12:00:00",
            max_count: 50,
        },
    )
    .expect("routine");
    create_restore_point(
        &conn,
        user,
        "before",
        "Before",
        "2026-10-21T12:00:00",
        &[],
        20,
    )
    .expect("restore point");
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

fn body_of(response: &Value) -> Value {
    serde_json::from_str(tool_ok_text(response).unwrap_or("null")).unwrap_or(Value::Null)
}

fn list<'a>(value: &'a Value, key: &str) -> Option<&'a Vec<Value>> {
    value.get(key).and_then(Value::as_array)
}

fn by_id<'a>(items: &'a [Value], id: &str) -> Option<&'a Value> {
    items
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(id))
}

fn ids_of(items: &[Value]) -> Vec<&str> {
    items
        .iter()
        .filter_map(|item| item.get("id").and_then(Value::as_str))
        .collect()
}

#[test]
fn get_today_rewrites_the_session_and_counts_the_open_afternoon() {
    let world = fixture("today");
    let mut server = boot(&world);
    server.handshake();
    let response = server.call("get_today", json!({}), 2);
    let day = body_of(&response);
    assert_eq!(
        day.get("date").and_then(Value::as_str),
        Some("2026-10-21"),
        "with no date, today is the date of --now, got {response}"
    );
    let sessions = list(&day, "sessions").filter(|items| !items.is_empty());
    assert!(
        sessions.is_some(),
        "the day must list its work session, got {response}"
    );
    let sessions = sessions.expect("asserted");
    assert_eq!(sessions[0].get("id").and_then(Value::as_str), Some("s1"));
    assert_eq!(
        sessions[0].get("title").and_then(Value::as_str),
        Some("Essay"),
        "the stored title Draft must be rewritten from the assignment"
    );
    assert_eq!(
        day.get("workload")
            .and_then(|item| item.get("available_min"))
            .and_then(Value::as_i64),
        Some(1335),
        "a full day minus the two placed blocks is (96 - 7) * 15"
    );
    let due = list(&day, "due_soon").filter(|items| !items.is_empty());
    assert!(due.is_some(), "due soon must not be empty");
    assert_eq!(
        ids_of(due.expect("asserted")),
        vec!["old", "quiz", "essay"],
        "due soon is everything open through tomorrow"
    );
}

#[test]
fn get_week_returns_the_saved_revision() {
    let world = fixture("week");
    let mut server = boot(&world);
    server.handshake();
    let saved = body_of(&server.call("get_week", json!({"week_start": "2026-10-19"}), 2));
    assert_eq!(
        saved.get("revision").and_then(Value::as_i64),
        Some(4),
        "the week tool returns the stored revision"
    );
    let blocks = list(&saved, "blocks").filter(|items| !items.is_empty());
    assert!(blocks.is_some(), "the saved week must have blocks");
    let blocks = blocks.expect("asserted");
    assert_eq!(
        by_id(blocks, "s1")
            .and_then(|block| block.get("title"))
            .and_then(Value::as_str),
        Some("Essay"),
        "the week view rewrites the stored title"
    );
    assert!(
        by_id(blocks, "school").is_some(),
        "standing school is part of the week"
    );
    let empty = body_of(&server.call("get_week", json!({"week_start": "2026-10-26"}), 3));
    assert_eq!(
        empty.get("revision").and_then(Value::as_i64),
        Some(0),
        "a week nobody saved reads as revision 0"
    );
    let empty_blocks = list(&empty, "blocks").filter(|items| !items.is_empty());
    assert!(
        empty_blocks.is_some(),
        "standing still fills a week that was never saved"
    );
    assert!(
        by_id(empty_blocks.expect("asserted"), "school").is_some(),
        "the unsaved week shows standing school"
    );
}

#[test]
fn get_month_keeps_the_stored_chip_title() {
    let world = fixture("month");
    let mut server = boot(&world);
    server.handshake();
    let month = body_of(&server.call("get_month", json!({"month": "2026-10"}), 2));
    assert_eq!(
        month.get("start").and_then(Value::as_str),
        Some("2026-10-01"),
        "October starts on the 1st"
    );
    let days = list(&month, "days").filter(|items| !items.is_empty());
    assert!(days.is_some(), "the month grid must not be empty");
    let days = days.expect("asserted");
    assert_eq!(
        days.len(),
        35,
        "28 September through 1 November is five weeks"
    );
    let monday = days
        .iter()
        .find(|day| day.get("date").and_then(Value::as_str) == Some("2026-09-28"));
    assert_eq!(
        monday
            .and_then(|day| day.get("locked_count"))
            .and_then(Value::as_i64),
        Some(1),
        "an unsaved Monday still shows the standing school block"
    );
    let wednesday = days
        .iter()
        .find(|day| day.get("date").and_then(Value::as_str) == Some("2026-10-21"));
    let chips = wednesday
        .and_then(|day| list(day, "blocks"))
        .filter(|items| !items.is_empty());
    assert!(chips.is_some(), "the Wednesday must have chips");
    assert_eq!(
        by_id(chips.expect("asserted"), "s1")
            .and_then(|chip| chip.get("title"))
            .and_then(Value::as_str),
        Some("Draft"),
        "a month chip keeps the stored title"
    );
}

#[test]
fn list_homework_sorts_by_due_and_names_every_session_week() {
    let world = fixture("homework");
    let mut server = boot(&world);
    server.handshake();
    let open = body_of(&server.call("list_homework", json!({"week_start": "2026-10-19"}), 2));
    let items = list(&open, "assignments").filter(|items| !items.is_empty());
    assert!(items.is_some(), "the homework list must not be empty");
    let items = items.expect("asserted");
    assert_eq!(
        ids_of(items),
        vec!["old", "quiz", "essay", "later"],
        "date order, and a completed row stays out"
    );
    let essay = by_id(items, "essay");
    assert_eq!(
        essay.and_then(|item| item.get("session_weeks")),
        Some(&json!(["2026-10-12", "2026-10-19"])),
        "session weeks are every week that holds the assignment, oldest first"
    );
    assert_eq!(
        essay
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(45)
    );
    let with_done = body_of(&server.call(
        "list_homework",
        json!({"week_start": "2026-10-19", "include_completed": true}),
        3,
    ));
    let done_items = list(&with_done, "assignments").filter(|items| !items.is_empty());
    assert!(
        done_items.is_some(),
        "include_completed must still return a list"
    );
    assert_eq!(
        ids_of(done_items.expect("asserted")),
        vec!["old", "quiz", "essay", "done", "later"],
        "the completed row sorts on its due date among the others"
    );
}

#[test]
fn list_routines_and_restore_points_use_the_route_names() {
    let world = fixture("lists");
    let mut server = boot(&world);
    server.handshake();
    let routines = body_of(&server.call("list_routines", json!({}), 2));
    let rows = list(&routines, "routines").filter(|items| !items.is_empty());
    assert!(rows.is_some(), "routines must not be empty");
    let row = &rows.expect("asserted")[0];
    assert_eq!(row.get("name").and_then(Value::as_str), Some("Morning"));
    assert_eq!(
        row.get("revision").and_then(Value::as_i64),
        Some(1),
        "a new routine is stored at revision 1"
    );
    let blocks = list(row, "blocks").filter(|items| !items.is_empty());
    assert!(blocks.is_some(), "a routine body is the block list");
    assert_eq!(
        blocks.expect("asserted")[0]
            .get("title")
            .and_then(Value::as_str),
        Some("Stretch")
    );
    let points = body_of(&server.call("list_restore_points", json!({}), 3));
    let listed = list(&points, "restore_points").filter(|items| !items.is_empty());
    assert!(listed.is_some(), "restore points must not be empty");
    let point = &listed.expect("asserted")[0];
    assert_eq!(point.get("id").and_then(Value::as_str), Some("rp-before"));
    assert_eq!(point.get("label").and_then(Value::as_str), Some("Before"));
    assert_eq!(
        point.get("weeks").and_then(Value::as_i64),
        Some(2),
        "the route names the week count weeks"
    );
    assert_eq!(
        point.get("assignments").and_then(Value::as_i64),
        Some(5),
        "the route names the assignment count assignments"
    );
}

#[test]
fn a_bad_date_week_or_month_is_the_route_sentence() {
    let world = fixture("reject");
    let mut server = boot(&world);
    server.handshake();
    let date = server.call("get_today", json!({"date": "2026-10-32"}), 2);
    assert_eq!(
        tool_error_text(&date),
        Some(DATE_RULE),
        "a bad date must be refused with the date rule, got {date}"
    );
    let week = server.call("get_week", json!({"week_start": "2026-10-20"}), 3);
    assert_eq!(
        tool_error_text(&week),
        Some(WEEK_START_RULE),
        "a Tuesday must be refused with the week rule, got {week}"
    );
    let month = server.call("get_month", json!({"month": "2026-13"}), 4);
    assert_eq!(
        tool_error_text(&month),
        Some(MONTH_RULE),
        "a bad month must be refused with the month rule, got {month}"
    );
    let homework = server.call("list_homework", json!({"week_start": "2026-10-20"}), 5);
    assert_eq!(
        tool_error_text(&homework),
        Some(WEEK_START_RULE),
        "homework must refuse a week that is not a Monday, got {homework}"
    );
}

fn column(path: &str, sql: &str) -> Vec<String> {
    let conn = open_connection(Path::new(path)).expect("open");
    let mut statement = conn.prepare(sql).expect("prepare");
    let rows = statement
        .query_map((), |row| row.get::<_, String>(0))
        .expect("rows");
    rows.map(|row| row.expect("row")).collect()
}

#[test]
fn reads_do_not_change_the_schedule() {
    let world = fixture("readonly");
    let weeks_before = column(
        &world.database_arg,
        "SELECT week_start || blocks || revision FROM weeks ORDER BY week_start",
    );
    let work_before = column(
        &world.database_arg,
        "SELECT id || body || revision FROM assignments ORDER BY id",
    );
    let routines_before = column(
        &world.database_arg,
        "SELECT id || body || revision FROM routines ORDER BY id",
    );
    let points_before = column(
        &world.database_arg,
        "SELECT id || label || weeks_count || assignments_count FROM restore_points ORDER BY id",
    );
    let mut server = boot(&world);
    server.handshake();
    let calls = [
        ("whoami", json!({})),
        ("get_today", json!({})),
        ("get_week", json!({"week_start": "2026-10-19"})),
        ("get_month", json!({"month": "2026-10"})),
        ("list_homework", json!({"week_start": "2026-10-19"})),
        ("list_routines", json!({})),
        ("list_restore_points", json!({})),
    ];
    for (offset, (name, arguments)) in calls.into_iter().enumerate() {
        let response = server.call(name, arguments, 2 + offset as i64);
        assert!(
            tool_ok_text(&response).is_some(),
            "{name} must succeed so the read can be checked, got {response}"
        );
    }
    assert_eq!(
        column(
            &world.database_arg,
            "SELECT week_start || blocks || revision FROM weeks ORDER BY week_start"
        ),
        weeks_before,
        "a read must not change a week"
    );
    assert_eq!(
        column(
            &world.database_arg,
            "SELECT id || body || revision FROM assignments ORDER BY id"
        ),
        work_before,
        "a read must not change homework"
    );
    assert_eq!(
        column(
            &world.database_arg,
            "SELECT id || body || revision FROM routines ORDER BY id"
        ),
        routines_before,
        "a read must not change a routine"
    );
    assert_eq!(
        column(
            &world.database_arg,
            "SELECT id || label || weeks_count || assignments_count FROM restore_points ORDER BY id"
        ),
        points_before,
        "a read must not change a restore point"
    );
}
