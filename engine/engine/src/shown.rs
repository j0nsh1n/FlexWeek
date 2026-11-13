//! A week on screen that starts on another day than Monday. Stored weeks stay keyed by their Monday
//! and a block's `days` count from that Monday, so a shown week from Wednesday covers the Wednesday to
//! Sunday of its Monday's week (the first) and the Monday and Tuesday of the next (the second). These
//! functions show the two stored weeks as one and split a shown week back, so the server does both and
//! a client holds one week whatever day it starts on.
//!
//! The rule that keeps work from being lost or doubled across the seam: a block with a time happens on
//! each of its days, so each shown day goes back to the one stored week it belongs to, and the days the
//! shown week cannot see keep the block as stored. A block with no time yet (a session waiting to be
//! planned) happens once, and its `days` are the days it may go on. It lives in one stored week; once
//! it is shown, the shown week decides it, so a session placed on screen does not also stay waiting on
//! the days the screen could not see.

use std::collections::HashSet;

use chrono::{Datelike, Duration};
use serde_json::{Map, Value};

use crate::desk::calendar::{DAY_FULL, DAYS};
use crate::desk::pydate::{from_iso, iso_text};
use crate::error::{EngineError, EngineResult};
use crate::time::{is_calendar_date, monday_of};

/// Day fields read against the week's first day; everything else is the block's content.
const DAY_FIELDS: [&str; 3] = ["days", "missed_days", "completed_day"];
const MAX_ID: usize = 80;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Part {
    First,
    Second,
}

/// The stored weeks a shown week starting on `shown_start` covers: the Monday of its own week, the
/// next Monday, and how many days into the first the shown week starts. None for a Monday, which is
/// one stored week.
pub fn shown_parts(shown_start: &str) -> EngineResult<Option<(String, String, i64)>> {
    if !is_calendar_date(shown_start) {
        return Err(EngineError::value(
            "week_start must be a date written YYYY-MM-DD",
        ));
    }
    let day = from_iso(shown_start)?;
    let offset = i64::from(day.weekday().num_days_from_monday());
    if offset == 0 {
        return Ok(None);
    }
    let first = monday_of(shown_start)?;
    let second = from_iso(&first)? + Duration::days(7);
    Ok(Some((first, iso_text(second), offset)))
}

/// The stored weeks a shown week covers, first first: its own Monday alone for a Monday, else two.
pub fn stored_weeks(shown_start: &str) -> EngineResult<Vec<String>> {
    Ok(match shown_parts(shown_start)? {
        Some((first, second, _)) => vec![first, second],
        None => vec![shown_start.to_string()],
    })
}

/// The weekday (0 Monday to 6 Sunday) of each day of the week on screen from `week_start`.
fn weekdays(week_start: &str) -> EngineResult<[usize; 7]> {
    let first = from_iso(week_start)?.weekday().num_days_from_monday() as usize;
    Ok(std::array::from_fn(|day| (first + day) % 7))
}

/// The days of the week on screen that have a column: all seven, or, with the weekend hidden, every
/// day but Saturday and Sunday wherever they fall.
pub fn shown_columns(week_start: &str, weekends: bool) -> EngineResult<Vec<i64>> {
    Ok(weekdays(week_start)?
        .iter()
        .enumerate()
        .filter(|(_, weekday)| weekends || **weekday < 5)
        .map(|(day, _)| day as i64)
        .collect())
}

/// The names of the days of the week on screen, from their dates: "Wed" or "Wednesday" first for a
/// week from Wednesday.
pub fn day_names(week_start: &str, full: bool) -> EngineResult<Vec<&'static str>> {
    let names = if full { DAY_FULL } else { DAYS };
    Ok(weekdays(week_start)?
        .iter()
        .map(|weekday| names[*weekday])
        .collect())
}

/// Weekdays (0 Monday) as days of the week on screen from `week_start`, in order.
pub fn weekdays_on_shown_week(week_start: &str, of_week: &[i64]) -> EngineResult<Vec<i64>> {
    let first = weekdays(week_start)?[0] as i64;
    let mut days: Vec<i64> = of_week
        .iter()
        .map(|weekday| (weekday - first).rem_euclid(7))
        .collect();
    days.sort_unstable();
    Ok(days)
}

