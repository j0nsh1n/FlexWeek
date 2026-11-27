//! Setup's write queue and the preference request bodies (P4 group 8): the rules of controller.py's
//! `keep_setup` and `flush_setup`, of the bodies `save_preferences` and `save_availability` send, and of
//! what `follow_first_weekday` decides before it acts. The window keeps the requests, their callbacks and
//! its signals, and applies what is answered here.

use flexweek_engine::desk::custom_look::known_pack;
use flexweek_engine::stored::{self, py_int, truthy, type_name};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

/// Study hours limit shared by first-run setup, Settings and the service validator.
pub const MAX_WORK_WINDOWS: usize = 21;

/// Built-in Study hours presets: `(label, days, start, end)`.
pub const WORK_WINDOW_PRESETS: &[(&str, &[i64], &str, &str)] = &[
    ("After school", &[0, 1, 2, 3, 4], "15:30", "18:00"),
    ("Evenings", &[0, 1, 2, 3, 4], "19:00", "21:00"),
    ("Weekend mornings", &[5, 6], "10:00", "12:00"),
];

pub const WORK_WINDOW_PRESETS_NOTE: &str = "Each adds a row of hours you can change.";
pub const HOURS_REFUSED: &str = "Check the days and times in Study hours and Protected time.";
pub const SAVING_AVAILABILITY: &str = "Saving availability\u{2026}";
pub const SAVED_AVAILABILITY: &str = "Saved availability.";
pub const SAVING_PREFERENCES: &str = "Saving preferences\u{2026}";
pub const SAVED_PREFERENCES: &str = "Saved preferences.";

/// The theme axis a pack stands for (look.py's `pack_axis`): a pack the engine does not know is "system".
pub fn pack_axis(pack: &Value) -> &'static str {
    match known_pack(pack).as_str() {
        Some("light-frost" | "slate") => "slate",
        Some("dark-frost" | "nocturne") => "nocturne",
        _ => "system",
    }
}

fn object_of(value: &Value) -> Map<String, Value> {
    match value {
        Value::Object(fields) => fields.clone(),
        _ => Map::new(),
    }
}

/// Python's idea of an empty answer, which the old `day_cutoff or None` turned into null.
fn is_empty_answer(value: &Value) -> bool {
    match value {
        Value::Null => true,
        Value::Bool(flag) => !flag,
        Value::Number(number) => number.as_f64() == Some(0.0),
        Value::String(text) => text.is_empty(),
        Value::Array(items) => items.is_empty(),
        Value::Object(fields) => fields.is_empty(),
    }
}

/// The preferences as they stand with the updates on top. Whenever the result holds a pack, its theme is
/// the pack's axis, so a caller cannot send a theme that disagrees with the pack.
pub fn preferences_body(current: &Value, updates: &Value) -> Value {
    let mut body = object_of(current);
    body.extend(object_of(updates));
    let axis = body.get("theme_pack").map(pack_axis);
    if let Some(axis) = axis {
        body.insert("theme".into(), json!(axis));
    }
    Value::Object(body)
}

/// The preferences with Study hours and the day cutoff on top. An empty cutoff is sent as null; work
/// windows travel only when the caller has some, so a save of the protected time alone leaves them.
pub fn availability_body(
    prefs: &Value,
    protected: &Value,
    day_cutoff: &Value,
    work_windows: Option<&Value>,
) -> Value {
    let mut body = object_of(prefs);
    body.insert("protected".into(), protected.clone());
    let cutoff = if is_empty_answer(day_cutoff) {
        Value::Null
    } else {
        day_cutoff.clone()
    };
    body.insert("day_cutoff".into(), cutoff);
    if let Some(windows) = work_windows {
        body.insert("work_windows".into(), windows.clone());
    }
    Value::Object(body)
}

/// What the queue says to send next.
#[derive(Debug, Clone, PartialEq)]
pub enum SetupStep {
    Nothing,
    Preferences(Map<String, Value>),
    Windows(Value),
    Week,
}

impl SetupStep {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Nothing => json!({ "step": "nothing" }),
            Self::Preferences(updates) => json!({ "step": "preferences", "updates": updates }),
            Self::Windows(windows) => json!({ "step": "windows", "windows": windows }),
            Self::Week => json!({ "step": "week" }),
        }
    }
}

/// What setup has kept and not yet written, sent one request at a time: preferences, then Study hours,
/// then the week. A second request would replace the first on the session.
#[derive(Debug, Default)]
pub struct SetupQueue {
    prefs: Map<String, Value>,
    windows: Option<Value>,
    week: bool,
}

