//! `plan_homework` runs FlexWeek's own planner as "Plan my homework" does (the phone's Rust port of
//! it, `ffi/src/plan_week.rs`): homework that has no time gets one around the fixed blocks, never
//! before now (Wednesday 2026-10-21 12:00), and never after it is due. What it places is written in
//! one change with one restore point; what it cannot place comes back with the planner's reason.
//! `day` keeps the plan to one day.

mod common;

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use common::{NOW_ISO, NOW_UNIX, Server, scratch, session_path, tool_error_text, tool_ok_text};
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

/// An essay of 60 minutes due Friday 21:00 whose one planned session ended on Monday 10:00 (a hand-shaped
/// one when `pinned`), for a plan on Wednesday 21 Oct 12:00, and what the plan placed.
fn plan_with_a_session_from_monday(name: &str, pinned: bool) -> (Value, Value) {
    plan_with_a_session_from_monday_due(name, pinned, "2026-10-23T21:00")
}

fn plan_with_a_session_from_monday_due(name: &str, pinned: bool, due: &str) -> (Value, Value) {
    let world = signed_in(name);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "essay",
        &format!(
            r#"{{"id":"essay","title":"Essay","due":"{due}","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium","spread":"one"}}"#
        ),
    )
    .expect("homework");
    let mut session = json!({
        "id": "essay-session", "title": "Essay", "kind": "flexible", "assignment_id": "essay",
        "duration_min": 60, "days": [0], "start": "09:00", "priority": 2, "energy": "medium",
        "category": "assignments"
    });
    if pinned {
        session["pinned"] = json!(true);
    }
    save_week(&conn, world.user, WEEK, &json!([session]).to_string(), 0).expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let mut server = boot(&world);
    let planned = server.call(
        "plan_homework",
        json!({"operation_id": "op-plan-passed", "week_start": WEEK}),
        2,
    );
    (body_of(&planned), stored(&world).0)
}

#[test]
fn plan_moves_a_session_of_this_week_that_passed_unfinished() {
    // Monday 09:00-10:00 is over at Wednesday 12:00: Plan gives the 60 minutes a time still ahead.
    let (body, blocks) = plan_with_a_session_from_monday("plan-moves-passed", false);
    assert_eq!(body["ok"], json!(true), "got {body}");
    let session = session_of(&blocks, "essay");
    let taken = spans(session);
    assert_eq!(taken.len(), 1, "one time, got {session}");
    let (day, start, end) = taken[0];
    assert_eq!(end - start, 60);
    assert!(
        (day, start) >= (2, 12 * 60),
        "not before now, got {day} {start}"
    );
    assert!(
        (day, end) <= (4, 21 * 60),
        "before it is due, got {day} {end}"
    );
}

#[test]
fn plan_that_cannot_place_a_passed_session_still_saves_that_it_has_no_time() {
    // Due Wednesday 12:30 and now Wednesday 12:00: the passed Monday session (60 minutes) cannot fit
    // before it is due. It places nothing, but the expired Monday time must not stay saved.
    let (body, blocks) =
        plan_with_a_session_from_monday_due("plan-saves-unplaced", false, "2026-10-21T12:30");
    assert_eq!(body["ok"], json!(true), "got {body}");
    assert_eq!(body["result"]["placed"], json!([]), "got {body}");
    assert_eq!(
        spans(session_of(&blocks, "essay")),
        Vec::<(i64, i64, i64)>::new(),
        "the passed time is still saved: {blocks}"
    );
}

