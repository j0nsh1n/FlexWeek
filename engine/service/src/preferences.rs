//! Preferences as `backend/app.py`'s `Preferences` model accepts and writes them: every field and its
//! default, the alarms, protected windows, Study hours and setup progress inside it, older clients'
//! preferred study hours folded into Study hours, the rules between fields, unknown fields refused, and
//! the written preferences with each default left out where the model leaves it out, in its field order.
//! `tests/preferences_parity.rs` holds it to pydantic.

use std::collections::BTreeSet;

use flexweek_engine::model::valid_spotify_url;
use flexweek_engine::plan::fold_study_windows;
use flexweek_engine::time::{
    clock_to_minutes, decimal_digit, on_slot, span_fits_day, start_fits_day,
};
use serde_json::{Map, Value};

use crate::blocks::{
    BlockRefused, Checked, bool_field, defaulted, int_field, one_of, optional, refuse, text_field,
    whole_number,
};

const TONES: [&str; 6] = ["chime", "soft", "bright", "low", "glass", "spotify"];

type Fields<'a> = &'a Map<String, Value>;

fn object<'a>(value: &'a Value, name: &str, allowed: &[&str]) -> Checked<Fields<'a>> {
    let Value::Object(fields) = value else {
        return refuse(format!("{name} must be an object"));
    };
    if let Some(extra) = fields.keys().find(|key| !allowed.contains(&key.as_str())) {
        return refuse(format!("{name} does not take {extra}"));
    }
    Ok(fields)
}

fn required<'a>(fields: Fields<'a>, name: &str) -> Checked<&'a Value> {
    fields
        .get(name)
        .ok_or_else(|| BlockRefused(format!("{name} is required")))
}

/// Whole-number days, 1 to 7 of them, each 0..6 and none twice.
fn unique_days(value: &Value, name: &str) -> Checked<Vec<i64>> {
    let Value::Array(items) = value else {
        return refuse(format!("{name} must be a list"));
    };
    if !(1..=7).contains(&items.len()) {
        return refuse(format!("{name} must hold 1 to 7 days"));
    }
    let days: Option<Vec<i64>> = items
        .iter()
        .map(|item| whole_number(item).and_then(|day| i64::try_from(day).ok()))
        .collect();
    let Some(days) = days else {
        return refuse(format!("{name} must be whole numbers"));
    };
    let unique: BTreeSet<_> = days.iter().collect();
    if unique.len() != days.len() || days.iter().any(|day| !(0..=6).contains(day)) {
        return refuse(format!("{name} must be unique values in 0..6"));
    }
    Ok(days)
}

/// Python's `\d`: any Unicode decimal digit, which `int()` then reads.
fn digit(ch: char) -> bool {
    decimal_digit(ch).is_some()
}

/// `(?:[01]\d|2[0-3]):[0-5]\d` matched against all of `text`: the bracketed ranges are ASCII, `\d` is
/// any Unicode decimal digit, as in Python's and pydantic's patterns.
fn hhmm(text: &str) -> bool {
    let chars: Vec<char> = text.chars().collect();
    chars.len() == 5
        && chars[2] == ':'
        && match chars[0] {
            '0' | '1' => digit(chars[1]),
            '2' => ('0'..='3').contains(&chars[1]),
            _ => false,
        }
        && ('0'..='5').contains(&chars[3])
        && digit(chars[4])
}

/// Python's truthiness for a JSON value: `value or []` keeps only a truthy one.
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(number) => number.as_f64().is_some_and(|n| n != 0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(fields) => !fields.is_empty(),
    }
}

fn minutes(text: &str) -> i64 {
    clock_to_minutes(text).unwrap_or(-1)
}

/// The minute of the day `HH:MM` names, read as Python's pattern and `int()` read it; None when it is not
/// `HH:MM`.
pub(crate) fn grid_minutes(text: &str) -> Option<i64> {
    hhmm(text).then(|| minutes(text))
}

/// A start on the 15-minute grid, as GridWindow and WorkWindow read it.
fn grid_start(value: &Value) -> Checked<String> {
    let start = text_field(value, "start", 5, 5)?;
    if !hhmm(&start) {
        return refuse("start must be HH:MM");
    }
    let at = minutes(&start);
    if !(start_fits_day(at) && on_slot(at)) {
        return refuse("start must be on the 00:00-24:00 grid");
    }
    Ok(start)
}

