//! The month, as GET /api/month describes it: the weeks of a month with each date's blocks, deadlines and
//! counts. Grid lengths come from the calendar, not a recorded run; "now" is the tests' fixed moment,
//! Thursday 5 November 2026 at 19:00, unless a test says otherwise. The Rust twins of
//! backend/tests/test_month_endpoint.py (its signed-out, no-month and negative first-day checks stay
//! with the route, in test_session_cookie_and_request_checks.py).

use flexweek_engine::plan::{Moment, parse_moment};
use flexweek_service::blocks::check_block;
use flexweek_service::views;
use flexweek_service::{Refusal, ServiceError, with_db};
use flexweek_testkit::{TestDb, merged};
use serde_json::{Value, json};

const MONTH: &str = "2026-09";
const WEEK: &str = "2026-09-14";
const MONTH_RULE: &str = "month must be YYYY-MM between 2000-01 and 2099-12";

fn now() -> Moment {
    parse_moment("2026-11-05T19:00").unwrap()
}

type Db = TestDb;

fn fresh(name: &str) -> Db {
    TestDb::new(name)
}

fn account(db: &Db, name: &str) -> i64 {
    db.account(name)
}

fn homework(id: &str, changes: Value) -> Value {
    merged(
        json!({
            "id": id, "title": "Essay", "course": null, "category": "Homework", "priority": 3,
            "energy": "medium", "spotify_url": null, "due": "2026-09-16T23:59", "estimate_min": 120,
            "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
        }),
        changes,
    )
}

fn school() -> Value {
    json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 390,
        "days": [0, 1, 2, 3, 4], "priority": 1, "energy": "medium", "start": "08:00",
        "category": "School",
    })
}

/// A homework session on `day` at `start` (no start when `start` is empty).
fn session(id: &str, day: i64, start: &str, changes: Value) -> Value {
    let mut block = merged(
        json!({
            "id": id, "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [day],
            "priority": 3, "energy": "medium", "start": start, "assignment_id": "hw-essay",
            "category": "Homework",
        }),
        changes,
    );
    if start.is_empty() {
        block.as_object_mut().unwrap().shift_remove("start");
    }
    block
}

fn club(id: &str, title: &str, days: Value, start: &str, minutes: i64) -> Value {
    json!({
        "id": id, "title": title, "kind": "locked", "duration_min": minutes, "days": days,
        "start": start, "category": "extra",
    })
}

fn save_homework(db: &Db, user: i64, body: Value) {
    let id = body["id"].as_str().unwrap().to_string();
    with_db(&db.path, |conn| {
        flexweek_store::save_assignment(conn, user, &id, &body.to_string(), 0, 1000)?;
        Ok(())
    })
    .unwrap();
}

/// Saved as the week save writes blocks: each one written out in full.
fn save_week_from(db: &Db, user: i64, week: &str, blocks: &[Value]) {
    let written: Vec<Value> = blocks.iter().map(|b| check_block(b).unwrap()).collect();
    with_db(&db.path, |conn| {
        flexweek_store::save_week(conn, user, week, &Value::Array(written).to_string(), 0)?;
        Ok(())
    })
    .unwrap();
}

fn save_week(db: &Db, user: i64, blocks: &[Value]) {
    save_week_from(db, user, WEEK, blocks);
}

fn month_at(db: &Db, user: i64, month: &str, first_day: u32, at: Moment) -> Value {
    views::month(&db.path, user, month, first_day, at).unwrap()
}

fn month(db: &Db, user: i64, label: &str) -> Value {
    month_at(db, user, label, 0, now())
}

fn on<'a>(body: &'a Value, date: &str) -> &'a Value {
    body["days"]
        .as_array()
        .unwrap()
        .iter()
        .find(|day| day["date"] == date)
        .unwrap_or_else(|| panic!("{date} is not in the grid"))
}

fn ids(list: &Value) -> Vec<&str> {
    list.as_array()
        .unwrap()
        .iter()
        .map(|item| item["id"].as_str().unwrap())
        .collect()
}

fn counts(cell: &Value) -> (i64, i64, i64) {
    (
        cell["session_count"].as_i64().unwrap(),
        cell["scheduled_min"].as_i64().unwrap(),
        cell["focus_min"].as_i64().unwrap(),
    )
}

/// What a deadline line holds for the plain essay, revision 1 after its first save.
fn deadline(due: &str, date: &str) -> Value {
    json!({
        "id": "hw-essay", "title": "Essay", "due": due, "date": date, "completed": false,
        "estimate_min": 120, "unplanned_min": 120, "revision": 1,
    })
}

