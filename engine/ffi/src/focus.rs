use serde_json::{Map, Value, json};

use crate::agenda::{operation_seen, remember_operation};
use crate::core::{FlexWeek, db_lock, engine_failure, failure, parse_local, require_user};

fn decode(raw: &str) -> Result<Value, crate::core::FfiError> {
    serde_json::from_str(raw).map_err(failure)
}

pub(crate) fn begin(
    week: &FlexWeek,
    assignment_id: &str,
    saved: &str,
    replace: bool,
) -> Result<String, crate::core::FfiError> {
    begin_at(week, assignment_id, saved, replace, week.host.now_unix_ms())
}

fn begin_at(
    week: &FlexWeek,
    assignment_id: &str,
    saved: &str,
    replace: bool,
    now_ms: i64,
) -> Result<String, crate::core::FfiError> {
    let saved = decode(saved)?;
    let running = saved
        .get("running")
        .and_then(Value::as_bool)
        .unwrap_or_else(|| !saved.get("endsAt").is_none_or(Value::is_null));
    if running && !replace {
        let current = saved
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or("Focus session");
        let incoming = assignment_title(week, assignment_id)?;
        return Ok(
            json!({"kind":"needs_replace", "current":current, "incoming":incoming}).to_string(),
        );
    }
    let title = assignment_title(week, assignment_id)?;
    let local = parse_local(&week.host.local_now())?;
    let monday =
        flexweek_engine::time::monday_of(&local.date_naive().format("%Y-%m-%d").to_string())
            .map_err(engine_failure)?;
    let prefs: Value = serde_json::from_str(&week.settings_for_phone()?).map_err(failure)?;
    let target = json!({"assignmentId":assignment_id, "title":title, "weekStart":monday,
        "sessionId":format!("focus-{}", crate::account::hex_id(&week.host.random_bytes(8)))});
    let state = flexweek_engine::desk::focus::begin_state(&target, &prefs, now_ms)
        .map_err(engine_failure)?;
    Ok(json!({"kind":"started", "state":state, "persist":persist_value(&state)?}).to_string())
}

fn assignment_title(week: &FlexWeek, id: &str) -> Result<String, crate::core::FfiError> {
    let user = require_user(week)?;
    let db = db_lock(week)?;
    let found = flexweek_store::list_assignment_rows(&db, user)
        .map_err(failure)?
        .into_iter()
        .find(|(key, _, _)| key == id);
    let Some((_, raw, _)) = found else {
        return Err(failure("homework was not found"));
    };
    let body: Value = serde_json::from_str(&raw).map_err(failure)?;
    body.get("title")
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| failure("homework title was not found"))
}

pub(crate) fn pause(week: &FlexWeek, raw: &str) -> Result<String, crate::core::FfiError> {
    pause_at(raw, week.host.now_unix_ms())
}

fn pause_at(raw: &str, now_ms: i64) -> Result<String, crate::core::FfiError> {
    let state = decode(raw)?;
    let changed =
        flexweek_engine::desk::focus::pause_state(&state, now_ms).map_err(engine_failure)?;
    Ok(json!({"state":changed, "persist":persist_value(&changed)?}).to_string())
}

pub(crate) fn finish(raw: &str) -> Result<String, crate::core::FfiError> {
    let state = decode(raw)?;
    let finished = flexweek_engine::desk::focus::pause_state(&state, 0).map_err(engine_failure)?;
    let finished =
        flexweek_engine::desk::focus::set_phase(&finished, &json!("ended"), &json!({}), 0)
            .map_err(engine_failure)?;
    Ok(json!({"state":Value::Null,"focus_now":flexweek_engine::desk::focus::focus_now(&finished).map_err(engine_failure)?}).to_string())
}

pub(crate) fn persist(raw: &str) -> Result<String, crate::core::FfiError> {
    let state = decode(raw)?;
    Ok(persist_value(&state)?.to_string())
}

