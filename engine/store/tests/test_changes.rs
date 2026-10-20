//! `post_changes` (`backend/app.py:1292-1358`) through `changes::apply`.
mod common;

use common::scratch;
use flexweek_store::{
    ApplyClock, ApplyFailure, ApplyInput, AssignmentInput, AssignmentSave, StandingInput,
    WeekInput, apply, initialize, open_connection, save_assignment,
};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};

const MAX_ASSIGNMENTS: i64 = 1000;
const WEEK: &str = "2026-10-19";
const ESSAY: &str = r#"{"category":null,"completed":false,"completed_at":null,"course":null,"due":"2026-10-23T21:00","energy":"medium","estimate_min":90,"focus_minutes":0,"focus_sessions":0,"id":"essay","priority":3,"spotify_url":null,"title":"Essay"}"#;
const MATH: &str = r#"{"course":null,"days":[0],"duration_min":30,"earliest":null,"energy":"medium","id":"b1","kind":"flexible","latest":null,"priority":3,"start":null,"title":"Math"}"#;
const SCHOOL: &str = r#"{"category":"class","days":[0,1,2,3,4],"duration_min":405,"id":"school","kind":"locked","start":"08:30","title":"School"}"#;

fn clock() -> ApplyClock {
    ApplyClock {
        now: "2026-10-21T12:00".into(),
        restore_token: "abcdabcd".into(),
    }
}

/// A previous request has finished. Store writes leave the transaction open for Python's `with`.
fn settle(conn: &Connection) {
    if !conn.is_autocommit() {
        conn.execute("COMMIT", []).unwrap();
    }
}

fn account(name: &str) -> (Connection, i64) {
    let path = scratch(name);
    initialize(&path, WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    conn.execute(
        "INSERT INTO users(username, password_hash) VALUES ('ada', 'x')",
        [],
    )
    .unwrap();
    let user_id: i64 = conn
        .query_row("SELECT id FROM users WHERE username = 'ada'", [], |row| {
            row.get(0)
        })
        .unwrap();
    (conn, user_id)
}

fn parsed(text: &str) -> Value {
    serde_json::from_str(text).unwrap_or(Value::Null)
}

fn essay(title: &str) -> Value {
    let mut body = parsed(ESSAY);
    if let Some(object) = body.as_object_mut() {
        object.insert("title".into(), json!(title));
    }
    body
}

fn math_block() -> Value {
    json!({
        "id": "b1",
        "title": "Math",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0]
    })
}

fn school_block() -> Value {
    parsed(SCHOOL)
}

fn empty_input() -> ApplyInput {
    ApplyInput {
        weeks: Vec::new(),
        assignments: Vec::new(),
        operation_id: None,
        snapshot_label: None,
        standing: None,
    }
}

fn shown(result: Result<Value, ApplyFailure>) -> Result<Value, String> {
    match result {
        Ok(value) => Ok(value),
        Err(ApplyFailure::Refused {
            message,
            current_revision,
        }) => Err(match current_revision {
            Some(revision) => format!("{message} @ {revision}"),
            None => message,
        }),
        Err(ApplyFailure::Store(error)) => Err(format!("store: {error}")),
    }
}

fn apply_shown(conn: &Connection, user_id: i64, input: &ApplyInput) -> Result<Value, String> {
    shown(apply(conn, user_id, input, &clock()))
}

fn count_rows(conn: &Connection, table: &str, user_id: i64) -> i64 {
    conn.query_row(
        &format!("SELECT COUNT(*) FROM {table} WHERE user_id = ?1"),
        params![user_id],
        |row| row.get(0),
    )
    .unwrap_or(-1)
}

fn week_blocks(conn: &Connection, user_id: i64, week_start: &str) -> String {
    match conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| row.get(0),
        )
        .optional()
    {
        Ok(Some(text)) => text,
        Ok(None) => "missing".into(),
        Err(error) => error.to_string(),
    }
}

fn week_revision(conn: &Connection, user_id: i64, week_start: &str) -> i64 {
    match conn
        .query_row(
            "SELECT revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| row.get(0),
        )
        .optional()
    {
        Ok(Some(revision)) => revision,
        Ok(None) => -1,
        Err(_) => -2,
    }
}