/// A weekday's occupancy (0 Monday) for each day of the week on screen from `week_start`.
pub fn occupancy_on_shown_week(week_start: &str, occupancy: &[u128]) -> EngineResult<Vec<u128>> {
    let days = weekdays(week_start)?;
    Ok(days
        .iter()
        .map(|weekday| occupancy.get(*weekday).copied().unwrap_or(0))
        .collect())
}

/// Work and study windows, kept by weekday, with their `days` as days of the week on screen.
pub fn windows_on_shown_week(week_start: &str, windows: &[Value]) -> EngineResult<Vec<Value>> {
    windows
        .iter()
        .map(|window| {
            let mut window = window.clone();
            if let Some(days) = window.get("days").and_then(Value::as_array) {
                let of_week: Vec<i64> = days.iter().filter_map(Value::as_i64).collect();
                window["days"] = Value::from(weekdays_on_shown_week(week_start, &of_week)?);
            }
            Ok(window)
        })
        .collect()
}

/// Planner settings for a week on screen from `week_start`: they name the weekday its day 0 falls
/// on, so Saturday and Sunday are found wherever they are. No settings stay none.
pub fn rules_on_shown_week(week_start: &str, rules: &Value) -> EngineResult<Value> {
    let first = weekdays(week_start)?[0];
    let mut rules = rules.clone();
    if let Some(fields) = rules.as_object_mut() {
        fields.insert("first_weekday".into(), Value::from(first));
    }
    Ok(rules)
}

/// `block` with its days, missed days and done day moved `by` days round the week.
fn turned(block: &Value, by: i64) -> Value {
    let turn = |day: i64| (day + by).rem_euclid(7);
    let days = day_list(block, "days").into_iter().map(turn).collect();
    let missed = day_list(block, "missed_days")
        .into_iter()
        .map(turn)
        .collect();
    with_days(block, days, missed, completed_day(block).map(turn))
}

/// How far a week on screen from `week_start` is turned from a Monday week: its day 0's weekday.
fn turn_of(week_start: &str) -> EngineResult<i64> {
    Ok(weekdays(week_start)?[0] as i64)
}

/// Repeat changes applied to the week on screen from `week_start`, as `repeats::apply_to_week` applies
/// them to a Monday week. Repeats keep their days by weekday, so the week's blocks are read by weekday
/// for the change and given back by day of the week on screen.
pub fn apply_repeats_to_shown_week(
    week_start: &str,
    blocks: &[Value],
    repeats: &[Value],
    intents: &[crate::repeats::Intent],
) -> Result<(Vec<Value>, Vec<Value>), String> {
    let by = turn_of(week_start).map_err(|error| error.message)?;
    if by == 0 {
        return crate::repeats::apply_to_week(blocks, repeats, intents);
    }
    let by_weekday: Vec<Value> = blocks.iter().map(|block| turned(block, by)).collect();
    let (week, repeats) = crate::repeats::apply_to_week(&by_weekday, repeats, intents)?;
    Ok((
        week.iter().map(|block| turned(block, -by)).collect(),
        repeats,
    ))
}

/// The blocks of the week on screen from `week_start` with their days as weekdays (0 Monday), as a
/// routine keeps them.
pub fn blocks_by_weekday(week_start: &str, blocks: &[Value]) -> EngineResult<Vec<Value>> {
    let by = turn_of(week_start)?;
    if by == 0 {
        return Ok(blocks.to_vec());
    }
    Ok(blocks.iter().map(|block| turned(block, by)).collect())
}

/// A routine, which keeps its days as weekdays, with its days as days of the week on screen from
/// `week_start`, to copy into that week.
pub fn routine_on_shown_week(week_start: &str, routine: &Value) -> EngineResult<Value> {
    let by = turn_of(week_start)?;
    let mut routine = routine.clone();
    if by == 0 {
        return Ok(routine);
    }
    if let Some(templates) = routine.get_mut("blocks").and_then(Value::as_array_mut) {
        for template in templates.iter_mut() {
            *template = turned(template, -by);
        }
    }
    Ok(routine)
}

