//! What the session decides about restore points, account export and import, and week and day file
//! import (P4 group 9): the rules of `desktop/native/controller.py`'s `create_restore_point`,
//! `apply_restore_point`, `export_account`, `preview_account_import`, `apply_account_import` and
//! `import_week_file`, moved here with the same words. The window still sends the requests and applies
//! what is decided here. Group 9B adds the request each of those calls builds, and what a reply does
//! to the list, the preview and the open week.

use flexweek_engine::desk::files::{DAY_FORMAT, merge_imported_blocks, plan_imported_homework};
use flexweek_engine::desk::reuse::MAX_WEEK_BLOCKS;
use flexweek_engine::stored::{self, truthy};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

use super::routines::quote_component;

/// The restore points the window lists, newest first.
pub const RESTORE_POINT_LIMIT: usize = 20;

pub const PREVIEW_FIRST: &str = "Preview the saved copy first.";

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

pub const NAME_THE_SAVED_COPY: &str = "Name the saved copy.";
/// What the status line says while the restore point is being written. The ellipsis is U+2026.
pub const SAVING_A_COPY: &str = "Saving a copy\u{2026}";
pub const RESTORING: &str = "Restoring\u{2026}";
pub const RESTORED: &str = "Restored.";
pub const IMPORTED_ACCOUNT: &str = "Imported account data.";

/// Whether a restore point can be made. A blank name and a signed-out window say the same sentence.
/// `account_id` is read only once the name is usable, so a blank name does not complain about a missing id.
pub fn prepare_create_restore(
    signed_in: bool,
    account_id: Option<i64>,
    label: &str,
) -> EngineResult<CreateRestore> {
    let stripped = py_strip(label);
    if !signed_in || stripped.is_empty() {
        return Ok(CreateRestore::Say(NAME_THE_SAVED_COPY.to_string()));
    }
    let Some(account_id) = account_id else {
        return Err(EngineError::key("id"));
    };
    Ok(CreateRestore::Ready {
        key: create_restore_key(account_id, stripped),
        method: "POST",
        path: "/api/restore-points".to_string(),
        // The attempt id is drawn by the window after this, and written into the body then.
        body: json!({ "label": stripped }),
        progress: SAVING_A_COPY,
    })
}

/// The list and the sentence after a restore point was made. `requested_label` is what was typed,
/// spaces included: it is the sentence only when the point itself has no label.
pub fn finish_create_restore(
    current: &[Value],
    reply: &Value,
    requested_label: &str,
) -> EngineResult<FinishedCreate> {
    let fields = stored::dict(reply)?;
    let point = match fields.get("restore_point") {
        Some(value) if truthy(Some(value)) => value,
        _ => reply,
    };
    let point_fields = stored::dict(point)?;
    let label = point_fields
        .get("label")
        .cloned()
        .unwrap_or_else(|| Value::String(requested_label.to_string()));
    let said = concat_text("Saved copy ", &label)?;
    Ok(FinishedCreate {
        points: restore_points_after_create(current, point),
        words: format!("{said}."),
    })
}

/// The GET for one point's preview. Signed out sends nothing and says nothing.
pub fn prepare_preview_restore(signed_in: bool, point_id: &str) -> PreviewRestore {
    if !signed_in {
        return PreviewRestore::Absent;
    }
    PreviewRestore::Ready {
        method: "GET",
        path: format!("/api/restore-points/{}/preview", quote_component(point_id)),
    }
}

/// Whether this point may be put back, and the POST when it may. The body has no attempt id yet.
pub fn prepare_apply_restore(
    signed_in: bool,
    account_id: Option<i64>,
    preview: Option<&Value>,
    point_id: &str,
) -> EngineResult<ApplyRestore> {
    if let Some(words) = restore_apply_guard(signed_in, preview, point_id) {
        return Ok(ApplyRestore::Say(words.to_string()));
    }
    let Some(account_id) = account_id else {
        return Err(EngineError::key("id"));
    };
    let preview = preview.ok_or_else(|| EngineError::key("state_token"))?;
    let token = subscript(preview, "state_token")?;
    Ok(ApplyRestore::Ready {
        key: restore_key(account_id, point_id),
        method: "POST",
        path: format!("/api/restore-points/{}/restore", quote_component(point_id)),
        body: json!({ "state_token": token }),
        progress: RESTORING,
    })
}

