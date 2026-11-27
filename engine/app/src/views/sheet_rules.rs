//! Rules and wording the block, homework and running-late sheets share.
//!
//! Category presets are copied from `desktop/native/calendar.py`. `CategoryInfo` has no preset,
//! so this table can drift from that file until the categories themselves move.

use std::collections::BTreeSet;

use flexweek_engine::desk::calendar::{DAY_FULL, DAYS};
use flexweek_engine::desk::datetext::{day_long, day_of};
use flexweek_engine::desk::grid::{date_for_day, due_day_in_week};
use flexweek_engine::desk::weekmodel::{clock_text, due_label_text, hhmm_text, range_label};
use flexweek_engine::shown::{day_names, weekdays_on_shown_week};
use flexweek_engine::stored::{py_int, py_repr_of, truthy, type_name};
use flexweek_engine::time::{self, DAY_END_MIN, SLOT_MIN, hhmm_to_minutes};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

pub const SPREAD_NOTHING: &str =
    "Nothing left to spread: all of this homework is already done or has focus time recorded.";

// A no-break space keeps "45." on the same line as "or" in a narrow sheet.
pub const SLOT_HINT: &str = "Use a multiple of 15 minutes, such as 15, 30, or\u{00a0}45.";

pub const DUE_PASSED: &str = "That due time has passed. Choose a later one.";
pub const ESTIMATE_ERROR: &str = "That time isn't a multiple of 15 minutes.";
pub const ESTIMATE_SHORT: &str = "Give it at least 15 minutes.";
pub const ESTIMATE_LONG: &str =
    "That's more than 24 hours. Split it into parts and add each part as its own homework.";
pub const HOMEWORK_REFUSED: &str = "Check the homework details and try again.";
pub const REPEAT_NOTE: &str = "Pick every day it happens.";
pub const LATE_WAIT: &str = "Press Preview first to see what moves.";
pub const BLOCK_REFUSED: &str =
    "FlexWeek can't keep this block as it is. Check its title, days and times.";

pub const HOMEWORK_PROBLEMS: &[(&str, &str)] = &[
    ("due", "Choose a valid due date."),
    ("course", "Keep the course name under 40 characters."),
    (
        "spotify_url",
        "Paste a Spotify share link from open.spotify.com.",
    ),
    ("notes", "Keep notes under 4,000 characters."),
    ("priority", "Choose a type from the list."),
    ("energy", "Choose a time of day from the list."),
    ("completed_at", "Set a valid time for finished homework."),
];

pub const BLOCK_PROBLEMS: &[(&str, &str)] = &[
    ("title", "Give it a title."),
    ("days", "Tick at least one day."),
    (
        "spotify_url",
        "That's not a Spotify share link. Paste one that starts with https://open.spotify.com, or leave it empty.",
    ),
];

pub const CUTOFFS: [&str; 7] = [
    "20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00",
];

// Meals first: 18:00-19:30 sits inside the afternoon activity window.
const MEAL_WINDOWS: [(i64, i64); 3] = [
    (7 * 60, 8 * 60),
    (12 * 60, 13 * 60),
    (18 * 60, 19 * 60 + 30),
];

const CLASS_DAYS: [i64; 5] = [0, 1, 2, 3, 4];

struct Preset {
    label: &'static str,
    start: Option<(&'static str, &'static str)>,
    duration_min: Option<i64>,
    days: Option<&'static [i64]>,
}

fn preset_for(category: &str) -> Option<Preset> {
    Some(match category {
        "class" => Preset {
            label: "School",
            start: Some(("08:00", "14:30")),
            duration_min: None,
            days: Some(&CLASS_DAYS),
        },
        "assignments" => Preset {
            label: "Homework",
            start: None,
            duration_min: Some(60),
            days: None,
        },
        "study" => Preset {
            label: "Study",
            start: None,
            duration_min: Some(60),
            days: None,
        },
        "exercise" => Preset {
            label: "Sports",
            start: Some(("15:30", "17:00")),
            duration_min: None,
            days: None,
        },
        "extra" => Preset {
            label: "Activity",
            start: Some(("17:00", "18:00")),
            duration_min: None,
            days: None,
        },
        "meals" => Preset {
            label: "Meals",
            start: Some(("18:00", "18:30")),
            duration_min: None,
            days: None,
        },
        "sleep" => Preset {
            label: "Sleep",
            start: Some(("22:00", "23:00")),
            duration_min: None,
            days: None,
        },
        "free" => Preset {
            label: "Free",
            start: Some(("19:00", "20:00")),
            duration_min: None,
            days: None,
        },
        _ => return None,
    })
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

fn as_dict(value: &Value) -> EngineResult<&Map<String, Value>> {
    value.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Attribute,
        message: format!("'{}' object has no attribute 'get'", type_name(value)),
    })
}

