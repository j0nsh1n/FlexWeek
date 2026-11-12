//! A repeating block (School, Setup's activities) changed by what the student meant: from a date on,
//! these fields and these days, or stopped. A change names only what it changes, so a week's own
//! changes are never mistaken for the repeat, and a later week that changed something itself keeps
//! that change when the repeat changes from an earlier week (a three-way merge: the repeat before,
//! the repeat after, and the week's copy).
//!
//! Weeks still start on Monday and the store keeps one copy of each repeat per saved week, so a
//! change from a date applies from that date's Monday. The intent names the date so a store that
//! keeps per-date exceptions can take the same writes.

use chrono::{Datelike, NaiveDate};
use serde_json::{Map, Value, json};

use crate::desk::calendar::{DAY_FULL, SETUP_SCHOOL_ID};
use crate::desk::grid::is_setup_block;
use crate::desk::pydate::from_iso;
use crate::error::EngineResult;
use crate::time::{hhmm_to_minutes, is_calendar_date, monday_of};
use crate::validate::time_block;

/// The fields a change may set. Everything else a repeat holds stays as it was made.
pub const PATCH_FIELDS: [&str; 4] = ["title", "category", "start", "duration_min"];
/// Fields that say which block and when, never compared or patched as a value.
const SHAPE_FIELDS: [&str; 3] = ["id", "days", "missed_days"];
const INTENT_FIELDS: [&str; 7] = [
    "id",
    "scope",
    "from_date",
    "set",
    "add_days",
    "remove_days",
    "stop",
];
const MONTHS_SHORT: [&str; 12] = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
const MAX_KEPT_SAID: usize = 3;

pub const RULE: &str = "A change to a repeating block names School or a Setup activity, a from_date \
written YYYY-MM-DD, and only title, category, start and duration_min to set";
pub const NOTHING_LEFT: &str =
    "That change leaves no day, so nothing changed. Use stop to take it off the calendar.";
pub const NEW_NEEDS_ALL: &str =
    "A new repeating block needs a title, a start, a length and at least one day";

/// One change to a repeat. `scope` is "from" in this version: the change holds from `from_date` on.
#[derive(Clone, Debug, PartialEq)]
pub struct Intent {
    pub id: String,
    pub from_date: String,
    pub set: Map<String, Value>,
    pub add_days: Vec<i64>,
    pub remove_days: Vec<i64>,
    pub stop: bool,
}

impl Intent {
    /// The Monday this change holds from: weeks still start on Monday.
    pub fn from_week(&self) -> EngineResult<String> {
        monday_of(&self.from_date)
    }

    pub fn to_value(&self) -> Value {
        json!({
            "id": self.id,
            "scope": "from",
            "from_date": self.from_date,
            "set": self.set,
            "add_days": self.add_days,
            "remove_days": self.remove_days,
            "stop": self.stop,
        })
    }
}

fn day_list(value: Option<&Value>) -> Result<Vec<i64>, String> {
    let Some(value) = value else {
        return Ok(Vec::new());
    };
    let items = value.as_array().ok_or_else(|| RULE.to_string())?;
    let mut days = Vec::with_capacity(items.len());
    for item in items {
        match item.as_i64() {
            Some(day) if (0..7).contains(&day) && !days.contains(&day) => days.push(day),
            _ => return Err(RULE.into()),
        }
    }
    days.sort_unstable();
    Ok(days)
}

