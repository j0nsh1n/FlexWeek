use serde_json::{Map, Value, json};

use crate::account::{
    hex_id, remember, rollback, store_operation, stored_weeks, views_for_week, write_week,
};
use crate::core::{FfiError, FlexWeek, db_lock, engine_failure, failure, require_user};

const TITLE_TOO_LONG: &str = "String should have at most 80 characters";
const TITLE_REQUIRED: &str = "title required";
const ESTIMATE_RULE: &str = "estimate_min must be a positive multiple of 15";
const DUE_RULE: &str = "must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with no seconds or timezone";
const ID_RULE: &str = "String should have at most 80 characters";

pub(crate) fn recent_titles(week: &FlexWeek) -> Result<Vec<String>, FfiError> {
    let user_id = require_user(week)?;
    let db = db_lock(week)?;
    let mut statement = db
        .prepare("SELECT body FROM assignments WHERE user_id = ?1 ORDER BY rowid DESC")
        .map_err(failure)?;
    let rows = statement
        .query_map([user_id], |row| row.get::<_, String>(0))
        .map_err(failure)?;
    let mut seen = std::collections::HashSet::new();
    let mut titles = Vec::new();
    for stored in rows {
        let stored = stored.map_err(failure)?;
        let value: Value = serde_json::from_str(&stored).map_err(failure)?;
        if let Some(title) = value.get("title").and_then(Value::as_str)
            && seen.insert(title.to_lowercase())
        {
            titles.push(title.to_string());
            if titles.len() == 5 {
                break;
            }
        }
    }
    Ok(titles)
}

fn text_field<'a>(draft: &'a Map<String, Value>, key: &str) -> Result<Option<&'a str>, FfiError> {
    match draft.get(key) {
        None => Ok(None),
        Some(Value::String(text)) => Ok(Some(text.as_str())),
        Some(_) => Err(failure(format!("{key} must be a string"))),
    }
}

fn validate_draft(draft: &Map<String, Value>, generated_id: &str) -> Result<Value, FfiError> {
    let id = match text_field(draft, "id")? {
        Some("") => return Err(failure("String should have at least 1 character")),
        Some(id) if id.chars().count() > 80 => return Err(failure(ID_RULE)),
        Some(id) => id.to_string(),
        None => generated_id.to_string(),
    };
    let title = text_field(draft, "title")?.ok_or_else(|| failure(TITLE_REQUIRED))?;
    if title.trim().is_empty() {
        return Err(failure(TITLE_REQUIRED));
    }
    if title.chars().count() > 80 {
        return Err(failure(TITLE_TOO_LONG));
    }
    let due = text_field(draft, "due")?.ok_or_else(|| failure(DUE_RULE))?;
    flexweek_engine::model::valid_due(due).map_err(|_| failure(DUE_RULE))?;
    flexweek_engine::desk::calendar::parse_due(due).map_err(|_| failure(DUE_RULE))?;
    let estimate = draft
        .get("estimate_min")
        .and_then(Value::as_i64)
        .ok_or_else(|| failure(ESTIMATE_RULE))?;
    if estimate <= 0 || estimate % 15 != 0 {
        return Err(failure(ESTIMATE_RULE));
    }
    if estimate > flexweek_engine::model::ESTIMATE_MAX_MIN {
        return Err(failure(format!(
            "Input should be less than or equal to {}",
            flexweek_engine::model::ESTIMATE_MAX_MIN
        )));
    }
    let spread = match text_field(draft, "spread")? {
        None => "one",
        Some("one" | "spread") => draft.get("spread").and_then(Value::as_str).unwrap_or("one"),
        Some(_) => return Err(failure("Input should be 'one' or 'spread'")),
    };
    let mut body = json!({
        "id": id,
        "title": title,
        "due": due,
        "estimate_min": estimate,
        "priority": draft.get("priority").and_then(Value::as_i64).unwrap_or(3),
        "energy": draft.get("energy").and_then(Value::as_str).unwrap_or("medium"),
        "focus_minutes": draft.get("focus_minutes").and_then(Value::as_i64).unwrap_or(0),
        "focus_sessions": draft.get("focus_sessions").and_then(Value::as_i64).unwrap_or(0),
        "completed": draft.get("completed").and_then(Value::as_bool).unwrap_or(false),
        "completed_at": draft.get("completed_at").cloned().unwrap_or(Value::Null),
    });
    if spread != "one" {
        body["spread"] = json!(spread);
    }
    for key in ["course", "category", "spotify_url", "notes"] {
        if let Some(value) = draft.get(key) {
            body[key] = value.clone();
        }
    }
    Ok(body)
}

