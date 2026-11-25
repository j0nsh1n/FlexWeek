//! The homework minute counts refuse a total no count can hold instead of wrapping or panicking.

use flexweek_engine::desk::planning::{credited_done_minutes, session_minutes};
use serde_json::{Value, json};

fn done_session(minutes: i64) -> Value {
    json!({"id": "s", "assignment_id": "essay", "completed": true, "duration_min": minutes})
}

#[test]
fn a_server_done_count_below_what_a_number_holds_less_the_saved_ticks_is_refused() {
    let assignment = json!({"id": "essay", "done_min": i64::MIN});
    let saved_week = json!([done_session(30)]);
    let said = credited_done_minutes(&assignment, &json!("essay"), &json!([]), &saved_week)
        .expect_err("MIN less 30 cannot be counted");
    assert!(said.message.contains("too many"), "{}", said.message);
}

#[test]
fn a_server_done_count_at_the_top_plus_this_weeks_ticks_is_refused() {
    let assignment = json!({"id": "essay", "done_min": i64::MAX});
    let blocks = json!([done_session(30)]);
    assert!(credited_done_minutes(&assignment, &json!("essay"), &blocks, &json!([])).is_err());
}

#[test]
fn sessions_whose_lengths_add_past_the_top_are_refused() {
    let open = |minutes: i64| json!({"assignment_id": "essay", "duration_min": minutes});
    let blocks = json!([open(i64::MAX), open(1)]);
    assert!(session_minutes(&blocks, &json!("essay")).is_err());
    assert_eq!(
        session_minutes(&json!([open(30), open(45)]), &json!("essay")).unwrap(),
        75
    );
}
