//! Each test names the `desktop/native/controller.py` lines it mirrors.
//! Expected blocks are the `TimeBlock` dump: null bounds stay, false flags are omitted
//! until the finish cascade writes `completed` itself.

use flexweek_engine::desk::homework::{
    HomeworkEdit, MarkedHomework, MarkedWeek, edit_homework, mark_homework_done,
};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-10-19";
const TODAY: &str = "2026-10-21";
const NOW_MINUTE: i64 = 12 * 60;

fn show(result: Result<HomeworkEdit, String>) -> Result<Value, String> {
    result.map(|edit| {
        json!({
            "label": edit.label,
            "assignment": edit.assignment,
            "blocks": edit.blocks,
            "lost": edit.lost,
        })
    })
}

fn assignments_of(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(map) => map,
        _ => Map::new(),
    }
}

fn put(value: &mut Value, key: &str, patch: Value) {
    if let Some(map) = value.as_object_mut() {
        map.insert(key.to_string(), patch);
    }
}

fn school() -> Value {
    json!({
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 405,
        "days": [0, 1, 2, 3, 4],
        "start": "08:30"
    })
}

fn essay(title: &str, estimate: i64) -> Value {
    json!({
        "id": "essay",
        "title": title,
        "due": "2026-10-23T21:00",
        "estimate_min": estimate
    })
}

fn known_essay() -> Value {
    json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-23T21:00",
        "estimate_min": 90,
        "revision": 4,
        "focus_minutes": 15,
        "focus_sessions": 2,
        "session_weeks": ["2026-10-12"],
        "completed": false,
        "completed_at": null
    })
}

fn flexible(id: &str, title: &str, minutes: i64, days: Vec<i64>) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "flexible",
        "duration_min": minutes,
        "days": days,
        "assignment_id": "essay"
    })
}

fn dumped(id: &str, title: &str, minutes: i64, days: Vec<i64>, start: Option<&str>) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "flexible",
        "duration_min": minutes,
        "days": days,
        "priority": 3,
        "energy": "medium",
        "earliest": Value::Null,
        "latest": Value::Null,
        "start": start,
        "course": Value::Null,
        "assignment_id": "essay"
    })
}

fn saved(
    title: &str,
    estimate: i64,
    revision: i64,
    focus_minutes: i64,
    focus_sessions: i64,
) -> Value {
    json!({
        "id": "essay",
        "title": title,
        "course": Value::Null,
        "category": Value::Null,
        "priority": 3,
        "energy": "medium",
        "spotify_url": Value::Null,
        "due": "2026-10-23T21:00",
        "estimate_min": estimate,
        "focus_minutes": focus_minutes,
        "focus_sessions": focus_sessions,
        "completed": false,
        "completed_at": Value::Null,
        "revision": revision
    })
}

fn edit(
    blocks: &[Value],
    assignments: &Map<String, Value>,
    assignment: &Value,
    days: Option<&[i64]>,
    spread: bool,
    new_session_id: &str,
) -> Result<HomeworkEdit, String> {
    edit_homework(
        blocks,
        assignments,
        WEEK,
        assignment,
        days,
        spread,
        new_session_id,
        TODAY,
        NOW_MINUTE,
    )
}

/// controller.py:1001-1015. A homework with no session gets one flexible session.
#[test]
fn adding_homework_creates_one_session() {
    let blocks = vec![school()];
    let got = show(edit(
        &blocks,
        &Map::new(),
        &essay("Essay", 90),
        None,
        false,
        "s-essay",
    ));
    let assignment = saved("Essay", 90, 0, 0, 0);
    assert_eq!(
        got,
        Ok(json!({
            "label": "adding Essay",
            "assignment": assignment,
            "blocks": [
                school(),
                dumped("s-essay", "Essay", 90, vec![0, 1, 2, 3, 4], None)
            ],
            "lost": []
        }))
    );
}

/// controller.py:967-971 and 973-997. One session as long as the old estimate follows the new one.
#[test]
fn one_session_resizes_and_keeps_the_stored_revision() {
    let blocks = vec![flexible("s1", "Essay", 90, vec![0, 1, 2, 3, 4])];
    let mut dialog = essay("Essay draft", 120);
    put(&mut dialog, "revision", json!(0));
    put(&mut dialog, "focus_minutes", json!(0));
    put(&mut dialog, "focus_sessions", json!(0));
    let mut assignment = saved("Essay draft", 120, 4, 15, 2);
    put(&mut assignment, "session_weeks", json!(["2026-10-12"]));
    let got = show(edit(
        &blocks,
        &assignments_of(json!({"essay": known_essay()})),
        &dialog,
        Some(&[1, 2]),
        false,
        "unused",
    ));
    assert_eq!(
        got,
        Ok(json!({
            "label": "editing Essay draft",
            "assignment": assignment,
            "blocks": [dumped("s1", "Essay draft", 120, vec![1, 2], None)],
            "lost": []
        }))
    );
}

