//! What the session decides about restore points, account export and import, and week and day file
//! import (P4 group 9): the rules of `desktop/native/controller.py`'s `create_restore_point`,
//! `apply_restore_point`, `export_account`, `preview_account_import`, `apply_account_import` and
//! `import_week_file`, moved here with the same words. The window still sends the requests and applies
//! what is decided here.

use flexweek_engine::desk::files::{DAY_FORMAT, merge_imported_blocks, plan_imported_homework};
use flexweek_engine::desk::reuse::MAX_WEEK_BLOCKS;
use flexweek_engine::{EngineError, ErrorKind};
use serde_json::{Value, json};

/// The restore points the window lists, newest first.
pub const RESTORE_POINT_LIMIT: usize = 20;

pub const PREVIEW_FIRST: &str = "Preview the restore point first.";

/// The list after a restore point was made: the new one first, any older one with the same id gone, and
/// no more than [`RESTORE_POINT_LIMIT`].
pub fn restore_points_after_create(current: &[Value], point: &Value) -> Vec<Value> {
    let mut points = vec![point.clone()];
    points.extend(
        current
            .iter()
            .filter(|item| {
                item.get("id").unwrap_or(&Value::Null) != point.get("id").unwrap_or(&Value::Null)
            })
            .cloned(),
    );
    points.truncate(RESTORE_POINT_LIMIT);
    points
}

/// The words that refuse a restore, or `None` when it may go ahead: only a signed-in session with the
/// preview of this very point on screen may restore.
pub fn restore_apply_guard(
    signed_in: bool,
    preview: Option<&Value>,
    point_id: &str,
) -> Option<&'static str> {
    let shown = preview
        .and_then(|found| found.get("id"))
        .and_then(Value::as_str);
    (!signed_in || shown != Some(point_id)).then_some(PREVIEW_FIRST)
}

/// The words that stop an export or import while changes are unsaved, or `None`. `verb` is "export" or
/// "import".
pub fn transfer_blocked(dirty: bool, dirty_assignment_count: usize, verb: &str) -> Option<String> {
    (dirty || dirty_assignment_count > 0)
        .then(|| format!("Save your last change first (More > Retry save), then {verb}."))
}

/// The key a repeated "save a restore point" request shares, so a retry is the same operation.
pub fn create_restore_key(account_id: i64, label: &str) -> String {
    format!("create-restore|{account_id}|{label}")
}

pub fn restore_key(account_id: i64, point_id: &str) -> String {
    format!("restore|{account_id}|{point_id}")
}

/// `state_token` is the preview's token as the service sent it; a missing one reads "None", as the
/// window's text formatting always has.
pub fn import_key(account_id: i64, state_token: &Value) -> String {
    let token = match state_token {
        Value::Null => "None".to_string(),
        Value::String(text) => text.clone(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        other => other.to_string(),
    };
    format!("import|{account_id}|{token}")
}

/// What `import_week_file` needs besides the file: the week on screen, the words for it and for the
/// week the file names, what the week holds now, and the caller's choice (`None` when not asked).
pub struct ImportContext<'a> {
    pub week_start: &'a str,
    pub week_words: &'a str,
    pub target_words: &'a str,
    pub blocks: &'a Value,
    pub assignments: &'a Value,
    pub replace: Option<bool>,
}

#[derive(Debug, PartialEq)]
pub enum ImportDecision {
    /// Nothing is imported; these are the words to say.
    Say(String),
    /// Put these blocks in the week and add this homework (each already at revision 0).
    Apply {
        blocks: Vec<Value>,
        create: Vec<Value>,
    },
}

impl ImportDecision {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "say": words }),
            Self::Apply { blocks, create } => json!({ "blocks": blocks, "create": create }),
        }
    }
}

fn say(words: impl Into<String>) -> Result<ImportDecision, EngineError> {
    Ok(ImportDecision::Say(words.into()))
}

fn list_or_empty(value: Option<&Value>) -> Value {
    match value {
        Some(Value::Array(items)) if !items.is_empty() => Value::Array(items.clone()),
        _ => json!([]),
    }
}

/// What to do with a parsed week or day file: refuse it in words, or the blocks and homework to apply.
/// A failure of the engine's own file rules that is not a refusal comes back as the error.
pub fn import_week_decision(
    parsed: &Value,
    context: &ImportContext,
) -> Result<ImportDecision, EngineError> {
    if let Some(Value::String(error)) = parsed.get("error")
        && !error.is_empty()
    {
        return say(error.clone());
    }
    let target = match parsed.get("week_start") {
        Some(Value::String(text)) if !text.is_empty() => text.as_str(),
        _ => context.week_start,
    };
    if target != context.week_start {
        return say(format!(
            "Nothing imported: this file is for {}. Go to that week, then import again.",
            context.target_words
        ));
    }
    let plan = plan_imported_homework(
        &list_or_empty(parsed.get("assignments")),
        &list_or_empty(parsed.get("blocks")),
        &json!(context.week_start),
        context.assignments,
    )?;
    let day_file = parsed.get("format").and_then(Value::as_str) == Some(DAY_FORMAT);
    let mode = match context.replace {
        Some(true) => "replace",
        Some(false) => "merge",
        None if day_file => "merge",
        None => "replace",
    };
    let week_has_blocks = context
        .blocks
        .as_array()
        .is_some_and(|blocks| !blocks.is_empty());
    if mode == "replace" && week_has_blocks && context.replace != Some(true) {
        return say(format!(
            "Nothing imported: it would replace everything in {}. Import again and choose Replace week.",
            context.week_words
        ));
    }
    let day = parsed.get("day").cloned().unwrap_or(Value::Null);
    let merged = match merge_imported_blocks(context.blocks, &plan["blocks"], &json!(mode), &day) {
        Ok(merged) => merged,
        Err(error) if matches!(error.kind, ErrorKind::Value) => {
            return say(format!("{} Nothing was imported.", error.message));
        }
        Err(error) => return Err(error),
    };
    if merged.len() as i64 > MAX_WEEK_BLOCKS {
        return say(format!(
            "{} would exceed {MAX_WEEK_BLOCKS} blocks. Uncheck an item or remove a block first.",
            context.week_words
        ));
    }
    // New to this account, so not yet saved: revision 0, as Add gives new homework.
    let create = plan["create"]
        .as_array()
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    let mut item = item.clone();
                    if let Some(fields) = item.as_object_mut() {
                        fields.insert("revision".into(), json!(0));
                    }
                    item
                })
                .collect()
        })
        .unwrap_or_default();
    Ok(ImportDecision::Apply {
        blocks: merged,
        create,
    })
}
