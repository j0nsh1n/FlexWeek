//! Where this computer keeps FlexWeek, and the clock: live for a student, or held still for a test.
//!
//! `--now` holds a timestamp; an explicit offset keeps its own wall date and minute.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use chrono::{DateTime, Datelike, NaiveDateTime, TimeZone, Timelike, Utc};

#[cfg_attr(not(windows), allow(dead_code))]
pub const WINDOWS_REFUSAL: &str =
    "FlexWeek's assistant can't check that a session file stays private on Windows yet.";

pub struct Launch {
    pub data_dir: PathBuf,
    pub database: PathBuf,
    pub session_file: PathBuf,
    pub now_flag: Option<String>,
    pub read_only: bool,
    /// Explicit `--week-starts-on` override when passed; otherwise each call reads `week-start.json`.
    pub week_starts_on_override: Option<u32>,
}

pub use flexweek_platform::folders::WEEK_STARTS;
use flexweek_platform::folders::{default_data_dir, default_session_file, kept_week_start};

/// The first day of the week for this computer right now: `--week-starts-on` if passed at launch,
/// otherwise read fresh from `<data_dir>/week-start.json`.
pub(crate) fn first_weekday(data_dir: &Path, override_day: Option<u32>) -> u32 {
    override_day.unwrap_or_else(|| kept_week_start(data_dir))
}

#[derive(Clone)]
pub struct Clock {
    pub unix: i64,
    pub today: String,
    pub minute: i64,
}

impl Clock {
    /// This minute as the engine's count of what sessions hold reads it.
    pub fn moment(&self) -> Result<flexweek_engine::plan::Moment, String> {
        flexweek_engine::plan::parse_moment(&format!(
            "{}T{:02}:{:02}",
            self.today,
            self.minute / 60,
            self.minute % 60
        ))
        .map_err(|error| error.message)
    }
}

pub fn parse(args: impl Iterator<Item = String>) -> Result<Launch, String> {
    let mut data_dir: Option<String> = None;
    let mut database: Option<String> = None;
    let mut session_file: Option<String> = None;
    let mut now_flag: Option<String> = None;
    let mut week_starts_on: Option<String> = None;
    let mut read_only = false;
    let mut args = args;
    while let Some(flag) = args.next() {
        match flag.as_str() {
            "--data-dir" => data_dir = Some(take_value(&mut args, "--data-dir")?),
            "--database" => database = Some(take_value(&mut args, "--database")?),
            "--session-file" => session_file = Some(take_value(&mut args, "--session-file")?),
            "--now" => now_flag = Some(take_value(&mut args, "--now")?),
            "--week-starts-on" => {
                week_starts_on = Some(take_value(&mut args, "--week-starts-on")?);
            }
            "--read-only" => read_only = true,
            "--help" | "-h" => return Err("help".into()),
            _ => return Err("unknown argument".into()),
        }
    }
    let database_was_set = database.is_some();
    let data_dir = data_dir.map(PathBuf::from).unwrap_or_else(default_data_dir);
    let database = database
        .map(PathBuf::from)
        .unwrap_or_else(|| data_dir.join("flexweek.db"));
    let session_file = match session_file {
        Some(path) => PathBuf::from(path),
        None => default_session_file(&data_dir, database.as_path(), database_was_set),
    };
    let week_starts_on_override = match week_starts_on {
        Some(name) => Some(
            WEEK_STARTS
                .iter()
                .position(|day| *day == name)
                .ok_or("--week-starts-on must be a day of the week, such as monday")?
                as u32,
        ),
        None => None,
    };
    Ok(Launch {
        data_dir,
        database,
        session_file,
        now_flag,
        read_only,
        week_starts_on_override,
    })
}

fn take_value(args: &mut impl Iterator<Item = String>, name: &str) -> Result<String, String> {
    args.next().ok_or_else(|| format!("{name} needs a value"))
}

pub fn log_line(line: &str) {
    eprintln!("{line}");
    let _ = std::io::Write::flush(&mut std::io::stderr());
}