/// controller.py:974-991. Two sessions are retitled and keep the lengths already chosen.
#[test]
fn two_sessions_keep_their_lengths() {
    let blocks = vec![
        flexible("s1", "Essay", 30, vec![0]),
        flexible("s2", "Essay", 60, vec![1]),
    ];
    let mut known = known_essay();
    put(&mut known, "estimate_min", json!(90));
    let dialog = essay("Essay draft", 120);
    let got = show(edit(
        &blocks,
        &assignments_of(json!({"essay": known})),
        &dialog,
        Some(&[4]),
        false,
        "unused",
    ));
    let first = dumped("s1", "Essay draft", 30, vec![0], None);
    let second = dumped("s2", "Essay draft", 60, vec![1], None);
    assert_eq!(
        got,
        Ok(json!({
            "label": "editing Essay draft",
            "assignment": {
                "id": "essay",
                "title": "Essay draft",
                "course": Value::Null,
                "category": Value::Null,
                "priority": 3,
                "energy": "medium",
                "spotify_url": Value::Null,
                "due": "2026-10-23T21:00",
                "estimate_min": 120,
                "focus_minutes": 15,
                "focus_sessions": 2,
                "completed": false,
                "completed_at": Value::Null,
                "revision": 4,
                "session_weeks": ["2026-10-12"]
            },
            "blocks": [first, second],
            "lost": []
        }))
    );
}

/// controller.py:986-987 and 1001. Spread drops open sessions and adds none.
#[test]
fn spread_drops_open_sessions_and_keeps_a_finished_one() {
    let mut done = flexible("s-done", "Essay", 30, vec![0]);
    put(&mut done, "completed", json!(true));
    let blocks = vec![done, flexible("s-open", "Essay", 60, vec![1])];
    let got = show(edit(
        &blocks,
        &assignments_of(json!({"essay": known_essay()})),
        &essay("Essay draft", 90),
        None,
        true,
        "unused",
    ));
    let mut kept = dumped("s-done", "Essay draft", 30, vec![0], None);
    put(&mut kept, "completed", json!(true));
    assert_eq!(
        got,
        Ok(json!({
            "label": "editing Essay draft",
            "assignment": {
                "id": "essay",
                "title": "Essay draft",
                "course": Value::Null,
                "category": Value::Null,
                "priority": 3,
                "energy": "medium",
                "spotify_url": Value::Null,
                "due": "2026-10-23T21:00",
                "estimate_min": 90,
                "focus_minutes": 15,
                "focus_sessions": 2,
                "completed": false,
                "completed_at": Value::Null,
                "revision": 4,
                "session_weeks": ["2026-10-12"]
            },
            "blocks": [kept],
            "lost": []
        }))
    );
}

/// controller.py:1016-1028. Finishing stamps the one day a started session was on.
#[test]
fn finishing_sets_completed_day_on_a_one_day_session() {
    let mut session = flexible("s1", "Essay", 90, vec![2]);
    put(&mut session, "start", json!("16:00"));
    let mut dialog = essay("Essay", 90);
    put(&mut dialog, "completed", json!(true));
    put(&mut dialog, "completed_at", json!("2026-10-21T12:00"));
    let got = show(edit(
        &[session],
        &assignments_of(json!({"essay": known_essay()})),
        &dialog,
        None,
        false,
        "unused",
    ));
    let mut block = dumped("s1", "Essay", 90, vec![2], Some("16:00"));
    put(&mut block, "completed", json!(true));
    put(&mut block, "completed_day", json!(2));
    let mut assignment = saved("Essay", 90, 4, 15, 2);
    put(&mut assignment, "completed", json!(true));
    put(&mut assignment, "completed_at", json!("2026-10-21T12:00"));
    put(&mut assignment, "session_weeks", json!(["2026-10-12"]));
    assert_eq!(
        got,
        Ok(json!({
            "label": "finishing Essay",
            "assignment": assignment,
            "blocks": [block],
            "lost": []
        }))
    );
}

