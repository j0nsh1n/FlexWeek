//! Read views, with expected values taken from the day, month and homework rules.
//! A loop over a list asserts the list is not empty first.

mod common;

use common::scratch;
use flexweek_store::{
    day_view, homework_list, initialize, insert_assignment, insert_user, month_view,
    open_connection, restore_point_list, routine_list, set_standing, week_view,
};
use rusqlite::params;
use serde_json::{Value, json};

const DATE_RULE: &str = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31";
const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";
const MONTH_RULE: &str = "month must be YYYY-MM between 2000-01 and 2099-12";

fn account(name: &str) -> (rusqlite::Connection, i64) {
    let path = scratch(name);
    initialize(&path, "2026-10-19").expect("schema");
    let conn = open_connection(&path).expect("open");
    let user = insert_user(&conn, "ada", "hash").expect("user");
    (conn, user)
}

fn text(value: &Value) -> String {
    serde_json::to_string(value).expect("json")
}

fn assignment(id: &str, title: &str, due: &str, estimate: i64, completed: bool) -> Value {
    json!({
        "id": id,
        "title": title,
        "due": due,
        "estimate_min": estimate,
        "focus_minutes": 0,
        "completed": completed,
    })
}

/// Essay is due Wednesday 2026-10-21 at 21:00. A 30-minute session sits in the
/// previous week and a 45-minute one in the week of 2026-10-19, stored under the
/// title "Draft" so a rewrite has something to change. School stands on Mondays
/// from 2026-09-28. A different locked block sits on that Wednesday.
fn fixture(name: &str) -> (rusqlite::Connection, i64) {
    let (conn, user) = account(name);
    for (id, title, due, estimate, completed) in [
        ("essay", "Essay", "2026-10-21T21:00", 90, false),
        ("quiz", "Quiz", "2026-10-20", 30, false),
        ("later", "Later", "2026-10-30", 30, false),
        ("old", "Old", "2026-09-15", 30, false),
        ("done", "Done", "2026-10-22", 30, true),
    ] {
        insert_assignment(
            &conn,
            user,
            id,
            &text(&assignment(id, title, due, estimate, completed)),
        )
        .expect("assignment");
    }
    let earlier = json!([{
        "id": "s0", "title": "Draft", "kind": "flexible", "duration_min": 30,
        "days": [2], "start": "16:00", "assignment_id": "essay"
    }]);
    let current = json!([
        {
            "id": "s1", "title": "Draft", "kind": "flexible", "duration_min": 45,
            "days": [2], "start": "16:00", "assignment_id": "essay"
        },
        {
            "id": "class-wed", "title": "School", "kind": "locked", "duration_min": 60,
            "days": [2], "start": "09:00", "category": "school"
        }
    ]);
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)",
        params![user, "2026-10-12", text(&earlier)],
    )
    .expect("earlier week");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 4)",
        params![user, "2026-10-19", text(&current)],
    )
    .expect("current week");
    let standing = json!([{
        "id": "school", "title": "School", "kind": "locked", "duration_min": 60,
        "days": [0], "start": "09:00", "category": "school"
    }]);
    set_standing(&conn, user, "2026-09-28", &text(&standing)).expect("standing");
    (conn, user)
}

fn list<'a>(value: &'a Value, key: &str) -> Option<&'a Vec<Value>> {
    value.get(key).and_then(Value::as_array)
}

fn by_id<'a>(items: &'a [Value], id: &str) -> Option<&'a Value> {
    items
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(id))
}

fn by_date<'a>(days: &'a [Value], date: &str) -> Option<&'a Value> {
    days.iter()
        .find(|day| day.get("date").and_then(Value::as_str) == Some(date))
}

