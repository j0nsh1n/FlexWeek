//! The live week, the weeks set aside, the save under way, the retry attempts and both history stacks
//! (P4 group 2, cut 2D): what `desktop/native/controller.py`'s `NativeSession` held as attributes. The
//! window reads one field at a time with `view("drafts.<field>")` and changes them only with `drafts_*`
//! commands. Every answer carries each field's version, so the window knows which of its copies are out
//! of date. The decisions themselves are 2A-2C's (changes.rs, week.rs, `desk::history`); this module
//! applies them to the state it owns, in the order the window applied them.

mod effects;

use std::collections::{BTreeMap, BTreeSet, HashSet, VecDeque};

use flexweek_engine::desk::history;
use flexweek_engine::shown::stored_weeks;
use flexweek_engine::stored::truthy;
use flexweek_store::Revision;
use serde_json::{Map, Value, json};

use super::changes::{self, SaveAnswer, SaveDraft, SaveFailureKind, StepPlace, Travel};
use super::week::{self, DraftFlags, History, LoadFinish, LoadReply, LoadRoute, ReadWeek, Row};

/// A week's own fields: what the open week holds and what a week set aside keeps.
const WEEK_FIELDS: [&str; 21] = [
    "week_start",
    "blocks",
    "revision",
    "stored_parts",
    "assignments",
    "dirty_assignments",
    "trace",
    "dirty",
    "conflict",
    "pending_save",
    "undo",
    "redo",
    "committed_blocks",
    "assignments_basis",
    "committed_assignments",
    "pending_step",
    "history_label",
    "repeats",
    "saved_repeats",
    "repeat_send",
    "repeat_ack",
];

/// The save under way and the retry attempts: the window's, whichever week is open.
const SAVE_FIELDS: [&str; 7] = [
    "join_step",
    "plan_step_id",
    "save_status",
    "last_save_refused",
    "preview_attempt",
    "move_attempt",
    "attempts",
];

const HISTORY_LABEL: &str = "editing the week";

fn default_value(name: &str) -> Value {
    match name {
        "week_start" => json!(""),
        "blocks" | "stored_parts" | "dirty_assignments" | "undo" | "redo" | "committed_blocks"
        | "assignments_basis" | "repeats" | "saved_repeats" => json!([]),
        "revision" => json!(0),
        "assignments" | "committed_assignments" | "attempts" => json!({}),
        "dirty" | "conflict" | "join_step" | "last_save_refused" => json!(false),
        "history_label" => json!(HISTORY_LABEL),
        _ => Value::Null,
    }
}

fn known(name: &str) -> bool {
    WEEK_FIELDS.contains(&name) || SAVE_FIELDS.contains(&name)
}

/// A history step with the token that stands for its identity: the window compares tokens where it
/// compared objects (a notice loses its Undo once a later step is saved). A step put back on its
/// stack keeps its token; a join, a restore or a replaced stack makes new ones.
type Stack = Vec<(u64, Value)>;

/// A week set aside: its fields as they were, and the selection the window had in it.
#[derive(Clone, Debug)]
struct Parked {
    fields: Map<String, Value>,
    selection: Value,
}

/// What a delete answer will change, read before anything is changed.
struct DeletePrepared {
    removed: Map<String, Value>,
    current: Option<(Value, Revision, Value)>,
    parked: Vec<Map<String, Value>>,
}

/// A homework delete waiting for its answer, then for the other weeks it read back for Undo.
#[derive(Clone, Debug)]
struct Deleting {
    homework: String,
    title: String,
    key: String,
    before: Vec<Value>,
    item: Value,
    step: Option<Value>,
    removed: Map<String, Value>,
    others: VecDeque<String>,
    reading: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
struct PendingBatch {
    request: Map<String, Value>,
    stay: Option<bool>,
}

impl PendingBatch {
    fn capture(value: Value) -> Result<Option<Self>, String> {
        let mut request = match value {
            Value::Null => return Ok(None),
            Value::Object(request) => request,
            _ => return Err("pending_save must be an object".into()),
        };
        let stay = match request.shift_remove("stay") {
            None | Some(Value::Null) => None,
            Some(Value::Bool(stay)) => Some(stay),
            _ => return Err("stay must be a boolean".into()),
        };
        Ok(Some(Self { request, stay }))
    }

    fn project(&self) -> Value {
        let mut request = self.request.clone();
        if let Some(stay) = self.stay {
            request.insert("stay".into(), json!(stay));
        }
        Value::Object(request)
    }
}

#[derive(Clone, Debug)]
struct WeekDraft {
    fields: Map<String, Value>,
    revision: Revision,
    pending: Option<PendingBatch>,
    undo: Stack,
    redo: Stack,
}

impl Default for WeekDraft {
    fn default() -> Self {
        let fields = WEEK_FIELDS
            .into_iter()
            .filter(|name| !matches!(*name, "revision" | "pending_save" | "undo" | "redo"))
            .map(|name| (name.to_string(), default_value(name)))
            .collect();
        Self {
            fields,
            revision: Revision::Stored(0),
            pending: None,
            undo: Vec::new(),
            redo: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Default)]
enum HistoryAction {
    #[default]
    Save,
    EarlierWeeks(Value),
    Travel {
        direction: Travel,
        token: u64,
        step: Value,
    },
}

impl HistoryAction {
    fn direction(&self) -> Option<Travel> {
        match self {
            Self::Travel { direction, .. } => Some(*direction),
            _ => None,
        }
    }

    fn step(&self) -> Option<&Value> {
        match self {
            Self::Save => None,
            Self::EarlierWeeks(step) | Self::Travel { step, .. } => Some(step),
        }
    }
}

#[derive(Debug)]
pub struct Drafts {
    week: WeekDraft,
    save: Map<String, Value>,
    action: HistoryAction,
    parked: Vec<(String, Parked)>,
    versions: BTreeMap<String, u64>,
    clock: u64,
    deleting: Option<Deleting>,
    effects: effects::Effects,
}

/// Everything an answer can change but the effects waiting for answers, kept so a failed answer
/// leaves the session as it was.
struct Saved {
    week: WeekDraft,
    save: Map<String, Value>,
    action: HistoryAction,
    parked: Vec<(String, Parked)>,
    versions: BTreeMap<String, u64>,
    clock: u64,
    deleting: Option<Deleting>,
}

impl Drafts {
    fn keep_state(&self) -> Saved {
        Saved {
            week: self.week.clone(),
            save: self.save.clone(),
            action: self.action.clone(),
            parked: self.parked.clone(),
            versions: self.versions.clone(),
            clock: self.clock,
            deleting: self.deleting.clone(),
        }
    }

    fn put_state_back(&mut self, saved: Saved) {
        self.week = saved.week;
        self.save = saved.save;
        self.action = saved.action;
        self.parked = saved.parked;
        self.versions = saved.versions;
        self.clock = saved.clock;
        self.deleting = saved.deleting;
    }
}

impl Default for Drafts {
    fn default() -> Self {
        Self {
            week: WeekDraft::default(),
            save: SAVE_FIELDS
                .into_iter()
                .map(|name| (name.to_string(), default_value(name)))
                .collect(),
            action: HistoryAction::Save,
            parked: Vec::new(),
            versions: BTreeMap::new(),
            clock: 0,
            deleting: None,
            effects: effects::Effects::default(),
        }
    }
}

fn flags_of(fields: &Map<String, Value>) -> DraftFlags {
    DraftFlags {
        dirty: truthy(fields.get("dirty")),
        dirty_assignments: truthy(fields.get("dirty_assignments")),
        pending_save: truthy(fields.get("pending_save")),
    }
}

fn text<'a>(command: &'a Value, name: &str) -> Result<&'a str, String> {
    command[name]
        .as_str()
        .ok_or_else(|| format!("{name} is text"))
}

fn optional_text<'a>(command: &'a Value, name: &str) -> Result<Option<&'a str>, String> {
    match &command[name] {
        Value::Null => Ok(None),
        value => value
            .as_str()
            .map(Some)
            .ok_or_else(|| format!("{name} is text or null")),
    }
}

fn flag(command: &Value, name: &str) -> Result<bool, String> {
    command[name]
        .as_bool()
        .ok_or_else(|| format!("{name} is true or false"))
}

fn optional_flag(command: &Value, name: &str) -> Result<bool, String> {
    match &command[name] {
        Value::Null => Ok(false),
        value => value
            .as_bool()
            .ok_or_else(|| format!("{name} is true or false")),
    }
}

fn rows<'a>(value: &'a Value, name: &str) -> Result<&'a [Value], String> {
    value
        .as_array()
        .filter(|rows| rows.iter().all(Value::is_object))
        .map(Vec::as_slice)
        .ok_or_else(|| format!("{name} must be a list of objects"))
}

fn optional_rows<'a>(value: &'a Value, name: &str) -> Result<&'a [Value], String> {
    if value.is_null() {
        Ok(&[])
    } else {
        rows(value, name)
    }
}

fn object<'a>(value: &'a Value, name: &str) -> Result<&'a Map<String, Value>, String> {
    value
        .as_object()
        .ok_or_else(|| format!("{name} must be an object"))
}

fn owned_rows(value: &Value, name: &str) -> Result<Vec<Row>, String> {
    Ok(rows(value, name)?
        .iter()
        .filter_map(|row| row.as_object().cloned())
        .collect())
}