/// `repeats::this_week_line` for the week on screen from `week_start`, its days named as weekdays.
pub fn this_week_line_on_shown_week(
    week_start: &str,
    blocks: &[Value],
    repeats: &[Value],
    h24: bool,
) -> EngineResult<Option<String>> {
    let by = turn_of(week_start)?;
    let by_weekday: Vec<Value> = blocks.iter().map(|block| turned(block, by)).collect();
    Ok(crate::repeats::this_week_line(&by_weekday, repeats, h24))
}

/// `repeats::one_day_note` for day `day` of the week on screen from `week_start`.
pub fn one_day_note_on_shown_week(
    week_start: &str,
    block: &Value,
    day: i64,
    school_hours: bool,
) -> EngineResult<Option<String>> {
    let weekday = (day + turn_of(week_start)?).rem_euclid(7);
    crate::repeats::one_day_note(block, weekday, school_hours)
}

fn offset_of(shown_start: &str) -> EngineResult<i64> {
    Ok(shown_parts(shown_start)?.map_or(0, |(_, _, offset)| offset))
}

fn id_of(block: &Value) -> &str {
    block.get("id").and_then(Value::as_str).unwrap_or_default()
}

fn day_list(block: &Value, key: &str) -> Vec<i64> {
    block
        .get(key)
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(Value::as_i64).collect())
        .unwrap_or_default()
}

fn placed(block: &Value) -> bool {
    block
        .get("start")
        .is_some_and(|start| start.as_str().is_some_and(|text| !text.is_empty()))
}

/// The block without its day fields and id, to tell a changed block from the same one on other days.
fn content(block: &Value) -> Map<String, Value> {
    let mut fields = block.as_object().cloned().unwrap_or_default();
    for key in DAY_FIELDS {
        fields.shift_remove(key);
    }
    fields.shift_remove("id");
    fields
}

/// Stored day of `part` to shown day, or None when the shown week does not hold it.
fn to_shown(part: Part, day: i64, offset: i64) -> Option<i64> {
    match part {
        Part::First if day >= offset => Some(day - offset),
        Part::Second if day < offset => Some(day + 7 - offset),
        _ => None,
    }
}

/// Shown day to the stored week it belongs to and its day there.
fn to_stored(day: i64, offset: i64) -> (Part, i64) {
    if day + offset < 7 {
        (Part::First, day + offset)
    } else {
        (Part::Second, day + offset - 7)
    }
}

fn sorted(mut days: Vec<i64>) -> Vec<i64> {
    days.sort_unstable();
    days.dedup();
    days
}

/// `block` with its day fields set: `days` always, `missed_days` only when any is left, and
/// `completed_day` when it has one.
fn with_days(block: &Value, days: Vec<i64>, missed: Vec<i64>, completed_day: Option<i64>) -> Value {
    let mut fields = block.as_object().cloned().unwrap_or_default();
    fields.insert("days".into(), Value::from(sorted(days)));
    if missed.is_empty() {
        fields.shift_remove("missed_days");
    } else {
        fields.insert("missed_days".into(), Value::from(sorted(missed)));
    }
    match completed_day {
        Some(day) => {
            fields.insert("completed_day".into(), Value::from(day));
        }
        None => {
            fields.shift_remove("completed_day");
        }
    }
    Value::Object(fields)
}

fn completed_day(block: &Value) -> Option<i64> {
    block.get("completed_day").and_then(Value::as_i64)
}

/// A stored block as the shown week sees it, or None when none of its days are shown.
fn shown_copy(block: &Value, part: Part, offset: i64) -> Option<Value> {
    let days: Vec<i64> = day_list(block, "days")
        .into_iter()
        .filter_map(|day| to_shown(part, day, offset))
        .collect();
    if days.is_empty() {
        return None;
    }
    let missed = day_list(block, "missed_days")
        .into_iter()
        .filter_map(|day| to_shown(part, day, offset))
        .collect();
    let done = completed_day(block).and_then(|day| to_shown(part, day, offset));
    Some(with_days(block, days, missed, done))
}

/// An id not in `taken`, made from `id` and a tag, kept within the id length limit.
fn fresh_id(id: &str, tag: &str, taken: &HashSet<String>) -> String {
    let mut attempt = 1;
    loop {
        let suffix = if attempt == 1 {
            format!("@{tag}")
        } else {
            format!("@{tag}-{attempt}")
        };
        let room = MAX_ID.saturating_sub(suffix.chars().count());
        let base: String = id.chars().take(room).collect();
        let candidate = format!("{base}{suffix}");
        if !taken.contains(&candidate) {
            return candidate;
        }
        attempt += 1;
    }
}

