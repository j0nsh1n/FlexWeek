//! Each refusal is a sentence from `backend/models.py` or the pydantic 2.13
//! field-constraint template those fields use. The list is asserted non-empty first.

use flexweek_engine::validate::{
    assignment_content, encode_json, routine, time_block, week_request,
};
use serde_json::{Value, json};

struct Case {
    name: &'static str,
    value: Value,
    message: &'static str,
}

fn check(name: &str, result: Result<impl std::fmt::Debug, String>, message: &str) {
    let error = match result {
        Ok(_) => String::new(),
        Err(error) => error,
    };
    assert_eq!(error, message, "{name}");
}

fn run<T: std::fmt::Debug>(cases: &[Case], call: fn(&Value) -> Result<T, String>) {
    assert!(!cases.is_empty(), "the rule list must not be empty");
    for case in cases {
        check(case.name, call(&case.value), case.message);
    }
}

fn block() -> Value {
    json!({
        "id": "b1",
        "title": "Math",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0]
    })
}

fn with(mut value: Value, key: &str, patch: Value) -> Value {
    value
        .as_object_mut()
        .expect("object")
        .insert(key.to_string(), patch);
    value
}

fn without(mut value: Value, key: &str) -> Value {
    value.as_object_mut().expect("object").shift_remove(key);
    value
}

fn repeat(count: usize) -> String {
    "a".repeat(count)
}