/// days, start, duration_min: the part ProtectedWindow and the older StudyWindow share.
fn grid_window(fields: Fields<'_>) -> Checked<(Vec<i64>, String, i64)> {
    let days = unique_days(required(fields, "days")?, "days")?;
    let start = grid_start(required(fields, "start")?)?;
    // Both bounds before narrowing: a negative past 64 bits must not wrap into a positive length.
    let duration = match whole_number(required(fields, "duration_min")?) {
        Some(minutes) if (1..=7140).contains(&minutes) => minutes as i64,
        Some(minutes) if minutes <= 7140 => {
            return refuse("duration_min must be a positive multiple of 15");
        }
        _ => return refuse("duration_min must be a whole number up to 7140"),
    };
    if !on_slot(duration) {
        return refuse("duration_min must be a positive multiple of 15");
    }
    if !span_fits_day(minutes(&start), duration) {
        return refuse("window must fit the 00:00-24:00 grid");
    }
    Ok((days, start, duration))
}

fn trimmed_subject(value: Option<&Value>) -> Checked<Option<String>> {
    let Some(subject) = optional(value, |v| text_field(v, "subject", 1, 40))? else {
        return Ok(None);
    };
    let trimmed = subject.trim().to_string();
    if trimmed.is_empty() {
        return refuse("subject must not be blank");
    }
    Ok(Some(trimmed))
}

pub(crate) fn study_window(value: &Value) -> Checked<Value> {
    let fields = object(
        value,
        "a study window",
        &["days", "start", "duration_min", "subject"],
    )?;
    let (days, start, duration) = grid_window(fields)?;
    let subject = trimmed_subject(fields.get("subject"))?;
    let mut out = Map::new();
    out.insert("days".into(), Value::from(days));
    out.insert("start".into(), Value::String(start));
    out.insert("duration_min".into(), Value::from(duration));
    if let Some(subject) = subject {
        out.insert("subject".into(), Value::String(subject));
    }
    Ok(Value::Object(out))
}

pub(crate) fn work_window(value: &Value) -> Checked<Value> {
    let fields = object(
        value,
        "a study hours window",
        &["days", "start", "end", "subject"],
    )?;
    let days = unique_days(required(fields, "days")?, "days")?;
    let start = grid_start(required(fields, "start")?)?;
    let end = text_field(required(fields, "end")?, "end", 5, 5)?;
    if !(hhmm(&end) || end == "24:00") {
        return refuse("end must be HH:MM, or 24:00");
    }
    let end_at = minutes(&end);
    if !on_slot(end_at) || end_at <= 0 || end_at > 24 * 60 {
        return refuse("end must be on the 00:00-24:00 grid");
    }
    let subject = trimmed_subject(fields.get("subject"))?;
    if end_at <= minutes(&start) {
        return refuse("end must be after start");
    }
    let mut out = Map::new();
    out.insert("days".into(), Value::from(days));
    out.insert("start".into(), Value::String(start));
    out.insert("end".into(), Value::String(end));
    if let Some(subject) = subject {
        out.insert("subject".into(), Value::String(subject));
    }
    Ok(Value::Object(out))
}

pub(crate) fn protected_window(value: &Value) -> Checked<Value> {
    let fields = object(
        value,
        "a protected window",
        &["days", "start", "duration_min", "kind", "title"],
    )?;
    let (days, start, duration) = grid_window(fields)?;
    let kind = one_of(
        required(fields, "kind")?,
        "kind",
        &["downtime", "commute", "meal"],
    )?;
    // The title is trimmed first, and a blank one counts as none.
    let title = match fields.get("title") {
        Some(Value::String(text)) => {
            let trimmed = text.trim();
            if trimmed.is_empty() {
                None
            } else {
                Some(text_field(&Value::from(trimmed), "title", 0, 40)?)
            }
        }
        other => optional(other, |v| text_field(v, "title", 0, 40))?,
    };
    let mut out = Map::new();
    out.insert("days".into(), Value::from(days));
    out.insert("start".into(), Value::String(start));
    out.insert("duration_min".into(), Value::from(duration));
    out.insert("kind".into(), Value::String(kind));
    if let Some(title) = title {
        out.insert("title".into(), Value::String(title));
    }
    Ok(Value::Object(out))
}

