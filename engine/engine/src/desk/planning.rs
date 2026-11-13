//! Planning helpers from `desktop/native/reuse.py`, on the values as the Python code held them, so a
//! wrong kind of value raises what Python raised.

use chrono::Datelike;
use serde_json::{Value, json};

use crate::desk::calendar::DAY_FULL;
use crate::desk::grid::unpack_pair;
use crate::desk::pydate::from_iso;
use crate::desk::pyops::{
    Cmp, PyDict, compare, contains, eq, first_of, get, hashable, head, hhmm_of, in_set, int_of,
    is_int, iso_day_of, iterate, length, or_default, order, py_dict, to_int, tuple_index,
};
use crate::desk::pyval::{list_of, subscript, type_error};
use crate::error::{EngineError, EngineResult};
use crate::snapshot::dumps_sorted;
use crate::stored::{attribute_error, py_int, py_str, text, truthy};
use crate::time::{DAY_END_MIN, DAY_START_MIN, SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm};

fn null() -> &'static Value {
    static NULL: Value = Value::Null;
    &NULL
}

fn minutes_of(start: &Value) -> EngineResult<i64> {
    hhmm_to_minutes(text(start, "split")?)
}

fn list_field(block: &Value, key: &str) -> EngineResult<Value> {
    Ok(or_default(get(block, key)?, json!([])))
}

pub fn is_homework_session(block: &Value) -> EngineResult<bool> {
    Ok(truthy(get(block, "assignment_id")?))
}

pub fn session_days(week_start: &str, due: &Value) -> EngineResult<Vec<i64>> {
    let monday = from_iso(week_start)?;
    let due_day = iso_day_of(&head(due, 10)?)?;
    let last = crate::stored::add_days(monday, 6)?;
    if due_day < monday {
        return Ok(vec![0]);
    }
    if due_day > last {
        return Ok((0..=6).collect());
    }
    Ok((0..=i64::from(due_day.weekday().num_days_from_monday())).collect())
}

pub fn is_planned(block: &Value) -> EngineResult<bool> {
    if !eq(get(block, "kind")?.unwrap_or(null()), &json!("flexible")) {
        return Ok(false);
    }
    if !truthy(get(block, "start")?) {
        return Ok(false);
    }
    if truthy(get(block, "completed")?) {
        return Ok(false);
    }
    Ok(length(&list_field(block, "days")?)? == 1)
}

/// `assignments.get(key)` for a key of any kind.
fn table_get<'a>(table: &'a Value, key: &Value) -> EngineResult<Option<&'a Value>> {
    let Value::Object(map) = table else {
        return Err(attribute_error(table, "get"));
    };
    hashable(key, "dict key")?;
    Ok(key.as_str().and_then(|name| map.get(name)))
}

pub fn planning_days(
    block: &Value,
    assignments: &Value,
    week_start: &str,
) -> EngineResult<Vec<Value>> {
    // `assignments.get(...)` finds `get` before it reads the block.
    table_get(assignments, &Value::Null)?;
    let link = or_default(get(block, "assignment_id")?, json!(""));
    let assignment = table_get(assignments, &link)?;
    if let Some(found) = assignment
        && truthy(Some(found))
        && truthy(get(found, "due")?)
    {
        let due = subscript(found, "due")?;
        return Ok(session_days(week_start, due)?
            .into_iter()
            .map(Value::from)
            .collect());
    }
    list_of(&or_default(get(block, "days")?, json!([0])))
}

fn place_map(trace: &Value, key: &str) -> EngineResult<Vec<Value>> {
    let source = or_default(Some(trace), json!({}));
    let listed = or_default(get(&source, key)?, json!([]));
    iterate(&listed)
}

fn write_duration(fields: &mut serde_json::Map<String, Value>, source: &Value) -> EngineResult<()> {
    if let Some(duration) = get(source, "duration_min")?
        && !duration.is_null()
    {
        fields.insert("duration_min".into(), duration.clone());
    }
    Ok(())
}

fn split_parent_id(id: &Value) -> Option<Value> {
    let parent = id.as_str()?.strip_suffix("~2")?;
    if parent.is_empty() {
        return None;
    }
    Some(Value::String(parent.to_string()))
}

pub fn apply_plan(
    blocks: &Value,
    trace: &Value,
    targets: Option<&Value>,
    assignments: Option<&Value>,
    week_start: Option<&str>,
) -> EngineResult<Vec<Value>> {
    let placed_items = place_map(trace, "placed")?;
    let unplaced_items = place_map(trace, "unplaced")?;
    let mut placed = PyDict::new();
    for item in &placed_items {
        placed.set(subscript(item, "id")?.clone(), item.clone())?;
    }
    let mut unplaced_ids: Vec<Value> = Vec::new();
    let mut unplaced_body = PyDict::new();
    for item in &unplaced_items {
        let id = subscript(item, "id")?.clone();
        hashable(&id, "set element")?;
        unplaced_ids.push(id.clone());
        unplaced_body.set(id, item.clone())?;
    }
    let input = iterate(blocks)?;
    let mut seen: Vec<Value> = Vec::new();
    let mut out = Vec::new();
    for block in &input {
        let mut copy = Value::Object(py_dict(block)?);
        if let Ok(id) = subscript(&copy, "id") {
            seen.push(id.clone());
        }
        let unplanned = eq(get(&copy, "kind")?.unwrap_or(null()), &json!("flexible"))
            && !truthy(get(&copy, "completed")?);
        let skip = !unplanned
            || match targets {
                Some(set) => !in_set(&iterate(set)?, subscript(&copy, "id")?)?,
                None => false,
            };
        if skip {
            out.push(copy);
            continue;
        }
        let id = subscript(&copy, "id")?.clone();
        let winner = placed.get(&id)?.cloned();
        let fields = match &mut copy {
            Value::Object(fields) => fields,
            _ => return Err(type_error("block is not a dict")),
        };
        if let Some(winner) = winner.as_ref()
            && truthy(Some(winner))
            && truthy(get(winner, "start")?)
        {
            fields.insert("start".into(), subscript(winner, "start")?.clone());
            if truthy(get(winner, "days")?) {
                fields.insert(
                    "days".into(),
                    Value::Array(list_of(subscript(winner, "days")?)?),
                );
            }
            write_duration(fields, winner)?;
        } else if in_set(&unplaced_ids, &id)? {
            if let Some(missed) = unplaced_body.get(&id)? {
                write_duration(fields, missed)?;
            }
            fields.shift_remove("pinned");
            let had_start = fields.shift_remove("start");
            if had_start.as_ref().is_some_and(|value| truthy(Some(value)))
                && let (Some(assignments), Some(week_start)) = (assignments, week_start)
            {
                let days = planning_days(&copy, assignments, week_start)?;
                if let Value::Object(fields) = &mut copy {
                    fields.insert("days".into(), Value::Array(days));
                }
            }
        }
        out.push(copy);
    }
    for item in placed_items.iter().chain(&unplaced_items) {
        let id = subscript(item, "id")?.clone();
        if seen.iter().any(|held| eq(held, &id)) {
            continue;
        }
        let Some(parent_id) = split_parent_id(&id) else {
            continue;
        };
        let Some(parent) = input.iter().find(|block| {
            subscript(block, "id")
                .ok()
                .is_some_and(|held| eq(held, &parent_id))
        }) else {
            continue;
        };
        let parent_open = eq(get(parent, "kind")?.unwrap_or(null()), &json!("flexible"))
            && !truthy(get(parent, "completed")?)
            && match targets {
                Some(set) => in_set(&iterate(set)?, subscript(parent, "id")?)?,
                None => true,
            };
        if !parent_open {
            continue;
        }
        let mut fields = py_dict(parent)?;
        fields.insert("id".into(), id.clone());
        write_duration(&mut fields, item)?;
        if placed.contains(&id)? && truthy(get(item, "start")?) {
            fields.insert("start".into(), subscript(item, "start")?.clone());
            if truthy(get(item, "days")?) {
                fields.insert(
                    "days".into(),
                    Value::Array(list_of(subscript(item, "days")?)?),
                );
            }
        } else {
            fields.shift_remove("start");
            fields.shift_remove("pinned");
        }
        out.push(Value::Object(fields));
        seen.push(id);
    }
    Ok(out)
}