fn engine(error: flexweek_engine::EngineError) -> String {
    error.message
}

fn checked_revision(revision: &Value) -> Result<Revision, String> {
    match revision {
        Value::Number(number) => number.as_i64().map(Revision::Stored),
        Value::Array(parts) => match parts.as_slice() {
            [first, second] => first
                .as_i64()
                .zip(second.as_i64())
                .map(|(first, second)| Revision::Shown(first, second)),
            _ => None,
        },
        _ => None,
    }
    .ok_or_else(|| "revision must be an integer or two stored-week revisions".to_string())
}

fn revision_json(revision: &Revision) -> Value {
    match revision {
        Revision::Stored(revision) => json!(revision),
        Revision::Shown(first, second) => json!([first, second]),
    }
}

fn of_homework(block: &Value, homework: &str) -> bool {
    block.get("assignment_id").and_then(Value::as_str) == Some(homework)
}

fn without_homework(blocks: &Value, homework: &str) -> Value {
    Value::Array(
        blocks
            .as_array()
            .map(|blocks| {
                blocks
                    .iter()
                    .filter(|block| !of_homework(block, homework))
                    .cloned()
                    .collect()
            })
            .unwrap_or_default(),
    )
}

/// `int(value or 0)` for a homework's revision.
fn whole_revision(value: Option<&Value>) -> Result<i64, String> {
    if !truthy(value) {
        return Ok(0);
    }
    match value {
        Some(Value::Bool(_)) => Ok(1),
        Some(Value::Number(number)) => number
            .as_i64()
            .ok_or_else(|| "revision is too large".to_string()),
        Some(Value::String(text)) => text
            .trim()
            .parse()
            .map_err(|_| format!("invalid literal for int(): {text:?}")),
        _ => Err("a homework revision must be a number".into()),
    }
}

/// Sorted and without repeats, as the window's set read: the order a set had was never used.
fn id_set(value: &Value) -> Result<Value, String> {
    let ids = value
        .as_array()
        .ok_or("dirty_assignments is a list of ids")?
        .iter()
        .map(|id| {
            id.as_str()
                .map(str::to_string)
                .ok_or_else(|| "dirty_assignments is a list of ids".to_string())
        })
        .collect::<Result<BTreeSet<String>, String>>()?;
    Ok(json!(ids))
}

impl Drafts {
    fn bump(&mut self, name: &str) {
        self.clock += 1;
        self.versions.insert(name.to_string(), self.clock);
    }

    fn get(&self, name: &str) -> Value {
        match name {
            "undo" => Value::Array(
                self.week
                    .undo
                    .iter()
                    .map(|(_, step)| step.clone())
                    .collect(),
            ),
            "redo" => Value::Array(
                self.week
                    .redo
                    .iter()
                    .map(|(_, step)| step.clone())
                    .collect(),
            ),
            "revision" => revision_json(&self.week.revision),
            "pending_save" => self
                .week
                .pending
                .as_ref()
                .map_or(Value::Null, PendingBatch::project),
            _ => self.field(name).clone(),
        }
    }

    fn field(&self, name: &str) -> &Value {
        static NULL: Value = Value::Null;
        self.week
            .fields
            .get(name)
            .or_else(|| self.save.get(name))
            .unwrap_or(&NULL)
    }

    fn put(&mut self, name: &str, value: Value) {
        let changed =
            self.field(name) != &value || matches!(name, "assignments" | "committed_assignments");
        let fields = if SAVE_FIELDS.contains(&name) {
            &mut self.save
        } else {
            &mut self.week.fields
        };
        fields.insert(name.to_string(), value);
        if changed {
            self.bump(name);
        }
    }

    fn set_revision(&mut self, revision: Revision) {
        if self.week.revision != revision {
            self.week.revision = revision;
            self.bump("revision");
        }
    }

    fn set_pending(&mut self, pending: Option<PendingBatch>) {
        if self.week.pending != pending {
            self.week.pending = pending;
            self.bump("pending_save");
        }
    }

    fn restore_stack(&mut self, redo: bool, value: Value) {
        // A parked copy used fresh Python objects, so restoring it gives its steps fresh tokens.
        let steps = match value {
            Value::Array(steps) => steps,
            _ => Vec::new(),
        };
        let stack = steps.into_iter().map(|step| (self.token(), step)).collect();
        self.set_stack(redo, stack);
    }

    fn token(&mut self) -> u64 {
        self.clock += 1;
        self.clock
    }

    fn set_stack(&mut self, redo: bool, stack: Stack) {
        let (slot, name) = if redo {
            (&mut self.week.redo, "redo")
        } else {
            (&mut self.week.undo, "undo")
        };
        if *slot != stack {
            *slot = stack;
            self.bump(name);
        }
    }

    fn stack(&self, redo: bool) -> &Stack {
        if redo {
            &self.week.redo
        } else {
            &self.week.undo
        }
    }

    /// `history.push_step`: one step on, the oldest off past the limit.
    fn push_step(&mut self, redo: bool, token: u64, step: Value) {
        let mut stack = self.stack(redo).clone();
        stack.push((token, step));
        if history::over_limit(stack.len()) {
            stack.remove(0);
        }
        self.set_stack(redo, stack);
    }

    /// `list.append`, with no limit, as the window put a step back.
    fn append_step(&mut self, redo: bool, token: u64, step: Value) {
        let mut stack = self.stack(redo).clone();
        stack.push((token, step));
        self.set_stack(redo, stack);
    }

    fn week_start(&self) -> String {
        self.field("week_start")
            .as_str()
            .unwrap_or_default()
            .to_string()
    }

    fn flags(&self) -> DraftFlags {
        DraftFlags {
            dirty: truthy(Some(self.field("dirty"))),
            dirty_assignments: !self.dirty_ids().is_empty(),
            pending_save: self
                .week
                .pending
                .as_ref()
                .is_some_and(|pending| !pending.request.is_empty() || pending.stay.is_some()),
        }
    }

    fn assignments(&self) -> Map<String, Value> {
        self.field("assignments")
            .as_object()
            .cloned()
            .unwrap_or_default()
    }

