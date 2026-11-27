//! Decisions the hour tracks, the zoom, and the block sentences share. Callers pass the clock
//! and the week in; nothing here reads the time or the disk.

use flexweek_engine::desk::datetext::{day_of, day_short};
use flexweek_engine::desk::weekmodel::{length_label, range_label};
use flexweek_engine::model::parse_due;
use flexweek_engine::stored::add_days;
use flexweek_engine::{EngineError, EngineResult};
use serde_json::Value;

pub const GAP: f64 = 2.0;
pub const BETWEEN: f64 = 3.0;
pub const OPENS: i64 = 8 * 60;
pub const NARROW_WIDTH: i64 = 1150;
pub const DEFAULT_DRAG_STEP: i64 = 15;
pub const DRAG_STEPS: [i64; 2] = [5, 15];

const END_OF_DAY: i64 = 24 * 60;

pub const WEEK_STARTS: [&str; 7] = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
];

pub fn span_minutes(start: i64, end: i64) -> i64 {
    end - start
}

pub fn snap(minute: f64, step: i64) -> EngineResult<i64> {
    if step == 0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    // Python's round() is half to even, including the negative halves.
    let units = (minute / step as f64).round_ties_even();
    if units.is_nan() {
        return Err(EngineError::value("cannot convert float NaN to integer"));
    }
    if units.is_infinite() {
        return Err(EngineError::overflow(
            "cannot convert float infinity to integer",
        ));
    }
    let units = units as i64;
    units
        .checked_mul(step)
        .ok_or_else(|| EngineError::overflow("int too big"))
}

pub fn next_slot(minute: i64, first: i64, last: i64, step: i64) -> EngineResult<(i64, i64)> {
    if step == 0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    let minute = i128::from(minute);
    let step = i128::from(step);
    // `-(-minute // step) * step`: ceil to the step, with Python's floor division.
    let slot = -floor_div(-minute, step) * step;
    let slot = slot.max(i128::from(first));
    let (day, at) = if slot <= i128::from(last) {
        (0, slot)
    } else {
        (1, i128::from(first))
    };
    let at = i64::try_from(at).map_err(|_| EngineError::overflow("int too big"))?;
    Ok((day, at))
}

fn floor_div(numer: i128, denom: i128) -> i128 {
    let quotient = numer / denom;
    let remainder = numer % denom;
    if remainder != 0 && (numer < 0) != (denom < 0) {
        quotient - 1
    } else {
        quotient
    }
}

pub fn drag_step(chosen: Option<i64>) -> i64 {
    match chosen {
        Some(step) if DRAG_STEPS.contains(&step) => step,
        _ => DEFAULT_DRAG_STEP,
    }
}

pub fn overlap_columns(spans: &[(i64, i64)]) -> EngineResult<Vec<(i64, i64)>> {
    let mut order: Vec<usize> = (0..spans.len()).collect();
    order.sort_by(|&left, &right| spans[left].cmp(&spans[right]));
    let mut ends: Vec<i64> = Vec::new();
    let mut column = vec![0i64; spans.len()];
    for at in order {
        let start = spans[at].0;
        let free = ends
            .iter()
            .position(|end| *end <= start)
            .unwrap_or(ends.len());
        if free == ends.len() {
            ends.push(spans[at].1);
        } else {
            ends[free] = spans[at].1;
        }
        column[at] = free as i64;
    }
    let mut placed = Vec::with_capacity(spans.len());
    for (at, &(start, end)) in spans.iter().enumerate() {
        let mut widest: Option<i64> = None;
        for (other, &(other_start, other_end)) in spans.iter().enumerate() {
            if other_start < end && start < other_end {
                let column = column[other];
                widest = Some(widest.map_or(column, |so_far| so_far.max(column)));
            }
        }
        let widest =
            widest.ok_or_else(|| EngineError::value("max() iterable argument is empty"))?;
        placed.push((column[at], widest + 1));
    }
    Ok(placed)
}