/// What a successful restore does to the window. The week reload keeps the "Restored." line for when
/// the load finishes; it does not discard unsaved edits on its own.
pub fn finish_apply_restore_ok() -> Value {
    json!({
        "clear_preview": true,
        "clear_history": true,
        "focus_after_restore": true,
        "words": RESTORED,
        "reload": true,
        "fetch_points": true,
    })
}

/// A failed restore drops the preview only when the account changed under it (409). Any other
/// failure leaves the preview up so the student can try again.
pub fn finish_apply_restore_err(status: i64) -> Value {
    conflict_clears_preview(status)
}

/// The export POST, or the sentence that waits for unsaved work. Signed out counts as unsaved.
pub fn prepare_export_account(
    signed_in: bool,
    dirty: bool,
    dirty_assignment_count: usize,
    password: &str,
) -> ExportAccount {
    match transfer_blocked(!signed_in || dirty, dirty_assignment_count, "export") {
        Some(words) => ExportAccount::Say(words),
        None => ExportAccount::Ready {
            method: "POST",
            path: "/api/account-export".to_string(),
            body: json!({ "password": password }),
        },
    }
}

/// The import-preview POST, or the same unsaved-work sentence. Signed out counts as unsaved.
pub fn prepare_preview_import(
    signed_in: bool,
    dirty: bool,
    dirty_assignment_count: usize,
    snapshot: &Value,
) -> PreviewImport {
    match transfer_blocked(!signed_in || dirty, dirty_assignment_count, "import") {
        Some(words) => PreviewImport::Say(words),
        None => PreviewImport::Ready {
            method: "POST",
            path: "/api/account-import/preview".to_string(),
            body: json!({ "snapshot": snapshot }),
        },
    }
}

/// The preview the window keeps: the file that was sent, with every field of the reply written over it.
/// A reply field named `snapshot` replaces the file. The reply has to be an object.
pub fn finish_preview_import(snapshot: &Value, data: &Value) -> EngineResult<Value> {
    let Some(fields) = data.as_object() else {
        return Err(type_error(format!(
            "'{}' object is not a mapping",
            stored::type_name(data)
        )));
    };
    let mut merged = Map::new();
    merged.insert("snapshot".to_string(), snapshot.clone());
    for (key, value) in fields {
        merged.insert(key.clone(), value.clone());
    }
    Ok(Value::Object(merged))
}

/// Whether the shown import may be applied. No account or no preview does nothing, without a sentence.
/// Unsaved work is refused before the preview is read, so a preview of the wrong shape still says the
/// sentence. The body has no attempt id yet.
pub fn prepare_apply_import(
    account_id: Option<i64>,
    preview: Option<&Value>,
    dirty: bool,
    dirty_assignment_count: usize,
) -> EngineResult<ApplyImport> {
    let (Some(account_id), Some(preview)) = (account_id, preview) else {
        return Ok(ApplyImport::Absent);
    };
    if let Some(words) = transfer_blocked(dirty, dirty_assignment_count, "import") {
        return Ok(ApplyImport::Say(words));
    }
    let fields = stored::dict(preview)?;
    let token = fields.get("state_token").unwrap_or(&Value::Null);
    let key = import_key(account_id, token);
    let snapshot = subscript(preview, "snapshot")?;
    let state_token = subscript(preview, "state_token")?;
    Ok(ApplyImport::Ready {
        key,
        method: "POST",
        path: "/api/account-import".to_string(),
        body: json!({ "snapshot": snapshot, "state_token": state_token }),
    })
}

/// What a successful import does. The open week is reloaded with its unsaved edits discarded.
pub fn finish_apply_import_ok() -> Value {
    json!({
        "clear_preview": true,
        "clear_history": true,
        "words": IMPORTED_ACCOUNT,
        "reload_discard": true,
        "fetch_points": true,
    })
}

