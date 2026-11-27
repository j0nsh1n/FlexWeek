//! Clipboard, copy rows and relocation (P4 group 4, slice 4C): the rules of
//! `desktop/native/controller.py`'s `_fixed_copy_rows`, the empty-offer choice in
//! `copy_last_week_fixed_rows`, `date_problem`, the decision half of `_commit_move_to_date`,
//! `paste_destination`, `copy_block`, `copy_day`, the destination half of `paste_proposals`,
//! `duplicate_selected`'s day default aside, and the head of `confirm_preview`, moved here with the
//! same words. The window keeps the state: it reads the clock, fetches weeks, draws ids, looks
//! assignments up, writes what is decided here, then settles the week (`_touch`), saves, and keeps
//! history and attempts — none of which move.

use flexweek_engine::desk::{calendar, clipboard, datetext, grid, planning, reuse};
use flexweek_engine::shown;
use flexweek_engine::stored::{py_str, truthy, type_name};
use flexweek_engine::{EngineError, ErrorKind, time};
use serde_json::{Map, Value, json};

/// What the empty-week copy sheet says when last week holds nothing worth copying.
pub const NOTHING_TO_COPY: &str = "There's nothing to copy from last week yet.";

/// What the empty-week copy sheet says when last week holds only Setup blocks: those already
/// stand in this week, so a copy would show them twice.
pub const SETUP_ALREADY_HERE: &str =
    "Nothing to copy: School and the fixed times you added in Setup are already in every week.";

/// Why a block cannot move to a date the student dropped it on when the block is not there.
pub const NOT_ON_THAT_DATE: &str = "That block isn't on that date.";

/// What choosing a day without a block on screen says.
pub const SELECT_BEFORE_COPYING: &str = "Select a block before copying it.";

/// What duplicating without a selected block says.
pub const SELECT_BEFORE_DUPLICATING: &str = "Select a block before duplicating it.";

/// What copying a day with nowhere chosen says.
pub const CHOOSE_BEFORE_COPYING_DAY: &str =
    "Select a block or open Day view before copying a day from this week.";

/// What pasting with an empty clipboard says.
pub const COPY_BEFORE_PASTING: &str = "Copy a block or day before pasting.";

/// What pasting with nowhere chosen says.
pub const CHOOSE_BEFORE_PASTING: &str =
    "Select a block or open Day view before pasting into this week.";

/// What saving the preview with nothing checked says.
pub const SELECT_BEFORE_SAVING: &str = "Select at least one item before saving.";

/// What saving the preview with a refused row still checked says.
pub const UNCHECK_INVALID: &str = "Uncheck what can't be added before saving.";

/// What saving the preview with no groups says.
pub const NOTHING_TO_ADD: &str = "There's nothing available to add.";

/// Why a start the planner cannot read or hold is refused: the same words as an hours drag.
pub const OUTSIDE_PLANNED_HOURS: &str =
    "FlexWeek can't use that time, so the block stayed where it was.";

fn rows<'a>(value: &'a Value, what: &str) -> Result<&'a Vec<Value>, EngineError> {
    value.as_array().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: format!("{what} are a list"),
    })
}

fn objects(items: &[Value], what: &str) -> Result<(), EngineError> {
    if items.iter().any(|item| !item.is_object()) {
        return Err(EngineError {
            kind: ErrorKind::Type,
            message: format!("every one of the {what} is an object"),
        });
    }
    Ok(())
}

/// `int(day)` as the copy sheet reads it: whole numbers pass, text parses, anything else is
/// refused as Python refused it.
fn day_number(value: &Value) -> Result<i64, EngineError> {
    match value {
        Value::Bool(true) => Ok(1),
        Value::Bool(false) => Ok(0),
        Value::Number(number) => {
            if let Some(int) = number.as_i64() {
                return Ok(int);
            }
            if let Some(uint) = number.as_u64()
                && let Ok(int) = i64::try_from(uint)
            {
                return Ok(int);
            }
            if let Some(float) = number.as_f64()
                && float.is_finite()
            {
                let cut = float.trunc();
                if cut >= i64::MIN as f64 && cut <= i64::MAX as f64 {
                    return Ok(cut as i64);
                }
            }
            Err(EngineError {
                kind: ErrorKind::Type,
                message: format!("int() argument is out of range: {number}"),
            })
        }
        Value::String(text) => text.parse::<i64>().map_err(|_| {
            EngineError::value(format!("invalid literal for int() with base 10: '{text}'"))
        }),
        _ => Err(EngineError {
            kind: ErrorKind::Type,
            message: format!(
                "int() argument must be a string, a bytes-like object or a real number, not '{}'",
                type_name(value)
            ),
        }),
    }
}

/// Whether `day` counts as one of `days`, as Python `in` judges it: strings like `"3"` and
/// fractions like `3.7` do not match `3`, and non-lists return false.
fn days_contain(days: &Value, day: i64) -> bool {
    let Value::Array(days) = days else {
        return false;
    };
    days.iter().any(|item| match item {
        Value::Number(n) => {
            n.as_i64() == Some(day)
                || n.as_f64()
                    .is_some_and(|f| f.fract() == 0.0 && f == day as f64)
        }
        Value::Bool(b) => i64::from(*b) == day,
        _ => false,
    })
}

/// The object with `id` in `items`, or `None`. Items that are not objects cannot match, as
/// subscripting them raised before a copy ran.
fn find_block<'a>(items: &'a [Value], id: &str) -> Result<Option<&'a Value>, EngineError> {
    objects(items, "blocks")?;
    Ok(items
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(id)))
}

/// A block's end minute. The lengths arrive from the binding unchecked, and the old Python handed the sum to
/// the engine as a 64-bit integer, which refused one too large; a wrapped end would slip past the hours check.
fn end_of(start: i64, length: i64) -> Result<i64, EngineError> {
    start
        .checked_add(length)
        .ok_or_else(|| EngineError::overflow("Python int too large to convert to C long"))
}

fn assignment_of<'a>(assignments: &'a Value, id: &str) -> Option<&'a Value> {
    assignments.as_object()?.get(id)
}

/// The blocks a week object holds: a missing or null field reads as none, as `or []` did.
/// Anything else that is not a list is refused.
fn week_blocks(source: &Value) -> Result<&[Value], EngineError> {
    match get(source, "blocks")? {
        None | Some(Value::Null) => Ok(&[]),
        Some(Value::Array(blocks)) => Ok(blocks),
        Some(_) => Err(EngineError {
            kind: ErrorKind::Type,
            message: "blocks are a list".to_string(),
        }),
    }
}

/// `block[key]`: only an object answers, as `.get` only answered for one.
fn get<'a>(block: &'a Value, key: &str) -> Result<Option<&'a Value>, EngineError> {
    match block {
        Value::Object(fields) => Ok(fields.get(key)),
        _ => Err(EngineError {
            kind: ErrorKind::Attribute,
            message: format!("'{}' object has no attribute 'get'", type_name(block)),
        }),
    }
}

