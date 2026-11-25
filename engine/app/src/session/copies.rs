//! Clipboard, copy rows and relocation (P4 group 4, slice 4C): the rules of
//! `desktop/native/controller.py`'s `_fixed_copy_rows`, the empty-offer choice in
//! `copy_last_week_fixed_rows`, `date_problem`, the decision half of `_commit_move_to_date`,
//! `paste_destination`, `copy_block`, `copy_day`, the destination half of `paste_proposals`,
//! `duplicate_selected`'s day default aside, and the head of `confirm_preview`, moved here with the
//! same words. The window keeps the state: it reads the clock, fetches weeks, draws ids, looks
//! assignments up, writes what is decided here, then settles the week (`_touch`), saves, and keeps
//! history and attempts — none of which move.

use flexweek_engine::desk::{calendar, clipboard, grid, planning, reuse};
use flexweek_engine::shown;
use flexweek_engine::stored::{py_str, truthy, type_name};
use flexweek_engine::{EngineError, ErrorKind};
use serde_json::{Value, json};

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
    "That's outside the hours FlexWeek plans in, so it stayed where it was.";

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
