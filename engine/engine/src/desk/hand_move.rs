//! A block let go at a new day and time by hand: the one rule the phone, the desktop and a coming
//! MCP server share.

use serde_json::{Value, json};

use crate::desk::calendar::is_series_checked;
use crate::desk::grid::{
    apply_block_edit, apply_block_times, linked_homework, past_problem, span_clash, span_problem,
};
use crate::desk::planning::due_point;
use crate::desk::pydate::from_iso;
use crate::desk::pyops::{contains, get, iterate};
use crate::error::{EngineError, EngineResult};
use crate::stored::truthy;
use crate::time::{hhmm_to_minutes, minutes_to_hhmm};

type Fresh<'a> = &'a mut dyn FnMut() -> String;

const DAYS_IN_WEEK: i64 = 7;
const NOT_FOUND: &str = "That block is not in this week, so nothing moved.";
const FINISHED: &str = "That's finished, so it stayed where it was.";
const NO_SUCH_DAY: &str = "That day is not in this week, so it stayed where it was.";
const NOT_ON_DAY: &str = "That block is not on that day, so it stayed where it was.";
const END_BEFORE_START: &str = "The end has to come after the start, so it stayed where it was.";
const NO_TIME_TO_MOVE: &str = "That has no time to move, so it stayed where it was.";

/// Where the block was let go, in the week's day numbers (0 is Monday) and minutes of the day.
/// `from_day` is the day it was dragged from, or -1 for homework that has no day yet.
pub struct HandDrop<'a> {
    pub block_id: &'a str,
    pub from_day: i64,
    pub to_day: i64,
    pub start_min: i64,
    pub end_min: i64,
}

/// The week being edited and the local date and minute it is now.
pub struct WeekClock<'a> {
    pub week_start: &'a str,
    pub now_iso: &'a str,
    pub now_min: i64,
}

pub enum HandMove {
    Moved {
        blocks: Vec<Value>,
        /// The block that moved: a new id when one day was split off a repeating block.
        block_id: String,
        /// Another block already there, which is allowed and said.
        beside: Option<String>,
    },
    Refused(String),
}

impl HandMove {
    /// The answer as the bindings pass it on: `moved` with the week's blocks, the block that moved
    /// and any block beside it, or not moved with the words why.
    pub fn to_value(&self) -> Value {
        match self {
            Self::Moved {
                blocks,
                block_id,
                beside,
            } => json!({"moved": true, "blocks": blocks, "block_id": block_id, "beside": beside}),
            Self::Refused(words) => json!({"moved": false, "problem": words}),
        }
    }
}

fn refused(words: &str) -> EngineResult<HandMove> {
    Ok(HandMove::Refused(words.to_string()))
}

fn id_of(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str)
}

/// Why a start is already past, in the calendar's words, or None. Finished homework may sit in the
/// past, and a drag that leaves the start where it was (the end moved) is never refused for that.
/// A fixed time already on a day before today may still change its start there.
fn past_words(
    block: &Value,
    clock: &WeekClock<'_>,
    drop: &HandDrop<'_>,
) -> EngineResult<Option<String>> {
    if truthy(get(block, "completed")?) {
        return Ok(None);
    }
    if drop.from_day == drop.to_day
        && let Some(held) = get(block, "start")?.and_then(Value::as_str)
        && hhmm_to_minutes(held).is_ok_and(|minutes| minutes == drop.start_min)
    {
        return Ok(None);
    }
    let Some(words) = past_problem(
        clock.week_start,
        drop.to_day,
        drop.start_min,
        clock.now_iso,
        clock.now_min,
    )?
    else {
        return Ok(None);
    };
    if get(block, "kind")?.and_then(Value::as_str) == Some("locked") && drop.from_day == drop.to_day
    {
        let Ok(monday) = from_iso(clock.week_start) else {
            return Ok(Some(words));
        };
        let on = crate::stored::add_days(monday, drop.to_day)?;
        return Ok((on >= from_iso(clock.now_iso)?).then_some(words));
    }
    Ok(Some(words))
}

fn replacing(all: Vec<Value>, id: &str, updated: Value) -> Vec<Value> {
    all.into_iter()
        .map(|item| {
            if id_of(&item) == Some(id) {
                updated.clone()
            } else {
                item
            }
        })
        .collect()
}