fn name_at<'a>(names: &[&'a str], day: i64) -> EngineResult<&'a str> {
    let len = i64::try_from(names.len()).unwrap_or(i64::MAX);
    let index = if day < 0 { day + len } else { day };
    if index < 0 || index >= len {
        return Err(EngineError::index("tuple index out of range"));
    }
    Ok(names[usize::try_from(index).unwrap_or(usize::MAX)])
}

fn names_of(week_start: &str, full: bool) -> EngineResult<Vec<&'static str>> {
    if week_start.is_empty() {
        let names: &[&str] = if full { &DAY_FULL } else { &DAYS };
        return Ok(names.to_vec());
    }
    day_names(week_start, full)
}

pub fn guess_locked_category(start: &str) -> EngineResult<String> {
    let minute = hhmm_to_minutes(start)?;
    for (low, high) in MEAL_WINDOWS {
        if low <= minute && minute < high {
            return Ok("meals".to_string());
        }
    }
    let school_start = 8 * 60;
    let school_end = 14 * 60 + 30;
    if school_start <= minute && minute < school_end {
        return Ok("class".to_string());
    }
    Ok("extra".to_string())
}

pub fn short_day_name(week_start: &str, day: i64) -> EngineResult<String> {
    Ok(name_at(&names_of(week_start, false)?, day)?.to_string())
}

pub fn full_day_name(week_start: &str, day: i64) -> EngineResult<String> {
    Ok(name_at(&names_of(week_start, true)?, day)?.to_string())
}

pub fn same_weekday(day: i64, from_week: &str, to_week: &str) -> EngineResult<i64> {
    if from_week.is_empty() || to_week.is_empty() || from_week == to_week {
        return Ok(day);
    }
    let date = date_for_day(from_week, &Value::from(day))?;
    Ok(due_day_in_week(&date, to_week)?.rem_euclid(7))
}

fn same_first_weekday(from_week: &str, to_week: &str) -> EngineResult<bool> {
    let from_name = day_names(from_week, false)?;
    let to_name = day_names(to_week, false)?;
    Ok(from_name.first() == to_name.first())
}

pub type DayShift = (i64, i64);

pub type TurnedDays = (Vec<i64>, Vec<DayShift>);

pub fn turn_days_keeping_weekdays(
    days: &[i64],
    from_week: &str,
    to_week: &str,
) -> EngineResult<TurnedDays> {
    if from_week.is_empty() || to_week.is_empty() || from_week == to_week {
        let mut kept = days.to_vec();
        kept.sort();
        return Ok((kept, Vec::new()));
    }
    let mut turned = Vec::with_capacity(days.len());
    for day in days {
        turned.push((*day, same_weekday(*day, from_week, to_week)?));
    }
    let mut news: Vec<i64> = turned.iter().map(|(_, new)| *new).collect();
    news.sort();
    // Another week from the same first day keeps every day's place: nothing moved.
    if same_first_weekday(from_week, to_week)? {
        return Ok((news, Vec::new()));
    }
    let mut moved = Vec::new();
    for (old, new) in turned {
        let old_date = date_for_day(from_week, &Value::from(old))?;
        let new_date = date_for_day(to_week, &Value::from(new))?;
        if old_date != new_date {
            moved.push((old, new));
        }
    }
    Ok((news, moved))
}

pub fn first_day_changed(from_week: &str, to_week: &str) -> EngineResult<bool> {
    if from_week.is_empty() || to_week.is_empty() {
        return Ok(false);
    }
    Ok(!same_first_weekday(from_week, to_week)?)
}

fn month_of(iso: &str) -> Option<&str> {
    iso.get(..7)
}

fn day_number(iso: &str) -> EngineResult<i64> {
    let digits = iso.get(8..).ok_or_else(|| {
        EngineError::value(format!("invalid literal for int() with base 10: {iso:?}"))
    })?;
    time::py_int(digits)
}