fn alarm(value: &Value) -> Checked<Value> {
    let fields = object(
        value,
        "an alarm",
        &[
            "id",
            "name",
            "time",
            "days",
            "enabled",
            "sound",
            "spotify_url",
        ],
    )?;
    let id = text_field(required(fields, "id")?, "id", 1, 80)?;
    let name = text_field(required(fields, "name")?, "name", 1, 80)?;
    let time = text_field(required(fields, "time")?, "time", 0, usize::MAX)?;
    // pydantic's pattern is searched for anywhere in the text, not matched against all of it.
    let chars: Vec<char> = time.chars().collect();
    if !chars
        .windows(5)
        .any(|window| hhmm(&window.iter().collect::<String>()))
    {
        return refuse("time must hold HH:MM");
    }
    let mut days = unique_days(required(fields, "days")?, "days")?;
    days.sort_unstable();
    let enabled = defaulted(fields.get("enabled"), true, |v| bool_field(v, "enabled"))?;
    let sound = defaulted(fields.get("sound"), "chime".to_string(), |v| {
        one_of(v, "sound", &TONES)
    })?;
    let spotify_url = spotify(fields.get("spotify_url"))?;
    let mut out = Map::new();
    out.insert("id".into(), Value::String(id));
    out.insert("name".into(), Value::String(name));
    out.insert("time".into(), Value::String(time));
    out.insert("days".into(), Value::from(days));
    out.insert("enabled".into(), Value::Bool(enabled));
    out.insert("sound".into(), Value::String(sound));
    out.insert(
        "spotify_url".into(),
        spotify_url.map_or(Value::Null, Value::String),
    );
    Ok(Value::Object(out))
}

fn spotify(value: Option<&Value>) -> Checked<Option<String>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) if text.chars().count() <= 500 => {
            valid_spotify_url(Some(text)).map_err(|error| BlockRefused(error.message))
        }
        Some(_) => refuse("spotify_url must be an open.spotify.com share link"),
    }
}

fn setup(value: &Value) -> Checked<Value> {
    let fields = object(value, "setup", &["version", "step", "finished_at"])?;
    let version = int_field(required(fields, "version")?, "version", 1, 100)?;
    let step = defaulted(fields.get("step"), 0, |v| int_field(v, "step", 0, 20))?;
    let finished_at = optional(fields.get("finished_at"), |v| {
        text_field(v, "finished_at", 0, 32)
    })?;
    if let Some(stamp) = &finished_at {
        // \d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})? with Python's Unicode \d.
        let chars: Vec<char> = stamp.chars().collect();
        let digits = |range: std::ops::Range<usize>| range.into_iter().all(|at| digit(chars[at]));
        let minute_form = chars.len() == 16;
        let second_form = chars.len() == 19 && chars[16] == ':' && digits(17..19);
        let ok = (minute_form || second_form)
            && digits(0..4)
            && chars[4] == '-'
            && digits(5..7)
            && chars[7] == '-'
            && digits(8..10)
            && chars[10] == 'T'
            && digits(11..13)
            && chars[13] == ':'
            && digits(14..16);
        if !ok {
            return refuse("finished_at must be YYYY-MM-DDTHH:MM");
        }
    }
    let mut out = Map::new();
    out.insert("version".into(), Value::from(version));
    out.insert("step".into(), Value::from(step));
    out.insert(
        "finished_at".into(),
        finished_at.map_or(Value::Null, Value::String),
    );
    Ok(Value::Object(out))
}

fn list_of(
    value: Option<&Value>,
    name: &str,
    most: usize,
    read: fn(&Value) -> Checked<Value>,
) -> Checked<Vec<Value>> {
    match value {
        None => Ok(Vec::new()),
        Some(Value::Array(items)) if items.len() <= most => items.iter().map(read).collect(),
        Some(_) => refuse(format!("{name} must be a list of at most {most}")),
    }
}

