//! A block keeps who it is across the Monday seam. Shown from Wednesday 11 November 2026, the week
//! takes Wednesday 11 to Sunday 15 from Monday 9's stored week (its days 2 to 6) and Monday 16 and
//! Tuesday 17 from Monday 16's (its days 0 and 1). School stands Monday to Friday, so a change made on
//! screen reaches only some days of each stored week and the other days keep what they had.

use flexweek_engine::shown::{compose_shown_week, split_shown_week};
use serde_json::{Value, json};

const WED: &str = "2026-11-11";

fn school(start: &str) -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
           "start": start, "duration_min": 405, "days": [0, 1, 2, 3, 4]})
}

fn days(block: &Value) -> Vec<i64> {
    block["days"]
        .as_array()
        .unwrap()
        .iter()
        .map(|day| day.as_i64().unwrap())
        .collect()
}

/// (start, days) of every School block in a stored week, earliest start first.
fn school_times(blocks: &[Value]) -> Vec<(String, Vec<i64>)> {
    let mut times: Vec<(String, Vec<i64>)> = blocks
        .iter()
        .filter(|block| block["title"] == "School")
        .map(|block| (block["start"].as_str().unwrap().to_string(), days(block)))
        .collect();
    times.sort();
    times
}

#[test]
fn school_changed_on_screen_still_shows_as_school_and_keeps_its_id_in_both_stored_weeks() {
    let (first, second) = (vec![school("08:30")], vec![school("08:30")]);
    let mut shown = compose_shown_week(WED, &first, &second).unwrap();
    assert_eq!(shown.len(), 1);
    shown[0]["start"] = json!("10:00");
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    // Monday 9 and Tuesday 10 keep 08:30, Wednesday 18 to Friday 20 too.
    assert_eq!(
        school_times(&first_back),
        vec![
            ("08:30".to_string(), vec![0, 1]),
            ("10:00".to_string(), vec![2, 3, 4])
        ]
    );
    assert_eq!(
        school_times(&second_back),
        vec![
            ("08:30".to_string(), vec![2, 3, 4]),
            ("10:00".to_string(), vec![0, 1])
        ]
    );
    // Each stored week still has School by its own id.
    assert!(first_back.iter().any(|block| block["id"] == "school"));
    assert!(second_back.iter().any(|block| block["id"] == "school"));
    // Shown again it is one block, School, at 10:00 on every school day of the week.
    let again = compose_shown_week(WED, &first_back, &second_back).unwrap();
    assert_eq!(again.len(), 1, "{again:?}");
    assert_eq!(again[0]["id"], "school");
    assert_eq!(again[0]["start"], "10:00");
    assert_eq!(days(&again[0]), vec![0, 1, 2, 5, 6]);
}

#[test]
fn school_changed_from_this_week_on_leaves_the_next_stored_week_whole() {
    // The server moves the repeat to 10:00 from Monday 16 before it splits the week on screen, so the
    // second stored week already has School at 10:00 on every day.
    let first = vec![school("08:30")];
    let before = compose_shown_week(WED, &first, &[school("08:30")]).unwrap();
    let mut shown = before.clone();
    shown[0]["start"] = json!("10:00");
    let second = vec![school("10:00")];
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    assert_eq!(second_back, second);
    assert_eq!(
        school_times(&first_back),
        vec![
            ("08:30".to_string(), vec![0, 1]),
            ("10:00".to_string(), vec![2, 3, 4])
        ]
    );
    assert!(
        first_back
            .iter()
            .any(|block| block["id"] == "school" && block["start"] == "08:30")
    );
    let again = compose_shown_week(WED, &first_back, &second_back).unwrap();
    assert_eq!(again.len(), 1, "{again:?}");
    assert_eq!(again[0]["id"], "school");
    assert_eq!(days(&again[0]), vec![0, 1, 2, 5, 6]);
}