#[test]
fn plan_keeps_a_pinned_session_of_this_week_that_passed() {
    let (body, blocks) = plan_with_a_session_from_monday("plan-keeps-pinned-passed", true);
    assert_eq!(body["ok"], json!(true), "got {body}");
    let sessions: Vec<&Value> = blocks
        .as_array()
        .into_iter()
        .flatten()
        .filter(|block| block["assignment_id"].as_str() == Some("essay"))
        .collect();
    // The pinned session stays where the student put it, unfinished; its 60 minutes are still needed,
    // so the plan gives them a new session at a time still ahead.
    assert_eq!(sessions.len(), 2, "pinned plus a new one, got {blocks}");
    let pinned = sessions
        .iter()
        .find(|block| block["id"] == "essay-session")
        .expect("the pinned session");
    assert_eq!(spans(pinned), vec![(0, 9 * 60, 10 * 60)]);
    let fresh = sessions
        .iter()
        .find(|block| block["id"] != "essay-session")
        .expect("a new session");
    let taken = spans(fresh);
    assert_eq!(taken.len(), 1, "one time, got {fresh}");
    assert_eq!(taken[0].2 - taken[0].1, 60);
    assert!(
        taken[0].0 > 2 || (taken[0].0 == 2 && taken[0].1 >= 12 * 60),
        "not before now, got {taken:?}"
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

#[test]
fn plan_homework_follows_monday_sunday_wednesday_and_month_end_crossing_weeks() {
    let world = signed_in("plan-shown-weeks");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    // Enable weekend_homework_free and set work windows ONLY on Monday 16:00-18:00 and Saturday 10:00-12:00.
    // On a Wednesday-starting week 2026-10-21..2026-10-27:
    //   - Saturday Oct 24 is shown day 3 (must be skipped because weekend_homework_free: true)
    //   - Monday Oct 26 is shown day 5 (must be chosen at 16:00 and stored in 2026-10-26 at day 0).
    let availability = json!({
        "work_windows": [
            {"days": [0], "start": "16:00", "end": "18:00"},
            {"days": [5], "start": "10:00", "end": "12:00"}
        ]
    });
    conn.execute(
        "UPDATE preferences SET weekend_homework_free = 1, buffer_min = 0, availability_json = ?1 WHERE user_id = ?2",
        (availability.to_string(), world.user),
    )
    .expect("prefs");
    insert_assignment(
        &conn,
        world.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    // Waiting session in earlier week 2026-10-12 must move into 2026-10-21; 2026-10-19 stays clean.
    save_week(
        &conn,
        world.user,
        "2026-10-12",
        &json!([{
            "id": "math-early", "title": "Math", "kind": "flexible", "assignment_id": "math",
            "duration_min": 60, "days": [2], "priority": 2, "energy": "medium"
        }])
        .to_string(),
        0,
    )
    .expect("earlier week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    // 1. Monday WEEK_OVER carries week_starts_on: "monday".
    let mon_over = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-mon-over", "week_start": "2026-10-12"}),
        2,
    ));
    assert_eq!(mon_over["result"]["message"], json!(WEEK_OVER));
    assert_eq!(mon_over["result"]["week_starts_on"], json!("monday"));

    // 2. Switch live to Wednesday.
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let wed_over = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-wed-over", "week_start": "2026-10-14"}),
        3,
    ));
    assert_eq!(wed_over["result"]["message"], json!(WEEK_OVER));
    assert_eq!(wed_over["result"]["week_starts_on"], json!("wednesday"));

    let wed_plan = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-wed-plan", "week_start": "2026-10-21"}),
        4,
    ));
    assert_eq!(wed_plan["ok"], json!(true), "got {wed_plan}");
    assert_eq!(wed_plan["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(wed_plan["revision"], json!([0, 1]));
    let placed = wed_plan["result"]["placed"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert_eq!(placed.len(), 1, "got {wed_plan}");
    assert_eq!(
        placed[0]["day"],
        json!(5),
        "Monday Oct 26 is day 5 from Wed 21, skipping weekend"
    );
    assert_eq!(placed[0]["start"], json!("16:00"));
    let wed_retry = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-wed-plan", "week_start": "2026-10-21"}),
        5,
    ));
    assert_eq!(wed_retry, wed_plan);
    // Stored: 2026-10-12 emptied, 2026-10-26 has math-early at day 0 16:00, 2026-10-19 not created.
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let w12: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = '2026-10-12'",
            (world.user,),
            |row| row.get(0),
        )
        .expect("w12");
    assert_eq!(w12, "[]");
    let w26: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = '2026-10-26'",
            (world.user,),
            |row| row.get(0),
        )
        .expect("w26");
    let w26_blocks: Value = serde_json::from_str(&w26).expect("json");
    assert_eq!(session_of(&w26_blocks, "math")["days"], json!([0]));
    // Over-month homework for 2026-10-28..2026-11-03.
    insert_assignment(
        &conn,
        world.user,
        "bio",
        r#"{"id":"bio","title":"Bio","due":"2026-11-03T21:00","estimate_min":45,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("bio");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    // Month-end crossing Wednesday 2026-10-28..2026-11-03 places bio on Monday Nov 2 (shown day 5 -> 2026-11-02 day 0).
    let cross_wed = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-wed-plan-cross", "week_start": "2026-10-28"}),
        6,
    ));
    assert_eq!(cross_wed["ok"], json!(true), "got {cross_wed}");
    assert_eq!(cross_wed["result"]["week_starts_on"], json!("wednesday"));
    let bio_row = cross_wed["result"]["placed"]
        .as_array()
        .and_then(|arr| arr.iter().find(|r| r["assignment_id"] == "bio"))
        .cloned()
        .unwrap_or(Value::Null);
    assert_eq!(bio_row["day"], json!(5));
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let w_nov: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = '2026-11-02'",
            (world.user,),
            |row| row.get(0),
        )
        .expect("w_nov");
    let w_nov_blocks: Value = serde_json::from_str(&w_nov).expect("json");
    assert_eq!(session_of(&w_nov_blocks, "bio")["days"], json!([0]));
    drop(conn);

    // Old client Monday compatibility.
    let compat = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-mon-plan-compat", "week_start": "2026-11-09"}),
        7,
    ));
    assert_eq!(compat["result"]["week_starts_on"], json!("monday"));
    assert!(compat["revision"].is_i64(), "got {compat}");

    // 3. Switch live to Sunday and test 2026-11-29 (Sun..Dec 5) placing chem on Monday Nov 30 (day 1 -> 2026-11-30 day 0).
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "chem",
        r#"{"id":"chem","title":"Chem","due":"2026-12-05T21:00","estimate_min":45,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("chem");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");
    let cross_sun = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-sun-plan-cross", "week_start": "2026-11-29"}),
        8,
    ));
    assert_eq!(cross_sun["ok"], json!(true), "got {cross_sun}");
    assert_eq!(cross_sun["result"]["week_starts_on"], json!("sunday"));
    let chem_row = cross_sun["result"]["placed"]
        .as_array()
        .and_then(|arr| arr.iter().find(|r| r["assignment_id"] == "chem"))
        .cloned()
        .unwrap_or(Value::Null);
    assert_eq!(chem_row["day"], json!(1));
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let w_dec: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = '2026-11-30'",
            (world.user,),
            |row| row.get(0),
        )
        .expect("w_dec");
    let w_dec_blocks: Value = serde_json::from_str(&w_dec).expect("json");
    assert_eq!(session_of(&w_dec_blocks, "chem")["days"], json!([0]));
}