    fn dirty_ids(&self) -> Vec<String> {
        self.field("dirty_assignments")
            .as_array()
            .map(|ids| {
                ids.iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default()
    }

    fn set_dirty_ids(&mut self, ids: impl IntoIterator<Item = String>) {
        let ids: BTreeSet<String> = ids.into_iter().collect();
        self.put("dirty_assignments", json!(ids));
    }

    pub(super) fn save_flags(&self) -> (bool, bool, bool) {
        (
            truthy(Some(self.field("conflict"))),
            self.flags().dirty,
            self.week.pending.is_some(),
        )
    }

    pub(super) fn leave_flags(&self) -> (bool, bool) {
        (
            self.flags().held(),
            week::first_held(&self.parked_flags()).is_some(),
        )
    }

    pub(super) fn versions(&self) -> Value {
        let mut versions = Map::new();
        for name in WEEK_FIELDS.iter().chain(SAVE_FIELDS.iter()) {
            versions.insert(
                (*name).to_string(),
                json!(self.versions.get(*name).copied().unwrap_or(0)),
            );
        }
        Value::Object(versions)
    }

    /// The open week's head Undo step and its token, or nulls.
    pub fn last_step(&self) -> Value {
        match self.week.undo.last() {
            Some((token, step)) => json!({ "step": step, "token": token }),
            None => json!({ "step": null, "token": null }),
        }
    }

    pub fn parked_count(&self) -> usize {
        self.parked.len()
    }

    pub fn view(&self, name: &str) -> Option<Value> {
        let suffix = name.strip_prefix("drafts.")?;
        match suffix {
            "versions" => Some(self.versions()),
            "last_step" => Some(self.last_step()),
            "meta" => Some(json!({
                "held": self.flags().held(),
                "parked_count": self.parked_count(),
                "parked_held": week::first_held(&self.parked_flags()).cloned(),
            })),
            field if known(field) => Some(self.get(field)),
            _ => None,
        }
    }

    fn snapshot(&self, selection: &Value) -> Parked {
        let mut fields = Map::new();
        for name in WEEK_FIELDS {
            fields.insert(name.to_string(), self.get(name));
        }
        Parked {
            fields,
            selection: selection.clone(),
        }
    }

    /// `drafts[key] = snapshot`: a week already set aside keeps its place in the order.
    fn park(&mut self, key: String, selection: &Value) {
        let parked = self.snapshot(selection);
        match self.parked.iter_mut().find(|(start, _)| *start == key) {
            Some(slot) => slot.1 = parked,
            None => self.parked.push((key, parked)),
        }
    }

    fn take_parked(&mut self, key: &str) -> Option<Parked> {
        let at = self.parked.iter().position(|(start, _)| start == key)?;
        Some(self.parked.remove(at).1)
    }

    fn find_parked(&self, key: &str) -> Option<&Parked> {
        self.parked
            .iter()
            .find(|(start, _)| start == key)
            .map(|(_, parked)| parked)
    }

    /// The week set aside becomes the open week; its steps are new objects, as a copy made them.
    /// The fallible parts are read first, so a bad parked copy changes nothing.
    fn restore(&mut self, parked: &Parked) -> Result<Value, String> {
        let field = |name: &str| {
            parked
                .fields
                .get(name)
                .cloned()
                .unwrap_or_else(|| default_value(name))
        };
        let mut revision = Some(checked_revision(&field("revision"))?);
        let mut pending = Some(PendingBatch::capture(field("pending_save"))?);
        for name in WEEK_FIELDS {
            match name {
                "undo" | "redo" => self.restore_stack(name == "redo", field(name)),
                "revision" => {
                    if let Some(revision) = revision.take() {
                        self.set_revision(revision);
                    }
                }
                "pending_save" => {
                    if let Some(pending) = pending.take() {
                        self.set_pending(pending);
                    }
                }
                _ => self.put(name, field(name)),
            }
        }
        Ok(parked.selection.clone())
    }

    fn parked_flags(&self) -> Vec<(String, DraftFlags)> {
        self.parked
            .iter()
            .map(|(start, parked)| (start.clone(), flags_of(&parked.fields)))
            .collect()
    }

    /// One `drafts_*` command; the answer carries the versions.
    pub(super) fn command(
        &mut self,
        command: &Value,
        status: &super::Status,
        epoch: u64,
    ) -> Result<Value, String> {
        let ticket = status.ticket();
        let mut answer = match command["cmd"].as_str().unwrap_or_default() {
            "drafts_reply" => self.answer_effect(command, epoch, ticket)?,
            "drafts_refresh" => self.refresh_effect(epoch),
            name @ ("drafts_fetch" | "drafts_post" | "drafts_delete_start") => {
                if command["ticket"].as_u64() != Some(ticket) || !status.busy() {
                    return Err("the week request is no longer current".into());
                }
                match name {
                    "drafts_fetch" => self.fetch_effect(command, epoch, ticket)?,
                    "drafts_post" => self.post_effect(command, epoch, ticket)?,
                    _ => self.delete_effect(command, epoch, ticket)?,
                }
            }
            _ => self.run(command, status.busy())?,
        };
        if let Value::Object(fields) = &mut answer {
            fields.insert("versions".into(), self.versions());
        }
        Ok(answer)
    }

    fn run(&mut self, command: &Value, busy: bool) -> Result<Value, String> {
        match command["cmd"].as_str().unwrap_or_default() {
            "drafts_set" => self.set_fields(command),
            "drafts_clear" => {
                self.clear(text(command, "week_start")?);
                Ok(json!({}))
            }
            "drafts_set_week_start" => {
                self.put("week_start", json!(text(command, "week_start")?));
                Ok(json!({}))
            }
            "drafts_load" => self.load(command),
            "drafts_reload" => {
                self.set_pending(None);
                self.put("dirty", json!(false));
                self.put("conflict", json!(false));
                self.set_dirty_ids([]);
                Ok(json!({}))
            }
            "drafts_remote_change" => self.remote_change(command, busy),
            "drafts_wrote_open" => self.wrote_open(command),
            "drafts_touch" => self.touch(command),
            "drafts_credit_focus" => self.credit_focus(command),
            "drafts_add_focus_time" => self.add_focus_time(command),
            "drafts_submit_batch" => self.submit_batch(command),
            "drafts_apply_plan" => self.apply_plan(command),
            "drafts_can" => {
                let redo = flag(command, "redo")?;
                Ok(json!({ "can": self.can_travel(redo, busy) }))
            }
            "drafts_travel" => self.travel(flag(command, "redo")?, busy),
            "drafts_save" => self.save(command),
            "drafts_drop_refused" => Ok(json!({ "dropped": self.drop_refused() })),
            "drafts_attempt" => self.attempt(command),
            "drafts_preview_attempt" => {
                self.put("preview_attempt", json!(text(command, "key")?));
                Ok(json!({}))
            }
            "drafts_forget_attempt" => {
                let mut attempts = self
                    .field("attempts")
                    .as_object()
                    .cloned()
                    .unwrap_or_default();
                if attempts.shift_remove(text(command, "key")?).is_some() {
                    self.put("attempts", Value::Object(attempts));
                }
                Ok(json!({}))
            }
            "drafts_history_clear" => {
                self.set_stack(false, Vec::new());
                self.set_stack(true, Vec::new());
                Ok(json!({}))
            }
            "drafts_local" => Ok(json!({ "week": self.local(text(command, "week_start")?) })),
            "drafts_parked" => {
                let week = self
                    .find_parked(text(command, "week_start")?)
                    .map(|parked| {
                        json!({
                            "blocks": parked.fields.get("blocks").cloned().unwrap_or(json!([])),
                            "trace": parked.fields.get("trace").cloned().unwrap_or(Value::Null),
                        })
                    });
                Ok(json!({ "week": week }))
            }
            "drafts_unsaved" => {
                let flags = self.parked_flags();
                let weeks: Vec<Value> = week::dirty_parked(&flags)
                    .filter_map(|start| {
                        let parked = self.find_parked(start)?;
                        let field = |name: &str| parked.fields.get(name).cloned().unwrap_or_default();
                        Some(json!([
                            start,
                            { "blocks": field("blocks"), "assignments": field("assignments"), "trace": field("trace") }
                        ]))
                    })
                    .collect();
                Ok(json!({ "weeks": weeks }))
            }
            "drafts_parked_held" => {
                Ok(json!({ "week": week::first_held(&self.parked_flags()).cloned() }))
            }
            "drafts_meta" => Ok(json!({ "held": self.flags().held() })),
            other => Err(format!("no command called {other:?}")),
        }
    }

    // Fixture writes use the same parsed state as edit and submission commands.
    fn set_fields(&mut self, command: &Value) -> Result<Value, String> {
        let fields = object(&command["fields"], "fields")?;
        for (name, value) in fields {
            match name.as_str() {
                "revision" => self.set_revision(checked_revision(value)?),
                "pending_save" => self.set_pending(PendingBatch::capture(value.clone())?),
                "dirty_assignments" => self.put(name, id_set(value)?),
                "week_start" | "blocks" | "stored_parts" | "assignments" | "trace" | "dirty"
                | "conflict" => self.put(name, value.clone()),
                _ => return Err(format!("no writable fixture field called {name:?}")),
            }
        }
        Ok(json!({}))
    }

    /// The account is gone: the window's `_clear_local`. Whether a save joins, its held words, its
    /// refusal and the move attempt stay as they were, as they did in the window.
    pub fn clear(&mut self, week_start: &str) {
        for name in self.week.fields.keys().cloned().collect::<Vec<_>>() {
            self.put(&name, default_value(&name));
        }
        self.set_revision(Revision::Stored(0));
        self.set_pending(None);
        self.set_stack(false, Vec::new());
        self.set_stack(true, Vec::new());
        self.put("week_start", json!(week_start));
        for name in ["plan_step_id", "preview_attempt", "attempts"] {
            self.put(name, default_value(name));
        }
        self.action = HistoryAction::Save;
        self.parked.clear();
        self.deleting = None;
        self.effects.clear();
    }

    fn load(&mut self, command: &Value) -> Result<Value, String> {
        let requested = text(command, "requested")?;
        let first_weekday = command["first_weekday"]
            .as_u64()
            .and_then(|day| u32::try_from(day).ok())
            .ok_or("first_weekday is a whole number")?;
        let discard = flag(command, "discard")?;
        let selection = &command["selection"];
        let open = self.week_start();
        let route = week::select_week(
            requested,
            &open,
            first_weekday,
            discard,
            self.flags(),
            &self.parked_flags(),
        )
        .map_err(engine)?;
        Ok(match route {
            LoadRoute::KeepOpen => json!({ "action": "keep" }),
            LoadRoute::Restore {
                start,
                park_open,
                words,
            } => {
                // A parked week that cannot be restored stays parked, and the open week stays open.
                let parked_before = self.parked.clone();
                if park_open {
                    self.park(open, selection);
                }
                let Some(parked) = self.take_parked(&start) else {
                    self.parked = parked_before;
                    return Err(format!("no week set aside from {start}"));
                };
                let selection = match self.restore(&parked) {
                    Ok(selection) => selection,
                    Err(error) => {
                        self.parked = parked_before;
                        return Err(error);
                    }
                };
                json!({ "action": "restore", "start": start, "words": words, "selection": selection })
            }
            LoadRoute::Fetch {
                start,
                discard_parked,
            } => {
                if discard_parked {
                    self.take_parked(&start);
                }
                json!({ "action": "fetch", "start": start })
            }
        })
    }

    /// Both reads are in: the read week becomes the open week, the open one set aside when it moved
    /// with changes the server does not have.
    fn install(&mut self, command: &Value) -> Result<Value, String> {
        let previous = text(command, "previous")?;
        let said = optional_text(command, "said")?;
        let reply = object(&command["week"], "week")?;
        let loaded = reply.get("week_start").cloned().unwrap_or(Value::Null);
        let start = loaded
            .as_str()
            .ok_or("week_start must be text")?
            .to_string();
        let read = ReadWeek {
            start,
            revision: checked_revision(reply.get("revision").unwrap_or(&Value::Null))?,
            blocks: owned_rows(reply.get("blocks").unwrap_or(&Value::Null), "blocks")?,
            stored: match reply.get("stored") {
                None | Some(Value::Null) => Vec::new(),
                Some(stored) => owned_rows(stored, "stored")?,
            },
            repeats: match reply.get("repeats") {
                None | Some(Value::Null) => Vec::new(),
                Some(repeats) => owned_rows(repeats, "repeats")?,
            },
        };
        let finished = week::finish_load(
            previous,
            LoadReply::Read {
                week: read,
                assignments: owned_rows(&command["assignments"], "assignments")?,
                revision: self.week.revision,
                current: self.flags(),
            },
        )
        .map_err(engine)?;
        let LoadFinish::Install {
            week,
            assignments,
            park_open,
            history,
        } = finished
        else {
            return Err("both reads are in".into());
        };
        if park_open {
            self.park(previous.to_string(), &command["selection"]);
        }
        match history {
            History::Keep => {}
            History::Clear => {
                self.set_stack(false, Vec::new());
                self.set_stack(true, Vec::new());
            }
            History::MarkStale => {
                for redo in [false, true] {
                    let mut stack = self.stack(redo).clone();
                    for (_, step) in &mut stack {
                        if history::touches(step, &loaded).map_err(engine)? {
                            step["stale"] = json!(true);
                        }
                    }
                    self.set_stack(redo, stack);
                }
            }
        }
        self.take_parked(&week.start);
        let blocks = Value::Array(week.blocks.into_iter().map(Value::Object).collect());
        let repeats = Value::Array(week.repeats.into_iter().map(Value::Object).collect());
        let assignments = Value::Object(assignments);
        self.put("blocks", blocks.clone());
        self.set_revision(week.revision);
        self.put(
            "stored_parts",
            Value::Array(week.stored.into_iter().map(Value::Object).collect()),
        );
        self.put("repeats", repeats.clone());
        self.put("saved_repeats", repeats);
        self.put("repeat_send", Value::Null);
        self.put("repeat_ack", Value::Null);
        self.put("week_start", json!(week.start));
        self.put("dirty", json!(false));
        self.put("conflict", json!(false));
        self.set_pending(None);
        self.put("pending_step", Value::Null);
        self.put("trace", Value::Null);
        self.put("assignments", assignments.clone());
        self.set_dirty_ids([]);
        self.put("committed_blocks", blocks.clone());
        self.put("assignments_basis", blocks);
        self.put("committed_assignments", assignments);
        Ok(json!({ "words": week::load_words(said), "start": week.start }))
    }

    /// An edit to the open week: the blocks as the window settled them, optional homework rows and
    /// repeat updates, and the label of its Undo step. The week is changed, any batch is dropped, and
    /// the last plan's notes go unless `trace` is explicitly given.
    fn touch(&mut self, command: &Value) -> Result<Value, String> {
        if let Some(label) = command.get("label").filter(|label| truthy(Some(label))) {
            self.put("history_label", label.clone());
        }
        if let Some(homeworks) = command.get("put_homework").filter(|value| !value.is_null()) {
            for row in rows(homeworks, "put_homework")? {
                self.put_homework(row)?;
            }
        }
        if let Some(repeats) = command.get("repeats").filter(|value| !value.is_null()) {
            rows(repeats, "repeats")?;
            self.put("repeats", repeats.clone());
        }
        if let Some(changes) = command.get("hold_repeats").filter(|value| !value.is_null()) {
            self.hold_repeats(rows(changes, "hold_repeats")?)?;
        }
        rows(&command["blocks"], "blocks")?;
        self.put("blocks", command["blocks"].clone());
        self.put("dirty", json!(true));
        self.put("conflict", json!(false));
        self.set_pending(None);
        let trace = match command.get("trace") {
            Some(trace) if !trace.is_null() => {
                object(trace, "trace")?;
                trace.clone()
            }
            _ => Value::Null,
        };
        self.put("trace", trace);
        Ok(json!({}))
    }

    /// Stamped repeat intents stay until the server acknowledges the save that carries them; a newer
    /// choice for the same repeat replaces the earlier one.
    fn hold_repeats(&mut self, changes: &[Value]) -> Result<(), String> {
        let mut incoming_ids = HashSet::new();
        for item in changes {
            let id = item
                .get("id")
                .and_then(Value::as_str)
                .ok_or("a repeat change id is text")?;
            incoming_ids.insert(id.to_string());
        }
        let mut held: Vec<Value> = optional_rows(self.field("repeat_send"), "repeat_send")?
            .iter()
            .filter(|item| {
                item.get("id")
                    .and_then(Value::as_str)
                    .is_none_or(|id| !incoming_ids.contains(id))
            })
            .cloned()
            .collect();
        held.extend(changes.iter().cloned());
        self.put("repeat_send", Value::Array(held));
        Ok(())
    }

    /// Another program or paired phone wrote this account's week.
    fn remote_change(&mut self, command: &Value, busy: bool) -> Result<Value, String> {
        let signed_in = flag(command, "signed_in")?;
        let who = text(command, "who")?;
        let flags = DraftFlags {
            pending_save: self.week.pending.is_some(),
            ..self.flags()
        };
        Ok(match week::remote_change(signed_in, busy, flags, who) {
            week::RemoteChange::Ignore => {
                json!({ "accepted": true, "conflict": false, "words": null })
            }
            week::RemoteChange::Wait => {
                json!({ "accepted": false, "conflict": false, "words": null })
            }
            week::RemoteChange::Conflict => {
                self.put("conflict", json!(true));
                json!({ "accepted": true, "conflict": true, "words": null })
            }
            week::RemoteChange::Reload(words) => {
                json!({ "accepted": true, "conflict": false, "words": words })
            }
        })
    }

    fn wrote_open(&self, command: &Value) -> Result<Value, String> {
        let written: HashSet<String> = command["written"]
            .as_array()
            .ok_or("written is a list")?
            .iter()
            .map(|item| {
                item.as_str()
                    .map(str::to_string)
                    .ok_or_else(|| "written is a list of dates".to_string())
            })
            .collect::<Result<_, _>>()?;
        Ok(json!({
            "wrote": week::wrote_open_weeks(&self.week_start(), self.flags(), &written)
        }))
    }

    /// Credit finished focus minutes to homework or a block and mark the draft ready to save.
    fn credit_focus(&mut self, command: &Value) -> Result<Value, String> {
        if let Some(row) = command.get("homework").filter(|value| !value.is_null()) {
            self.put_homework(row)?;
        }
        if let Some(blocks) = command.get("blocks").filter(|value| !value.is_null()) {
            rows(blocks, "blocks")?;
            self.put("blocks", blocks.clone());
        }
        if optional_flag(command, "mark_dirty")? {
            self.put("dirty", json!(true));
            self.set_pending(None);
        }
        Ok(json!({}))
    }

    /// Add more time to homework from a finished focus session.
    fn add_focus_time(&mut self, command: &Value) -> Result<Value, String> {
        self.put_homework(&command["homework"])?;
        self.put("history_label", json!(text(command, "history_label")?));
        self.put("dirty", json!(true));
        self.set_pending(None);
        Ok(json!({}))
    }

    /// Submit a prebuilt multi-week batch (move to another date, or grouped preview).
    fn submit_batch(&mut self, command: &Value) -> Result<Value, String> {
        let pending = PendingBatch::capture(command["pending_save"].clone())?
            .ok_or("pending_save must be an object")?;
        if let Some(blocks) = command.get("blocks").filter(|value| !value.is_null()) {
            rows(blocks, "blocks")?;
            self.put("blocks", blocks.clone());
            self.put("dirty", json!(true));
            self.put("conflict", json!(false));
        }
        if let Some(label) = optional_text(command, "history_label")? {
            self.put("history_label", json!(label));
        }
        if optional_flag(command, "capture_step")? {
            let label = self
                .field("history_label")
                .as_str()
                .unwrap_or(HISTORY_LABEL)
                .to_string();
            let revision = revision_json(&self.week.revision);
            let draft = self.save_draft(&[], false, &[], &revision)?;
            let step = changes::save_step(&draft, &label).map_err(engine)?;
            self.put("pending_step", step.unwrap_or(Value::Null));
        } else if let Some(step) = command.get("pending_step") {
            if !step.is_null() {
                object(step, "pending_step")?;
            }
            self.put("pending_step", step.clone());
        }
        if let Some(attempt) = optional_text(command, "move_attempt")? {
            self.put("move_attempt", json!(attempt));
        }
        if let Some(status) = optional_text(command, "save_status")? {
            self.put("save_status", json!(status));
        }
        self.set_pending(Some(pending));
        Ok(json!({}))
    }

    /// Apply the result of `solve()`, optionally recording prior-week updates as a travel step.
    fn apply_plan(&mut self, command: &Value) -> Result<Value, String> {
        if let Some(blocks) = command.get("blocks").filter(|value| !value.is_null()) {
            rows(blocks, "blocks")?;
            self.put("blocks", blocks.clone());
        }
        if let Some(trace) = command.get("trace") {
            if !trace.is_null() {
                object(trace, "trace")?;
            }
            self.put("trace", trace.clone());
        }
        if let Some(label) = optional_text(command, "history_label")? {
            self.put("history_label", json!(label));
        }
        if let Some(dirty) = command.get("dirty").and_then(Value::as_bool) {
            self.put("dirty", json!(dirty));
        }
        if let Some(prior) = command
            .get("prior_updates")
            .filter(|value| !value.is_null())
        {
            let prior_rows = rows(prior, "prior_updates")?;
            if !prior_rows.is_empty() {
                self.action = HistoryAction::EarlierWeeks(json!({ "weeks": prior_rows }));
                let dirty = self.dirty_ids();
                let label = self
                    .field("history_label")
                    .as_str()
                    .unwrap_or(HISTORY_LABEL)
                    .to_string();
                let step = {
                    let revision = revision_json(&self.week.revision);
                    let draft = self.save_draft(&dirty, false, &[], &revision)?;
                    changes::save_step(&draft, &label).map_err(engine)?
                };
                if let Some(mut step) = step {
                    if let Some(Value::Array(weeks)) = step.get_mut("weeks") {
                        weeks.extend(prior_rows.iter().cloned());
                    }
                    let step_id = text(command, "step_id")?;
                    step["id"] = json!(step_id);
                    self.put("pending_step", step);
                    self.put("plan_step_id", json!(step_id));
                } else {
                    self.put("pending_step", Value::Null);
                }
            }
        }
        if optional_flag(command, "clear_plan_step_id")? {
            self.put("plan_step_id", Value::Null);
        }
        Ok(json!({}))
    }

    /// Wire payload, destination week and written week list for the held `pending_save`.
    fn prepare_post(&self, command: &Value) -> Result<Value, String> {
        let Some(pending) = &self.week.pending else {
            return Ok(json!({ "post": false }));
        };
        let shifted_week = flag(command, "shifted_week")?;
        let request = object(&pending.project(), "pending_save")?.clone();
        let weeks = optional_rows(request.get("weeks").unwrap_or(&Value::Null), "weeks")?;
        let mut written = Vec::new();
        for week in weeks {
            let start = week
                .get("week_start")
                .and_then(Value::as_str)
                .ok_or("week_start must be text")?;
            if !written.iter().any(|seen| seen == start) {
                written.push(start.to_string());
            }
        }
        if let Some(order) = command["written_order"].as_array() {
            let ordered: Vec<String> = order
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect();
            if ordered.len() != written.len()
                || !written.iter().all(|start| ordered.contains(start))
            {
                return Err("written_order must list each written week once".into());
            }
            written = ordered;
        }
        let (payload, destination) =
            changes::prepare_post(request, &written, &self.week_start(), shifted_week)
                .map_err(engine)?;
        Ok(json!({
            "post": true,
            "payload": payload,
            "destination": destination,
            "written": written,
            "held_status": self.field("save_status"),
        }))
    }

    /// One homework row as the window edited it, kept as changed until it is saved.
    fn put_homework(&mut self, row: &Value) -> Result<(), String> {
        let id = row["id"]
            .as_str()
            .ok_or("a homework id is text")?
            .to_string();
        let mut assignments = self.assignments();
        assignments.insert(id.clone(), row.clone());
        self.put("assignments", Value::Object(assignments));
        let mut dirty = self.dirty_ids();
        dirty.push(id);
        self.set_dirty_ids(dirty);
        Ok(())
    }

    fn drop_stale(&mut self) {
        for redo in [false, true] {
            let mut stack = self.stack(redo).clone();
            while stack
                .last()
                .is_some_and(|(_, step)| truthy(step.get("stale")))
            {
                stack.pop();
            }
            self.set_stack(redo, stack);
        }
    }

    fn can_travel(&mut self, redo: bool, busy: bool) -> bool {
        self.drop_stale();
        !self.stack(redo).is_empty()
            && !busy
            && !truthy(Some(self.field("conflict")))
            && !truthy(Some(self.field("dirty")))
            && self.week.pending.is_none()
    }

    /// Undo or Redo up to its save: the step leaves its stack and its side is put in the open week.
    /// The window then settles the week (`_touch`) with the step's label and saves.
    fn travel(&mut self, redo: bool, busy: bool) -> Result<Value, String> {
        if !self.can_travel(redo, busy) {
            let stale = self
                .stack(redo)
                .last()
                .is_some_and(|(_, step)| truthy(step.get("stale")));
            let words = stale.then(|| history::stale_words(redo));
            return Ok(json!({ "go": false, "words": words }));
        }
        let mut stack = self.stack(redo).clone();
        let Some((token, step)) = stack.pop() else {
            return Ok(json!({ "go": false, "words": null }));
        };
        self.set_stack(redo, stack);
        let open = self.week_start();
        if let Some(refused) = history::travel_refusal(&step, &open, redo) {
            self.append_step(redo, token, step);
            return Ok(json!({ "go": false, "words": refused }));
        }
        let applied = history::travel_side(
            &step,
            redo,
            &open,
            rows(self.field("blocks"), "blocks")?,
            object(self.field("assignments"), "assignments")?,
            rows(self.field("assignments_basis"), "basis")?,
        )
        .map_err(engine)?;
        if let Some(blocks) = applied.blocks {
            self.put("blocks", Value::Array(blocks));
        }
        let mut assignments = self.assignments();
        for (id, row) in applied.assignments {
            match row {
                None => {
                    assignments.shift_remove(&id);
                }
                Some(row) => {
                    assignments.insert(id, row);
                }
            }
        }
        self.put("assignments", Value::Object(assignments));
        if let Some(basis) = applied.basis {
            self.put("assignments_basis", Value::Array(basis));
        }
        let mut dirty = self.dirty_ids();
        dirty.extend(applied.dirty);
        self.set_dirty_ids(dirty);
        let label = step.get("label").cloned().unwrap_or(Value::Null);
        let direction = if redo { Travel::Redo } else { Travel::Undo };
        self.action = HistoryAction::Travel {
            direction,
            token,
            step,
        };
        Ok(json!({ "go": true, "label": label }))
    }

    fn save_draft<'a>(
        &'a self,
        dirty: &'a [String],
        undo: bool,
        travel_weeks: &'a [Value],
        revision: &'a Value,
    ) -> Result<SaveDraft<'a>, String> {
        Ok(SaveDraft {
            week_start: self.field("week_start").as_str().unwrap_or_default(),
            blocks: rows(self.field("blocks"), "blocks")?,
            revision,
            committed_blocks: rows(self.field("committed_blocks"), "committed blocks")?,
            assignments: object(self.field("assignments"), "assignments")?,
            committed_assignments: object(
                self.field("committed_assignments"),
                "committed assignments",
            )?,
            dirty_assignments: dirty,
            travel_weeks,
            undo,
            stored_parts: rows(self.field("stored_parts"), "stored parts")?,
            saved_repeats: rows(self.field("saved_repeats"), "saved repeats")?,
            repeats: rows(self.field("repeats"), "repeats")?,
            queued_repeats: optional_rows(self.field("repeat_send"), "queued repeats")?,
        })
    }

