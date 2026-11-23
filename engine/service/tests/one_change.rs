//! The app and the assistant save a batch through one function (`flexweek_store::changes`): the assistant's
//! door (`apply_within`, inside its own transaction) now saves a week shown from another weekday, and a save
//! the app made is the same operation to the store, so a resend through either door finds the first answer.

use flexweek_engine::validate::time_block;
use flexweek_service::changes::apply_changes;
use flexweek_service::weeks;
use flexweek_store::{ApplyClock, ApplyInput, Revision, WeekInput, apply, apply_within};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const NOW: &str = "2026-11-05T19:00";
/// A week on screen from Thursday 2026-09-17 covers the stored weeks of 2026-09-14 and 2026-09-21.
const SHOWN: &str = "2026-09-17";
const FIRST: &str = "2026-09-14";
const MONDAY: &str = "2026-09-14";

fn clock() -> ApplyClock {
    ApplyClock {
        now: NOW.to_string(),
        restore_token: "0123456789abcdef".to_string(),
    }
}

/// A fixed block on the first day of whatever week holds it, as a block reads once checked.
fn club() -> Value {
    time_block(
        &json!({ "id": "club", "title": "Club", "kind": "locked", "duration_min": 60, "days": [0],
                        "start": "16:00" }),
    )
    .unwrap()
    .to_value()
}

fn input(week_start: &str, revision: Revision, operation_id: Option<&str>) -> ApplyInput {
    ApplyInput {
        weeks: vec![WeekInput {
            week_start: week_start.to_string(),
            blocks: vec![club()],
            revision,
        }],
        assignments: Vec::new(),
        operation_id: operation_id.map(str::to_string),
        snapshot_label: None,
        repeats: None,
        argument_digest: None,
    }
}

fn stored_rows(db: &TestDb) -> Vec<(String, String)> {
    let conn = db.sql();
    let mut stmt = conn
        .prepare("SELECT week_start, blocks FROM weeks ORDER BY week_start")
        .unwrap();
    stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
        .unwrap()
        .collect::<Result<_, _>>()
        .unwrap()
}

#[test]
fn the_assistants_door_saves_a_week_shown_from_thursday_into_its_stored_week() {
    let db = TestDb::new("one-change-shown");
    let ana = db.account("ana");
    let conn = db.sql();
    flexweek_store::begin_immediate(&conn).unwrap();
    apply_within(
        &conn,
        ana,
        &input(SHOWN, Revision::Shown(0, 0), None),
        &clock(),
    )
    .unwrap();
    conn.execute("COMMIT", []).unwrap();
    // The shown week's first day is Thursday, day 3 of the stored week it starts in.
    let rows = stored_rows(&db);
    assert_eq!(rows.len(), 1, "{rows:?}");
    assert_eq!(rows[0].0, FIRST);
    let stored: Value = serde_json::from_str(&rows[0].1).unwrap();
    assert_eq!(stored[0]["days"], json!([3]));
    let shown = weeks::read_week(&db.path, ana, SHOWN).unwrap();
    assert_eq!(shown["blocks"][0]["id"], "club");
    assert_eq!(shown["blocks"][0]["days"], json!([0]));
}

#[test]
fn a_shown_week_the_assistant_rolls_back_leaves_nothing() {
    let db = TestDb::new("one-change-rollback");
    let ana = db.account("ana");
    let conn = db.sql();
    flexweek_store::begin_immediate(&conn).unwrap();
    apply_within(
        &conn,
        ana,
        &input(SHOWN, Revision::Shown(0, 0), None),
        &clock(),
    )
    .unwrap();
    conn.execute("ROLLBACK", []).unwrap();
    assert!(stored_rows(&db).is_empty());
}

#[test]
fn a_save_the_app_made_is_the_same_operation_to_the_store() {
    let db = TestDb::new("one-change-replay");
    let ana = db.account("ana");
    let given = json!({ "weeks": [{ "week_start": MONDAY, "blocks": [club()], "revision": 0 }],
                        "assignments": [], "operation_id": "op-1" });
    let first = apply_changes(&db.path, ana, &given, "0123456789abcdef", NOW).unwrap();
    // The same save again, now as the store's input: the first answer, not "used with different data" and
    // not a second write.
    let again = apply(
        &db.sql(),
        ana,
        &input(MONDAY, Revision::Stored(0), Some("op-1")),
        &clock(),
    )
    .unwrap();
    assert_eq!(again, first);
    assert_eq!(stored_rows(&db).len(), 1);
}

/// School standing from `week_start` on, as Setup sends it.
fn school_from(week_start: &str) -> Value {
    json!({ "id": "school", "scope": "from", "from_date": week_start,
            "set": { "title": "School", "category": "class", "start": "08:30", "duration_min": 405 },
            "add_days": [0, 1, 2, 3, 4] })
}

fn school_at(start: &str) -> Value {
    json!({ "id": "school", "title": "School", "kind": "locked", "category": "class", "start": start,
            "duration_min": 405, "days": [0, 1, 2, 3, 4] })
}

/// The open week holds its own School time, and one save sends that week and changes School in all weeks,
/// which rewrites the open week's row after the save wrote it. The answer carries the revision as now
/// stored, so the window's next save is not refused as changed elsewhere.
#[test]
fn after_repeats_rewrite_the_open_week_the_answer_has_its_stored_revision() {
    let db = TestDb::new("one-change-reread");
    let ana = db.account("ana");
    let week_before = "2026-09-07";
    let stand = json!({ "weeks": [], "repeats": [school_from(week_before)] });
    apply_changes(&db.path, ana, &stand, "0123456789abcdef", NOW).unwrap();
    let own = json!({ "week_start": MONDAY, "blocks": [school_at("09:00")], "revision": 0 });
    let revision =
        flexweek_service::week_saves::save_week(&db.path, ana, &own).unwrap()["revision"].clone();
    let all_weeks = json!({ "id": "school", "scope": "from", "from_date": week_before,
                            "set": { "start": "08:00" }, "remove_days": [], "edited": "replace" });
    let given = json!({
        "weeks": [{ "week_start": MONDAY, "blocks": [school_at("09:00")], "revision": revision }],
        "repeats": [all_weeks],
    });
    let saved =
        apply_changes(&db.path, ana, &given, "0123456789abcdef", NOW).unwrap()["weeks"][0].clone();
    let stored = weeks::read_week(&db.path, ana, MONDAY).unwrap()["revision"].clone();
    assert_eq!(saved["revision"], stored);
    let next =
        json!({ "week_start": MONDAY, "blocks": saved["blocks"], "revision": saved["revision"] });
    flexweek_service::week_saves::save_week(&db.path, ana, &next).unwrap();
}
