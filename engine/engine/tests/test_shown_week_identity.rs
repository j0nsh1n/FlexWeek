//! A block keeps who it is across the Monday seam. Shown from Wednesday 11 November 2026, the week
//! takes Wednesday 11 to Sunday 15 from Monday 9's stored week (its days 2 to 6) and Monday 16 and
//! Tuesday 17 from Monday 16's (its days 0 and 1). School stands Monday to Friday, so a change made on
//! screen reaches only some days of each stored week and the other days keep what they had.

use flexweek_engine::shown::{compose_shown_week, split_shown_week};
use serde_json::{Map, Value, json};

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

fn ids(blocks: &[Value]) -> Vec<String> {
    let mut ids: Vec<String> = blocks
        .iter()
        .map(|block| block["id"].as_str().unwrap().to_string())
        .collect();
    ids.sort();
    ids
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

/// A small fixed-seed generator: the same weeks on every run.
struct Seeded(u64);

impl Seeded {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        self.0 >> 33
    }

    fn below(&mut self, n: u64) -> u64 {
        self.next() % n
    }

    fn days(&mut self) -> Vec<i64> {
        let mut days: Vec<i64> = (0..7).filter(|_| self.below(2) == 0).collect();
        if days.is_empty() {
            days.push(self.below(7) as i64);
        }
        days
    }
}

fn random_week(rng: &mut Seeded) -> Vec<Value> {
    let mut week = Vec::new();
    for id in ["school", "read", "gym", "club", "activity-1a2b3c4d"] {
        if rng.below(3) == 0 {
            continue;
        }
        let title = if rng.below(4) == 0 { "Other" } else { id };
        let start = ["09:00", "11:00"][rng.below(2) as usize];
        week.push(
            json!({"id": id, "title": title, "kind": "locked", "duration_min": 60,
                         "start": start, "days": rng.days()}),
        );
    }
    week
}

/// What a week on screen shows, ids aside: each block's content and the days it is on.
fn picture(shown: &[Value]) -> Vec<String> {
    let mut rows: Vec<String> = shown
        .iter()
        .map(|block| {
            let mut fields: Map<String, Value> = block.as_object().unwrap().clone();
            fields.shift_remove("id");
            let mut keys: Vec<String> = fields.keys().cloned().collect();
            keys.sort();
            keys.iter()
                .map(|key| format!("{key}={}", fields[key]))
                .collect::<Vec<_>>()
                .join(",")
        })
        .collect();
    rows.sort();
    rows
}

/// Every (stored week, day, start, title) a block happens on.
fn happenings(first: &[Value], second: &[Value]) -> Vec<String> {
    let mut out = Vec::new();
    for (week, blocks) in [("A", first), ("B", second)] {
        for block in blocks {
            for day in days(block) {
                out.push(format!("{week}{day}{}{}", block["start"], block["title"]));
            }
        }
    }
    out.sort();
    out
}

fn edit(rng: &mut Seeded, shown: &mut Vec<Value>, round: usize) -> Option<usize> {
    if shown.is_empty() {
        return None;
    }
    let at = rng.below(shown.len() as u64) as usize;
    match rng.below(4) {
        0 => shown[at]["title"] = json!(format!("Edit {round}")),
        1 => shown[at]["start"] = json!(format!("15:{:02}", round % 60)),
        2 => shown[at]["days"] = json!(rng.days()),
        _ => {
            shown.remove(at);
            return None;
        }
    }
    Some(at)
}

#[test]
fn one_change_on_screen_never_splits_a_block_and_the_next_change_reaches_all_of_it() {
    let mut rng = Seeded(20_261_111);
    // 9 to 15 November are Monday to Sunday; each of them but Monday starts a week over the seam.
    for start in [
        "2026-11-10",
        "2026-11-11",
        "2026-11-12",
        "2026-11-13",
        "2026-11-14",
        "2026-11-15",
    ] {
        for round in 0..400 {
            let (first, second) = (random_week(&mut rng), random_week(&mut rng));
            let original = compose_shown_week(start, &first, &second).unwrap();
            // Saved back unchanged, both stored weeks stay exactly as they were.
            assert_eq!(
                split_shown_week(start, &original, &first, &second).unwrap(),
                (first.clone(), second.clone())
            );
            let mut shown = original.clone();
            let edited = edit(&mut rng, &mut shown, round);
            let (first_now, second_now) = split_shown_week(start, &shown, &first, &second).unwrap();
            let again = compose_shown_week(start, &first_now, &second_now).unwrap();
            let case = format!("start {start} round {round}\n{first:?}\n{second:?}\n{shown:?}");
            assert_eq!(picture(&again), picture(&shown), "{case}");
            for week in [&first_now, &second_now] {
                let all = ids(week);
                let mut unique = all.clone();
                unique.dedup();
                assert_eq!(all, unique, "{case}");
                // A piece is named after its family once, never after another piece.
                assert!(all.iter().all(|id| id.matches('@').count() <= 1), "{case}");
            }
            // The next change reaches every day of the block changed before.
            if let Some(at) = edited {
                let target = picture(&shown[at..=at]);
                let mut next = again.clone();
                let row = next
                    .iter()
                    .position(|block| picture(std::slice::from_ref(block)) == target)
                    .unwrap();
                next[row]["title"] = json!("Next");
                let (first_next, second_next) =
                    split_shown_week(start, &next, &first_now, &second_now).unwrap();
                let shown_next = compose_shown_week(start, &first_next, &second_next).unwrap();
                assert_eq!(picture(&shown_next), picture(&next), "{case}");
            }
            // Undo puts the original week on screen back over the changed weeks: nothing lost or doubled.
            let (first_undo, second_undo) =
                split_shown_week(start, &original, &first_now, &second_now).unwrap();
            assert_eq!(
                happenings(&first_undo, &second_undo),
                happenings(&first, &second),
                "{case}"
            );
        }
    }
}
