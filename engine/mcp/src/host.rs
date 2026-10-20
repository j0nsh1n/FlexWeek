//! Where this computer keeps FlexWeek, and the clock a test can hold still.
//!
//! `--now` is UTC (`YYYY-MM-DDTHH:MM:SSZ`). The desktop's own clock is local;
//! the flag exists so a test names one instant.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use chrono::{DateTime, Datelike, NaiveDateTime, TimeZone, Utc};

#[cfg_attr(not(windows), allow(dead_code))]
pub const WINDOWS_REFUSAL: &str =
    "FlexWeek's assistant can't check that a session file stays private on Windows yet.";

pub struct Launch {
    pub data_dir: PathBuf,
    pub database: PathBuf,
    pub session_file: PathBuf,
    pub now_flag: Option<String>,
    pub read_only: bool,
}

pub struct Clock {
    pub unix: i64,
    pub today: String,
}

pub fn parse(args: impl Iterator<Item = String>) -> Result<Launch, String> {
    let mut data_dir: Option<String> = None;
    let mut database: Option<String> = None;
    let mut session_file: Option<String> = None;
    let mut now_flag: Option<String> = None;
    let mut read_only = false;
    let mut args = args;
    while let Some(flag) = args.next() {
        match flag.as_str() {
            "--data-dir" => data_dir = Some(take_value(&mut args, "--data-dir")?),
            "--database" => database = Some(take_value(&mut args, "--database")?),
            "--session-file" => session_file = Some(take_value(&mut args, "--session-file")?),
            "--now" => now_flag = Some(take_value(&mut args, "--now")?),
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
    Ok(Launch {
        data_dir,
        database,
        session_file,
        now_flag,
        read_only,
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

pub fn clock(now_flag: Option<&str>) -> Result<Clock, String> {
    let Some(text) = now_flag else {
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
        return Ok(Clock { unix, today });
    };
    let stamp = if let Ok(parsed) = DateTime::parse_from_rfc3339(text) {
        parsed.with_timezone(&Utc)
    } else if let Ok(naive) = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%SZ") {
        Utc.from_utc_datetime(&naive)
    } else if let Ok(naive) = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S") {
        Utc.from_utc_datetime(&naive)
    } else {
        return Err("--now must be YYYY-MM-DDTHH:MM:SSZ".into());
    };
    Ok(Clock {
        unix: stamp.timestamp(),
        today: format!(
            "{:04}-{:02}-{:02}",
            stamp.year(),
            stamp.month(),
            stamp.day()
        ),
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
}