#[test]
fn an_empty_september_is_a_five_week_grid() {
    let db = fresh("empty");
    let ana = account(&db, "ana");
    let body = month(&db, ana, MONTH);
    assert_eq!(
        (
            &body["month"],
            &body["start"],
            &body["end"],
            &body["grid_start"],
            &body["grid_end"]
        ),
        (
            &json!(MONTH),
            &json!("2026-09-01"),
            &json!("2026-09-30"),
            &json!("2026-08-31"),
            &json!("2026-10-04")
        )
    );
    assert_eq!(body["days"].as_array().unwrap().len(), 35);
    assert_eq!(
        body["days"][0],
        json!({
            "date": "2026-08-31", "week_start": "2026-08-31", "in_month": false, "due_ids": [],
            "session_count": 0, "locked_count": 0, "scheduled_min": 0, "focus_min": 0, "blocks": [],
        })
    );
    assert_eq!(
        body["unscheduled"],
        json!({ "session_count": 0, "minutes": 0 })
    );
    let first = on(&body, "2026-09-01");
    assert_eq!(
        (&first["in_month"], &first["week_start"]),
        (&json!(true), &json!("2026-08-31"))
    );
    assert_eq!(body["days"][34]["date"], "2026-10-04");
    for list in ["deadlines", "projects", "overdue"] {
        assert_eq!(body[list], json!([]), "{list}");
    }
}

#[test]
fn a_school_week_fills_only_that_monday_to_friday() {
    let db = fresh("school");
    let ana = account(&db, "ana");
    save_week(&db, ana, &[school()]);
    let body = month(&db, ana, MONTH);
    for date in [
        "2026-09-14",
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
    ] {
        let cell = on(&body, date);
        assert_eq!(
            (
                &cell["locked_count"],
                &cell["session_count"],
                &cell["scheduled_min"]
            ),
            (&json!(1), &json!(0), &json!(390)),
            "{date}"
        );
    }
    let saturday = on(&body, "2026-09-19");
    assert_eq!(
        (&saturday["locked_count"], &saturday["scheduled_min"]),
        (&json!(0), &json!(0))
    );
    assert_eq!(on(&body, "2026-09-07")["scheduled_min"], 0);
}

#[test]
fn open_homework_due_in_the_month_is_a_deadline_not_a_project() {
    let db = fresh("deadline");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    let body = month(&db, ana, MONTH);
    assert_eq!(
        body["deadlines"],
        json!([deadline("2026-09-16T23:59", "2026-09-16")])
    );
    assert_eq!(on(&body, "2026-09-16")["due_ids"], json!(["hw-essay"]));
    assert_eq!(body["projects"], json!([]));
    assert_eq!(body["overdue"], json!([]));
}

#[test]
fn notes_make_the_same_homework_a_project() {
    let db = fresh("notes");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("hw-essay", json!({ "notes": "Outline first." })),
    );
    let mut project = deadline("2026-09-16T23:59", "2026-09-16");
    project.as_object_mut().unwrap().extend(
        json!({
            "session_dates": [], "has_notes": true, "has_links": false, "checklist_total": 0,
            "checklist_done": 0,
        })
        .as_object()
        .unwrap()
        .clone(),
    );
    assert_eq!(month(&db, ana, MONTH)["projects"], json!([project]));
}

#[test]
fn two_placed_session_dates_make_a_project_without_notes() {
    let db = fresh("two-dates");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(
        &db,
        ana,
        &[
            session("s-tue", 1, "16:00", json!({})),
            session("s-wed", 2, "16:00", json!({})),
        ],
    );
    // Before both sessions, so each still holds its hour.
    let body = month_at(
        &db,
        ana,
        MONTH,
        0,
        parse_moment("2026-09-14T08:00").unwrap(),
    );
    let project = &body["projects"][0];
    assert_eq!(project["id"], "hw-essay");
    assert_eq!(
        project["session_dates"],
        json!(["2026-09-15", "2026-09-16"])
    );
    assert_eq!(
        (&project["has_notes"], &project["unplanned_min"]),
        (&json!(false), &json!(0))
    );
    assert_eq!(counts(on(&body, "2026-09-15")), (1, 60, 0));
    assert_eq!(on(&body, "2026-09-16")["session_count"], 1);
}