pub struct Frame {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

pub struct Drawn {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

pub struct Lane {
    pub column: i64,
    pub columns: i64,
}

pub fn track_length(width: f64, height: f64, axis: &str) -> EngineResult<f64> {
    if axis_down(axis)? {
        Ok(height)
    } else {
        Ok(width)
    }
}

pub fn track_per_minute(
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
) -> EngineResult<f64> {
    per_minute(track_length(width, height, axis)?, first, last)
}

pub fn linear_offset(
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
    minute: f64,
) -> EngineResult<f64> {
    let per = per_minute(track_length(width, height, axis)?, first, last)?;
    Ok((minute - first as f64) * per)
}

pub fn linear_minute_at(
    frame: Frame,
    axis: &str,
    first: i64,
    last: i64,
    turn: f64,
    x: f64,
    y: f64,
) -> EngineResult<f64> {
    let (cx, cy) = center(&frame);
    let (local_x, local_y) = unrotate(cx, cy, turn, x, y);
    let along = if axis_down(axis)? {
        local_y - frame.y
    } else {
        local_x - frame.x
    };
    let per = per_minute(track_length(frame.width, frame.height, axis)?, first, last)?;
    Ok(first as f64 + along / per)
}

pub fn linear_contains(frame: Frame, turn: f64, x: f64, y: f64) -> bool {
    let (cx, cy) = center(&frame);
    let (local_x, local_y) = unrotate(cx, cy, turn, x, y);
    contains_frame(&frame, local_x, local_y)
}

pub fn linear_rect(
    frame: Frame,
    axis: &str,
    first: i64,
    last: i64,
    start: i64,
    end: i64,
    lane: Lane,
) -> EngineResult<Drawn> {
    if lane.columns == 0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    let start = start.max(first);
    let end = end.min(last);
    let per = per_minute(track_length(frame.width, frame.height, axis)?, first, last)?;
    let offset = |minute: i64| (minute - first) as f64 * per;
    let span = (offset(end) - offset(start) - BETWEEN).max(4.0);
    if axis_down(axis)? {
        let width = (frame.width - 2.0 * GAP) / lane.columns as f64;
        Ok(Drawn {
            x: frame.x + GAP + lane.column as f64 * width,
            y: frame.y + offset(start) + 1.0,
            width: width - GAP,
            height: span,
        })
    } else {
        let height = (frame.height - 2.0 * GAP) / lane.columns as f64;
        Ok(Drawn {
            x: frame.x + offset(start) + 1.0,
            y: frame.y + GAP + lane.column as f64 * height,
            width: span,
            height: height - GAP,
        })
    }
}

pub fn linear_point(
    frame: Frame,
    axis: &str,
    first: i64,
    last: i64,
    turn: f64,
    minute: i64,
) -> EngineResult<(f64, f64)> {
    let per = per_minute(track_length(frame.width, frame.height, axis)?, first, last)?;
    let along = (minute - first) as f64 * per;
    let upright = if axis_down(axis)? {
        (frame.x + frame.width / 2.0, frame.y + along)
    } else {
        (frame.x + along, frame.y + frame.height / 2.0)
    };
    let (cx, cy) = center(&frame);
    Ok(rotate(cx, cy, turn, upright.0, upright.1))
}

fn axis_down(axis: &str) -> EngineResult<bool> {
    match axis {
        "down" => Ok(true),
        "across" => Ok(false),
        _ => Err(EngineError::value("axis")),
    }
}

fn per_minute(length: f64, first: i64, last: i64) -> EngineResult<f64> {
    let span = last - first;
    if span == 0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    Ok(length / span as f64)
}

fn center(frame: &Frame) -> (f64, f64) {
    (frame.x + frame.width / 2.0, frame.y + frame.height / 2.0)
}

/// Qt's `QTransform.rotate` about a centre, with y still growing downward.
fn rotate(cx: f64, cy: f64, degrees: f64, x: f64, y: f64) -> (f64, f64) {
    let (sin, cos) = degrees.to_radians().sin_cos();
    let dx = x - cx;
    let dy = y - cy;
    (cx + dx * cos - dy * sin, cy + dx * sin + dy * cos)
}

fn unrotate(cx: f64, cy: f64, degrees: f64, x: f64, y: f64) -> (f64, f64) {
    rotate(cx, cy, -degrees, x, y)
}

/// `QRectF.contains` keeps every edge, and a zero width or height contains nothing.
fn contains_frame(frame: &Frame, x: f64, y: f64) -> bool {
    let (left, right) = edges(frame.x, frame.width);
    let (top, bottom) = edges(frame.y, frame.height);
    if left == right || top == bottom {
        return false;
    }
    x >= left && x <= right && y >= top && y <= bottom
}

fn edges(origin: f64, size: f64) -> (f64, f64) {
    if size < 0.0 {
        (origin + size, origin)
    } else {
        (origin, origin + size)
    }
}

pub struct Ring {
    pub x: f64,
    pub y: f64,
    pub inner: f64,
    pub outer: f64,
    pub first: i64,
    pub last: i64,
    pub sweep: f64,
}

pub fn dial_turn(ring: &Ring, x: f64, y: f64) -> f64 {
    let dx = x - ring.x;
    let dy = y - ring.y;
    dx.atan2(-dy).to_degrees()
}

pub fn dial_minute(ring: &Ring, x: f64, y: f64) -> EngineResult<f64> {
    if ring.sweep == 0.0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    let half = ring.sweep / 2.0;
    let turn = dial_turn(ring, x, y).clamp(-half, half);
    let span = ring.last - ring.first;
    Ok(ring.first as f64 + (turn + half) / ring.sweep * span as f64)
}

pub fn dial_contains(ring: &Ring, x: f64, y: f64) -> bool {
    let dx = x - ring.x;
    let dy = y - ring.y;
    let reach = dx.hypot(dy);
    ring.inner <= reach && reach <= ring.outer && dial_turn(ring, x, y).abs() <= ring.sweep / 2.0
}

pub fn dial_point(ring: &Ring, minute: i64) -> EngineResult<(f64, f64)> {
    let span = ring.last - ring.first;
    if span == 0 {
        return Err(EngineError::zero_division("division by zero"));
    }
    let clamped = minute.max(ring.first).min(ring.last);
    let share = (clamped - ring.first) as f64 / span as f64;
    let turn = (-ring.sweep / 2.0 + share * ring.sweep).to_radians();
    let radius = (ring.inner + ring.outer) / 2.0;
    Ok((ring.x + radius * turn.sin(), ring.y - radius * turn.cos()))
}

pub fn scale_key_ok(key: &str) -> bool {
    let Some((left, right)) = key.split_once('.') else {
        return false;
    };
    !left.is_empty()
        && !right.is_empty()
        && !right.contains('.')
        && left.bytes().all(|byte| byte.is_ascii_lowercase())
        && right.bytes().all(|byte| byte.is_ascii_lowercase())
}

pub fn scale_check(key: &str) -> Result<(), String> {
    if scale_key_ok(key) && key.chars().count() <= 40 {
        Ok(())
    } else {
        Err(format!(
            "{} cannot be kept in the look file: use design.surface, a to z",
            py_repr(key)
        ))
    }
}

pub enum Pixel {
    Absent,
    Number(i128),
    High,
    Low,
}

pub fn nearest(levels: &[i64], default: i64, px: Pixel) -> Result<i64, String> {
    let number = match px {
        Pixel::Absent => return Ok(default),
        Pixel::High => return extreme(levels, true),
        Pixel::Low => return extreme(levels, false),
        Pixel::Number(number) => number,
    };
    levels
        .iter()
        .copied()
        .min_by_key(|level| ((*level as i128).abs_diff(number), *level))
        .ok_or_else(|| "min() iterable argument is empty".to_string())
}

fn extreme(levels: &[i64], high: bool) -> Result<i64, String> {
    let found = if high {
        levels.iter().copied().max()
    } else {
        levels.iter().copied().min()
    };
    found.ok_or_else(|| "min() iterable argument is empty".to_string())
}

pub fn step(levels: &[i64], default: i64, px: Pixel, by: i64) -> Result<i64, String> {
    let near = nearest(levels, default, px)?;
    let at = levels
        .iter()
        .position(|level| *level == near)
        .ok_or_else(|| "tuple.index(x): x not in tuple".to_string())?;
    let last = levels.len() as i64 - 1;
    let index = (at as i64).saturating_add(by).clamp(0, last);
    Ok(levels[index as usize])
}

pub fn opening_minute(
    today: Option<i64>,
    now: Option<i64>,
    day: Option<i64>,
    starts: &[i64],
    day_starts: Option<&[i64]>,
) -> i64 {
    if let (Some(today), Some(now)) = (today, now)
        && (day.is_none() || day == Some(today))
    {
        return now;
    }
    let items = if day.is_none() {
        starts
    } else {
        day_starts.unwrap_or(&[])
    };
    items.iter().copied().min().unwrap_or(OPENS)
}

pub fn short_length(minutes: i64) -> String {
    let minutes = minutes.max(0);
    let hours = minutes / 60;
    let rest = minutes % 60;
    if hours == 0 {
        format!("{rest} min")
    } else if rest == 0 {
        format!("{hours}h")
    } else {
        format!("{hours}h {rest}m")
    }
}

pub fn sanitize_zoom(pairs: &[(Option<String>, Option<i64>)]) -> Vec<(String, i64)> {
    let mut clean = Vec::new();
    for (key, px) in pairs {
        if clean.len() >= 32 {
            break;
        }
        let (Some(key), Some(px)) = (key, px) else {
            continue;
        };
        if key.chars().count() > 40 || !scale_key_ok(key) || !(8..=480).contains(px) {
            continue;
        }
        clean.push((key.clone(), *px));
    }
    clean
}

pub fn read_clock(text: &str, end: bool, whole: bool) -> Option<i64> {
    let lowered = text.trim().to_lowercase();
    let (mut hour, minute, half) = parse_written(&lowered)?;
    if whole && minute.is_none() {
        return None;
    }
    let minute = minute.unwrap_or(0);
    if minute > 59 {
        return None;
    }
    if let Some(half) = half {
        if !(1..=12).contains(&hour) {
            return None;
        }
        let shift = if half == 'p' { 12 } else { 0 };
        hour = hour % 12 + shift;
    }
    let total = hour * 60 + minute;
    if total == END_OF_DAY {
        return end.then_some(END_OF_DAY);
    }
    if hour > 23 {
        return None;
    }
    if end && total == 0 {
        Some(END_OF_DAY)
    } else {
        Some(total)
    }
}

fn parse_written(text: &str) -> Option<(i64, Option<i64>, Option<char>)> {
    let chars: Vec<char> = text.chars().collect();
    for hour_len in [2, 1] {
        if let Some(found) = parse_hour(&chars, hour_len) {
            return Some(found);
        }
    }
    None
}

fn parse_hour(chars: &[char], hour_len: usize) -> Option<(i64, Option<i64>, Option<char>)> {
    if chars.len() < hour_len || !chars[..hour_len].iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let hour = chars[..hour_len].iter().collect::<String>().parse().ok()?;
    if let Some((minute, at)) = take_minutes(chars, hour_len)
        && let Some(half) = finish(chars, at)
    {
        return Some((hour, Some(minute), half));
    }
    finish(chars, hour_len).map(|half| (hour, None, half))
}

fn take_minutes(chars: &[char], start: usize) -> Option<(i64, usize)> {
    let mut at = start;
    if chars.get(at) == Some(&':') {
        at += 1;
    }
    let tens = chars.get(at)?.to_digit(10)?;
    let ones = chars.get(at + 1)?.to_digit(10)?;
    Some((i64::from(tens * 10 + ones), at + 2))
}

fn finish(chars: &[char], start: usize) -> Option<Option<char>> {
    let mut at = start;
    while chars.get(at).is_some_and(|ch| ch.is_whitespace()) {
        at += 1;
    }
    if at == chars.len() {
        return Some(None);
    }
    let half = *chars.get(at)?;
    if half != 'a' && half != 'p' {
        return None;
    }
    at += 1;
    if chars.get(at) == Some(&'.') {
        at += 1;
    }
    if chars.get(at) == Some(&'m') {
        at += 1;
        if chars.get(at) == Some(&'.') {
            at += 1;
        }
    }
    (at == chars.len()).then_some(Some(half))
}

pub fn accepted_week_start(value: Option<&str>) -> &'static str {
    value
        .and_then(|name| WEEK_STARTS.iter().find(|day| **day == name).copied())
        .unwrap_or("monday")
}

pub fn week_start_day(name: &str) -> i64 {
    WEEK_STARTS
        .iter()
        .position(|day| *day == name)
        .map_or(0, |index| index as i64)
}

// The four flags are one block's own fields. Packing them would hide which one the caller read.
#[allow(clippy::fn_params_excessive_bools)]
pub fn plan_placed(work: bool, pinned: bool, done: bool, missed: bool) -> bool {
    work && !pinned && !done && !missed
}

pub fn tag_words(history: &str, placed_by_plan: bool) -> Vec<String> {
    let mut tags = Vec::new();
    if history == "Overdue" {
        tags.push("Overdue".to_string());
    }
    if history == "Left from last week" {
        tags.push("Left from last week".to_string());
    }
    if placed_by_plan {
        tags.push("Placed by Plan".to_string());
    }
    tags
}

pub fn length_words(minutes: i64, done: bool, missed: bool) -> String {
    let mut words = length_label(minutes);
    if done {
        words.push_str(" · Finished");
    }
    if missed {
        words.push_str(" · Missed");
    }
    words
}

// Done, missed, pinned and placed are the block's own flags, kept together so a sentence takes one argument.
#[allow(clippy::struct_excessive_bools)]
pub struct BlockWords<'a> {
    pub done: bool,
    pub missed: bool,
    pub pinned: bool,
    pub history: &'a str,
    pub history_due: Option<&'a str>,
    pub placed_by_plan: bool,
}