pub fn moved_day_names(
    old_day: i64,
    from_week: &str,
    new_day: i64,
    to_week: &str,
) -> EngineResult<(String, String)> {
    let old_date = date_for_day(from_week, &Value::from(old_day))?;
    let new_date = date_for_day(to_week, &Value::from(new_day))?;
    if month_of(&old_date) == month_of(&new_date) {
        return Ok((
            format!(
                "{} {}",
                full_day_name(from_week, old_day)?,
                day_number(&old_date)?
            ),
            format!(
                "{} {}",
                full_day_name(to_week, new_day)?,
                day_number(&new_date)?
            ),
        ));
    }
    // Each date is its own reference, so the year stays hidden and the month is named.
    let old = day_of(&old_date)?;
    let new = day_of(&new_date)?;
    Ok((day_long(old, old), day_long(new, new)))
}

pub fn moved_across_months(
    old_day: i64,
    from_week: &str,
    new_day: i64,
    to_week: &str,
) -> EngineResult<bool> {
    let old_date = date_for_day(from_week, &Value::from(old_day))?;
    let new_date = date_for_day(to_week, &Value::from(new_day))?;
    Ok(month_of(&old_date) != month_of(&new_date))
}

fn join_and(parts: &[String]) -> String {
    let last = parts.len().saturating_sub(1);
    let mut text = parts[..last].join(", ");
    text.push_str(" and ");
    text.push_str(&parts[last]);
    text
}

pub fn moved_days_note(moves: &[(String, String)]) -> String {
    if moves.is_empty() {
        return String::new();
    }
    if moves.len() == 1 {
        return format!(
            "{} isn't in this week any more, so it moved to {}.",
            moves[0].0, moves[0].1
        );
    }
    let olds: Vec<String> = moves.iter().map(|(old, _)| old.clone()).collect();
    let news: Vec<String> = moves.iter().map(|(_, new)| new.clone()).collect();
    format!(
        "{} aren't in this week any more, so they moved to {}.",
        join_and(&olds),
        join_and(&news)
    )
}

pub fn day_range_words(days: &[i64], week_start: &str) -> EngineResult<String> {
    if days.is_empty() {
        return Ok(String::new());
    }
    let names = names_of(week_start, false)?;
    let mut ordered = days.to_vec();
    ordered.sort();
    ordered.dedup();
    let mut runs: Vec<Vec<i64>> = vec![vec![ordered[0]]];
    for day in ordered.iter().skip(1) {
        let last = runs.last_mut().expect("a range starts with one run");
        if *day == last[last.len() - 1] + 1 {
            last.push(*day);
        } else {
            runs.push(vec![*day]);
        }
    }
    let mut parts = Vec::new();
    for run in &runs {
        if run.len() >= 3 {
            let start = name_at(&names, run[0])?;
            let end = name_at(&names, run[run.len() - 1])?;
            parts.push(format!("{start}\u{2013}{end}"));
        } else {
            for day in run {
                parts.push(name_at(&names, *day)?.to_string());
            }
        }
    }
    Ok(parts.join(", "))
}

pub fn day_range_and_words(days: &[i64], week_start: &str) -> EngineResult<String> {
    let words = day_range_words(days, week_start)?;
    Ok(match words.rsplit_once(", ") {
        Some((head, last)) => format!("{head} and {last}"),
        None => words,
    })
}

fn category_key(value: &Value) -> &str {
    match value {
        Value::String(text) => text.as_str(),
        _ => "",
    }
}

fn minutes_between(start: &str, end: &str) -> EngineResult<i64> {
    let start_min = hhmm_to_minutes(start)?;
    let end_min = hhmm_to_minutes(end)?;
    end_min
        .checked_sub(start_min)
        .ok_or_else(|| EngineError::overflow("Python int too large to convert to C long"))
}