#[test]
fn a_finished_session_counts_only_on_its_finished_day() {
    let db = fresh("finished");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    let done = session(
        "s-done",
        1,
        "16:00",
        json!({ "days": [1, 2, 3], "completed": true, "completed_day": 2 }),
    );
    save_week(&db, ana, &[done]);
    let body = month(&db, ana, MONTH);
    assert_eq!(on(&body, "2026-09-15")["session_count"], 0);
    assert_eq!(counts(on(&body, "2026-09-16")), (1, 60, 60));
    assert_eq!(on(&body, "2026-09-17")["session_count"], 0);
    assert_eq!(body["projects"], json!([]));
    assert_eq!(
        body["unscheduled"],
        json!({ "session_count": 0, "minutes": 0 })
    );
}

#[test]
fn open_work_with_several_possible_days_is_unscheduled() {
    let db = fresh("several");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(
        &db,
        ana,
        &[session("s-tue", 1, "", json!({ "days": [1, 2, 3] }))],
    );
    let body = month(&db, ana, MONTH);
    for date in ["2026-09-15", "2026-09-16", "2026-09-17"] {
        assert_eq!(counts(on(&body, date)), (0, 0, 0), "{date}");
    }
    assert_eq!(
        body["unscheduled"],
        json!({ "session_count": 1, "minutes": 60 })
    );
    assert_eq!(body["projects"], json!([]));
    assert_eq!(body["deadlines"][0]["unplanned_min"], 60);
}

#[test]
fn a_session_with_one_possible_day_and_no_time_is_unscheduled() {
    let db = fresh("one-day");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[session("s-tue", 1, "", json!({}))]);
    let body = month(&db, ana, MONTH);
    assert_eq!(counts(on(&body, "2026-09-15")), (0, 0, 0));
    assert_eq!(on(&body, "2026-09-15")["blocks"], json!([]));
    assert_eq!(
        body["unscheduled"],
        json!({ "session_count": 1, "minutes": 60 })
    );
}

#[test]
fn a_planned_session_is_scheduled_work_on_its_day() {
    let db = fresh("planned");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[session("s-tue", 1, "16:00", json!({}))]);
    let body = month(&db, ana, MONTH);
    assert_eq!(counts(on(&body, "2026-09-15")), (1, 60, 0));
    assert_eq!(
        body["unscheduled"],
        json!({ "session_count": 0, "minutes": 0 })
    );
}

#[test]
fn overdue_open_homework_is_not_a_deadline_of_the_month() {
    let db = fresh("overdue");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("hw-essay", json!({ "due": "2026-08-15T23:59" })),
    );
    let body = month(&db, ana, MONTH);
    assert_eq!(body["deadlines"], json!([]));
    assert_eq!(
        body["overdue"],
        json!([deadline("2026-08-15T23:59", "2026-08-15")])
    );
    assert_eq!(on(&body, "2026-09-01")["due_ids"], json!([]));
}

#[test]
fn a_finished_deadline_stays_on_its_date() {
    let db = fresh("finished-deadline");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "completed": true, "completed_at": "2026-09-16T20:00" }),
        ),
    );
    let body = month(&db, ana, MONTH);
    assert_eq!(body["deadlines"][0]["completed"], true);
    assert_eq!(body["projects"], json!([]));
    assert_eq!(on(&body, "2026-09-16")["due_ids"], json!(["hw-essay"]));
}

#[test]
fn finished_homework_due_before_the_grid_is_not_overdue() {
    let db = fresh("finished-old");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "due": "2026-08-15T23:59", "completed": true, "completed_at": "2026-08-14T20:00" }),
        ),
    );
    let body = month(&db, ana, MONTH);
    assert_eq!(
        (&body["overdue"], &body["deadlines"]),
        (&json!([]), &json!([]))
    );
}

#[test]
fn timer_work_chunks_count_as_sessions_and_breaks_as_fixed_blocks() {
    let db = fresh("pomodoro");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    let work = json!({
        "id": "essay-w1", "title": "Essay", "kind": "locked", "duration_min": 30, "days": [1],
        "priority": 3, "energy": "medium", "start": "16:00", "assignment_id": "hw-essay",
        "category": "Homework", "pomodoro_parent_id": "essay", "pomodoro_role": "work",
        "pomodoro_index": 1,
    });
    let rest = json!({
        "id": "essay-b1", "title": "Break", "kind": "locked", "duration_min": 15, "days": [1],
        "priority": 3, "energy": "medium", "start": "16:30", "category": "Homework",
        "pomodoro_parent_id": "essay", "pomodoro_role": "break", "pomodoro_index": 1,
    });
    save_week(&db, ana, &[work, rest]);
    let cell = month(&db, ana, MONTH);
    let tuesday = on(&cell, "2026-09-15");
    assert_eq!(
        (
            &tuesday["session_count"],
            &tuesday["locked_count"],
            &tuesday["scheduled_min"]
        ),
        (&json!(1), &json!(1), &json!(45))
    );
}

