//! `desktop/native/controller.py` `delete_block` (1750-1771) and
//! `grid.rs` `delete_occurrence`. School or a Setup activity taken out of this week keeps a copy
//! with its removed days, or the standing week would bring it back.

use flexweek_engine::desk::blocks::{BlockDeletion, delete_block, mark_block_done, until_problem};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-10-19";
const TODAY: &str = "2026-10-21";
const NOW_MINUTE: i64 = 12 * 60;

fn show(result: Result<BlockDeletion, String>) -> Result<Value, String> {
    result.map(|edit| {
        json!({
            "label": edit.label,
            "blocks": edit.blocks,
            "lost": edit.lost,
        })
    })
}

fn delete(
    blocks: &[Value],
    block_id: &str,
    scope: &str,
    day: Option<i64>,
) -> Result<BlockDeletion, String> {
    delete_every(blocks, block_id, scope, day, false)
}

fn delete_every(
    blocks: &[Value],
    block_id: &str,
    scope: &str,
    day: Option<i64>,
    every_week: bool,
) -> Result<BlockDeletion, String> {
    delete_block(
        blocks,
        &Map::new(),
        WEEK,
        block_id,
        scope,
        day,
        TODAY,
        NOW_MINUTE,
        every_week,
    )
}

fn setup_ids() -> Vec<&'static str> {
    vec!["school", "sport", "activity-piano"]
}

fn club() -> Value {
    json!({
        "id": "club",
        "title": "Club",
        "kind": "locked",
        "duration_min": 60,
        "days": [0, 1, 2],
        "start": "15:00"
    })
}

/// controller.py:1544-1546. A missing id leaves the week alone.
#[test]
fn a_missing_block_is_left_alone() {
    let blocks = vec![club()];
    assert_eq!(
        show(delete(&blocks, "nope", "series", None)),
        Ok(json!({
            "label": Value::Null,
            "blocks": [club()],
            "lost": []
        }))
    );
}

/// controller.py:1547-1548. Scope series removes the whole block.
#[test]
fn deleting_a_series_removes_the_block() {
    let other = json!({"id": "other", "title": "Other", "kind": "flexible", "duration_min": 30, "days": [0]});
    assert_eq!(
        show(delete(&[club(), other.clone()], "club", "series", None)),
        Ok(json!({
            "label": "deleting Club",
            "blocks": [other],
            "lost": []
        }))
    );
}

/// controller.py:1550 and grid.rs delete_occurrence. One day of a series is removed.
#[test]
fn deleting_one_day_keeps_the_other_days() {
    let mut kept = club();
    if let Some(map) = kept.as_object_mut() {
        map.insert("days".into(), json!([0, 2]));
        map.insert("missed_days".into(), json!([]));
    }
    assert_eq!(
        show(delete(&[club()], "club", "occurrence", Some(1))),
        Ok(json!({
            "label": "deleting Club",
            "blocks": [kept],
            "lost": []
        }))
    );
}

/// controller.py:1547. A homework session is the whole block, even for one day.
#[test]
fn a_homework_session_is_removed_whole() {
    let session = json!({
        "id": "s1",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": [0, 1],
        "assignment_id": "essay"
    });
    let other = json!({"id": "other", "title": "Other"});
    assert_eq!(
        show(delete(
            &[session, other.clone()],
            "s1",
            "occurrence",
            Some(0)
        )),
        Ok(json!({
            "label": "deleting Essay",
            "blocks": [other],
            "lost": []
        }))
    );
}

