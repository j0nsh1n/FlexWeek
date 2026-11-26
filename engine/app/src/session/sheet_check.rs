//! Field-aware validation for the Add/Edit fixed time and homework sheets (`sheet_block.py`,
//! `sheet_homework.py`, `bridge_settings.py`, `sheet_rules.py`). Built on the engine's own
//! `validate.rs` and `homework_saves.rs` rules so accept/refuse matches the service 100%, while
//! naming the field and student-facing sentence the sheet displays.

use flexweek_engine::model;
use flexweek_engine::validate::{
    ASSIGNMENT_FIELDS, time_block, week_request, whole_number, yes_or_no,
};
use flexweek_service::homework_saves::check_homework;
use serde_json::{Map, Value, json};

const REVISION_MAX: i128 = (1_i128 << 53) - 1;

pub const BLOCK_TITLE_PROBLEM: &str = "Give it a title.";
pub const BLOCK_DAYS_PROBLEM: &str = "Tick at least one day.";
pub const BLOCK_SPOTIFY_PROBLEM: &str = "That's not a Spotify share link. Paste one that starts with https://open.spotify.com, or leave it empty.";
pub const BLOCK_REFUSED: &str =
    "FlexWeek can't keep this block as it is. Check its title, days and times.";

pub const HOMEWORK_TITLE_EMPTY: &str = "Give the homework a title.";
pub const HOMEWORK_TITLE_LONG: &str = "Keep the homework title under 80 characters.";
pub const HOMEWORK_ESTIMATE_PROBLEM: &str = "That time isn't a multiple of 15 minutes.";
pub const HOMEWORK_LINK_URL_PROBLEM: &str = "A link needs an http:// or https:// address.";
pub const HOMEWORK_LINK_LABEL_PROBLEM: &str = "Give each link a name under 80 characters.";
pub const HOMEWORK_LINKS_LIMIT_PROBLEM: &str = "Keep no more than 20 links.";
pub const HOMEWORK_CHECKLIST_TEXT_PROBLEM: &str = "Keep each checklist step under 80 characters.";
pub const HOMEWORK_CHECKLIST_LIMIT_PROBLEM: &str = "Keep no more than 40 checklist steps.";
pub const HOMEWORK_DUE_PROBLEM: &str = "Choose a valid due date.";
pub const HOMEWORK_COURSE_PROBLEM: &str = "Keep the course name under 40 characters.";
pub const HOMEWORK_SPOTIFY_PROBLEM: &str = "Paste a Spotify share link from open.spotify.com.";
pub const HOMEWORK_NOTES_PROBLEM: &str = "Keep notes under 4,000 characters.";
pub const HOMEWORK_PRIORITY_PROBLEM: &str = "Choose a type from the list.";
pub const HOMEWORK_ENERGY_PROBLEM: &str = "Choose a time of day from the list.";
pub const HOMEWORK_COMPLETED_AT_PROBLEM: &str = "Set a valid time for finished homework.";
pub const HOMEWORK_REFUSED: &str = "Check the homework details and try again.";

/// Validates one block as a single-block `WeekRequest` (all `TimeBlock` and week rules).
/// Returns `None` when valid, or `Some((field, message))` matching `sheet_rules.py`'s
/// `BLOCK_PROBLEMS` / `BLOCK_REFUSED`.
pub fn block_sheet_problem(value: &Value) -> Option<(String, String)> {
    if week_request(&json!({ "blocks": [value] })).is_ok() {
        return None;
    }
    // `WeekRequest`'s own validator only reports on `blocks`, so any failure after `TimeBlock`
    // passes maps straight to `BLOCK_REFUSED`.
    if time_block(value).is_ok() {
        return Some((String::new(), BLOCK_REFUSED.to_string()));
    }
    if let Some(map) = value.as_object() {
        if !valid_req_str(map, "title", 1, 80) {
            return Some(("title".to_string(), BLOCK_TITLE_PROBLEM.to_string()));
        }
        if !valid_block_days(map) {
            return Some(("days".to_string(), BLOCK_DAYS_PROBLEM.to_string()));
        }
        if !valid_spotify(map) {
            return Some(("spotify_url".to_string(), BLOCK_SPOTIFY_PROBLEM.to_string()));
        }
    }
    Some((String::new(), BLOCK_REFUSED.to_string()))
}

/// Validates a homework dict from the sheet: filters to `Assignment`'s 18 fields, checks via
/// `homework_saves::check_homework`, and on refusal returns the first failing field (in
/// `Assignment` declaration order) and student-facing sentence from `sheet_rules.py`.
pub fn homework_sheet_problem(value: &Value) -> Option<(String, String)> {
    let Some(raw) = value.as_object() else {
        return Some((String::new(), HOMEWORK_REFUSED.to_string()));
    };
    let filtered: Map<String, Value> = raw
        .iter()
        .filter(|(key, _)| key.as_str() == "revision" || ASSIGNMENT_FIELDS.contains(&key.as_str()))
        .map(|(key, val)| (key.clone(), val.clone()))
        .collect();
    if check_homework(&Value::Object(filtered.clone())).is_ok() {
        return None;
    }
    Some(classify_homework_problem(&filtered))
}

