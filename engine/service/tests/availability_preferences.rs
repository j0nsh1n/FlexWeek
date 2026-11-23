//! Availability preferences (Settings > Study hours, protected time and the end of the day): they stay on
//! the 15-minute grid, keep their saved shape, and Plan honours them. Old builds' separate "preferred study
//! hours" open as study hours. The Rust twins of backend/tests/test_availability_preferences_api.py.

use flexweek_service::homework_saves::{save_homework, spread_preview};
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{check_preferences, read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn with(prefs: &Value, changes: Value) -> Value {
    let mut prefs = prefs.clone();
    for (key, value) in changes.as_object().unwrap() {
        prefs[key] = value.clone();
    }
    prefs
}

fn refused(result: Result<Value, ServiceError>) -> bool {
    matches!(result, Err(ServiceError::Refused(Refusal::Invalid(_))))
}

fn solve(db: &TestDb, user: i64, blocks: Value) -> Value {
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    plan(&db.path, user, &json!({ "blocks": blocks }), &start_clock).unwrap()
}

fn placed_start(trace: &Value, id: &str) -> Value {
    trace["placed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == id)
        .unwrap()["start"]
        .clone()
}

fn homework_block(days: Value, energy: &str) -> Value {
    json!({ "id": "hw", "title": "Homework", "kind": "flexible", "duration_min": 60, "days": days, "priority": 3,
            "energy": energy })
}

fn availability(db: &TestDb, set: Option<&Value>) -> Option<String> {
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    if let Some(value) = set {
        conn.execute(
            "UPDATE preferences SET availability_json = ?1",
            [value.to_string()],
        )
        .unwrap();
        return None;
    }
    Some(
        conn.query_row("SELECT availability_json FROM preferences", [], |row| {
            row.get(0)
        })
        .unwrap(),
    )
}

#[test]
fn time_off_the_grid_is_refused_and_plan_keeps_to_the_end_of_the_day() {
    let db = TestDb::new("avail-cutoff");
    let ana = db.account("ana");
    let prefs = read_preferences(&db.path, ana).unwrap();
    let off_grid = json!({ "protected": [{ "kind": "downtime", "days": [0], "start": "06:07", "duration_min": 60 }] });
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(&prefs, off_grid)
    )));
    let saved = write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "day_cutoff": "06:15" })),
    )
    .unwrap();
    assert_eq!(saved["day_cutoff"], "06:15");
    assert_eq!(
        read_preferences(&db.path, ana).unwrap()["day_cutoff"],
        "06:15"
    );
    let trace = solve(&db, ana, json!([homework_block(json!([0]), "high")]));
    let hw = trace["placed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == "hw")
        .unwrap();
    let start: Vec<i64> = hw["start"]
        .as_str()
        .unwrap()
        .split(':')
        .map(|p| p.parse().unwrap())
        .collect();
    assert!(
        start[0] * 60 + start[1] + hw["duration_min"].as_i64().unwrap() <= 6 * 60 + 15,
        "{hw}"
    );
}

/// Blocks take any minute; what the planner works in does not. Each of these is one or five minutes off a
/// quarter hour, and each is refused.
#[test]
fn estimates_and_the_planners_hours_stay_on_the_quarter_hour() {
    let db = TestDb::new("avail-quarter");
    let ana = db.account("ana");
    let essay = |estimate: i64| json!({ "id": "hw-essay", "title": "Essay", "due": "2026-09-15T23:59", "estimate_min": estimate, "revision": 0 });
    assert!(refused(save_homework(
        &db.path,
        ana,
        "hw-essay",
        &essay(50)
    )));
    let prefs = read_preferences(&db.path, ana).unwrap();
    for change in [
        json!({ "work_windows": [{ "days": [0], "start": "17:05", "end": "19:00" }] }),
        json!({ "work_windows": [{ "days": [0], "start": "17:00", "end": "19:10" }] }),
        json!({ "study_windows": [{ "days": [0], "start": "17:05", "duration_min": 60 }] }),
        json!({ "study_windows": [{ "days": [0], "start": "17:00", "duration_min": 50 }] }),
        json!({ "protected": [{ "kind": "meal", "days": [0], "start": "18:05", "duration_min": 30 }] }),
        json!({ "day_cutoff": "21:05" }),
        json!({ "auto_split_pomodoro": true, "timer_work_min": 25 }),
    ] {
        assert!(
            refused(write_preferences(
                &db.path,
                ana,
                &with(&prefs, change.clone())
            )),
            "{change}"
        );
    }
    save_homework(&db.path, ana, "hw-essay", &essay(120)).unwrap();
    let spread = spread_preview(
        &db.path,
        ana,
        "hw-essay",
        &json!({ "session_min": 50, "from_date": "2026-09-14" }),
    );
    assert!(refused(spread));
}

