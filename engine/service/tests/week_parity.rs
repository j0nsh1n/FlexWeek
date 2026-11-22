//! The Rust week reader against `GET /api/week` and `GET /api/weeks`, the routes it replaces: accounts
//! seeded through the Python app (fixtures/make_week_scenarios.py), the database as SQL text, and the
//! answers Python gave for four Mondays, nineteen weeks shown from other weekdays and a refused date.

use std::path::PathBuf;

use flexweek_service::weeks::{WEEK_START_RULE, list_weeks, read_week};
use flexweek_service::{Refusal, ServiceError};
use serde_json::Value;

fn database(fixture: &Value, name: &str) -> (PathBuf, PathBuf) {
    let dir = std::env::temp_dir().join(format!(
        "flexweek-week-parity-{name}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("weeks.db");
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(fixture["sql"].as_str().unwrap())
        .unwrap();
    (dir, path)
}

fn fixture() -> Value {
    serde_json::from_str(include_str!("fixtures/week_parity.json")).unwrap()
}

#[test]
fn every_week_reads_as_python_answered_it() {
    let fixture = fixture();
    let (dir, path) = database(&fixture, "weeks");
    let mut wrong = Vec::new();
    for case in fixture["cases"].as_array().unwrap() {
        let user = case["user_id"].as_i64().unwrap();
        let start = case["week_start"].as_str().unwrap();
        let got = read_week(&path, user, start);
        let same = match (&got, case.get("answer")) {
            (Ok(answer), Some(expected)) => {
                serde_json::to_string(answer).unwrap() == serde_json::to_string(expected).unwrap()
            }
            (Err(ServiceError::Refused(Refusal::Invalid(words))), None) => {
                case["status"] == 422
                    && words == WEEK_START_RULE
                    && case["detail"] == WEEK_START_RULE
            }
            _ => false,
        };
        if !same {
            wrong.push(format!(
                "{start}\n  python: {}\n  rust:   {got:?}",
                case.get("answer").unwrap_or(&case["detail"])
            ));
        }
    }
    let _ = std::fs::remove_dir_all(&dir);
    assert!(
        wrong.is_empty(),
        "{} weeks differ:\n{}",
        wrong.len(),
        wrong.join("\n")
    );
}

#[test]
fn the_week_list_matches_and_another_accounts_weeks_stay_apart() {
    let fixture = fixture();
    let (dir, path) = database(&fixture, "list");
    let user = fixture["weeks"]["user_id"].as_i64().unwrap();
    assert_eq!(list_weeks(&path, user).unwrap(), fixture["weeks"]["answer"]);
    let bob = fixture["bob_id"].as_i64().unwrap();
    let theirs = read_week(&path, bob, "2026-11-09").unwrap();
    let ids: Vec<&str> = theirs["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert_eq!(
        ids,
        ["bob-only"],
        "one account's week shows another's blocks"
    );
    let _ = std::fs::remove_dir_all(&dir);
}
