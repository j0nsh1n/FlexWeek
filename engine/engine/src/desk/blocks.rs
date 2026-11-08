//! `desktop/native/controller.py` `delete_block` (1750-1771).

use serde_json::{Map, Value, json};

use super::{grid, planning};
use crate::model;
use crate::stored::truthy;

pub struct BlockDeletion {
    pub blocks: Vec<Value>,
    pub label: Option<String>,
    pub lost: Vec<Value>,
}

pub fn delete_block(
    blocks: &[Value],
    assignments: &Map<String, Value>,
    week_start: &str,
    block_id: &str,
    scope: &str,
    day: Option<i64>,
    today: &str,
    now_minute: i64,
    every_week: bool,
) -> Result<BlockDeletion, String> {
    let Some(block) = blocks
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(block_id))
    else {
        return Ok(BlockDeletion {
            blocks: blocks.to_vec(),
            label: None,
            lost: Vec::new(),
        });
    };
    let mut removed: Vec<Value> = if truthy(block.get("assignment_id")) || scope != "occurrence" {
        blocks
            .iter()
            .filter(|item| item.get("id").and_then(Value::as_str) != Some(block_id))
            .cloned()
            .collect()
    } else {
        let day_value = day.map_or(Value::Null, Value::from);
        grid::delete_occurrence(&Value::Array(blocks.to_vec()), &json!(block_id), &day_value)
            .map_err(|err| err.message)?
    };
    // School or a Setup activity stands in every week, so taking it out of this week alone keeps
    // it here missed on every day, or the standing week would bring it back. `every_week` is the
    // caller's to take out of the standing week too.
    let gone = !removed
        .iter()
        .any(|item| item.get("id").and_then(Value::as_str) == Some(block_id));
    if gone && !every_week && grid::is_setup_block(block).map_err(|err| err.message)? {
        let mut missed = block.clone();
        let days = block.get("days").cloned().unwrap_or_else(|| json!([]));
        if let Some(fields) = missed.as_object_mut() {
            fields.insert("missed_days".into(), days);
        }
        removed.push(missed);
    }
    let title = match block.get("title") {
        Some(Value::String(text)) => text.clone(),
        _ => return Err("'title'".to_string()),
    };
    let (cleared, lost) = touch(removed, assignments, week_start, today, now_minute)?;
    Ok(BlockDeletion {
        blocks: cleared,
        label: Some(format!("deleting {title}")),
        lost,
    })
}

/// `agenda.rs` `set_block_done`. School and activities stay a caller's guard.
pub fn mark_block_done(
    blocks: &mut [Value],
    block_id: &str,
    day: i64,
    done: bool,
) -> Result<(), String> {
    let Some(block) = blocks
        .iter_mut()
        .find(|block| block.get("id").and_then(Value::as_str) == Some(block_id))
    else {
        return Err("block was not found".into());
    };
    let object = block
        .as_object_mut()
        .ok_or_else(|| "stored block is not an object".to_string())?;
    let flexible = object.get("kind").and_then(Value::as_str) == Some("flexible");
    let has_start = object
        .get("start")
        .and_then(Value::as_str)
        .is_some_and(|start| !start.is_empty());
    let day_ok = object
        .get("days")
        .and_then(Value::as_array)
        .is_some_and(|days| days.iter().any(|value| value.as_i64() == Some(day)));
    if done && flexible && has_start && !day_ok {
        return Err("day is not one of the block's days".into());
    }
    object.insert("completed".into(), json!(done));
    if done && flexible && has_start && day_ok {
        object.insert("completed_day".into(), json!(day));
    } else {
        object.shift_remove("completed_day");
    }
    Ok(())
}

fn touch(
    blocks: Vec<Value>,
    assignments: &Map<String, Value>,
    week_start: &str,
    today: &str,
    now_minute: i64,
) -> Result<(Vec<Value>, Vec<Value>), String> {
    let overdue = overdue_ids(assignments, today, now_minute)?;
    let mut after_deadline = Vec::new();
    for block in &blocks {
        let link = block.get("assignment_id").and_then(Value::as_str);
        if truthy(block.get("start"))
            && link.is_some_and(|id| overdue.iter().any(|item| item == id))
            && let Some(id) = block.get("id")
        {
            after_deadline.push(id.clone());
        }
    }
    let (settled, lost) = planning::settle_placements_after_deadline(
        &Value::Array(blocks),
        &Value::Object(assignments.clone()),
        week_start,
        &json!([]),
        true,
        &Value::Array(after_deadline),
    )
    .map_err(|err| err.message)?;
    let cleared = planning::clear_stale_pins(&settled).map_err(|err| err.message)?;
    Ok((cleared, lost))
}

fn overdue_ids(
    assignments: &Map<String, Value>,
    today: &str,
    now_minute: i64,
) -> Result<Vec<String>, String> {
    let today_day = model::iso_day(today).map_err(|err| err.message)?;
    let mut ids = Vec::new();
    for (key, item) in assignments {
        if !truthy(item.get("due")) || truthy(item.get("completed")) {
            continue;
        }
        let Some(due) = item.get("due").and_then(Value::as_str) else {
            return Err(
                "must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with no seconds or timezone".into(),
            );
        };
        let (due_day, due_minute) = model::parse_due(due).map_err(|err| err.message)?;
        if (due_day, due_minute) <= (today_day, now_minute) {
            ids.push(key.clone());
        }
    }
    Ok(ids)
}