/// A change as a client sent it, or the sentence saying why it is not one.
pub fn parse_intent(value: &Value) -> Result<Intent, String> {
    let map = value.as_object().ok_or_else(|| RULE.to_string())?;
    if map.keys().any(|key| !INTENT_FIELDS.contains(&key.as_str())) {
        return Err(RULE.into());
    }
    let id = map
        .get("id")
        .and_then(Value::as_str)
        .filter(|id| !id.is_empty() && id.chars().count() <= 80)
        .ok_or_else(|| RULE.to_string())?;
    if !is_setup_block(&json!({"id": id})).map_err(|err| err.message)? {
        return Err(RULE.into());
    }
    if map.get("scope").and_then(Value::as_str) != Some("from") {
        return Err(RULE.into());
    }
    let from_date = map
        .get("from_date")
        .and_then(Value::as_str)
        .filter(|date| is_calendar_date(date))
        .ok_or_else(|| RULE.to_string())?;
    let set = match map.get("set") {
        None | Some(Value::Null) => Map::new(),
        Some(Value::Object(set)) => set.clone(),
        Some(_) => return Err(RULE.into()),
    };
    if set.keys().any(|key| !PATCH_FIELDS.contains(&key.as_str())) {
        return Err(RULE.into());
    }
    let stop = match map.get("stop") {
        None | Some(Value::Null) => false,
        Some(Value::Bool(stop)) => *stop,
        Some(_) => return Err(RULE.into()),
    };
    let add_days = day_list(map.get("add_days"))?;
    let remove_days = day_list(map.get("remove_days"))?;
    if add_days.iter().any(|day| remove_days.contains(day)) {
        return Err(RULE.into());
    }
    if stop && (!set.is_empty() || !add_days.is_empty() || !remove_days.is_empty()) {
        return Err(RULE.into());
    }
    Ok(Intent {
        id: id.to_string(),
        from_date: from_date.to_string(),
        set,
        add_days,
        remove_days,
        stop,
    })
}

pub fn parse_intents(value: &Value) -> Result<Vec<Intent>, String> {
    let items = value.as_array().ok_or_else(|| RULE.to_string())?;
    let intents = items
        .iter()
        .map(parse_intent)
        .collect::<Result<Vec<_>, _>>()?;
    for (at, intent) in intents.iter().enumerate() {
        if intents[..at].iter().any(|seen| seen.id == intent.id) {
            return Err(RULE.into());
        }
    }
    Ok(intents)
}

pub fn days_of(block: &Value) -> Vec<i64> {
    let mut days: Vec<i64> = block
        .get("days")
        .and_then(Value::as_array)
        .map(|days| days.iter().filter_map(Value::as_i64).collect())
        .unwrap_or_default();
    days.sort_unstable();
    days.dedup();
    days
}

fn missed_of(block: &Value) -> Vec<i64> {
    block
        .get("missed_days")
        .and_then(Value::as_array)
        .map(|days| days.iter().filter_map(Value::as_i64).collect())
        .unwrap_or_default()
}

fn id_of(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str)
}

/// The repeat after `intent`, from the version standing at its date (None when none stands there).
/// None when the change stops it. A new repeat must name everything it needs.
pub fn patched(base: Option<&Value>, intent: &Intent) -> Result<Option<Value>, String> {
    if intent.stop {
        return Ok(None);
    }
    let mut body = match base {
        Some(base) => base.clone(),
        None => {
            if PATCH_FIELDS
                .iter()
                .any(|field| *field != "category" && !intent.set.contains_key(*field))
                || intent.add_days.is_empty()
            {
                return Err(NEW_NEEDS_ALL.into());
            }
            json!({"id": intent.id, "kind": "locked"})
        }
    };
    let Some(fields) = body.as_object_mut() else {
        return Err(RULE.into());
    };
    fields.shift_remove("missed_days");
    for (key, value) in &intent.set {
        fields.insert(key.clone(), value.clone());
    }
    let mut days: Vec<i64> = base.map(days_of).unwrap_or_default();
    days.retain(|day| !intent.remove_days.contains(day));
    for day in &intent.add_days {
        if !days.contains(day) {
            days.push(*day);
        }
    }
    days.sort_unstable();
    if days.is_empty() {
        return Err(NOTHING_LEFT.into());
    }
    fields.insert("days".into(), json!(days));
    let checked = time_block(&body)?;
    if checked.kind != "locked" || checked.start.is_none() {
        return Err(RULE.into());
    }
    Ok(Some(body))
}