fn assignment_title(conn: &Connection, user_id: i64, id: &str) -> String {
    let body: String = match conn
        .query_row(
            "SELECT body FROM assignments WHERE user_id = ?1 AND id = ?2",
            params![user_id, id],
            |row| row.get(0),
        )
        .optional()
    {
        Ok(Some(body)) => body,
        Ok(None) => return "missing".into(),
        Err(error) => return error.to_string(),
    };
    parsed(&body)
        .get("title")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn restore_field(conn: &Connection, user_id: i64, field: &str) -> String {
    let (id, label, body): (String, String, String) = match conn.query_row(
        "SELECT id, label, body FROM restore_points WHERE user_id = ?1",
        params![user_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    ) {
        Ok(row) => row,
        Err(error) => return error.to_string(),
    };
    if field == "id" {
        return id;
    }
    if field == "label" {
        return label;
    }
    parsed(&body)
        .get("assignments")
        .and_then(|items| items.get(0))
        .and_then(|item| item.get("body"))
        .and_then(|body| body.get("title"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn standing_body(conn: &Connection, user_id: i64) -> String {
    match conn
        .query_row(
            "SELECT body FROM standing_blocks WHERE user_id = ?1 AND id = 'school'",
            params![user_id],
            |row| row.get(0),
        )
        .optional()
    {
        Ok(Some(body)) => body,
        Ok(None) => "missing".into(),
        Err(error) => error.to_string(),
    }
}

/// app.py:1354 builds `{weeks, assignments}` and writes nothing when both lists are empty.
#[test]
fn an_empty_batch_changes_nothing() {
    let (conn, user_id) = account("empty-batch");
    assert_eq!(
        apply_shown(&conn, user_id, &empty_input()),
        Ok(json!({"assignments": [], "weeks": []})),
        "app.py:1354 an empty batch still answers with both lists"
    );
    assert_eq!(count_rows(&conn, "assignments", user_id), 0);
    assert_eq!(count_rows(&conn, "weeks", user_id), 0);
    assert_eq!(count_rows(&conn, "operations", user_id), 0);
}

/// app.py:105-107 and :201 store `model_dump` with sorted compact JSON. Revision starts at 1.
#[test]
fn an_assignment_is_stored_as_sorted_compact_json() {
    let (conn, user_id) = account("assignment-json");
    let mut input = empty_input();
    input.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("Essay")),
        revision: 0,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Ok(json!({
            "assignments": [{
                "assignment": parsed(ESSAY),
                "id": "essay",
                "revision": 1
            }],
            "weeks": []
        })),
        "app.py:1312 the saved assignment is the dumped body plus its new revision"
    );
    assert_eq!(
        assignment_title(&conn, user_id, "essay"),
        "Essay",
        "app.py:201 the row was stored"
    );
    let body: String = conn
        .query_row(
            "SELECT body FROM assignments WHERE user_id = ?1 AND id = 'essay'",
            params![user_id],
            |row| row.get(0),
        )
        .unwrap_or_default();
    assert_eq!(
        body, ESSAY,
        "app.py:105 encode_assignment sorts keys and drops spaces"
    );
}

/// app.py:1298 returns the remembered response before any write.
#[test]
fn the_same_operation_returns_the_first_answer_and_writes_nothing() {
    let (conn, user_id) = account("retry-op");
    let mut input = empty_input();
    input.operation_id = Some("op-retry1".into());
    input.weeks.push(WeekInput {
        week_start: WEEK.into(),
        blocks: vec![math_block()],
        revision: 0,
    });
    let first = apply_shown(&conn, user_id, &input);
    assert_eq!(
        first,
        Ok(json!({
            "assignments": [],
            "weeks": [{
                "blocks": [parsed(MATH)],
                "revision": 1,
                "week_start": WEEK
            }]
        })),
        "app.py:1338 the first save answers with the stored week"
    );
    conn.execute(
        "UPDATE weeks SET blocks = '[]', revision = 5 WHERE user_id = ?1 AND week_start = ?2",
        params![user_id, WEEK],
    )
    .unwrap();
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        first,
        "app.py:1299 the same operation id returns the first answer"
    );
    assert_eq!(
        week_revision(&conn, user_id, WEEK),
        5,
        "app.py:1299 a repeat writes nothing, so the later edit stays"
    );
    assert_eq!(count_rows(&conn, "operations", user_id), 1);
}

/// app.py:272 the same id with a different payload is refused.
#[test]
fn the_same_operation_with_different_data_is_refused() {
    let (conn, user_id) = account("op-conflict");
    let mut first = empty_input();
    first.operation_id = Some("op-same-1".into());
    first.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("Essay")),
        revision: 0,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &first),
        Ok(json!({
            "assignments": [{
                "assignment": parsed(ESSAY),
                "id": "essay",
                "revision": 1
            }],
            "weeks": []
        })),
        "app.py:1312 the first save of this operation id stores the essay"
    );
    let mut second = empty_input();
    second.operation_id = Some("op-same-1".into());
    second.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("Changed")),
        revision: 1,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &second),
        Err("This operation was already used with different data.".into()),
        "app.py:272 a reused operation id with different data is refused"
    );
    assert_eq!(assignment_title(&conn, user_id, "essay"), "Essay");
}

