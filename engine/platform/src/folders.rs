//! Where this computer keeps FlexWeek: the data folder Qt's `AppDataLocation` picks for the desktop, the
//! kept sign-in file's name, and the first day of the week the desktop keeps there. The desktop, the
//! assistant helper and the upgrade check must all find the same files, so the rules live once, here.

use std::path::{Path, PathBuf};

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
pub fn kept_week_start(data_dir: &Path) -> u32 {
    std::fs::read_to_string(data_dir.join("week-start.json"))
        .ok()
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| {
            let name = value.get("week_starts_on")?.as_str()?.to_string();
            WEEK_STARTS.iter().position(|day| *day == name)
        })
        .map_or(0, |at| at as u32)
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

/// Where XDG keeps this user's login entries' folder (`autostart` inside it), as the desktop finds it
/// (`desktop/native/autostart.py`): `XDG_CONFIG_HOME` when set and not empty, otherwise `~/.config`.
pub fn config_dir() -> PathBuf {
    config_dir_from(
        std::env::var_os("HOME"),
        std::env::var_os("XDG_CONFIG_HOME"),
    )
}

pub fn config_dir_from(
    home: Option<std::ffi::OsString>,
    xdg_config_home: Option<std::ffi::OsString>,
) -> PathBuf {
    match xdg_config_home.filter(|value| !value.is_empty()) {
        Some(config) => PathBuf::from(config),
        None => PathBuf::from(home.unwrap_or_else(|| ".".into())).join(".config"),
    }
}

/// The data folder for this user, from `HOME` and `XDG_DATA_HOME`.
pub fn default_data_dir() -> PathBuf {
    data_dir_from(std::env::var_os("HOME"), std::env::var_os("XDG_DATA_HOME"))
}

/// The folder the desktop's Qt picks for "FlexWeek" (`AppDataLocation`). On Linux Qt takes an
/// absolute `XDG_DATA_HOME` exactly as written and appends `/FlexWeek`; a relative or empty one is
/// ignored. The string must match the desktop's, because the session file's name is its hash.
pub fn data_dir_from(
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

    use super::{config_dir_from, data_dir_from};

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
    fn the_login_entry_folder_follows_xdg_config_home_as_the_desktop_reads_it() {
        assert_eq!(
            config_dir_from(home(), Some(OsString::from("rel/config"))),
            PathBuf::from("rel/config"),
            "Python's os.environ.get takes any value that is not empty"
        );
        assert_eq!(
            config_dir_from(home(), Some(OsString::new())),
            PathBuf::from("/home/student/.config")
        );
        assert_eq!(
            config_dir_from(home(), None),
            PathBuf::from("/home/student/.config")
        );
    }
}
