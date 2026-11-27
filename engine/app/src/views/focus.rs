//! The Material Focus screen's decisions (P5-F1), moved from `desktop/native/material/bridge_focus.py`.
//! The timer state, preferences and homework arrive as the Python values the bridge held; the
//! caller passes the clock reading in. Wrong kinds of value raise what Python raised.

use flexweek_engine::desk::focus::{format_countdown, phase_duration_ms, remaining_ms};
use flexweek_engine::stored::{attribute_error, py_str, truthy};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::Value;

pub const PHASE_WORDS: [(&str, &str); 4] = [
    ("work", "Focus"),
    ("break", "Break"),
    ("long_break", "Long break"),
    ("ended", "Session finished"),
];
pub const READY_WORDS: &str = "Ready when you are";
pub const QUICK_TITLE: &str = "Quick focus";
pub const PAUSED_SUFFIX: &str = " · Paused";
pub const SKIP_HINTS: [(&str, &str); 3] = [
    ("work", "Skip to the break"),
    ("break", "Skip the break"),
    ("long_break", "Skip the break"),
];
pub const SKIP_DEFAULT: &str = "Skip";
pub const AUDIO_WORDS: [(&str, &str); 4] = [
    ("rain", "Rain"),
    ("lo-fi", "Lo-Fi"),
    ("white-noise", "White noise"),
    ("spotify", "Spotify"),
];
pub const MUTED_WORDS: &str = "Alerts muted";
pub const COUNTS_TOWARD_HOMEWORK: &str = " It counts toward the homework.";
pub const MARKED_ORIGIN_NAME: &str = "materialFocus";

/// What the bridge does next. The Python side keeps the Qt calls and maps each word to one.
pub const STEP_HIDE: &str = "hide";
pub const STEP_REQUEST_END: &str = "request_end";
pub const STEP_CONFIRM_END: &str = "confirm_end";
pub const STEP_STAY: &str = "stay";

fn lookup(words: &[(&'static str, &'static str)], key: &str) -> Option<&'static str> {
    words
        .iter()
        .find(|(name, _)| *name == key)
        .map(|(_, text)| *text)
}

/// `value.get(key)`: only a dict has `get`.
fn get<'a>(value: &'a Value, key: &str) -> EngineResult<Option<&'a Value>> {
    match value {
        Value::Object(map) => Ok(map.get(key)),
        other => Err(attribute_error(other, "get")),
    }
}

/// A list or dict cannot be a dict key.
fn hashable(value: &Value) -> EngineResult<()> {
    let kind = match value {
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
        _ => return Ok(()),
    };
    Err(EngineError {
        kind: ErrorKind::Type,
        message: format!("unhashable type: '{kind}'"),
    })
}

fn key_error(message: &str) -> EngineError {
    EngineError {
        kind: ErrorKind::Key,
        message: message.to_string(),
    }
}

/// `str(state.get("phase") or "work")`, or "ready" when no timer exists.
pub fn phase(state: &Value) -> EngineResult<String> {
    if state.is_null() {
        return Ok("ready".to_string());
    }
    Ok(match get(state, "phase")? {
        Some(found) if truthy(Some(found)) => py_str(found),
        _ => "work".to_string(),
    })
}

pub fn ready(state: &Value) -> bool {
    state.is_null()
}

pub fn ended(state: &Value) -> EngineResult<bool> {
    Ok(phase(state)? == "ended")
}

/// A timer exists and its session has not ended: Skip, Pause and Finish apply.
pub fn active(state: &Value) -> EngineResult<bool> {
    Ok(!state.is_null() && phase(state)? != "ended")
}

/// `bool(state and state.get("running") and phase != "ended")`: an empty state is not running.
pub fn running(state: &Value) -> EngineResult<bool> {
    if !truthy(Some(state)) || !truthy(get(state, "running")?) {
        return Ok(false);
    }
    Ok(phase(state)? != "ended")
}

pub fn paused(state: &Value) -> EngineResult<bool> {
    Ok(active(state)? && !running(state)?)
}

pub fn phase_text(state: &Value) -> EngineResult<String> {
    if state.is_null() {
        return Ok(READY_WORDS.to_string());
    }
    let mut words = lookup(&PHASE_WORDS, &phase(state)?)
        .unwrap_or("")
        .to_string();
    if paused(state)? {
        words.push_str(PAUSED_SUFFIX);
    }
    Ok(words)
}

/// The homework on now or next today, while Ready; a running timer has already chosen.
fn offer_for<'a>(state: &Value, offer: &'a Value) -> Option<&'a Value> {
    if state.is_null() && !offer.is_null() {
        Some(offer)
    } else {
        None
    }
}

/// Ready with homework on now or next today: Start counts toward it and Just a timer does not.
pub fn offered(state: &Value, offer: &Value) -> bool {
    offer_for(state, offer).is_some()
}

pub fn title(state: &Value, offer: &Value) -> EngineResult<String> {
    if state.is_null() {
        return match offer_for(state, offer) {
            None => Ok(QUICK_TITLE.to_string()),
            Some(found) => match get(found, "title")? {
                Some(name) => Ok(py_str(name)),
                None => Err(key_error("title")),
            },
        };
    }
    Ok(match get(state, "title")? {
        Some(name) if truthy(Some(name)) => py_str(name),
        _ => QUICK_TITLE.to_string(),
    })
}