pub fn tail_words(words: &str, block: BlockWords<'_>) -> String {
    let mut words = words.to_string();
    for mut tag in tag_words(block.history, block.placed_by_plan) {
        if tag.starts_with("Overdue")
            && let Some(due) = block.history_due.filter(|due| !due.is_empty())
            && let Some(when) = overdue_date(due)
        {
            tag = format!("{tag}, was due {when}");
        }
        words.push_str(" · ");
        words.push_str(&tag);
    }
    if block.pinned && !block.done {
        words.push_str(" · Pinned");
    }
    words
}

pub fn detail_words(start: i64, end: i64, block: BlockWords<'_>) -> String {
    let line = format!(
        "{} · {}",
        range_label(start, end),
        length_words(end - start, block.done, block.missed)
    );
    tail_words(&line, block)
}

fn overdue_date(history_due: &str) -> Option<String> {
    let head: String = history_due.chars().take(10).collect();
    let date = day_of(&head).ok()?;
    Some(day_short(date, date))
}

pub fn end_after_start_words(start: &str) -> String {
    format!("End needs to be later than Start ({start}).")
}

pub fn homework_time_sentence(left_over: &str, needed: &str) -> Result<String, String> {
    let left = json_list(left_over, "left_over")?;
    let needed = json_list(needed, "needed")?;
    crate::session::plan::homework_time_sentence(&left, &needed)
}