/// The rows the empty-week copy sheet offers from last week's `source` (`None` when the sheet
/// stays shut), with the words for that case. `shown_start` is the week on screen, which the
/// rows belong to. One id is drawn per offered row.
pub struct CopyRows {
    pub rows: Option<Vec<Value>>,
    pub words: Option<String>,
}

impl CopyRows {
    pub fn to_json(&self) -> Value {
        json!({ "rows": self.rows, "words": self.words })
    }
}

pub fn fixed_copy_rows(
    source: Option<&Value>,
    shown_start: &str,
    ids: &mut impl Iterator<Item = String>,
) -> Result<CopyRows, EngineError> {
    let Some(source) = source.filter(|value| !value.is_null()) else {
        return Ok(CopyRows {
            rows: None,
            words: Some(NOTHING_TO_COPY.to_string()),
        });
    };
    let blocks = week_blocks(source)?;
    objects(blocks, "blocks")?;
    let mut offered = Vec::new();
    for item in blocks {
        if item.get("kind").and_then(Value::as_str) != Some("locked")
            || !truthy(item.get("start"))
            || grid::is_standing_block(item)?
        {
            continue;
        }
        // `[int(day) for day in item.get("days") or []]`: nothing there skips the block, a
        // truthy non-list is not iterable, and one bad day refuses the sheet.
        let raw_days = item.get("days").unwrap_or(&Value::Null);
        if !truthy(Some(raw_days)) {
            continue;
        }
        let Value::Array(raw_days) = raw_days else {
            return Err(EngineError {
                kind: ErrorKind::Type,
                message: format!("'{}' object is not iterable", type_name(raw_days)),
            });
        };
        if raw_days.is_empty() {
            continue;
        }
        let days: Vec<i64> = raw_days.iter().map(day_number).collect::<Result<_, _>>()?;
        let copy = reuse::copied_fixed_block(
            item,
            &days,
            &ids.next()
                .ok_or_else(|| EngineError::value("new_ids holds one id per copied row"))?,
        )?;
        let id = copy.get("id").cloned().unwrap_or(Value::Null);
        offered.push(json!({
            "week_start": shown_start,
            "day": days[0],
            "fixed": true,
            "block": copy,
            "group_id": id,
            "checked": true,
            "invalid": "",
        }));
    }
    if offered.is_empty() {
        return Ok(CopyRows {
            rows: None,
            words: Some(copy_empty_words(Some(source))?.to_string()),
        });
    }
    Ok(CopyRows {
        rows: Some(offered),
        words: None,
    })
}

/// What the empty-week copy sheet says when `source` offers no rows: Setup's blocks already
/// stand in this week, so only those explain the silence.
pub fn copy_empty_words(source: Option<&Value>) -> Result<&'static str, EngineError> {
    let blocks = match source.filter(|value| !value.is_null()) {
        None => return Ok(NOTHING_TO_COPY),
        Some(source) => week_blocks(source)?,
    };
    objects(blocks, "blocks")?;
    for item in blocks {
        if grid::is_setup_block(item)? {
            return Ok(SETUP_ALREADY_HERE);
        }
    }
    Ok(NOTHING_TO_COPY)
}

/// What `date_problem` needs: the drag's ends and the weeks the window resolved them to, the
/// days in those weeks, the week-local block (or `None`), the dialog's own start, length and
/// homework (used only without a block), every assignment for the due lookup, and the clock the
/// window read with the student's time step.
pub struct DateProblemInput<'a> {
    pub block_id: &'a str,
    pub from_iso: &'a str,
    pub to_iso: &'a str,
    pub from_week: &'a str,
    pub to_week: &'a str,
    pub from_day: i64,
    pub to_day: i64,
    pub block: Option<&'a Value>,
    pub start: Option<&'a str>,
    pub duration_min: Option<i64>,
    pub assignment_id: Option<&'a str>,
    pub assignments: &'a Value,
    pub now_iso: &'a str,
    pub now_minute: i64,
    pub time_step: i64,
}

/// Why the block cannot go on `to_iso`, in the same words as an hours drag, or `None`.
pub fn date_problem(input: &DateProblemInput) -> Result<Option<String>, EngineError> {
    if input.from_iso == input.to_iso {
        return Ok(None);
    }
    let mut clock = input.start.map(Value::from).unwrap_or(Value::Null);
    let mut length = input.duration_min.map(Value::from).unwrap_or(Value::Null);
    let mut homework_id = input.assignment_id.unwrap_or("").to_string();
    let mut kind = String::new();
    let mut completed = false;
    if let Some(block) = input.block.filter(|block| !block.is_null()) {
        if !days_contain(get(block, "days")?.unwrap_or(&Value::Null), input.from_day)
            || !truthy(get(block, "start")?)
        {
            return Ok(None);
        }
        clock = get(block, "start")?.cloned().unwrap_or(Value::Null);
        length = get(block, "duration_min")?
            .cloned()
            .ok_or_else(|| EngineError::key("duration_min"))?;
        if let Some(found) = get(block, "assignment_id")?
            && truthy(Some(found))
        {
            homework_id = found.as_str().unwrap_or(&homework_id).to_string();
        }
        kind = match get(block, "kind")?.unwrap_or(&Value::Null) {
            value if !truthy(Some(value)) => String::new(),
            Value::String(text) => text.clone(),
            other => py_str(other),
        };
        completed = get(block, "completed")?.is_some_and(|done| truthy(Some(done)));
    }
    let clock = match &clock {
        Value::Null => return Ok(None),
        Value::String(text) if text.is_empty() => return Ok(None),
        Value::String(text) => text.clone(),
        other => {
            return Err(EngineError {
                kind: ErrorKind::Type,
                message: format!("expected string, got '{}'", type_name(other)),
            });
        }
    };
    let length = match length {
        Value::Null => return Ok(None),
        value => day_number(&value)?,
    };
    // Whatever the clock fails to parse as is refused in these words, as the hours drag was.
    let start_min = match flexweek_engine::time::hhmm_to_minutes(&clock) {
        Ok(start_min) => start_min,
        Err(error) if error.kind == ErrorKind::Value => {
            return Ok(Some(OUTSIDE_PLANNED_HOURS.into()));
        }
        Err(error) => return Err(error),
    };
    if (input.block.filter(|block| !block.is_null()).is_none() || !completed)
        && let Some(past) = grid::past_problem(
            &kind,
            input.to_week,
            input.to_day,
            start_min,
            input.now_iso,
            input.now_minute,
            input.time_step,
        )?
    {
        return Ok(Some(past));
    }
    // `get(homework_id) or get(block_id)`: a null or empty record falls back like a missing one.
    let assignment = assignment_of(input.assignments, &homework_id)
        .filter(|record| truthy(Some(record)))
        .or_else(|| assignment_of(input.assignments, input.block_id));
    let due_value = assignment
        .and_then(|assignment| assignment.get("due"))
        .cloned()
        .unwrap_or(Value::Null);
    let due = planning::due_point(&due_value, input.to_week)?;
    let (due_json, due_type) = match due {
        Some((day, minute)) => (json!([day, minute]), "tuple"),
        None => (Value::Null, "NoneType"),
    };
    let end_min = end_of(start_min, length)?;
    Ok(
        grid::span_problem(input.to_day, start_min, end_min, &due_json, due_type)?
            .map(str::to_string),
    )
}