#[test]
fn a_month_label_that_is_not_ascii_yyyy_mm_in_range_is_refused() {
    let db = fresh("labels");
    let ana = account(&db, "ana");
    for label in [
        "\u{0662}\u{0660}\u{0662}\u{0666}-\u{0660}\u{0669}",
        "\u{ff12}\u{ff10}\u{ff12}\u{ff16}-\u{ff10}\u{ff19}",
        "2026-09-01",
        "2026-9",
        "2026-13",
        "1999-12",
        "2100-01",
    ] {
        match views::month(&db.path, ana, label, 0, now()) {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => {
                assert_eq!(words, MONTH_RULE, "{label}");
            }
            other => panic!("{label:?} was not refused: {other:?}"),
        }
    }
}

#[test]
fn a_first_day_past_sunday_is_refused() {
    let db = fresh("first-day");
    let ana = account(&db, "ana");
    assert!(matches!(
        views::month(&db.path, ana, "2026-12", 7, now()),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

#[test]
fn a_month_does_not_show_another_accounts_work() {
    let db = fresh("other");
    let (ana, ben) = (account(&db, "ana"), account(&db, "ben"));
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[school()]);
    let body = month(&db, ben, MONTH);
    assert_eq!(
        (&body["deadlines"], &body["projects"]),
        (&json!([]), &json!([]))
    );
    assert_eq!(on(&body, "2026-09-14")["scheduled_min"], 0);
}

#[test]
fn january_2000_starts_its_grid_on_the_first() {
    let db = fresh("2000");
    let ana = account(&db, "ana");
    let body = month(&db, ana, "2000-01");
    assert_eq!(body["grid_start"], "2000-01-01");
    let first = &body["days"][0];
    assert_eq!(
        (&first["date"], &first["week_start"], &first["in_month"]),
        (&json!("2000-01-01"), &json!("1999-12-27"), &json!(true))
    );
}

#[test]
fn december_2099_ends_its_grid_on_the_31st() {
    let db = fresh("2099");
    let ana = account(&db, "ana");
    let body = month(&db, ana, "2099-12");
    assert_eq!(body["grid_end"], "2099-12-31");
    let days = body["days"].as_array().unwrap();
    let last = &days[days.len() - 1];
    assert_eq!(
        (&last["date"], &last["week_start"], &last["in_month"]),
        (&json!("2099-12-31"), &json!("2099-12-28"), &json!(true))
    );
}

#[test]
fn a_deadline_with_no_time_sorts_after_a_morning_one_on_the_same_date() {
    let db = fresh("untimed");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("allday", json!({ "title": "All day", "due": "2026-09-15" })),
    );
    save_homework(
        &db,
        ana,
        homework(
            "morning",
            json!({ "title": "Morning", "due": "2026-09-15T09:00" }),
        ),
    );
    let body = month(&db, ana, MONTH);
    assert_eq!(ids(&body["deadlines"]), ["morning", "allday"]);
    assert_eq!(
        on(&body, "2026-09-15")["due_ids"],
        json!(["morning", "allday"])
    );
}

#[test]
fn blank_notes_do_not_make_a_deadline_a_project() {
    let db = fresh("blank-notes");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("hw-essay", json!({ "notes": "   \n\t  " })),
    );
    let body = month(&db, ana, MONTH);
    assert_eq!(body["projects"], json!([]));
    assert_eq!(ids(&body["deadlines"]), ["hw-essay"]);
}

#[test]
fn a_repeating_block_shows_on_each_of_its_dates_with_the_same_id() {
    let db = fresh("repeating");
    let ana = account(&db, "ana");
    save_week(&db, ana, &[school()]);
    let body = month(&db, ana, MONTH);
    let chip = json!({
        "id": "school", "title": "School", "start": "08:00", "duration_min": 390,
        "category": "School", "kind": "locked", "assignment_id": null, "repeats": true,
        "pinned": false, "completed": false,
    });
    for date in [
        "2026-09-14",
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
    ] {
        assert_eq!(on(&body, date)["blocks"], json!([chip]), "{date}");
    }
    assert_eq!(on(&body, "2026-09-19")["blocks"], json!([]));
}

