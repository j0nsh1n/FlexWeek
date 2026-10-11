//! Regression (no fix-specs item; Sammy's finding 6): a block's key is (user, week_start, id).
//!
//! In 0.18.4 a week is one row of `weeks` holding its blocks as a JSON list, so the key is split:
//! the row's primary key covers (user_id, week_start) and the id must be unique inside the list.
//! Python's `WeekRequest` checks the list (see `backend/tests/test_regress_extra_block_keys.py`); these
//! tests check what the store itself guarantees.
//!
//! Run: `cargo test -p flexweek-store --test test_regress_extra_block_keys` from `engine/`;
//! known failures: add `-- --include-ignored`.

mod common;

use common::scratch;
use flexweek_store::{WeekSave, initialize, insert_user, open_connection, read_week, save_week};
use rusqlite::Connection;

const WEEK: &str = "2026-10-05";
const NEXT: &str = "2026-10-12";

fn db(name: &str) -> (Connection, i64, i64) {
    let path = scratch(name);
    initialize(&path, WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    let ann = insert_user(&conn, "ann", "scrypt$x").unwrap();
    let ben = insert_user(&conn, "ben", "scrypt$x").unwrap();
    conn.execute("COMMIT", []).unwrap();
    (conn, ann, ben)
}

fn commit(conn: &Connection) {
    if !conn.is_autocommit() {
        conn.execute("COMMIT", []).unwrap();
    }
}

fn block(id: &str, title: &str) -> String {
    format!(
        r#"{{"days":[0],"duration_min":60,"id":"{id}","kind":"locked","start":"08:00","title":"{title}"}}"#
    )
}

#[test]
fn weeks_primary_key_is_user_and_week_start() {
    let (conn, _, _) = db("keys-pk");
    let mut stmt = conn.prepare("PRAGMA table_info(weeks)").unwrap();
    let mut pk: Vec<(i64, String)> = stmt
        .query_map([], |row| {
            Ok((row.get::<_, i64>(5)?, row.get::<_, String>(1)?))
        })
        .unwrap()
        .map(Result::unwrap)
        .filter(|(order, _)| *order > 0)
        .collect();
    pk.sort();
    let names: Vec<&str> = pk.iter().map(|(_, n)| n.as_str()).collect();
    assert_eq!(names, ["user_id", "week_start"]);
}

#[test]
fn a_raw_duplicate_week_row_is_rejected_by_the_constraint() {
    let (conn, ann, _) = db("keys-raw-dup");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[]', 1)",
        rusqlite::params![ann, WEEK],
    )
    .unwrap();
    let again = conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[]', 1)",
        rusqlite::params![ann, WEEK],
    );
    let err = again.expect_err("a second row for the same (user, week_start) must be refused");
    assert!(err.to_string().contains("UNIQUE"), "{err}");
}

#[test]
fn saving_the_same_week_again_upserts_one_row() {
    let (conn, ann, _) = db("keys-upsert");
    let one = format!("[{}]", block("school", "School"));
    let two = format!("[{}]", block("school", "School 9-3"));
    assert_eq!(
        save_week(&conn, ann, WEEK, &one, 0).unwrap(),
        WeekSave::Ready(1)
    );
    commit(&conn);
    assert_eq!(
        save_week(&conn, ann, WEEK, &two, 1).unwrap(),
        WeekSave::Ready(2)
    );
    commit(&conn);
    let rows: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            rusqlite::params![ann, WEEK],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(rows, 1);
    assert_eq!(read_week(&conn, ann, WEEK).unwrap(), Some((two, 2)));
}

#[test]
fn the_same_block_id_may_repeat_across_weeks_and_users() {
    let (conn, ann, ben) = db("keys-repeat");
    let school = format!("[{}]", block("school", "School"));
    for (user, week) in [(ann, WEEK), (ann, NEXT), (ben, WEEK)] {
        assert_eq!(
            save_week(&conn, user, week, &school, 0).unwrap(),
            WeekSave::Ready(1)
        );
        commit(&conn);
    }
    for (user, week) in [(ann, WEEK), (ann, NEXT), (ben, WEEK)] {
        assert_eq!(
            read_week(&conn, user, week).unwrap(),
            Some((school.clone(), 1))
        );
    }
}

#[test]
#[ignore = "known failure (no fix-specs item; Sammy's finding 6): store::save_week writes a block list that repeats an id; only Python's WeekRequest refuses it"]
fn the_store_refuses_a_week_that_repeats_a_block_id() {
    let (conn, ann, _) = db("keys-dup-id");
    let doubled = format!(
        "[{},{}]",
        block("school", "School"),
        block("school", "School again")
    );
    let saved = save_week(&conn, ann, WEEK, &doubled, 0);
    commit(&conn);
    let stored = read_week(&conn, ann, WEEK).unwrap();
    assert!(
        saved.is_err() && stored.is_none(),
        "store kept a week with two blocks keyed (ann, {WEEK}, school): {stored:?}"
    );
}