/// What the relocation half of `_commit_move_to_date` needs: the resolved weeks and days, the
/// week the drag started on (`source`) and, for another week, the week it lands on (`dest`),
/// every assignment for the due lookup, the destination week's words for the capacity refusal,
/// and the id one split-off day would take (used at most once).
pub struct RelocationInput<'a> {
    pub block_id: &'a str,
    pub from_day: i64,
    pub to_day: i64,
    pub from_week: &'a str,
    pub to_week: &'a str,
    pub source: &'a Value,
    pub dest: Option<&'a Value>,
    pub assignments: &'a Value,
    pub dest_words: &'a str,
}

/// The relocation's answer: refusal words, or the weeks after the move with the Undo title.
pub enum Relocation {
    Say(String),
    Apply {
        source_after: Vec<Value>,
        dest_after: Option<Vec<Value>>,
        title: String,
    },
}

impl Relocation {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({
                "say": words,
                "source_after": Value::Null,
                "dest_after": Value::Null,
                "title": Value::Null,
            }),
            Self::Apply {
                source_after,
                dest_after,
                title,
            } => json!({
                "say": Value::Null,
                "source_after": source_after,
                "dest_after": dest_after,
                "title": title,
            }),
        }
    }
}

fn say(words: impl Into<String>) -> Result<Relocation, EngineError> {
    Ok(Relocation::Say(words.into()))
}

/// One block moved to another calendar date, same week or not: the weeks after the move, or the
/// refusal in the same words as an hours drag. Composes `grid::relocate_block` with the span and
/// capacity rules the drop was judged by.
pub fn relocate(
    input: &RelocationInput,
    ids: &mut impl Iterator<Item = String>,
) -> Result<Relocation, EngineError> {
    let same_week = input.from_week == input.to_week;
    let source_blocks = rows(
        get(input.source, "blocks")?.unwrap_or(&Value::Null),
        "blocks",
    )?;
    objects(source_blocks, "blocks")?;
    let block = find_block(source_blocks, input.block_id)?;
    let Some(block) = block else {
        return say(NOT_ON_THAT_DATE);
    };
    if !days_contain(get(block, "days")?.unwrap_or(&Value::Null), input.from_day)
        || !truthy(get(block, "start")?)
    {
        return say(NOT_ON_THAT_DATE);
    }
    let clock = match get(block, "start")?.cloned().unwrap_or(Value::Null) {
        Value::String(text) => text,
        other => {
            return Err(EngineError {
                kind: ErrorKind::Type,
                message: format!("expected string, got '{}'", type_name(&other)),
            });
        }
    };
    let start = flexweek_engine::time::hhmm_to_minutes(&clock)?;
    let length = day_number(
        &get(block, "duration_min")?
            .cloned()
            .ok_or_else(|| EngineError::key("duration_min"))?,
    )?;
    // Only the block's own homework judges the move: unlike the drag check, nothing falls back
    // to an assignment sharing the block's id.
    let homework_id = match get(block, "assignment_id")? {
        Some(Value::String(id)) if !id.is_empty() => id.clone(),
        _ => String::new(),
    };
    let assignment = assignment_of(input.assignments, &homework_id);
    let due_value = assignment
        .and_then(|assignment| assignment.get("due"))
        .cloned()
        .unwrap_or(Value::Null);
    let due = planning::due_point(&due_value, input.to_week)?;
    let (due_json, due_type) = match due {
        Some((day, minute)) => (json!([day, minute]), "tuple"),
        None => (Value::Null, "NoneType"),
    };
    let end = end_of(start, length)?;
    if let Some(problem) = grid::span_problem(input.to_day, start, end, &due_json, due_type)? {
        return say(problem);
    }
    let dest_blocks = if same_week {
        None
    } else {
        Some(rows(
            get(
                input.dest.ok_or_else(|| EngineError {
                    kind: ErrorKind::Type,
                    message: "the destination week is a week".to_string(),
                })?,
                "blocks",
            )?
            .unwrap_or(&Value::Null),
            "blocks",
        )?)
    };
    if let Some(dest_blocks) = dest_blocks {
        objects(dest_blocks, "blocks")?;
    }
    let source_value = Value::Array(source_blocks.clone());
    let dest_value = dest_blocks.map(|blocks| Value::Array(blocks.clone()));
    // A split day draws one fresh id; running dry is refused instead of reusing an id.
    let mut ran_out = false;
    let mut fresh = || match ids.next() {
        Some(id) => id,
        None => {
            ran_out = true;
            String::new()
        }
    };
    let moved = grid::relocate_block(
        &source_value,
        &json!(input.block_id),
        &json!(input.from_day),
        &json!(input.to_day),
        dest_value.as_ref(),
        &mut fresh,
    );
    if ran_out {
        return Err(EngineError::value("new_ids holds one id per split day"));
    }
    let Some((source_after, dest_after, _made)) = moved? else {
        return say(NOT_ON_THAT_DATE);
    };
    if let Some(dest_after) = dest_after.as_ref()
        && dest_after.len() as i64 > reuse::MAX_WEEK_BLOCKS
    {
        let before = dest_blocks.map_or(0, |blocks| blocks.len() as i64);
        return say(planning::capacity_problem(before, 1, input.dest_words));
    }
    let title = match get(block, "title")? {
        Some(value) if truthy(Some(value)) => py_str(value),
        _ => "the block".to_string(),
    };
    Ok(Relocation::Apply {
        source_after,
        dest_after,
        title,
    })
}

/// One block copied: the clipboard with its words, or nothing when the block is not on the week.
/// `block_id` is `None` when nothing is selected, which names the refusal.
pub struct ClipboardBlock {
    pub clipboard: Option<Value>,
    pub words: Option<String>,
}

impl ClipboardBlock {
    pub fn to_json(&self) -> Value {
        json!({ "clipboard": self.clipboard, "words": self.words })
    }
}

