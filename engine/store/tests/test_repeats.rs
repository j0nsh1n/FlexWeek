//! Changing School and Setup's activities through the Rust save handler (`changes::apply`), checked
//! by what each week shows afterwards (`week_with_standing`), never by stored rows. The weeks are
//! real: School stands from Monday 2 November 2026, the student has 9 November open, and 16, 23
//! and 30 November are later weeks. Cases P1 to P5 and item 7 are the design study's
//! (`scratch/repeats-design/REPEATS-DESIGN.md`), each of which went wrong before this change.

mod common;

use common::scratch;
use flexweek_engine::repeats::{apply_to_week, edit_intent};
use flexweek_store::{
    ApplyClock, ApplyFailure, ApplyInput, Connection, WeekInput, apply, initialize,
    insert_preferences, open_connection, read_week, standing_blocks, week_with_standing,
};
use serde_json::{Value, json};

const SETUP_WEEK: &str = "2026-11-02";
const OPEN_WEEK: &str = "2026-11-09";
const NEXT_WEEK: &str = "2026-11-16";
const WEEK_AFTER: &str = "2026-11-23";
const LAST_WEEK: &str = "2026-11-30";

fn school() -> Value {
    json!({"category": "class", "days": [0, 1, 2, 3, 4], "duration_min": 405, "id": "school",
           "kind": "locked", "start": "08:30", "title": "School"})
}

fn soccer() -> Value {
    json!({"category": "extra", "days": [1, 3], "duration_min": 90, "id": "activity-1",
           "kind": "locked", "start": "16:00", "title": "Soccer"})
}

fn with(base: Value, changes: Value) -> Value {
    let mut out = base;
    for (key, value) in changes.as_object().unwrap() {
        out[key] = value.clone();
    }
    out
}

fn account(name: &str, clock_24h: bool) -> (Connection, i64) {
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
    conn.execute(
        "UPDATE preferences SET comfort_json = ?1 WHERE user_id = ?2",
        rusqlite::params![json!({"clock_24h": clock_24h}).to_string(), user_id],
    )
    .unwrap();
    conn.execute_batch("COMMIT").unwrap();
    (conn, user_id)
}

fn clock() -> ApplyClock {
    ApplyClock {
        now: "2026-11-12T09:00:00".into(),
        restore_token: "tok".into(),
    }
}

fn batch(
    weeks: Vec<(&str, Vec<Value>)>,
    repeats: Option<Vec<Value>>,
    conn: &Connection,
    user_id: i64,
) -> ApplyInput {
    ApplyInput {
        weeks: weeks
            .into_iter()
            .map(|(week_start, blocks)| WeekInput {
                week_start: week_start.into(),
                blocks,
                revision: revision(conn, user_id, week_start),
            })
            .collect(),
        assignments: Vec::new(),
        operation_id: None,
        snapshot_label: None,
        repeats,
        argument_digest: None,
    }
}

fn run(conn: &Connection, user_id: i64, input: &ApplyInput) -> Value {
    match apply(conn, user_id, input, &clock()) {
        Ok(value) => value,
        Err(ApplyFailure::Refused { message, .. }) => panic!("refused: {message}"),
        Err(ApplyFailure::Store(error)) => panic!("store: {error:?}"),
    }
}

fn revision(conn: &Connection, user_id: i64, week: &str) -> i64 {
    read_week(conn, user_id, week)
        .unwrap()
        .map_or(0, |(_, revision)| revision)
}

/// What the student sees in a week: its saved blocks with the repeats merged in.
fn shown(conn: &Connection, user_id: i64, week: &str) -> Vec<Value> {
    let stored = read_week(conn, user_id, week)
        .unwrap()
        .map_or_else(|| "[]".to_string(), |(text, _)| text);
    serde_json::from_str(&week_with_standing(conn, user_id, week, &stored).unwrap()).unwrap()
}

fn block<'a>(week: &'a [Value], id: &str) -> Option<&'a Value> {
    week.iter().find(|block| block["id"] == json!(id))
}

/// School's days and minutes in a week, with the days skipped that week.
fn school_in(conn: &Connection, user_id: i64, week: &str) -> (Vec<i64>, i64, Vec<i64>) {
    let week = shown(conn, user_id, week);
    let school = block(&week, "school").expect("School in that week");
    let ints = |key: &str| -> Vec<i64> {
        school[key]
            .as_array()
            .map(|items| items.iter().map(|d| d.as_i64().unwrap()).collect())
            .unwrap_or_default()
    };
    (
        ints("days"),
        school["duration_min"].as_i64().unwrap(),
        ints("missed_days"),
    )
}

