//! Settings, account and sign-in wording. The sign-in sentences are repeated beside the literals
//! `client.py` keeps: this slice only moves the four checks, not those constants.

use std::borrow::Cow;

use flexweek_engine::desk::calendar::DAY_FULL;
use flexweek_engine::stored::{truthy, type_name};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Number, Value};

pub const RECOVERY_KEEP: &str =
    "Keep this file somewhere private. Anyone who has it can reset your password.";
pub const RECOVERY_WAIT: &str = "Turn on \u{201c}I have saved these codes\u{201d} to continue.";
pub const SIGN_IN_HEADING: &str = "Sign in";
pub const CREATE_HEADING: &str = "Create your account";
pub const CREATE_NOTE: &str = concat!(
    "FlexWeek fits homework around school and sports. ",
    "Your week is saved on this computer, under this account. ",
    "Export a backup file now and then (Settings > This computer > Manage account)."
);
pub const RESET_HEADING: &str = "Reset your password";
pub const RESET_NOTE: &str = concat!(
    "Use one of the recovery codes you saved when you made your account. Lost them too? Create a new ",
    "account and import a backup file, or start fresh."
);
pub const RECOVERY_COPY: &str = "Copy";
pub const RECOVERY_SAVE: &str = "Save\u{2026}";
pub const RECOVERY_FILE: &str = "flexweek-recovery-codes.txt";
pub const RECOVERY_SAID_MS: i64 = 2000;
pub const READ_FAILED: &str =
    "Couldn't open that file. Choose a FlexWeek backup file (it ends in .json).";
pub const READ_WEEK_FAILED: &str =
    "Couldn't open that file. Choose a FlexWeek week or day file (it ends in .json).";
pub const WRITE_FAILED: &str = "Couldn't save there. Choose another folder, like Documents.";
pub const ACCOUNT_SAVED: &str =
    "Saved your backup file to {path}. Keep it private: it has all your weeks and homework.";
pub const REPLACE_WEEK_QUESTION: &str =
    "Replace everything in {week} with this file? Other weeks aren't changed. You can undo this.";
pub const DELETE_ACCOUNT_QUESTION: &str = concat!(
    "Delete the account {name}? Every week, all your homework and your settings are removed ",
    "from {where}. This can't be undone."
);

pub const SPORT_FALLBACK: &str = "Sport or club";
pub const ALARM_NOTE: &str =
    "An alarm rings at its time on the days you pick, until you dismiss or snooze it.";
pub const DRAG_STEP_QUESTION: &str = "When you drag a block, it moves in steps of this length.";
pub const DRAG_STEP_CHOICES: [(i64, &str); 2] = [
    (5, "5 minutes (more control)"),
    (15, "15 minutes (quarter hours)"),
];
pub const PLANNING_STYLES: [(&str, &str, &str); 3] = [
    (
        "auto",
        "Plan it for me as I add it",
        "New homework gets a time straight away.",
    ),
    (
        "suggest",
        "Plan when I press Plan my homework",
        "Homework waits in a list until you ask for times.",
    ),
    (
        "manual",
        "I'll drag it onto the calendar myself",
        "The planning button becomes Suggest times.",
    ),
];
// `concat!` accepts only literals, so each sentence is one macro and the note joins those macros.
macro_rules! string_parts {
    ($($part:literal),+ $(,)?) => {
        concat!($($part),+)
    };
}

macro_rules! spotify_hint {
    ($next:ident) => {
        $next!(
            "Plays when a block starts if the alarm sound is Spotify, or when focus starts if the focus sound",
            " is Spotify."
        )
    };
}

macro_rules! spotify_rest {
    ($next:ident $(, $prefix:literal)*) => {
        $next!(
            $($prefix,)*
            "It plays in your Spotify app, and stopping the alarm stops it. Reminders before a block and the",
            " end of a focus session play Chime. Without the Spotify app, the link opens and Chime rings too."
        )
    };
}

macro_rules! spotify_note {
    ($($hint:literal),+) => {
        spotify_rest!(string_parts, $($hint),+, " ")
    };
}

pub const SPOTIFY_LINK_HINT: &str = spotify_hint!(string_parts);
pub const SPOTIFY_TONE_REST: &str = spotify_rest!(string_parts);
pub const SPOTIFY_TONE_NOTE: &str = spotify_hint!(spotify_note);
pub const STUDY_HOURS_LINE: &str =
    "Choose when FlexWeek may plan homework, including hours kept for one class.";
