//! A session placed on top of a fixed block (School, say) loses its time and the student is told why.

use flexweek_engine::desk::planning::settle_placements;
use serde_json::json;

#[test]
fn a_session_that_overlaps_school_loses_its_start_and_says_what_is_there_now() {
    let blocks = json!([
        {
            "id": "school",
            "kind": "locked",
            "title": "School",
            "start": "09:00",
            "duration_min": 60,
            "days": [0],
        },
        {
            "id": "hw",
            "kind": "flexible",
            "title": "Essay",
            "start": "09:30",
            "duration_min": 30,
            "days": [0],
            "assignment_id": "a",
        },
    ]);
    let assignments = json!({"a": {"id": "a", "due": "2026-09-07T18:00", "title": "Essay"}});

    let (kept, lost) =
        settle_placements(&blocks, &assignments, "2026-09-07", &json!([]), false).expect("a week");

    let kept = kept.as_array().expect("blocks");
    assert_eq!(kept[1]["id"], "hw");
    assert!(kept[1].get("start").is_none(), "{:?}", kept[1]);
    let message = lost[0]["message"].as_str().expect("a message");
    assert!(message.contains("Essay no longer fits"), "{message}");
    assert!(message.contains("School is there now"), "{message}");
}

#[test]
fn the_notice_names_the_day_from_the_week_on_screen() {
    let blocks = json!([
        {
            "id": "club",
            "kind": "locked",
            "title": "Club",
            "start": "16:00",
            "duration_min": 120,
            "days": [2],
        },
        {
            "id": "hw",
            "kind": "flexible",
            "title": "History essay",
            "start": "16:30",
            "duration_min": 60,
            "days": [2],
            "assignment_id": "a",
        },
    ]);
    let assignments =
        json!({"a": {"id": "a", "due": "2026-11-24T21:00", "title": "History essay"}});

    // Column 2 of a week that starts on Wednesday 18 November is Friday.
    let (_, lost) = settle_placements(&blocks, &assignments, "2026-11-18", &json!(["club"]), false)
        .expect("a week");
    let message = lost[0]["message"].as_str().expect("a message");
    assert!(
        message.contains("no longer fits Friday at 16:30"),
        "{message}"
    );

    let (_, lost) = settle_placements(&blocks, &assignments, "2026-11-16", &json!(["club"]), false)
        .expect("a week");
    let message = lost[0]["message"].as_str().expect("a message");
    assert!(
        message.contains("no longer fits Wednesday at 16:30"),
        "{message}"
    );
}