/// `held` after the repeat under it changed from `old` to `new`. A field or a day it shares with `old`
/// follows `new`; one it changed itself stays. Missed days are the week's own and stay while still
/// days of it; a block missed on every day (how "this week only" takes one out) stays missed on every
/// day. When nothing would be left, it is missed on every day of `new`, so the week keeps showing
/// nothing rather than the repeat coming back.
pub fn three_way(old: &Value, new: &Value, held: &Value) -> Value {
    let mut out = held.clone();
    let Some(fields) = out.as_object_mut() else {
        return out;
    };
    let mut keys: Vec<String> = Vec::new();
    for source in [old, new, held] {
        for key in source.as_object().into_iter().flat_map(|map| map.keys()) {
            if !SHAPE_FIELDS.contains(&key.as_str()) && !keys.contains(key) {
                keys.push(key.clone());
            }
        }
    }
    for key in keys {
        if held.get(&key) != old.get(&key) {
            continue;
        }
        match new.get(&key) {
            Some(value) => {
                fields.insert(key, value.clone());
            }
            None => {
                fields.shift_remove(&key);
            }
        }
    }
    let (old_days, new_days, held_days) = (days_of(old), days_of(new), days_of(held));
    let days: Vec<i64> = (0..7)
        .filter(|day| {
            let in_held = held_days.contains(day);
            if in_held == old_days.contains(day) {
                new_days.contains(day)
            } else {
                in_held
            }
        })
        .collect();
    let missed = missed_of(held);
    let all_missed = !held_days.is_empty() && held_days.iter().all(|day| missed.contains(day));
    let (days, missed): (Vec<i64>, Vec<i64>) = if days.is_empty() {
        (new_days.clone(), new_days)
    } else if all_missed {
        (days.clone(), days)
    } else {
        let kept = missed
            .into_iter()
            .filter(|day| days.contains(day))
            .collect();
        (days, kept)
    };
    fields.insert("days".into(), json!(days));
    if missed.is_empty() {
        if fields.contains_key("missed_days") {
            fields.insert("missed_days".into(), json!([]));
        }
    } else {
        fields.insert("missed_days".into(), json!(missed));
    }
    out
}

/// A later version of a repeat after the version before it changed from `old` to `new`: a stop stays
/// a stop, and a version made after a stop is a new start that owes the earlier one nothing.
pub fn restated_version(
    old: Option<&Value>,
    new: Option<&Value>,
    held: Option<&Value>,
) -> Option<Value> {
    let held = held?;
    match (old, new) {
        (Some(old), Some(new)) => {
            let merged = three_way(old, new, held);
            if days_of(&merged).is_empty() || !missed_of(&merged).is_empty() {
                Some(held.clone())
            } else {
                Some(merged)
            }
        }
        _ => Some(held.clone()),
    }
}

/// The week's copy of a repeat after the repeat for that week changed from `old` to `new`. None takes
/// it out of the week (the repeat stopped). A copy of a repeat that did not stand then is the week's
/// own and stays.
pub fn restated_copy(old: Option<&Value>, new: Option<&Value>, copy: &Value) -> Option<Value> {
    match (old, new) {
        (Some(_), None) => None,
        (Some(old), Some(new)) => Some(three_way(old, new, copy)),
        (None, _) => Some(copy.clone()),
    }
}

/// The change a School hours or Setup form makes: from the repeat standing in the open week to what
/// the form now says. Only what differs is sent; None when nothing does.
pub fn edit_intent(
    id: &str,
    from_date: &str,
    repeat: Option<&Value>,
    edited: Option<&Value>,
) -> Option<Intent> {
    let blank = || Intent {
        id: id.to_string(),
        from_date: from_date.to_string(),
        set: Map::new(),
        add_days: Vec::new(),
        remove_days: Vec::new(),
        stop: false,
    };
    let Some(edited) = edited else {
        return repeat.map(|_| Intent {
            stop: true,
            ..blank()
        });
    };
    let mut intent = blank();
    let before_days = repeat.map(days_of).unwrap_or_default();
    let after_days = days_of(edited);
    for field in PATCH_FIELDS {
        // A form that does not show a field leaves it as the repeat has it.
        let Some(value) = edited.get(field).filter(|value| !value.is_null()) else {
            continue;
        };
        if repeat.and_then(|repeat| repeat.get(field)) != Some(value) {
            intent.set.insert(field.into(), value.clone());
        }
    }
    intent.add_days = after_days
        .iter()
        .copied()
        .filter(|day| !before_days.contains(day))
        .collect();
    intent.remove_days = before_days
        .iter()
        .copied()
        .filter(|day| !after_days.contains(day))
        .collect();
    let empty =
        intent.set.is_empty() && intent.add_days.is_empty() && intent.remove_days.is_empty();
    (!empty).then_some(intent)
}