/// The app's first Setup: School and Soccer stand from 2 November.
fn set_up(conn: &Connection, user_id: i64) {
    let intents = [school(), soccer()]
        .iter()
        .map(|body| {
            edit_intent(body["id"].as_str().unwrap(), SETUP_WEEK, None, Some(body))
                .unwrap()
                .to_value()
        })
        .collect();
    run(
        conn,
        user_id,
        &batch(Vec::new(), Some(intents), conn, user_id),
    );
}

/// A week saved the way the app saves it: every repeat copied in, with this week's own changes.
fn save_week_as(conn: &Connection, user_id: i64, week: &str, blocks: Vec<Value>) {
    run(
        conn,
        user_id,
        &batch(vec![(week, blocks)], None, conn, user_id),
    );
}

/// What School hours or Setup sends from the open week: the change against the repeat, with the
/// open week changed locally by the same rule.
fn change_from_open_week(
    conn: &Connection,
    user_id: i64,
    week: &str,
    edited: &[(&str, Option<Value>)],
) -> Value {
    let repeats = standing_blocks(conn, user_id, week).unwrap();
    let open = shown(conn, user_id, week);
    let intents: Vec<_> = edited
        .iter()
        .filter_map(|(id, body)| {
            let repeat = repeats.iter().find(|r| r["id"] == json!(id));
            edit_intent(id, week, repeat, body.as_ref())
        })
        .collect();
    let (blocks, _) = apply_to_week(&open, &repeats, &intents).unwrap();
    let values = intents.iter().map(|intent| intent.to_value()).collect();
    run(
        conn,
        user_id,
        &batch(vec![(week, blocks)], Some(values), conn, user_id),
    )
}

#[test]
fn p1_school_hours_after_skipping_wednesday_keeps_wednesday_school_in_later_weeks() {
    let (conn, user_id) = account("repeats-p1", true);
    set_up(&conn, user_id);
    save_week_as(
        &conn,
        user_id,
        OPEN_WEEK,
        vec![with(school(), json!({"days": [0, 1, 3, 4]})), soccer()],
    );
    change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    assert_eq!(
        school_in(&conn, user_id, OPEN_WEEK),
        (vec![0, 1, 3, 4], 360, vec![])
    );
    for later in [NEXT_WEEK, LAST_WEEK] {
        assert_eq!(
            school_in(&conn, user_id, later),
            (vec![0, 1, 2, 3, 4], 360, vec![]),
            "{later}"
        );
    }
}

