//! The standing week: the School and activities Setup made, which every week from Setup's week on
//! has without the student copying them. Each standing block keeps the id Setup gave it (`school`,
//! `sport`, `activity-N`), the same in every week and on every device, so a week that holds a block
//! with that id holds its own version of it for that week.

use std::collections::{HashMap, HashSet};

use serde_json::{Map, Value, json};

use crate::EngineResult;
use crate::desk::grid::is_setup_block;
use crate::desk::pydate::from_iso;
use crate::repeats::days_of;
use crate::shown::family_id;

fn id_of(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str)
}

pub fn removed_on(block: &Value, day: &Value) -> bool {
    block
        .get("removed_days")
        .and_then(Value::as_array)
        .is_some_and(|days| days.contains(day))
}

pub fn keep_removed_days(fields: &mut Map<String, Value>) {
    if let Some(Value::Array(mut removed)) = fields.shift_remove("removed_days") {
        removed.retain(|day| {
            fields
                .get("days")
                .and_then(Value::as_array)
                .is_some_and(|days| days.contains(day))
        });
        if !removed.is_empty() {
            fields.insert("removed_days".into(), Value::Array(removed));
        }
    }
}

/// Keep a week's copy so the standing block cannot fill it in again.
pub fn remove_for_week(mut block: Value) -> Value {
    let missed = block.get("missed_days").and_then(Value::as_array);
    let removed: Vec<i64> = days_of(&block)
        .into_iter()
        .filter(|day| !missed.is_some_and(|missed| missed.contains(&Value::from(*day))))
        .collect();
    if !removed.is_empty() {
        block["removed_days"] = json!(removed);
    }
    block
}

/// The block as it stands in every week, without that week's day exceptions.
pub fn standing_body(block: &Value) -> Value {
    let mut body = block.clone();
    if let Some(fields) = body.as_object_mut() {
        fields.shift_remove("missed_days");
        fields.shift_remove("removed_days");
    }
    body
}

/// A week as the student sees it: its own blocks, then each standing block it has no version of. A
/// piece of School split off at a week's seam is that week's version of School.
pub fn with_standing(stored: &[Value], standing: &[Value]) -> Vec<Value> {
    let held: HashSet<&str> = stored.iter().filter_map(id_of).map(family_id).collect();
    let mut week = stored.to_vec();
    week.extend(
        standing
            .iter()
            .filter(|block| id_of(block).is_some_and(|id| !held.contains(id)))
            .cloned(),
    );
    week
}

/// A block as the week starting `week_start` (a Monday) shows it under its Until date (#118): only the
/// days up to that date, with its missed days among them. None when no day is left. A block with no
/// `until` is shown as it is. Nothing is stored cut: a week's copy keeps every day, and moving Until
/// later shows them again.
pub fn cut_at_until(block: &Value, week_start: &str) -> EngineResult<Option<Value>> {
    let Some(until) = block
        .get("until")
        .and_then(Value::as_str)
        .filter(|text| !text.is_empty())
    else {
        return Ok(Some(block.clone()));
    };
    let last = (from_iso(until)? - from_iso(week_start)?).num_days();
    let days: Vec<i64> = days_of(block)
        .into_iter()
        .filter(|day| *day <= last)
        .collect();
    if days.is_empty() {
        return Ok(None);
    }
    let mut out = block.clone();
    out["days"] = json!(days);
    if let Some(fields) = out.as_object_mut() {
        for key in ["missed_days", "removed_days"] {
            let kept: Vec<i64> = fields
                .get(key)
                .and_then(Value::as_array)
                .map(|items| {
                    items
                        .iter()
                        .filter_map(Value::as_i64)
                        .filter(|day| *day <= last)
                        .collect()
                })
                .unwrap_or_default();
            if kept.is_empty() {
                fields.shift_remove(key);
            } else {
                fields.insert(key.into(), json!(kept));
            }
        }
    }
    Ok(Some(out))
}

/// A week's copy of a repeat with the days the repeat's Until (`repeat`, as it stood for that week) cut
/// away put back. A copy saved while cut holds only the days the week showed; the student never saw the
/// others, so they are not days the week took out, and a change to the repeat (Until moved later) must
/// not read them as such.
pub fn uncut_copy(copy: &Value, repeat: Option<&Value>, week_start: &str) -> EngineResult<Value> {
    let Some(repeat) = repeat else {
        return Ok(copy.clone());
    };
    let shown = cut_at_until(repeat, week_start)?
        .map(|block| days_of(&block))
        .unwrap_or_default();
    let mut days = days_of(copy);
    let before = days.len();
    for day in days_of(repeat) {
        if !shown.contains(&day) && !days.contains(&day) {
            days.push(day);
        }
    }
    if days.len() == before {
        return Ok(copy.clone());
    }
    days.sort_unstable();
    let mut out = copy.clone();
    out["days"] = json!(days);
    Ok(out)
}