pub fn clipboard_block(
    blocks: &Value,
    block_id: Option<&str>,
    day: Option<i64>,
    scope: &str,
    new_id: &str,
) -> Result<ClipboardBlock, EngineError> {
    let Some(block_id) = block_id else {
        return Ok(ClipboardBlock {
            clipboard: None,
            words: Some(SELECT_BEFORE_COPYING.to_string()),
        });
    };
    let blocks = rows(blocks, "blocks")?;
    let Some(source) = find_block(blocks, block_id)? else {
        return Ok(ClipboardBlock {
            clipboard: None,
            words: None,
        });
    };
    let mut cleaned = source.clone();
    let source = if source
        .get("removed_days")
        .and_then(Value::as_array)
        .is_some_and(|days| !days.is_empty())
    {
        let active = planning::occurrence_days(source)?;
        if active.is_empty() {
            return Ok(ClipboardBlock {
                clipboard: None,
                words: None,
            });
        }
        if let Some(day) = day
            && flexweek_engine::standing::removed_on(source, &json!(day))
        {
            return Ok(ClipboardBlock {
                clipboard: None,
                words: None,
            });
        }
        if let Some(fields) = cleaned.as_object_mut() {
            fields.insert("days".into(), Value::Array(active));
            fields.shift_remove("removed_days");
        }
        &cleaned
    } else {
        source
    };
    let source_day = match day {
        Some(day) => json!(day),
        None => get(source, "days")?
            .and_then(|days| days.as_array())
            .and_then(|days| days.first())
            .cloned()
            .unwrap_or(json!(0)),
    };
    let resolved = if scope != "auto" {
        scope.to_string()
    } else if calendar::is_series_checked(source)? {
        "occurrence".to_string()
    } else {
        "block".to_string()
    };
    let label = planning::copy_label(source, &source_day, &json!(resolved))?;
    let Some(label) = label.as_str() else {
        return Err(EngineError {
            kind: ErrorKind::Type,
            message: "the copy label is text".to_string(),
        });
    };
    let label = label.to_string();
    let source_day_number = day_number(&source_day)?;
    let items = vec![reuse::clipboard_item(
        source,
        source_day_number,
        &resolved,
        new_id,
    )];
    let clipboard = json!({
        "kind": "block",
        "label": label,
        "items": items,
        "fingerprint": planning::clipboard_fingerprint(&Value::Array(items.clone()))?,
    });
    let words = format!("{label} copied. Choose a destination and paste.");
    Ok(ClipboardBlock {
        clipboard: Some(clipboard),
        words: Some(words),
    })
}

/// What `paste_destination` reads from the window: the selected block with the occurrence it
/// was selected on (both set, or the selection does not decide), the planner's view of the
/// selected day with the week the window resolved it to, and the local date the window read.
pub struct PasteSelection<'a> {
    pub selected_block_id: Option<&'a str>,
    pub selected_occurrence_day: Option<i64>,
    pub planner_view: &'a str,
    pub first_weekday: u32,
    pub selected_day: &'a str,
    pub today_iso: &'a str,
}

/// Where a paste or a day copy lands: the day with the start to match, if any.
pub struct Destination {
    pub day: Option<i64>,
    pub start: Option<String>,
}

impl Destination {
    pub fn to_json(&self) -> Value {
        json!({ "day": self.day, "start": self.start })
    }
}

/// Where the paste lands: the selected occurrence with its placed start, the planner's day, or
/// the column holding today — or `None` when none of those names a day.
pub fn paste_destination(
    blocks: &Value,
    trace: &Value,
    selection: &PasteSelection,
    week_start: &str,
) -> Result<Option<Destination>, EngineError> {
    let block_list = rows(blocks, "blocks")?;
    objects(block_list, "blocks")?;
    // A stale or empty selection decides nothing: the planner day and today still get asked.
    if let (Some(selected), Some(occurrence_day)) = (
        selection.selected_block_id,
        selection.selected_occurrence_day,
    ) && !selected.is_empty()
        && let Some(source) = find_block(block_list, selected)?
    {
        let mut placed = if truthy(get(source, "start").unwrap_or(None)) {
            Some(source.clone())
        } else {
            None
        };
        if placed.is_none()
            && let Some(shown) = trace.get("placed")
            && let Value::Array(shown) = shown
        {
            placed = shown
                .iter()
                .find(|item| {
                    item.get("id").and_then(Value::as_str) == Some(selected)
                        && days_contain(item.get("days").unwrap_or(&Value::Null), occurrence_day)
                })
                .cloned();
        }
        let start = placed
            .as_ref()
            .and_then(|block| block.get("start"))
            .and_then(Value::as_str)
            .filter(|start| !start.is_empty())
            .map(str::to_string);
        return Ok(Some(Destination {
            day: Some(occurrence_day),
            start,
        }));
    }
    // The planner's day counts only inside the open week; resolving its week reads nothing the
    // window did not already hold.
    if selection.planner_view == "day"
        && flexweek_engine::time::week_start_on(selection.selected_day, selection.first_weekday)?
            == week_start
    {
        let day = grid::due_day_in_week(selection.selected_day, week_start)?;
        return Ok(Some(Destination {
            day: Some(day),
            start: None,
        }));
    }
    let column = grid::due_day_in_week(selection.today_iso, week_start).unwrap_or(-1);
    if !(0..=6).contains(&column) {
        return Ok(None);
    }
    Ok(Some(Destination {
        day: Some(column),
        start: None,
    }))
}

/// One day copied: the clipboard with its words, or the refusal when there is nothing to take.
pub enum CopyDay {
    Say(String),
    Copied { clipboard: Value, words: String },
}

impl CopyDay {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "clipboard": Value::Null, "words": words }),
            Self::Copied { clipboard, words } => json!({ "clipboard": clipboard, "words": words }),
        }
    }
}

pub fn copy_day_items(
    blocks: &Value,
    trace: &Value,
    day: Option<i64>,
    week_start: &str,
    ids: &mut impl Iterator<Item = String>,
) -> Result<CopyDay, EngineError> {
    // A day the destination never named cannot index the week, as it could not before.
    let chosen = day.ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: "tuple indices must be integers or slices, not NoneType".to_string(),
    })?;
    let names = shown::day_names(week_start, true)?;
    let name = names
        .get(usize::try_from(chosen).unwrap_or(usize::MAX))
        .copied()
        .ok_or_else(|| EngineError::index("tuple index out of range"))?;
    let placed = match trace.get("placed") {
        Some(Value::Array(_)) => trace.get("placed"),
        _ => None,
    };
    let blocks = rows(blocks, "blocks")?;
    objects(blocks, "blocks")?;
    let mut items = Vec::new();
    for block in blocks {
        if !planning::block_occurs_on_day(block, &json!(chosen), placed)? {
            continue;
        }
        if truthy(get(block, "assignment_id")?) && truthy(get(block, "completed")?) {
            continue;
        }
        let id = ids
            .next()
            .ok_or_else(|| EngineError::value("new_ids holds one id per copied item"))?;
        items.push(reuse::clipboard_item(block, chosen, "occurrence", &id));
    }
    if items.is_empty() {
        return Ok(CopyDay::Say(format!("{name} has nothing to copy.")));
    }
    let noun = if items.len() == 1 { " item" } else { " items" };
    let label = format!("{name} · {}{noun}", items.len());
    let clipboard = json!({
        "kind": "day",
        "label": label,
        "items": items,
        "fingerprint": planning::clipboard_fingerprint(&Value::Array(items.clone()))?,
    });
    Ok(CopyDay::Copied {
        words: format!("{label} copied. Choose a destination and paste."),
        clipboard,
    })
}

/// A paste about to preview: the destination, or why there is none.
pub enum PasteReady {
    Say(String),
    Ready { day: i64, start: Option<String> },
}

impl PasteReady {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "day": Value::Null, "start": Value::Null, "words": words }),
            Self::Ready { day, start } => {
                json!({ "day": day, "start": start, "words": Value::Null })
            }
        }
    }
}