#[test]
fn p2_a_wednesday_deleted_in_a_later_week_stays_deleted_and_the_student_is_told() {
    let (conn, user_id) = account("repeats-p2", true);
    set_up(&conn, user_id);
    save_week_as(
        &conn,
        user_id,
        NEXT_WEEK,
        vec![with(school(), json!({"days": [0, 1, 3, 4]})), soccer()],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    assert_eq!(
        school_in(&conn, user_id, NEXT_WEEK),
        (vec![0, 1, 3, 4], 360, vec![])
    );
    assert_eq!(
        school_in(&conn, user_id, WEEK_AFTER),
        (vec![0, 1, 2, 3, 4], 360, vec![])
    );
    assert_eq!(
        answer["repeats"],
        json!({
            "changed_weeks": [NEXT_WEEK],
            "kept": [{"week_start": NEXT_WEEK, "id": "school", "changes": ["no School on Wednesday"]}],
            "notice": "School changed from this week on. The week of 16 Nov keeps its own change: no School on Wednesday.",
        })
    );
    // The answer's open week carries the repeats as they now stand, for School hours to show.
    assert_eq!(
        answer["weeks"][0]["repeats"],
        json!([with(school(), json!({"duration_min": 360})), soccer()])
    );
}

#[test]
fn p3_a_wednesday_moved_in_a_later_week_shows_once() {
    let (conn, user_id) = account("repeats-p3", false);
    set_up(&conn, user_id);
    let moved = json!({"category": "class", "days": [2], "duration_min": 120, "id": "98f0907e",
                       "kind": "locked", "start": "10:00", "title": "School"});
    save_week_as(
        &conn,
        user_id,
        NEXT_WEEK,
        vec![
            with(school(), json!({"days": [0, 1, 3, 4]})),
            moved,
            soccer(),
        ],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    let week = shown(&conn, user_id, NEXT_WEEK);
    let on_wednesday: Vec<&Value> = week
        .iter()
        .filter(|b| {
            b["title"] == json!("School") && b["days"].as_array().unwrap().contains(&json!(2))
        })
        .collect();
    assert_eq!(on_wednesday.len(), 1);
    assert_eq!(on_wednesday[0]["start"], json!("10:00"));
    assert_eq!(
        answer["repeats"]["notice"],
        json!(
            "School changed from this week on. The week of 16 Nov keeps its own change: School at 10:00 AM–12:00 PM on Wednesday."
        )
    );
}

#[test]
fn p4_a_one_week_rename_is_not_the_new_school() {
    let (conn, user_id) = account("repeats-p4", true);
    set_up(&conn, user_id);
    let trip = with(school(), json!({"title": "School trip", "start": "07:00"}));
    save_week_as(&conn, user_id, OPEN_WEEK, vec![trip, soccer()]);
    change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    let open = shown(&conn, user_id, OPEN_WEEK);
    assert_eq!(
        block(&open, "school").unwrap()["title"],
        json!("School trip")
    );
    for later in [NEXT_WEEK, LAST_WEEK] {
        let week = shown(&conn, user_id, later);
        let school = block(&week, "school").unwrap();
        assert_eq!(
            (&school["title"], &school["start"], &school["duration_min"]),
            (&json!("School"), &json!("08:30"), &json!(360))
        );
    }
}

#[test]
fn p5_an_activity_ended_from_a_later_week_stays_ended() {
    let (conn, user_id) = account("repeats-p5", true);
    set_up(&conn, user_id);
    change_from_open_week(&conn, user_id, WEEK_AFTER, &[("activity-1", None)]);
    assert!(block(&shown(&conn, user_id, WEEK_AFTER), "activity-1").is_none());
    change_from_open_week(
        &conn,
        user_id,
        NEXT_WEEK,
        &[(
            "activity-1",
            Some(with(soccer(), json!({"start": "17:00"}))),
        )],
    );
    assert_eq!(
        block(&shown(&conn, user_id, NEXT_WEEK), "activity-1").unwrap()["start"],
        json!("17:00")
    );
    for later in [WEEK_AFTER, LAST_WEEK] {
        assert!(
            block(&shown(&conn, user_id, later), "activity-1").is_none(),
            "{later}"
        );
    }
    assert_eq!(
        block(&shown(&conn, user_id, OPEN_WEEK), "activity-1").unwrap()["start"],
        json!("16:00")
    );
}

#[test]
fn item7_setup_again_keeps_school_deleted_for_this_week_only() {
    let (conn, user_id) = account("repeats-item7", true);
    set_up(&conn, user_id);
    save_week_as(
        &conn,
        user_id,
        OPEN_WEEK,
        vec![
            with(school(), json!({"missed_days": [0, 1, 2, 3, 4]})),
            soccer(),
        ],
    );
    change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[
            (
                "school",
                Some(with(
                    school(),
                    json!({"start": "08:00", "duration_min": 435}),
                )),
            ),
            ("activity-1", Some(soccer())),
        ],
    );
    assert_eq!(school_in(&conn, user_id, OPEN_WEEK).2, vec![0, 1, 2, 3, 4]);
    assert_eq!(
        school_in(&conn, user_id, NEXT_WEEK),
        (vec![0, 1, 2, 3, 4], 435, vec![])
    );
}

#[test]
fn a_later_week_that_matched_the_repeat_follows_it_and_is_not_named() {
    let (conn, user_id) = account("repeats-follow", true);
    set_up(&conn, user_id);
    save_week_as(&conn, user_id, NEXT_WEEK, vec![school(), soccer()]);
    let before = revision(&conn, user_id, NEXT_WEEK);
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[(
            "activity-1",
            Some(with(soccer(), json!({"days": [1, 3, 5]}))),
        )],
    );
    assert_eq!(
        block(&shown(&conn, user_id, NEXT_WEEK), "activity-1").unwrap()["days"],
        json!([1, 3, 5])
    );
    assert_eq!(revision(&conn, user_id, NEXT_WEEK), before + 1);
    assert_eq!(
        answer["repeats"],
        json!({"changed_weeks": [NEXT_WEEK], "kept": [], "notice": null})
    );
}