fn literal_int(value: Option<&Value>, name: &str, default: i64, allowed: &[i64]) -> Checked<i64> {
    let Some(value) = value else {
        return Ok(default);
    };
    let read = match value {
        Value::Bool(_) | Value::Number(_) => whole_number(value),
        _ => None,
    };
    match read.and_then(|level| i64::try_from(level).ok()) {
        Some(level) if allowed.contains(&level) => Ok(level),
        _ => refuse(format!("{name} must be one of {allowed:?}")),
    }
}

/// The preference fields, in their order (unknown fields are refused). The desktop reads them too.
pub const FIELDS: &[&str] = &[
    "theme",
    "reminders_enabled",
    "reminder_lead_min",
    "reminder_sound",
    "reminder_dnd_override",
    "timer_work_min",
    "timer_break_min",
    "timer_long_break_min",
    "timer_long_break_every",
    "auto_split_pomodoro",
    "default_spotify_url",
    "alarms",
    "protected",
    "work_windows",
    "day_cutoff",
    "weekend_homework_free",
    "buffer_min",
    "urgent_first",
    "split_long_tasks",
    "show_weekends",
    "alert_volume",
    "end_chime",
    "tray_notifications",
    "start_at_login",
    "preferred_view",
    "sidebar_collapsed",
    "sidebar_width_px",
    "theme_pack",
    "accent",
    "accent_chips",
    "motion",
    "alarm_tone",
    "planning_style",
    "drag_step_min",
    "clock_24h",
    "focus_audio",
    "focus_auto_mute",
    "focus_auto_complete",
    "setup",
];