/// A failed import drops the preview only on 409, the same rule as a failed restore.
pub fn finish_apply_import_err(status: i64) -> Value {
    conflict_clears_preview(status)
}

/// `data.get("restore_points") or data.get("points") or []`, then `list` of that.
/// An empty list is skipped, so a reply that sends both keeps `points` when `restore_points` is empty.
pub fn restore_points_from_reply(data: &Value) -> EngineResult<Vec<Value>> {
    let fields = stored::dict(data)?;
    let chosen = if truthy(fields.get("restore_points")) {
        fields.get("restore_points")
    } else if truthy(fields.get("points")) {
        fields.get("points")
    } else {
        None
    };
    stored::py_list(chosen)
}

fn conflict_clears_preview(status: i64) -> Value {
    json!({ "clear_preview": status == 409 })
}

/// `str.strip`, including the four control characters Python treats as space and Rust does not.
fn py_strip(text: &str) -> &str {
    text.trim_matches(|ch: char| {
        ch.is_whitespace() || matches!(ch, '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{1f}')
    })
}

/// `value[key]` for a string key, with the error Python raises.
fn subscript<'a>(value: &'a Value, key: &str) -> EngineResult<&'a Value> {
    match value {
        Value::Object(map) => map.get(key).ok_or_else(|| EngineError::key(key)),
        Value::Array(_) => Err(type_error(
            "list indices must be integers or slices, not str",
        )),
        Value::String(_) => Err(type_error("string indices must be integers, not 'str'")),
        other => Err(type_error(format!(
            "'{}' object is not subscriptable",
            stored::type_name(other)
        ))),
    }
}

fn concat_text(left: &str, value: &Value) -> EngineResult<String> {
    match value {
        Value::String(text) => Ok(format!("{left}{text}")),
        other => Err(type_error(format!(
            "can only concatenate str (not \"{}\") to str",
            stored::type_name(other)
        ))),
    }
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum CreateRestore {
    Say(String),
    Ready {
        key: String,
        method: &'static str,
        path: String,
        body: Value,
        progress: &'static str,
    },
}

impl CreateRestore {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                key,
                method,
                path,
                body,
                progress,
            } => json!({
                "kind": "ready",
                "key": key,
                "method": method,
                "path": path,
                "body": body,
                "progress": progress,
            }),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct FinishedCreate {
    pub points: Vec<Value>,
    pub words: String,
}

impl FinishedCreate {
    pub fn to_json(&self) -> Value {
        json!({ "points": self.points, "words": self.words })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum PreviewRestore {
    Absent,
    Ready { method: &'static str, path: String },
}

impl PreviewRestore {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Ready { method, path } => {
                json!({ "kind": "ready", "method": method, "path": path })
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum ApplyRestore {
    Say(String),
    Ready {
        key: String,
        method: &'static str,
        path: String,
        body: Value,
        progress: &'static str,
    },
}

impl ApplyRestore {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                key,
                method,
                path,
                body,
                progress,
            } => json!({
                "kind": "ready",
                "key": key,
                "method": method,
                "path": path,
                "body": body,
                "progress": progress,
            }),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum ExportAccount {
    Say(String),
    Ready {
        method: &'static str,
        path: String,
        body: Value,
    },
}

impl ExportAccount {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready { method, path, body } => {
                json!({ "kind": "ready", "method": method, "path": path, "body": body })
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum PreviewImport {
    Say(String),
    Ready {
        method: &'static str,
        path: String,
        body: Value,
    },
}

impl PreviewImport {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready { method, path, body } => {
                json!({ "kind": "ready", "method": method, "path": path, "body": body })
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum ApplyImport {
    Absent,
    Say(String),
    Ready {
        key: String,
        method: &'static str,
        path: String,
        body: Value,
    },
}

impl ApplyImport {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                key,
                method,
                path,
                body,
            } => json!({
                "kind": "ready",
                "key": key,
                "method": method,
                "path": path,
                "body": body,
            }),
        }
    }
}