#[test]
fn the_open_week_already_changed_by_the_client_is_left_as_sent() {
    let (conn, user_id) = account("repeats-open", true);
    set_up(&conn, user_id);
    save_week_as(
        &conn,
        user_id,
        OPEN_WEEK,
        vec![with(school(), json!({"days": [0, 1, 3, 4]})), soccer()],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"start": "09:00"}))))],
    );
    // Only the save of the open week itself moved its revision; the store's pass changed nothing.
    assert_eq!(answer["weeks"][0]["revision"], json!(2));
    assert_eq!(answer["repeats"]["changed_weeks"], json!([]));
}

#[test]
fn a_change_that_is_not_one_is_refused_and_saves_nothing() {
    let (conn, user_id) = account("repeats-refused", true);
    set_up(&conn, user_id);
    let empties =
        json!({"id": "activity-1", "scope": "from", "from_date": OPEN_WEEK, "remove_days": [1, 3]});
    let input = batch(
        vec![(OPEN_WEEK, vec![school()])],
        Some(vec![empties]),
        &conn,
        user_id,
    );
    match apply(&conn, user_id, &input, &clock()) {
        Err(ApplyFailure::Refused { message, .. }) => {
            assert_eq!(message, flexweek_engine::repeats::NOTHING_LEFT);
        }
        other => panic!("not refused: {other:?}"),
    }
    assert_eq!(revision(&conn, user_id, OPEN_WEEK), 0);
    assert_eq!(
        standing_blocks(&conn, user_id, OPEN_WEEK).unwrap(),
        vec![school(), soccer()]
    );
}

#[test]
fn a_replayed_batch_gets_the_same_answer_and_changes_nothing_more() {
    let (conn, user_id) = account("repeats-replay", true);
    set_up(&conn, user_id);
    save_week_as(
        &conn,
        user_id,
        NEXT_WEEK,
        vec![with(school(), json!({"days": [0, 1, 3, 4]})), soccer()],
    );
    let intent = json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "set": {"duration_min": 360}});
    let mut input = batch(
        vec![(OPEN_WEEK, shown(&conn, user_id, OPEN_WEEK))],
        Some(vec![intent]),
        &conn,
        user_id,
    );
    input.operation_id = Some("op-school-hours".into());
    let first = run(&conn, user_id, &input);
    let later = revision(&conn, user_id, NEXT_WEEK);
    let again = run(&conn, user_id, &input);
    assert_eq!(again, first);
    assert_eq!(revision(&conn, user_id, NEXT_WEEK), later);
}

/// What a week shows, as `fixtures/repeat_cases.json` writes it.
fn summary(week: &[Value]) -> Value {
    let mut out = serde_json::Map::new();
    for block in week {
        out.insert(
            block["id"].as_str().unwrap().to_string(),
            json!([
                block["title"],
                block["start"],
                block["duration_min"],
                block["days"],
                block
                    .get("missed_days")
                    .cloned()
                    .unwrap_or_else(|| json!([]))
            ]),
        );
    }
    Value::Object(out)
}