fn persist_value(state: &Value) -> Result<Value, crate::core::FfiError> {
    let mut payload = flexweek_engine::desk::focus::persist_payload(state)
        .map_err(engine_failure)?
        .unwrap_or(Value::Null);
    if let (Value::Object(target), Value::Object(source)) = (&mut payload, state) {
        for key in ["title", "workMin", "sessionId"] {
            if let Some(value) = source.get(key) {
                target.insert(key.into(), value.clone());
            }
        }
    }
    Ok(payload)
}

pub(crate) fn restore(week: &FlexWeek, raw: &str) -> Result<String, crate::core::FfiError> {
    let saved = decode(raw)?;
    let user = require_user(week)?;
    let db = db_lock(week)?;
    let rows = flexweek_store::list_assignment_rows(&db, user).map_err(failure)?;
    let mut assignments = Map::new();
    for (id, body, _) in rows {
        assignments.insert(id, serde_json::from_str(&body).map_err(failure)?);
    }
    let state = flexweek_engine::desk::focus::restore_state(
        &saved,
        &Value::Object(assignments),
        &json!([]),
        week.host.now_unix_ms(),
    )
    .map_err(engine_failure)?;
    drop(db);
    let mut result = state.unwrap_or(Value::Null);
    if let (Some(saved_fields), Some(fields)) = (saved.as_object(), result.as_object_mut()) {
        for key in ["sessionId", "workMin"] {
            if let Some(value) = saved_fields.get(key) {
                fields.insert(key.into(), value.clone());
            }
        }
    }
    if result.get("expired").and_then(Value::as_bool) == Some(true) && result["phase"] == "work" {
        if let (Some(id), Some(minutes), Some(session)) = (
            result.get("assignmentId").and_then(Value::as_str),
            result.get("workMin").and_then(Value::as_i64),
            result.get("sessionId").and_then(Value::as_str),
        ) {
            let _ = credit(week, id, minutes, &format!("focus-{session}"))?;
        }
        result = Value::Null;
    }
    Ok(json!({"state":result, "persist":if result.is_null(){Value::Null}else{persist_value(&result)?}}).to_string())
}

pub(crate) fn credit(
    week: &FlexWeek,
    assignment_id: &str,
    work_min: i64,
    op_id: &str,
) -> Result<String, crate::core::FfiError> {
    credit_with_revision(week, assignment_id, work_min, op_id, None)
}