/// Whether a week's own blocks (`stored`, of the week starting `week_start`) already hold a hand-made copy
/// of the weekly time `repeat` makes: a locked block that is not a repeat, with the same name, start and
/// length on a day the repeat (cut at its Until) also has. The week would then show it twice.
pub fn twin_in_week(repeat: &Value, week_start: &str, stored: &[Value]) -> EngineResult<bool> {
    let Some(repeat) = cut_at_until(repeat, week_start)? else {
        return Ok(false);
    };
    let text = |block: &Value, key: &str| {
        block
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_default()
            .trim()
            .to_lowercase()
    };
    let days = days_of(&repeat);
    for copy in stored {
        if copy.get("kind").and_then(Value::as_str) != Some("locked")
            || crate::desk::grid::is_standing_block(copy)?
            || text(copy, "start").is_empty()
            || text(copy, "start") != text(&repeat, "start")
            || copy.get("duration_min") != repeat.get("duration_min")
            || text(copy, "title") != text(&repeat, "title")
        {
            continue;
        }
        if days_of(copy).iter().any(|day| days.contains(day)) {
            return Ok(true);
        }
    }
    Ok(false)
}

/// `with_standing` for the week starting `week_start`, each block cut at its Until date.
pub fn shown_with_standing(
    stored: &[Value],
    standing: &[Value],
    week_start: &str,
) -> EngineResult<Vec<Value>> {
    let mut week = Vec::new();
    for block in with_standing(stored, standing) {
        if let Some(shown) = cut_at_until(&block, week_start)? {
            week.push(shown);
        }
    }
    Ok(week)
}

/// An account from before the standing week: its Setup blocks are those of the newest saved week that
/// has any, standing from that week. None when no week has a Setup block.
pub fn derive_standing(
    weeks: &[(String, Vec<Value>)],
) -> EngineResult<Option<(String, Vec<Value>)>> {
    let mut newest: Option<(String, Vec<Value>)> = None;
    for (week_start, blocks) in weeks {
        if newest
            .as_ref()
            .is_some_and(|(start, _)| start >= week_start)
        {
            continue;
        }
        let mut setup: Vec<Value> = Vec::new();
        // How many days the piece each standing block took its fields from held.
        let mut taken_from: Vec<usize> = Vec::new();
        for block in blocks {
            let Some(id) = id_of(block) else {
                continue;
            };
            if !is_setup_block(block)? {
                continue;
            }
            // School stands once, by its own id, however many pieces the week holds: on all their
            // days, as the piece holding the most of them has it (School's own id on a tie).
            let family = family_id(id);
            let days = days_of(block);
            let mut body = standing_body(block);
            body["id"] = Value::from(family);
            match setup.iter().position(|held| id_of(held) == Some(family)) {
                None => {
                    taken_from.push(days.len());
                    setup.push(body);
                }
                Some(at) => {
                    let mut all = days_of(&setup[at]);
                    for day in &days {
                        if !all.contains(day) {
                            all.push(*day);
                        }
                    }
                    all.sort_unstable();
                    if days.len() > taken_from[at] || (days.len() == taken_from[at] && id == family)
                    {
                        taken_from[at] = days.len();
                        setup[at] = body;
                    }
                    setup[at]["days"] = Value::from(all);
                }
            }
        }
        if !setup.is_empty() {
            newest = Some((week_start.clone(), setup));
        }
    }
    Ok(newest)
}

/// The most repeats a list of standing rows (`id`, `from_week`, `body`; a null body stops) holds in any
/// one week: for each week a row starts, the ids whose latest row from that week or earlier has a body.
/// An import whose rows hold more than `repeats::MAX_REPEATS` at once is refused.
pub fn most_standing_at_once(rows: &[Value]) -> usize {
    let text = |row: &Value, key: &str| {
        row.get(key)
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string()
    };
    let mut weeks: Vec<String> = rows.iter().map(|row| text(row, "from_week")).collect();
    weeks.sort_unstable();
    weeks.dedup();
    weeks
        .iter()
        .map(|week| {
            let mut latest: HashMap<String, (String, bool)> = HashMap::new();
            for row in rows {
                let from = text(row, "from_week");
                if &from > week {
                    continue;
                }
                let live = !row.get("body").is_none_or(Value::is_null);
                let entry = latest
                    .entry(text(row, "id"))
                    .or_insert((from.clone(), live));
                if from >= entry.0 {
                    *entry = (from, live);
                }
            }
            latest.values().filter(|(_, live)| *live).count()
        })
        .max()
        .unwrap_or(0)
}