pub fn paste_ready(
    clipboard: Option<&Value>,
    target_day: Option<i64>,
    target_start: Option<&str>,
    blocks: &Value,
    trace: &Value,
    selection: &PasteSelection,
    week_start: &str,
) -> Result<PasteReady, EngineError> {
    if clipboard.filter(|value| !value.is_null()).is_none() {
        return Ok(PasteReady::Say(COPY_BEFORE_PASTING.to_string()));
    }
    if let Some(day) = target_day {
        return Ok(PasteReady::Ready {
            day,
            start: target_start.map(str::to_string),
        });
    }
    match paste_destination(blocks, trace, selection, week_start)? {
        None => Ok(PasteReady::Say(CHOOSE_BEFORE_PASTING.to_string())),
        Some(destination) => destination.day.map_or_else(
            || {
                Err(EngineError {
                    kind: ErrorKind::Type,
                    message:
                        "argument 'target_day': 'NoneType' object cannot be converted to 'PyLong'"
                            .to_string(),
                })
            },
            |day| {
                Ok(PasteReady::Ready {
                    day,
                    start: destination.start,
                })
            },
        ),
    }
}

/// The preview's checked rows after the merge: refusal words, or the rows grouped by week in the
/// order their groups first appeared.
pub enum PreviewGroups {
    Say(String),
    Groups { by_week: Value },
}

impl PreviewGroups {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "say": words, "by_week": Value::Null }),
            Self::Groups { by_week } => json!({ "say": Value::Null, "by_week": by_week }),
        }
    }
}

pub fn preview_groups(all_rows: &Value, operation_id: &str) -> Result<PreviewGroups, EngineError> {
    let rows = rows(all_rows, "rows")?;
    for row in rows {
        if !row.is_object() {
            return Err(EngineError {
                kind: ErrorKind::Attribute,
                message: format!("'{}' object has no attribute 'get'", type_name(row)),
            });
        }
    }
    if !rows.iter().any(|row| truthy(row.get("checked"))) {
        return Ok(PreviewGroups::Say(SELECT_BEFORE_SAVING.to_string()));
    }
    if rows
        .iter()
        .filter(|row| truthy(row.get("checked")))
        .any(|row| truthy(row.get("invalid")))
    {
        return Ok(PreviewGroups::Say(UNCHECK_INVALID.to_string()));
    }
    let groups = clipboard::merge_preview_rows(&Value::Array(rows.clone()), operation_id)?;
    if groups.is_empty() {
        return Ok(PreviewGroups::Say(NOTHING_TO_ADD.to_string()));
    }
    let mut by_week = serde_json::Map::new();
    for group in &groups {
        let week = group
            .get("week_start")
            .and_then(Value::as_str)
            .ok_or_else(|| EngineError::key("week_start"))?;
        by_week
            .entry(week.to_string())
            .or_insert_with(|| Value::Array(Vec::new()))
            .as_array_mut()
            .ok_or_else(|| EngineError {
                kind: ErrorKind::Type,
                message: "weeks group blocks".to_string(),
            })?
            .push(
                group
                    .get("block")
                    .cloned()
                    .ok_or_else(|| EngineError::key("block"))?,
            );
    }
    Ok(PreviewGroups::Groups {
        by_week: Value::Object(by_week),
    })
}

/// Which week `copy_last_week_fixed_rows` reads, or why it stops.
#[derive(Debug, PartialEq)]
pub enum PreviousWeekCopy {
    Absent,
    Say(&'static str),
    Ready { week_start: String, path: String },
}

impl PreviousWeekCopy {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready { week_start, path } => json!({
                "kind": "ready",
                "week_start": week_start,
                "path": path,
            }),
        }
    }
}

/// The shown week seven days before `week_start`, or `NOTHING_TO_COPY` when `week_start` is not a
/// valid date. Signed-out sessions return `Absent`.
pub fn previous_week_for_copy(
    signed_in: bool,
    week_start: &str,
    first_weekday: u32,
) -> PreviousWeekCopy {
    if !signed_in {
        return PreviousWeekCopy::Absent;
    }
    let Ok(before) = grid::date_for_day(week_start, &Value::from(-7)) else {
        return PreviousWeekCopy::Say(NOTHING_TO_COPY);
    };
    let Ok(previous) = time::week_start_on(&before, first_weekday) else {
        return PreviousWeekCopy::Say(NOTHING_TO_COPY);
    };
    PreviousWeekCopy::Ready {
        path: format!("/api/week?week_start={previous}"),
        week_start: previous,
    }
}

/// Look up `block_id` inside one local week state (`{"blocks": [...]}`), or `None` when the week
/// or the block is absent.
pub fn block_on_week(state: Option<&Value>, block_id: &str) -> Result<Option<Value>, EngineError> {
    let Some(state) = state.filter(|value| !value.is_null()) else {
        return Ok(None);
    };
    let blocks = rows(get(state, "blocks")?.unwrap_or(&Value::Null), "blocks")?;
    Ok(find_block(blocks, block_id)?.cloned())
}

/// Resolved weeks and day indices for a `(from_iso, to_iso)` drag.
#[derive(Debug, PartialEq)]
pub struct DateSpan {
    pub from_week: String,
    pub to_week: String,
    pub from_day: i64,
    pub to_day: i64,
}

impl DateSpan {
    pub fn to_json(&self) -> Value {
        json!({
            "from_week": self.from_week,
            "to_week": self.to_week,
            "from_day": self.from_day,
            "to_day": self.to_day,
        })
    }
}

/// Resolve both ends of a date drag against `first_weekday`, or `None` when either date is invalid.
pub fn resolve_date_span(from_iso: &str, to_iso: &str, first_weekday: u32) -> Option<DateSpan> {
    let to_week = time::week_start_on(to_iso, first_weekday).ok()?;
    let from_week = time::week_start_on(from_iso, first_weekday).ok()?;
    let from_day = grid::due_day_in_week(from_iso, &from_week).ok()?;
    let to_day = grid::due_day_in_week(to_iso, &to_week).ok()?;
    Some(DateSpan {
        from_week,
        to_week,
        from_day,
        to_day,
    })
}

/// Guard inputs for `move_to_date`.
pub struct MoveToDateInput<'a> {
    pub account_id: Option<i64>,
    pub conflict: bool,
    pub busy: bool,
    pub pending_save: bool,
    pub block_id: &'a str,
    pub from_iso: &'a str,
    pub to_iso: &'a str,
    pub first_weekday: u32,
}

#[derive(Debug, PartialEq)]
pub enum MoveToDatePlan {
    Stop {
        result: bool,
    },
    Ready {
        from_week: String,
        to_week: String,
        key: String,
    },
}

impl MoveToDatePlan {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Stop { result } => json!({ "kind": "stop", "result": result }),
            Self::Ready {
                from_week,
                to_week,
                key,
            } => json!({
                "kind": "ready",
                "from_week": from_week,
                "to_week": to_week,
                "key": key,
            }),
        }
    }
}