fn compact(date: &str) -> String {
    date.replace('-', "")
}

/// Where each stored block shows: (part, index in its stored week, shown id). Built from the stored
/// weeks alone, so the server rebuilds the same ids when the shown week comes back.
struct Layout {
    entries: Vec<(Part, usize, String)>,
    shown: Vec<Value>,
}

fn lay_out(shown_start: &str, offset: i64, first: &[Value], second: &[Value]) -> Layout {
    let mut entries = Vec::new();
    let mut shown: Vec<Value> = Vec::new();
    for (index, block) in first.iter().enumerate() {
        if let Some(copy) = shown_copy(block, Part::First, offset) {
            entries.push((Part::First, index, id_of(block).to_string()));
            shown.push(copy);
        }
    }
    let mut taken: HashSet<String> = first
        .iter()
        .chain(second.iter())
        .map(|block| id_of(block).to_string())
        .collect();
    for (index, block) in second.iter().enumerate() {
        let Some(copy) = shown_copy(block, Part::Second, offset) else {
            continue;
        };
        let id = id_of(block);
        let Some(at) = shown.iter().position(|held| id_of(held) == id) else {
            entries.push((Part::Second, index, id.to_string()));
            shown.push(copy);
            continue;
        };
        // One block with a time on both sides of the seam shows once, with the days of both.
        if placed(block) && placed(&shown[at]) && content(block) == content(&shown[at]) {
            let held = &shown[at];
            let days = [day_list(held, "days"), day_list(&copy, "days")].concat();
            let missed = [
                day_list(held, "missed_days"),
                day_list(&copy, "missed_days"),
            ]
            .concat();
            let done = completed_day(held).or(completed_day(&copy));
            shown[at] = with_days(held, days, missed, done);
            entries.push((Part::Second, index, id.to_string()));
            continue;
        }
        let renamed = fresh_id(id, &compact(shown_start), &taken);
        taken.insert(renamed.clone());
        let mut copy = copy;
        copy["id"] = Value::from(renamed.clone());
        entries.push((Part::Second, index, renamed));
        shown.push(copy);
    }
    Layout { entries, shown }
}

/// The shown week starting on `shown_start` from its two stored weeks as the student sees them (each
/// with its standing blocks), days counted from `shown_start`.
pub fn compose_shown_week(
    shown_start: &str,
    first: &[Value],
    second: &[Value],
) -> EngineResult<Vec<Value>> {
    compose_shown_week_due(shown_start, first, second, &Map::new())
}

/// `compose_shown_week`, with the account's homework by id. A session waiting for a time lives in one
/// stored week, so it can hold only that week's days. One given every day of its week through its
/// due date shows on every day of the week on screen through that date; saved back, it keeps its own
/// week's days and is stored once.
pub fn compose_shown_week_due(
    shown_start: &str,
    first: &[Value],
    second: &[Value],
    homework: &Map<String, Value>,
) -> EngineResult<Vec<Value>> {
    let offset = offset_of(shown_start)?;
    if offset == 0 {
        return Ok(first.to_vec());
    }
    let mut shown = lay_out(shown_start, offset, first, second).shown;
    let seam = 7 - offset;
    for block in &mut shown {
        let due = block
            .get("assignment_id")
            .and_then(Value::as_str)
            .and_then(|id| homework.get(id))
            .and_then(|item| item.get("due"))
            .filter(|due| due.is_string());
        let (Some(due), false) = (due, placed(block) || done(block)) else {
            continue;
        };
        let days = sorted(day_list(block, "days"));
        let Some(first_day) = days.first() else {
            continue;
        };
        let home = if *first_day < seam { 0..seam } else { seam..7 };
        if !days.iter().all(|day| home.contains(day)) {
            continue;
        }
        let through = crate::desk::planning::session_days(shown_start, due)?;
        let in_home: Vec<i64> = through
            .iter()
            .copied()
            .filter(|day| home.contains(day))
            .collect();
        if days == in_home && through != days {
            block["days"] = Value::from(through);
        }
    }
    Ok(shown)
}

