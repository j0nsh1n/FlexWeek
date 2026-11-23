//! Planner settings (Settings > Planning: the gap before fixed blocks, homework-free weekends, due work first,
//! splitting long tasks, the end of the day, weekends on screen) as Plan uses them. Times are the same counts
//! as the engine's tests. The Rust twins of backend/tests/test_planner_settings.py.

use std::collections::BTreeMap;

use flexweek_service::homework_saves::save_homework;
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const PLANNER_KEYS: [&str; 5] = [
    "weekend_homework_free",
    "buffer_min",
    "urgent_first",
    "split_long_tasks",
    "show_weekends",
];

fn save(db: &TestDb, user: i64, changes: Value) -> Value {
    let mut prefs = read_preferences(&db.path, user).unwrap();
    for (key, value) in changes.as_object().unwrap() {
        prefs[key] = value.clone();
    }
    write_preferences(&db.path, user, &prefs).unwrap()
}

fn refused(db: &TestDb, user: i64, changes: Value) -> bool {
    let mut prefs = read_preferences(&db.path, user).unwrap();
    for (key, value) in changes.as_object().unwrap() {
        prefs[key] = value.clone();
    }
    matches!(
        write_preferences(&db.path, user, &prefs),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    )
}

fn block(id: &str, minutes: i64, days: Value, extra: Value) -> Value {
    let mut block = json!({ "id": id, "title": id, "kind": "flexible", "duration_min": minutes, "days": days,
                            "priority": 3, "energy": "medium" });
    for (key, value) in extra.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

fn solve(db: &TestDb, user: i64, given: Value) -> Value {
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    plan(&db.path, user, &given, &start_clock).unwrap()
}

/// Each flexible block placed, by id: (day, start, length).
fn placed(db: &TestDb, user: i64, blocks: Value) -> BTreeMap<String, (i64, String, i64)> {
    solve(db, user, json!({ "blocks": blocks }))["placed"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|item| item["kind"] == "flexible")
        .map(|item| {
            (
                item["id"].as_str().unwrap().to_string(),
                (
                    item["days"][0].as_i64().unwrap(),
                    item["start"].as_str().unwrap().to_string(),
                    item["duration_min"].as_i64().unwrap(),
                ),
            )
        })
        .collect()
}

fn at(day: i64, start: &str, minutes: i64) -> (i64, String, i64) {
    (day, start.to_string(), minutes)
}

#[test]
fn a_new_account_answers_no_planner_settings_and_saves_back_unchanged() {
    let db = TestDb::new("planner-fresh");
    let ana = db.account("ana");
    let body = read_preferences(&db.path, ana).unwrap();
    for key in PLANNER_KEYS {
        assert!(body.get(key).is_none(), "{key} in {body}");
    }
    assert_eq!(write_preferences(&db.path, ana, &body).unwrap(), body);
}

#[test]
fn the_focus_timers_pacing_stays_apart_from_splitting_a_long_task() {
    let db = TestDb::new("planner-pacing");
    let ana = db.account("ana");
    let saved = save(
        &db,
        ana,
        json!({ "split_long_tasks": true, "timer_work_min": 25, "timer_break_min": 5 }),
    );
    assert_eq!(
        (
            &saved["split_long_tasks"],
            &saved["timer_work_min"],
            &saved["auto_split_pomodoro"]
        ),
        (&json!(true), &json!(25), &json!(false))
    );
    assert!(refused(&db, ana, json!({ "auto_split_pomodoro": true })));
}

#[test]
fn the_gap_before_fixed_blocks_is_15_by_default_and_an_unknown_gap_is_refused() {
    let db = TestDb::new("planner-gap");
    let ana = db.account("ana");
    assert!(
        save(&db, ana, json!({ "buffer_min": 15 }))
            .get("buffer_min")
            .is_none()
    );
    assert!(
        read_preferences(&db.path, ana)
            .unwrap()
            .get("buffer_min")
            .is_none()
    );
    assert!(refused(&db, ana, json!({ "buffer_min": 10 })));
}

#[test]
fn each_planner_setting_moves_the_week() {
    let db = TestDb::new("planner-moves");
    let ana = db.account("ana");
    let friday = json!([{ "days": [4], "start": "16:00", "end": "20:00" }]);
    let both = json!([{ "days": [4], "start": "16:00", "end": "20:00" }, { "days": [5], "start": "10:00", "end": "12:00" }]);
    save(&db, ana, json!({ "work_windows": friday }));
    let homework = json!([
        block(
            "class",
            60,
            json!([4]),
            json!({ "kind": "locked", "start": "15:00" })
        ),
        block("hw", 60, json!([4]), json!({})),
    ]);
    assert_eq!(placed(&db, ana, homework.clone())["hw"], at(4, "16:15", 60));
    save(&db, ana, json!({ "buffer_min": 0 }));
    assert_eq!(placed(&db, ana, homework.clone())["hw"], at(4, "16:00", 60));
    save(&db, ana, json!({ "buffer_min": 30 }));
    assert_eq!(placed(&db, ana, homework)["hw"], at(4, "16:30", 60));
    save(&db, ana, json!({ "buffer_min": 0, "work_windows": both }));
    let pair = json!([
        block(
            "science",
            60,
            json!([4]),
            json!({ "latest": "Friday 18:00" })
        ),
        block("math", 60, json!([4, 5]), json!({ "energy": "high" })),
    ]);
    let found = placed(&db, ana, pair.clone());
    assert_eq!(
        (&found["science"], &found["math"]),
        (&at(4, "16:00", 60), &at(5, "10:00", 60))
    );
    save(&db, ana, json!({ "weekend_homework_free": true }));
    assert_eq!(placed(&db, ana, pair)["math"], at(4, "17:00", 60));
    save(
        &db,
        ana,
        json!({ "weekend_homework_free": false, "work_windows": [{ "days": [4], "start": "16:00", "end": "18:00" }] }),
    );
    let urgent = json!([
        block(
            "a-math",
            60,
            json!([4]),
            json!({ "latest": "Sunday 20:00" })
        ),
        block(
            "b-science",
            60,
            json!([4]),
            json!({ "latest": "Friday 20:00" })
        ),
    ]);
    assert_eq!(
        placed(&db, ana, urgent.clone())["b-science"],
        at(4, "16:00", 60)
    );
    save(&db, ana, json!({ "urgent_first": false }));
    assert_eq!(placed(&db, ana, urgent)["a-math"], at(4, "16:00", 60));
    save(
        &db,
        ana,
        json!({ "urgent_first": true, "work_windows": both }),
    );
    let essay = json!([block("essay", 120, json!([4, 5]), json!({}))]);
    assert_eq!(
        placed(&db, ana, essay.clone())["essay"],
        at(4, "16:00", 120)
    );
    save(&db, ana, json!({ "split_long_tasks": true }));
    let parts = placed(&db, ana, essay);
    assert_eq!(
        (&parts["essay"], &parts["essay~2"]),
        (&at(4, "16:00", 60), &at(5, "10:00", 60))
    );
    save(
        &db,
        ana,
        json!({ "split_long_tasks": false, "work_windows": [{ "days": [4], "start": "21:00", "end": "23:00" }],
                           "day_cutoff": "22:00" }),
    );
    let late = json!([block("hw", 60, json!([4]), json!({ "energy": "low" }))]);
    assert_eq!(placed(&db, ana, late.clone())["hw"], at(4, "21:00", 60));
    save(&db, ana, json!({ "day_cutoff": "21:00" }));
    let missed = solve(&db, ana, json!({ "blocks": late }));
    let unplaced: Vec<&str> = missed["unplaced"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert_eq!(unplaced, ["hw"]);
    save(
        &db,
        ana,
        json!({ "day_cutoff": null, "work_windows": [{ "days": [5], "start": "10:00", "end": "12:00" }],
                           "show_weekends": false }),
    );
    assert_eq!(
        placed(
            &db,
            ana,
            json!([block("math", 60, json!([5]), json!({ "energy": "high" }))])
        )["math"],
        at(5, "10:00", 60)
    );
    assert_eq!(
        read_preferences(&db.path, ana).unwrap()["show_weekends"],
        false
    );
}

#[test]
fn a_new_account_plans_with_a_15_minute_gap() {
    let db = TestDb::new("planner-default-gap");
    let ana = db.account("ana");
    // The answer leaves out the 15-minute default as it leaves out the other planner defaults.
    let body = read_preferences(&db.path, ana).unwrap();
    assert!(body.get("buffer_min").is_none_or(|gap| gap == 15));
    save(
        &db,
        ana,
        json!({ "work_windows": [{ "days": [4], "start": "16:00", "end": "20:00" }] }),
    );
    let homework = json!([
        block(
            "class",
            60,
            json!([4]),
            json!({ "kind": "locked", "start": "15:00" })
        ),
        block("hw", 60, json!([4]), json!({})),
    ]);
    assert_eq!(placed(&db, ana, homework)["hw"], at(4, "16:15", 60));
}

#[test]
fn choosing_no_gap_is_saved_and_kept() {
    let db = TestDb::new("planner-no-gap");
    let ana = db.account("ana");
    assert_eq!(save(&db, ana, json!({ "buffer_min": 0 }))["buffer_min"], 0);
    assert_eq!(read_preferences(&db.path, ana).unwrap()["buffer_min"], 0);
}

#[test]
fn a_spread_that_must_share_a_day_is_planned_and_says_so() {
    let db = TestDb::new("planner-spread-notice");
    let ana = db.account("ana");
    let essay = json!({ "id": "essay", "title": "History essay", "course": null, "category": null, "priority": 3,
                        "energy": "medium", "spotify_url": null, "due": "2026-09-11T21:00", "estimate_min": 90,
                        "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0 });
    save_homework(&db.path, ana, "essay", &essay).unwrap();
    save(
        &db,
        ana,
        json!({ "work_windows": [{ "days": [2], "start": "16:00", "end": "21:00" }] }),
    );
    let pieces = json!([
        block(
            "essay-a",
            60,
            json!([2]),
            json!({ "title": "History essay", "assignment_id": "essay" })
        ),
        block(
            "essay-b",
            30,
            json!([2]),
            json!({ "title": "History essay", "assignment_id": "essay" })
        ),
    ]);
    let trace = solve(
        &db,
        ana,
        json!({ "blocks": pieces, "week_start": "2026-09-07" }),
    );
    let notice = "Couldn't spread History essay over separate days, so two parts share Wednesday.";
    let notices = trace["notices"].as_array().cloned().unwrap_or_default();
    assert!(
        notices
            .iter()
            .any(|item| item["kind"] == "spread_same_day" && item["message"] == notice),
        "{notices:?}"
    );
}

#[test]
fn splitting_long_tasks_leaves_homework_saved_as_one_go_whole() {
    let db = TestDb::new("planner-split-one-go");
    let ana = db.account("ana");
    save(
        &db,
        ana,
        json!({ "split_long_tasks": true,
                           "work_windows": [{ "days": [4], "start": "16:00", "end": "20:00" },
                                            { "days": [5], "start": "10:00", "end": "12:00" }] }),
    );
    for (revision, spread, expected) in [
        (0, "one", vec![("hw1".to_string(), 120)]),
        (
            1,
            "spread",
            vec![("hw1".to_string(), 60), ("hw1~2".to_string(), 60)],
        ),
    ] {
        let body = json!({ "id": "hw", "title": "Essay", "course": null, "category": null, "priority": 2,
                           "energy": "medium", "spotify_url": null, "due": "2026-09-19T23:59", "estimate_min": 120,
                           "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
                           "revision": revision, "spread": spread });
        save_homework(&db.path, ana, "hw", &body).unwrap();
        let session = block("hw1", 120, json!([4, 5]), json!({ "assignment_id": "hw" }));
        let trace = solve(
            &db,
            ana,
            json!({ "blocks": [session], "week_start": "2026-09-14" }),
        );
        let mut flexible: Vec<(String, i64)> = trace["placed"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|item| item["kind"] == "flexible")
            .map(|item| {
                (
                    item["id"].as_str().unwrap().to_string(),
                    item["duration_min"].as_i64().unwrap(),
                )
            })
            .collect();
        flexible.sort();
        assert_eq!(flexible, expected, "{spread}");
    }
}
