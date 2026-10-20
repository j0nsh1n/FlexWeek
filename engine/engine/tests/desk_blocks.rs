//! `desktop/native/controller.py` `delete_block` (1538-1559) and
//! `grid.rs` `delete_occurrence`. Setup blocks are refused (decision Q5).

use flexweek_engine::desk::blocks::{BlockDeletion, SETUP_BLOCK, delete_block, mark_block_done};
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
    delete_block(
        blocks,
        &Map::new(),
        WEEK,
        block_id,
        scope,
        day,
        TODAY,
        NOW_MINUTE,
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

/// Decision Q5. School, the old sport card, and a Setup activity are refused.
#[test]
fn school_and_activities_are_refused() {
    let ids = setup_ids();
    assert!(!ids.is_empty(), "the setup ids are listed");
    for id in ids {
        let block = json!({
            "id": id,
            "title": "School",
            "kind": "locked",
            "duration_min": 60,
            "days": [0],
            "start": "08:30"
        });
        assert_eq!(
            delete(&[block], id, "series", None).map(|_| ()),
            Err(SETUP_BLOCK.to_string()),
            "{id}"
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
