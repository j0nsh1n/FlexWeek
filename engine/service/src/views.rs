//! Day, Month and the homework list, as `backend/app.py`'s `GET /api/day`, `GET /api/month` and
//! `GET /api/assignments` answer them. Month and the homework list are the store's views (which the
//! assistant helper reads too); Day writes its blocks out in full, as the week answer does. The caller
//! passes the time; a refused date gives Python's sentence.

use std::path::Path;

use flexweek_engine::plan::{Moment, build_day};
use flexweek_engine::time::{is_calendar_date, monday_of};
use flexweek_store::{self as store, StoreError};
use serde_json::Value;

use crate::blocks::check_block;
use crate::weeks::{homework_of, parsed, rewritten};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub const DATE_RULE: &str = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31";

fn refused_date(error: ServiceError) -> ServiceError {
    match error {
        ServiceError::Store(StoreError::Date(sentence)) => Refusal::Invalid(sentence).into(),
        other => other,
    }
}

fn parsed_one(text: &str) -> ServiceResult<Value> {
    serde_json::from_str(text).map_err(|error| {
        StoreError::Json {
            text: text.to_string(),
            error,
        }
        .into()
    })
}

/// One day: its blocks, what is due and what is left, as Day and My day show it.
pub fn day(path: &Path, user_id: i64, date: &str, now: Moment) -> ServiceResult<Value> {
    if !is_calendar_date(date) {
        return Err(Refusal::Invalid(DATE_RULE.to_string()).into());
    }
    let week_start = monday_of(date)?;
    with_db(path, |conn| {
        let stored = store::week_blocks(conn, user_id, &week_start)?;
        let stored = stored.as_deref().unwrap_or("[]");
        let merged = parsed(&store::week_with_standing(
            conn,
            user_id,
            &week_start,
            stored,
        )?)?;
        let owned = homework_of(conn, user_id, &merged)?;
        let blocks = rewritten(merged, &owned)?;
        let mut assignments = Vec::new();
        for (body, revision) in store::assignment_bodies(conn, user_id)? {
            assignments.push((parsed_one(&body)?, revision));
        }
        let mut weeks = Vec::new();
        for (start, text) in store::list_account_weeks(conn, user_id)? {
            weeks.push((start, parsed(&text)?));
        }
        let mut built = build_day(date, &week_start, &blocks, &assignments, &weeks, Some(now))?;
        // As backend/day.py does: the day's sessions and fixed blocks are written out in full.
        for list in ["sessions", "locked"] {
            if let Some(Value::Array(items)) = built.get_mut(list) {
                for item in items.iter_mut() {
                    *item = check_block(item).map_err(|refused| {
                        ServiceError::Broken(format!(
                            "a day's block no longer reads as a block: {}",
                            refused.0
                        ))
                    })?;
                }
            }
        }
        Ok(built)
    })
}

/// The month `month` (YYYY-MM) with its rows starting on `first_day` (0 Monday to 6 Sunday).
pub fn month(
    path: &Path,
    user_id: i64,
    month: &str,
    first_day: u32,
    now: Moment,
) -> ServiceResult<Value> {
    if first_day > 6 {
        return Err(Refusal::Invalid(crate::accounts::INVALID_INPUT.to_string()).into());
    }
    with_db(path, |conn| {
        Ok(store::month_view_from(
            conn,
            user_id,
            month,
            first_day,
            Some(now),
        )?)
    })
    .map_err(refused_date)
}

/// The account's homework for the week from `week_start` (a Monday or any other day), with its planned
/// and done minutes, finished homework only when asked, soonest due first.
pub fn homework(
    path: &Path,
    user_id: i64,
    week_start: &str,
    include_completed: bool,
    now: Moment,
) -> ServiceResult<Value> {
    with_db(path, |conn| {
        Ok(store::homework_list(
            conn,
            user_id,
            week_start,
            include_completed,
            Some(now),
        )?)
    })
    .map_err(refused_date)
}

/// The account's routines, as `GET /api/routines` lists them.
pub fn routines(path: &Path, user_id: i64) -> ServiceResult<Value> {
    with_db(path, |conn| Ok(store::routine_list(conn, user_id)?))
}

/// The account's restore points, newest first, as `GET /api/restore-points` lists them.
pub fn restore_points(path: &Path, user_id: i64) -> ServiceResult<Value> {
    with_db(path, |conn| Ok(store::restore_point_list(conn, user_id)?))
}
