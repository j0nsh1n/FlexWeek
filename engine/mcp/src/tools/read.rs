//! Read tools. They check the session, then translate JSON to the store views.

use flexweek_store::{
    StoreError, day_view, homework_list, month_view_from, open_connection, restore_point_list,
    routine_list, week_view,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::json;

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
/// stored week from Monday, else the two it covers shown as one, days counted from `week_start`, with
/// both revisions, first week first.
fn shown_week_view(
    conn: &flexweek_store::Connection,
    user_id: i64,
    week_start: &str,
    first_weekday: u32,
) -> Result<serde_json::Value, String> {
    if first_weekday == 0 {
        return week_view(conn, user_id, week_start).map_err(view_error);
    }
    let day = host::WEEK_STARTS[first_weekday as usize];
    let refusal = || format!("week_start must be a {day}: weeks on this computer start on {day}");
    let starts =
        flexweek_engine::time::week_start_on(week_start, first_weekday).map_err(|_| refusal())?;
    if starts != week_start || !flexweek_engine::time::is_calendar_date(week_start) {
        return Err(refusal());
    }
    let Some((first, second, _)) =
        flexweek_engine::shown::shown_parts(week_start).map_err(|error| error.message)?
    else {
        return week_view(conn, user_id, week_start).map_err(view_error);
    };
    let first = week_view(conn, user_id, &first).map_err(view_error)?;
    let second = week_view(conn, user_id, &second).map_err(view_error)?;
    let blocks_of = |view: &serde_json::Value| -> Vec<serde_json::Value> {
        view.get("blocks")
            .and_then(serde_json::Value::as_array)
            .cloned()
            .unwrap_or_default()
    };
    let (first_blocks, second_blocks) = (blocks_of(&first), blocks_of(&second));
    // The homework its sessions belong to: one waiting for a time may run to its due date.
    let ids: Vec<String> = first_blocks
        .iter()
        .chain(&second_blocks)
        .filter_map(|block| {
            block
                .get("assignment_id")
                .and_then(serde_json::Value::as_str)
        })
        .map(str::to_string)
        .collect();
    let mut homework = serde_json::Map::new();
    for (id, body, _) in
        flexweek_store::load_assignment_rows(conn, user_id, &ids).map_err(view_error)?
    {
        let parsed = serde_json::from_str(&body)
            .map_err(|error| view_error(StoreError::Json { text: body, error }))?;
        homework.insert(id, parsed);
    }
    let blocks = flexweek_engine::shown::compose_shown_week_due(
        week_start,
        &first_blocks,
        &second_blocks,
        &homework,
    )
    .map_err(|error| error.message)?;
    Ok(json!({
        "week_start": week_start,
        "revision": [first["revision"], second["revision"]],
        "blocks": blocks,
    }))
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
            Ok(json!({
                "username": account.username,
                "session_expires": account.expires,
                "data_folder_name": host::folder_name(&self.data_dir),
                "week_starts_on": host::WEEK_STARTS[self.first_weekday as usize],
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
            let view = day_view(&conn, account_id(&account), &date).map_err(view_error)?;
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
                self.first_weekday,
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
            let view =
                month_view_from(&conn, account_id(&account), &args.month, self.first_weekday)
                    .map_err(view_error)?;
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
            let view = homework_list(
                &conn,
                account_id(&account),
                &args.week_start,
                args.include_completed.unwrap_or(false),
            )
            .map_err(view_error)?;
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
