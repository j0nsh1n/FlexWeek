//! Day, Month and the homework list against `GET /api/day`, `/api/month` and `/api/assignments` on the
//! same Python-seeded database as the week test (fixtures/make_week_scenarios.py, removed with backend/app.py in P2): every day of
//! November 2026, the month from each of the seven first days, and the homework list for every week
//! start with and without finished homework, the routines and the restore points, all at the fixtures'
//! clock (Thursday 5 Nov, 19:00).

use std::path::PathBuf;

use chrono::NaiveDate;
use flexweek_service::views::{day, homework, month, restore_points, routines};
use serde_json::Value;

fn setup(name: &str) -> (Value, PathBuf, PathBuf) {
    let fixture: Value = serde_json::from_str(include_str!("fixtures/week_parity.json")).unwrap();
    let dir = std::env::temp_dir().join(format!(
        "flexweek-view-parity-{name}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("views.db");
    rusqlite::Connection::open(&path)
        .unwrap()
        .execute_batch(fixture["sql"].as_str().unwrap())
        .unwrap();
    (fixture, dir, path)
}

fn now(fixture: &Value) -> (NaiveDate, i64) {
    let (day, clock) = fixture["views"]["now"]
        .as_str()
        .unwrap()
        .split_once('T')
        .unwrap();
    let (hour, minute) = clock.split_once(':').unwrap();
    (
        day.parse().unwrap(),
        hour.parse::<i64>().unwrap() * 60 + minute.parse::<i64>().unwrap(),
    )
}

fn same(got: &Value, expected: &Value) -> bool {
    serde_json::to_string(got).unwrap() == serde_json::to_string(expected).unwrap()
}

#[test]
fn every_day_month_and_homework_list_reads_as_python_answered_it() {
    let (fixture, dir, path) = setup("all");
    let views = &fixture["views"];
    let user = views["user_id"].as_i64().unwrap();
    let at = now(&fixture);
    let mut wrong = Vec::new();
    for case in views["day"].as_array().unwrap() {
        let date = case["date"].as_str().unwrap();
        match day(&path, user, date, at) {
            Ok(got) if same(&got, &case["answer"]) => {}
            got => wrong.push(format!(
                "day {date}\n  python: {}\n  rust:   {got:?}",
                case["answer"]
            )),
        }
    }
    for case in views["month"].as_array().unwrap() {
        let first = case["first_day"].as_u64().unwrap() as u32;
        match month(&path, user, case["month"].as_str().unwrap(), first, at) {
            Ok(got) if same(&got, &case["answer"]) => {}
            got => wrong.push(format!(
                "month from {first}\n  python: {}\n  rust:   {got:?}",
                case["answer"]
            )),
        }
    }
    for case in views["homework"].as_array().unwrap() {
        let start = case["week_start"].as_str().unwrap();
        let all = case["include_completed"].as_bool().unwrap();
        match homework(&path, user, start, all, at) {
            Ok(got) if same(&got, &case["answer"]) => {}
            got => wrong.push(format!(
                "homework {start} {all}\n  python: {}\n  rust:   {got:?}",
                case["answer"]
            )),
        }
    }
    for (name, got) in [
        ("routines", routines(&path, user)),
        ("restore_points", restore_points(&path, user)),
    ] {
        match got {
            Ok(got) if same(&got, &views[name]) => {}
            got => wrong.push(format!(
                "{name}\n  python: {}\n  rust:   {got:?}",
                views[name]
            )),
        }
    }
    let _ = std::fs::remove_dir_all(&dir);
    assert!(
        wrong.is_empty(),
        "{} answers differ:\n{}",
        wrong.len(),
        wrong.iter().take(6).cloned().collect::<Vec<_>>().join("\n")
    );
}
