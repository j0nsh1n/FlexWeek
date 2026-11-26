//! What the session decides when a block is added, moved by hand, deleted, or when the standing
//! repeats change (P4 slice 4B): the rules of `desktop/native/controller.py`'s `add_block`,
//! `hand_move`, `delete_block`, `setup_repeats`, `change_repeats` and `_stamp_edited`, moved here with
//! the same words. The window keeps the state: it writes what is decided here, then settles the week
//! (`_touch`), which this module does not. `_hold_repeats`, `_acknowledge_repeats`, drag retry, the
//! setup queue and save orchestration stay in Python.

use flexweek_engine::desk::calendar::is_series_checked;
use flexweek_engine::desk::grid::{
    apply_block_edit as grid_apply, delete_occurrence, is_standing_block,
};
use flexweek_engine::shown::{
    apply_repeats_to_shown_week, family_id, replaced_repeat_on_shown_week,
};
use flexweek_engine::stored::truthy;
use flexweek_engine::{EngineError, ErrorKind, repeats};
use flexweek_service::blocks::check_block;
use serde_json::{Value, json};

fn rows<'a>(value: &'a Value, what: &str) -> Result<&'a Vec<Value>, EngineError> {
    value.as_array().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: format!("{what} are a list"),
    })
}

/// The changes as the save sends them. `keep` stays as the form built it.
fn stamp_edited(
    changes: &[Value],
    edited: &str,
    today: &str,
    first_weekday: i64,
) -> Result<Vec<Value>, EngineError> {
    if edited == "keep" {
        return Ok(changes.to_vec());
    }
    changes
        .iter()
        .map(|change| {
            let mut item = change.as_object().cloned().ok_or_else(|| EngineError {
                kind: ErrorKind::Type,
                message: "every change is an object".to_string(),
            })?;
            item.insert("edited".into(), json!(edited));
            if edited == "from_today" {
                item.insert("today".into(), json!(today));
                item.insert("first_weekday".into(), json!(first_weekday));
            }
            Ok(Value::Object(item))
        })
        .collect()
}

/// What `apply_block_edit` needs: the week as it stands, the block as the dialog built it, the scope
/// (`series` or `occurrence`) and day the edit is for, and the id one split-off day would take (used
/// at most once: one edit splits off one day).
pub struct BlockEditInput<'a> {
    pub blocks: &'a Value,
    pub block: &'a Value,
    pub scope: &'a str,
    pub day: Option<i64>,
    pub new_id: &'a str,
}

#[derive(Debug, PartialEq)]
pub struct BlockEdit {
    pub blocks: Vec<Value>,
    pub label: String,
    pub block_id: String,
}

impl BlockEdit {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "label": self.label,
            "block_id": self.block_id,
        })
    }
}

fn checked_title(block: &Value) -> Result<&str, EngineError> {
    block
        .get("title")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::key("title"))
}

/// An added or edited block on the week, checked as a save checks it, with the words for its Undo
/// step: `editing ` when its id is already there, `adding ` otherwise.
pub fn apply_block_edit(input: &BlockEditInput) -> Result<BlockEdit, EngineError> {
    let blocks = rows(input.blocks, "blocks")?;
    let checked = check_block(input.block).map_err(|refused| EngineError::value(refused.0))?;
    let id = checked
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::key("id"))?;
    let verb = if blocks
        .iter()
        .any(|item| item.get("id").and_then(Value::as_str) == Some(id))
    {
        "editing "
    } else {
        "adding "
    };
    let label = format!("{verb}{}", checked_title(&checked)?);
    let scope = json!(input.scope);
    let day = input.day.map(Value::from).unwrap_or(Value::Null);
    let mut fresh = Some(input.new_id.to_string());
    let mut take_fresh = || fresh.take().unwrap_or_else(|| input.new_id.to_string());
    let edited = grid_apply(
        &Value::Array(blocks.clone()),
        &checked,
        &scope,
        &day,
        &mut take_fresh,
    )?;
    Ok(BlockEdit {
        blocks: edited,
        label,
        block_id: id.to_string(),
    })
}