#[test]
fn pinned_homework_shows_with_its_homework_id() {
    let db = fresh("pinned");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(
        &db,
        ana,
        &[session("s-tue", 1, "16:00", json!({ "pinned": true }))],
    );
    assert_eq!(
        on(&month(&db, ana, MONTH), "2026-09-15")["blocks"],
        json!([{
            "id": "s-tue", "title": "Essay", "start": "16:00", "duration_min": 60,
            "category": "Homework", "kind": "flexible", "assignment_id": "hw-essay",
            "repeats": false, "pinned": true, "completed": false,
        }])
    );
}

#[test]
fn blocks_on_a_date_are_in_start_then_title_order() {
    let db = fresh("order");
    let ana = account(&db, "ana");
    save_week(
        &db,
        ana,
        &[
            club("late-z", "Yoga", json!([0]), "18:00", 45),
            club("early-b", "Band", json!([0]), "07:00", 30),
            club("early-a", "Art", json!([0]), "07:00", 30),
        ],
    );
    let body = month(&db, ana, MONTH);
    let titles: Vec<&str> = on(&body, "2026-09-14")["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|chip| chip["title"].as_str().unwrap())
        .collect();
    assert_eq!(titles, ["Art", "Band", "Yoga"]);
}

/// September's grid ends Sunday 4 October; October's weeks begin Monday 28 September.
#[test]
fn a_block_on_the_last_sunday_and_one_on_the_next_months_first_monday_stay_on_their_dates() {
    let db = fresh("edges");
    let ana = account(&db, "ana");
    save_week_from(
        &db,
        ana,
        "2026-09-28",
        &[
            club("sunday-club", "Sunday club", json!([6]), "10:00", 60),
            club("week-open", "Week open", json!([0]), "07:00", 30),
        ],
    );
    let september = month(&db, ana, "2026-09");
    let last_sunday = &on(&september, "2026-10-04")["blocks"];
    assert_eq!(ids(last_sunday), ["sunday-club"]);
    assert_eq!(last_sunday[0]["start"], "10:00");
    let october = month(&db, ana, "2026-10");
    let first_monday = &on(&october, "2026-09-28")["blocks"];
    assert_eq!(ids(first_monday), ["week-open"]);
    assert_eq!(first_monday[0]["start"], "07:00");
}

/// Five timed blocks a day across the grid, as a packed week looks: the month names chips, not whole
/// week rows, so it stays a compact read.
#[test]
fn a_busy_month_stays_a_compact_read() {
    let db = fresh("busy");
    let ana = account(&db, "ana");
    for week in [
        "2026-08-31",
        "2026-09-07",
        "2026-09-14",
        "2026-09-21",
        "2026-09-28",
    ] {
        let mut blocks = Vec::new();
        for day in 0..7 {
            for slot in 0..5 {
                blocks.push(club(
                    &format!("{week}-{day}-{slot}"),
                    &format!("Club {slot}"),
                    json!([day]),
                    &format!("{:02}:00", 8 + slot),
                    45,
                ));
            }
        }
        save_week_from(&db, ana, week, &blocks);
    }
    let size = month(&db, ana, MONTH).to_string().len();
    assert!((20_000..80_000).contains(&size), "{size}");
}

/// December 2026 from Wednesday: 25 November (a Wednesday) to 5 January 2027 (a Tuesday), so the rows
/// reach back into the week of 23 November.
#[test]
fn rows_start_on_the_first_day_asked_for_and_carry_their_weeks() {
    let db = fresh("first-day-rows");
    let ana = account(&db, "ana");
    save_week_from(&db, ana, "2026-11-23", &[school()]);
    let body = month_at(&db, ana, "2026-12", 2, now());
    let days = body["days"].as_array().unwrap();
    assert_eq!(
        (&days[0]["date"], &days[days.len() - 1]["date"]),
        (&json!("2026-11-25"), &json!("2027-01-05"))
    );
    assert_eq!(days.len(), 42);
    let titles: Vec<&str> = on(&body, "2026-11-26")["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|chip| chip["title"].as_str().unwrap())
        .collect();
    assert_eq!(titles, ["School"]);
    let monday = month(&db, ana, "2026-12");
    let rows = monday["days"].as_array().unwrap();
    assert_eq!(
        (&rows[0]["date"], &rows[rows.len() - 1]["date"]),
        (&json!("2026-11-30"), &json!("2027-01-03"))
    );
}