/// controller.py:1027-1028. Reopening clears the finished day and writes completed false.
#[test]
fn reopening_clears_completed_day() {
    let mut session = flexible("s1", "Essay", 90, vec![2]);
    put(&mut session, "start", json!("16:00"));
    put(&mut session, "completed", json!(true));
    put(&mut session, "completed_day", json!(2));
    let mut known = known_essay();
    put(&mut known, "completed", json!(true));
    put(&mut known, "completed_at", json!("2026-10-21T11:00"));
    let mut dialog = essay("Essay", 90);
    put(&mut dialog, "completed", json!(false));
    put(&mut dialog, "completed_at", Value::Null);
    let got = show(edit(
        &[session],
        &assignments_of(json!({"essay": known})),
        &dialog,
        None,
        false,
        "unused",
    ));
    let mut block = dumped("s1", "Essay", 90, vec![2], Some("16:00"));
    put(&mut block, "completed", json!(false));
    let mut assignment = saved("Essay", 90, 4, 15, 2);
    put(&mut assignment, "session_weeks", json!(["2026-10-12"]));
    assert_eq!(
        got,
        Ok(json!({
            "label": "reopening Essay",
            "assignment": assignment,
            "blocks": [block],
            "lost": []
        }))
    );
}

/// controller.py:1035-1041. "Do it at" pins the start, the day and pinned.
#[test]
fn fixed_at_pins_the_session() {
    let blocks = vec![flexible("s1", "Essay", 90, vec![0, 1, 2, 3, 4])];
    let mut dialog = essay("Essay", 90);
    put(&mut dialog, "fixed_at", json!({"start": "16:00", "day": 2}));
    let got = show(edit(
        &blocks,
        &assignments_of(json!({"essay": known_essay()})),
        &dialog,
        None,
        false,
        "unused",
    ));
    let mut block = dumped("s1", "Essay", 90, vec![2], Some("16:00"));
    put(&mut block, "pinned", json!(true));
    assert_eq!(
        got.as_ref()
            .map(|value| value.pointer("/blocks/0").cloned())
            .map_err(String::as_str),
        Ok(Some(block))
    );
    assert_eq!(
        got.as_ref()
            .map(|value| value.pointer("/label").cloned())
            .map_err(String::as_str),
        Ok(Some(json!("editing Essay")))
    );
}

/// controller.py:1038-1039. None means let FlexWeek pick a time, so the pin goes.
#[test]
fn fixed_at_null_drops_the_pin_only() {
    let mut session = flexible("s1", "Essay", 90, vec![2]);
    put(&mut session, "start", json!("16:00"));
    put(&mut session, "pinned", json!(true));
    let mut dialog = essay("Essay", 90);
    put(&mut dialog, "fixed_at", Value::Null);
    let got = show(edit(
        &[session],
        &assignments_of(json!({"essay": known_essay()})),
        &dialog,
        None,
        false,
        "unused",
    ));
    assert_eq!(
        got.as_ref()
            .map(|value| value.pointer("/blocks/0").cloned())
            .map_err(String::as_str),
        Ok(Some(dumped("s1", "Essay", 90, vec![2], Some("16:00"))))
    );
}

/// controller.py:917. A pin with no start, on a block this edit does not rewrite, is cleared.
#[test]
fn a_stale_pin_with_no_start_is_cleared() {
    let loose = json!({
        "id": "loose",
        "title": "Loose",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0, 1],
        "pinned": true
    });
    let got = show(edit(
        &[loose],
        &Map::new(),
        &essay("Essay", 90),
        None,
        false,
        "s-essay",
    ));
    assert_eq!(got.as_ref().map(|_| ()).map_err(String::as_str), Ok(()));
    let blocks = got
        .as_ref()
        .ok()
        .and_then(|value| value.get("blocks"))
        .and_then(|value| value.as_array())
        .cloned()
        .unwrap_or_default();
    assert!(!blocks.is_empty(), "the edit returns the week blocks");
    let mut found = Value::Null;
    for block in &blocks {
        if block.get("id").and_then(|id| id.as_str()) == Some("loose") {
            found = block.clone();
        }
    }
    assert_eq!(
        found,
        json!({
            "id": "loose",
            "title": "Loose",
            "kind": "flexible",
            "duration_min": 30,
            "days": [0, 1]
        })
    );
}

