//! Read tools return the day, week, month, homework, routines, and restore points.
//! Expected numbers are the same ones the view rules fix: a full day is 96 slots of 15 minutes,
//! this Wednesday holds 7 of them, and a kept session's week revision is the stored one.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
use flexweek_engine::repeats::edit_intent;
use flexweek_store::{
    RoutineWrite, apply_repeat_intents, create_restore_point, initialize, insert_assignment,
    insert_preferences, insert_user, open_connection, open_session, save_routine,
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
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 60,
        "days": [0], "start": "09:00", "category": "school"
    });
    let intent = edit_intent("school", "2026-09-28", None, Some(&school)).expect("new");
    apply_repeat_intents(&conn, user, &[intent]).expect("standing");
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

#[test]
fn the_helper_follows_the_first_day_of_the_week_it_is_told() {
    let world = fixture("week-start");
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
        "--week-starts-on",
        "wednesday",
    ]);
    server.handshake();
    let me = body_of(&server.call("whoami", json!({}), 2));
    assert_eq!(me["week_starts_on"], "wednesday");
    // Wednesday 21 to Tuesday 27 October: Monday 19's week gives its Wednesday to Sunday (days 0
    // to 4) and Monday 26's its Monday and Tuesday (days 5 and 6).
    let week = body_of(&server.call("get_week", json!({"week_start": "2026-10-21"}), 3));
    assert_eq!(week["week_start"], "2026-10-21");
    assert_eq!(week["week_starts_on"], "wednesday");
    assert_eq!(week["revision"], json!([4, 0]));
    let blocks = list(&week, "blocks").expect("blocks");
    let days_of = |id: &str| {
        by_id(blocks, id)
            .and_then(|block| block.get("days"))
            .cloned()
    };
    assert_eq!(days_of("s1"), Some(json!([0])));
    // Standing School on Mondays falls on Monday 26, day 5.
    assert_eq!(days_of("school"), Some(json!([5])));
    // Old clients passing a Monday stored week are still accepted when weeks start on Wednesday.
    let monday_compat = body_of(&server.call("get_week", json!({"week_start": "2026-10-19"}), 4));
    assert_eq!(monday_compat["week_start"], "2026-10-19");
    assert_eq!(monday_compat["week_starts_on"], "monday");
    assert_eq!(monday_compat["revision"], json!(4));
    let refused = server.call("get_week", json!({"week_start": "2026-10-20"}), 5);
    assert!(tool_error_text(&refused).is_some(), "{refused}");
    // October's rows start on Wednesday 30 September.
    let month = body_of(&server.call("get_month", json!({"month": "2026-10"}), 6));
    assert_eq!(month["week_starts_on"], "wednesday");
    let first = list(&month, "days").and_then(|days| days.first()).cloned();
    assert_eq!(
        first.and_then(|day| day.get("date").cloned()),
        Some(json!("2026-09-30"))
    );
    drop(server);
    // Without the flag it reads the day the desktop keeps in the data folder.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("week start file");
    let mut server = boot(&world);
    server.handshake();
    let me = body_of(&server.call("whoami", json!({}), 2));
    assert_eq!(me["week_starts_on"], "sunday");
}

#[test]
fn the_helpers_week_from_another_day_lets_waiting_homework_run_to_its_due_date() {
    // "Later" is due Friday 30 October. Its session waits for a time on every day of Monday 19's
    // week. The week from Wednesday 21 to Tuesday 27 October shows it on all seven days, as the
    // desktop's week does: Monday 26 and Tuesday 27 are before the due date too.
    let world = fixture("week-start-due");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let blocks = json!([{
        "id": "w1", "title": "Later", "kind": "flexible", "duration_min": 30,
        "days": [0, 1, 2, 3, 4, 5, 6], "assignment_id": "later"
    }])
    .to_string();
    conn.execute(
        "UPDATE weeks SET blocks = ?1 WHERE week_start = '2026-10-19'",
        [blocks],
    )
    .expect("waiting session");
    drop(conn);
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
        "--week-starts-on",
        "wednesday",
    ]);
    server.handshake();
    let week = body_of(&server.call("get_week", json!({"week_start": "2026-10-21"}), 2));
    assert_eq!(week["week_starts_on"], "wednesday");
    let blocks = list(&week, "blocks").expect("blocks");
    assert_eq!(
        by_id(blocks, "w1")
            .and_then(|block| block.get("days"))
            .cloned(),
        Some(json!([0, 1, 2, 3, 4, 5, 6])),
        "{week}"
    );
}