pub const SCHOOL_HOURS_NOTE: &str =
    "The days and times you're at school, so nothing is planned then.";
pub const NO_SCHOOL_DAYS: &str = "No school days picked: School won't appear on the calendar.";
pub const NO_STUDY_HOURS: &str = "No study hours yet, so homework can go at any time of day.";
pub const NO_PROTECTED: &str = "Nothing protected yet. Add practice, family time or a job.";
pub const DND_NOTE: &str = "Each one stays in the window until you press Got it.";
pub const TRAY_NOTE: &str = "FlexWeek waits in the tray, so reminders and alarms still come.";
pub const BLOCK_SONG_NOTE: &str = concat!(
    "When a block starts and the alarm sound is Spotify, the Spotify link in Settings plays. Dismiss or",
    " snooze it as you would an alarm."
);
pub const FOCUS_AUDIO_NOTE: &str = concat!(
    "Rain, Lo-Fi and White noise play inside FlexWeek and pause with the timer. Spotify opens the link",
    " from Settings > Alerts when focus starts."
);
pub const NO_SOUND: &str = concat!(
    "No sound played. Check that Volume is above 0 % and that your speakers or headphones are connected",
    " and not muted, then press Play again."
);
pub const SPLIT_ROUNDED: &str = "Focus lengths were rounded to {step} minutes so FlexWeek can split them into sessions and breaks.";
pub const ABOUT_LINE: &str =
    "FlexWeek plans your homework around school, sports and everything else in your week.";
pub const ABOUT_HERE: &str = "Your week is saved on this computer, under this account.";
pub const HELP_SCREENS: [(&str, &str); 4] = [
    (
        "Day",
        "One day hour by hour, with homework that isn't placed yet beside it, ready to drag in.",
    ),
    (
        "Week",
        "Your seven-day week. Drag a block to move it, or drag across empty time to add one.",
    ),
    (
        "Month",
        "Each date's blocks and the homework due that day; click a date to open it in Day.",
    ),
    (
        "My day",
        "What is on now and what comes next, to follow once your plan is made.",
    ),
];
// Material has no command bar, so its Help ends before the Ctrl+K sentence.
macro_rules! planning_body {
    ($next:ident) => {
        $next!(
            "Add homework with its due date and length. Press Plan my homework and FlexWeek finds free time for ",
            "it in your study hours, around your fixed times, before it's due. Homework that already has a time ",
            "keeps it, unless that time has passed, the work isn't finished and you didn't pin it. Replan all ",
            "starts fresh but keeps pinned homework. Anything that doesn't ",
            "fit stays under Not placed yet, and Details says why."
        )
    };
}

macro_rules! planning_with_keys {
    ($($body:literal),+) => {
        string_parts!(
            $($body),+,
            " From the keyboard, press Ctrl+K and type Plan."
        )
    };
}

pub const HELP_PLANNING_MATERIAL: &str = planning_body!(string_parts);
pub const HELP_PLANNING: &str = planning_body!(planning_with_keys);
pub const HELP_NUMBER_KEYS: &[(&str, &str)] =
    &[("[1] to [5]", "Day, Week, Month, My day, Settings")];
pub const HELP_LETTER_KEYS: &[(&str, &str)] = &[
    ("[T]", "Go to today"),
    ("[D] [W] [M]", "Day, Week, Month"),
    ("[J] [K]", "Next and previous week, day or month"),
    ("[C]", "Add homework"),
    ("[P]", "Plan my homework"),
    ("[Z]", "Undo"),
    ("[F]", "Focus screen"),
];
pub const HELP_OTHER_KEYS: &[(&str, &str)] = &[
    ("[B] or [Esc]", "Back from My day"),
    ("[Ctrl]+[Shift]+[F]", "Quick focus"),
    ("[F1]", "Help"),
    ("[Ctrl]+[N]", "Add homework"),
    ("[Ctrl]+[K]", "Command bar"),
    ("[Ctrl]+[Shift]+[L]", "Week as a list"),
    ("[Ctrl]+[Z]", "Undo"),
    ("[Ctrl]+[Y] or [Ctrl]+[Shift]+[Z]", "Redo"),
    (
        "[Ctrl]+[C] then [Ctrl]+[V]",
        "Copy the selected block, then paste it into the selected day",
    ),
    ("[Ctrl]+[D]", "Duplicate the selected block"),
    ("[Delete]", "Delete the selected block"),
    ("[Ctrl]+[S]", "Save now"),
    (
        "[Ctrl]+[=] [-] [0]",
        "Zoom the hours in, out, or back to normal",
    ),
    ("[Ctrl] and the mouse wheel", "Zoom the hours"),
    ("[Esc] while dragging", "Put the block back where it was"),
];

