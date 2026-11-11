//! The standing week in the store (fix-specs item 1): the upgrade from a 0.18 database, the read
//! rule, changing it for this week and every later week, and carrying it in an export.

mod common;

use common::scratch;
use flexweek_store::{
    create_restore_point, delete_account, initialize, insert_preferences, open_connection,
    replace_standing, restore_point_body, set_standing, standing_blocks, standing_rows,
    week_with_standing,
};
use rusqlite::{Connection, params};
use serde_json::{Value, json};

const SETUP_WEEK: &str = "2026-10-05";
const WEEK_BEFORE: &str = "2026-09-28";
const NEXT_WEEK: &str = "2026-10-12";
const WEEK_AFTER: &str = "2026-10-19";

fn school() -> Value {
    json!({"category": "class", "days": [0, 1, 2, 3, 4], "duration_min": 405, "id": "school",
           "kind": "locked", "start": "08:30", "title": "School"})
}

fn soccer() -> Value {
    json!({"category": "extra", "days": [1, 3], "duration_min": 90, "id": "activity-1",
           "kind": "locked", "start": "16:00", "title": "Soccer"})
}

fn gym() -> Value {
    json!({"days": [2], "duration_min": 60, "id": "gym", "kind": "locked", "start": "18:00",
           "title": "Gym"})
}

fn text(value: &Value) -> String {
    serde_json::to_string(value).unwrap()
}

fn add_week(conn: &Connection, user_id: i64, week_start: &str, blocks: &Value) {
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)",
        params![user_id, week_start, text(blocks)],
    )
    .unwrap();
}

fn week_row(conn: &Connection, user_id: i64, week_start: &str) -> (Value, i64) {
    let (blocks, revision): (String, i64) = conn
        .query_row(
            "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    (serde_json::from_str(&blocks).unwrap(), revision)
}

fn seen(conn: &Connection, user_id: i64, week_start: &str) -> Vec<Value> {
    let stored: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| row.get(0),
        )
        .unwrap_or_else(|_| "[]".to_string());
    let merged = week_with_standing(conn, user_id, week_start, &stored).unwrap();
    serde_json::from_str::<Vec<Value>>(&merged).unwrap()
}

fn ids(blocks: &[Value]) -> Vec<String> {
    blocks
        .iter()
        .map(|b| b["id"].as_str().unwrap().to_string())
        .collect()
}

/// A database as 0.18.5 left it: no standing table, every account at preferences version 2.
fn as_left_by_0_18(name: &str) -> (std::path::PathBuf, i64) {
    let path = scratch(name);
    initialize(&path, SETUP_WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    conn.execute_batch("DROP TABLE standing_blocks").unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('ada', 'x')",
        [],
    )
    .unwrap();
    let user_id = conn.last_insert_rowid();
    insert_preferences(&conn, user_id, 2).unwrap();
    conn.execute_batch("COMMIT").unwrap();
    let mut missed_monday = school();
    missed_monday["missed_days"] = json!([0]);
    add_week(&conn, user_id, WEEK_BEFORE, &json!([gym()]));
    add_week(
        &conn,
        user_id,
        SETUP_WEEK,
        &json!([missed_monday, soccer(), gym()]),
    );
    (path, user_id)
}

fn fresh_account(name: &str) -> (Connection, i64) {
    let path = scratch(name);
    initialize(&path, SETUP_WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('ada', 'x')",
        [],
    )
    .unwrap();
    let user_id = conn.last_insert_rowid();
    insert_preferences(&conn, user_id, 3).unwrap();
    conn.execute_batch("COMMIT").unwrap();
    (conn, user_id)
}

