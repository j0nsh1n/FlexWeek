//! Reading weeks as `backend/app.py`'s `GET /api/week` and `GET /api/weeks` answer: a stored (Monday)
//! week with the School and activities standing in it and its homework sessions brought up to date,
//! or a week shown from another weekday, put together from the two stored weeks it covers with both
//! of them as saved, for Undo. The caller resolves "this week" from its clock.

use std::path::Path;

use flexweek_engine::shown::shown_parts;
use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_store::{self as store, Connection, shown_weeks};
use serde_json::{Map, Value, json};

use crate::{Refusal, ServiceResult, with_db};

pub const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";

pub(crate) fn parsed(text: &str) -> ServiceResult<Vec<Value>> {
    Ok(shown_weeks::parsed_blocks(text)?)
}

pub(crate) fn homework_of(
    conn: &Connection,
    user_id: i64,
    blocks: &[Value],
) -> ServiceResult<Map<String, Value>> {
    Ok(shown_weeks::homework_of(conn, user_id, blocks)?)
}

/// Sessions brought up to date from their homework, each written as a block is written.
pub(crate) fn rewritten(
    blocks: Vec<Value>,
    owned: &Map<String, Value>,
) -> ServiceResult<Vec<Value>> {
    Ok(shown_weeks::rewritten(blocks, owned)?)
}

fn monday_week(conn: &Connection, user_id: i64, week_start: &str) -> ServiceResult<Value> {
    Ok(shown_weeks::monday_week(conn, user_id, week_start)?)
}

/// `between` runs just before the second stored week is read as saved, so a test can commit there.
pub(crate) fn shown_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    weeks: (&str, &str),
    between: impl FnOnce(),
) -> ServiceResult<Value> {
    Ok(shown_weeks::shown_week(
        conn, user_id, week_start, weeks, between,
    )?)
}

/// The week from `week_start`: a Monday is one stored week; another calendar day shows the seven days
/// from it, taken from the two stored weeks it covers, read in one snapshot so both come from the same
/// moment. A week nobody saved is empty with revision 0.
pub fn read_week(path: &Path, user_id: i64, week_start: &str) -> ServiceResult<Value> {
    let parts = if is_week_start(week_start) || !is_calendar_date(week_start) {
        None
    } else {
        shown_parts(week_start)?
    };
    if let Some((first, second, _)) = parts {
        return read_shown(path, user_id, week_start, (&first, &second), || {});
    }
    if !is_week_start(week_start) {
        return Err(Refusal::Invalid(WEEK_START_RULE.to_string()).into());
    }
    with_db(path, |conn| monday_week(conn, user_id, week_start))
}

/// A shown week read in one snapshot, so both stored weeks come from the same moment.
fn read_shown(
    path: &Path,
    user_id: i64,
    week_start: &str,
    weeks: (&str, &str),
    between: impl FnOnce(),
) -> ServiceResult<Value> {
    with_db(path, |conn| {
        store::begin(conn)?;
        shown_week(conn, user_id, week_start, weeks, between)
    })
}

/// The Mondays of every week the account has saved, oldest first.
pub fn list_weeks(path: &Path, user_id: i64) -> ServiceResult<Value> {
    let weeks = with_db(path, |conn| Ok(store::week_starts(conn, user_id)?))?;
    Ok(json!({ "weeks": weeks }))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Another program commits to the second stored week while a shown week is being read: the answer
    /// must hold one moment of each stored week, so its revisions and its stored weeks agree.
    #[test]
    fn a_shown_week_is_read_in_one_snapshot() {
        let dir = std::env::temp_dir().join(format!("flexweek-snapshot-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("snapshot.db");
        store::initialize(&path, "2026-11-16").unwrap();
        let user = with_db(&path, |conn| {
            let user = store::insert_user(conn, "ana", "hash")?;
            let block = r#"[{"id":"b","title":"B","kind":"locked","duration_min":60,"days":[3],"start":"10:00"}]"#;
            for monday in ["2026-11-09", "2026-11-16"] {
                store::save_week(conn, user, monday, block, 0)?;
            }
            Ok(user)
        })
        .unwrap();
        let mut outcome = None;
        let shown = read_shown(
            &path,
            user,
            "2026-11-11",
            ("2026-11-09", "2026-11-16"),
            || {
                let other = rusqlite::Connection::open(&path).unwrap();
                other.busy_timeout(std::time::Duration::ZERO).unwrap();
                outcome = Some(other.execute(
                    "UPDATE weeks SET revision = revision + 1 WHERE week_start = '2026-11-16'",
                    [],
                ));
            },
        )
        .unwrap();
        assert!(
            matches!(outcome, Some(Ok(1)) | Some(Err(_))),
            "the commit was not tried between the reads: {outcome:?}"
        );
        assert_eq!(shown["revision"][1], 1, "the setup saved no week");
        let stored: Vec<Value> = shown["stored"]
            .as_array()
            .unwrap()
            .iter()
            .map(|part| part["revision"].clone())
            .collect();
        assert_eq!(
            shown["revision"],
            Value::Array(stored),
            "one answer mixed two moments of a week"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }
}