/// controller.py:1763-1768. School, the old sport card, and a Setup activity taken out of this week
/// stay in it missed on every day they were on; taken out of every week they are gone.
#[test]
fn school_and_activities_this_week_keep_removed_days_and_every_week_go() {
    let ids = setup_ids();
    assert!(!ids.is_empty(), "the setup ids are listed");
    for id in ids {
        let block = json!({
            "id": id,
            "title": "School",
            "kind": "locked",
            "duration_min": 60,
            "days": [0, 3],
            "start": "08:30"
        });
        let mut removed = block.clone();
        removed["removed_days"] = json!([0, 3]);
        assert_eq!(
            show(delete(std::slice::from_ref(&block), id, "series", None)),
            Ok(json!({"label": "deleting School", "blocks": [removed], "lost": []})),
            "{id} this week"
        );
        assert_eq!(
            show(delete_every(
                std::slice::from_ref(&block),
                id,
                "series",
                None,
                true
            )),
            Ok(json!({"label": "deleting School", "blocks": [], "lost": []})),
            "{id} every week"
        );
        let mut monday = block.clone();
        monday["days"] = json!([0]);
        monday["missed_days"] = json!([]);
        assert_eq!(
            show(delete(&[block], id, "occurrence", Some(3))),
            Ok(json!({"label": "deleting School", "blocks": [monday], "lost": []})),
            "{id} one day of it keeps the other day"
        );
    }
}

/// Jonathan, 2026-11-26 ("Disappear too"): "This day only" on School or an activity makes that day
/// disappear, even when it is the last day left. It is never marked missed.
#[test]
fn this_day_only_on_the_last_day_of_a_standing_block_removes_it_not_misses_it() {
    for id in setup_ids() {
        let last = json!({"id": id, "title": "School", "kind": "locked", "duration_min": 60,
                          "days": [3], "start": "08:30"});
        let mut removed = last.clone();
        removed["removed_days"] = json!([3]);
        assert_eq!(
            show(delete(
                std::slice::from_ref(&last),
                id,
                "occurrence",
                Some(3)
            )),
            Ok(json!({"label": "deleting School", "blocks": [removed], "lost": []})),
            "{id} one-day piece"
        );
        let mut missed = last.clone();
        missed["missed_days"] = json!([3]);
        let mut removed_over_missed = last.clone();
        removed_over_missed["removed_days"] = json!([3]);
        assert_eq!(
            show(delete(&[missed], id, "occurrence", Some(3))),
            Ok(json!({"label": "deleting School", "blocks": [removed_over_missed], "lost": []})),
            "{id} a missed last day disappears too"
        );
    }
}