/// The preferences as `Preferences.model_validate(value).model_dump()` gives them, or why pydantic
/// refuses them.
pub fn check_preferences(value: &Value) -> Checked<Value> {
    let Value::Object(given) = value else {
        return refuse("preferences must be an object");
    };
    let mut input = given.clone();
    // Older clients and export files send preferred study hours; they join Study hours first.
    if let Some(study) = input.shift_remove("study_windows") {
        // `data.pop("study_windows") or []`: anything falsy is no study hours.
        let study = match study {
            falsy if !truthy(&falsy) => Vec::new(),
            Value::Array(items) => items
                .iter()
                .map(study_window)
                .collect::<Checked<Vec<_>>>()?,
            _ => return refuse("study_windows must be a list"),
        };
        if !study.is_empty() {
            let work = match input.get("work_windows") {
                None => Vec::new(),
                Some(falsy) if !truthy(falsy) => Vec::new(),
                Some(Value::Array(items)) => {
                    items.iter().map(work_window).collect::<Checked<Vec<_>>>()?
                }
                Some(_) => return refuse("work_windows must be a list"),
            };
            let folded =
                fold_study_windows(&work, &study).map_err(|error| BlockRefused(error.message))?;
            input.insert("work_windows".into(), Value::Array(folded));
        }
    }
    if let Some(extra) = input.keys().find(|key| !FIELDS.contains(&key.as_str())) {
        return refuse(format!("preferences do not take {extra}"));
    }
    let get = |name: &str| input.get(name);
    let flag = |name: &str, default: bool| defaulted(get(name), default, |v| bool_field(v, name));
    let number = |name: &str, default: i64, low: i128, high: i128| {
        defaulted(get(name), default, |v| int_field(v, name, low, high))
    };
    let choice = |name: &str, default: &str, allowed: &[&str]| {
        defaulted(get(name), default.to_string(), |v| one_of(v, name, allowed))
    };

    let theme = one_of(
        get("theme").ok_or_else(|| BlockRefused("theme is required".into()))?,
        "theme",
        &["system", "slate", "nocturne"],
    )?;
    let reminders_enabled = flag("reminders_enabled", true)?;
    let reminder_lead_min = number("reminder_lead_min", 5, 0, 120)?;
    let reminder_sound = flag("reminder_sound", true)?;
    let reminder_dnd_override = flag("reminder_dnd_override", false)?;
    let timer_work_min = number("timer_work_min", 30, 1, 180)?;
    let timer_break_min = number("timer_break_min", 15, 1, 60)?;
    let timer_long_break_min = number("timer_long_break_min", 30, 1, 120)?;
    let timer_long_break_every = number("timer_long_break_every", 4, 2, 12)?;
    let auto_split_pomodoro = flag("auto_split_pomodoro", false)?;
    let default_spotify_url = spotify(get("default_spotify_url"))?;
    let alarms = list_of(get("alarms"), "alarms", 20, alarm)?;
    let protected = list_of(get("protected"), "protected", 21, protected_window)?;
    let work_windows = list_of(get("work_windows"), "work_windows", 21, work_window)?;
    let day_cutoff = optional(get("day_cutoff"), |v| {
        text_field(v, "day_cutoff", 0, usize::MAX)
    })?;
    if let Some(cutoff) = &day_cutoff {
        if !hhmm(cutoff) {
            return refuse("day_cutoff must be HH:MM on the 15-minute grid");
        }
        let at = minutes(cutoff);
        if at % 15 != 0 || !(15..=24 * 60 - 15).contains(&at) {
            return refuse("day_cutoff must be between 00:15 and 23:45 on the 15-minute grid");
        }
    }
    let weekend_homework_free = flag("weekend_homework_free", false)?;
    let buffer_min = literal_int(get("buffer_min"), "buffer_min", 15, &[0, 15, 30])?;
    let urgent_first = flag("urgent_first", true)?;
    let split_long_tasks = flag("split_long_tasks", false)?;
    let show_weekends = flag("show_weekends", true)?;
    let alert_volume = number("alert_volume", 80, 0, 100)?;
    let end_chime = flag("end_chime", false)?;
    let tray_notifications = flag("tray_notifications", true)?;
    let start_at_login = flag("start_at_login", false)?;
    let preferred_view = optional(get("preferred_view"), |v| {
        one_of(v, "preferred_view", &["week", "day", "month", "myday"])
    })?;
    let sidebar_collapsed = flag("sidebar_collapsed", false)?;
    let sidebar_width_px = optional(get("sidebar_width_px"), |v| {
        int_field(v, "sidebar_width_px", 200, 640)
    })?;
    let theme_pack = choice(
        "theme_pack",
        "system",
        &["system", "light-frost", "dark-frost", "nocturne", "slate"],
    )?;
    let accent = choice(
        "accent",
        "default",
        &["default", "sky", "gold", "sea", "sand"],
    )?;
    let accent_chips = flag("accent_chips", false)?;
    let motion = optional(get("motion"), |v| {
        one_of(v, "motion", &["off", "normal", "extra", "reduce"])
    })?;
    let alarm_tone = choice("alarm_tone", "chime", &TONES)?;
    let planning_style = choice("planning_style", "suggest", &["auto", "suggest", "manual"])?;
    let drag_step_min = literal_int(get("drag_step_min"), "drag_step_min", 15, &[5, 15])?;
    let clock_24h = flag("clock_24h", false)?;
    let focus_audio = choice(
        "focus_audio",
        "off",
        &["off", "rain", "lo-fi", "white-noise", "spotify"],
    )?;
    let focus_auto_mute = flag("focus_auto_mute", true)?;
    let focus_auto_complete = flag("focus_auto_complete", false)?;
    let setup = optional(get("setup"), setup)?;

    // The rules between fields, in the model's order.
    for day in 0..7 {
        let mut taken: Vec<(i64, i64)> = Vec::new();
        for window in &protected {
            if !window["days"]
                .as_array()
                .is_some_and(|days| days.contains(&Value::from(day)))
            {
                continue;
            }
            let start = minutes(window["start"].as_str().unwrap_or(""));
            let end = start + window["duration_min"].as_i64().unwrap_or(0);
            if taken
                .iter()
                .any(|(other_start, other_end)| start < *other_end && *other_start < end)
            {
                return refuse("protected windows must not overlap on a shared day");
            }
            taken.push((start, end));
        }
    }
    if auto_split_pomodoro
        && [timer_work_min, timer_break_min, timer_long_break_min]
            .iter()
            .any(|length| length % 15 != 0)
    {
        return refuse("auto_split_pomodoro needs 15-minute work and break lengths");
    }
    if theme_pack != "system" {
        let axis = if theme_pack == "light-frost" || theme_pack == "slate" {
            "slate"
        } else {
            "nocturne"
        };
        if theme != axis {
            return refuse("theme_pack needs theme on the same light or dark axis");
        }
    }

    let mut out = Map::new();
    let mut put = |name: &str, value: Value| {
        out.insert(name.into(), value);
    };
    put("theme", Value::String(theme));
    put("reminders_enabled", Value::Bool(reminders_enabled));
    put("reminder_lead_min", Value::from(reminder_lead_min));
    put("reminder_sound", Value::Bool(reminder_sound));
    put("reminder_dnd_override", Value::Bool(reminder_dnd_override));
    put("timer_work_min", Value::from(timer_work_min));
    put("timer_break_min", Value::from(timer_break_min));
    put("timer_long_break_min", Value::from(timer_long_break_min));
    put(
        "timer_long_break_every",
        Value::from(timer_long_break_every),
    );
    put("auto_split_pomodoro", Value::Bool(auto_split_pomodoro));
    put(
        "default_spotify_url",
        default_spotify_url.map_or(Value::Null, Value::String),
    );
    put("alarms", Value::Array(alarms));
    // From here on a value at its default is left out, as the model's exclude_if rules say.
    if !protected.is_empty() {
        put("protected", Value::Array(protected));
    }
    if !work_windows.is_empty() {
        put("work_windows", Value::Array(work_windows));
    }
    if let Some(cutoff) = day_cutoff {
        put("day_cutoff", Value::String(cutoff));
    }
    if weekend_homework_free {
        put("weekend_homework_free", Value::Bool(true));
    }
    if buffer_min != 15 {
        put("buffer_min", Value::from(buffer_min));
    }
    if !urgent_first {
        put("urgent_first", Value::Bool(false));
    }
    if split_long_tasks {
        put("split_long_tasks", Value::Bool(true));
    }
    if !show_weekends {
        put("show_weekends", Value::Bool(false));
    }
    if alert_volume != 80 {
        put("alert_volume", Value::from(alert_volume));
    }
    for (name, value, default) in [
        ("end_chime", end_chime, false),
        ("tray_notifications", tray_notifications, true),
        ("start_at_login", start_at_login, false),
    ] {
        if value != default {
            put(name, Value::Bool(value));
        }
    }
    if let Some(view) = preferred_view {
        put("preferred_view", Value::String(view));
    }
    if sidebar_collapsed {
        put("sidebar_collapsed", Value::Bool(true));
    }
    if let Some(width) = sidebar_width_px {
        put("sidebar_width_px", Value::from(width));
    }
    for (name, value, default) in [
        ("theme_pack", &theme_pack, "system"),
        ("accent", &accent, "default"),
    ] {
        if value != default {
            put(name, Value::String(value.clone()));
        }
    }
    if accent_chips {
        put("accent_chips", Value::Bool(true));
    }
    if let Some(motion) = motion {
        put("motion", Value::String(motion));
    }
    for (name, value, default) in [
        ("alarm_tone", &alarm_tone, "chime"),
        ("planning_style", &planning_style, "suggest"),
    ] {
        if value != default {
            put(name, Value::String(value.clone()));
        }
    }
    if drag_step_min != 15 {
        put("drag_step_min", Value::from(drag_step_min));
    }
    if clock_24h {
        put("clock_24h", Value::Bool(true));
    }
    if focus_audio != "off" {
        put("focus_audio", Value::String(focus_audio));
    }
    if !focus_auto_mute {
        put("focus_auto_mute", Value::Bool(false));
    }
    if focus_auto_complete {
        put("focus_auto_complete", Value::Bool(true));
    }
    if let Some(setup) = setup {
        put("setup", setup);
    }
    Ok(Value::Object(out))
}