#[test]
fn a_bad_date_week_or_month_is_refused_with_the_route_sentence() {
    let (conn, user) = account("reject");
    let date = day_view(&conn, user, "2026-10-32");
    assert!(
        date.is_err(),
        "a bad date must be refused with the date rule"
    );
    assert_eq!(
        date.expect_err("asserted").to_string(),
        DATE_RULE,
        "a bad date must be refused with the date rule"
    );
    let week = week_view(&conn, user, "2026-10-20");
    assert!(
        week.is_err(),
        "a Tuesday must be refused with the week rule"
    );
    assert_eq!(
        week.expect_err("asserted").to_string(),
        WEEK_START_RULE,
        "a Tuesday must be refused with the week rule"
    );
    let month = month_view(&conn, user, "2026-13");
    assert!(
        month.is_err(),
        "a bad month must be refused with the month rule"
    );
    assert_eq!(
        month.expect_err("asserted").to_string(),
        MONTH_RULE,
        "a bad month must be refused with the month rule"
    );
    let homework = homework_list(&conn, user, "2026-10-20", false);
    assert!(
        homework.is_err(),
        "homework must refuse a week that is not a Monday"
    );
    assert_eq!(
        homework.expect_err("asserted").to_string(),
        WEEK_START_RULE,
        "homework must refuse a week that is not a Monday"
    );
}

#[test]
fn day_rewrites_the_session_and_counts_the_open_afternoon() {
    let (conn, user) = fixture("day");
    let day = day_view(&conn, user, "2026-10-21").expect("day");
    assert_eq!(day.get("date").and_then(Value::as_str), Some("2026-10-21"));
    assert_eq!(
        day.get("week_start").and_then(Value::as_str),
        Some("2026-10-19")
    );
    let sessions = list(&day, "sessions").filter(|items| !items.is_empty());
    assert!(sessions.is_some(), "the day must list its work session");
    let sessions = sessions.expect("asserted");
    assert_eq!(sessions[0].get("id").and_then(Value::as_str), Some("s1"));
    assert_eq!(
        sessions[0].get("title").and_then(Value::as_str),
        Some("Essay"),
        "the stored title Draft must be rewritten from the assignment"
    );
    let locked = list(&day, "locked").filter(|items| !items.is_empty());
    assert!(locked.is_some(), "the day must list its locked block");
    assert_eq!(
        locked.expect("asserted")[0]
            .get("id")
            .and_then(Value::as_str),
        Some("class-wed")
    );
    assert_eq!(
        day.get("next_action"),
        Some(&json!({"kind": "start", "block_id": "s1"})),
        "the earliest open session is the next action"
    );
    let workload = day.get("workload");
    assert_eq!(
        workload
            .and_then(|item| item.get("scheduled_min"))
            .and_then(Value::as_i64),
        Some(105),
        "45 minutes of essay plus 60 minutes of school"
    );
    assert_eq!(
        workload
            .and_then(|item| item.get("focus_min"))
            .and_then(Value::as_i64),
        Some(0)
    );
    // 09:00–10:00 is 4 slots and 16:00 for 45 minutes is 3. (96 - 7) * 15.
    assert_eq!(
        workload
            .and_then(|item| item.get("available_min"))
            .and_then(Value::as_i64),
        Some(1335),
        "a full day minus the two placed blocks"
    );
    let categories = workload
        .and_then(|item| list(item, "by_category"))
        .filter(|items| !items.is_empty());
    assert!(categories.is_some(), "workload must group by category");
    let categories = categories.expect("asserted");
    assert_eq!(
        categories[0].get("category").and_then(Value::as_str),
        Some("school")
    );
    assert_eq!(
        categories[0].get("scheduled_min").and_then(Value::as_i64),
        Some(60)
    );
    assert_eq!(categories[1].get("category"), Some(&Value::Null));
    assert_eq!(
        categories[1].get("scheduled_min").and_then(Value::as_i64),
        Some(45)
    );
    let due = list(&day, "due_soon").filter(|items| !items.is_empty());
    assert!(due.is_some(), "due soon must not be empty");
    let due = due.expect("asserted");
    let ids: Vec<&str> = due
        .iter()
        .filter_map(|item| item.get("id").and_then(Value::as_str))
        .collect();
    assert_eq!(
        ids,
        vec!["old", "quiz", "essay"],
        "due soon is everything open through tomorrow: the overdue row, the quiz, then the essay"
    );
    let quiz = by_id(due, "quiz");
    assert_eq!(
        quiz.and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(0)
    );
    assert_eq!(
        quiz.and_then(|item| item.get("unplanned_min"))
            .and_then(Value::as_i64),
        Some(30)
    );
    let essay = by_id(due, "essay");
    assert_eq!(
        essay
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(45),
        "only this week's 45 minutes count; the earlier week is before this Monday"
    );
    assert_eq!(
        essay
            .and_then(|item| item.get("unplanned_min"))
            .and_then(Value::as_i64),
        Some(45)
    );
}