pub fn folder_name(data_dir: &Path) -> String {
    data_dir
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_default()
}

/// Where the helper reads the time from. A student's helper is `Live`: every call reads the clock, so
/// a session that expires, a day that changes and a restore point's time are all current. `--now`
/// holds one moment for the tests.
#[derive(Clone)]
pub enum ClockSource {
    Fixed(Clock),
    Live,
}

pub fn source(now_flag: Option<&str>) -> Result<ClockSource, String> {
    match now_flag {
        Some(text) => parse_fixed(text).map(ClockSource::Fixed),
        None => Ok(ClockSource::Live),
    }
}

impl ClockSource {
    pub fn now(&self) -> Result<Clock, String> {
        match self {
            ClockSource::Fixed(clock) => Ok(clock.clone()),
            ClockSource::Live => live(),
        }
    }
}

/// The tests' way to move a running helper's clock without waiting. The variable names a file holding
/// an RFC 3339 timestamp that is read on every call. It exists only in a debug build: the helper a
/// student runs is a release build, where nothing reads the variable, so it cannot be reached by accident.
#[cfg(debug_assertions)]
fn moved_by_test() -> Option<Result<Clock, String>> {
    let path = std::env::var_os("FLEXWEEK_MCP_TEST_CLOCK_FILE")?;
    Some(
        std::fs::read_to_string(path)
            .map_err(|_| "the test clock file can't be read".to_string())
            .and_then(|text| parse_fixed(text.trim())),
    )
}

#[cfg(not(debug_assertions))]
fn moved_by_test() -> Option<Result<Clock, String>> {
    None
}

fn live() -> Result<Clock, String> {
    if let Some(moved) = moved_by_test() {
        return moved;
    }
    let unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| "the clock went backwards".to_string())?
        .as_secs();
    let unix = i64::try_from(unix).map_err(|_| "the clock went backwards".to_string())?;
    let local = chrono::Local::now();
    let today = format!(
        "{:04}-{:02}-{:02}",
        local.year(),
        local.month(),
        local.day()
    );
    Ok(Clock {
        unix,
        today,
        minute: i64::from(local.hour()) * 60 + i64::from(local.minute()),
    })
}

fn parse_fixed(text: &str) -> Result<Clock, String> {
    let (unix, today, minute) = if let Ok(parsed) = DateTime::parse_from_rfc3339(text) {
        (
            parsed.timestamp(),
            format!(
                "{:04}-{:02}-{:02}",
                parsed.year(),
                parsed.month(),
                parsed.day()
            ),
            i64::from(parsed.hour()) * 60 + i64::from(parsed.minute()),
        )
    } else if let Ok(naive) = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%SZ") {
        let stamp = Utc.from_utc_datetime(&naive);
        (
            stamp.timestamp(),
            format!(
                "{:04}-{:02}-{:02}",
                stamp.year(),
                stamp.month(),
                stamp.day()
            ),
            i64::from(stamp.hour()) * 60 + i64::from(stamp.minute()),
        )
    } else if let Ok(naive) = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S") {
        let stamp = Utc.from_utc_datetime(&naive);
        (
            stamp.timestamp(),
            format!(
                "{:04}-{:02}-{:02}",
                stamp.year(),
                stamp.month(),
                stamp.day()
            ),
            i64::from(stamp.hour()) * 60 + i64::from(stamp.minute()),
        )
    } else {
        return Err("--now must be an RFC 3339 timestamp".into());
    };
    Ok(Clock {
        unix,
        today,
        minute,
    })
}

#[cfg(test)]
mod tests {
    #[test]
    fn held_offset_clock_keeps_its_wall_date_and_minute() {
        let clock = super::parse_fixed("2026-10-21T20:00:00-05:00").expect("clock");
        assert_eq!(clock.today, "2026-10-21");
        assert_eq!(clock.minute, 1200);
        assert_eq!(clock.unix, 1792630800);
    }
}