/// app.py:206 a stale assignment revision conflicts before the write.
#[test]
fn a_stale_assignment_revision_writes_nothing() {
    let (conn, user_id) = account("stale-assignment");
    assert_eq!(
        save_assignment(&conn, user_id, "essay", ESSAY, 0, MAX_ASSIGNMENTS).unwrap(),
        AssignmentSave::Ready(1)
    );
    settle(&conn);
    let mut input = empty_input();
    input.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("Changed")),
        revision: 0,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Err("This assignment changed in another window. Reload before saving. @ 1".into()),
        "app.py:206 a stale revision names the conflict and the current revision"
    );
    assert_eq!(assignment_title(&conn, user_id, "essay"), "Essay");
}

/// app.py:1296 one transaction: a later week conflict undoes the assignment saved before it.
#[test]
fn a_later_failure_rolls_the_batch_back() {
    let (conn, user_id) = account("rollback-batch");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[]', 3)",
        params![user_id, WEEK],
    )
    .unwrap();
    let mut input = empty_input();
    input.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("Essay")),
        revision: 0,
    });
    input.weeks.push(WeekInput {
        week_start: WEEK.into(),
        blocks: vec![math_block()],
        revision: 1,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Err("This week changed in another window. Reload before saving. @ 3".into()),
        "app.py:237 a stale week revision conflicts"
    );
    assert_eq!(
        count_rows(&conn, "assignments", user_id),
        0,
        "app.py:1296 the assignment insert rolls back with the week"
    );
    assert_eq!(week_revision(&conn, user_id, WEEK), 3);
    assert_eq!(week_blocks(&conn, user_id, WEEK), "[]");
}

/// app.py:1319 a delete reports the sessions it took off each week.
#[test]
fn deleting_homework_reports_the_sessions_it_removed() {
    let (conn, user_id) = account("delete-homework");
    assert_eq!(
        save_assignment(&conn, user_id, "essay", ESSAY, 0, MAX_ASSIGNMENTS).unwrap(),
        AssignmentSave::Ready(1)
    );
    let session = r#"[{"assignment_id":"essay","days":[0],"duration_min":90,"id":"s1","kind":"locked","start":"16:00","title":"Essay"}]"#;
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)",
        params![user_id, WEEK, session],
    )
    .unwrap();
    settle(&conn);
    let mut input = empty_input();
    input.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: None,
        revision: 1,
    });
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Ok(json!({
            "assignments": [{
                "assignment": null,
                "changed_weeks": [{"revision": 2, "week_start": WEEK}],
                "id": "essay",
                "removed_sessions": {
                    WEEK: [{
                        "assignment_id": "essay",
                        "days": [0],
                        "duration_min": 90,
                        "id": "s1",
                        "kind": "locked",
                        "start": "16:00",
                        "title": "Essay"
                    }]
                },
                "revision": 1
            }],
            "weeks": []
        })),
        "app.py:1321 the delete keeps the caller's revision and lists the sessions it removed"
    );
    assert_eq!(assignment_title(&conn, user_id, "essay"), "missing");
    assert_eq!(week_blocks(&conn, user_id, WEEK), "[]");
    assert_eq!(week_revision(&conn, user_id, WEEK), 2);
}