#[test]
fn time_block_rules_match_models_py() {
    let base = block();
    let cases = [
        Case {
            name: "models.py:125 a block is an object",
            value: json!([]),
            message: "Input should be a valid dictionary or instance of TimeBlock",
        },
        Case {
            name: "models.py:126 id is required",
            value: without(base.clone(), "id"),
            message: "Field required",
        },
        Case {
            name: "models.py:126 id has at least 1 character",
            value: with(base.clone(), "id", json!("")),
            message: "String should have at least 1 character",
        },
        Case {
            name: "models.py:126 id has at most 80 characters",
            value: with(base.clone(), "id", json!(repeat(81))),
            message: "String should have at most 80 characters",
        },
        Case {
            name: "models.py:126 id is a string",
            value: with(base.clone(), "id", json!(1)),
            message: "Input should be a valid string",
        },
        Case {
            name: "models.py:127 title has at most 80 characters",
            value: with(base.clone(), "title", json!(repeat(81))),
            message: "String should have at most 80 characters",
        },
        Case {
            name: "models.py:128 kind is locked or flexible",
            value: with(base.clone(), "kind", json!("school")),
            message: "Input should be 'locked' or 'flexible'",
        },
        Case {
            name: "models.py:131 duration is greater than 0",
            value: with(base.clone(), "duration_min", json!(0)),
            message: "Input should be greater than 0",
        },
        Case {
            name: "models.py:131 duration is at most 7140",
            value: with(base.clone(), "duration_min", json!(7141)),
            message: "Input should be less than or equal to 7140",
        },
        Case {
            name: "models.py:131 duration is a whole number",
            value: with(base.clone(), "duration_min", json!(1.5)),
            message: "Input should be a valid integer, got a number with a fractional part",
        },
        Case {
            name: "models.py:132 days is a list",
            value: with(base.clone(), "days", json!(0)),
            message: "Input should be a valid list",
        },
        Case {
            name: "models.py:132 days has at least one day",
            value: with(base.clone(), "days", json!([])),
            message: "List should have at least 1 item after validation, not 0",
        },
        Case {
            name: "models.py:132 days has at most 7 days",
            value: with(base.clone(), "days", json!([0, 1, 2, 3, 4, 5, 6, 0])),
            message: "List should have at most 7 items after validation, not 8",
        },
        Case {
            name: "models.py:179 days are 0..6",
            value: with(base.clone(), "days", json!([7])),
            message: "days must be in 0..6 (Mon..Sun)",
        },
        Case {
            name: "models.py:132 priority is 1, 2, 3 or 4",
            value: with(base.clone(), "priority", json!(5)),
            message: "Input should be 1, 2, 3 or 4",
        },
        Case {
            name: "models.py:133 energy is high, medium or low",
            value: with(base.clone(), "energy", json!("huge")),
            message: "Input should be 'high', 'medium' or 'low'",
        },
        Case {
            name: "models.py:134 earliest has at most 40 characters",
            value: with(base.clone(), "earliest", json!(repeat(41))),
            message: "String should have at most 40 characters",
        },
        Case {
            name: "models.py:136 start has at most 5 characters",
            value: with(base.clone(), "start", json!("09:000")),
            message: "String should have at most 5 characters",
        },
        Case {
            name: "models.py:137 course has at most 40 characters",
            value: with(base.clone(), "course", json!(repeat(41))),
            message: "String should have at most 40 characters",
        },
        Case {
            name: "models.py:138 category has at most 32 characters",
            value: with(base.clone(), "category", json!(repeat(33))),
            message: "String should have at most 32 characters",
        },
        Case {
            name: "models.py:143 completed is a boolean",
            value: with(base.clone(), "completed", json!("yes")),
            message: "Input should be a valid boolean",
        },
        Case {
            name: "models.py:147 completed_day is at least 0",
            value: with(base.clone(), "completed_day", json!(-1)),
            message: "Input should be greater than or equal to 0",
        },
        Case {
            name: "models.py:149 completed_day is at most 6",
            value: with(base.clone(), "completed_day", json!(7)),
            message: "Input should be less than or equal to 6",
        },
        Case {
            name: "models.py:186 missed_days are unique and inside 0..6",
            value: with(base.clone(), "missed_days", json!([0, 0])),
            message: "missed_days must be unique values in 0..6",
        },
        Case {
            name: "models.py:158 spotify_url has at most 500 characters",
            value: with(base.clone(), "spotify_url", json!(repeat(501))),
            message: "String should have at most 500 characters",
        },
        Case {
            name: "models.py:109 spotify_url is an open.spotify.com share link",
            value: with(
                base.clone(),
                "spotify_url",
                json!("https://evil.com/open.spotify.com/track/abc"),
            ),
            message: "spotify_url must be an open.spotify.com share link",
        },
        Case {
            name: "models.py:159 focus_sessions is at most 9999",
            value: with(base.clone(), "focus_sessions", json!(10000)),
            message: "Input should be less than or equal to 9999",
        },
        Case {
            name: "models.py:160 focus_minutes is at most 71400",
            value: with(base.clone(), "focus_minutes", json!(71401)),
            message: "Input should be less than or equal to 71400",
        },
        Case {
            name: "models.py:161 pomodoro_parent_id has at least 1 character",
            value: with(base.clone(), "pomodoro_parent_id", json!("")),
            message: "String should have at least 1 character",
        },
        Case {
            name: "models.py:164 pomodoro_role is work or break",
            value: with(base.clone(), "pomodoro_role", json!("nap")),
            message: "Input should be 'work' or 'break'",
        },
        Case {
            name: "models.py:165 pomodoro_index is at least 1",
            value: with(base.clone(), "pomodoro_index", json!(0)),
            message: "Input should be greater than or equal to 1",
        },
        Case {
            name: "models.py:192 pinned needs a flexible block with a start on one day",
            value: with(
                with(base.clone(), "pinned", json!(true)),
                "kind",
                json!("locked"),
            ),
            message: "pinned requires a flexible block with a start on one day",
        },
        Case {
            name: "models.py:195 only a locked block can have missed days",
            value: with(base.clone(), "missed_days", json!([0])),
            message: "only locked blocks can have missed days",
        },
        Case {
            name: "models.py:197 missed days are occurrences of the block",
            value: with(
                with(
                    with(base.clone(), "kind", json!("locked")),
                    "start",
                    json!("09:00"),
                ),
                "missed_days",
                json!([1]),
            ),
            message: "missed days must be occurrences of the block",
        },
        Case {
            name: "models.py:204 completed_day needs a completed flexible block",
            value: with(base.clone(), "completed_day", json!(0)),
            message: "completed_day requires a completed flexible block with a start on a candidate day",
        },
        Case {
            name: "models.py:209 a session cannot carry latest",
            value: with(
                with(base.clone(), "assignment_id", json!("essay")),
                "latest",
                json!("Friday 21:00"),
            ),
            message: "a session cannot carry latest",
        },
        Case {
            name: "models.py:211 session focus must be 0",
            value: with(
                with(base.clone(), "assignment_id", json!("essay")),
                "focus_minutes",
                json!(15),
            ),
            message: "session focus must be 0",
        },
        Case {
            name: "models.py:216 assignment_id is only a work session or a pomodoro work chunk",
            value: with(
                with(
                    with(base.clone(), "kind", json!("locked")),
                    "start",
                    json!("09:00"),
                ),
                "assignment_id",
                json!("essay"),
            ),
            message: "assignment_id is only valid on a work session or a pomodoro work chunk",
        },
        Case {
            name: "models.py:125 a flexible block with the defaults is accepted",
            value: with(base.clone(), "notes", json!("kept")),
            message: "",
        },
    ];
    run(&cases, time_block);
}

