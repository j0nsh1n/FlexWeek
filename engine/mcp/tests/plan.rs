//! `plan_homework` runs FlexWeek's own planner as "Plan my homework" does (the phone's Rust port of
//! it, `ffi/src/plan_week.rs`): homework that has no time gets one around the fixed blocks, never
//! before now (Wednesday 2026-10-21 12:00), and never after it is due. What it places is written in
//! one change with one restore point; what it cannot place comes back with the planner's reason.
//! `day` keeps the plan to one day.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_ok_text};
use flexweek_engine::repeats::edit_intent;
use flexweek_store::{
    apply_repeat_intents, initialize, insert_assignment, insert_preferences, insert_user,
    open_connection, open_session, save_week,
};
use serde_json::{Value, json};

const TOKEN: &str = "abcdefghijklmnopqrstuvwxyz012345";
const WEEK: &str = "2026-10-19";
const WEEK_OVER: &str = "This week is over, so nothing was planned. Plan this week or a later one.";

struct World {
    data_arg: String,
    database_arg: String,
    user: i64,
}

fn signed_in(name: &str) -> World {
    let dir = scratch(name);
    let data_arg = dir.to_string_lossy().into_owned();
    let database_arg = dir.join("flexweek.db").to_string_lossy().into_owned();
    initialize(Path::new(&database_arg), WEEK).expect("schema");
    let conn = open_connection(Path::new(&database_arg)).expect("open");
    let user = insert_user(&conn, "ada", "hash").expect("user");
    insert_preferences(&conn, user, 1).expect("preferences");
    open_session(&conn, TOKEN, user, NOW_UNIX, true).expect("session");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let session = session_path(&data_arg, &database_arg);
    if let Some(parent) = session.parent() {
        std::fs::create_dir_all(parent).expect("signed-in directory");
    }
    std::fs::write(&session, format!("{{\"token\":\"{TOKEN}\"}}")).expect("session file");
    std::fs::set_permissions(&session, std::fs::Permissions::from_mode(0o600)).expect("mode");
    World {
        data_arg,
        database_arg,
        user,
    }
}

fn boot(world: &World) -> Server {
    let mut server = Server::spawn(&[
        "--data-dir",
        &world.data_arg,
        "--database",
        &world.database_arg,
        "--now",
        NOW_ISO,
    ]);
    server.handshake();
    server
}

fn school_stands(world: &World) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 420,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"
    });
    let intent = edit_intent("school", WEEK, None, Some(&school)).expect("new");
    apply_repeat_intents(&conn, world.user, &[intent]).expect("school stands");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
}

fn body_of(response: &Value) -> Value {
    tool_ok_text(response)
        .and_then(|text| serde_json::from_str(text).ok())
        .unwrap_or(Value::Null)
}

fn stored(world: &World) -> (Value, i64) {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.query_row(
        "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
        (world.user, WEEK),
        |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
    )
    .map(|(text, revision)| (serde_json::from_str(&text).unwrap_or(Value::Null), revision))
    .unwrap_or((Value::Null, -1))
}

fn labels(world: &World) -> Vec<String> {
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut stmt = conn
        .prepare("SELECT label FROM restore_points WHERE user_id = ?1 ORDER BY seq")
        .expect("prepare");
    stmt.query_map((world.user,), |row| row.get::<_, String>(0))
        .expect("query")
        .map(|row| row.expect("label"))
        .collect()
}

fn minutes(hhmm: &str) -> i64 {
    let (hour, minute) = hhmm.split_once(':').unwrap_or(("0", "0"));
    hour.parse::<i64>().unwrap_or(0) * 60 + minute.parse::<i64>().unwrap_or(0)
}

/// `(day, start, end)` of every occurrence a block takes, missed days left out.
fn spans(block: &Value) -> Vec<(i64, i64, i64)> {
    let Some(start) = block.get("start").and_then(Value::as_str) else {
        return Vec::new();
    };
    let begin = minutes(start);
    let length = block["duration_min"].as_i64().unwrap_or(0);
    let missed: Vec<i64> = block["missed_days"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_i64)
        .collect();
    block["days"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_i64)
        .filter(|day| !missed.contains(day))
        .map(|day| (day, begin, begin + length))
        .collect()
}

fn add_essay(server: &mut Server, id: i64) -> String {
    let added = server.call(
        "add_homework",
        json!({
            "operation_id": "op-plan-essay",
            "title": "Essay",
            "due": "2026-10-23T21:00",
            "estimate_min": 90
        }),
        id,
    );
    body_of(&added)["result"]["assignment"]["id"]
        .as_str()
        .unwrap_or("")
        .to_string()
}