const MATERIAL_OTHER_KEYS: &[&str] = &[
    "[Ctrl]+[Shift]+[F]",
    "[F1]",
    "[Ctrl]+[N]",
    "[Ctrl]+[Shift]+[L]",
    "[Ctrl]+[Z]",
    "[Ctrl]+[Y] or [Ctrl]+[Shift]+[Z]",
    "[Ctrl]+[C] then [Ctrl]+[V]",
    "[Ctrl]+[D]",
    "[Delete]",
    "[Ctrl]+[S]",
    "[Ctrl]+[=] [-] [0]",
    "[Ctrl] and the mouse wheel",
];

pub const ACCOUNT_PASSWORD_NOTE: &str =
    "Your current password is needed for every change on this page.";
pub const ACCOUNT_CODES_NOTE: &str = "Each code signs you in once if you forget your password.";
pub const ACCOUNT_DATA_NOTE: &str =
    "Keep a copy of your account, or of one week or day, in a file.";
pub const RESTORE_FIRST: &str = "Choose a saved copy.";
pub const RELAY_SENTENCE: &str = concat!(
    "When your computer isn't on the same Wi-Fi, FlexWeek uses a public relay run by n0. ",
    "It sees that two devices are talking, not what they send."
);
pub const UNREACHABLE_WORDS: &str =
    "Couldn't reach your phone. Open FlexWeek on it, then try again.";
pub const PAIR_ONCE: &str = "It works once.";
pub const PAIR_CLOSED: &str = "That code isn't active anymore. Start a new one.";

pub const ALARM_TONE_LABELS: &[(&str, &str)] = &[("spotify", "A Spotify song or playlist")];
pub const PROTECTED_WORDS: &[(&str, &str)] = &[
    ("downtime", "Downtime"),
    ("commute", "Commute"),
    ("meal", "Meal"),
];
pub const DOT_WORDS: &[(&str, &str)] = &[
    ("off", ""),
    ("idle", "Waiting for a linked phone to sync"),
    ("syncing", "Syncing with your phone"),
    ("synced", "Synced with your phone"),
    ("problem", "Couldn't reach your phone"),
];

const SIGN_IN_NO_USERNAME: &str = "Type your username.";
const SIGN_IN_NO_PASSWORD: &str = "Type your password.";
const SIGN_IN_BAD_USERNAME: &str = "No FlexWeek username looks like that. Usernames are 3\u{2013}32 letters, numbers or underscores.";
const SIGN_IN_SHORT_PASSWORD: &str =
    "Passwords have at least 12 characters. Try again, or choose Forgot password.";
const SIGN_UP_NO_USERNAME: &str = "Choose a username.";
const SIGN_UP_NO_PASSWORD: &str = "Choose a password with at least 12 characters.";
const SIGN_UP_LONG_PASSWORD: &str = "Use 128 characters or fewer.";

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

fn name_at(day: i64) -> EngineResult<&'static str> {
    let names: &[&str] = &DAY_FULL;
    let len = i64::try_from(names.len()).unwrap_or(i64::MAX);
    let index = if day < 0 { day + len } else { day };
    if index < 0 || index >= len {
        return Err(EngineError::index("tuple index out of range"));
    }
    Ok(names[usize::try_from(index).unwrap_or(usize::MAX)])
}

fn join_and(parts: &[String]) -> String {
    let last = parts.len().saturating_sub(1);
    let mut text = parts[..last].join(", ");
    text.push_str(" and ");
    text.push_str(&parts[last]);
    text
}

pub fn ring_days(days: &[i64]) -> EngineResult<String> {
    let mut chosen = days.to_vec();
    chosen.sort();
    chosen.dedup();
    if chosen == [0, 1, 2, 3, 4, 5, 6] {
        return Ok("every day".to_string());
    }
    if chosen == [0, 1, 2, 3, 4] {
        return Ok("Monday to Friday".to_string());
    }
    if chosen == [5, 6] {
        return Ok("Saturday and Sunday".to_string());
    }
    if chosen.is_empty() {
        return Ok("no days".to_string());
    }
    if chosen.len() == 1 {
        return Ok(name_at(chosen[0])?.to_string());
    }
    let mut short = Vec::with_capacity(chosen.len());
    for day in chosen {
        short.push(name_at(day)?.chars().take(3).collect::<String>());
    }
    Ok(join_and(&short))
}