#[test]
fn week_request_rules_match_models_py() {
    let one = block();
    let mut second = block();
    second
        .as_object_mut()
        .expect("object")
        .insert("id".into(), json!("b2"));
    let cases = vec![
        Case {
            name: "models.py:480 a week is an object",
            value: json!([]),
            message: "Input should be a valid dictionary or instance of WeekRequest",
        },
        Case {
            name: "models.py:481 blocks is required",
            value: json!({}),
            message: "Field required",
        },
        Case {
            name: "models.py:481 at most 100 blocks",
            value: json!({
                "blocks": (0..101).map(|index| with(block(), "id", json!(format!("b{index}")))).collect::<Vec<_>>()
            }),
            message: "List should have at most 100 items after validation, not 101",
        },
        Case {
            name: "models.py:488 block ids must be unique",
            value: json!({"blocks": [one.clone(), one.clone()]}),
            message: "block ids must be unique",
        },
        Case {
            name: "models.py:491 a blank title or a repeated day is refused",
            value: json!({"blocks": [with(one.clone(), "title", json!("  "))]}),
            message: "title and unique days required",
        },
        Case {
            name: "models.py:491 days in a block are unique",
            value: json!({"blocks": [with(one.clone(), "days", json!([0, 0]))]}),
            message: "title and unique days required",
        },
        Case {
            name: "models.py:493 a locked block needs a start",
            value: json!({"blocks": [with(one.clone(), "kind", json!("locked"))]}),
            message: "locked blocks need a start",
        },
        Case {
            name: "models.py:496 start is HH:MM",
            value: json!({"blocks": [with(one.clone(), "start", json!("25:00"))]}),
            message: "invalid start time",
        },
        Case {
            name: "models.py:499 a block fits in the day",
            value: json!({"blocks": [with(with(one.clone(), "start", json!("23:30")), "duration_min", json!(60))]}),
            message: "block must fit between 00:00 and 24:00",
        },
        Case {
            name: "models.py:507 earliest and latest use a day name and a clock",
            value: json!({"blocks": [with(one.clone(), "earliest", json!("Mon 09:00"))]}),
            message: "invalid deadline or earliest time",
        },
        Case {
            name: "models.py:508 a pomodoro parent is not stored with its chunks",
            value: json!({"blocks": [
                with(one.clone(), "id", json!("parent")),
                with(second, "pomodoro_parent_id", json!("parent"))
            ]}),
            message: "a pomodoro parent cannot be stored with the chunks split from it",
        },
        Case {
            name: "models.py:480 a week of one flexible block is accepted",
            value: json!({"blocks": [with(one, "earliest", json!("Monday 09:00"))]}),
            message: "",
        },
    ];
    run(&cases, week_request);
}

fn homework() -> Value {
    json!({
        "id": "essay",
        "title": "Essay",
        "due": "2026-10-23T21:00",
        "estimate_min": 90
    })
}