#[test]
fn plan_carries_hidden_waiting_session_from_first_week_once_and_keeps_unrelated_hidden_blocks() {
    // Case A: Exact hidden-waiting fixture + unrelated hidden locked block and expired waiting block.
    let world = signed_in("plan-hidden-waiting");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    insert_assignment(
        &conn,
        world.user,
        "expired",
        r#"{"id":"expired","title":"Old","due":"2026-10-19T21:00","estimate_min":30,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("expired");
    let w19 = json!([
        {"id": "math-open", "title": "Math", "kind": "flexible", "assignment_id": "math",
         "duration_min": 60, "days": [0, 1], "priority": 2, "energy": "medium"},
        {"id": "gym-hidden", "title": "Gym", "kind": "locked", "duration_min": 60,
         "days": [0, 1], "start": "07:00", "category": "extra"},
        {"id": "expired-open", "title": "Old", "kind": "flexible", "assignment_id": "expired",
         "duration_min": 30, "days": [0, 1], "priority": 2, "energy": "medium"}
    ]);
    save_week(&conn, world.user, WEEK, &w19.to_string(), 0).expect("save w19");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    let planned = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-hidden-wait", "week_start": "2026-10-21"}),
        2,
    ));
    assert_eq!(planned["ok"], json!(true), "got {planned}");
    assert_eq!(
        planned["result"]["placed"].as_array().map(Vec::len),
        Some(1),
        "only one placed: {planned}"
    );

    let (w19_after, _) = stored(&world);
    let math_blocks: Vec<&Value> = w19_after
        .as_array()
        .into_iter()
        .flatten()
        .filter(|b| b["assignment_id"] == json!("math"))
        .collect();
    assert_eq!(
        math_blocks.len(),
        1,
        "must not duplicate math session, got {w19_after}"
    );
    assert_eq!(math_blocks[0]["id"], json!("math-open"));
    assert_eq!(math_blocks[0]["start"], json!("12:00"));
    assert_eq!(math_blocks[0]["days"], json!([2]));
    assert!(
        w19_after
            .as_array()
            .into_iter()
            .flatten()
            .any(|b| b["id"] == json!("gym-hidden")),
        "unrelated hidden locked block kept: {w19_after}"
    );
    assert!(
        w19_after
            .as_array()
            .into_iter()
            .flatten()
            .any(|b| b["id"] == json!("expired-open")),
        "unrelated expired hidden block kept: {w19_after}"
    );

    // Case B: Hidden waiting session in first (days [0, 1]) is placed into SECOND (Mon Oct 26, day 5).
    let world_b = signed_in("plan-hidden-to-second");
    std::fs::write(
        Path::new(&world_b.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&world_b.database_arg)).expect("open");
    let availability = json!({"work_windows": [{"days": [0], "start": "16:00", "end": "18:00"}]});
    conn.execute(
        "UPDATE preferences SET availability_json = ?1 WHERE user_id = ?2",
        (availability.to_string(), world_b.user),
    )
    .expect("prefs");
    insert_assignment(
        &conn,
        world_b.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    save_week(
        &conn,
        world_b.user,
        WEEK,
        &json!([
            {"id": "math-open", "title": "Math", "kind": "flexible", "assignment_id": "math",
             "duration_min": 60, "days": [0, 1], "priority": 2, "energy": "medium"},
            {"id": "gym-hidden", "title": "Gym", "kind": "locked", "duration_min": 60,
             "days": [0], "start": "07:00", "category": "extra"}
        ])
        .to_string(),
        0,
    )
    .expect("save w19");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server_b = boot(&world_b);
    let planned_b = body_of(&server_b.call(
        "plan_homework",
        json!({"operation_id": "op-hidden-sec", "week_start": "2026-10-21"}),
        2,
    ));
    assert_eq!(planned_b["ok"], json!(true), "got {planned_b}");
    assert_eq!(planned_b["revision"], json!([2, 1]));
    let (w19_b, _) = stored(&world_b);
    assert!(
        w19_b
            .as_array()
            .into_iter()
            .flatten()
            .all(|b| b["assignment_id"] != json!("math")),
        "hidden waiting copy must be removed from first week when placed in second: {w19_b}"
    );
    assert!(
        w19_b
            .as_array()
            .into_iter()
            .flatten()
            .any(|b| b["id"] == json!("gym-hidden")),
        "unrelated hidden block stays in first week: {w19_b}"
    );
    let conn = open_connection(Path::new(&world_b.database_arg)).expect("open");
    let w26_raw: String = conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = '2026-10-26'",
            (world_b.user,),
            |row| row.get(0),
        )
        .expect("w26");
    let w26: Value = serde_json::from_str(&w26_raw).expect("json");
    assert_eq!(session_of(&w26, "math")["id"], json!("math-open"));
    assert_eq!(session_of(&w26, "math")["start"], json!("16:00"));
    assert_eq!(session_of(&w26, "math")["days"], json!([0]));
}