fn family_evening(server: &mut Server, id: i64) {
    let added = server.call(
        "add_block",
        json!({
            "operation_id": "op-plan-family",
            "week_start": WEEK,
            "title": "Family",
            "category": "free",
            "days": [2],
            "start": "15:00",
            "end": "24:00"
        }),
        id,
    );
    assert_eq!(
        body_of(&added)["ok"],
        json!(true),
        "the evening is held, got {added}"
    );
}

fn session_of<'a>(blocks: &'a Value, assignment: &str) -> &'a Value {
    blocks
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .find(|block| block["assignment_id"].as_str() == Some(assignment))
        })
        .unwrap_or(&Value::Null)
}

#[test]
fn plan_places_homework_around_school_and_fixed_time_in_one_change() {
    let world = signed_in("plan-around-school");
    school_stands(&world);
    let mut server = boot(&world);
    let essay = add_essay(&mut server, 2);
    assert!(!essay.is_empty(), "the essay is saved");
    family_evening(&mut server, 3);
    let before = labels(&world).len();
    let (_, revision) = stored(&world);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-week", "week_start": WEEK}),
        4,
    );
    let body = body_of(&planned);
    assert_eq!(body["ok"], json!(true), "the plan lands, got {planned}");
    let placed = body["result"]["placed"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert_eq!(placed.len(), 1, "the essay's session is placed, got {body}");
    assert_eq!(placed[0]["assignment_id"], json!(essay));
    assert_eq!(
        body["result"]["not_placed"],
        json!([]),
        "nothing is left without a time, got {body}"
    );
    let (blocks, after) = stored(&world);
    assert_eq!(after, revision + 1, "the plan is one change to the week");
    assert_eq!(
        body["result"]["revision"],
        json!(after),
        "the reply has the new revision"
    );
    let session = session_of(&blocks, &essay);
    let taken = spans(session);
    assert_eq!(
        taken.len(),
        1,
        "the session sits on one day at one time, got {session}"
    );
    let (day, start, end) = taken[0];
    assert_eq!(end - start, 90, "the whole estimate is planned");
    assert!(
        (day, start) >= (2, 12 * 60),
        "nothing is placed before now, got day {day} at {start}"
    );
    assert!(
        (day, end) <= (4, 21 * 60),
        "the session ends before the essay is due, got day {day} ending {end}"
    );
    let fixed: Vec<(i64, i64, i64)> = blocks
        .as_array()
        .into_iter()
        .flatten()
        .filter(|block| block["kind"] == json!("locked"))
        .flat_map(spans)
        .collect();
    let school_seen = body_of(&server.call("get_week", json!({"week_start": WEEK}), 5))["blocks"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|block| block["kind"] == json!("locked"))
        .flat_map(spans)
        .collect::<Vec<_>>();
    assert!(
        school_seen.iter().any(|(d, s, _)| *d == 3 && *s == 8 * 60),
        "school stands in the week the planner saw, got {school_seen:?}"
    );
    for (other_day, other_start, other_end) in fixed.iter().chain(school_seen.iter()) {
        assert!(
            *other_day != day || end <= *other_start || *other_end <= start,
            "the session ({day}, {start}-{end}) must not overlap fixed time \
             ({other_day}, {other_start}-{other_end})"
        );
    }
    let saved = labels(&world);
    assert_eq!(
        saved.len(),
        before + 1,
        "the plan saves one restore point, got {saved:?}"
    );
    assert!(
        saved
            .last()
            .is_some_and(|label| label.starts_with("Before assistant plan_homework")),
        "got {saved:?}"
    );
    let again = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-week", "week_start": WEEK}),
        6,
    );
    assert_eq!(body_of(&again), body, "a retry returns the first answer");
    assert_eq!(stored(&world).1, after, "a retry writes nothing");
}

#[test]
fn plan_of_a_full_day_says_why_and_writes_nothing() {
    let world = signed_in("plan-full-day");
    school_stands(&world);
    let mut server = boot(&world);
    let essay = add_essay(&mut server, 2);
    family_evening(&mut server, 3);
    let points = labels(&world).len();
    let (_, revision) = stored(&world);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-wednesday", "week_start": WEEK, "day": 2}),
        4,
    );
    let body = body_of(&planned);
    assert_eq!(
        body["ok"],
        json!(true),
        "a plan that places nothing still answers, got {planned}"
    );
    assert_eq!(
        body["result"]["placed"],
        json!([]),
        "Wednesday has no free time, got {body}"
    );
    let waiting = body["result"]["not_placed"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert_eq!(waiting.len(), 1, "the essay is left waiting, got {body}");
    assert_eq!(waiting[0]["assignment_id"], json!(essay));
    assert!(
        waiting[0]["why"]
            .as_str()
            .is_some_and(|why| !why.is_empty()),
        "the reply says why in the planner's words, got {body}"
    );
    assert_eq!(
        stored(&world).1,
        revision,
        "nothing placed, nothing written"
    );
    assert_eq!(
        labels(&world).len(),
        points,
        "nothing written, no restore point"
    );
}

