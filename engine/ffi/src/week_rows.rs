use serde_json::{Value, json};

use crate::account::{assignment_map, load_open_week};
use crate::core::{FfiError, FlexWeek, db_lock, engine_failure, failure, require_user};

const DAYS_IN_WEEK: i64 = 7;
const HEAVY_THRESHOLD_MINUTES: i64 = 180;

fn is_homework(item: &Value) -> bool {
    item.get("work").and_then(Value::as_bool) == Some(true)
        || item.get("assignment_id").and_then(Value::as_str).is_some()
        || item.get("category").and_then(Value::as_str) == Some("assignments")
}

pub(crate) fn week_rows(week: &FlexWeek, week_start: &str) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    if week_start
        != flexweek_engine::time::monday_of(week_start).map_err(crate::core::engine_failure)?
    {
        return Err(failure("week_start must be a Monday"));
    }
    let start = chrono::NaiveDate::parse_from_str(week_start, "%Y-%m-%d").map_err(failure)?;
    let db = db_lock(week)?;
    let (keyed, _, _) = assignment_map(&db, user_id)?;
    let assignments = Value::Object(keyed);
    let (blocks, _) = load_open_week(&db, user_id, week_start, &assignments)?;
    drop(db);
    let model = flexweek_engine::desk::weekmodel::build_week(
        &json!(week_start),
        &Value::Array(blocks.clone()),
        &assignments,
        &json!({}),
    )
    .map_err(engine_failure)?;
    let occurrences = model["occurrences"].as_array().cloned().unwrap_or_default();
    let mut days = Vec::new();
    for day in 0..DAYS_IN_WEEK {
        let mut planned: Vec<(i64, String, i64)> = occurrences
            .iter()
            .filter(|item| item["day"].as_i64() == Some(day) && is_homework(item))
            .filter_map(|item| {
                Some((
                    item["start"].as_i64()?,
                    item["title"].as_str()?.to_string(),
                    item["end"].as_i64()? - item["start"].as_i64()?,
                ))
            })
            .collect();
        planned.sort_by_key(|(minute, _, _)| *minute);
        let minutes: i64 = planned.iter().map(|(_, _, length)| *length).sum();
        let mut named: Vec<(i64, String)> = planned
            .iter()
            .map(|(at, title, _)| (*at, title.clone()))
            .collect();
        for item in occurrences
            .iter()
            .filter(|item| item["day"].as_i64() == Some(day) && !is_homework(item))
        {
            if matches!(item["category"].as_str(), Some("class" | "sleep" | "free")) {
                continue;
            }
            if let (Some(at), Some(title)) = (item["start"].as_i64(), item["title"].as_str()) {
                named.push((at, title.to_string()));
            }
        }
        named.sort_by_key(|(at, _)| *at);
        let mut names: Vec<String> = named.into_iter().map(|(_, title)| title).collect();
        let unplaced: Vec<String> = blocks
            .iter()
            .filter(|item| is_homework(item) && item.get("start").is_none_or(Value::is_null))
            .filter(|item| {
                item["days"].as_array().is_some_and(|days| {
                    days.iter().any(|candidate| candidate.as_i64() == Some(day))
                })
            })
            .filter_map(|item| item["title"].as_str().map(str::to_string))
            .collect();
        let date = (start + chrono::Days::new(day as u64)).to_string();
        for (id, assignment) in assignments
            .as_object()
            .into_iter()
            .flat_map(|entries| entries.iter())
        {
            let due_today = assignment["due"]
                .as_str()
                .is_some_and(|due| due.get(..10) == Some(date.as_str()));
            let planned_today = occurrences.iter().any(|item| {
                item["day"].as_i64() == Some(day) && item["assignment_id"].as_str() == Some(id)
            });
            if due_today && !planned_today && !assignment["completed"].as_bool().unwrap_or(false) {
                names.push(format!(
                    "{} due",
                    assignment["title"].as_str().unwrap_or("Untitled")
                ));
            }
        }
        if names.is_empty()
            && occurrences.iter().any(|item| {
                item["day"].as_i64() == Some(day) && item["category"].as_str() == Some("class")
            })
        {
            names.push("School only".into());
        }
        let last_class_end = occurrences
            .iter()
            .filter(|item| {
                item["day"].as_i64() == Some(day) && item["category"].as_str() == Some("class")
            })
            .filter_map(|item| item["end"].as_i64())
            .max();
        days.push(json!({"day":day,"date":(start + chrono::Days::new(day as u64)).to_string(),"names":names,"minutes":minutes,"heavy":is_heavy(minutes),"unplaced":unplaced,"last_class_end":last_class_end}));
    }
    Ok(json!({"week_start": week_start, "days": days}).to_string())
}

