//! Plan offers a homework session every day from Monday through the day it is due, inside the open week.
//! A due date before the week offers Monday only; one after Sunday offers all seven days.

use flexweek_engine::desk::planning::session_days;
use serde_json::json;

const WEEK: &str = "2026-09-07"; // Monday

fn days(due: &str) -> Vec<i64> {
    session_days(WEEK, &json!(due)).expect("days")
}

#[test]
fn due_on_monday_offers_monday_only() {
    assert_eq!(days("2026-09-07T21:00"), vec![0]);
}

#[test]
fn due_on_friday_offers_monday_through_friday() {
    assert_eq!(days("2026-09-11T21:00"), vec![0, 1, 2, 3, 4]);
}

#[test]
fn due_after_the_week_offers_all_seven_days() {
    assert_eq!(days("2026-09-20T21:00"), vec![0, 1, 2, 3, 4, 5, 6]);
}

#[test]
fn due_before_the_week_offers_monday_only() {
    assert_eq!(days("2026-08-31T21:00"), vec![0]);
}