/// What `check_preferences` leaves out at its default, put back: the store keeps every value.
fn with_defaults(written: &Value) -> Map<String, Value> {
    let mut full = written.as_object().cloned().unwrap_or_default();
    let defaults: [(&str, Value); 26] = [
        ("protected", Value::Array(Vec::new())),
        ("work_windows", Value::Array(Vec::new())),
        ("day_cutoff", Value::Null),
        ("weekend_homework_free", Value::Bool(false)),
        ("buffer_min", Value::from(15)),
        ("urgent_first", Value::Bool(true)),
        ("split_long_tasks", Value::Bool(false)),
        ("show_weekends", Value::Bool(true)),
        ("alert_volume", Value::from(80)),
        ("end_chime", Value::Bool(false)),
        ("tray_notifications", Value::Bool(true)),
        ("start_at_login", Value::Bool(false)),
        ("preferred_view", Value::Null),
        ("sidebar_collapsed", Value::Bool(false)),
        ("sidebar_width_px", Value::Null),
        ("theme_pack", Value::from("system")),
        ("accent", Value::from("default")),
        ("accent_chips", Value::Bool(false)),
        ("motion", Value::Null),
        ("alarm_tone", Value::from("chime")),
        ("planning_style", Value::from("suggest")),
        ("drag_step_min", Value::from(15)),
        ("clock_24h", Value::Bool(false)),
        ("focus_audio", Value::from("off")),
        ("focus_auto_mute", Value::Bool(true)),
        ("focus_auto_complete", Value::Bool(false)),
    ];
    for (name, value) in defaults {
        full.entry(name.to_string()).or_insert(value);
    }
    full.entry("setup".to_string()).or_insert(Value::Null);
    full
}