pub fn clear_stale_pins(blocks: &Value) -> EngineResult<Vec<Value>> {
    let mut out = Vec::new();
    for block in iterate(blocks)? {
        let stale = truthy(get(&block, "pinned")?)
            && !(truthy(get(&block, "start")?) && length(&list_field(&block, "days")?)? == 1);
        if stale {
            let Value::Object(fields) = &block else {
                return Err(attribute_error(&block, "items"));
            };
            out.push(Value::Object(
                fields
                    .iter()
                    .filter(|(key, _)| key.as_str() != "pinned")
                    .map(|(key, value)| (key.clone(), value.clone()))
                    .collect(),
            ));
        } else {
            out.push(block);
        }
    }
    Ok(out)
}

pub fn held_in_place(block: &Value) -> EngineResult<Value> {
    let id = subscript(block, "id")?.clone();
    let title = or_default(get(block, "title")?, json!("Homework"));
    let duration = subscript(block, "duration_min")?.clone();
    let days = Value::Array(list_of(subscript(block, "days")?)?);
    let start = subscript(block, "start")?.clone();
    Ok(json!({
        "id": id,
        "title": title,
        "kind": "locked",
        "duration_min": duration,
        "days": days,
        "start": start,
    }))
}

pub fn plan_start(
    week_start: &str,
    today_iso: &str,
    clock_minutes: i64,
    partial_minute: bool,
) -> EngineResult<Option<(i64, i64)>> {
    let day = (from_iso(today_iso)? - from_iso(week_start)?).num_days();
    if day < 0 {
        return Ok(None);
    }
    let minute = clock_minutes + i64::from(partial_minute);
    let minute = -((-minute).div_euclid(SLOT_MIN)) * SLOT_MIN;
    if minute >= DAY_END_MIN {
        return Ok(Some((day + 1, DAY_START_MIN)));
    }
    Ok(Some((day, minute)))
}

/// `plan_start` for a moment read off the clock: its hour and minute, and whether any seconds have
/// gone past the minute.
pub fn plan_start_at(
    week_start: &str,
    today_iso: &str,
    hour: i64,
    minute: i64,
    second: i64,
    microsecond: i64,
) -> EngineResult<Option<(i64, i64)>> {
    plan_start(
        week_start,
        today_iso,
        hour * 60 + minute,
        second != 0 || microsecond != 0,
    )
}

/// `not_before` crosses as JSON, which cannot tell the tuple Python compares against from a list it
/// refuses to, so the caller says which it held.
fn begun(block: &Value, not_before: Option<&Value>, held_a_list: bool) -> EngineResult<bool> {
    let Some(not_before) = not_before.filter(|value| !value.is_null()) else {
        return Ok(false);
    };
    let here = json!([
        first_of(subscript(block, "days")?)?,
        minutes_of(subscript(block, "start")?)?
    ]);
    match not_before {
        Value::Array(_) if !held_a_list => compare(Cmp::Lt, &here, not_before),
        Value::Array(_) => Err(type_error(
            "'<' not supported between instances of 'tuple' and 'list'",
        )),
        other => Err(type_error(format!(
            "'<' not supported between instances of 'tuple' and '{}'",
            crate::stored::type_name(other)
        ))),
    }
}

fn from_not_before(session: &Value, not_before: &Value) -> EngineResult<Value> {
    let (day, minute) = unpack_pair(not_before)?;
    let mut days = Vec::new();
    for item in iterate(subscript(session, "days")?)? {
        if compare(Cmp::Ge, &item, &day)? {
            days.push(item);
        }
    }
    if days.is_empty() {
        days.push(day.clone());
    }
    let name = DAY_FULL[tuple_index(DAY_FULL.len(), &day)?];
    let earliest = format!("{name} {}", hhmm_of(&minute)?);
    let mut out = match session {
        Value::Object(fields) => fields.clone(),
        other => {
            return Err(type_error(format!(
                "'{}' object is not a mapping",
                crate::stored::type_name(other)
            )));
        }
    };
    out.insert("days".into(), Value::Array(days));
    out.insert("earliest".into(), json!(earliest));
    Ok(Value::Object(out))
}

pub fn solve_request(
    blocks: &Value,
    assignments: &Value,
    week_start: &str,
    everything: bool,
    only: Option<&Value>,
    not_before: Option<&Value>,
    not_before_is_list: bool,
) -> EngineResult<(Vec<Value>, Vec<Value>)> {
    solve_request_at(
        blocks,
        assignments,
        week_start,
        everything,
        only,
        not_before,
        not_before_is_list,
        None,
        &[],
    )
}