fn session_block(assignment: &Value, days: &[i64], duration: i64, session_id: &str) -> Value {
    json!({
        "id": session_id,
        "title": assignment.get("title").cloned().unwrap_or(json!("Homework")),
        "kind": "flexible",
        "duration_min": duration,
        "days": days,
        "priority": assignment.get("priority").cloned().unwrap_or(json!(3)),
        "energy": assignment.get("energy").cloned().unwrap_or(json!("medium")),
        "assignment_id": assignment.get("id"),
        "category": assignment.get("category").cloned().unwrap_or(json!("assignments")),
        "completed": false,
    })
}

pub(crate) fn save_homework(
    week: &FlexWeek,
    draft_json: &str,
    op_id: &str,
) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    let draft: Value = serde_json::from_str(draft_json).map_err(failure)?;
    let Some(fields) = draft.as_object() else {
        return Err(failure("draft is not an object"));
    };
    let generated = hex_id(&week.host.random_bytes(8));
    let body = validate_draft(fields, &generated)?;
    let assignment_id = body["id"].as_str().unwrap_or(&generated).to_string();
    let spread = body
        .get("spread")
        .and_then(Value::as_str)
        .unwrap_or("one")
        .to_string();
    let payload = json!(["save_homework", assignment_id, body]).to_string();
    let db = db_lock(week)?;
    if remember(&db, user_id, op_id, &payload)? {
        if let Some((_, stored, revision)) = flexweek_store::list_assignment_rows(&db, user_id)
            .map_err(failure)?
            .into_iter()
            .find(|(id, _, _)| id == &assignment_id)
        {
            let mut stored: Value = serde_json::from_str(&stored).map_err(failure)?;
            stored["revision"] = json!(revision);
            return Ok(stored.to_string());
        }
        return Ok(body.to_string());
    }
    let revision = fields
        .get("revision")
        .and_then(Value::as_i64)
        .unwrap_or_else(|| {
            flexweek_store::assignment_exists(&db, user_id, &assignment_id)
                .ok()
                .filter(|exists| *exists)
                .map(|_| -1)
                .unwrap_or(0)
        });
    let encoded = body.to_string();
    let saved_revision = match flexweek_store::save_assignment(
        &db,
        user_id,
        &assignment_id,
        &encoded,
        revision,
        i64::MAX,
    )
    .map_err(failure)?
    {
        flexweek_store::AssignmentSave::Ready(next) => next,
        flexweek_store::AssignmentSave::Conflict => {
            if revision < 0 {
                match flexweek_store::save_assignment(
                    &db,
                    user_id,
                    &assignment_id,
                    &encoded,
                    flexweek_store::list_assignment_rows(&db, user_id)
                        .ok()
                        .and_then(|rows| {
                            rows.into_iter()
                                .find(|(id, _, _)| id == &assignment_id)
                                .map(|(_, _, revision)| revision)
                        })
                        .unwrap_or(0),
                    i64::MAX,
                )
                .map_err(failure)?
                {
                    flexweek_store::AssignmentSave::Ready(next) => next,
                    flexweek_store::AssignmentSave::Conflict => {
                        rollback(&db);
                        return Err(failure("homework changed on another device"));
                    }
                    flexweek_store::AssignmentSave::OverLimit => {
                        rollback(&db);
                        return Err(failure("assignment limit reached"));
                    }
                }
            } else {
                rollback(&db);
                return Err(failure("homework changed on another device"));
            }
        }
        flexweek_store::AssignmentSave::OverLimit => {
            rollback(&db);
            return Err(failure("assignment limit reached"));
        }
    };
    let from_date = crate::core::parse_local(&week.host.local_now())?
        .format("%Y-%m-%d")
        .to_string();
    let due = body["due"].as_str().unwrap_or("");
    let estimate = body["estimate_min"].as_i64().unwrap_or(0);
    let focus = body["focus_minutes"].as_i64().unwrap_or(0);
    let mut weeks = stored_weeks(&db, user_id)?;
    let held: Vec<(String, Vec<Value>)> = weeks
        .iter()
        .map(|(start, blocks, _)| (start.clone(), blocks.clone()))
        .collect();
    let done = flexweek_engine::plan::done_minutes_by_id(&held)
        .get(body["id"].as_str().unwrap_or(""))
        .copied()
        .unwrap_or(0);
    if spread == "spread" && estimate >= 60 {
        // The homework's open sessions stay as they are, placed times included: only the minutes they
        // and its done time leave uncovered are spread, so a save that changes nothing adds nothing.
        let open = flexweek_engine::plan::planned_minutes_by_id(&held, "2000-01-01")
            .get(&assignment_id)
            .copied()
            .unwrap_or(0);
        let (sessions, _) = flexweek_engine::plan::spread_sessions(
            estimate, focus, done, open, due, 60, &from_date,
        )
        .map_err(engine_failure)?;
        for (index, session) in sessions.iter().enumerate() {
            let week_start = session["week_start"].as_str().unwrap_or("");
            let days = session
                .get("days")
                .and_then(Value::as_array)
                .map(|days| days.iter().filter_map(Value::as_i64).collect::<Vec<_>>())
                .unwrap_or_else(|| vec![0]);
            let duration = session["duration_min"].as_i64().unwrap_or(0);
            let base = format!("{assignment_id}-{week_start}-{index}");
            if let Some((_, blocks, _)) = weeks.iter_mut().find(|(start, _, _)| start == week_start)
            {
                // A new session never takes the id of one the week already holds.
                let taken = |id: &str| {
                    blocks
                        .iter()
                        .any(|item| item.get("id").and_then(Value::as_str) == Some(id))
                };
                let mut session_id = base.clone();
                let mut next = 1;
                while taken(&session_id) {
                    session_id = format!("{base}-{next}");
                    next += 1;
                }
                blocks.push(session_block(&body, &days, duration, &session_id));
            } else {
                let block = session_block(&body, &days, duration, &base);
                weeks.push((week_start.to_string(), vec![block], 0));
            }
        }
    } else {
        let week_start = flexweek_engine::time::monday_of(&from_date).map_err(engine_failure)?;
        let days = flexweek_engine::desk::planning::session_days(&week_start, &json!(due))
            .map_err(engine_failure)?;
        let session_id = format!("{assignment_id}-{week_start}");
        let block = session_block(&body, &days, estimate, &session_id);
        if let Some((_, blocks, _)) = weeks.iter_mut().find(|(start, _, _)| start == &week_start) {
            if !blocks.iter().any(|item| {
                item.get("assignment_id").and_then(Value::as_str) == Some(&assignment_id)
            }) {
                blocks.push(block);
            }
        } else {
            weeks.push((week_start, vec![block], 0));
        }
    }
    for (week_start, blocks, revision) in &weeks {
        write_week(
            &db,
            user_id,
            week_start,
            &Value::Array(blocks.clone()),
            *revision,
        )?;
    }
    if let Err(error) = store_operation(&db, user_id, op_id, &payload) {
        rollback(&db);
        return Err(error);
    }
    db.execute_batch("COMMIT").map_err(failure)?;
    let weeks = stored_weeks(&db, user_id)?;
    let rows = flexweek_store::list_assignment_rows(&db, user_id).map_err(failure)?;
    let mut keyed = Map::new();
    for (id, stored, _) in &rows {
        keyed.insert(id.clone(), serde_json::from_str(stored).map_err(failure)?);
    }
    let views = views_for_week(&keyed, &rows, &weeks, "2000-01-01")?;
    let mut saved = views.get(&assignment_id).cloned().unwrap_or(body);
    saved["revision"] = json!(saved_revision);
    drop(db);
    week.host.data_changed("homework".into());
    Ok(saved.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::open_test;
    use serde_json::json;

    fn details(error: FfiError) -> String {
        match error {
            FfiError::Failure { details } => details,
        }
    }

    #[test]
    fn save_homework_uses_the_desktop_validation_words() {
        let (week, _) = open_test("hw-validate");
        assert_eq!(
            details(
                week.save_homework(
                    r#"{"due":"2026-10-08T21:00","estimate_min":60}"#.into(),
                    "op-1".into()
                )
                .unwrap_err()
            ),
            "title required"
        );
        assert_eq!(
            details(
                week.save_homework(
                    r#"{"title":"   ","due":"2026-10-08T21:00","estimate_min":60}"#.into(),
                    "op-2".into()
                )
                .unwrap_err()
            ),
            "title required"
        );
        assert_eq!(
            details(
                week.save_homework(
                    r#"{"title":"Essay","due":"2026-10-08 21:00","estimate_min":60}"#.into(),
                    "op-3".into()
                )
                .unwrap_err()
            ),
            "must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with no seconds or timezone"
        );
        assert_eq!(
            details(
                week.save_homework(
                    r#"{"title":"Essay","due":"2026-10-08T21:00","estimate_min":10}"#.into(),
                    "op-4".into()
                )
                .unwrap_err()
            ),
            "estimate_min must be a positive multiple of 15"
        );
    }

    #[test]
    fn save_homework_writes_one_session_and_is_retry_safe() {
        let (week, _) = open_test("hw-save");
        let draft = json!({
            "id": "essay",
            "title": "History essay",
            "due": "2026-10-15T21:00",
            "estimate_min": 60,
        });
        let first: Value = serde_json::from_str(
            &week
                .save_homework(draft.to_string(), "op-hw".into())
                .unwrap(),
        )
        .unwrap();
        assert_eq!(first["id"], "essay");
        assert_eq!(first["title"], "History essay");
        assert_eq!(first["due"], "2026-10-15T21:00");
        let again: Value = serde_json::from_str(
            &week
                .save_homework(draft.to_string(), "op-hw".into())
                .unwrap(),
        )
        .unwrap();
        assert_eq!(again["id"], "essay");
        let db = week.db.lock().unwrap();
        let raw = flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-12")
            .unwrap()
            .unwrap();
        let blocks: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(blocks.as_array().unwrap().len(), 1);
        assert_eq!(blocks[0]["assignment_id"], "essay");
        assert_eq!(blocks[0]["duration_min"], 60);
        assert!(blocks[0].get("start").is_none());
    }

    #[test]
    fn a_spread_homework_grown_after_an_hour_ticked_done_gets_a_session_for_the_rest() {
        // Spread, 60 min, its one session ticked done; raised to 120 the done hour counts, so one
        // new hour is spread. Its id must not be the finished session's, which would drop it.
        let (week, _) = open_test("hw-spread-grown");
        let draft = |estimate: i64| {
            json!({"id": "essay", "title": "History essay", "due": "2026-10-15T21:00",
                   "estimate_min": estimate, "spread": "spread"})
        };
        let first: Value = serde_json::from_str(
            &week
                .save_homework(draft(60).to_string(), "op-spread-1".into())
                .unwrap(),
        )
        .unwrap();
        let user = week.user_id.unwrap();
        {
            let db = week.db.lock().unwrap();
            let raw = flexweek_store::week_blocks(&db, user, "2026-10-12")
                .unwrap()
                .unwrap();
            let mut blocks: Value = serde_json::from_str(&raw).unwrap();
            assert_eq!(blocks.as_array().unwrap().len(), 1);
            blocks[0]["completed"] = json!(true);
            db.execute(
                "UPDATE weeks SET blocks = ?1 WHERE user_id = ?2 AND week_start = '2026-10-12'",
                (blocks.to_string(), user),
            )
            .unwrap();
        }
        let mut grown = draft(120);
        grown["revision"] = first["revision"].clone();
        week.save_homework(grown.to_string(), "op-spread-2".into())
            .unwrap();
        let db = week.db.lock().unwrap();
        let raw = flexweek_store::week_blocks(&db, user, "2026-10-12")
            .unwrap()
            .unwrap();
        let blocks: Value = serde_json::from_str(&raw).unwrap();
        let open: i64 = blocks
            .as_array()
            .unwrap()
            .iter()
            .filter(|block| block["assignment_id"] == "essay" && block["completed"] != json!(true))
            .map(|block| block["duration_min"].as_i64().unwrap_or(0))
            .sum();
        assert_eq!(open, 60, "{blocks}");
    }

    #[test]
    fn a_spread_homework_saved_again_after_an_hour_ticked_done_keeps_its_time_once() {
        // Spread, 180 min in three hour sessions; the first is ticked done and one is given a time.
        // Saved again unchanged: the two open hours stay as they are (the placed one at its time)
        // and nothing is added, so 120 open minutes cover the 120 still to do. Saved a third time:
        // still nothing added.
        let (week, _) = open_test("hw-spread-resave");
        let draft = json!({"id": "essay", "title": "History essay", "due": "2026-10-15T21:00",
                           "estimate_min": 180, "spread": "spread"});
        let first: Value = serde_json::from_str(
            &week
                .save_homework(draft.to_string(), "op-resave-1".into())
                .unwrap(),
        )
        .unwrap();
        let user = week.user_id.unwrap();
        let read = |week: &FlexWeek| -> Value {
            let db = week.db.lock().unwrap();
            let raw = flexweek_store::week_blocks(&db, user, "2026-10-12")
                .unwrap()
                .unwrap();
            serde_json::from_str(&raw).unwrap()
        };
        let mut blocks = read(&week);
        let ours: Vec<usize> = (0..blocks.as_array().unwrap().len())
            .filter(|&at| blocks[at]["assignment_id"] == "essay")
            .collect();
        assert_eq!(ours.len(), 3, "{blocks}");
        blocks[ours[0]]["completed"] = json!(true);
        blocks[ours[1]]["start"] = json!("17:00");
        {
            let db = week.db.lock().unwrap();
            db.execute(
                "UPDATE weeks SET blocks = ?1 WHERE user_id = ?2 AND week_start = '2026-10-12'",
                (blocks.to_string(), user),
            )
            .unwrap();
        }
        let mut again = draft.clone();
        again["revision"] = first["revision"].clone();
        let second: Value = serde_json::from_str(
            &week
                .save_homework(again.to_string(), "op-resave-2".into())
                .unwrap(),
        )
        .unwrap();
        let open = |blocks: &Value| -> Vec<(i64, Option<String>)> {
            let mut open: Vec<(i64, Option<String>)> = blocks
                .as_array()
                .unwrap()
                .iter()
                .filter(|block| {
                    block["assignment_id"] == "essay" && block["completed"] != json!(true)
                })
                .map(|block| {
                    (
                        block["duration_min"].as_i64().unwrap_or(0),
                        block["start"].as_str().map(str::to_string),
                    )
                })
                .collect();
            open.sort();
            open
        };
        let expected = vec![(60, None), (60, Some("17:00".to_string()))];
        assert_eq!(open(&read(&week)), expected);
        let mut third = draft.clone();
        third["revision"] = second["revision"].clone();
        week.save_homework(third.to_string(), "op-resave-3".into())
            .unwrap();
        assert_eq!(open(&read(&week)), expected);
    }

    #[test]
    fn recent_titles_lists_the_latest_distinct_first() {
        let (week, _) = open_test("recent-title-order");
        for (id, title, due) in [
            ("one", "Essay", "2026-10-15"),
            ("two", "Lab", "2026-10-16"),
            ("three", "essay", "2026-10-17"),
        ] {
            week.save_homework(
                json!({"id":id,"title":title,"due":format!("{due}T23:59"),"estimate_min":60})
                    .to_string(),
                format!("op-{due}"),
            )
            .unwrap();
        }
        assert_eq!(recent_titles(&week).unwrap(), vec!["essay", "Lab"]);
    }

    #[test]
    fn phone_fixture_homework_save_matches_android_copy() {
        let (week, _) = open_test("homework-fixture");
        let mut result: Value = serde_json::from_str(&week.save_homework(
            r#"{"id":"fixture-homework","title":"History essay","due":"2026-10-23T23:59","estimate_min":60}"#.into(),
            "homework-fixture-op".into(),
        ).unwrap()).unwrap();
        result["id"] = json!("homework-id");
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/homework-save.json");
        let copy = root.join("../../android/app/src/test/resources/phone/homework-save.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        assert_eq!(std::fs::read_to_string(&fixture).unwrap(), text);
        assert_eq!(std::fs::read_to_string(&copy).unwrap(), text);
        assert_eq!(result["due"], "2026-10-23T23:59");
        assert_eq!(result["title"], "History essay");
    }
}