pub(crate) fn is_heavy(minutes: i64) -> bool {
    minutes > HEAVY_THRESHOLD_MINUTES
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_test, save_week};
    use crate::week_rows;
    use serde_json::json;

    const MONDAY: &str = "2026-10-19";
    const DAYS_IN_WEEK: usize = 7;
    const HEAVY_MINUTES: i64 = 180;
    const HEAVY_SAMPLE_MINUTES: i64 = 195;

    fn fixture_week(name: &str) -> std::sync::Arc<FlexWeek> {
        let (week, _) = open_test(name);
        week.save_homework(
            json!({"id":"english-log","title":"English log","due":"2026-10-25T23:59","estimate_min":30}).to_string(),
            format!("{name}-homework"),
        ).unwrap();
        save_week(
            &week,
            MONDAY,
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0,1,2,3,4],"start":"08:00","duration_min":390,"category":"class"},
                {"id":"essay","title":"History essay","kind":"flexible","days":[0],"start":"15:00","duration_min":60,"category":"assignments","work":true},
                {"id":"reading","title":"Bio reading","kind":"flexible","days":[0],"start":"16:00","duration_min":30,"category":"assignments","work":true},
                {"id":"soccer","title":"Soccer","kind":"locked","days":[1],"start":"17:00","duration_min":60,"category":"sport"},
                {"id":"unplaced","title":"Chem lab write-up","kind":"flexible","days":[1],"duration_min":45,"category":"assignments","work":true},
                {"id":"piano","title":"Piano","kind":"locked","days":[2],"start":"18:00","duration_min":60,"category":"activity"},
                {"id":"cafe","title":"Cafe shift","kind":"locked","days":[5],"start":"10:00","duration_min":120,"category":"work"},
                {"id":"due","title":"English log","kind":"flexible","days":[6],"duration_min":30,"category":"assignments","work":true,"assignment_id":"english-log"}
            ]),
        );
        week
    }

    fn rows(week: &FlexWeek) -> Value {
        serde_json::from_str(&week.week_rows(MONDAY.to_string()).unwrap()).unwrap()
    }

    #[test]
    fn week_rows_has_seven_days_in_order() {
        let output = rows(&fixture_week("week-rows-days"));
        let days = output["days"].as_array().unwrap();
        assert_eq!(
            days.len(),
            DAYS_IN_WEEK,
            "the week contains one row for each of seven days"
        );
        for (index, day) in days.iter().enumerate() {
            assert_eq!(
                day["day"],
                json!(index),
                "week rows are Monday through Sunday"
            );
            assert_eq!(
                day["date"],
                json!(
                    chrono::NaiveDate::parse_from_str(MONDAY, "%Y-%m-%d")
                        .unwrap()
                        .checked_add_days(chrono::Days::new(index as u64))
                        .unwrap()
                        .to_string()
                )
            );
        }
    }

    #[test]
    fn week_rows_names_the_homework_of_each_day() {
        let output = rows(&fixture_week("week-rows-names"));
        assert_eq!(
            output["days"][0]["names"],
            json!(["History essay", "Bio reading"]),
            "Monday names both planned homework items in start order"
        );
        assert_eq!(
            output["days"][0]["minutes"],
            json!(90),
            "Monday homework total is 90 minutes"
        );
        assert_eq!(
            output["days"][1]["names"],
            json!(["Soccer"]),
            "fixed activities are named after homework"
        );
        assert_eq!(
            output["days"][2]["names"],
            json!(["Piano"]),
            "fixed activities appear in their row"
        );
        assert_eq!(
            output["days"][4]["names"],
            json!(["School only"]),
            "class blocks are not named individually"
        );
        assert_eq!(
            output["days"][5]["names"],
            json!(["Cafe shift"]),
            "a fixed activity appears on a class-free day"
        );
        assert_eq!(
            output["days"][6]["names"],
            json!(["English log due"]),
            "homework due that day without a planned session is named"
        );
    }

    #[test]
    fn week_rows_heavy_is_more_than_three_hours() {
        assert!(
            !week_rows::is_heavy(HEAVY_MINUTES),
            "180 minutes is not heavy"
        );
        assert!(
            week_rows::is_heavy(HEAVY_SAMPLE_MINUTES),
            "195 minutes is heavy"
        );
    }

    #[test]
    fn week_rows_counts_placed_time_only() {
        let output = rows(&fixture_week("week-rows-placed"));
        assert_eq!(
            output["days"][1]["minutes"],
            json!(0),
            "unplaced homework does not add to planned minutes"
        );
        assert_eq!(
            output["days"][1]["unplaced"],
            json!(["Chem lab write-up"]),
            "unplaced homework is reported separately"
        );
    }

    #[test]
    fn phone_fixture_week_rows_matches_android_copy() {
        let result = rows(&fixture_week("week-rows-fixture"));
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/week-rows.json");
        let copy = root.join("../../android/app/src/test/resources/phone/week-rows.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        assert_eq!(std::fs::read_to_string(&fixture).unwrap(), text);
        assert_eq!(std::fs::read_to_string(&copy).unwrap(), text);
        assert_eq!(
            result["days"][0]["names"],
            json!(["History essay", "Bio reading"])
        );
        assert_eq!(result["days"][0]["minutes"], 90);
    }
}