/// A preferences row from an older build, with planning hours and preferred study hours apart, opens as one
/// Study hours list, Plan reads that list, and the next save writes it alone.
#[test]
fn preferred_study_hours_saved_by_an_older_build_open_as_study_hours() {
    let db = TestDb::new("avail-old-build");
    let ana = db.account("ana");
    availability(
        &db,
        Some(&json!({
            "work_windows": [{ "days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00" }],
            "study_windows": [{ "days": [5, 6], "start": "10:00", "duration_min": 120 }],
        })),
    );
    let prefs = read_preferences(&db.path, ana).unwrap();
    assert!(prefs.get("study_windows").is_none());
    let hours = json!([{ "days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00" },
                       { "days": [5, 6], "start": "10:00", "end": "12:00" }]);
    assert_eq!(prefs["work_windows"], hours);
    // Saturday has no other hours, so homework there goes in the carried hours or nowhere.
    assert_eq!(
        placed_start(
            &solve(&db, ana, json!([homework_block(json!([5]), "low")])),
            "hw"
        ),
        "10:00"
    );
    write_preferences(&db.path, ana, &prefs).unwrap();
    let stored: Value = serde_json::from_str(&availability(&db, None).unwrap()).unwrap();
    assert_eq!(stored["work_windows"], hours);
    assert!(stored.get("study_windows").is_none());
}

#[test]
fn an_older_app_sending_preferred_study_hours_saves_them_as_study_hours() {
    let db = TestDb::new("avail-old-app");
    let ana = db.account("ana");
    let prefs = read_preferences(&db.path, ana).unwrap();
    let preferred =
        json!([{ "days": [2], "start": "19:00", "duration_min": 90, "subject": "Math" }]);
    let saved = write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "study_windows": preferred })),
    )
    .unwrap();
    assert!(saved.get("study_windows").is_none());
    assert_eq!(
        saved["work_windows"],
        json!([{ "days": [2], "start": "19:00", "end": "20:30", "subject": "Math" }])
    );
    assert_eq!(
        read_preferences(&db.path, ana).unwrap()["work_windows"],
        saved["work_windows"]
    );
}

#[test]
fn protected_time_keeps_an_optional_name() {
    let db = TestDb::new("avail-protected-name");
    let ana = db.account("ana");
    let prefs = read_preferences(&db.path, ana).unwrap();
    let piano = json!({ "kind": "downtime", "days": [1, 3], "start": "17:00", "duration_min": 90 });
    let named = with(&piano, json!({ "title": "  Piano " }));
    let blank = with(&piano, json!({ "days": [5], "title": " " }));
    let saved = write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "protected": [named, blank] })),
    )
    .unwrap();
    assert_eq!(saved["protected"][0]["title"], "Piano", "trimmed");
    assert!(
        saved["protected"][1].get("title").is_none(),
        "a blank name is no name"
    );
    assert_eq!(
        read_preferences(&db.path, ana).unwrap()["protected"],
        saved["protected"]
    );
    let too_long = with(&piano, json!({ "title": "x".repeat(41) }));
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "protected": [too_long] }))
    )));
    // A row saved before names existed still opens, without one.
    availability(&db, Some(&json!({ "protected": [piano] })));
    assert_eq!(
        read_preferences(&db.path, ana).unwrap()["protected"],
        json!([piano])
    );
}

#[test]
fn protected_times_may_touch_but_not_overlap_on_the_same_day() {
    let db = TestDb::new("avail-protected-overlap");
    let ana = db.account("ana");
    let prefs = read_preferences(&db.path, ana).unwrap();
    let window = |kind: &str, day: i64, start: &str, minutes: i64| json!({ "kind": kind, "days": [day], "start": start, "duration_min": minutes });
    let overlapping = json!([
        window("downtime", 0, "18:00", 60),
        window("meal", 0, "18:30", 60)
    ]);
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "protected": overlapping }))
    )));
    let touching = json!([
        window("downtime", 0, "18:00", 60),
        window("meal", 0, "19:00", 60)
    ]);
    write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "protected": touching })),
    )
    .unwrap();
    let other_day = json!([
        window("downtime", 0, "18:00", 120),
        window("meal", 1, "19:00", 60)
    ]);
    write_preferences(
        &db.path,
        ana,
        &with(&prefs, json!({ "protected": other_day })),
    )
    .unwrap();
}

#[test]
fn the_preferences_check_refuses_overlapping_protected_time_and_takes_touching() {
    let overlapping = json!({ "theme": "system", "protected": [
        { "kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60 },
        { "kind": "meal", "days": [0], "start": "18:30", "duration_min": 60 },
    ] });
    assert!(check_preferences(&overlapping).is_err());
    let touching = json!({ "theme": "system", "protected": [
        { "kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60 },
        { "kind": "meal", "days": [0], "start": "19:00", "duration_min": 60 },
    ] });
    assert_eq!(
        check_preferences(&touching).unwrap()["protected"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
}

#[test]
fn a_study_hours_subject_must_be_a_real_name() {
    for subject in ["   ".to_string(), "x".repeat(41)] {
        let given = json!({ "theme": "system",
                            "study_windows": [{ "days": [0], "start": "15:30", "duration_min": 60, "subject": subject }] });
        assert!(check_preferences(&given).is_err(), "{subject:?}");
    }
}