#[test]
fn month_fills_empty_weeks_from_standing_and_keeps_the_stored_title() {
    let (conn, user) = fixture("month");
    let month = month_view(&conn, user, "2026-10").expect("month");
    assert_eq!(
        month.get("start").and_then(Value::as_str),
        Some("2026-10-01")
    );
    assert_eq!(month.get("end").and_then(Value::as_str), Some("2026-10-31"));
    assert_eq!(
        month.get("grid_start").and_then(Value::as_str),
        Some("2026-09-28")
    );
    assert_eq!(
        month.get("grid_end").and_then(Value::as_str),
        Some("2026-11-01")
    );
    let days = list(&month, "days").filter(|items| !items.is_empty());
    assert!(days.is_some(), "the month grid must not be empty");
    let days = days.expect("asserted");
    assert_eq!(
        days.len(),
        35,
        "28 September through 1 November is five weeks"
    );
    let before = by_date(days, "2026-09-28");
    assert_eq!(
        before
            .and_then(|day| day.get("in_month"))
            .and_then(Value::as_bool),
        Some(false)
    );
    assert_eq!(
        before
            .and_then(|day| day.get("locked_count"))
            .and_then(Value::as_i64),
        Some(1),
        "an unsaved Monday still shows the standing school block"
    );
    let fifth = by_date(days, "2026-10-05");
    assert_eq!(
        fifth
            .and_then(|day| day.get("locked_count"))
            .and_then(Value::as_i64),
        Some(1),
        "the next unsaved Monday is filled from standing too"
    );
    let wednesday = by_date(days, "2026-10-21");
    assert_eq!(
        wednesday
            .and_then(|day| day.get("in_month"))
            .and_then(Value::as_bool),
        Some(true)
    );
    assert_eq!(
        wednesday
            .and_then(|day| day.get("session_count"))
            .and_then(Value::as_i64),
        Some(1)
    );
    let chips = wednesday
        .and_then(|day| list(day, "blocks"))
        .filter(|items| !items.is_empty());
    assert!(chips.is_some(), "the Wednesday must have chips");
    let session = chips.and_then(|items| by_id(items, "s1"));
    assert_eq!(
        session
            .and_then(|chip| chip.get("title"))
            .and_then(Value::as_str),
        Some("Draft"),
        "a month chip keeps the stored title; the day view is what rewrites it"
    );
    let overdue = list(&month, "overdue").filter(|items| !items.is_empty());
    assert!(
        overdue.is_some(),
        "work due before the grid must be overdue"
    );
    assert!(
        overdue
            .expect("asserted")
            .iter()
            .any(|item| item.get("id").and_then(Value::as_str) == Some("old")),
        "the 15 September assignment is overdue, not on a grid day"
    );
    let empty = Vec::new();
    let deadlines = list(&month, "deadlines").unwrap_or(&empty);
    let essay = by_id(deadlines, "essay");
    // From the Monday of 1 October (28 September): 30 minutes on the 12th and 45 on the 19th.
    assert_eq!(
        essay
            .and_then(|item| item.get("unplanned_min"))
            .and_then(Value::as_i64),
        Some(15),
        "90 estimated minus 75 planned from the month's Monday"
    );
}