/// Validate guards, resolve both weeks and assemble the retry key for `move_to_date`.
pub fn prepare_move_to_date(input: &MoveToDateInput) -> MoveToDatePlan {
    let Some(account_id) = input.account_id else {
        return MoveToDatePlan::Stop { result: false };
    };
    if input.conflict || input.busy || input.pending_save {
        return MoveToDatePlan::Stop { result: false };
    }
    let Ok(from_week) = time::week_start_on(input.from_iso, input.first_weekday) else {
        return MoveToDatePlan::Stop { result: false };
    };
    let Ok(to_week) = time::week_start_on(input.to_iso, input.first_weekday) else {
        return MoveToDatePlan::Stop { result: false };
    };
    if input.from_iso == input.to_iso {
        return MoveToDatePlan::Stop { result: true };
    }
    let key = format!(
        "move-to-date|{account_id}|{}|{}|{}",
        input.block_id, input.from_iso, input.to_iso
    );
    MoveToDatePlan::Ready {
        from_week,
        to_week,
        key,
    }
}

/// Weeks that `move_to_date` still needs to GET, deduplicated in `(from_week, to_week)` order.
pub fn move_to_date_needed(
    from_week: &str,
    to_week: &str,
    has_source: bool,
    has_dest: bool,
) -> Vec<String> {
    let mut needed = Vec::new();
    if !has_source {
        needed.push(from_week.to_string());
    }
    if to_week != from_week && !has_dest {
        needed.push(to_week.to_string());
    }
    needed
}

/// Inputs for `_commit_move_to_date`: local/fetched source and destination week states, plus the
/// metadata needed to build the `/api/changes` batch and Undo step.
pub struct MoveToDateBatchInput<'a> {
    pub block_id: &'a str,
    pub from_iso: &'a str,
    pub to_iso: &'a str,
    pub from_week: &'a str,
    pub to_week: &'a str,
    pub source_local: Option<&'a Value>,
    pub dest_local: Option<&'a Value>,
    pub fetched: &'a Map<String, Value>,
    pub assignments: &'a Value,
    pub today_iso: &'a str,
    pub operation_id: &'a str,
    pub attempt_key: &'a str,
}

#[derive(Debug, PartialEq)]
pub enum MoveToDateBatch {
    Say(String),
    Submit {
        pending_step: Value,
        history_label: String,
        move_attempt: String,
        pending_save: Value,
    },
}

impl MoveToDateBatch {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Submit {
                pending_step,
                history_label,
                move_attempt,
                pending_save,
            } => json!({
                "kind": "submit",
                "pending_step": pending_step,
                "history_label": history_label,
                "move_attempt": move_attempt,
                "pending_save": pending_save,
            }),
        }
    }
}

/// Relocate one block between dates and build the `submit_batch` payload (`pending_step`,
/// `history_label`, `move_attempt`, `pending_save`), or return refusal words.
pub fn build_move_to_date_batch(
    input: &MoveToDateBatchInput,
    new_id: &str,
) -> Result<MoveToDateBatch, EngineError> {
    let source = input
        .source_local
        .filter(|value| !value.is_null())
        .or_else(|| input.fetched.get(input.from_week))
        .ok_or_else(|| EngineError::key(input.from_week))?;
    let dest = if input.to_week == input.from_week {
        None
    } else {
        Some(
            input
                .dest_local
                .filter(|value| !value.is_null())
                .or_else(|| input.fetched.get(input.to_week))
                .ok_or_else(|| EngineError::key(input.to_week))?,
        )
    };
    let from_day = grid::due_day_in_week(input.from_iso, input.from_week)?;
    let to_day = grid::due_day_in_week(input.to_iso, input.to_week)?;
    let today = datetext::day_of(input.today_iso)?;
    let dest_words = reuse::week_label(input.to_week, today)?;
    let reloc_input = RelocationInput {
        block_id: input.block_id,
        from_day,
        to_day,
        from_week: input.from_week,
        to_week: input.to_week,
        source,
        dest,
        assignments: input.assignments,
        dest_words: &dest_words,
    };
    let mut ids = std::iter::once(new_id.to_string());
    let (source_after, dest_after, title) = match relocate(&reloc_input, &mut ids)? {
        Relocation::Say(words) => return Ok(MoveToDateBatch::Say(words)),
        Relocation::Apply {
            source_after,
            dest_after,
            title,
        } => (source_after, dest_after, title),
    };
    let source_rev = get(source, "revision")?.ok_or_else(|| EngineError::key("revision"))?;
    let source_blocks = rows(get(source, "blocks")?.unwrap_or(&Value::Null), "blocks")?;
    let mut writes = vec![crate::session::changes::week_write(
        input.from_week,
        &source_after,
        source_rev,
    )?];
    let mut step_weeks = vec![json!({
        "week_start": input.from_week,
        "before": source_blocks,
        "after": source_after,
    })];
    if let Some(dest_after) = dest_after {
        let dest_state = dest.ok_or_else(|| EngineError::key(input.to_week))?;
        let dest_rev = get(dest_state, "revision")?.ok_or_else(|| EngineError::key("revision"))?;
        let dest_blocks = rows(get(dest_state, "blocks")?.unwrap_or(&Value::Null), "blocks")?;
        writes.push(crate::session::changes::week_write(
            input.to_week,
            &dest_after,
            dest_rev,
        )?);
        step_weeks.push(json!({
            "week_start": input.to_week,
            "before": dest_blocks,
            "after": dest_after,
        }));
    }
    let label = format!("moving {title} to another date");
    let pending_step = json!({
        "label": label,
        "weeks": step_weeks,
        "assignments": [],
        "stale": false,
    });
    let pending_save = json!({
        "weeks": writes,
        "assignments": [],
        "operation_id": input.operation_id,
        "stay": true,
    });
    Ok(MoveToDateBatch::Submit {
        pending_step,
        history_label: label,
        move_attempt: input.attempt_key.to_string(),
        pending_save,
    })
}

/// Decision for `copy_selected`.
#[derive(Debug, PartialEq)]
pub enum CopySelectedPlan {
    Absent,
    Say(String),
    Copied { clipboard: Value, say: String },
}

impl CopySelectedPlan {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Copied { clipboard, say } => json!({
                "kind": "copied",
                "clipboard": clipboard,
                "say": say,
            }),
        }
    }
}

/// Copy the selected block into the clipboard, or refuse when nothing is selected.
pub fn copy_selected_plan(
    signed_in: bool,
    blocks: &Value,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    scope: &str,
    new_id: &str,
) -> Result<CopySelectedPlan, EngineError> {
    let Some(block_id) = selected_block_id.filter(|id| !id.is_empty()) else {
        return Ok(CopySelectedPlan::Say(SELECT_BEFORE_COPYING.to_string()));
    };
    if !signed_in {
        return Ok(CopySelectedPlan::Absent);
    }
    let copied = clipboard_block(
        blocks,
        Some(block_id),
        selected_occurrence_day,
        scope,
        new_id,
    )?;
    match copied.clipboard {
        Some(clipboard) => Ok(CopySelectedPlan::Copied {
            clipboard,
            say: copied.words.unwrap_or_default(),
        }),
        None => Ok(CopySelectedPlan::Absent),
    }
}

