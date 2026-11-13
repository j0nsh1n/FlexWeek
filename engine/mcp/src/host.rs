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
    /// The day this computer's weeks start on, 0 Monday to 6 Sunday.
    pub first_weekday: u32,
}

/// The days a week can start on, as the desktop writes them in `week-start.json`.
pub const WEEK_STARTS: [&str; 7] = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
];

/// The day the desktop keeps for this computer in the data folder; Monday when there is none or it
/// cannot be read, as the desktop reads it.
fn kept_week_start(data_dir: &Path) -> u32 {
    std::fs::read_to_string(data_dir.join("week-start.json"))
        .ok()
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| {
            let name = value.get("week_starts_on")?.as_str()?.to_string();
            WEEK_STARTS.iter().position(|day| *day == name)
        })
        .map_or(0, |at| at as u32)
}

#[derive(Clone)]
pub struct Clock {
    pub unix: i64,
    pub today: String,
    pub minute: i64,
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
    let first_weekday = match week_starts_on {
        Some(name) => WEEK_STARTS
            .iter()
            .position(|day| *day == name)
            .ok_or("--week-starts-on must be a day of the week, such as monday")?
            as u32,
        None => kept_week_start(&data_dir),
    };
    Ok(Launch {
        data_dir,
        database,
        session_file,
        now_flag,
        read_only,
        first_weekday,
    })
}

fn take_value(args: &mut impl Iterator<Item = String>, name: &str) -> Result<String, String> {
    args.next().ok_or_else(|| format!("{name} needs a value"))
}

/// The desktop hashes the database path when `--database` was passed, and the
/// data folder otherwise (`desktop/main.py`). The string is the one we were
/// given, not a canonical path.
pub fn default_session_file(data_dir: &Path, database: &Path, database_was_set: bool) -> PathBuf {
    let root = if database_was_set { database } else { data_dir };
    let hash = flexweek_store::digest(&root.to_string_lossy());
    let instance = format!("flexweek-{}", &hash[..16]);
    data_dir.join("signed-in").join(format!("{instance}.json"))
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

fn default_data_dir() -> PathBuf {
    data_dir_from(std::env::var_os("HOME"), std::env::var_os("XDG_DATA_HOME"))
}

/// The folder the desktop's Qt picks for "FlexWeek" (`AppDataLocation`). On Linux Qt takes an
/// absolute `XDG_DATA_HOME` exactly as written and appends `/FlexWeek`; a relative or empty one is
/// ignored. The string must match the desktop's, because the session file's name is its hash.
fn data_dir_from(
    home: Option<std::ffi::OsString>,
    xdg_data_home: Option<std::ffi::OsString>,
) -> PathBuf {
    let home = home
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    #[cfg(target_os = "macos")]
    {
        let _ = xdg_data_home;
        return home.join("Library/Application Support/FlexWeek");
    }
    #[cfg(not(target_os = "macos"))]
    {
        if let Some(base) = xdg_data_home.filter(|base| Path::new(base).is_absolute()) {
            let mut folder = base;
            folder.push("/FlexWeek");
            return PathBuf::from(folder);
        }
        home.join(".local/share/FlexWeek")
    }
}

#[cfg(test)]
mod tests {
    use std::ffi::OsString;
    use std::path::PathBuf;

    use super::data_dir_from;

    fn home() -> Option<OsString> {
        Some(OsString::from("/home/student"))
    }

    // Expected values are what Qt 6.11's AppDataLocation gives the desktop for the app
    // name "FlexWeek" (checked with PySide6 on 2026-10-20). The session file's name is a
    // hash of this exact string, so a single changed character loses the session.
    #[test]
    fn an_absolute_xdg_data_home_holds_the_folder() {
        assert_eq!(
            data_dir_from(home(), Some(OsString::from("/x/data"))),
            PathBuf::from("/x/data/FlexWeek"),
            "Qt uses an absolute XDG_DATA_HOME"
        );
    }

    #[test]
    fn a_trailing_slash_is_kept_as_qt_keeps_it() {
        assert_eq!(
            data_dir_from(home(), Some(OsString::from("/x/data/")))
                .to_string_lossy()
                .into_owned(),
            "/x/data//FlexWeek",
            "Qt appends /FlexWeek to the variable as written"
        );
    }

    #[test]
    fn a_relative_or_empty_xdg_data_home_is_ignored() {
        let cases = ["rel/data", ""];
        assert!(!cases.is_empty(), "both ignored forms are checked");
        for value in cases {
            assert_eq!(
                data_dir_from(home(), Some(OsString::from(value))),
                PathBuf::from("/home/student/.local/share/FlexWeek"),
                "Qt ignores XDG_DATA_HOME={value:?}"
            );
        }
    }

    #[test]
    fn without_xdg_data_home_the_folder_is_under_home() {
        assert_eq!(
            data_dir_from(home(), None),
            PathBuf::from("/home/student/.local/share/FlexWeek"),
            "the default when XDG_DATA_HOME is unset"
        );
    }

    #[test]
    fn held_offset_clock_keeps_its_wall_date_and_minute() {
        let clock = super::parse_fixed("2026-10-21T20:00:00-05:00").expect("clock");
        assert_eq!(clock.today, "2026-10-21");
        assert_eq!(clock.minute, 1200);
        assert_eq!(clock.unix, 1792630800);
    }
}