/// What a week shows after `intents`, applied as the store applies them to a saved week, with the
/// repeats as they stand in it afterwards. `blocks` is the week as shown (repeats merged in) and
/// `repeats` the repeats standing in it before; the client calls this for the week it has open so
/// its Undo step holds the change, and the store's own pass over that week then changes nothing.
pub fn apply_to_week(
    blocks: &[Value],
    repeats: &[Value],
    intents: &[Intent],
) -> Result<(Vec<Value>, Vec<Value>), String> {
    let mut blocks = blocks.to_vec();
    let mut repeats = repeats.to_vec();
    for intent in intents {
        let at = repeats
            .iter()
            .position(|item| id_of(item) == Some(&intent.id));
        let old = at.map(|at| repeats[at].clone());
        let new = patched(old.as_ref(), intent)?;
        if new == old {
            continue;
        }
        match (at, &new) {
            (Some(at), Some(new)) => repeats[at] = new.clone(),
            (Some(at), None) => {
                repeats.remove(at);
            }
            (None, Some(new)) => repeats.push(new.clone()),
            (None, None) => {}
        }
        let held = blocks
            .iter()
            .position(|block| id_of(block) == Some(&intent.id));
        match (held, old.as_ref(), new.as_ref()) {
            (Some(at), _, _) => match restated_copy(old.as_ref(), new.as_ref(), &blocks[at]) {
                Some(copy) => blocks[at] = copy,
                None => {
                    blocks.remove(at);
                }
            },
            (None, None, Some(new)) => blocks.push(new.clone()),
            _ => {}
        }
    }
    Ok((blocks, repeats))
}

/// A minute of the day on the student's clock: "07:30", or "7:30 AM".
pub fn clock(minute: i64, h24: bool) -> String {
    let (hours, minutes) = (minute.div_euclid(60), minute.rem_euclid(60));
    if h24 {
        return format!("{hours:02}:{minutes:02}");
    }
    let half = if hours.rem_euclid(24) < 12 {
        "AM"
    } else {
        "PM"
    };
    let shown = match hours.rem_euclid(12) {
        0 => 12,
        other => other,
    };
    format!("{shown}:{minutes:02} {half}")
}

fn span_words(block: &Value, h24: bool) -> Option<String> {
    let start = hhmm_to_minutes(block.get("start")?.as_str()?).ok()?;
    let length = block.get("duration_min")?.as_i64()?;
    Some(format!(
        "{}–{}",
        clock(start, h24),
        clock(start + length, h24)
    ))
}

/// "Monday", "Monday and Friday", "Monday, Wednesday and Friday".
fn and_list(names: &[&str]) -> String {
    match names {
        [] => String::new(),
        [one] => (*one).to_string(),
        [rest @ .., last] => format!("{} and {last}", rest.join(", ")),
    }
}

fn days_words(days: &[i64]) -> String {
    let names: Vec<&str> = days
        .iter()
        .filter_map(|day| DAY_FULL.get(usize::try_from(*day).ok()?).copied())
        .collect();
    and_list(&names)
}

fn title_of(block: &Value) -> &str {
    block.get("title").and_then(Value::as_str).unwrap_or("")
}

/// What a week's copy of a repeat does differently from the repeat, in everyday words, for the
/// School hours line ("no School on Wednesday") and for the notice after a change. `week` is the
/// whole week, so a day moved to its own block reads as moved rather than as missing.
pub fn own_changes(copy: &Value, repeat: &Value, week: &[Value], h24: bool) -> Vec<String> {
    let name = title_of(repeat);
    let (repeat_days, copy_days, missed) = (days_of(repeat), days_of(copy), missed_of(copy));
    if !copy_days.is_empty() && copy_days.iter().all(|day| missed.contains(day)) {
        return vec![format!("no {name} that week")];
    }
    let showing: Vec<i64> = copy_days
        .iter()
        .copied()
        .filter(|day| !missed.contains(day))
        .collect();
    let mut said = Vec::new();
    let mut moved = Vec::new();
    let mut skipped = Vec::new();
    for day in repeat_days
        .iter()
        .copied()
        .filter(|day| !showing.contains(day))
    {
        // A day split off by a drag or a one-day edit is a block of its own with the same name.
        let split = week.iter().find(|block| {
            id_of(block) != id_of(copy)
                && !is_setup_block(block).unwrap_or(true)
                && title_of(block) == title_of(copy)
                && days_of(block) == vec![day]
                && !missed_of(block).contains(&day)
        });
        match split.and_then(|block| span_words(block, h24)) {
            Some(span) => moved.push(format!("{name} at {span} on {}", DAY_FULL[day as usize])),
            None => skipped.push(day),
        }
    }
    if !skipped.is_empty() {
        said.push(format!("no {name} on {}", days_words(&skipped)));
    }
    said.extend(moved);
    let extra: Vec<i64> = showing
        .iter()
        .copied()
        .filter(|day| !repeat_days.contains(day))
        .collect();
    if !extra.is_empty() {
        said.push(format!("{name} on {} too", days_words(&extra)));
    }
    if title_of(copy) != name {
        said.push(format!("called {}", title_of(copy)));
    }
    let moved = copy.get("start") != repeat.get("start")
        || copy.get("duration_min") != repeat.get("duration_min");
    if moved && let Some(span) = span_words(copy, h24) {
        said.push(format!("{name} at {span}"));
    }
    said
}