#[test]
fn week_start_changes_in_week_start_json_reach_the_running_helper_and_flag_stays_override() {
    let world = fixture("week-start-live");
    let mut server = boot(&world);
    server.handshake();
    assert_eq!(
        body_of(&server.call("whoami", json!({}), 2))["week_starts_on"],
        "monday"
    );
    assert_eq!(
        body_of(&server.call("get_today", json!({}), 3))["week_starts_on"],
        "monday"
    );
    // Changing week-start.json while the helper runs is picked up on the next call.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wednesday file");
    assert_eq!(
        body_of(&server.call("whoami", json!({}), 4))["week_starts_on"],
        "wednesday"
    );
    let wed = body_of(&server.call("get_week", json!({"week_start": "2026-10-21"}), 5));
    assert_eq!(wed["week_starts_on"], "wednesday");
    assert_eq!(wed["revision"], json!([4, 0]));
    // get_today keeps stored Monday week_start, reports active week_starts_on, and adds shown_week_start.
    let today = body_of(&server.call("get_today", json!({}), 6));
    assert_eq!(today["week_start"], "2026-10-19");
    assert_eq!(today["week_starts_on"], "wednesday");
    assert_eq!(today["shown_week_start"], "2026-10-21");
    // Switching again to Sunday without restarting is picked up immediately.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sunday file");
    assert_eq!(
        body_of(&server.call("whoami", json!({}), 7))["week_starts_on"],
        "sunday"
    );
    let sun = body_of(&server.call("get_week", json!({"week_start": "2026-10-18"}), 8));
    assert_eq!(sun["week_starts_on"], "sunday");
    assert_eq!(sun["revision"], json!([1, 4]));
    // Invalid content falls back to Monday.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "funday"}"#,
    )
    .expect("invalid file");
    assert_eq!(
        body_of(&server.call("whoami", json!({}), 9))["week_starts_on"],
        "monday"
    );
    drop(server);

    // --week-starts-on overrides week-start.json even if the file changes while running.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sunday override test");
    let mut fixed_server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
        "--week-starts-on",
        "wednesday",
    ]);
    fixed_server.handshake();
    assert_eq!(
        body_of(&fixed_server.call("whoami", json!({}), 2))["week_starts_on"],
        "wednesday"
    );
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "friday"}"#,
    )
    .expect("friday file");
    assert_eq!(
        body_of(&fixed_server.call("whoami", json!({}), 3))["week_starts_on"],
        "wednesday"
    );
}

#[test]
fn list_homework_follows_monday_sunday_wednesday_and_month_end_crossing_weeks() {
    let world = fixture("homework-shown-weeks");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    // Replace current week 2026-10-19 with two sessions for essay: Mon 19 (30m) and Wed 21 (45m),
    // plus a session in 2026-11-02 (Mon 2 Nov, 60m) for month-end crossing 2026-10-28 (Wed)..Nov 3.
    let w1 = json!([
        {
            "id": "s-mon", "title": "Draft", "kind": "flexible", "duration_min": 30,
            "days": [0], "start": "15:00", "assignment_id": "essay"
        },
        {
            "id": "s-wed", "title": "Draft", "kind": "flexible", "duration_min": 45,
            "days": [2], "start": "16:00", "assignment_id": "essay"
        }
    ])
    .to_string();
    let w_nov = json!([
        {
            "id": "s-nov", "title": "Later", "kind": "flexible", "duration_min": 60,
            "days": [0], "start": "17:00", "assignment_id": "later"
        }
    ])
    .to_string();
    let w_dec = json!([
        {
            "id": "s-dec", "title": "Later", "kind": "flexible", "duration_min": 30,
            "days": [1], "start": "17:00", "assignment_id": "later"
        }
    ])
    .to_string();
    conn.execute(
        "UPDATE weeks SET blocks = ?1 WHERE user_id = 1 AND week_start = '2026-10-19'",
        [w1],
    )
    .expect("update w1");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (1, '2026-11-02', ?1, 1)",
        [w_nov],
    )
    .expect("insert w_nov");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (1, '2026-11-30', ?1, 1)",
        [w_dec],
    )
    .expect("insert w_dec");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    server.handshake();
    // Monday start: counts Mon 19 + Wed 21 = 75 min.
    let mon = body_of(&server.call("list_homework", json!({"week_start": "2026-10-19"}), 2));
    assert_eq!(mon["week_starts_on"], "monday");
    assert_eq!(
        by_id(list(&mon, "assignments").expect("list"), "essay")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(75)
    );

    // Switch live to Wednesday: from Wed 21 Oct omits Mon 19 (30m) and keeps Wed 21 (45m).
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let wed = body_of(&server.call("list_homework", json!({"week_start": "2026-10-21"}), 3));
    assert_eq!(wed["week_start"], "2026-10-21");
    assert_eq!(wed["week_starts_on"], "wednesday");
    assert_eq!(
        by_id(list(&wed, "assignments").expect("list"), "essay")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(45)
    );
    // Month-end crossing Wednesday 2026-10-28..2026-11-03 sees Nov 2 (60m) + Nov 3/Dec (30m) = 90m.
    let cross_wed = body_of(&server.call("list_homework", json!({"week_start": "2026-10-28"}), 4));
    assert_eq!(cross_wed["week_starts_on"], "wednesday");
    assert_eq!(
        by_id(list(&cross_wed, "assignments").expect("list"), "later")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(90)
    );
    // Old client passing Monday 2026-10-19 still works as Monday.
    let compat = body_of(&server.call("list_homework", json!({"week_start": "2026-10-19"}), 5));
    assert_eq!(compat["week_starts_on"], "monday");
    assert_eq!(
        by_id(list(&compat, "assignments").expect("list"), "essay")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(75)
    );

    // Switch live to Sunday: Sun 18 Oct includes Mon 19 + Wed 21 = 75m; month-end crossing
    // Sun 2026-11-29..Sat Dec 5 includes Tue Dec 1 (30m).
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");
    let sun = body_of(&server.call("list_homework", json!({"week_start": "2026-10-18"}), 6));
    assert_eq!(sun["week_starts_on"], "sunday");
    assert_eq!(
        by_id(list(&sun, "assignments").expect("list"), "essay")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(75)
    );
    let cross_sun = body_of(&server.call("list_homework", json!({"week_start": "2026-11-29"}), 7));
    assert_eq!(cross_sun["week_starts_on"], "sunday");
    assert_eq!(
        by_id(list(&cross_sun, "assignments").expect("list"), "later")
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(30)
    );
}

