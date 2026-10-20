//! Read tools. They check the session, then translate JSON to the store views.

use flexweek_store::{
    StoreError, day_view, homework_list, month_view, open_connection, restore_point_list,
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

#[tool_router(router = read_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Who is signed in on this computer",
        annotations(read_only_hint = true)
    )]
    async fn whoami(&self) -> Result<String, String> {
        let result = (|| {
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
            )?;
            Ok(json!({
                "username": account.username,
                "session_expires": account.expires,
                "data_folder_name": host::folder_name(&self.data_dir),
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
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let date = args
                .date
                .filter(|date| !date.is_empty())
                .unwrap_or_else(|| self.today.clone());
            let view = day_view(&conn, account_id(&account), &date).map_err(view_error)?;
            Ok(view.to_string())
        })();
        finish("get_today", result)
    }

    #[tool(
        description = "One week, with standing blocks merged, and its saved revision",
        annotations(read_only_hint = true)
    )]
    async fn get_week(&self, Parameters(args): Parameters<WeekArgs>) -> Result<String, String> {
        let result = (|| {
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view =
                week_view(&conn, account_id(&account), &args.week_start).map_err(view_error)?;
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
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = month_view(&conn, account_id(&account), &args.month).map_err(view_error)?;
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
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
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
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
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
            let account = session::for_call(
                self.started_as.as_ref(),
                &self.session_file,
                &self.database,
                self.now_unix,
            )?;
            let conn = open_connection(&self.database).map_err(session::storage_sentence)?;
            let view = restore_point_list(&conn, account_id(&account)).map_err(view_error)?;
            Ok(view.to_string())
        })();
        finish("list_restore_points", result)
    }
}
