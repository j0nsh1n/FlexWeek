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