impl SetupQueue {
    /// Remember what a setup page answered. Preference updates merge by key with the later one winning;
    /// the latest Study hours replace the earlier; a kept week stays kept until it is sent.
    pub fn keep(&mut self, updates: &Map<String, Value>, windows: Option<Value>, save_week: bool) {
        self.prefs.extend(updates.clone());
        if windows.is_some() {
            self.windows = windows;
        }
        if save_week {
            self.week = true;
        }
    }

    /// The next write, taken off the queue; nothing while a request is out or nobody is signed in. The
    /// preferences and Study hours wait until the stored preferences have arrived, since both are sent on
    /// top of them; the week does not.
    pub fn next(&mut self, signed_in: bool, busy: bool, has_preferences: bool) -> SetupStep {
        if !signed_in || busy {
            return SetupStep::Nothing;
        }
        if has_preferences && !self.prefs.is_empty() {
            return SetupStep::Preferences(std::mem::take(&mut self.prefs));
        }
        if has_preferences && let Some(windows) = self.windows.take() {
            return SetupStep::Windows(windows);
        }
        if self.week {
            self.week = false;
            return SetupStep::Week;
        }
        SetupStep::Nothing
    }

    pub fn prefs(&self) -> &Map<String, Value> {
        &self.prefs
    }

    pub fn windows(&self) -> Option<&Value> {
        self.windows.as_ref()
    }

    pub fn week(&self) -> bool {
        self.week
    }

    pub fn set_prefs(&mut self, prefs: Map<String, Value>) {
        self.prefs = prefs;
    }

    pub fn set_windows(&mut self, windows: Option<Value>) {
        self.windows = windows;
    }

    pub fn set_week(&mut self, week: bool) {
        self.week = week;
    }

    /// Unsent answers belong to the account that gave them.
    pub fn clear(&mut self) {
        *self = Self::default();
    }

    /// A different account (or none) does not keep the previous one's unsent setup answers.
    /// Returns whether the account differed and the queue was cleared.
    pub fn drop_if_other_account(
        &mut self,
        current_id: Option<&Value>,
        incoming_id: &Value,
    ) -> bool {
        let different = current_id != Some(incoming_id);
        if different {
            self.clear();
        }
        different
    }

    /// Remember what a setup page answered and return the optimistic preferences merge (if stored
    /// preferences have already arrived) so the window shows the change immediately.
    pub fn keep_and_merge(
        &mut self,
        updates: &Map<String, Value>,
        windows: Option<Value>,
        save_week: bool,
        current_prefs: Option<&Value>,
    ) -> Option<Value> {
        self.keep(updates, windows, save_week);
        keep_setup_merged_prefs(current_prefs, &self.prefs)
    }

    /// The next write with availability defaults already resolved against `current_prefs`.
    pub fn next_action(
        &mut self,
        signed_in: bool,
        busy: bool,
        current_prefs: Option<&Value>,
    ) -> FlushSetupAction {
        let step = self.next(signed_in, busy, current_prefs.is_some());
        flush_setup_action(&step, current_prefs)
    }

    /// Whether setup still has anything queued to write.
    pub fn has_pending(&self) -> bool {
        !self.prefs.is_empty() || self.windows.is_some() || self.week
    }
}

/// Optimistically overlay `setup_prefs` on top of `current_prefs` when stored preferences exist.
pub fn keep_setup_merged_prefs(
    current_prefs: Option<&Value>,
    setup_prefs: &Map<String, Value>,
) -> Option<Value> {
    let current = current_prefs?;
    let mut merged = object_of(current);
    merged.extend(setup_prefs.clone());
    Some(Value::Object(merged))
}

/// What `flush_setup` sends next, with `protected` and `day_cutoff` defaults resolved for windows.
#[derive(Debug, Clone, PartialEq)]
pub enum FlushSetupAction {
    Nothing,
    Preferences(Map<String, Value>),
    Windows {
        protected: Value,
        day_cutoff: Value,
        work_windows: Value,
    },
    Week,
}

impl FlushSetupAction {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Nothing => json!({ "step": "nothing" }),
            Self::Preferences(updates) => json!({ "step": "preferences", "updates": updates }),
            Self::Windows {
                protected,
                day_cutoff,
                work_windows,
            } => json!({
                "step": "windows",
                "protected": protected,
                "day_cutoff": day_cutoff,
                "work_windows": work_windows,
            }),
            Self::Week => json!({ "step": "week" }),
        }
    }
}