#[test]
fn plan_retry_succeeds_after_week_start_setting_changes() {
    let world = signed_in("plan-retry-setting");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    let args = json!({"operation_id": "op-plan-retry-switch", "week_start": "2026-10-21"});
    let first = body_of(&server.call("plan_homework", args.clone(), 2));
    assert_eq!(first["ok"], json!(true), "got {first}");

    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "sunday"}"#,
    )
    .expect("sun");

    let retry_resp = server.call("plan_homework", args, 3);
    assert_eq!(
        tool_error_text(&retry_resp),
        None,
        "retry must succeed even after week_starts_on changes, got {retry_resp}"
    );
    assert_eq!(body_of(&retry_resp), first);
}

#[test]
fn plan_reply_failure_rolls_back_atomically() {
    let world = signed_in("plan-reply-fault");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    conn.execute_batch(
        "CREATE TRIGGER fail_reply_update BEFORE UPDATE OF response ON operations \
         BEGIN SELECT RAISE(FAIL, 'review injected reply failure'); END;",
    )
    .expect("trigger");
    drop(conn);

    let mut server = boot(&world);
    let args = json!({"operation_id": "op-plan-fault", "week_start": "2026-10-21"});
    let fail = server.call("plan_homework", args.clone(), 2);
    assert!(
        tool_error_text(&fail).is_some(),
        "fault must error, got {fail}"
    );
    assert_eq!(stored(&world).1, -1, "week must roll back on reply failure");
    assert!(labels(&world).is_empty(), "restore point must roll back");

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute_batch("DROP TRIGGER fail_reply_update;")
        .expect("drop");
    drop(conn);

    let retry = body_of(&server.call("plan_homework", args, 3));
    assert_eq!(retry["ok"], json!(true), "retry succeeds cleanly: {retry}");
    assert_eq!(retry["result"]["week_start"], json!("2026-10-21"));
    assert_eq!(retry["result"]["week_starts_on"], json!("wednesday"));
    assert_eq!(retry["revision"], json!([1, 0]));
}