/// "This week: no School on Wednesday." for the School hours and Setup forms; None when the open
/// week shows the repeat as it is.
pub fn this_week_line(week: &[Value], repeats: &[Value], h24: bool) -> Option<String> {
    let mut said = Vec::new();
    for repeat in repeats {
        if let Some(copy) = week.iter().find(|block| id_of(block) == id_of(repeat)) {
            said.extend(own_changes(copy, repeat, week, h24));
        }
    }
    (!said.is_empty()).then(|| format!("This week: {}.", said.join("; ")))
}

/// A later week that kept its own change when a repeat changed from an earlier week.
#[derive(Clone, Debug, PartialEq)]
pub struct Kept {
    pub week_start: String,
    pub id: String,
    pub changes: Vec<String>,
}

impl Kept {
    pub fn to_value(&self) -> Value {
        json!({"week_start": self.week_start, "id": self.id, "changes": self.changes})
    }
}

fn short_date(day: NaiveDate, reference: NaiveDate) -> String {
    let text = format!("{} {}", day.day(), MONTHS_SHORT[day.month0() as usize]);
    if day.year() == reference.year() {
        text
    } else {
        format!("{text} {}", day.year())
    }
}

/// The notice after a change from `from_week` on: what changed, then each later week that kept a
/// change of its own and what it is. None when no later week kept one, so the client says its usual
/// words.
pub fn kept_notice(
    titles: &[String],
    from_week: &str,
    kept: &[Kept],
) -> EngineResult<Option<String>> {
    if kept.is_empty() {
        return Ok(None);
    }
    let reference = from_iso(from_week)?;
    let mut weeks: Vec<(String, Vec<String>)> = Vec::new();
    for entry in kept {
        match weeks.iter_mut().find(|(week, _)| *week == entry.week_start) {
            Some((_, changes)) => changes.extend(entry.changes.iter().cloned()),
            None => weeks.push((entry.week_start.clone(), entry.changes.clone())),
        }
    }
    weeks.sort_by(|a, b| a.0.cmp(&b.0));
    let names: Vec<&str> = titles.iter().map(String::as_str).collect();
    let what = if names.is_empty() {
        "Your week".to_string()
    } else {
        and_list(&names)
    };
    let mut text = format!("{what} changed from this week on.");
    for (week, changes) in weeks.iter().take(MAX_KEPT_SAID) {
        let date = short_date(from_iso(week)?, reference);
        let noun = if changes.len() == 1 {
            "change"
        } else {
            "changes"
        };
        text.push_str(&format!(
            " The week of {date} keeps its own {noun}: {}.",
            changes.join("; ")
        ));
    }
    let more = weeks.len().saturating_sub(MAX_KEPT_SAID);
    if more == 1 {
        text.push_str(" 1 more week keeps its own change too.");
    } else if more > 1 {
        text.push_str(&format!(" {more} more weeks keep their own changes too."));
    }
    Ok(Some(text))
}

/// What a drag, a resize or Move to day... of one day of a repeating block says: that day changed,
/// and where the whole series is changed. None for a block that does not repeat. `school_hours` is
/// whether the look offers School hours; otherwise every repeat is changed in Setup.
pub fn one_day_note(block: &Value, day: i64, school_hours: bool) -> EngineResult<Option<String>> {
    if !is_setup_block(block)? {
        return Ok(None);
    }
    let Some(name) = usize::try_from(day).ok().and_then(|day| DAY_FULL.get(day)) else {
        return Ok(None);
    };
    let place = if school_hours && id_of(block) == Some(SETUP_SCHOOL_ID) {
        "open School hours"
    } else {
        "run setup again from Settings"
    };
    Ok(Some(format!(
        "Only this {name} changed. To change every week, {place}."
    )))
}