/// controller.py:914. Settle runs: a session that is not this homework loses a clashing start.
#[test]
fn settle_drops_a_session_that_no_longer_fits() {
    let mut homework = flexible("s1", "Essay", 90, vec![2]);
    put(&mut homework, "start", json!("16:00"));
    let math = json!({
        "id": "math",
        "title": "Math",
        "kind": "flexible",
        "duration_min": 30,
        "days": [2],
        "priority": 3,
        "energy": "medium",
        "start": "16:00"
    });
    let got = show(edit(
        &[homework, math],
        &assignments_of(json!({"essay": known_essay()})),
        &essay("Essay", 90),
        None,
        false,
        "unused",
    ));
    assert_eq!(got.as_ref().map(|_| ()).map_err(String::as_str), Ok(()));
    let lost = got
        .as_ref()
        .ok()
        .and_then(|value| value.get("lost"))
        .and_then(|value| value.as_array())
        .cloned()
        .unwrap_or_default();
    assert!(
        !lost.is_empty(),
        "settle reports the session that lost its time"
    );
    assert_eq!(
        lost.first().cloned().unwrap_or(Value::Null),
        json!({
            "block_id": "math",
            "assignment_id": Value::Null,
            "title": "Math",
            "day": 2,
            "start": "16:00",
            "message": "Math no longer fits Wednesday at 16:00: Essay is there now."
        })
    );
    let blocks = got
        .as_ref()
        .ok()
        .and_then(|value| value.get("blocks"))
        .and_then(|value| value.as_array())
        .cloned()
        .unwrap_or_default();
    assert!(!blocks.is_empty(), "the week still has its blocks");
    let mut math_after = Value::Null;
    for block in &blocks {
        if block.get("id").and_then(|id| id.as_str()) == Some("math") {
            math_after = block.clone();
        }
    }
    assert!(math_after.is_object(), "math is still in the week");
    assert_eq!(math_after.get("start"), None);
    let mut essay_after = Value::Null;
    for block in &blocks {
        if block.get("id").and_then(|id| id.as_str()) == Some("s1") {
            essay_after = block.clone();
        }
    }
    assert_eq!(
        essay_after.get("start").cloned().unwrap_or(Value::Null),
        json!("16:00")
    );
    assert_eq!(
        math_after.get("days").cloned().unwrap_or(Value::Null),
        json!([2])
    );
}

fn marked_or_stop(result: Result<MarkedHomework, String>, what: &str) -> Option<MarkedHomework> {
    match result {
        Ok(marked) => Some(marked),
        Err(error) => {
            assert_eq!(error, "", "{what}, got {error}");
            None
        }
    }
}

fn week_named<'a>(marked: &'a MarkedHomework, week_start: &str) -> Option<&'a MarkedWeek> {
    marked
        .weeks
        .iter()
        .find(|week| week.week_start == week_start)
}

/// `agenda.rs` `set_homework_done` 409-481 and
/// `set_homework_done_updates_the_assignment_and_session_together`.
#[test]
fn marking_homework_done_keeps_the_stamp_and_follows_every_session() {
    let assignment = json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-14T21:00",
        "estimate_min": 60,
        "focus_minutes": 0,
        "completed": false,
        "completed_at": "2026-10-01T08:00"
    });
    let session = json!({
        "id": "essay-session",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "days": [0],
        "start": "19:00",
        "duration_min": 60
    });
    let club = json!({
        "id": "club",
        "title": "Club",
        "kind": "locked",
        "days": [1],
        "start": "16:00",
        "duration_min": 60
    });
    let mut assignments = Map::new();
    assignments.insert("essay".into(), assignment.clone());
    let result = mark_homework_done(
        "essay",
        &assignment,
        &assignments,
        &[
            ("2026-10-12".into(), vec![session.clone()]),
            ("2026-10-19".into(), vec![club]),
            ("2026-10-26".into(), vec![session]),
        ],
        true,
        "2026-10-21T12:00",
    );
    let Some(marked) = marked_or_stop(
        result,
        "agenda.rs 415 keeps a completed_at that is already set, and 451 updates every week that holds a session",
    ) else {
        return;
    };
    assert_eq!(marked.assignment["completed"], json!(true));
    assert_eq!(
        marked.assignment["completed_at"],
        json!("2026-10-01T08:00"),
        "agenda.rs 413 keeps the existing stamp instead of the new one"
    );
    assert!(
        !marked.weeks.is_empty(),
        "weeks that hold a session must be returned"
    );
    assert_eq!(
        marked.weeks.len(),
        2,
        "a week with no session for this homework is left out, got {:?}",
        marked
            .weeks
            .iter()
            .map(|week| &week.week_start)
            .collect::<Vec<_>>()
    );
    assert!(
        week_named(&marked, "2026-10-19").is_none(),
        "agenda.rs 483 skips a week that has no session for this homework"
    );
    for start in ["2026-10-12", "2026-10-26"] {
        let Some(week) = week_named(&marked, start) else {
            assert_eq!(start, "", "{start} must be updated");
            return;
        };
        assert!(
            !week.blocks.is_empty(),
            "{start} must still hold the session"
        );
        let block = &week.blocks[0];
        assert_eq!(block["completed"], json!(true), "{start}");
        assert_eq!(
            block["completed_day"],
            json!(0),
            "agenda.rs 478 sets completed_day to the session's only day, {start}"
        );
        assert_eq!(block["start"], json!("19:00"), "{start}");
    }
}