/// Homework that needs a time gets the one it was let go at; a block that repeats moves only the
/// day it was dragged from; anything else moves. Homework moved this way is pinned, so no plan
/// moves it back. `assignments` is the week's homework keyed by id, for the due time.
pub fn hand_move(
    blocks: &Value,
    drop: &HandDrop<'_>,
    clock: &WeekClock<'_>,
    assignments: &Value,
    fresh: Fresh<'_>,
) -> EngineResult<HandMove> {
    let all = iterate(blocks)?;
    let Some(block) = all.iter().find(|item| id_of(item) == Some(drop.block_id)) else {
        return refused(NOT_FOUND);
    };
    if !(0..DAYS_IN_WEEK).contains(&drop.to_day) {
        return refused(NO_SUCH_DAY);
    }
    if drop.end_min <= drop.start_min {
        return refused(END_BEFORE_START);
    }
    if let Some(words) = past_words(block, clock, drop)? {
        return Ok(HandMove::Refused(words));
    }
    let due = match get(block, "assignment_id")?.and_then(Value::as_str) {
        Some(assignment_id) => match assignments.get(assignment_id).and_then(|a| a.get("due")) {
            Some(held) => due_point(held, clock.week_start)?,
            None => None,
        },
        None => None,
    };
    let (due, due_type) = match due {
        Some((day, minutes)) => (json!([day, minutes]), "tuple"),
        None => (Value::Null, "NoneType"),
    };
    if let Some(words) = span_problem(drop.to_day, drop.start_min, drop.end_min, &due, due_type)? {
        return refused(words);
    }
    let beside = span_clash(
        blocks,
        &json!(drop.block_id),
        &json!(drop.to_day),
        drop.start_min,
        drop.end_min,
    )?;
    let start_text = minutes_to_hhmm(drop.start_min);
    if !truthy(get(block, "start")?) {
        if get(block, "kind")?.and_then(Value::as_str) != Some("flexible") {
            return refused(NO_TIME_TO_MOVE);
        }
        if truthy(get(block, "completed")?) {
            return refused(FINISHED);
        }
        let mut placed = block.clone();
        if let Value::Object(fields) = &mut placed {
            fields.insert("start".into(), json!(start_text));
            fields.insert("days".into(), json!([drop.to_day]));
            fields.insert("duration_min".into(), json!(drop.end_min - drop.start_min));
            fields.insert("pinned".into(), json!(true));
        }
        return Ok(HandMove::Moved {
            blocks: replacing(all.clone(), drop.block_id, placed),
            block_id: drop.block_id.to_string(),
            beside,
        });
    }
    if is_series_checked(block)? {
        let origin = if contains(
            &get(block, "days")?.cloned().unwrap_or(json!([])),
            &json!(drop.from_day),
        )? {
            drop.from_day
        } else if contains(
            &get(block, "days")?.cloned().unwrap_or(json!([])),
            &json!(drop.to_day),
        )? {
            drop.to_day
        } else {
            return refused(NOT_ON_DAY);
        };
        let mut moved = block.clone();
        if let Value::Object(fields) = &mut moved {
            fields.insert("start".into(), json!(start_text));
            fields.insert("duration_min".into(), json!(drop.end_min - drop.start_min));
        }
        let before: Vec<String> = all
            .iter()
            .filter_map(|item| id_of(item).map(String::from))
            .collect();
        let edited = apply_block_edit(blocks, &moved, &json!("occurrence"), &json!(origin), fresh)?;
        let made = edited
            .iter()
            .filter_map(|item| id_of(item))
            .find(|id| !before.iter().any(|seen| seen == id))
            .unwrap_or(drop.block_id)
            .to_string();
        let blocks = edited
            .into_iter()
            .map(|mut item| {
                if id_of(&item) == Some(made.as_str())
                    && let Value::Object(fields) = &mut item
                {
                    fields.insert("days".into(), json!([drop.to_day]));
                }
                item
            })
            .collect();
        return Ok(HandMove::Moved {
            blocks,
            block_id: made,
            beside,
        });
    }
    let Some(mut updated) =
        apply_block_times(block, drop.start_min, drop.end_min, Some(drop.to_day))?
    else {
        return Err(EngineError::value("hand move found no times to apply"));
    };
    if linked_homework(&updated)?
        && let Value::Object(fields) = &mut updated
    {
        fields.insert("pinned".into(), json!(true));
    }
    Ok(HandMove::Moved {
        blocks: replacing(all, drop.block_id, updated),
        block_id: drop.block_id.to_string(),
        beside,
    })
}