#[test]
fn assignment_rules_match_models_py() {
    let base = homework();
    let cases = vec![
        Case {
            name: "models.py:249 homework is an object",
            value: json!(null),
            message: "Input should be a valid dictionary or instance of AssignmentContent",
        },
        Case {
            name: "models.py:250 an unknown field is refused",
            value: with(base.clone(), "colour", json!("blue")),
            message: "Extra inputs are not permitted",
        },
        Case {
            name: "models.py:287 a blank title is refused",
            value: with(base.clone(), "title", json!("  ")),
            message: "title required",
        },
        Case {
            name: "models.py:259 estimate_min is at most 1440",
            value: with(base.clone(), "estimate_min", json!(1500)),
            message: "Input should be less than or equal to 1440",
        },
        Case {
            name: "models.py:294 estimate_min is a positive multiple of 15",
            value: with(base.clone(), "estimate_min", json!(100)),
            message: "estimate_min must be a positive multiple of 15",
        },
        Case {
            name: "models.py:294 a zero estimate is refused",
            value: with(base.clone(), "estimate_min", json!(0)),
            message: "estimate_min must be a positive multiple of 15",
        },
        Case {
            name: "models.py:67 due is a date or a stamp with no seconds",
            value: with(base.clone(), "due", json!("2026-10-23T21:00:00")),
            message: "must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with no seconds or timezone",
        },
        Case {
            name: "models.py:49 due is between 2000 and 2099",
            value: with(base.clone(), "due", json!("1999-12-31")),
            message: "date must be between 2000-01-01 and 2099-12-31",
        },
        Case {
            name: "models.py:260 spread is one or spread",
            value: with(base.clone(), "spread", json!("twice")),
            message: "Input should be 'one' or 'spread'",
        },
        Case {
            name: "models.py:300 completed_at is required when completed",
            value: with(base.clone(), "completed", json!(true)),
            message: "completed_at is required when completed",
        },
        Case {
            name: "models.py:302 completed_at must be null when not completed",
            value: with(base.clone(), "completed_at", json!("2026-10-23T21:00")),
            message: "completed_at must be null when not completed",
        },
        Case {
            name: "models.py:56 completed_at has no seconds or timezone",
            value: with(
                with(base.clone(), "completed", json!(true)),
                "completed_at",
                json!("2026-10-23T21:00:00"),
            ),
            message: "must be YYYY-MM-DDTHH:MM with no seconds or timezone",
        },
        Case {
            name: "models.py:265 notes have at most 4000 characters",
            value: with(base.clone(), "notes", json!(repeat(4001))),
            message: "String should have at most 4000 characters",
        },
        Case {
            name: "models.py:266 at most 20 links",
            value: with(
                base.clone(),
                "links",
                json!((0..21).map(|index| json!({"label": format!("L{index}"), "url": "https://example.com"})).collect::<Vec<_>>()),
            ),
            message: "List should have at most 20 items after validation, not 21",
        },
        Case {
            name: "models.py:230 a blank link label is refused",
            value: with(base.clone(), "links", json!([{"label": "  ", "url": "https://example.com"}])),
            message: "link label required",
        },
        Case {
            name: "models.py:119 a link url is http or https",
            value: with(base.clone(), "links", json!([{"label": "Notes", "url": "ftp://example.com"}])),
            message: "link url must be an http or https URL",
        },
        Case {
            name: "models.py:221 an unknown link field is refused",
            value: with(base.clone(), "links", json!([{"label": "Notes", "url": "https://example.com", "extra": 1}])),
            message: "Extra inputs are not permitted",
        },
        Case {
            name: "models.py:245 checklist text is required",
            value: with(base.clone(), "checklist", json!([{"id": "c1", "text": "  "}])),
            message: "checklist text required",
        },
        Case {
            name: "models.py:305 checklist ids are unique",
            value: with(
                base.clone(),
                "checklist",
                json!([
                    {"id": "c1", "text": "Read"},
                    {"id": "c1", "text": "Write"}
                ]),
            ),
            message: "checklist ids must be unique",
        },
        Case {
            name: "models.py:249 homework of 90 minutes is accepted",
            value: base,
            message: "",
        },
    ];
    run(&cases, assignment_content);
}

fn routine_body() -> Value {
    json!({
        "id": "morning",
        "name": "Morning",
        "blocks": [{
            "template_id": "read",
            "title": "Read",
            "days": [0],
            "start": "08:00",
            "duration_min": 30
        }],
        "revision": 0
    })
}