pub fn help_keys(
    numbers: bool,
    letters: bool,
    material: bool,
) -> Vec<(&'static str, &'static str)> {
    let mut rows = Vec::new();
    if numbers {
        rows.extend_from_slice(HELP_NUMBER_KEYS);
    }
    if letters {
        rows.extend_from_slice(HELP_LETTER_KEYS);
    }
    for row in HELP_OTHER_KEYS {
        if !material || MATERIAL_OTHER_KEYS.contains(&row.0) {
            rows.push(*row);
        }
    }
    rows
}

pub fn keys_words(marked: &str) -> String {
    marked.replace(['[', ']'], "")
}

pub fn first_lines(notes: &str, limit: i64) -> String {
    let mut kept = Vec::new();
    for raw in notes.lines() {
        let line = raw.trim();
        if line.is_empty()
            || (line.chars().all(|ch| ch == '-' || ch == '=') && line.chars().count() > 2)
        {
            continue;
        }
        let line = line.trim_start_matches('#').trim();
        let line = if let Some(rest) = line.strip_prefix("- ").or_else(|| line.strip_prefix("* ")) {
            format!("\u{2022}  {rest}")
        } else {
            line.to_string()
        };
        kept.push(line.replace("**", ""));
        if kept.len() as i64 == limit {
            break;
        }
    }
    kept.join("\n")
}

pub fn key_parts(marked: &str) -> Vec<(String, bool)> {
    let chars: Vec<char> = marked.chars().collect();
    let mut parts = Vec::new();
    let mut index = 0;
    let mut plain_start = 0;
    while index < chars.len() {
        if chars[index] == '['
            && let Some(close) = chars[index + 1..].iter().position(|ch| *ch == ']')
            && close > 0
        {
            let end = index + 1 + close;
            push_key_piece(&mut parts, &chars[plain_start..index]);
            parts.push((chars[index + 1..end].iter().collect(), true));
            index = end + 1;
            plain_start = index;
            continue;
        }
        index += 1;
    }
    push_key_piece(&mut parts, &chars[plain_start..]);
    parts
}

fn push_key_piece(parts: &mut Vec<(String, bool)>, piece: &[char]) {
    let text: String = piece.iter().collect();
    if text.trim().is_empty() {
        return;
    }
    if text.starts_with('[') {
        let chars: Vec<char> = text.chars().collect();
        let inner = if chars.len() >= 2 {
            chars[1..chars.len() - 1].iter().collect()
        } else {
            String::new()
        };
        parts.push((inner, true));
        return;
    }
    parts.push((text.trim().to_string(), false));
}

fn number_text(number: &Number) -> String {
    number.to_string()
}

fn is_float(number: &Number) -> bool {
    number_text(number).contains(['.', 'e', 'E'])
}

fn py_eq_int(value: &Value, wanted: i64) -> bool {
    match value {
        Value::Bool(flag) => i64::from(*flag) == wanted,
        Value::Number(number) if is_float(number) => number.as_f64() == Some(wanted as f64),
        Value::Number(number) => number.as_i64() == Some(wanted),
        _ => false,
    }
}

fn is_py_int(value: &Value) -> bool {
    match value {
        Value::Bool(_) => true,
        Value::Number(number) => !is_float(number),
        _ => false,
    }
}

pub fn recovery_status(remaining: &Value) -> String {
    if py_eq_int(remaining, 0) {
        return "No unused recovery codes remain. Replace them before signing out.".to_string();
    }
    if py_eq_int(remaining, 1) {
        return "1 unused recovery code remains.".to_string();
    }
    if is_py_int(remaining) {
        let shown = match remaining {
            Value::Bool(true) => "True".to_string(),
            Value::Bool(false) => "False".to_string(),
            Value::Number(number) => number_text(number),
            _ => String::new(),
        };
        return format!("{shown} unused recovery codes remain.");
    }
    "Couldn't find out how many recovery codes are left.".to_string()
}

fn py_display(value: &Value) -> String {
    match value {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Number(number) => number_text(number),
        Value::String(text) => text.clone(),
        Value::Array(items) => {
            let shown: Vec<String> = items.iter().map(py_display).collect();
            format!("[{}]", shown.join(", "))
        }
        Value::Object(_) => "{}".to_string(),
    }
}