#[test]
fn the_upgrade_builds_the_standing_week_from_the_week_setup_ran_in() {
    let (path, user_id) = as_left_by_0_18("standing-upgrade");
    initialize(&path, NEXT_WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    assert_eq!(
        standing_blocks(&conn, user_id, NEXT_WEEK).unwrap(),
        vec![school(), soccer()]
    );
    assert_eq!(
        ids(&seen(&conn, user_id, "2026-11-02")),
        vec!["school", "activity-1"]
    );
    // The week before Setup is left alone, and Setup's week keeps its own missed Monday.
    assert_eq!(ids(&seen(&conn, user_id, WEEK_BEFORE)), vec!["gym"]);
    let (setup_week, revision) = week_row(&conn, user_id, SETUP_WEEK);
    assert_eq!(setup_week[0]["missed_days"], json!([0]));
    assert_eq!(revision, 1);
    let version: i64 = conn
        .query_row(
            "SELECT prefs_version FROM preferences WHERE user_id = ?1",
            [user_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(version, 4);
}

#[test]
fn the_upgrade_runs_once_so_a_standing_week_emptied_later_stays_empty() {
    let (path, user_id) = as_left_by_0_18("standing-once");
    initialize(&path, NEXT_WEEK).unwrap();
    {
        let conn = open_connection(&path).unwrap();
        set_standing(
            &conn,
            user_id,
            NEXT_WEEK,
            &text(&json!([
                {"id": "school", "stop": true},
                {"id": "activity-1", "stop": true}
            ])),
        )
        .unwrap();
        conn.execute_batch("COMMIT").unwrap();
    }
    initialize(&path, NEXT_WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    assert_eq!(
        standing_blocks(&conn, user_id, WEEK_AFTER).unwrap(),
        Vec::<Value>::new()
    );
    // The weeks before the change still have what stood then.
    assert_eq!(
        standing_blocks(&conn, user_id, SETUP_WEEK).unwrap(),
        vec![school(), soccer()]
    );
}

#[test]
fn a_change_reaches_this_week_on_and_leaves_earlier_weeks_as_they_were() {
    let (conn, user_id) = fresh_account("standing-change");
    set_standing(
        &conn,
        user_id,
        SETUP_WEEK,
        &text(&json!([school(), soccer()])),
    )
    .unwrap();
    let mut missed_wednesday = school();
    missed_wednesday["missed_days"] = json!([2, 4]);
    add_week(
        &conn,
        user_id,
        WEEK_AFTER,
        &json!([missed_wednesday, gym()]),
    );

    let mut later = school();
    later["start"] = json!("09:00");
    later["duration_min"] = json!(360);
    later["days"] = json!([0, 1, 2, 3]);
    let changed = set_standing(&conn, user_id, NEXT_WEEK, &text(&json!([later.clone()]))).unwrap();
    assert_eq!(changed, vec![WEEK_AFTER.to_string()]);

    // An unsaved week before the change keeps the old School and Soccer.
    assert_eq!(seen(&conn, user_id, SETUP_WEEK), vec![school(), soccer()]);
    assert_eq!(
        seen(&conn, user_id, NEXT_WEEK),
        vec![later.clone(), soccer()]
    );
    // The saved later week: new times, Wednesday still missed, Friday no longer a school day.
    let (after, revision) = week_row(&conn, user_id, WEEK_AFTER);
    let mut expected = later;
    expected["missed_days"] = json!([2]);
    assert_eq!(after, json!([expected, gym()]));
    assert_eq!(revision, 2);
}

#[test]
fn every_week_removes_a_block_from_saved_later_weeks_too() {
    let (conn, user_id) = fresh_account("standing-remove");
    set_standing(
        &conn,
        user_id,
        SETUP_WEEK,
        &text(&json!([school(), soccer()])),
    )
    .unwrap();
    add_week(
        &conn,
        user_id,
        WEEK_AFTER,
        &json!([school(), soccer(), gym()]),
    );
    set_standing(
        &conn,
        user_id,
        NEXT_WEEK,
        &text(&json!([{"id": "activity-1", "stop": true}])),
    )
    .unwrap();
    assert_eq!(
        ids(&seen(&conn, user_id, WEEK_AFTER)),
        vec!["school", "gym"]
    );
    assert_eq!(
        ids(&seen(&conn, user_id, SETUP_WEEK)),
        vec!["school", "activity-1"]
    );
}

#[test]
fn a_change_for_an_earlier_week_replaces_a_later_change() {
    let (conn, user_id) = fresh_account("standing-replace");
    set_standing(&conn, user_id, SETUP_WEEK, &text(&json!([school()]))).unwrap();
    let mut later = school();
    later["start"] = json!("09:00");
    set_standing(&conn, user_id, WEEK_AFTER, &text(&json!([later]))).unwrap();
    let mut earlier = school();
    earlier["start"] = json!("08:00");
    set_standing(&conn, user_id, NEXT_WEEK, &text(&json!([earlier.clone()]))).unwrap();
    assert_eq!(
        standing_blocks(&conn, user_id, "2026-11-30").unwrap(),
        vec![earlier]
    );
}

#[test]
fn rows_carry_over_to_another_account_and_go_with_the_account() {
    let (conn, user_id) = fresh_account("standing-export");
    set_standing(
        &conn,
        user_id,
        SETUP_WEEK,
        &text(&json!([school(), soccer()])),
    )
    .unwrap();
    set_standing(
        &conn,
        user_id,
        WEEK_AFTER,
        &text(&json!([{"id": "activity-1", "stop": true}])),
    )
    .unwrap();
    let rows = standing_rows(&conn, user_id).unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('bea', 'x')",
        [],
    )
    .unwrap();
    let other = conn.last_insert_rowid();
    replace_standing(&conn, other, &rows).unwrap();
    assert_eq!(standing_rows(&conn, other).unwrap(), rows);
    assert_eq!(
        standing_blocks(&conn, other, NEXT_WEEK).unwrap(),
        vec![school(), soccer()]
    );
    assert_eq!(
        standing_blocks(&conn, other, WEEK_AFTER).unwrap(),
        vec![school()]
    );

    delete_account(&conn, user_id).unwrap();
    assert_eq!(standing_rows(&conn, user_id).unwrap(), "[]");
}

#[test]
fn a_restore_point_holds_the_standing_rows_it_was_made_with() {
    let (conn, user_id) = fresh_account("standing-restore-point");
    set_standing(
        &conn,
        user_id,
        SETUP_WEEK,
        &text(&json!([school(), soccer()])),
    )
    .unwrap();
    set_standing(
        &conn,
        user_id,
        WEEK_AFTER,
        &text(&json!([{"id": "activity-1", "stop": true}])),
    )
    .unwrap();
    let rows: Value = serde_json::from_str(&standing_rows(&conn, user_id).unwrap()).unwrap();
    create_restore_point(&conn, user_id, "abc", "Before", "2026-10-10T09:00", &[], 10).unwrap();
    set_standing(&conn, user_id, NEXT_WEEK, &text(&json!([gym()]))).unwrap();
    let (_, body) = restore_point_body(&conn, user_id, "rp-abc")
        .unwrap()
        .unwrap();
    let body: Value = serde_json::from_str(&body).unwrap();
    assert_eq!(body["standing"], rows);
    assert_eq!(rows.as_array().map(Vec::len), Some(3));
}

// Dec 2026: Mon 30 Nov, Mon 7 Dec, Tue 8 Dec, Wed 9 Dec, Thu 10 Dec, Sat 12 Dec, Mon 14 Dec.
const FIRST_WEEK: &str = "2026-11-30";
const DEC_7: &str = "2026-12-07";
const DEC_14: &str = "2026-12-14";

fn piano(until: Option<&str>) -> Value {
    let mut block = json!({"category": "extra", "days": [1, 3], "duration_min": 60,
                           "id": "weekly-piano", "kind": "locked", "start": "16:00",
                           "title": "Piano"});
    if let Some(until) = until {
        block["until"] = json!(until);
    }
    block
}

fn days_in(conn: &Connection, user_id: i64, week_start: &str) -> Option<Value> {
    seen(conn, user_id, week_start)
        .into_iter()
        .find(|block| block["id"] == "weekly-piano")
        .map(|block| block["days"].clone())
}

#[test]
fn a_weekly_block_shows_from_its_week_on_and_not_before() {
    let (conn, user_id) = fresh_account("weekly-from");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    assert_eq!(days_in(&conn, user_id, "2026-11-23"), None);
    for week in [FIRST_WEEK, DEC_7, DEC_14, "2026-12-28"] {
        assert_eq!(days_in(&conn, user_id, week), Some(json!([1, 3])), "{week}");
    }
}

#[test]
fn until_cuts_the_weeks_a_student_never_opened() {
    let (conn, user_id) = fresh_account("weekly-until-unsaved");
    set_standing(
        &conn,
        user_id,
        FIRST_WEEK,
        &text(&json!([piano(Some("2026-12-09"))])),
    )
    .unwrap();
    assert_eq!(days_in(&conn, user_id, FIRST_WEEK), Some(json!([1, 3])));
    assert_eq!(days_in(&conn, user_id, DEC_7), Some(json!([1])));
    assert_eq!(days_in(&conn, user_id, DEC_14), None);
}

#[test]
fn until_also_cuts_saved_later_weeks_that_hold_their_own_copy() {
    let (conn, user_id) = fresh_account("weekly-until-saved");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    add_week(&conn, user_id, DEC_7, &json!([piano(None), gym()]));
    add_week(&conn, user_id, DEC_14, &json!([piano(None), gym()]));
    let changed = set_standing(
        &conn,
        user_id,
        FIRST_WEEK,
        &text(&json!([piano(Some("2026-12-09"))])),
    )
    .unwrap();
    assert_eq!(changed, vec![DEC_7.to_string(), DEC_14.to_string()]);
    let (dec_7, _) = week_row(&conn, user_id, DEC_7);
    let mut cut = piano(Some("2026-12-09"));
    cut["days"] = json!([1]);
    assert_eq!(dec_7, json!([cut, gym()]));
    let (dec_14, _) = week_row(&conn, user_id, DEC_14);
    assert_eq!(dec_14, json!([gym()]));
}

#[test]
fn running_setup_again_changes_school_and_leaves_a_weekly_block_alone() {
    let (conn, user_id) = fresh_account("weekly-setup-again");
    set_standing(
        &conn,
        user_id,
        FIRST_WEEK,
        &text(&json!([school(), piano(None)])),
    )
    .unwrap();
    add_week(&conn, user_id, DEC_7, &json!([school(), piano(None)]));
    let mut later = school();
    later["start"] = json!("09:00");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([later.clone()]))).unwrap();
    assert_eq!(days_in(&conn, user_id, DEC_14), Some(json!([1, 3])));
    let (dec_7, _) = week_row(&conn, user_id, DEC_7);
    assert_eq!(dec_7, json!([later, piano(None)]));
}

#[test]
fn a_weekly_block_stopped_from_a_week_leaves_that_week_and_later_ones() {
    let (conn, user_id) = fresh_account("weekly-stop");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    add_week(&conn, user_id, DEC_14, &json!([piano(None)]));
    set_standing(
        &conn,
        user_id,
        DEC_7,
        &text(&json!([{"id": "weekly-piano", "stop": true}])),
    )
    .unwrap();
    assert_eq!(days_in(&conn, user_id, FIRST_WEEK), Some(json!([1, 3])));
    assert_eq!(days_in(&conn, user_id, DEC_7), None);
    assert_eq!(days_in(&conn, user_id, DEC_14), None);
}

#[test]
fn rows_saved_without_until_read_and_export_exactly_as_they_were() {
    let (conn, user_id) = fresh_account("weekly-old-rows");
    set_standing(
        &conn,
        user_id,
        SETUP_WEEK,
        &text(&json!([school(), soccer()])),
    )
    .unwrap();
    let rows = standing_rows(&conn, user_id).unwrap();
    assert!(!rows.contains("until"), "{rows}");
    assert_eq!(
        standing_blocks(&conn, user_id, NEXT_WEEK).unwrap(),
        vec![school(), soccer()]
    );
    let with_until = set_standing(
        &conn,
        user_id,
        FIRST_WEEK,
        &text(&json!([piano(Some("2026-12-12"))])),
    );
    assert!(with_until.is_ok());
    let stored = standing_blocks(&conn, user_id, DEC_7).unwrap();
    assert_eq!(stored.last().unwrap()["until"], json!("2026-12-12"));
}

#[test]
fn moving_until_from_the_week_it_cut_keeps_the_cut_days_in_later_weeks() {
    // Tuesday and Thursday until Wednesday 9 December: the week of 7 December holds Tuesday alone. The
    // student then moves Until to Tuesday 22 December from that week, which sends Tuesday only.
    let (conn, user_id) = fresh_account("weekly-until-moved");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    set_standing(
        &conn,
        user_id,
        DEC_7,
        &text(&json!([piano(Some("2026-12-09"))])),
    )
    .unwrap();
    let mut moved = piano(Some("2026-12-22"));
    moved["days"] = json!([1]);
    set_standing(&conn, user_id, DEC_7, &text(&json!([moved]))).unwrap();
    assert_eq!(days_in(&conn, user_id, FIRST_WEEK), Some(json!([1, 3])));
    assert_eq!(days_in(&conn, user_id, DEC_7), Some(json!([1, 3])));
    assert_eq!(days_in(&conn, user_id, DEC_14), Some(json!([1, 3])));
    assert_eq!(days_in(&conn, user_id, "2026-12-21"), Some(json!([1])));
    assert_eq!(days_in(&conn, user_id, "2026-12-28"), None);
}

#[test]
fn moving_until_from_the_week_it_cut_gives_saved_later_weeks_their_days_back() {
    let (conn, user_id) = fresh_account("weekly-until-moved-saved");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    add_week(&conn, user_id, DEC_14, &json!([piano(None), gym()]));
    set_standing(
        &conn,
        user_id,
        DEC_7,
        &text(&json!([piano(Some("2026-12-09"))])),
    )
    .unwrap();
    let (dec_14, _) = week_row(&conn, user_id, DEC_14);
    assert_eq!(dec_14, json!([gym()]));
    let mut moved = piano(Some("2026-12-22"));
    moved["days"] = json!([1]);
    set_standing(&conn, user_id, DEC_7, &text(&json!([moved]))).unwrap();
    assert_eq!(days_in(&conn, user_id, DEC_14), Some(json!([1, 3])));
}

#[test]
fn moving_until_from_the_week_it_cut_gives_that_weeks_saved_copy_its_days_back() {
    // The open week's own copy holds Tuesday alone, because Until (Wednesday 9 December) cut Thursday.
    // Until moves to 22 December from that week: its Thursday 10 December is inside Until again.
    let (conn, user_id) = fresh_account("weekly-until-moved-open");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    set_standing(
        &conn,
        user_id,
        DEC_7,
        &text(&json!([piano(Some("2026-12-09"))])),
    )
    .unwrap();
    let mut moved = piano(Some("2026-12-22"));
    moved["days"] = json!([1]);
    add_week(&conn, user_id, DEC_7, &json!([moved.clone(), gym()]));
    let (_, saved_revision) = week_row(&conn, user_id, DEC_7);
    let changed = set_standing(&conn, user_id, DEC_7, &text(&json!([moved]))).unwrap();
    assert_eq!(changed, vec![DEC_7.to_string()]);
    let (dec_7, revision) = week_row(&conn, user_id, DEC_7);
    assert_eq!(dec_7, json!([piano(Some("2026-12-22")), gym()]));
    assert_eq!(revision, saved_revision + 1);
}

#[test]
fn an_ordinary_change_leaves_the_open_weeks_saved_copy_to_the_client() {
    let (conn, user_id) = fresh_account("weekly-open-week-untouched");
    set_standing(&conn, user_id, FIRST_WEEK, &text(&json!([piano(None)]))).unwrap();
    add_week(&conn, user_id, DEC_7, &json!([piano(None), gym()]));
    add_week(&conn, user_id, DEC_14, &json!([piano(None), gym()]));
    let mut later = piano(None);
    later["start"] = json!("17:00");
    let changed = set_standing(&conn, user_id, DEC_7, &text(&json!([later.clone()]))).unwrap();
    assert_eq!(changed, vec![DEC_14.to_string()]);
    let (dec_7, _) = week_row(&conn, user_id, DEC_7);
    assert_eq!(dec_7, json!([piano(None), gym()]));
    let (dec_14, _) = week_row(&conn, user_id, DEC_14);
    assert_eq!(dec_14, json!([later, gym()]));
}
