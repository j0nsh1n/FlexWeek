use serde_json::{Value, json};

use crate::account::load_open_week;
use crate::core::{FfiError, FlexWeek, db_lock, engine_failure, failure, require_user};

fn category_of(item: &Value) -> String {
    let raw = item
        .get("category")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    if flexweek_engine::desk::calendar::CATEGORIES
        .iter()
        .any(|(key, _)| *key == raw)
    {
        return raw;
    }
    if item.get("work").and_then(Value::as_bool) == Some(true)
        || item.get("assignment_id").and_then(Value::as_str).is_some()
    {
        return "assignments".into();
    }
    "free".into()
}

fn colour(category: &str) -> &'static str {
    flexweek_engine::desk::calendar::CATEGORIES
        .iter()
        .find(|(key, _)| *key == category)
        .map(|(_, info)| info.mark)
        .unwrap_or("#82878c")
}

fn whole(value: Option<&Value>) -> Option<i64> {
    value.and_then(|item| {
        item.as_i64().or_else(|| {
            item.as_f64()
                .and_then(|number| (number.fract() == 0.0).then_some(number as i64))
        })
    })
}

pub(crate) fn week_shape(week: &FlexWeek, week_start: &str) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    if week_start != flexweek_engine::time::monday_of(week_start).map_err(engine_failure)? {
        return Err(failure("week_start must be a Monday"));
    }
    let db = db_lock(week)?;
    let (keyed, _, _) = crate::account::assignment_map(&db, user_id)?;
    let assignments = Value::Object(keyed);
    let (blocks, _) = load_open_week(&db, user_id, week_start, &assignments)?;
    let model = flexweek_engine::desk::weekmodel::build_week(
        &json!(week_start),
        &Value::Array(blocks),
        &assignments,
        &json!({}),
    )
    .map_err(engine_failure)?;
    let occurrences = model
        .get("occurrences")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut days = Vec::new();
    for day in 0..7 {
        let mut items: Vec<(i64, i64, String)> = occurrences
            .iter()
            .filter(|item| whole(item.get("day")) == Some(day))
            .filter_map(|item| {
                let start = whole(item.get("start"))?;
                let end = whole(item.get("end"))?;
                Some((start, end, category_of(item)))
            })
            .collect();
        items.sort_by_key(|(start, _, _)| *start);
        let mut segments: Vec<Value> = Vec::new();
        for (start, end, category) in items {
            if let Some(last) = segments.last_mut()
                && last["end_min"] == json!(start)
                && last["category"] == json!(category)
            {
                last["end_min"] = json!(end);
                continue;
            }
            segments.push(json!({
                "start_min": start,
                "end_min": end,
                "category": category,
                "color": colour(&category),
            }));
        }
        days.push(json!({
            "day": day,
            "segments": segments,
        }));
    }
    Ok(json!({
        "week_start": week_start,
        "days": days,
    })
    .to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_test, save_week};
    use serde_json::json;

    #[test]
    fn week_shape_is_colour_segments_with_no_words() {
        let (week, _) = open_test("shape");
        save_week(
            &week,
            "2026-10-12",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":60,"category":"class"}
            ]),
        );
        let shape: Value =
            serde_json::from_str(&week.week_shape("2026-10-12".into()).unwrap()).unwrap();
        assert_eq!(shape["week_start"], "2026-10-12");
        assert_eq!(shape["days"].as_array().unwrap().len(), 7);
        let monday = &shape["days"][0]["segments"];
        assert_eq!(monday[0]["start_min"], 480);
        assert_eq!(monday[0]["end_min"], 540);
        assert_eq!(monday[0]["category"], "class");
        assert_eq!(monday[0]["color"], "#398ad6");
        assert!(monday[0].get("title").is_none());
    }
}
