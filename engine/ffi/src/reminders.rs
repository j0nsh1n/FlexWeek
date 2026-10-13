use chrono::{Datelike, Duration};
use flexweek_engine::desk::remind;
use serde_json::{Map, Value, json};

use crate::core::{FfiError, FlexWeek, Reminder, db_lock, engine_failure, failure, parse_local};

fn day_index(day: chrono::NaiveDate) -> i64 {
    i64::from(day.weekday().num_days_from_monday())
}

fn local_stamp(date: chrono::NaiveDate, hour: i64, minute: i64) -> String {
    format!("{date}T{hour:02}:{minute:02}")
}

fn reminder_days(
    from: &str,
    hours: u32,
) -> Result<
    (
        chrono::DateTime<chrono::FixedOffset>,
        chrono::DateTime<chrono::FixedOffset>,
    ),
    FfiError,
> {
    let start = parse_local(from)?;
    Ok((start, start + Duration::hours(i64::from(hours))))
}

fn fire_parts(
    date: chrono::NaiveDate,
    start_minute: i64,
    lead: i64,
) -> (chrono::NaiveDate, i64, i64) {
    let mut day = date;
    let mut minute = start_minute - lead.max(0);
    while minute < 0 {
        day -= Duration::days(1);
        minute += 24 * 60;
    }
    (day, minute.div_euclid(60), minute.rem_euclid(60))
}

pub(crate) fn upcoming(
    week: &FlexWeek,
    from_local: &str,
    hours: u32,
) -> Result<Vec<Reminder>, FfiError> {
    let (from, until) = reminder_days(from_local, hours)?;
    let mut reminders = Vec::new();
    let Some(user_id) = week.user_id else {
        return Ok(reminders);
    };
    let db = db_lock(week)?;
    let prefs_text = flexweek_store::preference_row(&db, user_id)
        .map_err(failure)?
        .unwrap_or_else(|| "{}".into());
    let prefs: Value = serde_json::from_str(&prefs_text).map_err(failure)?;
    let lead = i64::try_from(
        remind::reminder_lead_min(&prefs, remind::REMINDER_LEAD_DEFAULT_MIN)
            .map_err(engine_failure)?,
    )
    .map_err(failure)?;
    let block_reminders_enabled = prefs
        .get("reminders_enabled")
        .and_then(Value::as_i64)
        .unwrap_or(1)
        != 0;
    let alarms: Value = prefs
        .get("alarms_json")
        .and_then(Value::as_str)
        .map(serde_json::from_str)
        .transpose()
        .map_err(failure)?
        .unwrap_or_else(|| json!([]));
    let mut assignment_map = Map::new();
    for (body, _) in flexweek_store::assignment_bodies(&db, user_id).map_err(failure)? {
        let value: Value = serde_json::from_str(&body).map_err(failure)?;
        if let Some(id) = value.get("id").and_then(Value::as_str) {
            assignment_map.insert(id.to_string(), value);
        }
    }

    let first_date = from.date_naive();
    for offset in 0..3 {
        let date = first_date + Duration::days(offset);
        let date_text = date.format("%Y-%m-%d").to_string();
        let monday = flexweek_engine::time::monday_of(&date_text).map_err(engine_failure)?;
        let raw = flexweek_store::week_blocks(&db, user_id, &monday)
            .map_err(failure)?
            .unwrap_or_else(|| "[]".into());
        let merged =
            flexweek_store::week_with_standing(&db, user_id, &monday, &raw).map_err(failure)?;
        let stored_blocks: Value = serde_json::from_str(&merged).map_err(failure)?;
        let blocks = flexweek_store::rewrite_stored_blocks(
            &stored_blocks,
            &Value::Object(assignment_map.clone()),
            |block| Ok::<Value, std::convert::Infallible>(block.clone()),
        )
        .map_err(|relay| match relay {
            flexweek_store::Relay::Store(error) => failure(error),
            flexweek_store::Relay::Caller(error) => match error {},
        })?;

        if block_reminders_enabled {
            for (block, day, start_minute, _) in
                remind::todays_starts(&Value::Array(blocks.clone()), &Value::Null, &date_text)
                    .map_err(engine_failure)?
            {
                let block_id = block
                    .get("id")
                    .and_then(Value::as_str)
                    .ok_or_else(|| failure("reminder block has no id"))?;
                let start_text = block
                    .get("start")
                    .and_then(Value::as_str)
                    .ok_or_else(|| failure("reminder block has no start"))?;
                let day_number = day
                    .as_i64()
                    .ok_or_else(|| failure("reminder day is not a number"))?;
                let (fire_date, hour, minute) = fire_parts(date, start_minute, lead);
                let fire_at = fire_date
                    .and_hms_opt(hour as u32, minute as u32, 0)
                    .ok_or_else(|| failure("reminder time is outside the day"))?
                    .and_local_timezone(*from.offset())
                    .single()
                    .ok_or_else(|| failure("local reminder time is ambiguous"))?;
                if fire_at >= from && fire_at <= until {
                    reminders.push(Reminder {
                        id: remind::reminder_key(&monday, block_id, day_number, start_text),
                        title: block
                            .get("title")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                        local_time: local_stamp(fire_date, hour, minute),
                        kind: "block".into(),
                    });
                }
            }
        }

        let cutoff_ms = until.timestamp_millis();
        let from_ms = from.timestamp_millis();
        let mut added = Vec::new();
        let mut due_ms_of = |hour: i64, minute: i64| {
            date.and_hms_opt(hour as u32, minute as u32, 0)
                .ok_or_else(|| flexweek_engine::EngineError::value("invalid alarm time"))
                .and_then(|local| {
                    local
                        .and_local_timezone(*from.offset())
                        .single()
                        .map(|value| value.timestamp_millis())
                        .ok_or_else(|| flexweek_engine::EngineError::value("ambiguous alarm time"))
                })
        };
        let (due, _, _) = remind::due_alarms(
            &alarms,
            &date_text,
            day_index(date),
            cutoff_ms,
            Some(from_ms),
            &json!([]),
            true,
            &mut added,
            &json!({}),
            &mut due_ms_of,
        )
        .map_err(engine_failure)?;
        for alarm in due {
            let time = alarm
                .get("time")
                .and_then(Value::as_str)
                .unwrap_or_default();
            reminders.push(Reminder {
                id: remind::alarm_key(&date_text, &alarm).map_err(engine_failure)?,
                title: alarm
                    .get("name")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                local_time: format!("{date_text}T{time}"),
                kind: "alarm".into(),
            });
        }
    }
    reminders.sort_by(|left, right| {
        left.local_time
            .cmp(&right.local_time)
            .then_with(|| left.id.cmp(&right.id))
    });
    Ok(reminders)
}