/// app.py:1301 the restore point is the account from before the edits in this batch.
#[test]
fn a_restore_point_is_taken_before_the_edit() {
    let (conn, user_id) = account("restore-first");
    assert_eq!(
        save_assignment(&conn, user_id, "essay", ESSAY, 0, MAX_ASSIGNMENTS).unwrap(),
        AssignmentSave::Ready(1)
    );
    settle(&conn);
    let mut input = empty_input();
    input.snapshot_label = Some("Before edit".into());
    input.assignments.push(AssignmentInput {
        id: "essay".into(),
        assignment: Some(essay("New")),
        revision: 1,
    });
    let mut edited = parsed(ESSAY);
    if let Some(object) = edited.as_object_mut() {
        object.insert("title".into(), json!("New"));
    }
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Ok(json!({
            "assignments": [{
                "assignment": edited,
                "id": "essay",
                "revision": 2
            }],
            "weeks": []
        })),
        "app.py:1302 the edit after the snapshot still saves"
    );
    assert_eq!(
        restore_field(&conn, user_id, "id"),
        "rp-abcdabcd",
        "app.py:296 the point id is rp- plus the token"
    );
    assert_eq!(restore_field(&conn, user_id, "label"), "Before edit");
    assert_eq!(
        restore_field(&conn, user_id, "title"),
        "Essay",
        "app.py:1301 the snapshot keeps the title from before this batch"
    );
    assert_eq!(assignment_title(&conn, user_id, "essay"), "New");
}

/// app.py:1342 standing is saved, then each week in the answer includes it.
#[test]
fn a_standing_change_is_merged_into_the_week_response() {
    let (conn, user_id) = account("standing-merge");
    let mut input = empty_input();
    input.weeks.push(WeekInput {
        week_start: WEEK.into(),
        blocks: vec![math_block()],
        revision: 0,
    });
    input.standing = Some(StandingInput {
        week_start: WEEK.into(),
        blocks: vec![school_block()],
    });
    assert_eq!(
        apply_shown(&conn, user_id, &input),
        Ok(json!({
            "assignments": [],
            "standing_changed_weeks": [],
            "weeks": [{
                "blocks": [parsed(MATH), parsed(SCHOOL)],
                "revision": 1,
                "week_start": WEEK
            }]
        })),
        "app.py:1351 the answer's week shows School even though the saved row does not store it"
    );
    assert_eq!(
        week_blocks(&conn, user_id, WEEK),
        format!("[{MATH}]"),
        "app.py:229 the saved week is sorted compact JSON without the standing block"
    );
    assert_eq!(standing_body(&conn, user_id), SCHOOL);
}

/// app.py:1309 and :123. The list is asserted non-empty before the loop.
#[test]
fn an_assignment_id_must_match_and_must_belong_to_the_account() {
    let cases = [
        (
            "app.py:1309 assignment id in the path and body must match",
            {
                let mut input = empty_input();
                let mut body = essay("Essay");
                if let Some(object) = body.as_object_mut() {
                    object.insert("id".into(), json!("other"));
                }
                input.assignments.push(AssignmentInput {
                    id: "essay".into(),
                    assignment: Some(body),
                    revision: 0,
                });
                input
            },
            "assignment id in the path and body must match",
        ),
        (
            "app.py:123 assignment_id must name an assignment of this account",
            {
                let mut input = empty_input();
                input.weeks.push(WeekInput {
                    week_start: WEEK.into(),
                    blocks: vec![json!({
                        "id": "s1",
                        "title": "Essay",
                        "kind": "locked",
                        "duration_min": 90,
                        "days": [0],
                        "start": "16:00",
                        "assignment_id": "missing"
                    })],
                    revision: 0,
                });
                input
            },
            "assignment_id must name an assignment of this account",
        ),
    ];
    assert!(!cases.is_empty(), "the refusal list has both rules");
    for (name, input, message) in cases {
        let (conn, user_id) = account(name);
        assert_eq!(
            apply_shown(&conn, user_id, &input),
            Err(message.to_string()),
            "{name}"
        );
        assert_eq!(count_rows(&conn, "assignments", user_id), 0, "{name}");
        assert_eq!(count_rows(&conn, "weeks", user_id), 0, "{name}");
    }
}