    /// `save()` once the window has checked the account, a conflict and a request in flight: the
    /// batch is frozen with its Undo step unless one is already held for Retry. `ids` are fresh
    /// operation and step ids, taken only when needed.
    fn save(&mut self, command: &Value) -> Result<Value, String> {
        let mut ids = command["ids"]
            .as_array()
            .ok_or("ids is a list")?
            .iter()
            .map(|id| id.as_str().map(str::to_string).ok_or("an id is text"))
            .collect::<Result<VecDeque<String>, &str>>()?;
        let mut fresh = || ids.pop_front().ok_or("no fresh id left");
        self.put("join_step", json!(flag(command, "join")?));
        self.put("last_save_refused", json!(false));
        if let Some(status) = optional_text(command, "status")? {
            self.put("save_status", json!(status));
        }
        if self.week.pending.is_some() {
            return Ok(json!({ "post": true }));
        }
        let dirty = self.dirty_ids();
        let traveling = self.action.direction();
        let travel_weeks = self
            .action
            .step()
            .map_or(&Value::Null, |step| &step["weeks"]);
        let travel_weeks = optional_rows(travel_weeks, "travel weeks")?;
        let operation_id = optional_text(command, "operation_id")?.unwrap_or_default();
        let snapshot_label = optional_text(command, "snapshot_label")?;
        let label = self
            .field("history_label")
            .as_str()
            .unwrap_or(HISTORY_LABEL)
            .to_string();
        let wants_step = traveling.is_none() && flag(command, "record_history")?;
        let (mut request, step) = {
            let revision = revision_json(&self.week.revision);
            let draft = self.save_draft(
                &dirty,
                traveling == Some(Travel::Undo),
                travel_weeks,
                &revision,
            )?;
            let request =
                changes::freeze_save(&draft, operation_id, snapshot_label).map_err(engine)?;
            let step = if wants_step && !truthy(request.get("stay")) {
                let plain = self.save_draft(&dirty, false, travel_weeks, &revision)?;
                changes::save_step(&plain, &label).map_err(engine)?
            } else {
                None
            };
            (request, step)
        };
        if operation_id.is_empty() {
            request["operation_id"] = json!(fresh()?);
        }
        let stay = truthy(request.get("stay"));
        self.set_pending(PendingBatch::capture(request)?);
        if stay {
            return Ok(json!({ "post": true }));
        }
        let waiting = self.field("repeat_send").clone();
        self.put(
            "repeat_ack",
            if truthy(Some(&waiting)) {
                waiting
            } else {
                Value::Null
            },
        );
        if wants_step {
            let step = match step {
                Some(mut step) => {
                    step["id"] = json!(fresh()?);
                    Some(step)
                }
                None => None,
            };
            if flag(command, "plan")?
                && let Some(step) = &step
            {
                self.put("plan_step_id", step["id"].clone());
            }
            self.put("pending_step", step.unwrap_or(Value::Null));
        }
        Ok(json!({ "post": true }))
    }