#[cfg(test)]
mod tests {
    use crate::core::tests_support::{open_test, save_week};
    use serde_json::json;

    #[test]
    fn upcoming_reminders_uses_the_preference_lead_and_alarm_dates() {
        let (week, _path) = open_test("reminders");
        save_week(
            &week,
            "2026-10-12",
            &json!([
                {"id":"session","title":"Essay","kind":"flexible","days":[0],"start":"16:00","duration_min":60,"assignment_id":"essay"},
                {"id":"later","title":"Later","kind":"locked","days":[0],"start":"18:00","duration_min":30}
            ]),
        );
        {
            let db = week.db.lock().unwrap();
            db.execute(
                "UPDATE preferences SET reminder_lead_min=10, alarms_json=?1 WHERE user_id=?2",
                [
                    r#"[{"id":"wake","name":"Wake up","time":"16:15","days":[0],"enabled":true}]"#,
                    &week.user_id.unwrap().to_string(),
                ],
            )
            .unwrap();
            let _ = db.execute_batch("COMMIT");
        }
        let reminders = week
            .upcoming_reminders("2026-10-12T15:40:00-07:00".into(), 1)
            .unwrap();
        assert_eq!(reminders.len(), 2);
        assert_eq!(reminders[0].id, "2026-10-12|session|0|16:00");
        assert_eq!(reminders[0].kind, "block");
        assert_eq!(reminders[0].title, "Essay");
        assert_eq!(reminders[0].local_time, "2026-10-12T15:50");
        assert_eq!(reminders[1].id, "2026-10-12|wake|16:15");
        assert_eq!(reminders[1].kind, "alarm");
        assert_eq!(reminders[1].title, "Wake up");
        assert_eq!(reminders[1].local_time, "2026-10-12T16:15");
    }

    #[test]
    fn a_lead_that_crosses_midnight_fires_on_the_previous_evening() {
        let (week, _path) = open_test("midnight-reminder");
        save_week(
            &week,
            "2026-10-12",
            &json!([{"id":"night","title":"Night reading","kind":"flexible","days":[1],"start":"00:10","duration_min":30}]),
        );
        {
            let db = week.db.lock().unwrap();
            db.execute(
                "UPDATE preferences SET reminder_lead_min=15 WHERE user_id=?1",
                [week.user_id.unwrap()],
            )
            .unwrap();
            let _ = db.execute_batch("COMMIT");
        }
        let reminders = week
            .upcoming_reminders("2026-10-12T23:50:00-07:00".into(), 1)
            .unwrap();
        assert_eq!(reminders.len(), 1);
        assert_eq!(reminders[0].id, "2026-10-12|night|1|00:10");
        assert_eq!(reminders[0].local_time, "2026-10-12T23:55");
        assert_eq!(reminders[0].title, "Night reading");
        assert_eq!(reminders[0].kind, "block");
    }
}
