//! The kept session file, checked again on every call.
//!
//! A file other people can read is refused. A write renews a live session through the
//! store's `session_user`, as the desktop does on each request; starting the helper and the
//! read tools only look, so an assistant that reads all day does not keep a session alive.

use std::fs::File;
use std::io::Read;
use std::path::Path;
use std::sync::Mutex;

use flexweek_store::{StoreError, digest, open_connection, session_expired, session_user};
use serde_json::Value;

pub const PLEASE_SIGN_IN: &str = "Please sign in";
pub const NOT_A_SESSION: &str = "That is not a FlexWeek session.";
pub const SESSION_ENDED: &str = "Your session ended. Sign in again.";
pub const READABLE_BY_OTHERS: &str = "This session file is readable by other people.";
pub const ACCOUNT_CHANGED: &str = "Account changed. Please sign in again.";
pub const UNSUPPORTED_COMPUTER: &str =
    "FlexWeek's assistant can't check that a session file stays private on this computer yet.";
pub const STORAGE_BUSY: &str = "Storage is busy. Try again in a moment.";
pub const STORAGE_UNAVAILABLE: &str =
    "Storage unavailable. Your changes were not saved; retry shortly.";

pub struct SignedIn {
    pub user_id: i64,
    pub username: String,
    pub expires: i64,
}

/// The account for this call. The first successful sign-in is kept; a different account is refused.
pub fn for_call(
    started_as: &Mutex<Option<i64>>,
    session_file: &Path,
    database: &Path,
    now: i64,
) -> Result<SignedIn, String> {
    checked(started_as, session_file, database, now, true)
}

/// As `for_call`, for a read: the session is checked but not renewed.
pub fn for_read(
    started_as: &Mutex<Option<i64>>,
    session_file: &Path,
    database: &Path,
    now: i64,
) -> Result<SignedIn, String> {
    checked(started_as, session_file, database, now, false)
}

fn checked(
    started_as: &Mutex<Option<i64>>,
    session_file: &Path,
    database: &Path,
    now: i64,
    renew: bool,
) -> Result<SignedIn, String> {
    let token = read_token(session_file)?;
    let conn = open_existing(database)?;
    let live = live_user_id(&conn, &digest(&token), now)?;
    drop(conn);
    let switched = started_as
        .lock()
        .map_err(|_| STORAGE_UNAVAILABLE.to_string())?
        .is_some_and(|expected| live.is_some_and(|found| found != expected));
    if switched {
        return Err(ACCOUNT_CHANGED.into());
    }
    let account = if renew {
        resolve(session_file, database, now)?
    } else {
        peek(session_file, database, now)?
    };
    let mut started = started_as
        .lock()
        .map_err(|_| STORAGE_UNAVAILABLE.to_string())?;
    match *started {
        Some(expected) if expected == account.user_id => Ok(account),
        Some(_) => Err(ACCOUNT_CHANGED.into()),
        None => {
            *started = Some(account.user_id);
            Ok(account)
        }
    }
}

pub fn resolve(session_file: &Path, database: &Path, now: i64) -> Result<SignedIn, String> {
    let token = read_token(session_file)?;
    let conn = open_existing(database)?;
    let hash = digest(&token);
    let found = session_user(&conn, &hash, now).map_err(storage_sentence)?;
    let Some((user_id, username)) = found else {
        let expired = session_expired(&conn, &hash, now).map_err(storage_sentence)?;
        return Err(if expired {
            SESSION_ENDED
        } else {
            PLEASE_SIGN_IN
        }
        .into());
    };
    let expires: i64 = conn
        .query_row(
            "SELECT expires FROM sessions WHERE token_hash = ?1",
            [&hash],
            |row| row.get(0),
        )
        .map_err(|error| storage_sentence(StoreError::from(error)))?;
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT")
            .map_err(|error| storage_sentence(StoreError::from(error)))?;
    }
    Ok(SignedIn {
        user_id,
        username,
        expires,
    })
}

/// The signed-in account, checked like `resolve` but without renewing the session.
pub fn peek(session_file: &Path, database: &Path, now: i64) -> Result<SignedIn, String> {
    let token = read_token(session_file)?;
    let conn = open_existing(database)?;
    let hash = digest(&token);
    let mut stmt = conn
        .prepare(
            "SELECT users.id, users.username, sessions.expires FROM sessions
             JOIN users ON users.id = sessions.user_id
             WHERE token_hash = ?1 AND expires > ?2",
        )
        .map_err(|error| storage_sentence(StoreError::from(error)))?;
    let mut rows = stmt
        .query((&hash, now))
        .map_err(|error| storage_sentence(StoreError::from(error)))?;
    let found: Option<(i64, String, i64)> = match rows
        .next()
        .map_err(|error| storage_sentence(StoreError::from(error)))?
    {
        Some(row) => Some((
            row.get(0)
                .map_err(|error| storage_sentence(StoreError::from(error)))?,
            row.get(1)
                .map_err(|error| storage_sentence(StoreError::from(error)))?,
            row.get(2)
                .map_err(|error| storage_sentence(StoreError::from(error)))?,
        )),
        None => None,
    };
    drop(rows);
    drop(stmt);
    let Some((user_id, username, expires)) = found else {
        let expired = session_expired(&conn, &hash, now).map_err(storage_sentence)?;
        return Err(if expired {
            SESSION_ENDED
        } else {
            PLEASE_SIGN_IN
        }
        .into());
    };
    Ok(SignedIn {
        user_id,
        username,
        expires,
    })
}