/// Resolve a `SetupStep` against `current_prefs` so `flush_setup` needs no default-extraction logic.
pub fn flush_setup_action(step: &SetupStep, current_prefs: Option<&Value>) -> FlushSetupAction {
    match step {
        SetupStep::Nothing => FlushSetupAction::Nothing,
        SetupStep::Preferences(updates) => FlushSetupAction::Preferences(updates.clone()),
        SetupStep::Windows(windows) => {
            let prefs = current_prefs.map(object_of).unwrap_or_default();
            let protected = match prefs.get("protected") {
                Some(value) if !is_empty_answer(value) => value.clone(),
                _ => Value::Array(Vec::new()),
            };
            let day_cutoff = prefs.get("day_cutoff").cloned().unwrap_or(Value::Null);
            FlushSetupAction::Windows {
                protected,
                day_cutoff,
                work_windows: windows.clone(),
            }
        }
        SetupStep::Week => FlushSetupAction::Week,
    }
}

/// What `save_availability` decides before sending `PUT /api/preferences`.
#[derive(Debug, Clone, PartialEq)]
pub enum SaveAvailability {
    Absent,
    Refused {
        say: &'static str,
    },
    Ready {
        method: &'static str,
        path: &'static str,
        body: Value,
        progress: &'static str,
        done: &'static str,
    },
}

impl SaveAvailability {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Refused { say } => json!({ "kind": "refused", "say": say }),
            Self::Ready {
                method,
                path,
                body,
                progress,
                done,
            } => json!({
                "kind": "ready",
                "method": method,
                "path": path,
                "body": body,
                "progress": progress,
                "done": done,
            }),
        }
    }
}

/// Validate protected time and Study hours windows and build the availability save request.
pub fn prepare_save_availability(
    signed_in: bool,
    prefs: Option<&Value>,
    protected: &Value,
    day_cutoff: &Value,
    work_windows: Option<&Value>,
) -> SaveAvailability {
    if !signed_in {
        return SaveAvailability::Absent;
    }
    let Some(prefs) = prefs else {
        return SaveAvailability::Absent;
    };
    let Some(protected_items) = protected.as_array() else {
        return SaveAvailability::Refused { say: HOURS_REFUSED };
    };
    for window in protected_items {
        if flexweek_service::preferences::protected_window(window).is_err() {
            return SaveAvailability::Refused { say: HOURS_REFUSED };
        }
    }
    if let Some(work) = work_windows {
        let Some(work_items) = work.as_array() else {
            return SaveAvailability::Refused { say: HOURS_REFUSED };
        };
        for window in work_items {
            if flexweek_service::preferences::work_window(window).is_err() {
                return SaveAvailability::Refused { say: HOURS_REFUSED };
            }
        }
    }
    SaveAvailability::Ready {
        method: "PUT",
        path: "/api/preferences",
        body: availability_body(prefs, protected, day_cutoff, work_windows),
        progress: SAVING_AVAILABILITY,
        done: SAVED_AVAILABILITY,
    }
}

/// What a single `save_preferences` request sends when ready.
#[derive(Debug, Clone, PartialEq)]
pub enum SavePreferences {
    Absent,
    Ready {
        method: &'static str,
        path: &'static str,
        body: Value,
        progress: &'static str,
        done: &'static str,
    },
}

impl SavePreferences {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Ready {
                method,
                path,
                body,
                progress,
                done,
            } => json!({
                "kind": "ready",
                "method": method,
                "path": path,
                "body": body,
                "progress": progress,
                "done": done,
            }),
        }
    }
}

/// Guard, request body and status words for one `PUT /api/preferences`.
pub fn prepare_save_preferences(
    signed_in: bool,
    prefs: Option<&Value>,
    updates: &Value,
) -> SavePreferences {
    if !signed_in {
        return SavePreferences::Absent;
    }
    let Some(prefs) = prefs else {
        return SavePreferences::Absent;
    };
    SavePreferences::Ready {
        method: "PUT",
        path: "/api/preferences",
        body: preferences_body(prefs, updates),
        progress: SAVING_PREFERENCES,
        done: SAVED_PREFERENCES,
    }
}

/// What the queued Settings preferences writer decides to do next.
#[derive(Debug, Clone, PartialEq)]
pub enum SavePreferencesAction {
    Wait,
    Send {
        method: &'static str,
        path: &'static str,
        body: Value,
        progress: &'static str,
        done: &'static str,
        batch_len: usize,
    },
}