#[test]
fn plan_of_one_day_places_only_on_that_day_and_not_before_now() {
    let world = signed_in("plan-one-day");
    let mut server = boot(&world);
    let essay = add_essay(&mut server, 2);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-today", "week_start": WEEK, "day": 2}),
        3,
    );
    let body = body_of(&planned);
    assert_eq!(body["ok"], json!(true), "got {planned}");
    let (blocks, _) = stored(&world);
    let taken = spans(session_of(&blocks, &essay));
    assert_eq!(taken.len(), 1, "the essay is placed, got {blocks}");
    let (day, start, _) = taken[0];
    assert_eq!(day, 2, "a plan of Wednesday places on Wednesday");
    assert!(start >= 12 * 60, "not before now (12:00), got {start}");
    let thursday = signed_in("plan-thursday");
    let mut server = boot(&thursday);
    let essay = add_essay(&mut server, 2);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-thursday", "week_start": WEEK, "day": 3}),
        3,
    );
    assert_eq!(body_of(&planned)["ok"], json!(true), "got {planned}");
    let (blocks, _) = stored(&thursday);
    let taken = spans(session_of(&blocks, &essay));
    assert_eq!(
        taken.first().map(|span| span.0),
        Some(3),
        "Thursday's plan, got {blocks}"
    );
}

#[test]
fn plan_of_a_week_that_is_over_says_so() {
    let world = signed_in("plan-week-over");
    let mut server = boot(&world);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-old-week", "week_start": "2026-10-12"}),
        2,
    );
    let body = body_of(&planned);
    assert_eq!(body["result"]["message"], json!(WEEK_OVER), "got {planned}");
    assert_eq!(body["result"]["placed"], json!([]));
    assert!(
        labels(&world).is_empty(),
        "nothing written, no restore point"
    );
}

#[test]
fn plan_never_places_homework_in_time_that_has_passed() {
    // Wednesday is free only before noon, and it is noon now: the morning is over, so a plan of
    // Wednesday has nowhere to put the essay.
    let world = signed_in("plan-past-morning");
    let mut server = boot(&world);
    let essay = add_essay(&mut server, 2);
    let held = server.call(
        "add_block",
        json!({
            "operation_id": "op-plan-afternoon",
            "week_start": WEEK,
            "title": "Family",
            "category": "free",
            "days": [2],
            "start": "12:00",
            "end": "24:00"
        }),
        3,
    );
    assert_eq!(
        body_of(&held)["ok"],
        json!(true),
        "the afternoon is held, got {held}"
    );
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-past-morning", "week_start": WEEK, "day": 2}),
        4,
    );
    let body = body_of(&planned);
    assert_eq!(
        body["result"]["placed"],
        json!([]),
        "the passed morning is not used, got {body}"
    );
    let waiting = body["result"]["not_placed"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert_eq!(
        waiting.first().map(|row| row["assignment_id"].clone()),
        Some(json!(essay)),
        "the essay waits, got {body}"
    );
}

#[test]
fn plan_gives_homework_spread_over_days_its_share_of_this_week() {
    // 180 min "Spread over days", due Wed 4 Nov, its one session saved on this week with no time. Now is
    // Wed 21 Oct 12:00: this week's plannable days are Wed (after School) to Sun, 5; up to the 4th there
    // are 5 + 7 (next week) + 3 (Mon-Wed) = 15. No later week holds any of it, so this week's part is
    // 180, and the session being planned holds none of it yet: share = 180 x 5 / 15 = 60.
    let world = signed_in("plan-spread-share");
    school_stands(&world);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "poster",
        r#"{"id":"poster","title":"Poster","due":"2026-11-04T21:00","estimate_min":180,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium","spread":"spread"}"#,
    )
    .expect("homework");
    let waiting = json!([{
        "id": "poster-session", "title": "Poster", "kind": "flexible", "assignment_id": "poster",
        "duration_min": 180, "days": [0, 1, 2, 3, 4, 5, 6], "priority": 2, "energy": "medium",
        "category": "assignments"
    }]);
    save_week(&conn, world.user, WEEK, &waiting.to_string(), 0).expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-spread", "week_start": WEEK}),
        2,
    );
    let body = body_of(&planned);
    let placed: Vec<(Value, Value)> = body["result"]["placed"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(|row| (row["assignment_id"].clone(), row["duration_min"].clone()))
        .collect();
    assert_eq!(placed, vec![(json!("poster"), json!(60))], "got {body}");
}
