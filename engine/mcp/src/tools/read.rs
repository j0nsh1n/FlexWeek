//! Read tools. They check the session, then translate JSON to the store views.

use std::collections::{BTreeMap, BTreeSet};

use flexweek_engine::model::due_sort_key;
use flexweek_engine::plan::planned_minutes_from_day;
use flexweek_store::{
    StoreError, assignment_view, day_view, homework_list, list_account_weeks, list_assignment_rows,
    month_view_from, open_connection, restore_point_list, routine_list, week_view,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Value, json};

use super::week::{self, WeekTarget};
use crate::host;
use crate::session::{self, SignedIn};

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct TodayArgs {
    #[serde(default)]
    date: Option<String>,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct WeekArgs {
    week_start: String,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct MonthArgs {
    month: String,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct HomeworkArgs {
    week_start: String,
    #[serde(default)]
    include_completed: Option<bool>,
}

fn finish(name: &str, result: Result<String, String>) -> Result<String, String> {
    let class = if result.is_ok() { "ok" } else { "error" };
    host::log_line(&format!("{name} {class}"));
    result
}

fn view_error(error: StoreError) -> String {
    match error {
        StoreError::Date(sentence) => sentence,
        other => session::storage_sentence(other),
    }
}

fn account_id(account: &SignedIn) -> i64 {
    account.user_id
}

/// The week on screen from `week_start` when this computer's weeks start on `first_weekday`: one
/// stored week from Monday (also accepted for older clients when `first_weekday` is another day),
/// else the two it covers shown as one, days counted from `week_start`, with both revisions, first
/// week first, and `week_starts_on` naming `week_start`'s weekday.
fn shown_week_view(
    conn: &flexweek_store::Connection,
    user_id: i64,
    week_start: &str,
    first_weekday: u32,
) -> Result<Value, String> {
    let target = week::resolve_week(week_start, first_weekday)?;
    match target {
        WeekTarget::StoredMonday => {
            let mut view = week_view(conn, user_id, week_start).map_err(view_error)?;
            week::add_week_starts_on(&mut view, week_start)?;
            Ok(view)
        }
        WeekTarget::Shown { first, second, .. } => {
            let first = week_view(conn, user_id, &first).map_err(view_error)?;
            let second = week_view(conn, user_id, &second).map_err(view_error)?;
            let blocks_of = |view: &Value| -> Vec<Value> {
                view.get("blocks")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default()
            };
            let (first_blocks, second_blocks) = (blocks_of(&first), blocks_of(&second));
            // The homework its sessions belong to: one waiting for a time may run to its due date.
            let blocks = week::compose_shown_blocks(
                conn,
                user_id,
                week_start,
                &first_blocks,
                &second_blocks,
            )?;
            Ok(json!({
                "week_start": week_start,
                "week_starts_on": week::weekday_name(week_start)?,
                "revision": [first["revision"], second["revision"]],
                "blocks": blocks,
            }))
        }
    }
}

fn shown_homework_list(
    conn: &flexweek_store::Connection,
    user_id: i64,
    week_start: &str,
    include_completed: bool,
    first_weekday: u32,
) -> Result<Value, String> {
    let target = week::resolve_week(week_start, first_weekday)?;
    let mut view = match target {
        WeekTarget::StoredMonday => {
            let mut view =
                homework_list(conn, user_id, week_start, include_completed).map_err(view_error)?;
            if let Some(fields) = view.as_object_mut() {
                fields.insert("week_start".into(), json!(week_start));
            }
            view
        }
        WeekTarget::Shown { .. } => {
            let rows = list_assignment_rows(conn, user_id).map_err(view_error)?;
            let stored = list_account_weeks(conn, user_id).map_err(view_error)?;
            let mut weeks = Vec::with_capacity(stored.len());
            let mut session_weeks: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
            for (saved_week, raw) in stored {
                let blocks: Vec<Value> = serde_json::from_str(&raw)
                    .map_err(|error| view_error(StoreError::Json { text: raw, error }))?;
                for block in &blocks {
                    let Some(id) = block.get("assignment_id").and_then(Value::as_str) else {
                        continue;
                    };
                    session_weeks
                        .entry(id.to_string())
                        .or_default()
                        .insert(saved_week.clone());
                }
                weeks.push((saved_week, blocks));
            }
            let planned =
                planned_minutes_from_day(&weeks, week_start).map_err(|err| err.message)?;
            let mut keyed = Vec::new();
            for (row_id, row_body, row_revision) in rows {
                let body: Value = serde_json::from_str(&row_body).map_err(|error| {
                    view_error(StoreError::Json {
                        text: row_body,
                        error,
                    })
                })?;
                let completed = body
                    .get("completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                if completed && !include_completed {
                    continue;
                }
                let planned_min = planned.get(&row_id).copied().unwrap_or(0);
                let mut item =
                    assignment_view(&body, row_revision, planned_min).map_err(|err| err.message)?;
                let listed: Vec<&str> = session_weeks
                    .get(&row_id)
                    .map(|weeks| weeks.iter().map(String::as_str).collect())
                    .unwrap_or_default();
                if let Some(fields) = item.as_object_mut() {
                    fields.insert("session_weeks".into(), json!(listed));
                }
                let due = item.get("due").and_then(Value::as_str);
                let id = item.get("id").and_then(Value::as_str).unwrap_or("");
                let key = due_sort_key(due, id).map_err(|err| err.message)?;
                keyed.push((key, item));
            }
            keyed.sort_by(|left, right| left.0.cmp(&right.0));
            let items: Vec<Value> = keyed.into_iter().map(|(_, item)| item).collect();
            json!({
                "assignments": items,
                "week_start": week_start,
            })
        }
    };
    week::add_week_starts_on(&mut view, week_start)?;
    Ok(view)
}

#[tool_router(router = read_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Who is signed in on this computer",
        annotations(read_only_hint = true)
    )]
    async fn whoami(&self) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let first_weekday = self.first_weekday();
            Ok(json!({
                "username": account.username,
                "session_expires": account.expires,
                "data_folder_name": host::folder_name(&self.data_dir),
                "week_starts_on": host::WEEK_STARTS[first_weekday as usize],
            })
            .to_string())
        })();
        finish("whoami", result)
    }

    #[tool(
        description = "The day: due soon, sessions, fixed blocks, next action, and workload",
        annotations(read_only_hint = true)
    )]
    async fn get_today(&self, Parameters(args): Parameters<TodayArgs>) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let date = match args.date.filter(|date| !date.is_empty()) {
                Some(date) => date,
                None => self.now()?.today,
            };
            let mut view = day_view(&conn, account_id(&account), &date).map_err(view_error)?;
            if let Some(ws) = view
                .get("week_start")
                .and_then(Value::as_str)
                .map(str::to_string)
            {
                week::add_week_starts_on(&mut view, &ws)?;
            }
            Ok(view.to_string())
        })();
        finish("get_today", result)
    }

    #[tool(
        description = "One week from the day weeks start on on this computer (whoami's week_starts_on), \
            with standing blocks merged, and its saved revision; a week that does not start on Monday \
            shows two saved weeks, with both revisions",
        annotations(read_only_hint = true)
    )]
    async fn get_week(&self, Parameters(args): Parameters<WeekArgs>) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = shown_week_view(
                &conn,
                account_id(&account),
                &args.week_start,
                self.first_weekday(),
            )?;
            Ok(view.to_string())
        })();
        finish("get_week", result)
    }

    #[tool(
        description = "One month: the grid, chips, deadlines, and overdue work",
        annotations(read_only_hint = true)
    )]
    async fn get_month(&self, Parameters(args): Parameters<MonthArgs>) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let first_weekday = self.first_weekday();
            let mut view = month_view_from(&conn, account_id(&account), &args.month, first_weekday)
                .map_err(view_error)?;
            if let Some(fields) = view.as_object_mut() {
                fields.insert(
                    "week_starts_on".into(),
                    json!(host::WEEK_STARTS[first_weekday as usize]),
                );
            }
            Ok(view.to_string())
        })();
        finish("get_month", result)
    }

    #[tool(
        description = "Homework with planned and unplanned minutes and the weeks that hold a session",
        annotations(read_only_hint = true)
    )]
    async fn list_homework(
        &self,
        Parameters(args): Parameters<HomeworkArgs>,
    ) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = shown_homework_list(
                &conn,
                account_id(&account),
                &args.week_start,
                args.include_completed.unwrap_or(false),
                self.first_weekday(),
            )?;
            Ok(view.to_string())
        })();
        finish("list_homework", result)
    }

    #[tool(description = "Saved routines", annotations(read_only_hint = true))]
    async fn list_routines(&self) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = routine_list(&conn, account_id(&account)).map_err(view_error)?;
            Ok(view.to_string())
        })();
        finish("list_routines", result)
    }

    #[tool(description = "Restore points", annotations(read_only_hint = true))]
    async fn list_restore_points(&self) -> Result<String, String> {
        let result = (|| {
            let account = session::for_read(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now()?.unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = restore_point_list(&conn, account_id(&account)).map_err(view_error)?;
            Ok(view.to_string())
        })();
        finish("list_restore_points", result)
    }
}
