use flexweek_engine::ErrorKind;
use flexweek_engine::model::{END_OF_DAY_MIN, parse_due, valid_spotify_url};
use flexweek_engine::plan::{due_placement_bound, due_slack_point};

#[test]
fn test_a_spotify_link_cannot_be_faked_by_putting_the_host_somewhere_else() {
    for attack in [
        "https://open.spotify.com@evil.com/track/abc",
        "https://evil.com/open.spotify.com/track/abc",
        "https://evil.com/?x=https://open.spotify.com/track/abc",
        "https://open.spotify.com.evil.com/track/abc",
        "http://open.spotify.com/track/abc",
        "https://open.spotify.com:8080/track/abc",
        "javascript:alert(1)//open.spotify.com/track/abc",
    ] {
        match valid_spotify_url(Some(attack)) {
            Err(err) if err.kind == ErrorKind::Value => {}
            other => panic!("{attack}: {other:?}"),
        }
    }
}

#[test]
fn test_a_real_share_link_still_passes() {
    for url in [
        "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        "https://open.spotify.com/track/abc?si=xyz",
    ] {
        assert_eq!(valid_spotify_url(Some(url)).unwrap(), Some(url.to_string()));
    }
}

#[test]
fn test_parse_due_treats_a_date_and_2359_as_the_end_of_that_day() {
    let (tuesday, minutes) = parse_due("2026-09-15").unwrap();
    assert_eq!(tuesday.to_string(), "2026-09-15");
    assert_eq!(minutes, END_OF_DAY_MIN);
    let (same_day, end) = parse_due("2026-09-15T23:59").unwrap();
    assert_eq!(same_day.to_string(), "2026-09-15");
    assert_eq!(end, END_OF_DAY_MIN);
    let (morning, at_nine) = parse_due("2026-09-15T09:00").unwrap();
    assert_eq!(morning.to_string(), "2026-09-15");
    assert_eq!(at_nine, 9 * 60);

    let week = "2026-09-14";
    assert_eq!(
        due_placement_bound(week, "2026-09-15").unwrap(),
        Some((1, END_OF_DAY_MIN))
    );
    assert_eq!(
        due_placement_bound(week, "2026-09-15T23:59").unwrap(),
        Some((1, END_OF_DAY_MIN))
    );
    assert_eq!(
        due_placement_bound(week, "2026-09-15T09:00").unwrap(),
        Some((1, 9 * 60))
    );
    assert_eq!(
        due_slack_point(week, "2026-09-15").unwrap(),
        due_slack_point(week, "2026-09-15T23:59").unwrap()
    );
}

// The homework and session-block rules of docs/stage1-contract.md, as the engine checks them (the Rust twins
// of the model tests in backend/tests/test_homework_rules.py). Expected values are from the contract.

use flexweek_engine::validate::{assignment_content, time_block};
use serde_json::{Map, Value, json};

/// A homework as the app saves it (its revision travels beside it); `changes` replace single fields.
fn homework(changes: Value) -> Value {
    let mut body = json!({
        "id": "hw-essay", "title": "Essay", "course": "History", "category": null, "priority": 3,
        "energy": "medium", "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120,
        "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
    });
    merge(&mut body, changes);
    body
}

fn session(changes: Value) -> Value {
    let mut block = json!({
        "id": "sess-1", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0, 1],
        "priority": 3, "energy": "medium", "assignment_id": "hw-essay",
    });
    merge(&mut block, changes);
    block
}

fn merge(into: &mut Value, changes: Value) {
    let fields: &mut Map<String, Value> = into.as_object_mut().unwrap();
    for (key, value) in changes.as_object().unwrap() {
        fields.insert(key.clone(), value.clone());
    }
}

fn refused_homework(changes: Value) -> String {
    match assignment_content(&homework(changes.clone())) {
        Err(why) => why,
        Ok(_) => panic!("accepted {changes}"),
    }
}

fn refused_block(changes: Value) -> String {
    match time_block(&session(changes.clone())) {
        Err(why) => why,
        Ok(_) => panic!("accepted {changes}"),
    }
}

#[test]
fn a_homework_due_at_any_minute_is_kept_and_written_with_every_field() {
    assert_eq!(
        assignment_content(&homework(json!({}))).unwrap().to_value(),
        homework(json!({}))
    );
}

#[test]
fn a_homework_with_a_field_the_app_does_not_know_is_refused() {
    assert_eq!(
        refused_homework(json!({ "planned_min": 30 })),
        "Extra inputs are not permitted"
    );
}