#[test]
fn routine_rules_match_models_py() {
    let cases = vec![
        Case {
            name: "models.py:358 a routine is an object",
            value: json!("morning"),
            message: "Input should be a valid dictionary or instance of Routine",
        },
        Case {
            name: "models.py:361 an unknown field is refused",
            value: with(routine_body(), "colour", json!("blue")),
            message: "Extra inputs are not permitted",
        },
        Case {
            name: "models.py:369 a blank name is refused",
            value: with(routine_body(), "name", json!(" ")),
            message: "name required",
        },
        Case {
            name: "models.py:332 a blank block title is refused",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [{
                    "template_id": "read",
                    "title": " ",
                    "days": [0],
                    "start": "08:00",
                    "duration_min": 30
                }]
            }),
            message: "title required",
        },
        Case {
            name: "models.py:339 routine days are unique and inside 0..6",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [{
                    "template_id": "read",
                    "title": "Read",
                    "days": [0, 0],
                    "start": "08:00",
                    "duration_min": 30
                }]
            }),
            message: "days must be unique values in 0..6",
        },
        Case {
            name: "models.py:346 start is HH:MM",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [{
                    "template_id": "read",
                    "title": "Read",
                    "days": [0],
                    "start": "8:00",
                    "duration_min": 30
                }]
            }),
            message: "invalid start time",
        },
        Case {
            name: "models.py:354 a routine block fits in the day",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [{
                    "template_id": "read",
                    "title": "Read",
                    "days": [0],
                    "start": "23:30",
                    "duration_min": 60
                }]
            }),
            message: "block must fit between 00:00 and 24:00",
        },
        Case {
            name: "models.py:376 template ids are unique",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [
                    {"template_id": "read", "title": "Read", "days": [0], "start": "08:00", "duration_min": 30},
                    {"template_id": "read", "title": "Read again", "days": [1], "start": "08:00", "duration_min": 30}
                ]
            }),
            message: "template ids must be unique",
        },
        Case {
            name: "models.py:390 routine blocks on one day do not overlap",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 0,
                "blocks": [
                    {"template_id": "read", "title": "Read", "days": [0], "start": "08:00", "duration_min": 60},
                    {"template_id": "write", "title": "Write", "days": [0], "start": "08:30", "duration_min": 30}
                ]
            }),
            message: "routine blocks overlap",
        },
        Case {
            name: "models.py:363 revision is at least 0",
            value: with(routine_body(), "revision", json!(-1)),
            message: "Input should be greater than or equal to 0",
        },
        Case {
            name: "models.py:363 revision fits a JSON number",
            value: with(routine_body(), "revision", json!(9007199254740992_i64)),
            message: "Input should be less than or equal to 9007199254740991",
        },
        Case {
            name: "models.py:358 a routine whose blocks only touch is accepted",
            value: json!({
                "id": "morning",
                "name": "Morning",
                "revision": 1,
                "blocks": [
                    {"template_id": "read", "title": "Read", "days": [0], "start": "08:00", "duration_min": 60},
                    {"template_id": "write", "title": "Write", "days": [0], "start": "09:00", "duration_min": 30}
                ]
            }),
            message: "",
        },
    ];
    run(&cases, routine);
}

#[test]
fn a_flexible_block_dumps_like_model_dump() {
    let dumped = match time_block(&block()) {
        Ok(block) => encode_json(&block.to_value()),
        Err(error) => error,
    };
    assert_eq!(
        dumped,
        r#"{"course":null,"days":[0],"duration_min":30,"earliest":null,"energy":"medium","id":"b1","kind":"flexible","latest":null,"priority":3,"start":null,"title":"Math"}"#,
        "models.py:125 model_dump keeps null earliest and omits a false completed"
    );
}

#[test]
fn homework_dumps_like_model_dump() {
    let dumped = match assignment_content(&homework()) {
        Ok(item) => encode_json(&item.to_value()),
        Err(error) => error,
    };
    assert_eq!(
        dumped,
        r#"{"category":null,"completed":false,"completed_at":null,"course":null,"due":"2026-10-23T21:00","energy":"medium","estimate_min":90,"focus_minutes":0,"focus_sessions":0,"id":"essay","priority":3,"spotify_url":null,"title":"Essay"}"#,
        "models.py:249 model_dump omits an empty notes string and the default spread"
    );
}