fn clamp_ms(milliseconds: i128) -> i64 {
    i64::try_from(milliseconds).unwrap_or(if milliseconds < 0 { i64::MIN } else { i64::MAX })
}

/// The countdown the screen shows: a full work phase while Ready, zero once ended.
pub fn time_text(state: &Value, prefs: &Value, now_ms: i64) -> EngineResult<String> {
    if state.is_null() {
        let full = phase_duration_ms(&Value::String("work".into()), prefs)?;
        return Ok(format_countdown(clamp_ms(full)));
    }
    if phase(state)? == "ended" {
        return Ok(format_countdown(0));
    }
    Ok(format_countdown(clamp_ms(remaining_ms(state, now_ms)?)))
}

pub fn pause_text(state: &Value) -> EngineResult<&'static str> {
    Ok(if running(state)? { "Pause" } else { "Resume" })
}

pub fn skip_hint(state: &Value) -> EngineResult<&'static str> {
    Ok(lookup(&SKIP_HINTS, &phase(state)?).unwrap_or(SKIP_DEFAULT))
}

/// What is on for this session: "Alerts muted · Rain". The sound shows only once a timer exists.
pub fn note(state: &Value, prefs: &Value, mutes_alerts: bool) -> EngineResult<String> {
    let mut words: Vec<&str> = Vec::new();
    if mutes_alerts {
        words.push(MUTED_WORDS);
    }
    let chosen = if truthy(Some(prefs)) {
        get(prefs, "focus_audio")?
    } else {
        None
    };
    if let Some(name) = chosen {
        hashable(name)?;
    }
    if let Some(Value::String(name)) = chosen
        && let Some(sound) = lookup(&AUDIO_WORDS, name.as_str())
        && !state.is_null()
    {
        words.push(sound);
    }
    Ok(words.join(" · "))
}

/// `(assignments or {}).get(key)`: only a dict has `get`, and a key must be hashable.
fn assignment_for<'a>(assignments: &'a Value, key: &Value) -> EngineResult<Option<&'a Value>> {
    if !truthy(Some(assignments)) {
        return Ok(None);
    }
    // A truthy non-dict has no `get`: ask the same way Python does and keep the error.
    get(assignments, "")?;
    hashable(key)?;
    Ok(key.as_str().and_then(|name| assignments.get(name)))
}

/// Time is up on homework that is still open: Finished marks it done.
pub fn can_finish_homework(state: &Value, assignments: &Value) -> EngineResult<bool> {
    if state.is_null() || phase(state)? != "ended" {
        return Ok(false);
    }
    let id = get(state, "assignmentId")?.unwrap_or(&Value::Null);
    match assignment_for(assignments, id)? {
        None | Some(Value::Null) => Ok(false),
        Some(homework) => Ok(!truthy(get(homework, "completed")?)),
    }
}

/// The yes-or-no question before an unfinished session is ended.
pub fn end_question(
    state: &Value,
    assignments: &Value,
    title: &str,
    elapsed_min: i64,
) -> EngineResult<String> {
    let mut question = format!("You've done {elapsed_min} min of {title}.");
    let held = if truthy(Some(state)) {
        get(state, "assignmentId")?.unwrap_or(&Value::Null)
    } else {
        &Value::Null
    };
    hashable(held)?;
    let known = truthy(Some(assignments)) && assignment_for(assignments, held)?.is_some();
    if known {
        question.push_str(COUNTS_TOWARD_HOMEWORK);
    }
    Ok(question)
}

/// A session that is gone has nothing left to show: the screen closes with it.
pub fn refresh_open(open: bool, account_missing: bool) -> bool {
    open && !account_missing
}

/// Leaving by Finish: a timer that has begun asks first, none left just closes, an ended one is
/// cleared as a confirmed end.
pub fn leave_step(state: &Value) -> EngineResult<&'static str> {
    if active(state)? {
        Ok(STEP_REQUEST_END)
    } else if state.is_null() {
        Ok(STEP_HIDE)
    } else {
        Ok(STEP_CONFIRM_END)
    }
}

/// Back: a running or paused timer keeps going behind the other screens; otherwise leaving is Finish.
pub fn back_step(state: &Value) -> EngineResult<&'static str> {
    if active(state)? {
        Ok(STEP_HIDE)
    } else {
        leave_step(state)
    }
}

/// Queued still closes the screen: the week is loading behind it and the homework finishes when
/// that load lands. A failed load leaves the ended timer for the next open.
pub fn finish_step(outcome: Option<&str>) -> &'static str {
    match outcome {
        Some("finished") | Some("queued") => STEP_HIDE,
        _ => STEP_STAY,
    }
}

/// An empty block id from the screen means no block: the timer is not tied to one.
pub fn block_for_start(block_id: &str) -> Option<&str> {
    if block_id.is_empty() {
        None
    } else {
        Some(block_id)
    }
}

/// A started session opens the screen on it; a refused start leaves things as they were.
pub fn after_start_step(started: bool) -> &'static str {
    if started { "show" } else { STEP_STAY }
}

/// The item that held keyboard focus is remembered unless it is the screen's own.
pub fn remembers_origin(object_name: &str) -> bool {
    object_name != MARKED_ORIGIN_NAME
}

/// The remembered item gets focus back only while it is still shown and usable.
pub fn restores_origin(visible: bool, enabled: bool, can_take_focus: bool) -> bool {
    visible && enabled && can_take_focus
}