/// The columns `backend/app.py`'s write_preferences stores, from checked preferences.
fn stored_columns(written: &Value) -> Value {
    use flexweek_engine::snapshot::dumps_compact;
    let full = with_defaults(written);
    let get = |name: &str| full.get(name).cloned().unwrap_or(Value::Null);
    let int_flag = |name: &str| {
        Value::from(i64::from(
            full.get(name).and_then(Value::as_bool).unwrap_or(false),
        ))
    };
    let mut availability = Map::new();
    availability.insert("protected".into(), get("protected"));
    availability.insert("work_windows".into(), get("work_windows"));
    availability.insert("day_cutoff".into(), get("day_cutoff"));
    let mut comfort = Map::new();
    for name in [
        "alert_volume",
        "end_chime",
        "tray_notifications",
        "start_at_login",
        "preferred_view",
        "sidebar_collapsed",
        "sidebar_width_px",
        "theme_pack",
        "accent",
        "accent_chips",
        "motion",
        "alarm_tone",
        "planning_style",
        "drag_step_min",
        "clock_24h",
        "setup",
    ] {
        comfort.insert(name.into(), get(name));
    }
    // The focus choices are stored only away from their defaults.
    if get("focus_audio") != "off" {
        comfort.insert("focus_audio".into(), get("focus_audio"));
    }
    if get("focus_auto_mute") == Value::Bool(false) {
        comfort.insert("focus_auto_mute".into(), Value::Bool(false));
    }
    if get("focus_auto_complete") == Value::Bool(true) {
        comfort.insert("focus_auto_complete".into(), Value::Bool(true));
    }
    let mut columns = Map::new();
    columns.insert("theme".into(), get("theme"));
    columns.insert("reminders_enabled".into(), int_flag("reminders_enabled"));
    columns.insert("reminder_lead_min".into(), get("reminder_lead_min"));
    columns.insert("reminder_sound".into(), int_flag("reminder_sound"));
    columns.insert(
        "reminder_dnd_override".into(),
        int_flag("reminder_dnd_override"),
    );
    for name in [
        "timer_work_min",
        "timer_break_min",
        "timer_long_break_min",
        "timer_long_break_every",
    ] {
        columns.insert(name.into(), get(name));
    }
    columns.insert(
        "auto_split_pomodoro".into(),
        int_flag("auto_split_pomodoro"),
    );
    columns.insert(
        "weekend_homework_free".into(),
        int_flag("weekend_homework_free"),
    );
    columns.insert("buffer_min".into(), get("buffer_min"));
    columns.insert("urgent_first".into(), int_flag("urgent_first"));
    columns.insert("split_long_tasks".into(), int_flag("split_long_tasks"));
    columns.insert("show_weekends".into(), int_flag("show_weekends"));
    columns.insert("default_spotify_url".into(), get("default_spotify_url"));
    columns.insert(
        "alarms_json".into(),
        Value::from(dumps_compact(&get("alarms"))),
    );
    columns.insert(
        "availability_json".into(),
        Value::from(dumps_compact(&Value::Object(availability))),
    );
    columns.insert(
        "comfort_json".into(),
        Value::from(dumps_compact(&Value::Object(comfort))),
    );
    Value::Object(columns)
}