/// What `apply_hand_move` needs: the week as it stands, the hand-move rule's answer, and the id the
/// student dropped.
pub struct HandMoveInput<'a> {
    pub blocks: &'a Value,
    pub answer: &'a Value,
    pub block_id: &'a str,
}

#[derive(Debug, PartialEq)]
pub struct HandMove {
    pub moved: bool,
    pub blocks: Vec<Value>,
    /// The block that moved: a new id when one day split off a repeating block.
    pub block_id: Option<String>,
    pub label: Option<String>,
    pub problem: Option<String>,
}

impl HandMove {
    pub fn to_json(&self) -> Value {
        json!({
            "moved": self.moved,
            "blocks": self.blocks,
            "block_id": self.block_id,
            "label": self.label,
            "problem": self.problem,
        })
    }
}

/// The hand-move answer applied: the week's blocks and the words for its Undo step, or the words
/// saying why nothing moved. The block the words name is the one dropped: one with no start is
/// placed, a repeating one moves on one day, anything else is edited.
pub fn apply_hand_move(input: &HandMoveInput) -> Result<HandMove, EngineError> {
    let answer = input.answer.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: "the hand-move answer is an object".to_string(),
    })?;
    let moved = answer
        .get("moved")
        .and_then(Value::as_bool)
        .ok_or_else(|| EngineError::value("the hand-move answer says moved"))?;
    let blocks = rows(input.blocks, "blocks")?.clone();
    if !moved {
        let problem = answer
            .get("problem")
            .and_then(Value::as_str)
            .ok_or_else(|| EngineError::key("problem"))?;
        return Ok(HandMove {
            moved: false,
            blocks,
            block_id: None,
            label: None,
            problem: Some(problem.to_string()),
        });
    }
    let after = rows(answer.get("blocks").unwrap_or(&Value::Null), "blocks")?.clone();
    let kept = answer
        .get("block_id")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::key("block_id"))?;
    let label = match blocks
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(input.block_id))
    {
        None => None,
        Some(block) if !truthy(block.get("start")) => {
            Some(format!("placing {}", checked_title(block)?))
        }
        Some(block) if is_series_checked(block)? => {
            Some(format!("moving {} on one day", checked_title(block)?))
        }
        Some(block) => Some(format!("editing {}", checked_title(block)?)),
    };
    Ok(HandMove {
        moved: true,
        blocks: after,
        block_id: Some(kept.to_string()),
        label,
        problem: None,
    })
}

/// What `delete_block` needs: the week and the standing repeats as they stand, which block goes, the
/// scope (`series` or `occurrence`) and day the delete is for, whether the standing week loses it too,
/// the selected block (cleared when it is the one going), and the Undo step's words (or none for the
/// usual `deleting ` words).
pub struct BlockDeleteInput<'a> {
    pub blocks: &'a Value,
    pub repeats: &'a Value,
    pub block_id: &'a str,
    pub scope: &'a str,
    pub day: Option<i64>,
    pub every_week: bool,
    pub selected_id: Option<&'a str>,
    pub label: Option<&'a str>,
}

#[derive(Debug, PartialEq)]
pub struct BlockDelete {
    pub blocks: Vec<Value>,
    pub repeats: Vec<Value>,
    /// Whether the window clears its selection: it pointed at the block going away.
    pub clear_selection: bool,
    pub label: String,
}

impl BlockDelete {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "repeats": self.repeats,
            "clear_selection": self.clear_selection,
            "label": self.label,
        })
    }
}