/// `solve_request` that also knows the clock, `now` as (day, minute) of the real current minute. A
/// homework session that ended by `now`, is not pinned and still has minutes to do is then moved by
/// Replan all instead of kept for having begun. Without `now` no session counts as missed.
/// `saved_week` is the week the homework's server numbers were read with (`this_weeks_part`).
pub fn solve_request_at(
    blocks: &Value,
    assignments: &Value,
    week_start: &str,
    everything: bool,
    only: Option<&Value>,
    not_before: Option<&Value>,
    not_before_is_list: bool,
    now: Option<&Value>,
    saved_week: &[Value],
) -> EngineResult<(Vec<Value>, Vec<Value>)> {
    let mut payload = Vec::new();
    let mut targets: Vec<Value> = Vec::new();
    let all = iterate(blocks)?;
    let missed = match now.filter(|value| !value.is_null()) {
        Some(now) => missed_minutes(&all, assignments, saved_week, now)?,
        None => Vec::new(),
    };
    for block in all.iter().cloned() {
        if !eq(get(&block, "kind")?.unwrap_or(null()), &json!("flexible"))
            || truthy(get(&block, "completed")?)
        {
            payload.push(block);
            continue;
        }
        let planned = is_planned(&block)?;
        // A session whose time has passed is not "kept" for having begun: Replan all moves it.
        let id = subscript(&block, "id")?;
        let minutes = missed
            .iter()
            .find(|(held, _)| eq(held, id))
            .map(|(_, minutes)| *minutes);
        let kept = planned
            && minutes.is_none()
            && (truthy(get(&block, "pinned")?) || begun(&block, not_before, not_before_is_list)?);
        let wanted = match only.filter(|value| !value.is_null()) {
            Some(only) => contains(only, subscript(&block, "id")?)?,
            None => (everything && !kept) || !planned,
        };
        if wanted {
            let mut session = match &block {
                Value::Object(fields) => fields.clone(),
                other => return Err(attribute_error(other, "get")),
            };
            if planned {
                session.shift_remove("start");
                session.insert(
                    "days".into(),
                    Value::Array(planning_days(&block, assignments, week_start)?),
                );
            }
            if let Some(minutes) = minutes {
                session.insert("duration_min".into(), json!(minutes));
            }
            let session = Value::Object(session);
            payload.push(match not_before.filter(|value| !value.is_null()) {
                None => session,
                Some(limit) => from_not_before(&session, limit)?,
            });
            let id = subscript(&block, "id")?.clone();
            hashable(&id, "set element")?;
            if !targets.iter().any(|held| eq(held, &id)) {
                targets.push(id);
            }
        } else if planned {
            payload.push(held_in_place(&block)?);
        }
    }
    Ok((payload, targets))
}

/// Where a planned homework session stands against the clock: its (day, start) once it has ended by
/// `now`, the real current minute as (day, minute). `None` for anything else, a session still on
/// included. Rounding the plan's start up to the quarter hour is no part of this: a session ending
/// inside the current quarter hour is over only once its end is reached.
fn ended_session(block: &Value, now: &Value) -> EngineResult<Option<(i64, i64)>> {
    if !is_planned(block)? || !truthy(get(block, "assignment_id")?) {
        return Ok(None);
    }
    let start = minutes_of(subscript(block, "start")?)?;
    let length = int_of(&or_default(get(block, "duration_min")?, json!(0)))?;
    let end = (start + length).min(DAY_END_MIN);
    let day = first_of(subscript(block, "days")?)?;
    if !compare(Cmp::Le, &json!([day, end]), now)? {
        return Ok(None);
    }
    Ok(Some((int_of(&day)?, start)))
}