impl SavePreferencesAction {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Wait => json!({ "kind": "wait" }),
            Self::Send {
                method,
                path,
                body,
                progress,
                done,
                batch_len,
            } => json!({
                "kind": "send",
                "method": method,
                "path": path,
                "body": body,
                "progress": progress,
                "done": done,
                "batch_len": batch_len,
            }),
        }
    }
}

/// Queued Settings preference saves (roadmap R2) and preference-fetch ticket state.
///
/// While a request is in flight, later preference changes coalesce by key (later wins, matching
/// `SetupQueue`) and wait. Once the in-flight save completes, queued changes apply on top of the
/// latest saved preferences so rapid toggles keep both changes. When a save fails, its failure is
/// reported and not retried automatically; later queued changes still flush next on top of the last
/// saved preferences so they are neither lost nor left stuck as unsaved.
#[derive(Debug, Default)]
pub struct PreferencesQueue {
    /// `Some` even when empty so an explicit `{}` save is not silently dropped.
    pending: Option<Map<String, Value>>,
    /// How many enqueued calls were merged into `pending` (for callback dispatch in Python).
    pending_count: usize,
    /// Ticket of the `PUT /api/preferences` currently in flight, if any.
    in_flight_ticket: Option<u64>,
    /// Monotonic ticket guarding `GET /api/preferences` against stale replies.
    fetch_ticket: u64,
}

impl PreferencesQueue {
    /// Queue a preference update when signed in with stored preferences loaded.
    /// Returns `false` (and queues nothing) when signed out or before preferences arrive.
    pub fn enqueue(
        &mut self,
        signed_in: bool,
        has_preferences: bool,
        updates: &Map<String, Value>,
    ) -> bool {
        if !signed_in || !has_preferences {
            return false;
        }
        match &mut self.pending {
            Some(existing) => existing.extend(updates.clone()),
            None => self.pending = Some(updates.clone()),
        }
        self.pending_count += 1;
        true
    }

    /// Take the next coalesced preference save if the session is signed in, idle, and has loaded
    /// preferences. Any stale in-flight ticket from an earlier request is cleared when idle so the
    /// queue cannot wedge if another request preempted the previous save.
    pub fn next(
        &mut self,
        signed_in: bool,
        busy: bool,
        current_ticket: u64,
        current_prefs: Option<&Value>,
    ) -> SavePreferencesAction {
        if !busy
            || self
                .in_flight_ticket
                .is_some_and(|ticket| ticket != current_ticket)
        {
            self.in_flight_ticket = None;
        }
        if !signed_in || busy || self.in_flight_ticket.is_some() {
            return SavePreferencesAction::Wait;
        }
        let Some(prefs) = current_prefs else {
            return SavePreferencesAction::Wait;
        };
        let Some(updates) = self.pending.take() else {
            return SavePreferencesAction::Wait;
        };
        let batch_len = std::mem::take(&mut self.pending_count);
        match prepare_save_preferences(true, Some(prefs), &Value::Object(updates)) {
            SavePreferences::Ready {
                method,
                path,
                body,
                progress,
                done,
            } => SavePreferencesAction::Send {
                method,
                path,
                body,
                progress,
                done,
                batch_len,
            },
            SavePreferences::Absent => SavePreferencesAction::Wait,
        }
    }

    pub fn mark_in_flight(&mut self, ticket: u64) {
        self.in_flight_ticket = Some(ticket);
    }

    pub fn finish(&mut self, ticket: u64) {
        if self.in_flight_ticket == Some(ticket) {
            self.in_flight_ticket = None;
        }
    }

    pub fn has_pending(&self) -> bool {
        self.pending.is_some()
    }

    pub fn pending_count(&self) -> usize {
        self.pending_count
    }

    /// Drop queued preference saves on sign-out or account change, and advance `fetch_ticket` so an
    /// in-flight `GET /api/preferences` from the previous account cannot land later.
    pub fn clear(&mut self) {
        self.pending = None;
        self.pending_count = 0;
        self.in_flight_ticket = None;
        self.fetch_ticket += 1;
    }

    pub fn drop_if_other_account(
        &mut self,
        current_id: Option<&Value>,
        incoming_id: &Value,
    ) -> bool {
        let different = current_id != Some(incoming_id);
        if different {
            self.clear();
        }
        different
    }