/// Decision for `copy_day`.
#[derive(Debug, PartialEq)]
pub enum CopyDayPlan {
    Absent,
    Say(String),
    Copied { clipboard: Value, say: String },
}

impl CopyDayPlan {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Copied { clipboard, say } => json!({
                "kind": "copied",
                "clipboard": clipboard,
                "say": say,
            }),
        }
    }
}

/// Copy one day's items into the clipboard, resolving the destination day when `day` is omitted.
pub fn copy_day_plan(
    signed_in: bool,
    blocks: &Value,
    trace: &Value,
    day: Option<i64>,
    selection: &PasteSelection,
    week_start: &str,
    ids: &mut impl Iterator<Item = String>,
) -> Result<CopyDayPlan, EngineError> {
    if !signed_in {
        return Ok(CopyDayPlan::Absent);
    }
    let chosen_day = match day {
        Some(day) => Some(day),
        None => match paste_destination(blocks, trace, selection, week_start)? {
            None => return Ok(CopyDayPlan::Say(CHOOSE_BEFORE_COPYING_DAY.to_string())),
            Some(destination) => destination.day,
        },
    };
    match copy_day_items(blocks, trace, chosen_day, week_start, ids)? {
        CopyDay::Say(words) => Ok(CopyDayPlan::Say(words)),
        CopyDay::Copied { clipboard, words } => Ok(CopyDayPlan::Copied {
            clipboard,
            say: words,
        }),
    }
}

/// Guard and destination resolution for `paste_proposals`.
#[derive(Debug, PartialEq)]
pub enum PasteProposalsPrep {
    Absent,
    Say(String),
    Ready {
        day: i64,
        start: Option<String>,
        needs_minutes: bool,
    },
}

impl PasteProposalsPrep {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                day,
                start,
                needs_minutes,
            } => json!({
                "kind": "ready",
                "day": day,
                "start": start,
                "needs_minutes": needs_minutes,
            }),
        }
    }
}

/// Check sign-in, clipboard and paste destination; tell the window whether it needs to compute
/// homework minutes (skipped when there is no homework).
#[allow(clippy::too_many_arguments)]
pub fn paste_proposals_prepare(
    signed_in: bool,
    clipboard: Option<&Value>,
    target_day: Option<i64>,
    target_start: Option<&str>,
    blocks: &Value,
    trace: &Value,
    selection: &PasteSelection,
    week_start: &str,
    has_assignments: bool,
) -> Result<PasteProposalsPrep, EngineError> {
    let clipboard = clipboard.filter(|value| !value.is_null());
    if !signed_in {
        return Ok(if clipboard.is_none() {
            PasteProposalsPrep::Say(COPY_BEFORE_PASTING.to_string())
        } else {
            PasteProposalsPrep::Absent
        });
    }
    match paste_ready(
        clipboard,
        target_day,
        target_start,
        blocks,
        trace,
        selection,
        week_start,
    )? {
        PasteReady::Say(words) => Ok(PasteProposalsPrep::Say(words)),
        PasteReady::Ready { day, start } => Ok(PasteProposalsPrep::Ready {
            day,
            start,
            needs_minutes: has_assignments,
        }),
    }
}

/// Build the paste/duplicate proposal rows from `clipboard` and the per-assignment uncovered
/// minutes map.
pub fn paste_proposals_build(
    clipboard: &Value,
    week_start: &str,
    target_day: i64,
    target_start: Option<&str>,
    assignments: &Value,
    minutes: &Value,
) -> Result<Vec<Value>, EngineError> {
    let assignment_map = assignments.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: "the assignments are an object".to_string(),
    })?;
    let minutes_map = minutes.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: "the homework minutes are an object".to_string(),
    })?;
    let mut available = Map::new();
    for item_id in assignment_map.keys() {
        let uncovered = match minutes_map
            .get(item_id)
            .and_then(Value::as_object)
            .and_then(|entry| entry.get("uncovered_min"))
        {
            Some(value) => day_number(value)?,
            None => 0,
        };
        available.insert(item_id.clone(), Value::from(uncovered));
    }
    let items = get(clipboard, "items")?.ok_or_else(|| EngineError::key("items"))?;
    let kind = get(clipboard, "kind")?
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::key("kind"))?;
    clipboard::proposals_from_clipboard(
        items,
        kind,
        week_start,
        target_day,
        target_start,
        assignments,
        &Value::Object(available),
    )
}

/// Decision for `duplicate_selected`: prepares a temporary copy without touching the session's
/// clipboard and without announcing "Copied ...".
#[derive(Debug, PartialEq)]
pub enum DuplicatePrep {
    Absent,
    Say(String),
    Ready {
        clipboard: Value,
        target_day: i64,
        announce: Option<String>,
        needs_minutes: bool,
    },
}

impl DuplicatePrep {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                clipboard,
                target_day,
                announce,
                needs_minutes,
            } => json!({
                "kind": "ready",
                "clipboard": clipboard,
                "target_day": target_day,
                "announce": announce,
                "needs_minutes": needs_minutes,
            }),
        }
    }
}

/// Prepare a duplicate preview for the selected block. Never leaves anything on the clipboard and
/// never announces that anything was copied.
pub fn duplicate_selected_prepare(
    signed_in: bool,
    blocks: &Value,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    scope: &str,
    new_id: &str,
    has_assignments: bool,
) -> Result<DuplicatePrep, EngineError> {
    let Some(block_id) = selected_block_id else {
        return Ok(DuplicatePrep::Say(SELECT_BEFORE_DUPLICATING.to_string()));
    };
    if !signed_in {
        return Ok(DuplicatePrep::Absent);
    }
    let copied = clipboard_block(
        blocks,
        Some(block_id),
        selected_occurrence_day,
        scope,
        new_id,
    )?;
    let Some(clipboard) = copied.clipboard else {
        return Ok(DuplicatePrep::Absent);
    };
    // Nothing is left copied, so nothing says so.
    let announce: Option<String> = None;
    Ok(DuplicatePrep::Ready {
        clipboard,
        target_day: selected_occurrence_day.unwrap_or(0),
        announce,
        needs_minutes: has_assignments,
    })
}

/// The GET order `_commit_groups` uses for remote weeks: every week in `by_week` other than
/// `week_start`, reversed (matching Python's `needed.pop()`).
pub fn commit_groups_order(by_week: &Map<String, Value>, week_start: &str) -> Vec<String> {
    by_week
        .keys()
        .filter(|week| week.as_str() != week_start)
        .rev()
        .cloned()
        .collect()
}

/// Inputs for `confirm_preview`.
pub struct ConfirmPreviewInput<'a> {
    pub signed_in: bool,
    pub conflict: bool,
    pub rows: &'a Value,
    pub week_start: &'a str,
    pub blocks: &'a Value,
    pub today_iso: &'a str,
    pub operation_id: Option<&'a str>,
    pub attempt_key: Option<&'a str>,
    pub attempts: &'a Map<String, Value>,
    pub fresh_operation_id: &'a str,
}

