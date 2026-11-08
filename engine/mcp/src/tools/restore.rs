//! `restore_point` brings the account back to one restore point in one step, as the desktop's
//! Restore does (`backend/app.py` `restore_restore_point`): a "Before restore" point first, so the
//! restore can be undone, then every week, homework and the standing week as the point holds them.

use flexweek_store::{
    StoreError, create_restore_point, recall_operation, remember_operation, replace_account,
    replace_standing, restore_point_body,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Value, json};

use super::homework;
use super::write::{self, OPERATION_CONFLICT, REACHES_PHONE};
use crate::session;

const RESTORE_UNKNOWN: &str = "Restore point not found";
/// `changes.rs` keeps 20 restore points and 100 operations; those constants are private.
const MAX_RESTORE_POINTS: i64 = 20;
const MAX_OPERATIONS: i64 = 100;

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct RestoreArgs {
    operation_id: String,
    /// A restore point id from `list_restore_points`.
    id: String,
}

fn stored_error(error: StoreError) -> String {
    session::storage_sentence(error)
}

fn text_of(value: &Value) -> String {
    flexweek_engine::snapshot::canonical(value)
}

fn int_of(value: &Value) -> i64 {
    value.as_i64().unwrap_or(0)
}

fn replace(
    conn: &flexweek_store::Connection,
    user_id: i64,
    stored: &Value,
) -> Result<Value, String> {
    let mut weeks = Vec::new();
    for week in stored["weeks"].as_array().into_iter().flatten() {
        let start = week["week_start"].as_str().unwrap_or_default().to_string();
        weeks.push((start, text_of(&week["blocks"]), int_of(&week["revision"])));
    }
    let mut assignments = Vec::new();
    for item in stored["assignments"].as_array().into_iter().flatten() {
        let id = item["id"].as_str().unwrap_or_default().to_string();
        assignments.push((id, text_of(&item["body"]), int_of(&item["revision"])));
    }
    replace_account(conn, user_id, &weeks, &assignments).map_err(|error| match error {
        StoreError::RepeatedBlockId(id) => {
            format!("A week in this restore point repeats the block id {id}")
        }
        other => stored_error(other),
    })?;
    // A point made before 0.19.0 has no standing week, so the current one stays.
    if let Some(standing) = stored.get("standing") {
        replace_standing(conn, user_id, &text_of(standing)).map_err(stored_error)?;
    }
    Ok(json!({
        "weeks": weeks.iter().map(|(start, _, revision)| json!({"week_start": start, "revision": revision})).collect::<Vec<_>>(),
        "assignments": assignments.iter().map(|(id, _, revision)| json!({"id": id, "revision": revision})).collect::<Vec<_>>(),
    }))
}

fn perform(app: &crate::App, args: &RestoreArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest =
        write::argument_digest("restore_point", &args.operation_id, &json!({"id": args.id}));
    let (conn, user_id) = (&opened.conn, opened.user_id);
    let now = homework::clock_of(app).now;
    // A replay or a clashing reuse of the operation id is answered before the prune, so it changes
    // nothing, not even an old assistant restore point.
    let early = match recall_operation(conn, user_id, &operation_id, &digest).map_err(stored_error)
    {
        Ok(flexweek_store::Recall::Hit(text)) => Some(
            serde_json::from_str::<Value>(&text)
                .map_err(|_| session::STORAGE_UNAVAILABLE.to_string()),
        ),
        Ok(flexweek_store::Recall::Conflict) => Some(Err(OPERATION_CONFLICT.to_string())),
        Ok(flexweek_store::Recall::Missing) => None,
        Err(message) => Some(Err(message)),
    };
    if let Some(answer) = early {
        let _ = conn.execute_batch("ROLLBACK");
        return write::stable(answer?);
    }
    let (token, _) = write::restore_point_before(
        conn,
        user_id,
        "restore_point",
        &operation_id,
        Some(&args.id),
        &now,
    )?;
    // `homework::open` already holds the write lock, as every write does, so the point read here is
    // the one replaced, and a restore sent beside other writes waits its turn.
    let result = (|| {
        let Some((point_id, body)) =
            restore_point_body(conn, user_id, &args.id).map_err(stored_error)?
        else {
            return Err(RESTORE_UNKNOWN.to_string());
        };
        let stored: Value =
            serde_json::from_str(&body).map_err(|_| session::STORAGE_UNAVAILABLE.to_string())?;
        let recovery = create_restore_point(
            conn,
            user_id,
            &token,
            &format!("Before restore — {now}"),
            &now,
            std::slice::from_ref(&point_id),
            MAX_RESTORE_POINTS,
        )
        .map_err(stored_error)?;
        let replaced = replace(conn, user_id, &stored)?;
        let answer = json!({
            "ok": true,
            "result": {
                "id": point_id,
                "recovery_id": recovery["id"],
                "weeks": replaced["weeks"],
                "assignments": replaced["assignments"],
            },
            "reaches_phone": REACHES_PHONE,
        });
        remember_operation(
            conn,
            user_id,
            &operation_id,
            &digest,
            &flexweek_engine::snapshot::canonical(&answer),
            MAX_OPERATIONS,
        )
        .map_err(stored_error)?;
        Ok(answer)
    })();
    match &result {
        Ok(_) => conn
            .execute_batch("COMMIT")
            .map_err(|error| stored_error(StoreError::from(error)))?,
        Err(_) => {
            let _ = conn.execute_batch("ROLLBACK");
        }
    }
    write::stable(result?)
}

#[tool_router(router = restore_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Bring the schedule back to a restore point from list_restore_points, in one \
            step. Every assistant change saves one first, labelled for the tool. The restore saves \
            a point of its own first (recovery_id), so it can be undone the same way",
        annotations(destructive_hint = true, read_only_hint = false)
    )]
    async fn restore_point(
        &self,
        Parameters(args): Parameters<RestoreArgs>,
    ) -> Result<String, String> {
        write::finish("restore_point", perform(self, &args))
    }
}