fn classify_homework_problem(map: &Map<String, Value>) -> (String, String) {
    if !valid_req_str(map, "id", 1, 80) {
        return ("id".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if let Some(msg) = title_problem(map) {
        return ("title".to_string(), msg.to_string());
    }
    if !valid_opt_str(map, "course", 40) {
        return ("course".to_string(), HOMEWORK_COURSE_PROBLEM.to_string());
    }
    if !valid_opt_str(map, "category", 32) {
        return ("category".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if !valid_literal_i64_default(map, "priority", &[1, 2, 3, 4]) {
        return (
            "priority".to_string(),
            HOMEWORK_PRIORITY_PROBLEM.to_string(),
        );
    }
    if !valid_literal_str_default(map, "energy", &["high", "medium", "low"]) {
        return ("energy".to_string(), HOMEWORK_ENERGY_PROBLEM.to_string());
    }
    if !valid_spotify(map) {
        return (
            "spotify_url".to_string(),
            HOMEWORK_SPOTIFY_PROBLEM.to_string(),
        );
    }
    if !valid_required_due(map) {
        return ("due".to_string(), HOMEWORK_DUE_PROBLEM.to_string());
    }
    if !valid_estimate(map) {
        return (
            "estimate_min".to_string(),
            HOMEWORK_ESTIMATE_PROBLEM.to_string(),
        );
    }
    if !valid_literal_str_default(map, "spread", &["one", "spread"]) {
        return ("spread".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if !valid_int_default(map, "focus_minutes", 0, 71400) {
        return ("focus_minutes".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if !valid_int_default(map, "focus_sessions", 0, 9999) {
        return ("focus_sessions".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if !valid_bool_default(map, "completed") {
        return ("completed".to_string(), HOMEWORK_REFUSED.to_string());
    }
    if !valid_completed_at(map) {
        return (
            "completed_at".to_string(),
            HOMEWORK_COMPLETED_AT_PROBLEM.to_string(),
        );
    }
    if !valid_notes(map) {
        return ("notes".to_string(), HOMEWORK_NOTES_PROBLEM.to_string());
    }
    if let Some(msg) = links_problem(map) {
        return ("links".to_string(), msg.to_string());
    }
    if let Some(msg) = checklist_problem(map) {
        return ("checklist".to_string(), msg.to_string());
    }
    if !valid_revision(map) {
        return ("revision".to_string(), HOMEWORK_REFUSED.to_string());
    }
    (String::new(), HOMEWORK_REFUSED.to_string())
}

fn title_problem(map: &Map<String, Value>) -> Option<&'static str> {
    match map.get("title") {
        Some(Value::String(text)) => {
            let count = text.chars().count();
            if count > 80 {
                // Schema max_length runs before the blank-title validator, so >80 spaces is too long.
                Some(HOMEWORK_TITLE_LONG)
            } else if count < 1 || python_strip(text).is_empty() {
                Some(HOMEWORK_TITLE_EMPTY)
            } else {
                None
            }
        }
        _ => Some(HOMEWORK_TITLE_EMPTY),
    }
}

fn valid_req_str(map: &Map<String, Value>, key: &str, min: usize, max: usize) -> bool {
    match map.get(key) {
        Some(Value::String(text)) => {
            let count = text.chars().count();
            count >= min && count <= max
        }
        _ => false,
    }
}

fn valid_opt_str(map: &Map<String, Value>, key: &str, max: usize) -> bool {
    match map.get(key) {
        None | Some(Value::Null) => true,
        Some(Value::String(text)) => text.chars().count() <= max,
        Some(_) => false,
    }
}

fn valid_block_days(map: &Map<String, Value>) -> bool {
    let Some(Value::Array(items)) = map.get("days") else {
        return false;
    };
    if items.is_empty() || items.len() > 7 {
        return false;
    }
    items
        .iter()
        .all(|item| whole_number(item).is_some_and(|day| (0..=6).contains(&day)))
}

fn valid_spotify(map: &Map<String, Value>) -> bool {
    match map.get("spotify_url") {
        None | Some(Value::Null) => true,
        Some(Value::String(text)) => {
            text.chars().count() <= 500 && model::valid_spotify_url(Some(text)).is_ok()
        }
        Some(_) => false,
    }
}

fn valid_required_due(map: &Map<String, Value>) -> bool {
    match map.get("due") {
        Some(Value::String(text)) => model::valid_due(text).is_ok(),
        _ => false,
    }
}

fn valid_estimate(map: &Map<String, Value>) -> bool {
    map.get("estimate_min")
        .and_then(whole_number)
        .is_some_and(|n| n > 0 && n <= i128::from(model::ESTIMATE_MAX_MIN) && n % 15 == 0)
}

fn valid_literal_i64_default(map: &Map<String, Value>, key: &str, options: &[i64]) -> bool {
    let Some(value) = map.get(key) else {
        return true;
    };
    let read = match value {
        Value::Bool(_) | Value::Number(_) => whole_number(value),
        _ => None,
    };
    read.and_then(|int| i64::try_from(int).ok())
        .is_some_and(|int| options.contains(&int))
}

fn valid_literal_str_default(map: &Map<String, Value>, key: &str, options: &[&str]) -> bool {
    match map.get(key) {
        None => true,
        Some(Value::String(text)) => options.contains(&text.as_str()),
        Some(_) => false,
    }
}

fn valid_int_default(map: &Map<String, Value>, key: &str, min: i64, max: i64) -> bool {
    match map.get(key) {
        None => true,
        Some(value) => {
            whole_number(value).is_some_and(|int| int >= i128::from(min) && int <= i128::from(max))
        }
    }
}

fn valid_bool_default(map: &Map<String, Value>, key: &str) -> bool {
    match map.get(key) {
        None => true,
        Some(value) => yes_or_no(value).is_some(),
    }
}

fn valid_completed_at(map: &Map<String, Value>) -> bool {
    match map.get("completed_at") {
        None | Some(Value::Null) => true,
        Some(Value::String(text)) => model::valid_naive_stamp(text).is_ok(),
        Some(_) => false,
    }
}

fn valid_notes(map: &Map<String, Value>) -> bool {
    match map.get("notes") {
        None => true,
        Some(Value::String(text)) => text.chars().count() <= 4000,
        Some(_) => false,
    }
}

fn links_problem(map: &Map<String, Value>) -> Option<&'static str> {
    let value = map.get("links")?;
    let Some(items) = value.as_array() else {
        return Some(HOMEWORK_LINKS_LIMIT_PROBLEM);
    };
    // pydantic reports a list over its cap before looking at any item, so the cap sentence wins.
    if items.len() > 20 {
        return Some(HOMEWORK_LINKS_LIMIT_PROBLEM);
    }
    for item in items {
        let Some(obj) = item.as_object() else {
            return Some(HOMEWORK_LINKS_LIMIT_PROBLEM);
        };
        let label_ok = match obj.get("label") {
            Some(Value::String(text)) => {
                let len = text.chars().count();
                (1..=80).contains(&len) && !python_strip(text).is_empty()
            }
            _ => false,
        };
        if !label_ok {
            return Some(HOMEWORK_LINK_LABEL_PROBLEM);
        }
        let url_ok = match obj.get("url") {
            Some(Value::String(text)) => {
                let len = text.chars().count();
                (1..=500).contains(&len) && model::valid_http_url(text).is_ok()
            }
            _ => false,
        };
        if !url_ok {
            return Some(HOMEWORK_LINK_URL_PROBLEM);
        }
        if obj.keys().any(|k| k != "label" && k != "url") {
            return Some(HOMEWORK_LINKS_LIMIT_PROBLEM);
        }
    }
    None
}

fn checklist_problem(map: &Map<String, Value>) -> Option<&'static str> {
    let value = map.get("checklist")?;
    let Some(items) = value.as_array() else {
        return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
    };
    // pydantic reports a list over its cap before looking at any item, so the cap sentence wins.
    if items.len() > 40 {
        return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
    }
    for item in items {
        let Some(obj) = item.as_object() else {
            return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
        };
        if !valid_req_str(obj, "id", 1, 80) {
            return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
        }
        let text_ok = match obj.get("text") {
            Some(Value::String(text)) => {
                let len = text.chars().count();
                (1..=80).contains(&len) && !python_strip(text).is_empty()
            }
            _ => false,
        };
        if !text_ok {
            return Some(HOMEWORK_CHECKLIST_TEXT_PROBLEM);
        }
        if !valid_bool_default(obj, "done") {
            return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
        }
        if obj.keys().any(|k| k != "id" && k != "text" && k != "done") {
            return Some(HOMEWORK_CHECKLIST_LIMIT_PROBLEM);
        }
    }
    None
}

fn valid_revision(map: &Map<String, Value>) -> bool {
    map.get("revision")
        .and_then(whole_number)
        .is_some_and(|rev| (0..=REVISION_MAX).contains(&rev))
}

/// Python's `str.strip()` with no argument: Unicode white space and the four separator controls.
fn python_strip(text: &str) -> &str {
    text.trim_matches(|ch: char| ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch))
}
