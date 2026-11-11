//! The time step is 15 minutes for an account that never chose one: stored 5s move once, and a 5
//! chosen after that is kept.

mod common;

use common::scratch;
use flexweek_store::{initialize, insert_preferences, open_connection};
use rusqlite::params;
use serde_json::{Value, json};

const WEEK: &str = "2026-11-09";

fn user_with_comfort(path: &std::path::Path, version: i64, comfort: &str) -> i64 {
    initialize(path, WEEK).unwrap();
    let conn = open_connection(path).unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('ada', 'x')",
        [],
    )
    .unwrap();
    let user_id = conn.last_insert_rowid();
    insert_preferences(&conn, user_id, version).unwrap();
    conn.execute_batch("COMMIT").unwrap();
    set_comfort(path, user_id, comfort);
    user_id
}

fn set_comfort(path: &std::path::Path, user_id: i64, comfort: &str) {
    let conn = open_connection(path).unwrap();
    conn.execute(
        "UPDATE preferences SET comfort_json = ?1 WHERE user_id = ?2",
        params![comfort, user_id],
    )
    .unwrap();
}

fn comfort_and_version(path: &std::path::Path, user_id: i64) -> (String, i64) {
    let conn = open_connection(path).unwrap();
    conn.query_row(
        "SELECT comfort_json, prefs_version FROM preferences WHERE user_id = ?1",
        [user_id],
        |row| Ok((row.get(0)?, row.get(1)?)),
    )
    .unwrap()
}

fn comfort_of(path: &std::path::Path, user_id: i64) -> Value {
    serde_json::from_str(&comfort_and_version(path, user_id).0).unwrap()
}

#[test]
fn an_older_account_holding_five_reads_fifteen_after_opening_and_keeps_its_other_settings() {
    let path = scratch("step-old-five");
    let user_id = user_with_comfort(
        &path,
        4,
        r#"{"end_chime":true,"drag_step_min":5,"clock_24h":false}"#,
    );
    initialize(&path, WEEK).unwrap();
    assert_eq!(
        comfort_of(&path, user_id),
        json!({"end_chime": true, "drag_step_min": 15, "clock_24h": false})
    );
    assert_eq!(comfort_and_version(&path, user_id).1, 5);
}

#[test]
fn five_chosen_after_the_move_is_still_five_after_opening_twice_more() {
    let path = scratch("step-keep-five");
    let user_id = user_with_comfort(&path, 4, r#"{"drag_step_min":5}"#);
    initialize(&path, WEEK).unwrap();
    assert_eq!(comfort_of(&path, user_id)["drag_step_min"], json!(15));
    set_comfort(&path, user_id, r#"{"drag_step_min":5}"#);
    initialize(&path, WEEK).unwrap();
    initialize(&path, WEEK).unwrap();
    assert_eq!(comfort_of(&path, user_id)["drag_step_min"], json!(5));
}

#[test]
fn an_older_account_holding_fifteen_or_no_step_is_left_exactly_as_it_was() {
    for (name, comfort) in [
        (
            "step-old-fifteen",
            r#"{"drag_step_min":15,"end_chime":true}"#,
        ),
        ("step-old-missing", r#"{"end_chime":true}"#),
        ("step-old-empty", ""),
    ] {
        let path = scratch(name);
        let user_id = user_with_comfort(&path, 4, comfort);
        initialize(&path, WEEK).unwrap();
        assert_eq!(
            comfort_and_version(&path, user_id),
            (comfort.to_string(), 5),
            "{name}"
        );
    }
}

#[test]
fn an_account_made_after_the_move_keeps_a_five_it_holds() {
    let path = scratch("step-new-five");
    let user_id = user_with_comfort(&path, 5, r#"{"drag_step_min":5}"#);
    initialize(&path, WEEK).unwrap();
    assert_eq!(comfort_of(&path, user_id)["drag_step_min"], json!(5));
}