/// The account's preferences as `GET /api/preferences` answers them.
pub fn read_preferences(path: &std::path::Path, user_id: i64) -> crate::ServiceResult<Value> {
    crate::with_db(path, |conn| preferences_on(conn, user_id))
}

/// `read_preferences` inside the caller's connection.
pub(crate) fn preferences_on(
    conn: &flexweek_store::Connection,
    user_id: i64,
) -> crate::ServiceResult<Value> {
    use flexweek_store as store;
    let row = store::preference_row(conn, user_id)?
        .ok_or_else(|| crate::ServiceError::Broken("the account has no preferences row".into()))?;
    let row: Value = serde_json::from_str(&row).map_err(|error| store::StoreError::Json {
        text: row.clone(),
        error,
    })?;
    let mut fields = store::preferences_fields(&row)?;
    // The engine's reader drops the comfort keys it does not know; the focus choices are those.
    let comfort: Value = row
        .get("comfort_json")
        .and_then(Value::as_str)
        .filter(|text| !text.is_empty())
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null);
    if let (Some(fields), Value::Object(comfort)) = (fields.as_object_mut(), &comfort) {
        if let Some(audio) = comfort.get("focus_audio").and_then(Value::as_str)
            && ["rain", "lo-fi", "white-noise", "spotify"].contains(&audio)
        {
            fields.insert("focus_audio".into(), Value::from(audio));
        }
        for name in ["focus_auto_mute", "focus_auto_complete"] {
            if let Some(flag) = comfort.get(name).filter(|value| value.is_boolean()) {
                fields.insert(name.into(), flag.clone());
            }
        }
    }
    check_preferences(&fields).map_err(|refused| {
        crate::ServiceError::Broken(format!(
            "stored preferences no longer read as preferences: {}",
            refused.0
        ))
    })
}

/// Saves the preferences `given` as `PUT /api/preferences` does and answers them as written; bad input
/// is refused with the one sentence every bad request gets.
pub fn write_preferences(
    path: &std::path::Path,
    user_id: i64,
    given: &Value,
) -> crate::ServiceResult<Value> {
    let written = check_preferences(given).map_err(|_| {
        crate::ServiceError::from(crate::Refusal::Invalid(
            crate::accounts::INVALID_INPUT.to_string(),
        ))
    })?;
    crate::with_db(path, |conn| store_preferences(conn, user_id, &written))?;
    Ok(written)
}

/// Checked preferences (as `check_preferences` writes them) stored inside the caller's transaction.
pub(crate) fn store_preferences(
    conn: &flexweek_store::Connection,
    user_id: i64,
    written: &Value,
) -> crate::ServiceResult<()> {
    let columns = stored_columns(written).to_string();
    Ok(flexweek_store::write_preferences(conn, user_id, &columns)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The columns stored for each accepted preference set in the corpus are the ones Python's
    /// write_preferences stored (captured by fixtures/make_preferences_corpus.py), text for text.
    #[test]
    fn the_stored_columns_are_the_ones_python_stored() {
        let cases: Vec<Value> =
            serde_json::from_str(include_str!("../tests/fixtures/preferences_parity.json"))
                .unwrap();
        let mut checked = 0;
        for case in cases.iter().filter(|case| case.get("stored").is_some()) {
            let written = check_preferences(&case["input"]).unwrap();
            assert_eq!(
                stored_columns(&written),
                case["stored"],
                "{}",
                case["input"]
            );
            checked += 1;
        }
        assert!(
            checked >= 400,
            "only {checked} accepted cases carry stored columns"
        );
    }

    #[test]
    fn a_negative_length_past_64_bits_is_refused_not_wrapped() {
        // -(2**64) + 30 would read as 30 if it were narrowed before its lower bound was checked.
        for duration in [
            serde_json::json!(-18_446_744_073_709_551_586_i128),
            serde_json::json!("-18446744073709551586"),
        ] {
            let given = serde_json::json!({
                "theme": "system",
                "protected": [{ "days": [0], "start": "09:00", "duration_min": duration, "kind": "meal" }],
            });
            assert!(check_preferences(&given).is_err(), "{given}");
        }
    }
}