pub fn restore_parts(point: &Value) -> EngineResult<(String, String)> {
    let map = as_dict(point)?;
    let fallback = Value::from(0);
    let weeks = map
        .get("weeks_count")
        .or_else(|| map.get("week_count"))
        .or_else(|| map.get("weeks"))
        .unwrap_or(&fallback);
    let unit = if py_eq_int(weeks, 1) { "week" } else { "weeks" };
    let name = match map.get("label") {
        Some(value) => py_display(value),
        None => "None".to_string(),
    };
    let when = match map.get("created_at") {
        Some(value) if truthy(Some(value)) => py_display(value),
        _ => String::new(),
    };
    Ok((
        name,
        format!("{when} \u{00b7} {} {unit}", py_display(weeks)),
    ))
}

pub fn restore_row(point: &Value) -> EngineResult<String> {
    let (name, detail) = restore_parts(point)?;
    Ok(format!("{name} \u{00b7} {detail}"))
}

fn py_len(value: &Value) -> EngineResult<usize> {
    match value {
        Value::Array(items) => Ok(items.len()),
        Value::String(text) => Ok(text.chars().count()),
        Value::Object(map) => Ok(map.len()),
        other => Err(type_error(format!(
            "object of type '{}' has no len()",
            type_name(other)
        ))),
    }
}

fn counted(map: &Map<String, Value>, key: &str) -> EngineResult<usize> {
    match map.get(key) {
        Some(value) if truthy(Some(value)) => py_len(value),
        _ => Ok(0),
    }
}

fn truthy_map<'a>(value: Option<&'a Value>) -> EngineResult<Cow<'a, Map<String, Value>>> {
    match value {
        Some(found) if truthy(Some(found)) => Ok(Cow::Borrowed(as_dict(found)?)),
        _ => Ok(Cow::Owned(Map::new())),
    }
}

pub fn restore_summary(preview: &Value) -> EngineResult<String> {
    if !truthy(Some(preview)) {
        return Ok(String::new());
    }
    let preview = as_dict(preview)?;
    let changes = truthy_map(preview.get("changes"))?;
    let weeks = truthy_map(changes.get("weeks"))?;
    let homework = truthy_map(changes.get("assignments"))?;
    let added = counted(&weeks, "added")? + counted(&homework, "added")?;
    let changed = counted(&weeks, "changed")? + counted(&homework, "changed")?;
    let removed = counted(&weeks, "removed")? + counted(&homework, "removed")?;
    Ok(format!(
        "{added} added, {changed} changed, {removed} removed."
    ))
}

fn oxford(parts: &[String]) -> String {
    if parts.len() < 3 {
        return parts.join(" and ");
    }
    format!(
        "{}, and {}",
        parts[..parts.len() - 1].join(", "),
        parts[parts.len() - 1]
    )
}

fn gone_from_backup(count: usize, noun: &str) -> String {
    let verb = if count == 1 { "isn't" } else { "aren't" };
    format!("{count} of your {noun} that {verb} in the backup")
}

pub fn transfer_summary(preview: &Value) -> EngineResult<String> {
    let preview = as_dict(preview)?;
    let changes = truthy_map(preview.get("changes"))?;
    let weeks = truthy_map(changes.get("weeks"))?;
    let added = counted(&weeks, "added")?;
    let replaced = counted(&weeks, "changed")?;
    let deleted = counted(&weeks, "removed")?;
    let mut parts = Vec::new();
    if added > 0 {
        parts.push(format!(
            "adds {added} {}",
            if added == 1 { "week" } else { "weeks" }
        ));
    }
    if replaced > 0 {
        parts.push(format!("replaces {replaced} of your weeks"));
    }
    if deleted > 0 {
        parts.push(format!("deletes {}", gone_from_backup(deleted, "weeks")));
    }
    let mut lines = Vec::new();
    if !parts.is_empty() {
        lines.push(format!("{}.", oxford(&parts)));
    }
    for (key, one, many) in [
        ("assignments", "homework", "homework"),
        ("routines", "routine", "routines"),
    ] {
        let part = truthy_map(changes.get(key))?;
        let differ = counted(&part, "added")? + counted(&part, "changed")?;
        let gone = counted(&part, "removed")?;
        if differ > 0 {
            let noun = if differ == 1 { one } else { many };
            let verb = if differ == 1 { "changes" } else { "change" };
            lines.push(format!("{differ} {noun} {verb}."));
        }
        if gone > 0 {
            lines.push(format!("It also deletes {}.", gone_from_backup(gone, many)));
        }
    }
    if truthy(changes.get("preferences_changed")) {
        lines.push("Your settings will be replaced.".to_string());
    }
    if lines.is_empty() {
        lines.push("Nothing in it is different from your account.".to_string());
    }
    Ok(lines.join(" "))
}