fn done(block: &Value) -> bool {
    block.get("completed").and_then(Value::as_bool) == Some(true)
}

/// The days of a shown block that go to each stored week, in that week's days. A block with no time
/// goes to one week only: the one it was shown from while it still has a day there, else the other.
fn parts_of(block: &Value, offset: i64, home: Option<Part>) -> [Vec<i64>; 2] {
    let mut parts: [Vec<i64>; 2] = [Vec::new(), Vec::new()];
    for day in day_list(block, "days") {
        if !(0..7).contains(&day) {
            continue;
        }
        let (part, stored) = to_stored(day, offset);
        parts[slot(part)].push(stored);
    }
    if !placed(block) {
        let keep = match home {
            Some(part) if !parts[slot(part)].is_empty() => part,
            _ if !parts[0].is_empty() => Part::First,
            _ => Part::Second,
        };
        parts[slot(other(keep))].clear();
    }
    parts
}

fn slot(part: Part) -> usize {
    match part {
        Part::First => 0,
        Part::Second => 1,
    }
}

fn other(part: Part) -> Part {
    match part {
        Part::First => Part::Second,
        Part::Second => Part::First,
    }
}

/// `field` days of a shown block that land in `part`, in that week's days.
fn landing(block: &Value, key: &str, part: Part, offset: i64) -> Vec<i64> {
    day_list(block, key)
        .into_iter()
        .filter(|day| (0..7).contains(day))
        .map(|day| to_stored(day, offset))
        .filter(|(landed, _)| *landed == part)
        .map(|(_, day)| day)
        .collect()
}

fn landing_done(block: &Value, part: Part, offset: i64) -> Option<i64> {
    let day = completed_day(block)?;
    let (landed, stored) = to_stored(day, offset);
    (landed == part).then_some(stored)
}

/// A shown block as stored in `part` on `days`, with its missed and done days that land there.
fn stored_copy(shown: &Value, id: &str, part: Part, offset: i64, days: Vec<i64>) -> Value {
    let mut copy = with_days(
        shown,
        days,
        landing(shown, "missed_days", part, offset),
        landing_done(shown, part, offset),
    );
    copy["id"] = Value::from(id);
    copy
}

