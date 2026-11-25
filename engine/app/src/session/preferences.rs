//! Setup's write queue and the preference request bodies (P4 group 8): the rules of controller.py's
//! `keep_setup` and `flush_setup`, of the bodies `save_preferences` and `save_availability` send, and of
//! what `follow_first_weekday` decides before it acts. The window keeps the requests, their callbacks and
//! its signals, and applies what is answered here.

use flexweek_engine::desk::custom_look::known_pack;
use serde_json::{Map, Value, json};

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
