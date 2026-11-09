//! Rust twin of the pure checks in `desktop/tests/test_homework_plan.py`: where a plan may start (now,
//! rounded up to the next quarter hour) and that Plan sends the start as a `not_before` limit, never as
//! a stored field of the session.

use flexweek_engine::desk::planning::{plan_start_at, solve_request};
use serde_json::{Value, json};

/// The week of Monday 21 September 2026, with the clock read at `day` of September at `hour:minute`.
fn at(day: u32, hour: i64, minute: i64, second: i64) -> Option<(i64, i64)> {
    plan_start_at(
        "2026-09-21",
        &format!("2026-09-{day:02}"),
        hour,
        minute,
        second,
        0,
    )
    .expect("a start")
}

#[test]
fn test_a_plan_starts_at_now_rounded_up_to_the_next_quarter_hour() {
    assert_eq!(at(24, 10, 0, 0), Some((3, 600)), "on the quarter: now");
    assert_eq!(
        at(24, 10, 0, 30),
        Some((3, 615)),
        "a half minute counts as a whole one"
    );
    assert_eq!(at(24, 10, 7, 0), Some((3, 615)));
    assert_eq!(
        at(24, 23, 50, 0),
        Some((4, 0)),
        "past 23:45 the plan starts the next morning"
    );
    assert_eq!(
        at(27, 23, 55, 0),
        Some((7, 0)),
        "past Sunday: the week is over"
    );
    assert_eq!(at(20, 22, 0, 0), None, "the whole week is still ahead");
}

#[test]
fn test_plan_sends_earliest_from_not_before_not_a_stored_session_field() {
    // DEADLINE_PASSED compares due to earliest; Plan sets earliest from now through not_before.
    let blocks = json!([{
        "id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "assignment_id": "essay-a",
    }]);
    let assignments = json!({
        "essay-a": {
            "id": "essay-a",
            "title": "Essay",
            "due": "2026-09-08T23:59",
            "estimate_min": 60,
            "focus_minutes": 0,
            "revision": 0,
        }
    });
    let not_before = json!([0, 10 * 60 + 30]);
    let (payload, targets) = solve_request(
        &blocks,
        &assignments,
        "2026-09-07",
        false,
        None,
        Some(&not_before),
        false,
    )
    .expect("a request");
    assert_eq!(targets, [json!("essay")]);
    let placed = payload
        .iter()
        .find(|block| block["id"] == "essay")
        .expect("the essay in the request");
    assert_eq!(placed["earliest"], "Monday 10:30");
    assert_eq!(
        blocks[0].get("earliest"),
        None::<&Value>,
        "the stored block is left alone"
    );
}