/// The stored weeks after a shown week is saved: `shown` as the client sends it, `first` and `second`
/// the two stored weeks as the student sees them now (what `compose_shown_week` was given). Days the
/// shown week does not hold keep what was stored on them.
pub fn split_shown_week(
    shown_start: &str,
    shown: &[Value],
    first: &[Value],
    second: &[Value],
) -> EngineResult<(Vec<Value>, Vec<Value>)> {
    let offset = offset_of(shown_start)?;
    if offset == 0 {
        return Ok((shown.to_vec(), second.to_vec()));
    }
    let layout = lay_out(shown_start, offset, first, second);
    let stored = [first, second];
    let by_shown_id = |id: &str| shown.iter().find(|block| id_of(block) == id);
    // The part a shown block with no time was shown from: where its days stay unless it left them.
    let home_of = |id: &str| -> Option<Part> {
        layout
            .entries
            .iter()
            .find(|(_, _, shown_id)| shown_id == id)
            .map(|(part, _, _)| *part)
    };
    let mut out: [Vec<Value>; 2] = [Vec::new(), Vec::new()];
    // Shown ids whose days in a part a stored block there already took.
    let mut used: [HashSet<String>; 2] = [HashSet::new(), HashSet::new()];
    let tag = compact(shown_start);
    for part in [Part::First, Part::Second] {
        let mut taken: HashSet<String> = stored[slot(part)]
            .iter()
            .map(|block| id_of(block).to_string())
            .collect();
        for (index, block) in stored[slot(part)].iter().enumerate() {
            let Some((_, _, shown_id)) = layout
                .entries
                .iter()
                .find(|(at_part, at, _)| *at_part == part && *at == index)
            else {
                out[slot(part)].push(block.clone());
                continue;
            };
            used[slot(part)].insert(shown_id.clone());
            let hidden: Vec<i64> = day_list(block, "days")
                .into_iter()
                .filter(|day| to_shown(part, *day, offset).is_none())
                .collect();
            let hidden_missed: Vec<i64> = day_list(block, "missed_days")
                .into_iter()
                .filter(|day| to_shown(part, *day, offset).is_none())
                .collect();
            let hidden_done =
                completed_day(block).filter(|day| to_shown(part, *day, offset).is_none());
            let kept_hidden =
                || with_days(block, hidden.clone(), hidden_missed.clone(), hidden_done);
            let id = id_of(block);
            let Some(now) = by_shown_id(shown_id) else {
                // Taken off the shown week: a block with a time keeps the days it has elsewhere; one
                // waiting for a time was the shown week's to delete.
                if placed(block) && !hidden.is_empty() {
                    out[slot(part)].push(kept_hidden());
                }
                continue;
            };
            let landed = parts_of(now, offset, home_of(shown_id))[slot(part)].clone();
            if !placed(block) {
                if placed(now) {
                    if !landed.is_empty() {
                        out[slot(part)].push(stored_copy(now, id, part, offset, landed));
                    }
                } else if !landed.is_empty() {
                    let days = [hidden.clone(), landed].concat();
                    out[slot(part)].push(stored_copy(now, id, part, offset, days));
                }
                continue;
            }
            if placed(now) && content(now) == content(block) {
                if hidden.is_empty() && landed.is_empty() {
                    continue;
                }
                let mut copy =
                    stored_copy(now, id, part, offset, [hidden.clone(), landed].concat());
                let missed = [
                    hidden_missed.clone(),
                    landing(now, "missed_days", part, offset),
                ]
                .concat();
                let done = landing_done(now, part, offset).or(hidden_done);
                copy = with_days(&copy, day_list(&copy, "days"), missed, done);
                out[slot(part)].push(copy);
                continue;
            }
            // Changed on screen: the days the shown week cannot see keep the block as it was, and the
            // shown days become a block of their own unless there are no other days.
            if !hidden.is_empty() {
                out[slot(part)].push(kept_hidden());
                if !landed.is_empty() {
                    let fresh = fresh_id(id, &tag, &taken);
                    taken.insert(fresh.clone());
                    out[slot(part)].push(stored_copy(now, &fresh, part, offset, landed));
                }
            } else if !landed.is_empty() {
                out[slot(part)].push(stored_copy(now, id, part, offset, landed));
            }
        }
    }
    // Days of shown blocks no stored block took: new blocks, and blocks moved over the seam.
    for block in shown {
        let shown_id = id_of(block);
        let parts = parts_of(block, offset, home_of(shown_id));
        for part in [Part::First, Part::Second] {
            let days = parts[slot(part)].clone();
            if days.is_empty() || used[slot(part)].contains(shown_id) {
                continue;
            }
            let stored_id = layout
                .entries
                .iter()
                .find(|(_, _, id)| id == shown_id)
                .map(|(at_part, at, _)| id_of(&stored[slot(*at_part)][*at]).to_string())
                .unwrap_or_else(|| shown_id.to_string());
            let taken: HashSet<String> = out[slot(part)]
                .iter()
                .map(|held| id_of(held).to_string())
                .collect();
            let id = if taken.contains(&stored_id) {
                fresh_id(&stored_id, &tag, &taken)
            } else {
                stored_id
            };
            out[slot(part)].push(stored_copy(block, &id, part, offset, days));
        }
    }
    let [first_out, second_out] = out;
    Ok((first_out, second_out))
}

/// Changes to a repeat (School, Setup's activities) made "from this week on" in a shown week that
/// starts after its Monday. The shown days of the first stored week are already changed in the saved
/// shown week, as that week's own; the repeat itself changes from the next Monday, so the days before
/// the shown week keep it as it was. Other changes pass unchanged.
pub fn repeat_changes_from_shown_week(
    changes: &[Value],
    shown_start: &str,
) -> EngineResult<Vec<Value>> {
    let Some((_, second, _)) = shown_parts(shown_start)? else {
        return Ok(changes.to_vec());
    };
    Ok(changes
        .iter()
        .map(|change| {
            let mut change = change.clone();
            if change.get("from_date").and_then(Value::as_str) == Some(shown_start) {
                change["from_date"] = Value::from(second.clone());
            }
            change
        })
        .collect())
}
