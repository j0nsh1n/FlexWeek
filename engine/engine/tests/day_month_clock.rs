//! Day's due-soon list and Month's deadlines count what a session holds the way every other count does:
//! in an earlier week a session holds its time while it is still ahead of now, and not once it has passed.

use flexweek_engine::plan::{Moment, build_day, build_month_from, parse_moment};
use serde_json::{Value, json};

// Homework due Monday 2 November, 60 minutes, with its one session on Wednesday 21 October, 15:00.
fn weeks() -> Vec<(String, Vec<Value>)> {
    vec![(
        "2026-10-19".to_string(),
        vec![json!({
            "id": "s1", "title": "Essay", "kind": "flexible", "assignment_id": "essay",
            "start": "15:00", "duration_min": 60, "days": [2],
        })],
    )]
}

fn rows() -> Vec<(Value, i64)> {
    vec![(
        json!({"id": "essay", "title": "Essay", "due": "2026-11-02T18:00", "estimate_min": 60}),
        1,
    )]
}

fn moment(text: &str) -> Option<Moment> {
    Some(parse_moment(text).unwrap())
}

fn day_unplanned(now: Option<Moment>) -> i64 {
    let day = build_day("2026-11-02", "2026-11-02", &[], &rows(), &weeks(), now).unwrap();
    day["due_soon"][0]["unplanned_min"].as_i64().unwrap()
}

fn month_unplanned(now: Option<Moment>) -> i64 {
    let month = build_month_from("2026-11", &rows(), &weeks(), 0, now).unwrap();
    month["deadlines"][0]["unplanned_min"].as_i64().unwrap()
}

#[test]
fn a_session_ahead_of_now_in_an_earlier_week_holds_its_time_on_day_and_month() {
    let monday = moment("2026-10-19T00:00");
    assert_eq!(day_unplanned(monday), 0);
    assert_eq!(month_unplanned(monday), 0);
}

#[test]
fn a_session_that_passed_unfinished_is_still_needed_on_day_and_month() {
    let thursday = moment("2026-10-22T09:00");
    assert_eq!(day_unplanned(thursday), 60);
    assert_eq!(month_unplanned(thursday), 60);
}

// Homework due Friday 20 November 18:00, 60 minutes, with its one session in the week of Monday
// 16 November (the requested week), on `day` (0 = Monday) at 15:00, read on Thursday 19 November.
fn this_week(day: i64) -> Vec<(String, Vec<Value>)> {
    vec![(
        "2026-11-16".to_string(),
        vec![json!({
            "id": "s1", "title": "Essay", "kind": "flexible", "assignment_id": "essay",
            "start": "15:00", "duration_min": 60, "days": [day],
        })],
    )]
}

fn november_rows() -> Vec<(Value, i64)> {
    vec![(
        json!({"id": "essay", "title": "Essay", "due": "2026-11-20T18:00", "estimate_min": 60}),
        1,
    )]
}

fn friday_reading(day: i64) -> (i64, Value) {
    let thursday = moment("2026-11-19T09:00");
    let reading = build_day(
        "2026-11-20",
        "2026-11-16",
        &[],
        &november_rows(),
        &this_week(day),
        thursday,
    )
    .unwrap();
    (
        reading["due_soon"][0]["unplanned_min"].as_i64().unwrap(),
        reading["next_action"]["kind"].clone(),
    )
}

fn november_unplanned(day: i64) -> i64 {
    let thursday = moment("2026-11-19T09:00");
    let month =
        build_month_from("2026-11", &november_rows(), &this_week(day), 0, thursday).unwrap();
    month["deadlines"][0]["unplanned_min"].as_i64().unwrap()
}

#[test]
fn a_session_of_the_requested_week_that_passed_unfinished_is_still_needed() {
    // Missed on Tuesday 17th: only a session ticked done or still ahead of now holds its time.
    assert_eq!(friday_reading(1), (60, json!("plan")));
    assert_eq!(november_unplanned(1), 60);
}

#[test]
fn a_session_of_the_requested_week_still_ahead_holds_its_time() {
    // Thursday 19th 15:00 is after the 09:00 clock, so nothing is needed and nothing is to plan.
    assert_eq!(friday_reading(3), (0, json!("add")));
    assert_eq!(november_unplanned(3), 0);
}