    /// The save's answer, applied in the window's order: session weeks, moved counts, the open week,
    /// each homework row, the step, then the save's own state. The window then says the words, runs
    /// what waited for the save and reads what it must.
    fn saved(&mut self, command: &Value) -> Result<Value, String> {
        let data = &command["data"];
        object(data, "answer")?;
        let written: Vec<String> = command["written"]
            .as_array()
            .ok_or("written is a list")?
            .iter()
            .filter_map(Value::as_str)
            .map(str::to_string)
            .collect();
        let open = self.week_start();
        let pending_step = self.field("pending_step").clone();
        let plan_step_id = self.field("plan_step_id").clone();
        let sent = self.field("repeat_ack").clone();
        let waiting = self.field("repeat_send").clone();
        let acknowledged = changes::acknowledge_save(&SaveAnswer {
            data,
            week_start: &open,
            shifted_week: flag(command, "shifted_week")?,
            now: text(command, "now")?,
            sent_repeats: flag(command, "sent_repeats")?,
            assignments: object(self.field("assignments"), "assignments")?,
            committed_assignments: object(
                self.field("committed_assignments"),
                "committed assignments",
            )?,
            stored_parts: rows(self.field("stored_parts"), "stored parts")?,
            traveling: self.action.direction(),
            travel_step: self.action.step(),
            pending_step: (!pending_step.is_null()).then_some(&pending_step),
            plan_step_id: plan_step_id.as_str(),
            join: truthy(Some(self.field("join_step"))),
            held_words: optional_text(command, "held")?,
            sent_intents: (!sent.is_null())
                .then(|| rows(&sent, "sent intents"))
                .transpose()?,
            waiting_intents: (!waiting.is_null())
                .then(|| rows(&waiting, "waiting intents"))
                .transpose()?,
        })
        .map_err(engine)?;
        let mut assignments = self.assignments();
        for (id, weeks) in acknowledged.session_weeks {
            let row = assignments
                .get_mut(&id)
                .and_then(Value::as_object_mut)
                .ok_or_else(|| format!("no homework {id:?} to give its weeks"))?;
            row.insert("session_weeks".into(), weeks);
        }
        update_counts(&mut assignments, acknowledged.live_counts)?;
        self.put("assignments", Value::Object(assignments));
        let mut committed = self
            .field("committed_assignments")
            .as_object()
            .cloned()
            .unwrap_or_default();
        update_counts(&mut committed, acknowledged.saved_counts)?;
        self.put("committed_assignments", Value::Object(committed));
        let has_open_week = acknowledged.open_week.is_some();
        if let Some(week) = acknowledged.open_week {
            self.put("blocks", Value::Array(week.blocks));
            self.set_revision(checked_revision(&week.revision)?);
            self.put("stored_parts", Value::Array(week.stored));
            self.put("dirty", json!(false));
            self.put("conflict", json!(false));
            if let Some(repeats) = week.repeats {
                self.put("repeats", Value::Array(repeats.clone()));
                self.put("saved_repeats", Value::Array(repeats));
            }
        }
        let mut assignments = self.assignments();
        let mut dirty = self.dirty_ids();
        for (id, row) in acknowledged.homework {
            dirty.retain(|held| *held != id);
            match row {
                None => {
                    assignments.shift_remove(&id);
                }
                Some(row) => {
                    assignments.insert(id, row);
                }
            }
        }
        self.set_dirty_ids(dirty);
        self.put("assignments", Value::Object(assignments));
        match acknowledged.step {
            Some((StepPlace::Redo, step)) => {
                let token = self.token();
                self.push_step(true, token, step);
            }
            Some((StepPlace::Undo, step)) => {
                let token = self.token();
                self.push_step(false, token, step);
            }
            Some((StepPlace::JoinUndo, step)) => self.join_step(step)?,
            None => {}
        }
        if acknowledged.clear_redo {
            self.set_stack(true, Vec::new());
        }
        for name in ["pending_step", "plan_step_id", "repeat_ack", "save_status"] {
            self.put(name, Value::Null);
        }
        self.set_pending(None);
        self.action = HistoryAction::Save;
        self.put("join_step", json!(false));
        self.put(
            "repeat_send",
            acknowledged
                .waiting_intents
                .map_or(Value::Null, Value::Array),
        );
        if has_open_week {
            self.put("committed_blocks", self.field("blocks").clone());
            self.put("committed_assignments", self.field("assignments").clone());
        }
        self.forget_held_attempt("preview_attempt");
        self.forget_held_attempt("move_attempt");
        for start in written {
            if start != open {
                self.take_parked(&start);
            }
        }
        Ok(json!({
            "words": acknowledged.words,
            "planned": acknowledged.planned,
            "open_week": has_open_week,
        }))
    }