#[test]
fn plan_homework_with_nothing_to_plan_in_shown_week_returns_stored_revisions() {
    let world = signed_in("plan-empty-shown-revisions");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");

    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, '2026-10-19', '[]', 4)",
        (world.user,),
    )
    .expect("first week");
    conn.execute(
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, '2026-10-26', '[]', 2)",
        (world.user,),
    )
    .expect("second week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    let planned = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-empty-shown", "week_start": "2026-10-21"}),
        2,
    ));
    assert_eq!(planned["ok"], json!(true), "got {planned}");
    assert_eq!(
        planned["revision"],
        json!([4, 2]),
        "must return observed stored revisions, got {planned}"
    );
    assert_eq!(
        planned["result"]["revision"],
        json!([4, 2]),
        "result revision must match stored revisions, got {planned}"
    );

    let added = body_of(&server.call(
        "add_block",
        json!({
            "operation_id": "op-after-empty-plan",
            "week_start": "2026-10-21",
            "expected_revision": planned["revision"],
            "title": "Study",
            "days": [1],
            "start": "16:00",
            "end": "17:00"
        }),
        3,
    ));
    assert_eq!(
        added["ok"],
        json!(true),
        "write using returned revision pair must succeed without conflict: {added}"
    );
    assert_eq!(added["revision"], json!([5, 2]));
}

fn add_poster(server: &mut Server, operation: &str, spread: bool, id: i64) -> (String, i64) {
    let added = server.call(
        "add_homework",
        json!({
            "operation_id": operation,
            "title": "Poster",
            "due": "2026-10-25T21:00",
            "estimate_min": 180,
            "spread": spread
        }),
        id,
    );
    let body = body_of(&added);
    assert_eq!(body["ok"], json!(true), "got {added}");
    (
        body["result"]["assignment"]["id"]
            .as_str()
            .unwrap_or("")
            .to_string(),
        body["revision"].as_i64().unwrap_or(0),
    )
}