/// `agenda.rs` 415-417. An empty stamp is replaced by the one the caller gives.
#[test]
fn marking_homework_done_with_no_stamp_uses_the_given_one() {
    let assignment = json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-14T21:00",
        "estimate_min": 60,
        "completed": false,
        "completed_at": ""
    });
    let session = json!({
        "id": "essay-session",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "days": [2],
        "start": "16:00",
        "duration_min": 60
    });
    let mut assignments = Map::new();
    assignments.insert("essay".into(), assignment.clone());
    let result = mark_homework_done(
        "essay",
        &assignment,
        &assignments,
        &[("2026-10-19".into(), vec![session])],
        true,
        "2026-10-21T12:00",
    );
    let Some(marked) = marked_or_stop(result, "agenda.rs 416 uses the given stamp") else {
        return;
    };
    assert_eq!(marked.assignment["completed_at"], json!("2026-10-21T12:00"));
    assert_eq!(
        marked.weeks.len(),
        1,
        "the week that holds the session is returned"
    );
    assert_eq!(marked.weeks[0].blocks[0]["completed_day"], json!(2));
}

/// `agenda.rs` 419 and 479. Reopening clears the stamp and the finished day.
#[test]
fn reopening_homework_clears_the_stamp_and_completed_day() {
    let assignment = json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-14T21:00",
        "estimate_min": 60,
        "completed": true,
        "completed_at": "2026-10-01T08:00"
    });
    let session = json!({
        "id": "essay-session",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "days": [0],
        "start": "19:00",
        "duration_min": 60,
        "completed": true,
        "completed_day": 0
    });
    let mut assignments = Map::new();
    assignments.insert("essay".into(), assignment.clone());
    let result = mark_homework_done(
        "essay",
        &assignment,
        &assignments,
        &[("2026-10-12".into(), vec![session])],
        false,
        "2026-10-21T12:00",
    );
    let Some(marked) = marked_or_stop(result, "agenda.rs 419 clears completed_at") else {
        return;
    };
    assert_eq!(marked.assignment["completed"], json!(false));
    assert!(
        marked.assignment["completed_at"].is_null(),
        "agenda.rs 419 writes null, got {}",
        marked.assignment["completed_at"]
    );
    assert_eq!(marked.weeks.len(), 1);
    assert_eq!(marked.weeks[0].blocks[0]["completed"], json!(false));
    assert!(
        marked.weeks[0].blocks[0].get("completed_day").is_none(),
        "agenda.rs 480 removes completed_day when the homework is reopened"
    );
    assert_eq!(marked.weeks[0].blocks[0]["start"], json!("19:00"));
}

/// `agenda.rs` 471. A session on more than one day does not record completed_day.
#[test]
fn a_session_on_several_days_does_not_record_completed_day() {
    let assignment = json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-14T21:00",
        "estimate_min": 60,
        "completed": false
    });
    let session = json!({
        "id": "essay-session",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "days": [0, 2],
        "start": "19:00",
        "duration_min": 60
    });
    let mut assignments = Map::new();
    assignments.insert("essay".into(), assignment.clone());
    let result = mark_homework_done(
        "essay",
        &assignment,
        &assignments,
        &[("2026-10-12".into(), vec![session])],
        true,
        "2026-10-21T12:00",
    );
    let Some(marked) = marked_or_stop(result, "agenda.rs 471 requires one day") else {
        return;
    };
    assert_eq!(marked.weeks[0].blocks[0]["completed"], json!(true));
    assert!(
        marked.weeks[0].blocks[0].get("completed_day").is_none(),
        "a session on two days does not get completed_day, got {}",
        marked.weeks[0].blocks[0]
    );
}

/// `agenda.rs` 408.
#[test]
fn homework_that_is_not_an_object_is_refused() {
    let result = mark_homework_done(
        "essay",
        &Value::Null,
        &Map::new(),
        &[],
        true,
        "2026-10-21T12:00",
    );
    assert_eq!(
        result.map(|_| ()),
        Err("stored homework is not an object".to_string()),
        "agenda.rs 408 refuses a stored homework that is not an object"
    );
}