/// controller.py:1559 calls _touch, so a session that no longer fits loses its start.
#[test]
fn deleting_runs_settle() {
    let essay = json!({
        "id": "s-essay",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": [2],
        "start": "16:00"
    });
    let math = json!({
        "id": "s-math",
        "title": "Math",
        "kind": "flexible",
        "duration_min": 30,
        "days": [2],
        "start": "16:00"
    });
    let choir = json!({
        "id": "choir",
        "title": "Choir",
        "kind": "locked",
        "duration_min": 60,
        "days": [2],
        "start": "18:00"
    });
    let got = show(delete(&[essay, math, choir], "choir", "series", None));
    assert_eq!(got.as_ref().map(|_| ()).map_err(String::as_str), Ok(()));
    let lost = got
        .as_ref()
        .ok()
        .and_then(|value| value.get("lost"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    assert!(
        !lost.is_empty(),
        "settle reports the session that lost its time"
    );
    assert_eq!(
        lost.first()
            .cloned()
            .unwrap_or(Value::Null)
            .pointer("/message")
            .cloned(),
        Some(json!(
            "Math no longer fits Wednesday at 16:00: Essay is there now."
        ))
    );
}

/// `agenda.rs` `set_block_done` 350-366, and
/// `set_block_done_sets_both_completion_fields_and_is_retry_safe`.
#[test]
fn marking_a_block_done_sets_completed_and_completed_day() {
    let mut blocks = vec![
        json!({"id":"session","title":"Reading","kind":"flexible","days":[0],"start":"10:00","duration_min":30}),
        json!({"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":60}),
    ];
    let marked = mark_block_done(&mut blocks, "session", 0, true);
    assert_eq!(
        marked,
        Ok(()),
        "agenda.rs 362 sets completed on the block that was named"
    );
    assert_eq!(blocks[0]["completed"], json!(true));
    assert_eq!(
        blocks[0]["completed_day"],
        json!(0),
        "agenda.rs 364 records the day when it is one of the block's days"
    );
    assert_eq!(blocks[0]["start"], json!("10:00"));
    let school = mark_block_done(&mut blocks, "school", 0, true);
    assert_eq!(school, Ok(()), "a locked block can be marked done");
    assert_eq!(blocks[1]["completed"], json!(true));
    assert!(
        blocks[1].get("completed_day").is_none(),
        "agenda.rs 366 leaves completed_day off a block that is not a started flexible session, got {}",
        blocks[1]
    );
}

/// `agenda.rs` 359. A day the block does not have is refused and writes nothing.
#[test]
fn marking_done_on_a_foreign_day_is_refused() {
    let mut blocks = vec![
        json!({"id":"session","title":"Reading","kind":"flexible","days":[0],"start":"10:00","duration_min":30}),
    ];
    let refused = mark_block_done(&mut blocks, "session", 3, true);
    assert_eq!(
        refused,
        Err("day is not one of the block's days".to_string()),
        "agenda.rs 359 refuses a day the block does not have"
    );
    assert!(
        blocks[0].get("completed").is_none(),
        "a refused day does not set completed, got {}",
        blocks[0]
    );
}

/// `agenda.rs` 362-366. Reopening clears the finished day.
#[test]
fn reopening_a_block_clears_completed_day() {
    let mut blocks = vec![json!({
        "id": "session",
        "kind": "flexible",
        "days": [0],
        "start": "10:00",
        "completed": true,
        "completed_day": 0
    })];
    let opened = mark_block_done(&mut blocks, "session", 4, false);
    assert_eq!(opened, Ok(()), "reopening does not require the day");
    assert_eq!(blocks[0]["completed"], json!(false));
    assert!(
        blocks[0].get("completed_day").is_none(),
        "agenda.rs 366 removes completed_day when the block is not done, got {}",
        blocks[0]
    );
}

/// `agenda.rs` 346. An id that is not in the week is refused.
#[test]
fn marking_a_missing_block_is_refused() {
    let mut blocks = vec![json!({"id":"session","kind":"flexible","days":[0],"start":"10:00"})];
    let missing = mark_block_done(&mut blocks, "nope", 0, true);
    assert_eq!(
        missing,
        Err("block was not found".to_string()),
        "agenda.rs 346 refuses an id that is not in the week"
    );
}

// Until (#118): the last day a weekly time stands cannot come before the first day it holds that week.
#[test]
fn until_cannot_be_before_the_first_day_of_the_week_it_is_saved_from() {
    let guitar = |until: Value| json!({"id": "weekly-1", "days": [1, 3], "until": until});
    // The week of Monday 23 November 2026: Guitar's first day is Tuesday 24 November.
    let week = "2026-11-23";
    assert_eq!(
        until_problem(&guitar(json!("2026-11-23")), week, "2026-11-20")
            .unwrap()
            .as_deref(),
        Some("Until can't be before the first day, Tue 24 Nov.")
    );
    assert_eq!(
        until_problem(&guitar(json!("2026-11-24")), week, "2026-11-20").unwrap(),
        None
    );
    assert_eq!(
        until_problem(&json!({"id": "weekly-1", "days": [1]}), week, "2026-11-20").unwrap(),
        None
    );
    assert_eq!(
        until_problem(&guitar(json!("24/11/2026")), week, "2026-11-20")
            .unwrap()
            .as_deref(),
        Some("Until isn't a date we can read.")
    );
    // Seen in another year, the date says its year.
    assert_eq!(
        until_problem(&guitar(json!("2026-11-23")), week, "2025-12-01")
            .unwrap()
            .as_deref(),
        Some("Until can't be before the first day, Tue 24 Nov 2026.")
    );
}