/// A deleted block. Homework and anything but one occurrence take the whole family: School split at a
/// week's seam is School on each side, so all of it goes together. A standing block deleted for this
/// week alone stays here missed on every day, or the standing week would bring it back. `None` when
/// the block is not in this week: nothing goes.
pub fn delete_block(input: &BlockDeleteInput) -> Result<Option<BlockDelete>, EngineError> {
    let blocks = rows(input.blocks, "blocks")?.clone();
    let repeats = rows(input.repeats, "repeats")?.clone();
    let Some(block) = blocks
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(input.block_id))
        .cloned()
    else {
        return Ok(None);
    };
    let setup = is_standing_block(&block)?;
    let family = family_id(input.block_id).to_string();
    let (kept, gone) = if truthy(block.get("assignment_id")) || input.scope != "occurrence" {
        let mut kept = Vec::new();
        let mut gone = Vec::new();
        for item in blocks {
            let same = item.get("id").and_then(Value::as_str) == Some(input.block_id)
                || (setup
                    && item
                        .get("id")
                        .and_then(Value::as_str)
                        .is_some_and(|id| family_id(id) == family));
            if same {
                gone.push(item);
            } else {
                kept.push(item);
            }
        }
        (kept, gone)
    } else {
        let day = input.day.map(Value::from).unwrap_or(Value::Null);
        let block_id = json!(input.block_id);
        let kept = delete_occurrence(&Value::Array(blocks), &block_id, &day)?;
        let gone = if kept
            .iter()
            .any(|item| item.get("id").and_then(Value::as_str) == Some(input.block_id))
        {
            Vec::new()
        } else {
            vec![block.clone()]
        };
        (kept, gone)
    };
    let repeats_after = if setup && !gone.is_empty() && input.every_week {
        repeats
            .into_iter()
            .filter(|item| item.get("id").and_then(Value::as_str) != Some(family.as_str()))
            .collect()
    } else {
        repeats
    };
    let blocks_after = if setup && !gone.is_empty() && !input.every_week {
        let mut after = kept;
        after.extend(gone.iter().map(|item| {
            let mut missed = item.as_object().cloned().unwrap_or_default();
            let days = item
                .get("days")
                .and_then(Value::as_array)
                .map(|days| json!(days))
                .unwrap_or(json!([]));
            missed.insert("missed_days".into(), days);
            Value::Object(missed)
        }));
        after
    } else {
        kept
    };
    let label = match input.label {
        Some(words) if !words.is_empty() => words.to_string(),
        _ => format!("deleting {}", checked_title(&block)?),
    };
    Ok(Some(BlockDelete {
        blocks: blocks_after,
        repeats: repeats_after,
        clear_selection: input.selected_id == Some(input.block_id),
        label,
    }))
}

/// What `repeat_edit` needs: the open week and the repeats standing in it, the repeats as the form
/// holds them now, the repeats the server last said, the held repeat intents (or none), and how a
/// later week with its own edit is treated (`keep`, `replace`, or `from_today`), with the student's
/// today and first weekday for a `from_today` change.
pub struct RepeatEditInput<'a> {
    pub blocks: &'a Value,
    pub repeats: &'a Value,
    pub after: &'a Value,
    pub saved_repeats: &'a Value,
    pub send: Option<&'a Value>,
    pub week_start: &'a str,
    pub edited: &'a str,
    pub today: &'a str,
    pub first_weekday: i64,
}

#[derive(Debug, PartialEq)]
pub struct RepeatEdit {
    pub blocks: Vec<Value>,
    pub repeats: Vec<Value>,
    /// The stamped intents the save carries: the window holds them until the server answers.
    pub stamped: Vec<Value>,
    /// The unstamped changes, as the preview question sends them.
    pub preview: Vec<Value>,
    /// Whether the change leaves the open week as it is: nothing on it is rewritten.
    pub leaves_week: bool,
}

impl RepeatEdit {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "repeats": self.repeats,
            "stamped": self.stamped,
            "preview": self.preview,
            "leaves_week": self.leaves_week,
        })
    }
}