/// `weekday` is the computer's own name for `last_seen_ms`. This function reads no clock or zone.
pub fn seen_words(last_seen_ms: Option<&str>, now_ms: i64, weekday: &str) -> EngineResult<String> {
    let Some(text) = last_seen_ms.filter(|text| !text.is_empty()) else {
        return Ok("Not synced yet".to_string());
    };
    let seen = flexweek_engine::time::py_int(text)?;
    let minutes = (i128::from(now_ms) - i128::from(seen)).max(0) / 60_000;
    if minutes < 1 {
        return Ok("Synced just now".to_string());
    }
    if minutes < 60 {
        return Ok(format!("Synced {minutes} min ago"));
    }
    if minutes < 24 * 60 {
        return Ok(format!("Synced {} h ago", minutes / 60));
    }
    Ok(format!("Last seen on {weekday}"))
}

pub fn clock_warning_words(count: i64) -> String {
    if count <= 0 {
        return String::new();
    }
    let (noun, verb) = if count == 1 {
        ("change", "was")
    } else {
        ("changes", "were")
    };
    format!("Your phone's clock looks wrong. {count} {noun} {verb} held back.")
}

pub fn sync_state(status: &Value, linked: bool) -> EngineResult<String> {
    if !linked {
        return Ok("off".to_string());
    }
    let status = as_dict(status)?;
    let syncing = status
        .get("syncing")
        .ok_or_else(|| EngineError::key("syncing"))?;
    if truthy(Some(syncing)) {
        return Ok("syncing".to_string());
    }
    let last_error = status
        .get("last_error")
        .ok_or_else(|| EngineError::key("last_error"))?;
    if truthy(Some(last_error)) {
        return Ok("problem".to_string());
    }
    let last_sync = status
        .get("last_sync_ms")
        .ok_or_else(|| EngineError::key("last_sync_ms"))?;
    if last_sync.is_null() {
        return Ok("idle".to_string());
    }
    Ok("synced".to_string())
}

pub fn countdown_words(seconds: i64) -> String {
    let seconds = seconds.max(0);
    let minutes = seconds.div_euclid(60);
    let rest = seconds.rem_euclid(60);
    format!("Code works for {minutes}:{rest:02}")
}

pub fn tries_words(tries: i64) -> String {
    if tries == 1 {
        "1 try left".to_string()
    } else {
        format!("{tries} tries left")
    }
}

pub fn pair_problem(state: &str) -> String {
    match state {
        "expired" => "That code has expired. Start a new one.".to_string(),
        "too_many_tries" => "Too many wrong tries. Start a new code.".to_string(),
        _ => String::new(),
    }
}

pub fn username_ok(name: &str) -> bool {
    let count = name.chars().count();
    (3..=32).contains(&count)
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
}

pub fn sign_in_problem(name: &str, password: &str) -> EngineResult<String> {
    if name.is_empty() {
        return Ok(SIGN_IN_NO_USERNAME.to_string());
    }
    if password.is_empty() {
        return Ok(SIGN_IN_NO_PASSWORD.to_string());
    }
    if !username_ok(name) {
        return Ok(SIGN_IN_BAD_USERNAME.to_string());
    }
    if password.chars().count() < 12 {
        return Ok(SIGN_IN_SHORT_PASSWORD.to_string());
    }
    Ok(String::new())
}

pub fn sign_up_problem(name: &str, password: &str) -> EngineResult<String> {
    if name.is_empty() {
        return Ok(SIGN_UP_NO_USERNAME.to_string());
    }
    if !username_ok(name) {
        return Ok(crate::session::words::USERNAME_ERROR.to_string());
    }
    if password.is_empty() {
        return Ok(SIGN_UP_NO_PASSWORD.to_string());
    }
    let length = password.chars().count();
    if length > 128 {
        return Ok(SIGN_UP_LONG_PASSWORD.to_string());
    }
    if length < 12 {
        return Ok(short_password_needed(
            12 - i64::try_from(length).unwrap_or(0),
        ));
    }
    Ok(String::new())
}

pub fn short_password_needed(n: i64) -> String {
    let unit = if n == 1 { "character" } else { "characters" };
    format!("Add {n} more {unit}. Passwords need at least 12 characters.")
}