#[test]
fn a_homework_is_done_in_one_go_unless_spread_out_is_chosen() {
    let plain = assignment_content(&homework(json!({}))).unwrap().to_value();
    assert!(plain.get("spread").is_none(), "{plain}");
    let spread = assignment_content(&homework(json!({ "spread": "spread" })))
        .unwrap()
        .to_value();
    assert_eq!(spread["spread"], "spread");
    assert!(refused_homework(json!({ "spread": "sometimes" })).contains("spread"));
}

#[test]
fn a_due_can_be_a_date_alone() {
    let saved = assignment_content(&homework(json!({ "due": "2026-09-15" }))).unwrap();
    assert_eq!(saved.to_value()["due"], "2026-09-15");
}

#[test]
fn a_due_with_seconds_a_time_zone_or_outside_2000_to_2099_is_refused() {
    for due in [
        "2026-09-15T23:59:00",
        "2026-09-15T23:59Z",
        "2026-09-15 23:59",
        "2026-09-15T24:00",
        "1999-12-31T23:59",
        "2100-01-01T00:00",
        "20260915T23:59",
        "2026-09-15T",
        "2026-09-15 09:00",
        "15-09-2026",
    ] {
        refused_homework(json!({ "due": due }));
    }
}

#[test]
fn a_due_need_not_be_on_the_15_minute_grid() {
    for due in [
        "2026-09-15T23:59",
        "2026-09-14T00:00",
        "2026-09-08T05:01",
        "2026-09-15",
    ] {
        assert_eq!(
            assignment_content(&homework(json!({ "due": due })))
                .unwrap()
                .to_value()["due"],
            due
        );
    }
}

#[test]
fn an_estimate_is_a_positive_multiple_of_15_up_to_a_day() {
    for estimate in [0, 10, 7141, -15, 24 * 60 + 15, 99 * 60] {
        refused_homework(json!({ "estimate_min": estimate }));
    }
    let day = assignment_content(&homework(json!({ "estimate_min": 24 * 60 }))).unwrap();
    assert_eq!(day.to_value()["estimate_min"], 24 * 60);
}

#[test]
fn finished_homework_needs_its_finish_time_and_open_homework_has_none() {
    assert!(
        refused_homework(json!({ "completed": true, "completed_at": null }))
            .contains("completed_at")
    );
    assert!(
        refused_homework(json!({ "completed": false, "completed_at": "2026-09-13T23:59" }))
            .contains("completed_at")
    );
    let done = assignment_content(&homework(
        json!({ "completed": true, "completed_at": "2026-09-13T16:00" }),
    ));
    assert_eq!(done.unwrap().to_value()["completed_at"], "2026-09-13T16:00");
}

#[test]
fn a_homework_session_carries_no_latest_and_no_focus_time() {
    assert!(refused_block(json!({ "latest": "Thursday 21:00" })).contains("latest"));
    assert!(refused_block(json!({ "focus_minutes": 15 })).contains("focus"));
    assert!(refused_block(json!({ "focus_sessions": 1 })).contains("focus"));
}

#[test]
fn a_homework_session_does_not_keep_a_due() {
    let block = time_block(&session(json!({ "due": "2026-09-15T23:59" })))
        .unwrap()
        .to_value();
    assert!(block.get("due").is_none(), "{block}");
}

#[test]
fn a_break_chunk_or_a_fixed_block_cannot_be_a_homework_session() {
    let pomodoro_break = json!({
        "kind": "locked", "start": "16:00", "duration_min": 15, "pomodoro_parent_id": "essay",
        "pomodoro_role": "break", "pomodoro_index": 1,
    });
    assert!(refused_block(pomodoro_break).contains("assignment_id"));
    assert!(
        refused_block(json!({ "kind": "locked", "start": "08:00", "duration_min": 60 }))
            .contains("assignment_id")
    );
}

#[test]
fn a_flexible_session_and_a_pomodoro_work_chunk_can_be_homework_sessions() {
    let flexible = time_block(&session(json!({}))).unwrap().to_value();
    assert_eq!(flexible["assignment_id"], "hw-essay");
    assert_eq!(time_block(&session(json!({}))).unwrap().focus_minutes, 0);
    assert!(flexible["latest"].is_null());
    let work = json!({
        "kind": "locked", "start": "16:00", "duration_min": 30, "pomodoro_parent_id": "essay",
        "pomodoro_role": "work", "pomodoro_index": 1,
    });
    assert_eq!(
        time_block(&session(work)).unwrap().to_value()["assignment_id"],
        "hw-essay"
    );
}