/// The repeats become `after` from this week on. A repeat with a held intent changed again before the
/// server took the first is measured from what the server last said, so it carries both changes.
/// From today on, this week and every earlier week stay exactly as they are. `None` when nothing
/// changed.
pub fn repeat_edit(input: &RepeatEditInput) -> Result<Option<RepeatEdit>, EngineError> {
    let blocks = rows(input.blocks, "blocks")?.clone();
    let repeats = rows(input.repeats, "repeats")?.clone();
    let after = rows(input.after, "after")?.clone();
    let saved = rows(input.saved_repeats, "saved repeats")?.clone();
    let intents = repeats::intents_between(&repeats, &after, input.week_start);
    if intents.is_empty() {
        return Ok(None);
    }
    let changes: Vec<Value> = intents.iter().map(repeats::Intent::to_value).collect();
    let held: Vec<String> = match input.send {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(send)) => send
            .iter()
            .filter_map(|item| item.get("id").and_then(Value::as_str).map(str::to_string))
            .collect(),
        Some(_) => {
            return Err(EngineError {
                kind: ErrorKind::Type,
                message: "the held repeats are a list or null".to_string(),
            });
        }
    };
    let send = if held.iter().any(|id| {
        changes
            .iter()
            .any(|change| change.get("id").and_then(Value::as_str) == Some(id))
    }) {
        let saved_intents = repeats::intents_between(&saved, &after, input.week_start);
        let from_saved: std::collections::BTreeMap<&str, Value> = saved_intents
            .iter()
            .map(|intent| (intent.id.as_str(), intent.to_value()))
            .collect();
        changes
            .iter()
            .map(|change| {
                let id = change.get("id").and_then(Value::as_str).unwrap_or_default();
                if held.iter().any(|held| held == id) {
                    from_saved
                        .get(id)
                        .cloned()
                        .unwrap_or_else(|| change.clone())
                } else {
                    change.clone()
                }
            })
            .collect()
    } else {
        changes.clone()
    };
    let stamped = stamp_edited(&send, input.edited, input.today, input.first_weekday)?;
    let preview = changes;
    let first = stamped
        .first()
        .ok_or_else(|| EngineError::value("a repeat change is an object"))?;
    let leaves = repeats::leaves_week(
        &repeats::parse_intent(first).map_err(EngineError::value)?,
        input.week_start,
    )?;
    if leaves {
        return Ok(Some(RepeatEdit {
            blocks,
            repeats,
            stamped,
            preview,
            leaves_week: true,
        }));
    }
    let (blocks_after, repeats_after) = if input.edited == "replace" || input.edited == "from_today"
    {
        // Days on `after` count from Monday. The open week counts from its first day, so the engine
        // turns them. A stop has no body and comes off the week.
        let by_id: std::collections::BTreeMap<&str, &Value> = after
            .iter()
            .filter_map(|item| item.get("id").and_then(Value::as_str).map(|id| (id, item)))
            .collect();
        let mut week = blocks;
        for change in &preview {
            let id = change.get("id").and_then(Value::as_str).unwrap_or_default();
            week =
                replaced_repeat_on_shown_week(input.week_start, &week, id, by_id.get(id).copied())?;
        }
        (week, after)
    } else {
        let (week, standing) =
            apply_repeats_to_shown_week(input.week_start, &blocks, &repeats, &intents)
                .map_err(EngineError::value)?;
        (week, standing)
    };
    Ok(Some(RepeatEdit {
        blocks: blocks_after,
        repeats: repeats_after,
        stamped,
        preview,
        leaves_week: false,
    }))
}

/// The repeats after Setup: School and the activities as its page has them, and every weekly fixed
/// time the student made as it stands. Setup does not list those, so leaving them out would stop them.
pub fn setup_standing(blocks: &Value, repeats: &Value) -> Result<Vec<Value>, EngineError> {
    let mut made = Vec::new();
    for block in rows(blocks, "blocks")? {
        made.push(check_block(block).map_err(|refused| EngineError::value(refused.0))?);
    }
    let mut weekly = Vec::new();
    for item in rows(repeats, "repeats")? {
        if item
            .get("id")
            .and_then(Value::as_str)
            .is_some_and(|id| id.starts_with("weekly-"))
        {
            weekly.push(item.clone());
        }
    }
    made.extend(weekly);
    Ok(made)
}