/// The live account for this token, without the renewal `session_user` does.
fn live_user_id(
    conn: &flexweek_store::Connection,
    token_hash: &str,
    now: i64,
) -> Result<Option<i64>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT users.id FROM sessions JOIN users ON users.id = sessions.user_id
             WHERE token_hash = ?1 AND expires > ?2",
        )
        .map_err(|error| storage_sentence(StoreError::from(error)))?;
    let mut rows = stmt
        .query((token_hash, now))
        .map_err(|error| storage_sentence(StoreError::from(error)))?;
    let Some(row) = rows
        .next()
        .map_err(|error| storage_sentence(StoreError::from(error)))?
    else {
        return Ok(None);
    };
    row.get(0)
        .map(Some)
        .map_err(|error| storage_sentence(StoreError::from(error)))
}

/// The database the session belongs to. Opening a missing one would create an empty file the
/// desktop then finds, so a missing database means nobody is signed in here.
fn open_existing(database: &Path) -> Result<flexweek_store::Connection, String> {
    if !database.is_file() {
        return Err(PLEASE_SIGN_IN.into());
    }
    open_connection(database).map_err(storage_sentence)
}

fn read_token(path: &Path) -> Result<String, String> {
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Err(PLEASE_SIGN_IN.into());
        }
        Err(_) => return Err(STORAGE_UNAVAILABLE.into()),
    };
    ensure_owner_only(&file)?;
    let mut text = String::new();
    file.read_to_string(&mut text)
        .map_err(|_| STORAGE_UNAVAILABLE.to_string())?;
    let value: Value = serde_json::from_str(&text).map_err(|_| NOT_A_SESSION.to_string())?;
    let token = value
        .get("token")
        .and_then(Value::as_str)
        .ok_or_else(|| NOT_A_SESSION.to_string())?;
    if !token_shape(token) {
        return Err(NOT_A_SESSION.into());
    }
    Ok(token.to_string())
}

fn token_shape(token: &str) -> bool {
    (20..=128).contains(&token.len())
        && token
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
}

#[cfg(unix)]
fn ensure_owner_only(file: &File) -> Result<(), String> {
    ensure_private(file, owner_uid)
}

/// `owner` is injected so a test can say the process owner cannot be found.
#[cfg(unix)]
fn ensure_private(file: &File, owner: impl Fn() -> Option<u32>) -> Result<(), String> {
    use std::os::unix::fs::{MetadataExt, PermissionsExt};
    let meta = file
        .metadata()
        .map_err(|_| STORAGE_UNAVAILABLE.to_string())?;
    if meta.permissions().mode() & 0o077 != 0 {
        return Err(READABLE_BY_OTHERS.into());
    }
    let Some(uid) = owner() else {
        return Err(UNSUPPORTED_COMPUTER.into());
    };
    if meta.uid() != uid {
        return Err(READABLE_BY_OTHERS.into());
    }
    Ok(())
}

#[cfg(unix)]
fn owner_uid() -> Option<u32> {
    // The process owner. `libc` is not a direct dependency; `MetadataExt::uid`
    // on `/proc/self` is the same id without adding one.
    use std::os::unix::fs::MetadataExt;
    std::fs::metadata("/proc/self").ok().map(|meta| meta.uid())
}

#[cfg(all(test, unix))]
mod tests {
    use std::os::unix::fs::PermissionsExt;

    use super::{UNSUPPORTED_COMPUTER, ensure_private};

    #[test]
    fn a_missing_process_owner_says_this_computer_is_not_supported_yet() {
        let dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../target/mcp-tests/owner-missing");
        std::fs::create_dir_all(&dir).expect("scratch dir");
        let path = dir.join("session.json");
        std::fs::write(&path, "{}").expect("session file");
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).expect("mode");
        let file = std::fs::File::open(&path).expect("open");
        let error = match ensure_private(&file, || None) {
            Ok(()) => String::new(),
            Err(error) => error,
        };
        assert_eq!(
            error, UNSUPPORTED_COMPUTER,
            "when the process owner cannot be found the refusal must say this computer is not supported yet, got {error}"
        );
    }
}

#[cfg(not(unix))]
fn ensure_owner_only(_file: &File) -> Result<(), String> {
    Err(crate::host::WINDOWS_REFUSAL.into())
}

pub fn storage_sentence(error: StoreError) -> String {
    match error {
        // SQLite's own text for SQLITE_BUSY (5) and SQLITE_LOCKED (6). The store
        // does not re-export rusqlite, and this crate does not take it on.
        StoreError::Sqlite(failure) => {
            let text = failure.to_string();
            if text == "database is locked" || text == "database table is locked" {
                STORAGE_BUSY.into()
            } else {
                STORAGE_UNAVAILABLE.into()
            }
        }
        _ => STORAGE_UNAVAILABLE.into(),
    }
}