    /// `history.join_step` on the Undo stack.
    fn join_step(&mut self, step: Value) -> Result<(), String> {
        let mut stack = self.week.undo.clone();
        let Some((_, newest)) = stack.last() else {
            let token = self.token();
            self.push_step(false, token, step);
            return Ok(());
        };
        match history::join_into(newest, &step).map_err(engine)? {
            Some(joined) => {
                let token = self.token();
                if let Some(last) = stack.last_mut() {
                    *last = (token, joined);
                }
                self.set_stack(false, stack);
            }
            None => {
                let token = self.token();
                self.push_step(false, token, step);
            }
        }
        Ok(())
    }

    fn forget_held_attempt(&mut self, name: &str) {
        let held = self.field(name).clone();
        if !truthy(Some(&held)) {
            return;
        }
        if let Some(key) = held.as_str() {
            let mut attempts = self
                .field("attempts")
                .as_object()
                .cloned()
                .unwrap_or_default();
            attempts.shift_remove(key);
            self.put("attempts", Value::Object(attempts));
        }
        self.put(name, Value::Null);
    }

    /// A failed save: the batch stays for Retry, a conflict waits for Reload, and a failed Undo or
    /// Redo puts the saved week and its step back.
    fn save_failed(&mut self, command: &Value) -> Result<Value, String> {
        let status = command["status"]
            .as_i64()
            .ok_or("status is a whole number")?;
        let message = text(command, "message")?;
        self.put("join_step", json!(false));
        let refusal = changes::refuse_save(
            status,
            message,
            self.action.direction(),
            self.action.step().is_some(),
        );
        if refusal.roll_back {
            self.put("blocks", self.field("committed_blocks").clone());
            self.put("assignments", self.field("committed_assignments").clone());
            self.set_dirty_ids([]);
            self.put("dirty", json!(false));
            self.set_pending(None);
            self.put("conflict", json!(false));
        }
        if let Some(back) = refusal.step_back
            && let HistoryAction::Travel { token, step, .. } = std::mem::take(&mut self.action)
        {
            self.append_step(back == Travel::Redo, token, step);
        }
        self.put("conflict", json!(refusal.conflict));
        if refusal.conflict {
            self.forget_held_attempt("preview_attempt");
            self.forget_held_attempt("move_attempt");
        }
        self.put("save_status", Value::Null);
        let refused = refusal.failure.kind == SaveFailureKind::Refused;
        self.put("last_save_refused", json!(refused));
        Ok(json!({
            "words": refusal.failure.words,
            "refused": refused,
            "reload_words": refusal.reload_words,
        }))
    }

    /// `drop_refused_save`: a save the server read and refused is taken back.
    fn drop_refused(&mut self) -> bool {
        if !truthy(Some(self.field("last_save_refused"))) || self.week.pending.is_none() {
            return false;
        }
        self.set_pending(None);
        self.put("dirty", json!(false));
        self.set_dirty_ids([]);
        self.put("repeat_send", Value::Null);
        self.put("repeat_ack", Value::Null);
        true
    }

    /// The operation id a named attempt keeps until it lands; `new` is the id a first try takes.
    fn attempt(&mut self, command: &Value) -> Result<Value, String> {
        let key = text(command, "key")?;
        let mut attempts = self
            .field("attempts")
            .as_object()
            .cloned()
            .unwrap_or_default();
        if let Some(id) = attempts.get(key) {
            return Ok(json!({ "id": id }));
        }
        match optional_text(command, "new")? {
            Some(new) => {
                attempts.insert(key.to_string(), json!(new));
                self.put("attempts", Value::Object(attempts));
                Ok(json!({ "id": new }))
            }
            None => Ok(json!({ "id": null })),
        }
    }