fn credit_with_revision(
    week: &FlexWeek,
    assignment_id: &str,
    work_min: i64,
    op_id: &str,
    expected_revision: Option<i64>,
) -> Result<String, crate::core::FfiError> {
    let user = require_user(week)?;
    let payload = json!(["focus", assignment_id, work_min]).to_string();
    let db = db_lock(week)?;
    if operation_seen(&db, user, op_id, &payload)? {
        return Ok(json!({"ok":true,"replayed":true}).to_string());
    }
    let (raw, revision) = flexweek_store::list_assignment_rows(&db, user)
        .map_err(failure)?
        .into_iter()
        .find(|(id, _, _)| id == assignment_id)
        .map(|(_, body, rev)| (body, rev))
        .ok_or_else(|| failure("homework was not found"))?;
    let revision = expected_revision.unwrap_or(revision);
    let assignment: Value = serde_json::from_str(&raw).map_err(failure)?;
    let state = json!({"assignmentId":assignment_id});
    let credited =
        flexweek_engine::desk::focus::credit_target(&state, &assignment, &Value::Null, work_min)
            .map_err(engine_failure)?
            .ok_or_else(|| failure("focus session has no homework"))?;
    match flexweek_store::save_assignment(
        &db,
        user,
        assignment_id,
        &credited.to_string(),
        revision,
        i64::MAX,
    )
    .map_err(failure)?
    {
        flexweek_store::AssignmentSave::Ready(_) => (),
        flexweek_store::AssignmentSave::Conflict => {
            let _ = db.execute_batch("ROLLBACK");
            return Err(failure("homework changed on another device"));
        }
        flexweek_store::AssignmentSave::OverLimit => {
            let _ = db.execute_batch("ROLLBACK");
            return Err(failure("assignment limit reached"));
        }
    }
    remember_operation(&db, user, op_id, &payload)?;
    db.execute_batch("COMMIT").map_err(failure)?;
    drop(db);
    week.host.data_changed("assignments".into());
    Ok(json!({"ok":true,"assignment":credited}).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::open_at;
    use serde_json::json;

    fn homework(week: &FlexWeek, id: &str, title: &str) {
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(&db, week.user_id.unwrap(), id, &json!({"id":id,"title":title,"due":"2026-10-20T21:00","estimate_min":60,"focus_minutes":0,"focus_sessions":0,"completed":false}).to_string()).unwrap();
    }

    #[test]
    fn focus_begin_names_the_homework_and_sets_the_end() {
        let (week, _) = open_at("focus-begin", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let result: Value =
            serde_json::from_str(&begin_at(&week, "history", "null", false, 0).unwrap()).unwrap();
        assert_eq!(
            result["state"]["title"], "History essay",
            "focus names the homework"
        );
        assert_eq!(
            result["state"]["phase"], "work",
            "focus begins a work phase"
        );
        assert_eq!(
            result["state"]["endsAt"].as_i64(),
            Some(1_800_000),
            "default work timer ends after 30 minutes"
        );
    }

    #[test]
    fn focus_begin_refuses_an_unknown_homework() {
        let (week, _) = open_at("focus-missing", "2026-10-12T15:40:00");
        let result = begin(&week, "missing", "null", false);
        assert!(result.is_err(), "focus cannot start on an unknown homework");
        assert_eq!(
            result.unwrap_err().to_string(),
            "homework was not found",
            "unknown homework returns a clear error"
        );
    }

    #[test]
    fn focus_pause_keeps_the_time_left() {
        let (_week, _) = open_at("focus-pause", "2026-10-12T15:40:00");
        let state = json!({"assignmentId":"history","title":"History", "phase":"work", "running":true,"endsAt":2_400_000,"remainingMs":1_800_000,"weekStart":"2026-10-12","cycles":0,"workMin":30});
        let result: Value =
            serde_json::from_str(&pause_at(&state.to_string(), 1_200_000).unwrap()).unwrap();
        assert_eq!(
            result["state"]["remainingMs"], 1_200_000,
            "pause keeps the remaining 20 minutes"
        );
    }

    #[test]
    fn focus_pause_resumes_from_the_saved_time() {
        let (_week, _) = open_at("focus-resume", "2026-10-12T15:40:00");
        let state = json!({"assignmentId":"history","title":"History", "phase":"work", "running":true,"endsAt":1_800_000,"remainingMs":1_800_000,"weekStart":"2026-10-12","cycles":0,"workMin":30});
        let paused: Value =
            serde_json::from_str(&pause_at(&state.to_string(), 600_000).unwrap()).unwrap();
        let resumed: Value =
            serde_json::from_str(&pause_at(&paused["persist"].to_string(), 1_200_000).unwrap())
                .unwrap();
        assert_eq!(
            resumed["state"]["endsAt"], 2_400_000,
            "resume restores the saved 20 minutes"
        );
    }

    #[test]
    fn start_asks_before_replacing_a_running_timer() {
        let (week, _) = open_at("focus-replace-question", "2026-10-12T15:40:00");
        homework(&week, "bio", "Bio reading");
        let saved = json!({"running":true,"title":"History essay","endsAt":1_800_000}).to_string();
        let result: Value =
            serde_json::from_str(&begin(&week, "bio", &saved, false).unwrap()).unwrap();
        assert_eq!(
            result["kind"], "needs_replace",
            "a running timer asks before replacement"
        );
        assert_eq!(
            result["current"], "History essay",
            "the sheet names the current homework"
        );
        assert_eq!(
            result["incoming"], "Bio reading",
            "the sheet names the incoming homework"
        );
    }

    #[test]
    fn credit_adds_one_session_to_the_homework() {
        let (week, _) = open_at("focus-credit", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let before_revision =
            flexweek_store::list_assignment_rows(&week.db.lock().unwrap(), week.user_id.unwrap())
                .unwrap()[0]
                .2;
        let result: Value =
            serde_json::from_str(&credit(&week, "history", 30, "credit-one").unwrap()).unwrap();
        assert_eq!(
            result["assignment"]["focus_minutes"], 30,
            "a completed work phase adds its minutes"
        );
        assert_eq!(
            result["assignment"]["focus_sessions"], 1,
            "a completed work phase adds one session"
        );
        assert_eq!(
            result["assignment"]["completed"], false,
            "focus never completes homework"
        );
        assert_eq!(
            flexweek_store::list_assignment_rows(&week.db.lock().unwrap(), week.user_id.unwrap())
                .unwrap()[0]
                .2,
            before_revision + 1,
            "focus credit advances the homework revision"
        );
    }

    #[test]
    fn credit_never_completes_the_homework() {
        let (week, _) = open_at("focus-credit-open", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let answer: Value =
            serde_json::from_str(&credit(&week, "history", 30, "credit-open").unwrap()).unwrap();
        assert_eq!(
            answer["assignment"]["completed"], false,
            "focus minutes never complete homework"
        );
        assert!(
            answer["assignment"]["completed_at"].is_null(),
            "focus credit does not set a completion date"
        );
    }

    #[test]
    fn credit_on_a_changed_homework_is_refused() {
        let (week, _) = open_at("focus-credit-conflict", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let revision =
            flexweek_store::list_assignment_rows(&week.db.lock().unwrap(), week.user_id.unwrap())
                .unwrap()[0]
                .2;
        let result = credit_with_revision(&week, "history", 30, "credit-stale", Some(revision - 1));
        assert!(result.is_err(), "credit refuses a stale homework revision");
        assert_eq!(
            result.unwrap_err().to_string(),
            "homework changed on another device",
            "credit returns the conflict message"
        );
    }

    #[test]
    fn focus_restore_after_the_work_time_passed_credits_one_session() {
        let (week, _) = open_at("focus-restore-expired", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let saved = json!({"assignmentId":"history","title":"History essay","sessionId":"phase-one","phase":"work","cycles":0,"endsAt":1,"remainingMs":1_800_000,"weekStart":"2026-10-12","workMin":30}).to_string();
        let answer: Value = serde_json::from_str(&restore(&week, &saved).unwrap()).unwrap();
        assert!(
            answer["state"].is_null(),
            "an expired work timer clears after completing"
        );
        let row =
            flexweek_store::list_assignment_rows(&week.db.lock().unwrap(), week.user_id.unwrap())
                .unwrap()
                .remove(0);
        let saved: Value = serde_json::from_str(&row.1).unwrap();
        assert_eq!(
            saved["focus_minutes"], 30,
            "expired work adds one work length"
        );
        assert_eq!(saved["focus_sessions"], 1, "expired work adds one session");
    }

    #[test]
    fn focus_credit_for_one_phase_happens_once() {
        let (week, _) = open_at("focus-restore-dedupe", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let saved = json!({"assignmentId":"history","title":"History essay","sessionId":"phase-one","phase":"work","cycles":0,"endsAt":1,"remainingMs":1_800_000,"weekStart":"2026-10-12","workMin":30}).to_string();
        restore(&week, &saved).unwrap();
        restore(&week, &saved).unwrap();
        let row =
            flexweek_store::list_assignment_rows(&week.db.lock().unwrap(), week.user_id.unwrap())
                .unwrap()
                .remove(0);
        let body: Value = serde_json::from_str(&row.1).unwrap();
        assert_eq!(
            body["focus_minutes"], 30,
            "restoring the same expired phase credits its minutes once"
        );
        assert_eq!(
            body["focus_sessions"], 1,
            "restoring the same expired phase credits one session"
        );
    }

    #[test]
    fn phone_credit_reaches_the_desktop_record() {
        let (phone, _) = open_at("focus-sync-phone", "2026-10-12T15:40:00");
        homework(&phone, "history", "History essay");
        let answer: Value =
            serde_json::from_str(&credit(&phone, "history", 30, "focus-sync").unwrap()).unwrap();
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../target/ffi-tests/focus-sync-desktop.sqlite");
        let _ = std::fs::remove_file(&path);
        flexweek_store::initialize(&path, "2026-10-12").unwrap();
        let mut desktop = flexweek_store::open_connection(&path).unwrap();
        let user = flexweek_store::insert_user(&desktop, "desktop", "test").unwrap();
        flexweek_store::insert_preferences(&desktop, user, 2).unwrap();
        desktop.execute_batch("COMMIT").unwrap();
        flexweek_sync::migrate(&desktop).unwrap();
        flexweek_sync::set_device(&desktop, "desktop", "desktop").unwrap();
        flexweek_sync::set_account(&desktop, user, "focus-sync-account").unwrap();
        let batch = flexweek_sync::Batch {
            account_uuid: flexweek_sync::account_uuid(&desktop, user).unwrap(),
            from_device: "phone".into(),
            records: vec![flexweek_sync::Record {
                entity: "assignment".into(),
                key: "history".into(),
                body: Some(answer["assignment"].clone()),
                hlc: 1,
                device_id: "phone".into(),
                seq: 1,
            }],
            next_since: 1,
            more: false,
        };
        flexweek_sync::apply_batch(&mut desktop, &batch, 1_800_000).unwrap();
        let saved: Value = serde_json::from_str(
            &flexweek_store::list_assignment_rows(&desktop, user).unwrap()[0].1,
        )
        .unwrap();
        assert_eq!(
            saved["focus_minutes"], 30,
            "the synced desktop assignment contains the phone's minutes"
        );
        assert_eq!(
            saved["focus_sessions"], 1,
            "the synced desktop assignment contains one phone session"
        );
    }

    #[test]
    fn phone_fixture_credit_matches_android_copy() {
        fn paths(name: &str) -> (std::path::PathBuf, std::path::PathBuf) {
            let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
            (
                root.join("tests/fixtures/phone").join(name),
                root.join("../../android/app/src/test/resources/phone")
                    .join(name),
            )
        }
        let (week, _) = open_at("focus-fixture", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        homework(&week, "bio", "Bio reading");
        let running: Value =
            serde_json::from_str(&begin_at(&week, "history", "null", false, 0).unwrap()).unwrap();
        let paused: Value =
            serde_json::from_str(&pause_at(&running["state"].to_string(), 1_200_000).unwrap())
                .unwrap();
        let replace: Value = serde_json::from_str(
            &begin(&week, "bio", &running["persist"].to_string(), false).unwrap(),
        )
        .unwrap();
        let credit_result = credit(&week, "history", 30, "fixture-credit").unwrap();
        let values = [
            ("focus-running.json", running["persist"].clone()),
            ("focus-paused.json", paused["persist"].clone()),
            ("focus-replace.json", replace),
            (
                "focus-credit.json",
                serde_json::from_str(&credit_result).unwrap(),
            ),
        ];
        for (name, value) in values {
            let text = format!("{}\n", serde_json::to_string_pretty(&value).unwrap());
            let (fixture, android) = paths(name);
            if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
                for path in [&fixture, &android] {
                    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                    std::fs::write(path, &text).unwrap();
                }
            }
            assert!(
                fixture.exists(),
                "real focus fixture {} exists",
                fixture.display()
            );
            let saved = std::fs::read_to_string(&fixture).unwrap();
            assert_eq!(
                saved, text,
                "real focus output changed; update fixture {name}"
            );
            assert_eq!(
                std::fs::read_to_string(&android).expect("the Android focus copy exists"),
                saved,
                "Android focus fixture {name} differs from Rust output"
            );
        }
    }

    #[test]
    fn replace_starts_the_new_timer() {
        let (week, _) = open_at("focus-replace", "2026-10-12T15:40:00");
        homework(&week, "bio", "Bio reading");
        let saved = json!({"running":true,"assignmentId":"history","title":"History essay","endsAt":1_800_000}).to_string();
        let result: Value =
            serde_json::from_str(&begin(&week, "bio", &saved, true).unwrap()).unwrap();
        assert_eq!(
            result["kind"], "started",
            "Replace starts the incoming homework"
        );
        assert_eq!(
            result["state"]["title"], "Bio reading",
            "the incoming homework owns the new timer"
        );
    }

    #[test]
    fn replace_does_not_credit_the_old_timer() {
        let (week, _) = open_at("focus-replace-credit", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        homework(&week, "bio", "Bio reading");
        let saved = json!({"running":true,"assignmentId":"history","title":"History essay","endsAt":1_800_000}).to_string();
        let _ = begin(&week, "bio", &saved, true).unwrap();
        let db = week.db.lock().unwrap();
        let rows = flexweek_store::list_assignment_rows(&db, week.user_id.unwrap()).unwrap();
        let history: Value =
            serde_json::from_str(&rows.iter().find(|(id, _, _)| id == "history").unwrap().1)
                .unwrap();
        assert_eq!(
            history["focus_minutes"], 0,
            "replacing a timer does not credit its homework"
        );
    }

    #[test]
    fn focus_finish_clears_the_running_state() {
        let raw = json!({"phase":"work","running":true,"endsAt":1_800_000,"remainingMs":1_800_000,"workMin":30}).to_string();
        let result: Value = serde_json::from_str(&finish(&raw).unwrap()).unwrap();
        assert!(result["state"].is_null(), "Finish clears the saved timer");
        assert_eq!(result["focus_now"], "", "Finish no longer reports focusing");
    }

    #[test]
    fn focus_restore_of_a_paused_timer_keeps_its_time() {
        let (week, _) = open_at("focus-restore-paused", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let saved = json!({"assignmentId":"history","title":"History essay","phase":"work","cycles":0,"endsAt":null,"remainingMs":600_000,"weekStart":"2026-10-12","workMin":30}).to_string();
        let result: Value = serde_json::from_str(&restore(&week, &saved).unwrap()).unwrap();
        assert_eq!(
            result["state"]["remainingMs"], 600_000,
            "restoring a paused timer keeps its saved time"
        );
        assert_eq!(
            result["state"]["running"], false,
            "a paused timer stays paused"
        );
    }

    #[test]
    fn focus_persist_keeps_the_work_length() {
        let state = json!({"assignmentId":"history","title":"History essay","sessionId":"phase-one","weekStart":"2026-10-12","phase":"work","cycles":0,"running":false,"remainingMs":600_000,"workMin":45});
        let result: Value = serde_json::from_str(&persist(&state.to_string()).unwrap()).unwrap();
        assert_eq!(
            result["workMin"], 45,
            "persisted focus keeps the work length it began with"
        );
        assert_eq!(
            result["title"], "History essay",
            "persisted focus keeps the homework title"
        );
        assert_eq!(
            result["sessionId"], "phase-one",
            "persisted focus keeps its credit id"
        );
    }

    #[test]
    fn credit_retry_with_the_same_op_id_writes_once() {
        let (week, _) = open_at("focus-credit-retry", "2026-10-12T15:40:00");
        homework(&week, "history", "History essay");
        let first = credit(&week, "history", 30, "credit-retry");
        assert!(first.is_ok(), "first focus credit is saved");
        let retry = credit(&week, "history", 30, "credit-retry");
        assert!(
            retry.is_ok(),
            "retrying the same focus operation is accepted"
        );
        let db = week.db.lock().unwrap();
        let row = flexweek_store::list_assignment_rows(&db, week.user_id.unwrap())
            .unwrap()
            .remove(0);
        let saved: Value = serde_json::from_str(&row.1).unwrap();
        assert_eq!(
            saved["focus_minutes"], 30,
            "retrying a focus credit does not add minutes twice"
        );
        assert_eq!(
            saved["focus_sessions"], 1,
            "retrying a focus credit does not add a session twice"
        );
    }
}