#[test]
fn homework_sorts_by_due_and_names_every_session_week() {
    let (conn, user) = fixture("homework");
    let open = homework_list(&conn, user, "2026-10-19", false).expect("open");
    let items = list(&open, "assignments").filter(|items| !items.is_empty());
    assert!(items.is_some(), "the homework list must not be empty");
    let items = items.expect("asserted");
    let ids: Vec<&str> = items
        .iter()
        .filter_map(|item| item.get("id").and_then(Value::as_str))
        .collect();
    assert_eq!(
        ids,
        vec!["old", "quiz", "essay", "later"],
        "date order, and a completed row stays out"
    );
    let essay = by_id(items, "essay");
    assert_eq!(
        essay
            .and_then(|item| item.get("planned_min"))
            .and_then(Value::as_i64),
        Some(45)
    );
    assert_eq!(
        essay
            .and_then(|item| item.get("unplanned_min"))
            .and_then(Value::as_i64),
        Some(45)
    );
    assert_eq!(
        essay
            .and_then(|item| item.get("revision"))
            .and_then(Value::as_i64),
        Some(1)
    );
    assert_eq!(
        essay.and_then(|item| item.get("session_weeks")),
        Some(&json!(["2026-10-12", "2026-10-19"])),
        "session weeks are every week that holds the assignment, oldest first"
    );
    let with_done = homework_list(&conn, user, "2026-10-19", true).expect("done");
    let done_items = list(&with_done, "assignments").filter(|items| !items.is_empty());
    assert!(
        done_items.is_some(),
        "include_completed must still return a list"
    );
    let done_ids: Vec<&str> = done_items
        .expect("asserted")
        .iter()
        .filter_map(|item| item.get("id").and_then(Value::as_str))
        .collect();
    assert_eq!(
        done_ids,
        vec!["old", "quiz", "essay", "done", "later"],
        "the completed row sorts on its due date among the others"
    );
}

#[test]
fn week_view_uses_the_saved_revision_and_an_unsaved_week_is_zero() {
    let (conn, user) = fixture("week");
    let saved = week_view(&conn, user, "2026-10-19").expect("saved");
    assert_eq!(saved.get("revision").and_then(Value::as_i64), Some(4));
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
        "standing school is part of the week the student sees"
    );
    let empty = week_view(&conn, user, "2026-10-26").expect("empty");
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
        "the unsaved week shows the standing school block"
    );
}

#[test]
fn routines_and_restore_points_use_the_route_names() {
    let (conn, user) = account("lists");
    conn.execute(
        "INSERT INTO routines(user_id, id, name, body, revision, created_at, updated_at)
         VALUES (?1, 'morning', 'Morning', ?2, 2, '2026-10-01T00:00:00', '2026-10-02T00:00:00')",
        params![user, r#"[{"id":"stretch","title":"Stretch"}]"#],
    )
    .expect("routine");
    conn.execute(
        "INSERT INTO restore_points(user_id, id, label, created_at, weeks_count, assignments_count, body)
         VALUES (?1, 'p1', 'Before', '2026-10-01T00:00:00', 2, 3, '{}')",
        params![user],
    )
    .expect("point");
    let routines = routine_list(&conn, user).expect("routines");
    let rows = list(&routines, "routines").filter(|items| !items.is_empty());
    assert!(rows.is_some(), "routines must not be empty");
    let row = &rows.expect("asserted")[0];
    assert_eq!(row.get("name").and_then(Value::as_str), Some("Morning"));
    assert_eq!(row.get("revision").and_then(Value::as_i64), Some(2));
    let blocks = list(row, "blocks").filter(|items| !items.is_empty());
    assert!(
        blocks.is_some(),
        "a routine body is the block list, not a string"
    );
    assert_eq!(
        blocks.expect("asserted")[0]
            .get("title")
            .and_then(Value::as_str),
        Some("Stretch")
    );
    let points = restore_point_list(&conn, user).expect("points");
    let listed = list(&points, "restore_points").filter(|items| !items.is_empty());
    assert!(listed.is_some(), "restore points must not be empty");
    let point = &listed.expect("asserted")[0];
    assert_eq!(point.get("label").and_then(Value::as_str), Some("Before"));
    assert_eq!(point.get("weeks").and_then(Value::as_i64), Some(2));
    assert_eq!(point.get("assignments").and_then(Value::as_i64), Some(3));
    assert!(
        point.get("weeks_count").is_none(),
        "the route renames weeks_count to weeks"
    );
}
