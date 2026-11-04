//! The planner gap is 15 minutes for new rows and for stored 0s, once.

mod common;

use common::scratch;
use flexweek_store::{
    initialize, insert_preferences, open_connection, preference_row, write_preferences,
};
use rusqlite::{Connection, params};
use serde_json::{Value, json};

const WEEK: &str = "2026-09-14";

fn user_with_prefs(path: &std::path::Path, version: i64) -> i64 {
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
    user_id
}

fn buffer_and_chosen(path: &std::path::Path, user_id: i64) -> (i64, i64) {
    let conn = open_connection(path).unwrap();
    conn.query_row(
        "SELECT buffer_min, planner_settings_chosen FROM preferences WHERE user_id = ?1",
        [user_id],
        |row| Ok((row.get(0)?, row.get(1)?)),
    )
    .unwrap()
}

fn save_buffer(conn: &Connection, user_id: i64, buffer_min: i64) {
    let raw = preference_row(conn, user_id).unwrap().unwrap();
    let mut fields: Value = serde_json::from_str(&raw).unwrap();
    fields["buffer_min"] = json!(buffer_min);
    write_preferences(conn, user_id, &fields.to_string()).unwrap();
    conn.execute_batch("COMMIT").unwrap();
}

#[test]
fn a_new_database_gives_a_fifteen_minute_buffer() {
    let path = scratch("buffer-new");
    let user_id = user_with_prefs(&path, 4);
    assert_eq!(buffer_and_chosen(&path, user_id), (15, 0));
    let conn = open_connection(&path).unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('bea', 'x')",
        [],
    )
    .unwrap();
    let bea = conn.last_insert_rowid();
    conn.execute("INSERT INTO preferences(user_id) VALUES (?1)", [bea])
        .unwrap();
    let column_default: i64 = conn
        .query_row(
            "SELECT buffer_min FROM preferences WHERE user_id = ?1",
            [bea],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(column_default, 15);
}

#[test]
fn an_old_row_at_zero_reads_fifteen_after_opening() {
    let path = scratch("buffer-old-zero");
    let user_id = user_with_prefs(&path, 3);
    {
        let conn = open_connection(&path).unwrap();
        conn.execute(
            "UPDATE preferences SET buffer_min = 0, prefs_version = 3 WHERE user_id = ?1",
            [user_id],
        )
        .unwrap();
    }
    initialize(&path, WEEK).unwrap();
    assert_eq!(buffer_and_chosen(&path, user_id), (15, 0));
}

#[test]
fn saving_none_then_reopening_twice_still_reads_none() {
    let path = scratch("buffer-keep-none");
    let user_id = user_with_prefs(&path, 3);
    {
        let conn = open_connection(&path).unwrap();
        conn.execute(
            "UPDATE preferences SET buffer_min = 0, prefs_version = 3 WHERE user_id = ?1",
            [user_id],
        )
        .unwrap();
    }
    initialize(&path, WEEK).unwrap();
    assert_eq!(buffer_and_chosen(&path, user_id).0, 15);
    {
        let conn = open_connection(&path).unwrap();
        save_buffer(&conn, user_id, 0);
    }
    initialize(&path, WEEK).unwrap();
    initialize(&path, WEEK).unwrap();
    assert_eq!(buffer_and_chosen(&path, user_id).0, 0);
}

#[test]
fn the_zero_to_fifteen_move_is_not_a_settings_save() {
    let path = scratch("buffer-no-sync-edit");
    let user_id = user_with_prefs(&path, 3);
    {
        let conn = open_connection(&path).unwrap();
        conn.execute(
            "UPDATE preferences SET buffer_min = 0, prefs_version = 3, planner_settings_chosen = 0
             WHERE user_id = ?1",
            params![user_id],
        )
        .unwrap();
    }
    initialize(&path, WEEK).unwrap();
    let (buffer, chosen) = buffer_and_chosen(&path, user_id);
    assert_eq!(buffer, 15);
    assert_eq!(chosen, 0);
}
