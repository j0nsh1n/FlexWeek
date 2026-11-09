//! What the day's free time counts. Moved from backend/tests/test_day_api.py, which called the same
//! function through the Python wrapper.

use flexweek_engine::plan::build_day;
use serde_json::json;

#[test]
fn test_a_block_at_any_minute_takes_every_quarter_hour_it_touches_from_free_time() {
    // Free time is the quarter hours the planner can still use. A lesson from 17:37 to 18:22 leaves
    // none of 17:30 to 18:30; with its end floored, 18:15 was counted free.
    let lesson = json!({
        "id": "lesson", "title": "Lesson", "kind": "locked",
        "start": "17:37", "duration_min": 45, "days": [1],
    });
    let day = build_day("2026-09-15", "2026-09-14", &[lesson], &[], &[]).unwrap();
    assert_eq!(day["workload"]["available_min"], 24 * 60 - 60);
}