fn poster_sessions(world: &World, poster: &str) -> Vec<(i64, i64, bool)> {
    let (blocks, _) = stored(world);
    let mut rows: Vec<(i64, i64, bool)> = blocks
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter(|block| block["assignment_id"].as_str() == Some(poster))
        .map(|block| {
            (
                block["days"][0].as_i64().unwrap_or(-1),
                block["duration_min"].as_i64().unwrap_or(0),
                block["start"].is_string(),
            )
        })
        .collect();
    rows.sort();
    rows
}

fn plan_week(server: &mut Server, operation: &str, id: i64) -> Value {
    body_of(&server.call(
        "plan_homework",
        json!({"operation_id": operation, "week_start": WEEK}),
        id,
    ))
}

#[test]
fn a_homework_added_as_spread_is_hour_sessions_on_different_days_as_in_the_app() {
    // Now is Wed 21 Oct 12:00, due Sun 25 Oct, 180 min. The app's Spread over days makes sessions of
    // an hour from today: Wed, Thu and Fri (days 2, 3, 4), and Plan places each where it is.
    let world = signed_in("spread-add-sessions");
    school_stands(&world);
    let mut server = boot(&world);
    let (poster, _) = add_poster(&mut server, "op-spread-add", true, 2);
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(2, 60, false), (3, 60, false), (4, 60, false)]
    );
    let planned = plan_week(&mut server, "op-spread-add-plan", 3);
    assert_eq!(planned["ok"], json!(true), "got {planned}");
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(2, 60, true), (3, 60, true), (4, 60, true)]
    );
}

#[test]
fn a_homework_added_in_one_go_stays_one_session() {
    let world = signed_in("spread-add-one");
    school_stands(&world);
    let mut server = boot(&world);
    let (poster, _) = add_poster(&mut server, "op-one-add", false, 2);
    assert_eq!(poster_sessions(&world, &poster).len(), 1);
    plan_week(&mut server, "op-one-add-plan", 3);
    let sessions = poster_sessions(&world, &poster);
    assert_eq!(sessions.len(), 1);
    assert_eq!((sessions[0].1, sessions[0].2), (180, true));
}

#[test]
fn editing_a_planned_homework_to_spread_replaces_its_whole_session() {
    let world = signed_in("spread-edit-sessions");
    school_stands(&world);
    let mut server = boot(&world);
    let (poster, revision) = add_poster(&mut server, "op-edit-add", false, 2);
    plan_week(&mut server, "op-edit-plan-1", 3);
    assert_eq!(poster_sessions(&world, &poster).len(), 1);
    let edited = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-edit-spread",
            "id": poster,
            "expected_revision": revision,
            "spread": true
        }),
        4,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(2, 60, false), (3, 60, false), (4, 60, false)],
        "the old whole session is gone"
    );
    plan_week(&mut server, "op-edit-plan-2", 5);
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(2, 60, true), (3, 60, true), (4, 60, true)]
    );
}

#[test]
fn editing_to_spread_keeps_a_session_ticked_done_and_spreads_only_what_is_left() {
    // 180 min, one hour already ticked done on Monday: spreading leaves that hour alone and cuts the other
    // 120 into two hours, on Wednesday (today) and Thursday.
    let world = signed_in("spread-edit-done");
    school_stands(&world);
    let mut server = boot(&world);
    let (poster, revision) = add_poster(&mut server, "op-done-add", false, 2);
    let (_, week_revision) = stored(&world);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let done = json!([{
        "id": "done-hour", "title": "Poster", "kind": "flexible", "assignment_id": poster,
        "duration_min": 60, "days": [0], "start": "09:00", "completed": true, "completed_day": 0,
        "priority": 3, "energy": "medium", "category": "assignments"
    }]);
    save_week(&conn, world.user, WEEK, &done.to_string(), week_revision).expect("week");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let edited = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-done-spread",
            "id": poster,
            "expected_revision": revision,
            "spread": true
        }),
        3,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(0, 60, true), (2, 60, false), (3, 60, false)]
    );
}