    /// The server's new homework numbers: saved copies take their counts, a changed one keeps the
    /// student's fields and takes only the counts, and the rest are replaced. `basis` is the saved
    /// week the numbers were read against.
    fn refresh_assignments(&mut self, command: &Value) -> Result<Value, String> {
        let incoming = match &command["incoming"] {
            Value::Null => Vec::new(),
            incoming => owned_rows(incoming, "assignments")?,
        };
        let mut assignments = self.assignments();
        let mut committed = self
            .field("committed_assignments")
            .as_object()
            .cloned()
            .unwrap_or_default();
        let local: HashSet<String> = assignments.keys().cloned().collect();
        let saved: HashSet<String> = committed.keys().cloned().collect();
        let dirty: HashSet<String> = self.dirty_ids().into_iter().collect();
        let edits = week::refresh_assignments(incoming, &local, &saved, &dirty).map_err(engine)?;
        rows(&command["basis"], "basis")?;
        self.put("assignments_basis", command["basis"].clone());
        update_counts(&mut committed, edits.saved_counts)?;
        self.put("committed_assignments", Value::Object(committed));
        update_counts(&mut assignments, edits.dirty_counts)?;
        for (id, row) in edits.clean_rows {
            assignments.insert(id, row);
        }
        self.put("assignments", Value::Object(assignments));
        Ok(json!({}))
    }

    /// A week's blocks and revision as this window holds them: the open week, or one set aside with
    /// changes not yet saved, else null.
    fn local(&self, requested: &str) -> Value {
        let open = self.week_start();
        let parked = self.find_parked(requested);
        let parked_dirty = parked.is_some_and(|parked| truthy(parked.fields.get("dirty")));
        match week::local_week(requested, &open, parked_dirty) {
            week::LocalWeek::Open => {
                json!({ "blocks": self.field("blocks"), "revision": revision_json(&self.week.revision) })
            }
            week::LocalWeek::Parked => {
                let field = |name: &str| {
                    parked
                        .and_then(|parked| parked.fields.get(name))
                        .cloned()
                        .unwrap_or(Value::Null)
                };
                json!({ "blocks": field("blocks"), "revision": field("revision") })
            }
            week::LocalWeek::Missing => Value::Null,
        }
    }

    /// Delete homework in every week: the request, with this week as it reads without it. The window
    /// has checked that nothing is in flight or unsaved and chose the operation id.
    fn delete_begin(&mut self, command: &Value) -> Result<Value, String> {
        let homework = text(command, "assignment_id")?.to_string();
        let item = self
            .assignments()
            .get(&homework)
            .cloned()
            .ok_or_else(|| format!("no homework {homework:?}"))?;
        let title = match item.get("title") {
            Some(Value::String(title)) if !title.is_empty() => title.clone(),
            _ => "the homework".to_string(),
        };
        let before = rows(self.field("blocks"), "blocks")?.to_vec();
        let after: Vec<Value> = before
            .iter()
            .filter(|block| !of_homework(block, &homework))
            .cloned()
            .collect();
        let week_start = self.week_start();
        let body = json!({
            "weeks": [changes::week_write(&week_start, &after, &revision_json(&self.week.revision)).map_err(engine)?],
            "assignments": [changes::assignment_write(
                &homework,
                None,
                whole_revision(item.get("revision"))?,
            )
            .map_err(engine)?],
            "operation_id": text(command, "operation_id")?,
        });
        self.deleting = Some(Deleting {
            homework,
            title: title.clone(),
            key: text(command, "key")?.to_string(),
            before,
            item,
            step: None,
            removed: Map::new(),
            others: VecDeque::new(),
            reading: None,
        });
        Ok(json!({
            "title": title,
            "request": { "method": "POST", "path": "/api/changes", "body": body },
        }))
    }

    /// The delete is stored: the open week takes the server's copy, every week set aside forgets the
    /// homework, and the Undo step starts. The answer names the next week to read back, if any.
    /// `ids` are fresh operation ids for held batches the delete changed, one per week set aside.
    fn delete_ok(&mut self, command: &Value) -> Result<Value, String> {
        let deleting = self.deleting.take().ok_or("no delete is waiting")?;
        // Everything that can fail is read before anything changes, so a bad answer leaves the
        // delete waiting and every week as it was.
        let prepared = match self.prepare_delete(&deleting, command) {
            Ok(prepared) => prepared,
            Err(error) => {
                self.deleting = Some(deleting);
                return Err(error);
            }
        };
        let DeletePrepared {
            removed,
            current,
            parked,
        } = prepared;
        let homework = deleting.homework.clone();
        let open = self.week_start();
        if let Some((blocks, revision, stored)) = current {
            self.put("blocks", blocks);
            self.set_revision(revision);
            self.put("stored_parts", stored);
        }
        let mut assignments = self.assignments();
        assignments.shift_remove(&homework);
        self.put("assignments", Value::Object(assignments));
        let mut dirty = self.dirty_ids();
        dirty.retain(|id| *id != homework);
        self.set_dirty_ids(dirty);
        self.put("committed_blocks", self.field("blocks").clone());
        self.put("committed_assignments", self.field("assignments").clone());
        for ((_, draft), fields) in self.parked.iter_mut().zip(parked) {
            draft.fields = fields;
        }
        self.finish_delete_step(deleting, removed, open)
    }

    /// The fallible half of `delete_ok`: the server's removed sessions, the open week as stored, and
    /// each parked week with the homework taken out, all computed on copies.
    fn prepare_delete(
        &self,
        deleting: &Deleting,
        command: &Value,
    ) -> Result<DeletePrepared, String> {
        let homework = deleting.homework.clone();
        let data = &command["data"];
        let mut ids = command["ids"]
            .as_array()
            .map(|ids| {
                ids.iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect::<VecDeque<String>>()
            })
            .unwrap_or_default();
        let results = data.get("assignments").filter(|value| truthy(Some(value)));
        let empty = json!({});
        let result = results
            .and_then(Value::as_array)
            .and_then(|results| {
                results
                    .iter()
                    .find(|entry| entry["id"].as_str() == Some(homework.as_str()))
            })
            .unwrap_or(&empty);
        let removed = match result.get("removed_sessions") {
            Some(Value::Object(removed)) => removed.clone(),
            _ => Map::new(),
        };
        let mut revisions = Map::new();
        if let Some(changed) = result.get("changed_weeks").and_then(Value::as_array) {
            for week in changed {
                let start = week["week_start"]
                    .as_str()
                    .ok_or("week_start must be text")?;
                revisions.insert(start.to_string(), week["revision"].clone());
            }
        }
        let open = self.week_start();
        let weeks = data
            .get("weeks")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let current = match weeks
            .iter()
            .find(|week| week["week_start"].as_str() == Some(open.as_str()))
        {
            Some(current) => Some((
                current["blocks"].clone(),
                checked_revision(&current["revision"])?,
                match current.get("stored") {
                    Some(stored) if truthy(Some(stored)) => stored.clone(),
                    _ => json!([]),
                },
            )),
            None => None,
        };
        let mut parked = Vec::with_capacity(self.parked.len());
        for (start, draft) in &self.parked {
            let mut fields = draft.fields.clone();
            prune_parked(start, &mut fields, &homework, &revisions, &mut ids)?;
            parked.push(fields);
        }
        Ok(DeletePrepared {
            removed,
            current,
            parked,
        })
    }

    /// The infallible half of `delete_ok`: the Undo step and the reads of the other weeks.
    fn finish_delete_step(
        &mut self,
        mut deleting: Deleting,
        removed: Map<String, Value>,
        open: String,
    ) -> Result<Value, String> {
        let homework = deleting.homework.clone();
        let basis: Vec<Value> = self
            .field("assignments_basis")
            .as_array()
            .map(|basis| {
                basis
                    .iter()
                    .filter(|block| of_homework(block, &homework))
                    .cloned()
                    .collect()
            })
            .unwrap_or_default();
        deleting.step = Some(json!({
            "label": format!("deleting {}", deleting.title),
            "weeks": [{
                "week_start": open,
                "before": deleting.before,
                "after": self.field("blocks"),
                "revision": revision_json(&self.week.revision),
            }],
            "assignments": [{
                "id": homework,
                "before": deleting.item,
                "after": null,
                "basis": basis,
            }],
            "stale": false,
        }));
        deleting.others = removed
            .keys()
            .filter(|start| **start != open)
            .cloned()
            .collect();
        deleting.removed = removed;
        let next = Self::next_read(&mut deleting);
        self.deleting = Some(deleting);
        Ok(json!({ "request": next }))
    }

    fn next_read(deleting: &mut Deleting) -> Value {
        deleting.reading = deleting.others.pop_front();
        match &deleting.reading {
            Some(start) => json!({
                "method": "GET",
                "path": format!("/api/week?week_start={start}"),
                "body": null,
            }),
            None => Value::Null,
        }
    }

    /// A week read back for the delete's Undo step, or null when it could not be read (Undo still
    /// brings the homework back, with its sessions in every week that could be read).
    fn delete_read(&mut self, command: &Value) -> Result<Value, String> {
        let deleting = self.deleting.as_mut().ok_or("no delete is reading weeks")?;
        let week = &command["week"];
        if let (Some(start), false) = (deleting.reading.clone(), week.is_null()) {
            let kept = match week.get("blocks") {
                Some(Value::Array(blocks)) => blocks.clone(),
                _ => Vec::new(),
            };
            let mut before = kept.clone();
            if let Some(Value::Array(gone)) = deleting.removed.get(&start) {
                before.extend(gone.iter().cloned());
            } else {
                return Err(format!("no sessions removed from {start}"));
            }
            let revision = week
                .get("revision")
                .cloned()
                .ok_or("a week read back has a revision")?;
            if let Some(Value::Array(weeks)) = deleting
                .step
                .as_mut()
                .and_then(|step| step.get_mut("weeks"))
            {
                weeks.push(json!({
                    "week_start": start,
                    "before": before,
                    "after": kept,
                    "revision": revision,
                }));
            }
        }
        let next = Self::next_read(deleting);
        Ok(json!({ "request": next }))
    }