/// The cases the backend's `post_changes` runs too (`backend/tests/test_repeat_intents_api.py`), so
/// the two save handlers cannot drift apart unnoticed.
#[test]
fn shared_cases_give_the_answers_worked_out_for_both_save_handlers() {
    let cases: Value = serde_json::from_str(include_str!("fixtures/repeat_cases.json")).unwrap();
    let resolve = |block: &Value| match block.as_str() {
        Some(name) => cases[name].clone(),
        None => block.clone(),
    };
    for (n, case) in cases["cases"].as_array().unwrap().iter().enumerate() {
        let name = case["name"].as_str().unwrap();
        let (conn, user_id) = account(
            &format!("repeats-shared-{n}"),
            case["clock_24h"] == json!(true),
        );
        let setup = cases["setup"].as_array().unwrap().clone();
        run(
            &conn,
            user_id,
            &batch(Vec::new(), Some(setup), &conn, user_id),
        );
        let mut last = Value::Null;
        for step in case["steps"].as_array().unwrap() {
            let weeks: Vec<(String, Vec<Value>)> = step
                .get("weeks")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .map(|week| {
                    let blocks = week["blocks"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(resolve)
                        .collect();
                    (week["week_start"].as_str().unwrap().to_string(), blocks)
                })
                .collect();
            let weeks = weeks
                .iter()
                .map(|(week, blocks)| (week.as_str(), blocks.clone()))
                .collect();
            let repeats = step.get("repeats").and_then(Value::as_array).cloned();
            last = run(&conn, user_id, &batch(weeks, repeats, &conn, user_id));
        }
        assert_eq!(last["repeats"], case["answer_repeats"], "{name}");
        for (week, expected) in case["shown"].as_object().unwrap() {
            assert_eq!(
                summary(&shown(&conn, user_id, week)),
                *expected,
                "{name}: week of {week}"
            );
        }
    }
}

#[test]
fn a_later_this_week_and_later_change_that_stays_is_named() {
    // School stands from 2 Nov at 08:30. From 16 Nov the student moved it to 10:00, this week and later.
    // Then, from 9 Nov, School becomes 6 hours long. 16 Nov on keeps its own 10:00 start and takes the new
    // length (10:00 to 16:00); that kept start is named, as a later week's own change would be.
    let (conn, user_id) = account("repeats-later-version", true);
    set_up(&conn, user_id);
    change_from_open_week(
        &conn,
        user_id,
        NEXT_WEEK,
        &[("school", Some(with(school(), json!({"start": "10:00"}))))],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    let later = block(&shown(&conn, user_id, WEEK_AFTER), "school")
        .unwrap()
        .clone();
    assert_eq!(
        (later["start"].clone(), later["duration_min"].clone()),
        (json!("10:00"), json!(360))
    );
    let opened = block(&shown(&conn, user_id, OPEN_WEEK), "school")
        .unwrap()
        .clone();
    assert_eq!(
        (opened["start"].clone(), opened["duration_min"].clone()),
        (json!("08:30"), json!(360))
    );
    assert_eq!(answer["repeats"]["kept"][0]["week_start"], json!(NEXT_WEEK));
    assert_eq!(answer["repeats"]["kept"][0]["id"], json!("school"));
    let notice = answer["repeats"]["notice"].as_str().unwrap();
    assert!(
        notice.starts_with("School changed from this week on."),
        "{notice}"
    );
    assert!(notice.contains("16 Nov"), "{notice}");
    assert!(notice.contains("10:00"), "{notice}");
}

#[test]
fn a_later_version_and_that_weeks_own_copy_are_named_once_for_what_the_week_shows() {
    // From 16 Nov School starts at 10:00 (this week and later); the saved week of 16 Nov also has its own
    // 11:00 start. From 9 Nov School becomes 6 hours long. 16 Nov shows 11:00-17:00 and is named once,
    // with that; 23 Nov on shows 10:00-16:00 from the later change.
    let (conn, user_id) = account("repeats-version-and-copy", true);
    set_up(&conn, user_id);
    change_from_open_week(
        &conn,
        user_id,
        NEXT_WEEK,
        &[("school", Some(with(school(), json!({"start": "10:00"}))))],
    );
    save_week_as(
        &conn,
        user_id,
        NEXT_WEEK,
        vec![with(school(), json!({"start": "11:00"})), soccer()],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"duration_min": 360}))))],
    );
    let here = block(&shown(&conn, user_id, NEXT_WEEK), "school")
        .unwrap()
        .clone();
    assert_eq!(
        (here["start"].clone(), here["duration_min"].clone()),
        (json!("11:00"), json!(360))
    );
    let after = block(&shown(&conn, user_id, WEEK_AFTER), "school")
        .unwrap()
        .clone();
    assert_eq!(
        (after["start"].clone(), after["duration_min"].clone()),
        (json!("10:00"), json!(360))
    );
    let kept = answer["repeats"]["kept"].as_array().unwrap();
    let weeks: Vec<_> = kept.iter().map(|item| item["week_start"].clone()).collect();
    assert_eq!(weeks, vec![json!(NEXT_WEEK)], "{kept:?}");
    let notice = answer["repeats"]["notice"].as_str().unwrap();
    assert!(notice.contains("11:00"), "{notice}");
    assert!(!notice.contains("10:00"), "{notice}");
}

#[test]
fn a_later_version_that_already_says_what_the_change_says_is_not_named() {
    // From 16 Nov School starts at 10:00; then from 9 Nov School starts at 10:00 too. Nothing differs.
    let (conn, user_id) = account("repeats-version-same", true);
    set_up(&conn, user_id);
    change_from_open_week(
        &conn,
        user_id,
        NEXT_WEEK,
        &[("school", Some(with(school(), json!({"start": "10:00"}))))],
    );
    let answer = change_from_open_week(
        &conn,
        user_id,
        OPEN_WEEK,
        &[("school", Some(with(school(), json!({"start": "10:00"}))))],
    );
    assert_eq!(answer["repeats"]["kept"], json!([]));
    assert_eq!(answer["repeats"]["notice"], json!(null));
}