#[test]
fn spreading_takes_off_the_larger_of_focus_time_and_ticked_done_time() {
    // 180 min with 60 min of focus and one hour also ticked done: done time is 60, not 120, so 120 min
    // are cut into two hours (Wednesday and Thursday), not one.
    let world = signed_in("spread-edit-focus");
    school_stands(&world);
    let mut server = boot(&world);
    let (poster, revision) = add_poster(&mut server, "op-focus-add", false, 2);
    let (_, week_revision) = stored(&world);
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let done = json!([{
        "id": "done-hour", "title": "Poster", "kind": "flexible", "assignment_id": poster,
        "duration_min": 60, "days": [0], "start": "09:00", "completed": true, "completed_day": 0,
        "priority": 3, "energy": "medium", "category": "assignments"
    }]);
    save_week(&conn, world.user, WEEK, &done.to_string(), week_revision).expect("week");
    conn.execute(
        "UPDATE assignments SET body = json_set(body, '$.focus_minutes', 60) WHERE user_id = ?1 AND id = ?2",
        (world.user, &poster),
    )
    .expect("focus");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);
    let edited = server.call(
        "edit_homework",
        json!({
            "operation_id": "op-focus-spread",
            "id": poster,
            "expected_revision": revision,
            "spread": true
        }),
        3,
    );
    assert_eq!(body_of(&edited)["ok"], json!(true), "got {edited}");
    assert_eq!(
        poster_sessions(&world, &poster),
        vec![(0, 60, true), (2, 60, false), (3, 60, false)]
    );
}

/// From Wednesday 21 October, today, the week on screen is Wednesday 21 to Tuesday 27, and Monday 19's
/// stored week holds its first five days. A session waiting there on days the screen shows is this
/// week's: Plan gives the homework its hour once, not again for that stored week taken as an earlier one.
#[test]
fn plan_from_wednesday_gives_a_session_waiting_in_the_first_stored_week_its_length_once() {
    let world = signed_in("plan-wednesday-first-half");
    std::fs::write(
        Path::new(&world.data_arg).join("week-start.json"),
        r#"{"week_starts_on": "wednesday"}"#,
    )
    .expect("wed");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    insert_assignment(
        &conn,
        world.user,
        "math",
        r#"{"id":"math","title":"Math","due":"2026-10-27T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":2,"energy":"medium"}"#,
    )
    .expect("math");
    let waiting = json!([
        {"id": "math-open", "title": "Math", "kind": "flexible", "assignment_id": "math",
         "duration_min": 60, "days": [0, 1, 2, 3, 4, 5, 6], "priority": 2, "energy": "medium"}
    ]);
    save_week(&conn, world.user, WEEK, &waiting.to_string(), 0).expect("save w19");
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").expect("commit");
    }
    drop(conn);

    let mut server = boot(&world);
    let planned = body_of(&server.call(
        "plan_homework",
        json!({"operation_id": "op-wed-first-half", "week_start": "2026-10-21"}),
        2,
    ));
    assert_eq!(planned["ok"], json!(true), "got {planned}");
    let placed = planned["result"]["placed"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert_eq!(placed.len(), 1, "got {planned}");
    let conn = open_connection(Path::new(&world.database_arg)).expect("open");
    let mut lengths = Vec::new();
    for week in [WEEK, "2026-10-26"] {
        let text: String = conn
            .query_row(
                "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = ?2",
                (world.user, week),
                |row| row.get(0),
            )
            .unwrap_or_else(|_| "[]".into());
        let blocks: Value = serde_json::from_str(&text).expect("blocks");
        lengths.extend(
            blocks
                .as_array()
                .into_iter()
                .flatten()
                .filter(|block| block["assignment_id"] == json!("math"))
                .map(|block| block["duration_min"].clone()),
        );
    }
    assert_eq!(lengths, vec![json!(60)], "got {planned}");
}