#[test]
fn monday_list_homework_omits_week_start_and_keeps_only_week_starts_on() {
    let world = fixture("homework-monday-parity");
    let mut server = boot(&world);
    server.handshake();

    let mon = body_of(&server.call("list_homework", json!({"week_start": "2026-10-19"}), 2));
    assert_eq!(
        mon.get("week_start"),
        None,
        "Monday list_homework must not add week_start: {mon}"
    );
    assert_eq!(mon.get("week_starts_on"), Some(&json!("monday")));

    // Switch live to Wednesday: Monday compat call still omits week_start; Wednesday call includes it.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let compat = body_of(&server.call("list_homework", json!({"week_start": "2026-10-19"}), 3));
    assert_eq!(
        compat.get("week_start"),
        None,
        "Monday compat must not add week_start: {compat}"
    );
    assert_eq!(compat.get("week_starts_on"), Some(&json!("monday")));

    let wed = body_of(&server.call("list_homework", json!({"week_start": "2026-10-21"}), 4));
    assert_eq!(wed.get("week_start"), Some(&json!("2026-10-21")));
    assert_eq!(wed.get("week_starts_on"), Some(&json!("wednesday")));
}

#[test]
fn get_today_reports_active_week_starts_on_and_shown_week_start_when_not_monday() {
    let world = fixture("today-shown-week-start");
    let mut server = boot(&world);
    server.handshake();

    // 1. Monday start: stays as before (no shown_week_start).
    let mon = body_of(&server.call("get_today", json!({}), 2));
    assert_eq!(mon["week_start"], json!("2026-10-19"));
    assert_eq!(mon["week_starts_on"], json!("monday"));
    assert_eq!(
        mon.get("shown_week_start"),
        None,
        "Monday must not add shown_week_start: {mon}"
    );

    // 2. Live Wednesday setting: stored week_start unchanged, week_starts_on active, shown_week_start added.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let wed = body_of(&server.call("get_today", json!({}), 3));
    assert_eq!(wed["week_start"], json!("2026-10-19"));
    assert_eq!(wed["week_starts_on"], json!("wednesday"));
    assert_eq!(wed["shown_week_start"], json!("2026-10-21"));

    // Month-end crossing: Sunday Nov 1 belongs to Monday 2026-10-26 and Wednesday 2026-10-28.
    let cross = body_of(&server.call("get_today", json!({"date": "2026-11-01"}), 4));
    assert_eq!(cross["week_start"], json!("2026-10-26"));
    assert_eq!(cross["week_starts_on"], json!("wednesday"));
    assert_eq!(cross["shown_week_start"], json!("2026-10-28"));

    // 3. Live Sunday setting: Wednesday Oct 21 belongs to Sunday 2026-10-18.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");
    let sun = body_of(&server.call("get_today", json!({}), 5));
    assert_eq!(sun["week_start"], json!("2026-10-19"));
    assert_eq!(sun["week_starts_on"], json!("sunday"));
    assert_eq!(sun["shown_week_start"], json!("2026-10-18"));
    drop(server);

    // 4. --week-starts-on overrides week-start.json.
    let mut override_server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
        "--week-starts-on",
        "wednesday",
    ]);
    override_server.handshake();
    let forced = body_of(&override_server.call("get_today", json!({}), 2));
    assert_eq!(forced["week_start"], json!("2026-10-19"));
    assert_eq!(forced["week_starts_on"], json!("wednesday"));
    assert_eq!(forced["shown_week_start"], json!("2026-10-21"));
}
