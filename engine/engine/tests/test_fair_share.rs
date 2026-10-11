//! P1 keeps the homework estimate intact while sharing only work due beyond the coming week.

use flexweek_engine::desk::planning::{fair_share, open_rest_sessions, time_still_needed};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-10-05"; // Monday

fn science(due: &str, estimate: i64) -> Map<String, Value> {
    let mut table = Map::new();
    table.insert(
        "sci".into(),
        json!({"id": "sci", "title": "Science project", "due": due, "estimate_min": estimate,
               "focus_minutes": 0}),
    );
    table
}

fn session(id: &str, minutes: i64) -> Value {
    json!({"id": id, "title": "Science project", "kind": "flexible", "assignment_id": "sci",
           "duration_min": minutes, "days": [0, 1, 2, 3, 4, 5, 6]})
}

fn share(
    blocks: &[Value],
    due: &str,
    estimate: i64,
    first_day: i64,
    targets: &[&str],
) -> (Vec<Value>, Vec<Value>) {
    let targets: Vec<String> = targets.iter().map(|t| t.to_string()).collect();
    fair_share(
        blocks,
        &science(due, estimate),
        &json!([]),
        WEEK,
        first_day,
        &targets,
    )
    .unwrap()
}

#[test]
fn due_next_wednesday_planned_on_saturday_stays_whole_within_seven_days() {
    let (blocks, notes) = share(&[session("s1", 120)], "2026-10-14T23:59", 120, 5, &["s1"]);
    assert_eq!(blocks[0]["duration_min"], json!(120));
    assert!(notes.is_empty());
}

#[test]
fn due_wednesday_after_next_week_gets_a_fair_share() {
    let (blocks, notes) = share(&[session("s1", 105)], "2026-10-14T23:59", 105, 0, &["s1"]);
    assert_eq!(blocks[0]["duration_min"], json!(90));
    assert_eq!(notes[0]["left_min"], json!(15));
}

#[test]
fn work_due_this_week_is_left_whole() {
    let (blocks, notes) = share(&[session("s1", 120)], "2026-10-09T23:59", 120, 5, &["s1"]);
    assert_eq!(blocks[0]["duration_min"], json!(120));
    assert!(notes.is_empty());
}

#[test]
fn due_next_monday_keeps_all_of_it_this_week() {
    // Every plannable day before it is in this week.
    let (blocks, notes) = share(&[session("s1", 120)], "2026-10-12T08:00", 120, 5, &["s1"]);
    assert_eq!(blocks[0]["duration_min"], json!(120));
    assert!(notes.is_empty());
}

#[test]
fn homework_due_within_seven_days_keeps_its_unplaced_session_with_existing_time() {
    let mut held = session("held", 45);
    held["start"] = json!("16:00");
    held["days"] = json!([5]);
    let (blocks, notes) = share(
        &[held.clone(), session("s1", 75)],
        "2026-10-14T23:59",
        120,
        5,
        &["s1"],
    );
    assert_eq!(blocks[1]["duration_min"], json!(75));
    assert!(notes.is_empty());
}

#[test]
fn homework_due_within_seven_days_is_not_removed_when_another_session_is_held() {
    let mut held = session("held", 60);
    held["start"] = json!("16:00");
    let (blocks, notes) = share(
        &[held, session("s1", 60)],
        "2026-10-14T23:59",
        120,
        5,
        &["s1"],
    );
    assert_eq!(blocks.len(), 2);
    assert!(notes.is_empty());
}

#[test]
fn planning_again_does_not_shrink_it_further() {
    // The first plan left a 60 min session; the second plan is worked out from the 120 min left.
    let (blocks, _) = share(&[session("s1", 60)], "2026-10-14T23:59", 120, 5, &["s1"]);
    assert_eq!(blocks[0]["duration_min"], json!(60));
}

#[test]
fn open_rest_adds_one_idempotent_session_for_homework_due_after_this_week() {
    let mut assignments = science("2026-10-14T23:59", 120);
    assignments["sci"]["unplanned_min"] = json!(120);
    let first = open_rest_sessions(&[], &assignments, WEEK).unwrap();
    assert_eq!(first.len(), 1);
    assert_eq!(first[0]["duration_min"], json!(120));
    assert_eq!(
        open_rest_sessions(&first, &assignments, WEEK).unwrap(),
        first
    );
}

#[test]
fn time_still_needed_reports_the_open_session_amount() {
    let mut assignments = science("2026-10-14T23:59", 120);
    assignments["sci"]["unplanned_min"] = json!(0);
    let counts = time_still_needed(&assignments, &[session("s1", 120)], WEEK).unwrap();
    assert_eq!(counts[0]["minutes"], json!(120));
    assert_eq!(counts[0]["period"], json!("later"));
}

#[test]
fn time_still_needed_adds_unplanned_minutes_and_open_week_remainder() {
    let mut assignments = science("2026-10-14T23:59", 120);
    assignments["sci"]["unplanned_min"] = json!(60);
    let counts = time_still_needed(&assignments, &[session("s1", 30)], WEEK).unwrap();
    assert_eq!(counts[0]["minutes"], json!(90));
}