/// `id` is chosen by the caller. This function does not draw one.
pub fn preset_locked(input: &Value) -> EngineResult<Value> {
    let map = as_dict(input)?;
    let id = map
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| type_error("id must be text"))?;
    let category = map.get("category").cloned().unwrap_or(Value::Null);
    let day = py_int(map.get("day").ok_or_else(|| EngineError::key("day"))?)?;
    let start = map
        .get("start")
        .and_then(Value::as_str)
        .ok_or_else(|| type_error("start must be text"))?;
    let duration_min = py_int(
        map.get("duration_min")
            .ok_or_else(|| EngineError::key("duration_min"))?,
    )?;
    let week_start = map.get("week_start").and_then(Value::as_str).unwrap_or("");
    let mut days = vec![day];
    let mut title = String::new();
    let mut chosen_start = start.to_string();
    let mut chosen_duration = duration_min;
    if let Some(info) = preset_for(category_key(&category)) {
        title = info.label.to_string();
        if duration_min == 60
            && start == "16:00"
            && let Some((preset_start, preset_end)) = info.start
        {
            chosen_start = preset_start.to_string();
            chosen_duration = minutes_between(preset_start, preset_end)?;
            if let Some(preset_days) = info.days {
                days = preset_days.to_vec();
                if !week_start.is_empty() {
                    days = weekdays_on_shown_week(week_start, &days)?;
                }
            }
        } else if info.start.is_none()
            && let Some(preset_duration) = info.duration_min
        {
            chosen_duration = preset_duration;
        }
    }
    Ok(json!({
        "id": id,
        "kind": "locked",
        "title": title,
        "days": days,
        "start": chosen_start,
        "duration_min": chosen_duration,
        "category": category,
    }))
}

fn session_date(item: &Value) -> EngineResult<String> {
    let map = as_dict(item)?;
    let date = map.get("date").ok_or_else(|| EngineError::key("date"))?;
    match date {
        Value::String(text) => Ok(text.clone()),
        Value::Null => Ok("None".to_string()),
        Value::Bool(flag) => Ok(flag.to_string()),
        Value::Number(number) => Ok(number.to_string()),
        other => Err(type_error(format!(
            "unhashable type: '{}'",
            type_name(other)
        ))),
    }
}

pub fn spread_words(sessions: &Value, due: &str, today: &str) -> EngineResult<String> {
    if !truthy(Some(sessions)) {
        return Ok(SPREAD_NOTHING.to_string());
    }
    let Some(items) = sessions.as_array() else {
        return Err(type_error(format!(
            "'{}' object is not iterable",
            type_name(sessions)
        )));
    };
    let mut sizes = Vec::with_capacity(items.len());
    for item in items {
        let map = as_dict(item)?;
        let raw = map
            .get("duration_min")
            .ok_or_else(|| EngineError::key("duration_min"))?;
        sizes.push(py_int(raw)?);
    }
    let full = sizes[0];
    let whole = sizes.iter().filter(|size| **size == full).count();
    let lead = if whole > 1 {
        format!("{whole} \u{00d7} {full} min")
    } else {
        format!("{full} min")
    };
    let parts = if whole == sizes.len() {
        lead
    } else {
        format!("{lead} and {} min", sizes[sizes.len() - 1])
    };
    let due_words = due_label_text(Some(due), day_of(today)?)?;
    let ahead = format!("before it's due {due_words}.");
    if sizes.len() == 1 {
        return Ok(format!("{parts} in one session {ahead}"));
    }
    let mut dates = BTreeSet::new();
    for item in items {
        dates.insert(session_date(item)?);
    }
    let days = dates.len();
    if days == sizes.len() {
        return Ok(format!("{parts} on different days {ahead}"));
    }
    if days == 1 {
        Ok(format!("{parts} on the same day {ahead}"))
    } else {
        Ok(format!("{parts} over {days} days {ahead}"))
    }
}

/// The next quarter hour from `minute`, with no morning floor. `hours/geometry.py` stays with
/// another slice, so its rounding is repeated here.
pub fn today_from_words(minute: i64) -> String {
    let step = i128::from(SLOT_MIN);
    let minute = i128::from(minute);
    let last = i128::from(DAY_END_MIN - SLOT_MIN);
    let slot = (-((-minute).div_euclid(step))) * step;
    let slot = slot.max(0);
    if slot > last {
        return String::new();
    }
    let Ok(slot) = i64::try_from(slot) else {
        return String::new();
    };
    format!("Today from {} onward.", clock_text(slot))
}

fn is_word(ch: char) -> bool {
    ch.is_alphanumeric() || ch == '_'
}