fn json_list(text: &str, name: &str) -> Result<Vec<Value>, String> {
    let value: Value = serde_json::from_str(text).map_err(|err| err.to_string())?;
    value
        .as_array()
        .cloned()
        .ok_or_else(|| format!("{name} must be a list"))
}

pub struct Moment {
    pub year: i32,
    pub month: i32,
    pub day: i32,
    pub hour: i32,
    pub minute: i32,
    pub second: i32,
    pub micro: i32,
}

pub fn overdue_indexes(dues: &[Option<&str>], now: &Moment) -> Vec<usize> {
    dues.iter()
        .enumerate()
        .filter_map(|(index, due)| {
            let due = due.filter(|text| !text.is_empty())?;
            passed(due, now).then_some(index)
        })
        .collect()
}

fn passed(due: &str, now: &Moment) -> bool {
    let Ok((date, minute)) = parse_due(due) else {
        return false;
    };
    let extra = minute.div_euclid(END_OF_DAY);
    let rest = minute.rem_euclid(END_OF_DAY);
    let date = if extra == 0 {
        date
    } else {
        let Ok(shifted) = add_days(date, extra) else {
            return false;
        };
        shifted
    };
    let Some((year, month, day)) = ymd_of(&date) else {
        return false;
    };
    let deadline = (
        year,
        month,
        day,
        (rest / 60) as i32,
        (rest % 60) as i32,
        0,
        0,
    );
    let moment = (
        now.year, now.month, now.day, now.hour, now.minute, now.second, now.micro,
    );
    deadline <= moment
}

fn ymd_of(date: &impl std::fmt::Display) -> Option<(i32, i32, i32)> {
    let text = date.to_string();
    if text.len() < 10 {
        return None;
    }
    Some((
        text[0..4].parse().ok()?,
        text[5..7].parse().ok()?,
        text[8..10].parse().ok()?,
    ))
}

fn py_repr(text: &str) -> String {
    let mut out = String::from("'");
    for ch in text.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '\'' => out.push_str("\\'"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(ch),
        }
    }
    out.push('\'');
    out
}