fn finished(block: &Value) -> bool {
    block
        .get("completed")
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

/// What Replan all gives each homework session whose time has passed: the minutes it still needs,
/// as (session id, minutes). A session left out is not one a plan moves: not planned, pinned,
/// finished, not homework, still ahead or on now, or none of its homework's time is left for it.
///
/// A homework's minutes still needed are this week's part of it (`this_weeks_part`, read against
/// `saved_week`: the estimate less focus time, kept on the homework so the timer does not tick sessions
/// off, less what later weeks hold) less what its other open sessions of this week hold, on the quarter
/// hour. The passed sessions take them in time order, each no more than its own length: a passed
/// session counts for the ones after it, not for those before it, so neither the focus time nor another
/// passed session is taken off twice.
fn missed_minutes(
    blocks: &[Value],
    assignments: &Value,
    saved_week: &[Value],
    now: &Value,
) -> EngineResult<Vec<(Value, i64)>> {
    let saved = Value::Array(saved_week.to_vec());
    let mut passed = Vec::with_capacity(blocks.len());
    for block in blocks {
        let at = match ended_session(block, now)? {
            Some((day, start)) if !truthy(get(block, "pinned")?) => {
                let id = subscript(block, "id")?.as_str().unwrap_or_default();
                Some((day, start, id.to_string()))
            }
            _ => None,
        };
        passed.push(at);
    }
    let mut out = Vec::new();
    for (index, block) in blocks.iter().enumerate() {
        let Some(here) = &passed[index] else {
            continue;
        };
        let link = subscript(block, "assignment_id")?;
        let Some(assignment) = table_get(assignments, link)?.filter(|found| truthy(Some(found)))
        else {
            continue;
        };
        if truthy(get(assignment, "completed")?) {
            continue;
        }
        let part = this_weeks_part(assignment, link, &saved)?;
        let mut others = 0;
        for (at, other) in blocks.iter().enumerate() {
            if at == index
                || other.get("assignment_id") != Some(link)
                || finished(other)
                || passed[at].as_ref().is_some_and(|there| there >= here)
            {
                continue;
            }
            others += other
                .get("duration_min")
                .and_then(Value::as_i64)
                .unwrap_or(0);
        }
        let left = floor_slot(part - others);
        if left >= SLOT_MIN {
            let length = int_of(&or_default(get(block, "duration_min")?, json!(0)))?;
            out.push((subscript(block, "id")?.clone(), left.min(length)));
        }
    }
    Ok(out)
}

/// The ids of the sessions a screen calls missed: those Replan all moves for having passed, and a
/// pinned one that passed unfinished, which no plan moves.
pub fn missed_session_ids(
    blocks: &[Value],
    assignments: &Value,
    saved_week: &[Value],
    now: Option<&Value>,
) -> EngineResult<Vec<Value>> {
    let Some(now) = now.filter(|value| !value.is_null()) else {
        return Ok(Vec::new());
    };
    let mut ids: Vec<Value> = missed_minutes(blocks, assignments, saved_week, now)?
        .into_iter()
        .map(|(id, _)| id)
        .collect();
    for block in blocks {
        if ended_session(block, now)?.is_none() || !truthy(get(block, "pinned")?) {
            continue;
        }
        let link = subscript(block, "assignment_id")?;
        let open = table_get(assignments, link)?
            .filter(|found| truthy(Some(found)))
            .is_some_and(|found| !truthy(found.get("completed")));
        if open {
            ids.push(subscript(block, "id")?.clone());
        }
    }
    Ok(ids)
}

/// The week with each session Replan all would move for having passed read as one with no time (its
/// start dropped, its length the minutes still needed), so the count of homework that needs a time
/// does not call a missed session "has a time". The week as it is when there is no clock to read
/// (`now` empty).
pub fn without_missed_times(
    blocks: &[Value],
    assignments: &Value,
    saved_week: &[Value],
    now: Option<&Value>,
) -> EngineResult<Vec<Value>> {
    let Some(now) = now.filter(|value| !value.is_null()) else {
        return Ok(blocks.to_vec());
    };
    let missed = missed_minutes(blocks, assignments, saved_week, now)?;
    let mut out = Vec::with_capacity(blocks.len());
    for block in blocks {
        let id = subscript(block, "id")?;
        match missed.iter().find(|(held, _)| eq(held, id)) {
            Some((_, minutes)) => {
                let mut open = py_dict(block)?;
                open.shift_remove("start");
                open.insert("duration_min".into(), json!(minutes));
                out.push(Value::Object(open));
            }
            None => out.push(block.clone()),
        }
    }
    Ok(out)
}

/// The real current minute as (day, minute) of the week, or `None` when today is not in it: a week
/// ahead has nothing gone by, and one over is left to the earlier-week rules.
pub fn clock_point(
    week_start: &str,
    today_iso: &str,
    hour: i64,
    minute: i64,
) -> EngineResult<Option<(i64, i64)>> {
    let day = (from_iso(today_iso)? - from_iso(week_start)?).num_days();
    Ok((0..=6).contains(&day).then_some((day, hour * 60 + minute)))
}

/// The point a screen reads missed sessions at: the real minute in this week, the week's end once the
/// week is over (every session in it has ended), and none for a week still ahead. Replan all plans from
/// `clock_point`; a screen showing an earlier week still has to say which of its sessions were missed.
pub fn screen_point(
    week_start: &str,
    today_iso: &str,
    hour: i64,
    minute: i64,
) -> EngineResult<Option<(i64, i64)>> {
    let day = (from_iso(today_iso)? - from_iso(week_start)?).num_days();
    Ok(match day {
        0..=6 => Some((day, hour * 60 + minute)),
        7.. => Some((7, 0)),
        _ => None,
    })
}

/// `open_rest_sessions_since` with `blocks` as the week the server's numbers were read with.
pub fn open_rest_sessions(
    blocks: &[Value],
    assignments: &serde_json::Map<String, Value>,
    week_start: &str,
    earlier_blocks: &[Value],
) -> EngineResult<Vec<Value>> {
    open_rest_sessions_since(blocks, assignments, week_start, earlier_blocks, blocks)
}

/// Add one open session for homework with time remaining and no open session in this week, sized to
/// the minutes no session holds (counted against `saved_week`, `this_weeks_part`) down to a quarter
/// hour. The deterministic id makes applying the operation repeatedly safe.
pub fn open_rest_sessions_since(
    blocks: &[Value],
    assignments: &serde_json::Map<String, Value>,
    week_start: &str,
    earlier_blocks: &[Value],
    saved_week: &[Value],
) -> EngineResult<Vec<Value>> {
    let monday = from_iso(week_start)?;
    let here = Value::Array(blocks.to_vec());
    let saved = Value::Array(saved_week.to_vec());
    let mut out = blocks.to_vec();
    for (id, assignment) in assignments {
        if truthy(get(assignment, "completed")?) {
            continue;
        }
        let Some(due) = assignment.get("due").and_then(Value::as_str) else {
            continue;
        };
        if crate::model::parse_due(due)?.0 < monday {
            continue;
        }
        let has_open = out.iter().any(|block| {
            block.get("assignment_id").and_then(Value::as_str) == Some(id)
                && !truthy(block.get("start"))
                && !block
                    .get("completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        });
        let already_placed_earlier = earlier_blocks.iter().any(|block| {
            block.get("assignment_id").and_then(Value::as_str) == Some(id)
                && truthy(block.get("start"))
                && !truthy(block.get("completed"))
        });
        if has_open || already_placed_earlier {
            continue;
        }
        let minutes = floor_slot(uncovered_minutes(assignment, &json!(id), &here, &saved)?);
        if minutes < SLOT_MIN {
            continue;
        }
        let due = subscript(assignment, "due")?;
        out.push(json!({
            "id": format!("{id}-rest-{week_start}"),
            "kind": "flexible",
            "assignment_id": id,
            "title": assignment.get("title").cloned().unwrap_or(Value::Null),
            "duration_min": minutes,
            "days": session_days(week_start, due)?,
            "priority": assignment.get("priority").cloned().unwrap_or(json!(2)),
            "energy": assignment.get("energy").cloned().unwrap_or(json!("medium")),
            "completed": false
        }));
    }
    Ok(out)
}

/// Move open sessions from earlier weeks into this week and return both sides of each write.
pub fn move_earlier_homework(
    blocks: &[Value],
    earlier_weeks: &[Value],
    assignments: &serde_json::Map<String, Value>,
    week_start: &str,
) -> EngineResult<Value> {
    let monday = from_iso(week_start)?;
    let mut current = blocks.to_vec();
    let mut moved = Vec::new();
    let mut updates = Vec::new();
    for saved in earlier_weeks {
        let source_week = py_str(subscript(saved, "week_start")?);
        if source_week.as_str() >= week_start {
            continue;
        }
        let before = list_field(saved, "blocks")?;
        let before_blocks = iterate(&before)?;
        let mut after = Vec::new();
        let mut groups: Vec<(String, Vec<Value>)> = Vec::new();
        for block in before_blocks {
            let Some(assignment_id) = block.get("assignment_id").and_then(Value::as_str) else {
                after.push(block);
                continue;
            };
            let Some(assignment) = assignments.get(assignment_id) else {
                after.push(block);
                continue;
            };
            let is_open = eq(get(&block, "kind")?.unwrap_or(null()), &json!("flexible"))
                && !truthy(get(&block, "start")?)
                && !truthy(get(&block, "completed")?)
                && !truthy(get(assignment, "completed")?);
            let Some(due) = assignment.get("due").and_then(Value::as_str) else {
                after.push(block);
                continue;
            };
            if !is_open || crate::model::parse_due(due)?.0 < monday {
                after.push(block);
                continue;
            }
            if let Some((_, sessions)) = groups.iter_mut().find(|(id, _)| id == assignment_id) {
                sessions.push(block);
            } else {
                groups.push((assignment_id.to_string(), vec![block]));
            }
        }
        let mut changed = false;
        for (assignment_id, sessions) in &groups {
            let minutes: i64 = sessions
                .iter()
                .map(|block| {
                    block
                        .get("duration_min")
                        .and_then(Value::as_i64)
                        .unwrap_or(0)
                })
                .sum();
            let existing = current.iter().position(|block| {
                block.get("assignment_id").and_then(Value::as_str) == Some(assignment_id)
                    && eq(
                        get(block, "kind").ok().flatten().unwrap_or(null()),
                        &json!("flexible"),
                    )
                    && !truthy(block.get("start"))
                    && !truthy(block.get("completed"))
            });
            let Some(assignment) = assignments.get(assignment_id) else {
                after.extend(sessions.iter().cloned());
                continue;
            };
            let mut moved_block = if let Some(at) = existing {
                let block = &mut current[at];
                let duration = block
                    .get("duration_min")
                    .and_then(Value::as_i64)
                    .unwrap_or(0);
                if let Some(fields) = block.as_object_mut() {
                    fields.insert("duration_min".into(), json!(duration + minutes));
                    fields.insert(
                        "days".into(),
                        Value::Array(
                            session_days(week_start, subscript(assignment, "due")?)?
                                .into_iter()
                                .map(Value::from)
                                .collect(),
                        ),
                    );
                }
                block.clone()
            } else {
                if current.len() as i64 >= crate::desk::reuse::MAX_WEEK_BLOCKS {
                    after.extend(sessions.iter().cloned());
                    continue;
                }
                let mut block = sessions[0].clone();
                let Value::Object(fields) = &mut block else {
                    after.extend(sessions.iter().cloned());
                    continue;
                };
                fields.insert("duration_min".into(), json!(minutes));
                fields.insert(
                    "days".into(),
                    Value::Array(
                        session_days(week_start, subscript(assignment, "due")?)?
                            .into_iter()
                            .map(Value::from)
                            .collect(),
                    ),
                );
                fields.shift_remove("start");
                fields.shift_remove("earliest");
                fields.shift_remove("pinned");
                current.push(block.clone());
                block
            };
            if let Some(fields) = moved_block.as_object_mut() {
                fields.insert("duration_min".into(), json!(minutes));
            }
            moved.push(moved_block);
            changed = true;
        }
        if changed {
            updates.push(json!({
                "week_start": source_week,
                "before": before,
                "after": after,
                "revision": get(saved, "revision")?.cloned().unwrap_or(Value::Null),
            }));
        }
    }
    Ok(json!({"blocks": current, "moved": moved, "weeks": updates}))
}

/// Count homework time that still needs a time, grouped by deadline week relative to this week.
///
/// Minutes, exactly: a remainder that does not fill a quarter hour is still time with no time. The
/// four-field shape is what the screens read; `time_still_needed_parts` also splits the minutes.
/// With no saved week given, every session of the week is read as unsaved.
pub fn time_still_needed(
    assignments: &serde_json::Map<String, Value>,
    open_week_blocks: &[Value],
    week_start: &str,
) -> EngineResult<Vec<Value>> {
    time_still_needed_since(assignments, open_week_blocks, week_start, &[])
}

/// `time_still_needed` against `saved_week`, the week the server's numbers were read with
/// (`this_weeks_part`).
pub fn time_still_needed_since(
    assignments: &serde_json::Map<String, Value>,
    open_week_blocks: &[Value],
    week_start: &str,
    saved_week: &[Value],
) -> EngineResult<Vec<Value>> {
    Ok(
        time_still_needed_parts(assignments, open_week_blocks, week_start, saved_week)?
            .into_iter()
            .map(|mut item| {
                if let Some(fields) = item.as_object_mut() {
                    fields.shift_remove("waiting_min");
                    fields.shift_remove("uncovered_min");
                }
                item
            })
            .collect(),
    )
}

/// The same count with its two parts: `waiting_min`, sessions of the week that have no start yet,
/// and `uncovered_min`, minutes that no session holds at all (a remainder the planner could not
/// place, counted against `saved_week` as `uncovered_homework_minutes` counts it).
pub fn time_still_needed_parts(
    assignments: &serde_json::Map<String, Value>,
    open_week_blocks: &[Value],
    week_start: &str,
    saved_week: &[Value],
) -> EngineResult<Vec<Value>> {
    let monday = from_iso(week_start)?;
    let here = Value::Array(open_week_blocks.to_vec());
    let saved = Value::Array(saved_week.to_vec());
    let mut result = Vec::new();
    for (id, assignment) in assignments {
        if truthy(get(assignment, "completed")?) {
            continue;
        }
        let waiting: i64 = open_week_blocks
            .iter()
            .filter(|block| {
                block.get("assignment_id").and_then(Value::as_str) == Some(id)
                    && !truthy(block.get("start"))
                    && !block
                        .get("completed")
                        .and_then(Value::as_bool)
                        .unwrap_or(false)
            })
            .map(|block| {
                block
                    .get("duration_min")
                    .and_then(Value::as_i64)
                    .unwrap_or(0)
            })
            .sum();
        let uncovered = uncovered_minutes(assignment, &json!(id), &here, &saved)?;
        let minutes = waiting + uncovered;
        if minutes == 0 {
            continue;
        }
        let due = assignment.get("due").and_then(Value::as_str);
        let offset = due
            .map(|text| crate::model::parse_due(text).map(|(day, _)| (day - monday).num_days()))
            .transpose()?;
        let period = match offset {
            Some(day) if day < 0 => "earlier",
            Some(day) if day <= 6 => "this_week",
            _ => "later",
        };
        result.push(json!({
            "assignment_id": id,
            "title": assignment.get("title").cloned().unwrap_or(Value::Null),
            "minutes": minutes,
            "waiting_min": waiting,
            "uncovered_min": uncovered,
            "period": period
        }));
    }
    Ok(result)
}

/// Homework with a session still waiting for a time (`open`), and of those the ones whose every minute
/// is in a session (`waiting_only`). A homework with a waiting session and minutes no session holds is
/// open but not waiting only: Plan names it by its minutes, so it is not also counted as waiting.
pub fn plan_open_counts(
    assignments: &serde_json::Map<String, Value>,
    open_week_blocks: &[Value],
    week_start: &str,
    saved_week: &[Value],
) -> EngineResult<(i64, i64)> {
    let mut open = 0;
    let mut waiting_only = 0;
    for item in time_still_needed_parts(assignments, open_week_blocks, week_start, saved_week)? {
        if item["waiting_min"].as_i64().unwrap_or(0) > 0 {
            open += 1;
            if item["uncovered_min"].as_i64().unwrap_or(0) == 0 {
                waiting_only += 1;
            }
        }
    }
    Ok((open, waiting_only))
}

pub fn due_point(due: &Value, week_start: &str) -> EngineResult<Option<(i64, i64)>> {
    if !truthy(Some(due)) {
        return Ok(None);
    }
    let text = match due {
        Value::String(found) => found.as_str(),
        other => {
            return Err(type_error(format!(
                "expected string or bytes-like object, got '{}'",
                crate::stored::type_name(other)
            )));
        }
    };
    let (due_day, minutes) = crate::model::parse_due(text)?;
    let offset = (due_day - from_iso(week_start)?).num_days();
    if offset > 6 {
        return Ok(None);
    }
    Ok(Some((offset, minutes)))
}

type Taken = Vec<Vec<(i64, i64, Value)>>;

fn taken_slot(day: &Value) -> EngineResult<usize> {
    hashable(day, "dict key")?;
    for slot in 0..7 {
        if eq(day, &json!(slot)) {
            return Ok(slot as usize);
        }
    }
    Err(match day {
        Value::String(name) => EngineError::key(name.as_str()),
        other => EngineError::key_repr(crate::stored::py_repr_of(other)),
    })
}

pub fn settle_placements(
    blocks: &Value,
    assignments: &Value,
    week_start: &str,
    keep: &Value,
    keep_is_set: bool,
) -> EngineResult<(Value, Vec<Value>)> {
    settle_placements_after_deadline(
        blocks,
        assignments,
        week_start,
        keep,
        keep_is_set,
        &json!([]),
    )
}

pub fn settle_placements_after_deadline(
    blocks: &Value,
    assignments: &Value,
    week_start: &str,
    keep: &Value,
    keep_is_set: bool,
    after_deadline: &Value,
) -> EngineResult<(Value, Vec<Value>)> {
    let all = iterate(blocks)?;
    let mut taken: Taken = vec![Vec::new(); 7];
    for block in &all {
        if !truthy(get(block, "start")?) {
            continue;
        }
        let start = minutes_of(subscript(block, "start")?)?;
        let span = int_of(&or_default(get(block, "duration_min")?, json!(0)))?;
        let end = start + span;
        if eq(get(block, "kind")?.unwrap_or(null()), &json!("locked")) {
            for day in iterate(&list_field(block, "days")?)? {
                if !contains(&list_field(block, "missed_days")?, &day)? {
                    taken[taken_slot(&day)?].push((
                        start,
                        end,
                        or_default(get(block, "title")?, json!("a fixed block")),
                    ));
                }
            }
        } else if truthy(get(block, "completed")?) {
            let days = list_field(block, "days")?;
            let only_day = if length(&days)? == 1 {
                first_of(&days)?
            } else {
                Value::Null
            };
            let day = get(block, "completed_day")?.cloned().unwrap_or(only_day);
            if !day.is_null() {
                taken[taken_slot(&day)?].push((
                    start,
                    end,
                    or_default(get(block, "title")?, json!("finished work")),
                ));
            }
        }
    }
    let mut keyed: Vec<(Value, Value)> = Vec::new();
    for block in &all {
        if !is_planned(block)? {
            continue;
        }
        let id = subscript(block, "id")?;
        let rank = !if keep_is_set {
            in_set(&iterate(keep)?, id)?
        } else {
            contains(keep, id)?
        };
        let key = json!([
            rank,
            first_of(subscript(block, "days")?)?,
            subscript(block, "start")?,
            id
        ]);
        keyed.push((key, block.clone()));
    }
    let mut failure = None;
    keyed.sort_by(|left, right| {
        order(&left.0, &right.0, Cmp::Lt).unwrap_or_else(|error| {
            failure.get_or_insert(error);
            std::cmp::Ordering::Equal
        })
    });
    if let Some(error) = failure {
        return Err(error);
    }
    let sessions: Vec<Value> = keyed.into_iter().map(|(_, block)| block).collect();
    let mut lost = PyDict::new();
    for block in &sessions {
        let day = first_of(subscript(block, "days")?)?;
        let start = minutes_of(subscript(block, "start")?)?;
        let end = start + int_of(&or_default(get(block, "duration_min")?, json!(0)))?;
        let found = table_get(
            assignments,
            &or_default(get(block, "assignment_id")?, json!("")),
        )?;
        let assignment = or_default(found, json!({}));
        let due = due_point(get(&assignment, "due")?.unwrap_or(null()), week_start)?;
        let pinned = truthy(get(block, "pinned")?);
        let slot = taken_slot(&day)?;
        let clash = if pinned {
            None
        } else {
            taken[slot]
                .iter()
                .find(|(low, high, _)| start < *high && *low < end)
                .map(|(_, _, title)| title.clone())
        };
        let why = if start < DAY_START_MIN || end > DAY_END_MIN {
            Some("that's outside the hours FlexWeek plans in".to_string())
        } else if due.is_some_and(|due| (int_of(&day).unwrap_or(0), end) > due)
            && !contains(after_deadline, subscript(block, "id")?)?
        {
            Some("that's after it's due".to_string())
        } else {
            clash.map(|title| format!("{} is there now", py_str(&title)))
        };
        let Some(why) = why else {
            if !pinned {
                taken[slot].push((
                    start,
                    end,
                    or_default(get(block, "title")?, json!("homework")),
                ));
            }
            continue;
        };
        let title = or_default(get(block, "title")?, json!("Homework"));
        let shown = DAY_FULL[tuple_index(DAY_FULL.len(), &day)?];
        let stamp = crate::desk::weekmodel::hhmm_text(text(subscript(block, "start")?, "split")?)?;
        lost.set(
            subscript(block, "id")?.clone(),
            json!({
                "block_id": subscript(block, "id")?,
                "assignment_id": get(block, "assignment_id")?.cloned().unwrap_or(Value::Null),
                "title": title.clone(),
                "day": day,
                "start": subscript(block, "start")?,
                "message": format!("{} no longer fits {shown} at {stamp}: {why}.", py_str(&title)),
            }),
        )?;
    }
    if lost.is_empty() {
        return Ok((blocks.clone(), Vec::new()));
    }
    let mut out = Vec::new();
    for block in &all {
        if lost.contains(subscript(block, "id")?)? {
            let mut changed = match block {
                Value::Object(fields) => fields.clone(),
                other => return Err(attribute_error(other, "get")),
            };
            changed.shift_remove("start");
            changed.shift_remove("pinned");
            let changed_value = Value::Object(changed.clone());
            changed.insert(
                "days".into(),
                Value::Array(planning_days(&changed_value, assignments, week_start)?),
            );
            out.push(Value::Object(changed));
        } else {
            out.push(block.clone());
        }
    }
    let mut report = Vec::new();
    for block in &sessions {
        if let Some(entry) = lost.get(subscript(block, "id")?)? {
            report.push(entry.clone());
        }
    }
    Ok((Value::Array(out), report))
}

pub fn occurrence_days(block: &Value) -> EngineResult<Vec<Value>> {
    if truthy(Some(block))
        && eq(get(block, "kind")?.unwrap_or(null()), &json!("flexible"))
        && truthy(get(block, "completed")?)
    {
        let done = get(block, "completed_day")?.cloned().unwrap_or(Value::Null);
        if is_int(&done) {
            return Ok(vec![done]);
        }
        if let Some(days @ Value::Array(_)) = get(block, "days")?
            && length(days)? > 1
        {
            return Ok(Vec::new());
        }
    }
    let source = or_default(Some(block), json!({}));
    list_of(&or_default(get(&source, "days")?, json!([])))
}

pub fn session_minutes(blocks: &Value, assignment_id: &Value) -> EngineResult<i64> {
    let mut total = 0;
    for block in iterate(blocks)? {
        if eq(
            get(&block, "assignment_id")?.unwrap_or(null()),
            assignment_id,
        ) && !truthy(get(&block, "completed")?)
        {
            total += py_int(subscript(&block, "duration_min")?)?;
        }
    }
    Ok(total)
}

pub fn floor_slot(minutes: i64) -> i64 {
    (minutes.max(0) / SLOT_MIN) * SLOT_MIN
}

fn has_free_study_slot(
    day: i64,
    after: i64,
    work_windows: &[Value],
    blocks: &[Value],
) -> EngineResult<bool> {
    let windows: Vec<(i64, i64)> = if work_windows.is_empty() {
        vec![(DAY_START_MIN, DAY_END_MIN)]
    } else {
        let mut windows = Vec::new();
        for window in work_windows {
            if !window
                .get("days")
                .and_then(Value::as_array)
                .is_some_and(|days| days.iter().any(|value| value.as_i64() == Some(day)))
            {
                continue;
            }
            windows.push((
                minutes_of(subscript(window, "start")?)?,
                minutes_of(subscript(window, "end")?)?,
            ));
        }
        windows
    };
    for (start, end) in windows {
        let mut slot = ceil_slot(start.max(after));
        while slot + SLOT_MIN <= end {
            let occupied = blocks.iter().any(|block| {
                let Some(block_start) = block
                    .get("start")
                    .and_then(Value::as_str)
                    .and_then(|value| hhmm_to_minutes(value).ok())
                else {
                    return false;
                };
                let days = block.get("days").and_then(Value::as_array);
                let duration = block
                    .get("duration_min")
                    .and_then(Value::as_i64)
                    .unwrap_or(0);
                days.is_some_and(|days| days.iter().any(|value| value.as_i64() == Some(day)))
                    && slot < block_start + duration
                    && block_start < slot + SLOT_MIN
            });
            if !occupied {
                return Ok(true);
            }
            slot += SLOT_MIN;
        }
    }
    Ok(false)
}

fn plannable_days(
    first_day: i64,
    first_minute: i64,
    last_day: i64,
    work_windows: &[Value],
    blocks: &[Value],
) -> EngineResult<(i64, i64)> {
    let mut this_week = 0;
    for day in first_day.clamp(0, 6)..=6 {
        let after = if day == first_day {
            first_minute
        } else {
            DAY_START_MIN
        };
        if has_free_study_slot(day, after, work_windows, blocks)? {
            this_week += 1;
        }
    }
    let beyond_this_week = (last_day - 6).max(0);
    let full_weeks = beyond_this_week / 7;
    let tail_days = beyond_this_week % 7;
    let mut plannable_per_week = 0;
    for day in 0..7 {
        if has_free_study_slot(day, DAY_START_MIN, work_windows, &[])? {
            plannable_per_week += 1;
        }
    }
    let mut all_days = this_week + full_weeks * plannable_per_week;
    for day in 0..tail_days {
        if has_free_study_slot(day, DAY_START_MIN, work_windows, &[])? {
            all_days += 1;
        }
    }
    Ok((this_week, all_days))
}

/// Minutes of the homework that no session holds, exactly: `this_weeks_part` less what this week's
/// not-finished sessions (`blocks`, placed or waiting) hold, never below 0.
pub fn uncovered_homework_minutes(
    assignment: &Value,
    blocks: &Value,
    saved_week: &Value,
) -> EngineResult<i64> {
    if !truthy(Some(assignment)) || truthy(get(assignment, "completed")?) {
        return Ok(0);
    }
    uncovered_minutes(assignment, subscript(assignment, "id")?, blocks, saved_week)
}

fn uncovered_minutes(
    assignment: &Value,
    id: &Value,
    blocks: &Value,
    saved_week: &Value,
) -> EngineResult<i64> {
    Ok((this_weeks_part(assignment, id, saved_week)? - session_minutes(blocks, id)?).max(0))
}

/// Minutes of the homework that this week's sessions are to hold: the estimate less focus done, less
/// what its not-finished sessions in later weeks hold. Sessions in earlier weeks hold nothing here,
/// because the server counts from this week on.
///
/// `saved_week` is this week exactly as saved when the homework's `planned_min` and `unplanned_min`
/// were read, every session in it, placed or waiting. `planned_min` counted those sessions and every
/// later week's, so less them it is what later weeks hold. A homework not read from the server has no
/// later week known.
fn this_weeks_part(assignment: &Value, id: &Value, saved_week: &Value) -> EngineResult<i64> {
    let focus = int_of(&or_default(get(assignment, "focus_minutes")?, json!(0)))?;
    let Some(server) = get(assignment, "unplanned_min")?.filter(|value| !value.is_null()) else {
        // As the server branch below, a homework with no estimate is not an error: it asks for no time.
        let estimate = int_of(&or_default(get(assignment, "estimate_min")?, json!(0)))?;
        return Ok((estimate - focus).max(0));
    };
    let saved = session_minutes(&or_default(Some(saved_week), json!([])), id)?;
    let Some(estimate) = get(assignment, "estimate_min")?.filter(|value| !value.is_null()) else {
        return Ok(py_int(server)? + saved);
    };
    let need = (int_of(estimate)? - focus).max(0);
    let later = match get(assignment, "planned_min")?.filter(|value| !value.is_null()) {
        Some(planned) => py_int(planned)? - saved,
        // The unplanned number alone is floored at 0, so it says only that later weeks hold at least
        // what it leaves unexplained; read before a focus credit, that bound still holds.
        None => (need - py_int(server)? - saved).max(0),
    };
    Ok(need - later)
}

/// What the planner can place: the uncovered minutes, down to a whole quarter hour.
pub fn available_homework_minutes(
    assignment: &Value,
    blocks: &Value,
    saved_week: &Value,
) -> EngineResult<i64> {
    Ok(floor_slot(uncovered_homework_minutes(
        assignment, blocks, saved_week,
    )?))
}

pub fn block_occurs_on_day(
    block: &Value,
    day: &Value,
    placed: Option<&Value>,
) -> EngineResult<bool> {
    let flexible = is_homework_session(block)?
        || eq(get(block, "kind")?.unwrap_or(null()), &json!("flexible"));
    if flexible {
        let mut source = truthy(get(block, "start")?).then(|| block.clone());
        if source.is_none()
            && let Some(placed) = placed.filter(|list| truthy(Some(list)))
        {
            for item in iterate(placed)? {
                if eq(
                    get(&item, "id")?.unwrap_or(null()),
                    get(block, "id")?.unwrap_or(null()),
                ) && contains(&Value::Array(occurrence_days(&item)?), day)?
                {
                    source = Some(item);
                    break;
                }
            }
        }
        let Some(source) = source else {
            return Ok(false);
        };
        return Ok(truthy(Some(&source))
            && truthy(get(&source, "start")?)
            && contains(&Value::Array(occurrence_days(&source)?), day)?);
    }
    contains(&Value::Array(occurrence_days(block)?), day)
}

pub fn clipboard_fingerprint(items: &Value) -> EngineResult<String> {
    let mut payload = Vec::new();
    for item in iterate(items)? {
        payload.push(json!({
            "block": subscript(&item, "block")?,
            "source_day": subscript(&item, "source_day")?,
            "scope": subscript(&item, "scope")?,
        }));
    }
    Ok(dumps_sorted(&Value::Array(payload)))
}

pub fn capacity_problem(existing: i64, added: i64, label: &str) -> String {
    if i128::from(existing) + i128::from(added) > 100 {
        return format!(
            "{label} would exceed 100 blocks. Uncheck an item or remove a block first."
        );
    }
    String::new()
}

pub fn late_from_start(minute: i64) -> String {
    let snapped = minute.div_euclid(SLOT_MIN) * SLOT_MIN;
    minutes_to_hhmm(snapped.clamp(DAY_START_MIN, DAY_END_MIN - SLOT_MIN))
}

pub fn running_late_block(
    day: &Value,
    from_start: &str,
    minutes: i64,
    block_id: &Value,
) -> EngineResult<Value> {
    let start = hhmm_to_minutes(from_start)?;
    let duration = minutes.min(DAY_END_MIN - start);
    Ok(json!({
        "id": block_id,
        "kind": "locked",
        "title": "Running late",
        "duration_min": duration,
        "days": [day],
        "start": from_start,
        "priority": 1,
        "energy": "medium",
        "category": "downtime",
        "completed": false,
        "missed_days": [],
    }))
}

pub fn late_locked_line(block: &Value, moved: &Value) -> EngineResult<String> {
    let start = hhmm_to_minutes(&py_str(subscript(block, "start")?))?;
    let end = i128::from(start) + to_int(subscript(block, "duration_min")?)?;
    let extra = if truthy(Some(moved)) {
        format!("{} moved.", py_str(moved))
    } else {
        "Nothing had to move.".to_string()
    };
    Ok(format!(
        "Running late: {}–{} is now locked. {extra}",
        crate::desk::weekmodel::clock_text(start),
        crate::desk::weekmodel::clock_of(end)
    ))
}

pub fn copy_label(block: &Value, source_day: &Value, scope: &Value) -> EngineResult<Value> {
    let title = subscript(block, "title")?.clone();
    let series = eq(get(block, "kind")?.unwrap_or(null()), &json!("locked"))
        && length(&list_field(block, "days")?)? > 1;
    if eq(scope, &json!("series")) {
        return Ok(json!(format!("{} (all days)", py_str(&title))));
    }
    if series {
        let name = DAY_FULL[tuple_index(DAY_FULL.len(), source_day)?];
        return Ok(json!(format!("{} ({name} only)", py_str(&title))));
    }
    Ok(title)
}

fn ceil_slot(minutes: i64) -> i64 {
    (minutes.max(0) + SLOT_MIN - 1) / SLOT_MIN * SLOT_MIN
}

/// Keep homework due within seven days whole. Farther deadlines may receive a fair share.
///
/// `saved_week` is the week the homework's server numbers were read with (`this_weeks_part`); its
/// placed blocks are also the time already taken when today's free time is looked for.
pub fn fair_share(
    blocks: &[Value],
    assignments: &serde_json::Map<String, Value>,
    saved_week: &Value,
    week_start: &str,
    first_day: i64,
    first_minute: i64,
    work_windows: &[Value],
    targets: &[String],
) -> EngineResult<(Vec<Value>, Vec<Value>)> {
    let monday = from_iso(week_start)?;
    let id_of = |block: &Value| block.get("id").and_then(Value::as_str).map(str::to_string);
    let homework_of = |block: &Value| {
        block
            .get("assignment_id")
            .and_then(Value::as_str)
            .map(str::to_string)
    };
    let duration = |block: &Value| {
        block
            .get("duration_min")
            .and_then(Value::as_i64)
            .unwrap_or(0)
    };
    let mut order: Vec<String> = Vec::new();
    for block in blocks {
        if let (Some(id), Some(homework)) = (id_of(block), homework_of(block))
            && targets.contains(&id)
            && !order.contains(&homework)
        {
            order.push(homework);
        }
    }
    let mut out = blocks.to_vec();
    let mut notes = Vec::new();
    for homework in order {
        let Some(assignment) = assignments.get(&homework) else {
            continue;
        };
        if assignment
            .get("spread")
            .and_then(Value::as_str)
            .unwrap_or("one")
            == "one"
        {
            continue;
        }
        let Some(due) = assignment.get("due").and_then(Value::as_str) else {
            continue;
        };
        let due_offset = (crate::model::parse_due(due)?.0 - monday).num_days();
        if due_offset - first_day.clamp(0, 6) <= 7 {
            continue;
        }
        let (this_week, all_days) = plannable_days(
            first_day,
            first_minute,
            due_offset,
            work_windows,
            &iterate(saved_week)?,
        )?;
        // The share is cut from all of this week's part: the sessions being planned hold none of it yet
        // (no blocks), and the ones Plan keeps (`held`) are taken off the share below.
        let left = available_homework_minutes(assignment, &json!([]), saved_week)?;
        if this_week == 0 || all_days == 0 {
            notes.push(json!({
                "assignment_id": homework,
                "title": assignment.get("title").cloned().unwrap_or(Value::Null),
                "this_week_min": 0,
                "left_min": left,
            }));
            continue;
        }
        let share = ceil_slot((left * this_week + all_days - 1) / all_days).min(left);
        let held: i64 = out
            .iter()
            .filter(|block| {
                homework_of(block).as_deref() == Some(homework.as_str())
                    && !id_of(block).is_some_and(|id| targets.contains(&id))
                    && !block
                        .get("completed")
                        .and_then(Value::as_bool)
                        .unwrap_or(false)
            })
            .map(duration)
            .sum();
        let mut budget = (share - held).max(0);
        let mut placed = held;
        let mut cut = false;
        let mut kept = Vec::with_capacity(out.len());
        for block in out {
            let target = homework_of(&block).as_deref() == Some(homework.as_str())
                && id_of(&block).is_some_and(|id| targets.contains(&id));
            if !target {
                kept.push(block);
                continue;
            }
            let wanted = duration(&block);
            let given = floor_slot(wanted.min(budget));
            if given < wanted {
                cut = true;
            }
            if given < SLOT_MIN {
                continue;
            }
            budget -= given;
            placed += given;
            let mut trimmed = block;
            if let Some(fields) = trimmed.as_object_mut() {
                fields.insert("duration_min".into(), json!(given));
            }
            kept.push(trimmed);
        }
        out = kept;
        if cut {
            let remainder = (left - placed).max(0);
            if remainder >= SLOT_MIN {
                let rest_id = format!("{homework}-rest-{week_start}");
                out.retain(|block| id_of(block).as_deref() != Some(rest_id.as_str()));
                let due = subscript(assignment, "due")?;
                out.push(json!({
                    "id": rest_id,
                    "title": assignment.get("title").cloned().unwrap_or(Value::Null),
                    "kind": "flexible",
                    "assignment_id": homework,
                    "duration_min": remainder,
                    "days": session_days(week_start, due)?,
                    "priority": assignment.get("priority").cloned().unwrap_or(json!(2)),
                    "energy": assignment.get("energy").cloned().unwrap_or(json!("medium")),
                    "completed": false
                }));
            }
            notes.push(json!({
                "assignment_id": homework,
                "title": assignment.get("title").cloned().unwrap_or(Value::Null),
                "this_week_min": placed,
                "left_min": remainder,
            }));
        }
    }
    Ok((out, notes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_plan_starts_at_the_next_quarter_hour() {
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-21", 10, 30, 0, 0).unwrap(),
            Some((0, 630))
        );
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-21", 10, 31, 0, 0).unwrap(),
            Some((0, 645))
        );
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-24", 9, 0, 0, 1).unwrap(),
            Some((3, 555))
        );
    }

    #[test]
    fn a_half_minute_counts_as_a_whole_one() {
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-21", 10, 30, 30, 0).unwrap(),
            Some((0, 645))
        );
    }

    #[test]
    fn a_plan_that_starts_after_midnight_starts_the_next_day() {
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-21", 23, 59, 30, 0).unwrap(),
            Some((1, 0))
        );
        assert_eq!(
            plan_start_at("2026-09-21", "2026-09-27", 23, 50, 0, 0).unwrap(),
            Some((7, 0))
        );
    }

    #[test]
    fn a_week_still_ahead_has_no_start() {
        assert_eq!(
            plan_start_at("2026-09-28", "2026-09-27", 10, 0, 0, 0).unwrap(),
            None
        );
    }
}