    /// Start a `GET /api/preferences` fetch, returning its ticket when signed in.
    pub fn begin_fetch(&mut self, signed_in: bool) -> Option<u64> {
        if !signed_in {
            return None;
        }
        self.fetch_ticket += 1;
        Some(self.fetch_ticket)
    }

    /// Whether a `GET /api/preferences` reply for `token` is still current.
    pub fn accept_fetch(&self, token: u64, signed_in: bool) -> bool {
        signed_in && token == self.fetch_ticket
    }

    pub fn fetch_ticket(&self) -> u64 {
        self.fetch_ticket
    }

    pub fn set_fetch_ticket(&mut self, ticket: u64) {
        self.fetch_ticket = ticket;
    }
}

/// What `preview_timer_split` decides before sending `POST /api/timer-split-preview`.
#[derive(Debug, Clone, PartialEq)]
pub enum TimerSplitPreview {
    Absent,
    Ready {
        method: &'static str,
        path: &'static str,
        body: Value,
    },
}

impl TimerSplitPreview {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Ready { method, path, body } => json!({
                "kind": "ready",
                "method": method,
                "path": path,
                "body": body,
            }),
        }
    }
}

/// Build the 5-field `POST /api/timer-split-preview` payload from `duration_min` and preferences.
pub fn prepare_timer_split_preview(
    signed_in: bool,
    prefs: Option<&Value>,
    duration_min: i64,
) -> TimerSplitPreview {
    if !signed_in {
        return TimerSplitPreview::Absent;
    }
    let Some(prefs) = prefs else {
        return TimerSplitPreview::Absent;
    };
    let fields = object_of(prefs);
    let get = |name: &str| fields.get(name).cloned().unwrap_or(Value::Null);
    let body = json!({
        "duration_min": duration_min,
        "timer_work_min": get("timer_work_min"),
        "timer_break_min": get("timer_break_min"),
        "timer_long_break_min": get("timer_long_break_min"),
        "timer_long_break_every": get("timer_long_break_every"),
    });
    TimerSplitPreview::Ready {
        method: "POST",
        path: "/api/timer-split-preview",
        body,
    }
}

/// Extract `list(data.get("presets") or [])` from `/api/timer-presets`.
pub fn parse_timer_presets(data: &Value) -> EngineResult<Vec<Value>> {
    let fields = stored::dict(data)?;
    match fields.get("presets") {
        None => Ok(Vec::new()),
        Some(value) if !truthy(Some(value)) => Ok(Vec::new()),
        Some(Value::Array(items)) => Ok(items.clone()),
        Some(Value::String(text)) => {
            Ok(text.chars().map(|ch| Value::from(ch.to_string())).collect())
        }
        Some(Value::Object(map)) => Ok(map.keys().map(|key| Value::from(key.as_str())).collect()),
        Some(other) => Err(EngineError {
            kind: ErrorKind::Type,
            message: format!("'{}' object is not iterable", type_name(other)),
        }),
    }
}

/// Copy the `/api/reminder-limits` JSON object.
pub fn parse_reminder_limits(data: &Value) -> EngineResult<Map<String, Value>> {
    Ok(stored::dict(data)?.clone())
}

/// Extract `int(data.get("remaining") or 0)` from `/api/auth/recovery-status`.
pub fn parse_recovery_status(data: &Value) -> EngineResult<i64> {
    let fields = stored::dict(data)?;
    match fields.get("remaining") {
        None => Ok(0),
        Some(value) if !truthy(Some(value)) => Ok(0),
        Some(value) => py_int(value),
    }
}

/// What the window decides before it acts on a new first day of the week.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FirstWeekday {
    pub changed: bool,
    /// The open week becomes the one from the new first day, once nothing is held.
    pub refollow: bool,
    /// The focus timer keeps its date, in the week from the new first day.
    pub rebase_focus: bool,
}

impl FirstWeekday {
    pub fn to_json(self) -> Value {
        json!({
            "changed": self.changed,
            "refollow": self.refollow,
            "rebase_focus": self.rebase_focus,
        })
    }
}

/// Signed out, the shown week simply follows the selected day. Signed in, a first day that really changed
/// moves the focus timer's week and the open week; the same first day again moves nothing.
pub fn follow_first_weekday(old: i64, new: i64, signed_in: bool) -> FirstWeekday {
    let changed = old != new;
    FirstWeekday {
        changed,
        refollow: signed_in && changed,
        rebase_focus: signed_in && changed,
    }
}