    /// Every week is read back: the delete is one Undo step, and its attempt has landed.
    fn delete_finish(&mut self) -> Result<Value, String> {
        let deleting = self.deleting.take().ok_or("no delete to finish")?;
        let step = deleting.step.ok_or("the delete was not answered")?;
        let words = format!("Deleted {}.", deleting.title);
        let token = self.token();
        self.push_step(false, token, step);
        self.set_stack(true, Vec::new());
        let mut attempts = self
            .field("attempts")
            .as_object()
            .cloned()
            .unwrap_or_default();
        attempts.shift_remove(&deleting.key);
        self.put("attempts", Value::Object(attempts));
        Ok(json!({ "words": words }))
    }
}

/// `row.update(counts)` for each homework named.
fn update_counts(rows: &mut Map<String, Value>, counts: Map<String, Value>) -> Result<(), String> {
    for (id, counts) in counts {
        let row = rows
            .get_mut(&id)
            .and_then(Value::as_object_mut)
            .ok_or_else(|| format!("no homework {id:?} to count"))?;
        if let Value::Object(counts) = counts {
            for (key, value) in counts {
                row.insert(key, value);
            }
        }
    }
    Ok(())
}

/// A week set aside forgets deleted homework everywhere it holds it, not only in the weeks the delete
/// touched, or coming back to it brings the homework back and the week reads as changed elsewhere.
fn prune_parked(
    start: &str,
    parked: &mut Map<String, Value>,
    homework: &str,
    revisions: &Map<String, Value>,
    ids: &mut VecDeque<String>,
) -> Result<(), String> {
    for name in ["assignments", "committed_assignments"] {
        if let Some(Value::Object(rows)) = parked.get_mut(name) {
            rows.shift_remove(homework);
        }
    }
    if let Some(Value::Array(dirty)) = parked.get_mut("dirty_assignments") {
        dirty.retain(|id| id.as_str() != Some(homework));
    }
    for name in ["assignments_basis", "blocks", "committed_blocks"] {
        let kept = without_homework(parked.get(name).unwrap_or(&Value::Null), homework);
        parked.insert(name.to_string(), kept);
    }
    if let Some(trace) = parked.get("trace").filter(|trace| truthy(Some(trace))) {
        let mut trace = trace.as_object().cloned().ok_or("a trace is an object")?;
        for listing in ["placed", "unplaced"] {
            if let Some(rows) = trace.get(listing) {
                let kept = without_homework(rows, homework);
                trace.insert(listing.to_string(), kept);
            }
        }
        parked.insert("trace".into(), Value::Object(trace));
    }
    for side in ["undo", "redo"] {
        let steps: Vec<Value> = parked
            .get(side)
            .and_then(Value::as_array)
            .map(|steps| {
                steps
                    .iter()
                    .filter_map(|step| history::step_without_homework(step, homework, revisions))
                    .collect()
            })
            .unwrap_or_default();
        parked.insert(side.to_string(), Value::Array(steps));
    }
    let request = parked.get("pending_save").cloned().unwrap_or(Value::Null);
    if !request.is_null() {
        let held = json!({
            "week_start": parked.get("week_start").cloned().unwrap_or(Value::Null),
            "revision": parked.get("revision").cloned().unwrap_or(Value::Null),
        });
        let mut rebuilt = history::request_without_homework(&request, &held, homework, revisions)
            .map_err(engine)?;
        // A request the delete changed takes a new id: the old one may already have reached the store,
        // which would answer for the old request. One the delete left alone keeps its own.
        if changes::retry_needs_new_id(&request, &rebuilt) {
            rebuilt["operation_id"] = json!(ids.pop_front().ok_or("no fresh id left")?);
            parked.insert("pending_save".into(), rebuilt);
        }
    }
    let pending_step = parked.get("pending_step").cloned().unwrap_or(Value::Null);
    if !pending_step.is_null() {
        let kept = history::step_without_homework(&pending_step, homework, revisions);
        parked.insert("pending_step".into(), kept.unwrap_or(Value::Null));
    }
    if let Some(revision) = revisions.get(start) {
        let kept = without_homework(parked.get("blocks").unwrap_or(&Value::Null), homework);
        parked.insert("blocks".into(), kept);
        parked.insert("revision".into(), revision.clone());
    } else if let Some(Value::Array(held)) = parked.get("revision").cloned() {
        // A week on screen from another day: each of its stored weeks the delete changed.
        let stored = stored_weeks(start).map_err(engine)?;
        if stored.iter().any(|week| revisions.contains_key(week)) {
            if stored.len() != held.len() {
                return Err("zip() argument 2 is shorter or longer than argument 1".into());
            }
            let kept = without_homework(parked.get("blocks").unwrap_or(&Value::Null), homework);
            parked.insert("blocks".into(), kept);
            let moved: Vec<Value> = stored
                .iter()
                .zip(held)
                .map(|(week, revision)| revisions.get(week).cloned().unwrap_or(revision))
                .collect();
            parked.insert("revision".into(), Value::Array(moved));
            // The stored weeks it reads move on with it, or the window's own delete would look like
            // another program's change once the week is open again.
            let parts: Vec<Value> = parked
                .get("stored_parts")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .map(|part| {
                    let mut part = part.as_object().cloned().unwrap_or_default();
                    let week = part
                        .get("week_start")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .to_string();
                    if let Some(revision) = revisions.get(&week) {
                        part.insert("revision".into(), revision.clone());
                    }
                    let blocks = without_homework(
                        part.get("blocks")
                            .filter(|blocks| truthy(Some(blocks)))
                            .unwrap_or(&json!([])),
                        homework,
                    );
                    part.insert("blocks".into(), blocks);
                    Value::Object(part)
                })
                .collect();
            parked.insert("stored_parts".into(), Value::Array(parts));
        }
    }
    Ok(())
}

#[cfg(test)]
mod restore_tests {
    use super::*;

    /// A delete answer that cannot be applied to every parked week (here one with a trace that is
    /// not an object) is refused before anything changes: the delete is still waiting, the open
    /// week keeps its blocks and the homework, and the good parked week is untouched.
    #[test]
    fn a_delete_answer_that_cannot_reach_every_parked_week_changes_nothing() {
        let mut drafts = Drafts::default();
        drafts.put("week_start", json!("2026-11-23"));
        drafts.put("blocks", json!([{"id": "s1", "assignment_id": "essay"}]));
        drafts.put(
            "assignments",
            json!({"essay": {"id": "essay", "title": "Essay"}}),
        );
        let good = Map::from_iter([(
            "blocks".to_string(),
            json!([{"id": "s2", "assignment_id": "essay"}]),
        )]);
        let bad = Map::from_iter([("trace".to_string(), json!("not an object"))]);
        drafts.parked = vec![
            (
                "2026-11-30".into(),
                Parked {
                    fields: good.clone(),
                    selection: json!(null),
                },
            ),
            (
                "2026-12-07".into(),
                Parked {
                    fields: bad,
                    selection: json!(null),
                },
            ),
        ];
        drafts.deleting = Some(Deleting {
            homework: "essay".into(),
            title: "Essay".into(),
            key: "k".into(),
            before: vec![],
            item: json!({"id": "essay"}),
            step: None,
            removed: Map::new(),
            others: VecDeque::new(),
            reading: None,
        });
        let answer = json!({
            "data": {"weeks": [{"week_start": "2026-11-23", "blocks": [], "revision": 3}]},
            "ids": ["fresh-1", "fresh-2"],
        });
        assert!(drafts.delete_ok(&answer).is_err());
        assert!(drafts.deleting.is_some());
        assert_eq!(
            drafts.field("blocks"),
            &json!([{"id": "s1", "assignment_id": "essay"}])
        );
        assert!(drafts.assignments().contains_key("essay"));
        assert_eq!(drafts.parked[0].1.fields, good);
    }

    /// A parked copy whose revision or pending save cannot be read is refused before anything of it
    /// is put on the open week: no field, Undo step or batch from it shows up.
    #[test]
    fn a_parked_week_that_cannot_be_read_changes_nothing() {
        for (name, bad) in [
            ("revision", json!("seven")),
            ("pending_save", json!([1, 2])),
        ] {
            let mut drafts = Drafts::default();
            drafts.put("week_start", json!("2026-11-23"));
            drafts.put("blocks", json!([{"id": "open-block"}]));
            let mut fields = Map::new();
            fields.insert("week_start".into(), json!("2026-11-30"));
            fields.insert("blocks".into(), json!([{"id": "parked-block"}]));
            fields.insert(name.into(), bad);
            let parked = Parked {
                fields,
                selection: json!(null),
            };
            assert!(drafts.restore(&parked).is_err(), "{name}");
            assert_eq!(drafts.field("week_start"), &json!("2026-11-23"), "{name}");
            assert_eq!(
                drafts.field("blocks"),
                &json!([{"id": "open-block"}]),
                "{name}"
            );
        }
    }
}