#[derive(Debug, PartialEq)]
pub enum ConfirmPreviewPlan {
    Absent,
    Say {
        say: String,
        record_attempt: bool,
        op_id: String,
    },
    SingleWeek {
        op_id: String,
        record_attempt: bool,
        blocks: Vec<Value>,
    },
    MultiWeek {
        op_id: String,
        record_attempt: bool,
        by_week: Value,
        fetch_order: Vec<String>,
    },
}

impl ConfirmPreviewPlan {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say {
                say,
                record_attempt,
                op_id,
            } => json!({
                "kind": "say",
                "say": say,
                "record_attempt": record_attempt,
                "op_id": op_id,
            }),
            Self::SingleWeek {
                op_id,
                record_attempt,
                blocks,
            } => json!({
                "kind": "single_week",
                "op_id": op_id,
                "record_attempt": record_attempt,
                "blocks": blocks,
            }),
            Self::MultiWeek {
                op_id,
                record_attempt,
                by_week,
                fetch_order,
            } => json!({
                "kind": "multi_week",
                "op_id": op_id,
                "record_attempt": record_attempt,
                "by_week": by_week,
                "fetch_order": fetch_order,
            }),
        }
    }
}

/// Decide how `confirm_preview` saves checked preview rows: single-week fast path with capacity
/// check, multi-week grouped commit with fetch order, or refusal words. A refused selection never
/// reserves an attempt.
pub fn confirm_preview_plan(
    input: &ConfirmPreviewInput,
) -> Result<ConfirmPreviewPlan, EngineError> {
    if !input.signed_in || input.conflict {
        return Ok(ConfirmPreviewPlan::Absent);
    }
    let attempt_key = input.attempt_key.filter(|key| !key.is_empty());
    let held = attempt_key
        .and_then(|key| input.attempts.get(key))
        .and_then(Value::as_str)
        .filter(|id| !id.is_empty());
    let op_id = input
        .operation_id
        .filter(|id| !id.is_empty())
        .or(held)
        .unwrap_or(input.fresh_operation_id)
        .to_string();
    let by_week = match preview_groups(input.rows, &op_id)? {
        PreviewGroups::Say(words) => {
            return Ok(ConfirmPreviewPlan::Say {
                say: words,
                record_attempt: false,
                op_id,
            });
        }
        PreviewGroups::Groups { by_week } => by_week,
    };
    let record_attempt = attempt_key.is_some();
    let by_week_map = by_week.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Type,
        message: "grouped rows are an object".to_string(),
    })?;
    if by_week_map.len() == 1
        && let Some(added_value) = by_week_map.get(input.week_start)
    {
        let existing = rows(input.blocks, "blocks")?;
        let added = rows(added_value, "blocks")?;
        let today = datetext::day_of(input.today_iso)?;
        let week_words = reuse::week_label(input.week_start, today)?;
        let problem =
            planning::capacity_problem(existing.len() as i64, added.len() as i64, &week_words);
        if !problem.is_empty() {
            return Ok(ConfirmPreviewPlan::Say {
                say: problem,
                record_attempt,
                op_id,
            });
        }
        let mut combined = existing.clone();
        combined.extend(added.iter().cloned());
        return Ok(ConfirmPreviewPlan::SingleWeek {
            op_id,
            record_attempt,
            blocks: combined,
        });
    }
    let fetch_order = commit_groups_order(by_week_map, input.week_start);
    Ok(ConfirmPreviewPlan::MultiWeek {
        op_id,
        record_attempt,
        by_week,
        fetch_order,
    })
}

/// Inputs for `_commit_groups` after every remote week has been fetched.
pub struct CommitGroupsBatchInput<'a> {
    pub by_week: &'a Map<String, Value>,
    pub week_start: &'a str,
    pub current_blocks: &'a [Value],
    pub current_revision: &'a Value,
    pub fetched: &'a Map<String, Value>,
    pub today_iso: &'a str,
    pub label: &'a str,
    pub snapshot_label: Option<&'a str>,
    pub operation_id: &'a str,
    pub said: Option<&'a str>,
}

#[derive(Debug, PartialEq)]
pub enum CommitGroupsBatch {
    Say(String),
    Submit {
        pending_save: Value,
        blocks: Option<Vec<Value>>,
        history_label: Option<String>,
        capture_step: bool,
        save_status: Option<String>,
    },
}

impl CommitGroupsBatch {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Submit {
                pending_save,
                blocks,
                history_label,
                capture_step,
                save_status,
            } => json!({
                "kind": "submit",
                "pending_save": pending_save,
                "blocks": blocks,
                "history_label": history_label,
                "capture_step": capture_step,
                "save_status": save_status,
            }),
        }
    }
}

/// Check per-week block capacity and build the `submit_batch` arguments for `_commit_groups`.
pub fn commit_groups_batch(
    input: &CommitGroupsBatchInput,
) -> Result<CommitGroupsBatch, EngineError> {
    let mut writes = Vec::with_capacity(input.by_week.len());
    let mut current_after: Option<Vec<Value>> = None;
    let today = datetext::day_of(input.today_iso)?;
    for (week, added_value) in input.by_week {
        let added = rows(added_value, "blocks")?;
        let (blocks, revision) = if week == input.week_start {
            let mut combined = input.current_blocks.to_vec();
            combined.extend(added.iter().cloned());
            current_after = Some(combined.clone());
            (combined, input.current_revision)
        } else {
            let data = input
                .fetched
                .get(week)
                .ok_or_else(|| EngineError::key(week))?;
            let existing = rows(get(data, "blocks")?.unwrap_or(&Value::Null), "blocks")?;
            let mut combined = existing.clone();
            combined.extend(added.iter().cloned());
            let revision = get(data, "revision")?.ok_or_else(|| EngineError::key("revision"))?;
            (combined, revision)
        };
        if blocks.len() as i64 > reuse::MAX_WEEK_BLOCKS {
            let week_words = reuse::week_label(week, today)?;
            let existing_count = (blocks.len() - added.len()) as i64;
            return Ok(CommitGroupsBatch::Say(planning::capacity_problem(
                existing_count,
                added.len() as i64,
                &week_words,
            )));
        }
        writes.push(crate::session::changes::week_write(
            week, &blocks, revision,
        )?);
    }
    let mut payload = Map::new();
    payload.insert("weeks".into(), Value::Array(writes));
    payload.insert("assignments".into(), json!([]));
    payload.insert("operation_id".into(), json!(input.operation_id));
    if let Some(snapshot) = input.snapshot_label.filter(|text| !text.is_empty()) {
        payload.insert("snapshot_label".into(), json!(snapshot));
    }
    let capture_step = current_after.is_some();
    let history_label = capture_step.then(|| input.label.to_string());
    Ok(CommitGroupsBatch::Submit {
        pending_save: Value::Object(payload),
        blocks: current_after,
        history_label,
        capture_step,
        save_status: input.said.map(str::to_string),
    })
}

/// A copy does not start while signed out. The window then returns without a status line,
/// the same as a missing clipboard.
pub fn copy_block_skipped(signed_in: bool) -> bool {
    !signed_in
}