/// Only a time's own AM/PM: a title such as "PM review" keeps its plain space.
pub fn unbroken_time(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut index = 0;
    while index < chars.len() {
        if let Some(marker) = am_pm_marker(&chars, index) {
            out.push('\u{00a0}');
            out.push_str(marker);
            index += 1 + marker.len();
            continue;
        }
        out.push(chars[index]);
        index += 1;
    }
    out
}

fn am_pm_marker(chars: &[char], index: usize) -> Option<&'static str> {
    if chars.get(index) != Some(&' ') || index == 0 || !chars[index - 1].is_ascii_digit() {
        return None;
    }
    let marker = match (chars.get(index + 1), chars.get(index + 2)) {
        (Some('A'), Some('M')) => "AM",
        (Some('P'), Some('M')) => "PM",
        _ => return None,
    };
    if chars.get(index + 3).is_some_and(|ch| is_word(*ch)) {
        return None;
    }
    Some(marker)
}

/// Only zero is nothing. A negative count is still a count, as Python's `if not moved` treats it.
pub fn late_summary(moved: i64) -> String {
    if moved == 0 {
        return "Nothing needs to move.".to_string();
    }
    let noun = if moved == 1 { "task" } else { "tasks" };
    let verb = if moved == 1 { "moves" } else { "move" };
    format!("{moved} {noun} {verb}")
}

fn present(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(_) => true,
    }
}

fn time_text(value: &Value) -> EngineResult<&str> {
    value
        .as_str()
        .ok_or_else(|| type_error(format!("expected HH:MM, got {}", py_repr_of(value))))
}

fn duration_minutes(block: &Map<String, Value>) -> EngineResult<i64> {
    match block.get("duration_min") {
        Some(value) if truthy(Some(value)) => py_int(value),
        _ => Ok(0),
    }
}

fn checked_end(start: i64, duration: i64) -> EngineResult<i64> {
    start
        .checked_add(duration)
        .ok_or_else(|| EngineError::overflow("Python int too large to convert to C long"))
}

pub fn late_move(
    move_value: &Value,
    block: &Value,
    title: &str,
    week_start: &str,
) -> EngineResult<String> {
    let move_map = as_dict(move_value)?;
    let block_map = as_dict(block)?;
    let was = move_map.get("from_start");
    let now = move_map.get("to_start");
    let duration = duration_minutes(block_map)?;
    let old_day = move_map.get("from_day");
    let new_day = move_map.get("to_day");
    if truthy(was) && truthy(now) && present(old_day) && present(new_day) {
        let was_text = time_text(was.expect("from_start is set"))?;
        let now_text = time_text(now.expect("to_start is set"))?;
        let old_index = py_int(old_day.expect("from_day is set"))?;
        let new_index = py_int(new_day.expect("to_day is set"))?;
        let was_start = hhmm_to_minutes(was_text)?;
        let now_start = hhmm_to_minutes(now_text)?;
        let old = range_label(was_start, checked_end(was_start, duration)?);
        let new = range_label(now_start, checked_end(now_start, duration)?);
        let was_day = short_day_name(week_start, old_index)?;
        let new_name = short_day_name(week_start, new_index)?;
        return Ok(unbroken_time(&format!(
            "{title}: {was_day} {old} \u{2192} {new_name} {new}"
        )));
    }
    if truthy(now) && truthy(was) {
        let was_text = time_text(was.expect("from_start is set"))?;
        let now_text = time_text(now.expect("to_start is set"))?;
        return Ok(unbroken_time(&format!(
            "{title}: from {} to {}",
            hhmm_text(was_text)?,
            hhmm_text(now_text)?
        )));
    }
    if truthy(now) && present(new_day) {
        let now_text = time_text(now.expect("to_start is set"))?;
        let new_index = py_int(new_day.expect("to_day is set"))?;
        return Ok(unbroken_time(&format!(
            "{title}, placed {} {}",
            short_day_name(week_start, new_index)?,
            hhmm_text(now_text)?
        )));
    }
    if truthy(now) {
        let now_text = time_text(now.expect("to_start is set"))?;
        return Ok(unbroken_time(&format!(
            "{title}: placed at {}",
            hhmm_text(now_text)?
        )));
    }
    if truthy(was) {
        let was_text = time_text(was.expect("from_start is set"))?;
        return Ok(unbroken_time(&format!(
            "{title}: moves off {} and isn't placed",
            hhmm_text(was_text)?
        )));
    }
    Ok(format!("{title}: not placed"))
}
