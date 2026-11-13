//! One count of a homework's minutes for every caller (desktop, phone, assistant helper):
//!
//! this week's part = estimate - focus done - what its not-finished sessions in LATER weeks hold;
//! minutes no session holds = this week's part - what this week's not-finished sessions hold (placed
//! or waiting), never below 0; Plan and paste may place those minutes down to a quarter hour; a
//! "Spread over days" share is cut from all of this week's part, the sessions being planned holding
//! nothing yet. Sessions in an earlier week hold nothing here, as on main.
//!
//! What later weeks hold comes from the server's `planned_min` (every saved, not-finished session from
//! this week on) and the one input every caller passes: this week exactly as saved when that number was
//! read, every session in it, placed or waiting (`saved`).
//!
//! Every expected number is worked out by hand in the comment beside it.

mod common;

use common::desk::with;
use flexweek_engine::desk::{clipboard, planning};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-10-05"; // Monday

/// The homework as the server lists it for WEEK: `planned` is every saved, not-finished session from WEEK
/// on, and `unplanned_min` is the server's own max(0, estimate - focus - planned).
fn read(id: &str, estimate: i64, focus: i64, planned: i64, due: &str) -> Value {
    json!({
        "id": id, "title": id, "estimate_min": estimate, "focus_minutes": focus, "completed": false,
        "due": due, "spread": "one", "priority": 2, "energy": "medium",
        "planned_min": planned, "unplanned_min": (estimate - focus - planned).max(0),
    })
}

fn history(planned: i64) -> Value {
    read("history", 60, 0, planned, "2026-10-08T21:00")
}

fn session(id: &str, homework: &str, minutes: i64, start: Option<&str>) -> Value {
    let mut block = json!({
        "id": id, "assignment_id": homework, "title": homework, "kind": "flexible",
        "duration_min": minutes, "days": [3], "completed": false,
    });
    if let Some(start) = start {
        block["start"] = json!(start);
        block["pinned"] = json!(true);
    }
    block
}

fn uncovered(assignment: &Value, blocks: &[Value], saved: &[Value]) -> i64 {
    planning::uncovered_homework_minutes(assignment, &json!(blocks), &json!(saved)).unwrap()
}

fn placeable(assignment: &Value, blocks: &[Value], saved: &[Value]) -> i64 {
    planning::available_homework_minutes(assignment, &json!(blocks), &json!(saved)).unwrap()
}

fn table(assignment: &Value) -> Map<String, Value> {
    let id = assignment["id"].as_str().unwrap().to_string();
    let mut map = Map::new();
    map.insert(id, assignment.clone());
    map
}

/// (minutes, waiting_min, uncovered_min) of the one homework, or None when it needs nothing.
fn needed(assignment: &Value, blocks: &[Value], saved: &[Value]) -> Option<(i64, i64, i64)> {
    let parts = planning::time_still_needed_parts(&table(assignment), blocks, WEEK, saved).unwrap();
    parts.first().map(|item| {
        (
            item["minutes"].as_i64().unwrap(),
            item["waiting_min"].as_i64().unwrap(),
            item["uncovered_min"].as_i64().unwrap(),
        )
    })
}

/// The rest sessions Plan adds: (homework, minutes) of each block it made.
fn rests(
    assignment: &Value,
    blocks: &[Value],
    earlier: &[Value],
    saved: &[Value],
) -> Vec<(String, i64)> {
    let out = planning::open_rest_sessions_since(blocks, &table(assignment), WEEK, earlier, saved)
        .unwrap();
    out[blocks.len()..]
        .iter()
        .map(|block| {
            (
                block["assignment_id"].as_str().unwrap().to_string(),
                block["duration_min"].as_i64().unwrap(),
            )
        })
        .collect()
}

#[test]
fn a_session_cut_by_hand_then_plan_in_one_week() {
    // 60 min, its one session cut by hand to c and saved; the server read it (planned c). Step 15 reaches
    // c = 15 only; step 5 reaches all four. The engine counts the same on either step.
    //   c   no session holds   Plan's rest (down to 15)   after Plan places it
    //   5   60 - 5  = 55       45                         60 - 5 - 45  = 10
    //   15  60 - 15 = 45       45                         60 - 15 - 45 = 0
    //   20  60 - 20 = 40       30                         60 - 20 - 30 = 10
    //   50  60 - 50 = 10       none (10 < 15)             10
    for (cut, before, rest, after) in [
        (5, 55, Some(45), 10),
        (15, 45, Some(45), 0),
        (20, 40, Some(30), 10),
        (50, 10, None, 10),
    ] {
        let mine = session("cut", "history", cut, Some("18:45"));
        let saved = [mine.clone()];
        let assignment = history(cut);
        assert_eq!(
            uncovered(&assignment, &saved, &saved),
            before,
            "cut to {cut}"
        );
        assert_eq!(
            needed(&assignment, &saved, &saved),
            Some((before, 0, before))
        );
        let made = rests(&assignment, &saved, &[], &saved);
        assert_eq!(
            made.first().map(|(_, minutes)| *minutes),
            rest,
            "cut to {cut}"
        );
        // Plan placed the rest; the week is not saved yet, so the numbers are still those read with `saved`.
        let mut planned = vec![mine.clone()];
        if let Some(minutes) = rest {
            planned.push(session("rest", "history", minutes, Some("19:00")));
        }
        assert_eq!(
            uncovered(&assignment, &planned, &saved),
            after,
            "cut to {cut}"
        );
        // Saved and read again (planned c + rest): the same count.
        let reread = history(cut + rest.unwrap_or(0));
        assert_eq!(
            uncovered(&reread, &planned, &planned),
            after,
            "cut to {cut}"
        );
        // What Plan or paste may place of what is left: whole quarter hours only, so 10 is 0.
        assert_eq!(placeable(&reread, &planned, &planned), 0, "cut to {cut}");
    }
}

#[test]
fn the_poster_with_a_waiting_rest_session() {
    // 600 min due this week, its session cut to 5 and saved (planned 5): 595 have no session. Plan's rest
    // is 585 (39 quarter hours); it found no room, so it waits. 600 - 5 - 585 = 10 have no session.
    let poster = read("poster", 600, 0, 5, "2026-10-06T08:00");
    let cut = session("cut", "poster", 5, Some("18:45"));
    let saved = [cut.clone()];
    assert_eq!(
        rests(&poster, &saved, &[], &saved),
        vec![("poster".into(), 585)]
    );
    let waiting = session("rest", "poster", 585, None);
    let week = [cut.clone(), waiting.clone()];
    // Unsaved: 585 waiting + 10 with no session = 595.
    assert_eq!(needed(&poster, &week, &saved), Some((595, 585, 10)));
    // Saved and read again (planned 5 + 585 = 590): still 595 = 585 + 10.
    let reread = read("poster", 600, 0, 590, "2026-10-06T08:00");
    assert_eq!(needed(&reread, &week, &week), Some((595, 585, 10)));
    // Plan tried it and it still waits: open, and not "waiting only" (10 min are in no session).
    assert_eq!(
        planning::plan_open_counts(&table(&reread), &week, WEEK, &week).unwrap(),
        (1, 0)
    );
    // Plan again: the waiting session is the poster's open session, so no second rest is made.
    assert!(rests(&reread, &week, &[], &week).is_empty());
}

#[test]
fn a_twenty_five_minute_focus_timer() {
    // 60 min, nothing planned, read (planned 0, unplanned 60); then a 25 min timer is credited here and the
    // number is not read again yet: 60 - 25 - 0 = 35 have no session; Plan's rest is 30.
    let timed = with(history(0), json!({"focus_minutes": 25}));
    assert_eq!(uncovered(&timed, &[], &[]), 35);
    assert_eq!(rests(&timed, &[], &[], &[]), vec![("history".into(), 30)]);
    // Read again (unplanned 35): the same.
    assert_eq!(
        uncovered(&read("history", 60, 25, 0, "2026-10-08T21:00"), &[], &[]),
        35
    );
    // With a 30 min session saved before the timer (planned 30): 60 - 25 - 30 = 5. Too short to place.
    let held = [session("one", "history", 30, Some("18:45"))];
    let timed = with(history(30), json!({"focus_minutes": 25}));
    assert_eq!(uncovered(&timed, &held, &held), 5);
    assert_eq!(placeable(&timed, &held, &held), 0);
    assert!(rests(&timed, &held, &[], &held).is_empty());
}

#[test]
fn homework_finished_early_needs_nothing() {
    // Marked finished with 30 of its 60 min still in a session: no count, no rest, nothing to paste.
    let done = with(history(30), json!({"completed": true}));
    let held = [session("one", "history", 30, Some("18:45"))];
    assert_eq!(uncovered(&done, &held, &held), 0);
    assert_eq!(placeable(&done, &[], &[]), 0);
    assert_eq!(needed(&done, &held, &held), None);
    assert!(rests(&done, &[], &[], &[]).is_empty());
}

#[test]
fn a_finished_session_holds_nothing() {
    // 60 min, a 30 min session marked finished and 30 min of focus credited for it: the server counts no
    // finished session (planned 0), so 60 - 30 - 0 = 30 still have no session.
    let done = with(
        session("one", "history", 30, Some("18:45")),
        json!({"completed": true}),
    );
    let assignment = read("history", 60, 30, 0, "2026-10-08T21:00");
    let week = [done];
    assert_eq!(uncovered(&assignment, &week, &week), 30);
}

#[test]
fn sessions_this_week_and_next_week() {
    // 30 here + 30 next week on 60: planned 60, unplanned 0, saved [30]. Next week holds 60 - 30 = 30,
    // this week's part is 60 - 30 = 30, and the 30 here hold it: 0. A note saved on the homework changes
    // none of these numbers.
    let here = [session("a", "history", 30, Some("18:45"))];
    let noted = with(history(60), json!({"notes": "bring the atlas"}));
    assert_eq!(uncovered(&noted, &here, &here), 0);
    assert_eq!(needed(&noted, &here, &here), None);
    assert!(rests(&noted, &here, &[], &here).is_empty());

    // 45 here + 45 next week on 60 (planned 90). Next week holds 90 - 45 = 45, this week's part 15.
    // This week's session cut to 30, unsaved: 15 - 30 < 0, so 0. Cut to 5 instead: 15 - 5 = 10.
    let saved = [session("a", "history", 45, Some("18:45"))];
    let over = history(90);
    assert_eq!(
        uncovered(&over, &[session("a", "history", 30, Some("18:45"))], &saved),
        0
    );
    assert_eq!(
        uncovered(&over, &[session("a", "history", 5, Some("18:45"))], &saved),
        10
    );

    // 30 + 30 with the estimate raised to 90 and saved; read at 90: planned 60, unplanned 30. Next week
    // holds 60 - 30 = 30, this week's part 90 - 30 = 60, the 30 here hold half: 30 have no session.
    let raised = read("history", 90, 0, 60, "2026-10-08T21:00");
    assert_eq!(uncovered(&raised, &here, &here), 30);
    assert_eq!(placeable(&raised, &here, &here), 30);
    // Undo puts the estimate back to 60 while the numbers read at 90 are held: 60 - 30 - 30 = 0.
    let undone = with(raised, json!({"estimate_min": 60}));
    assert_eq!(uncovered(&undone, &here, &here), 0);
}

fn poster_far(planned: i64, estimate: i64) -> Value {
    with(
        read("poster", estimate, 0, planned, "2026-10-21T21:00"),
        json!({"title": "Science poster", "spread": "spread", "priority": 3}),
    )
}

fn school() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "days": [0, 1, 2, 3, 4],
           "start": "08:00", "duration_min": 390, "category": "class"})
}

/// fair_share on Saturday 10:00 (day 5, minute 600) with no study windows; returns the share notes.
fn share_of(assignment: &Value, blocks: &[Value], saved: &[Value]) -> (Vec<Value>, Vec<Value>) {
    planning::fair_share(
        blocks,
        &table(assignment),
        &json!(saved),
        WEEK,
        5,
        600,
        &[],
        &["poster-session".to_string()],
    )
    .unwrap()
}

#[test]
fn spread_over_days_is_shared_from_all_of_this_weeks_part() {
    // The phone's golden: 180 min due Wed 21 Oct, one 180 min session saved with no time (planned 180).
    // Planned on Saturday 10:00: this week's plannable days are Sat and Sun (2); up to the 21st there are
    // 2 + 7 (next week) + 3 (Mon-Wed) = 12. Next week holds 180 - 180 = 0, so this week's part is 180, and
    // the session being planned holds none of it yet: share = 180 x 2 / 12 = 30, the other 150 wait.
    let waiting = with(
        session("poster-session", "poster", 180, None),
        json!({"days": [5, 6]}),
    );
    let saved = [school(), waiting.clone()];
    let (week, notes) = share_of(&poster_far(180, 180), &saved, &saved);
    assert_eq!(
        notes,
        vec![json!({"assignment_id": "poster", "title": "Science poster",
                    "this_week_min": 30, "left_min": 150})]
    );
    let poster: Vec<i64> = week
        .iter()
        .filter(|block| block["assignment_id"] == "poster")
        .map(|block| block["duration_min"].as_i64().unwrap())
        .collect();
    assert_eq!(poster, vec![30, 150]);

    // The same homework at 240 min with 60 saved next week (planned 240): next week holds 240 - 180 = 60,
    // this week's part is 180 again: the same 30 and 150.
    let (_, notes) = share_of(&poster_far(240, 240), &saved, &saved);
    assert_eq!(notes[0]["this_week_min"], 30);
    assert_eq!(notes[0]["left_min"], 150);
}

#[test]
fn spread_over_days_after_a_waiting_session_moved_in_from_last_week() {
    // 180 min due Wed 21 Oct; its 180 min session waited in last week and Plan moved it into this one. The
    // server read this week empty (planned 0: last week is not counted, unplanned 180), so this week's part
    // is 180 and the moved session, not saved here yet, holds none of it: share 30, as above. Counting the
    // moved session as saved here would make the part 180 + 180 = 360 and the share 60.
    let moved = with(
        session("poster-session", "poster", 180, None),
        json!({"days": [5, 6]}),
    );
    let saved = [school()];
    let (_, notes) = share_of(&poster_far(0, 180), &[school(), moved], &saved);
    assert_eq!(notes[0]["this_week_min"], 30);
    assert_eq!(notes[0]["left_min"], 150);
}

#[test]
fn a_session_in_an_earlier_week_holds_nothing_here_as_on_main() {
    // 60 min due this Thursday; a 30 min session placed last week, not finished. The server counts from this
    // week on (planned 0, unplanned 60), so all 60 still need a time here, and the placed session last week
    // stops Plan from adding a rest session, both as on main.
    let last_week = [session("old", "history", 30, Some("16:00"))];
    let assignment = history(0);
    assert_eq!(uncovered(&assignment, &[], &[]), 60);
    assert_eq!(needed(&assignment, &[], &[]), Some((60, 0, 60)));
    assert!(rests(&assignment, &[], &last_week, &[]).is_empty());
    assert_eq!(
        rests(&assignment, &[], &[], &[]),
        vec![("history".into(), 60)]
    );
}

#[test]
fn plan_sizes_its_rest_from_the_numbers_and_the_week_they_were_read_with() {
    // 60 min, its 60 min session saved and read (planned 60, unplanned 0). The student cuts it to 5 and the
    // save goes through, but the new numbers have not been read yet. Against the week they were read with
    // ([60]): next week holds 60 - 60 = 0, 60 - 5 = 55 have no session, and Plan's rest is 45.
    let read_with = [session("a", "history", 60, Some("18:45"))];
    let now = [session("a", "history", 5, Some("18:45"))];
    assert_eq!(uncovered(&history(60), &now, &read_with), 55);
    assert_eq!(
        rests(&history(60), &now, &[], &read_with),
        vec![("history".into(), 45)]
    );
}

#[test]
fn a_paste_of_a_session_longer_than_what_is_left() {
    // 60 min with a 50 min session here (planned 50): 10 have no session. A copy of the 50 min session is
    // cut to the quarter hours that fit, none, so the paste names the 10 minutes.
    let held = [session("a", "history", 50, Some("18:45"))];
    let assignment = history(50);
    let left = uncovered(&assignment, &held, &held);
    assert_eq!(left, 10);
    let rows = clipboard::proposals_from_clipboard(
        &json!([{"block": held[0], "source_day": 3, "scope": "occurrence", "group_id": "g1"}]),
        "day",
        WEEK,
        4,
        None,
        &Value::Object(table(&assignment)),
        &json!({"history": left}),
    )
    .unwrap();
    assert_eq!(rows[0]["checked"], json!(false));
    assert_eq!(
        rows[0]["invalid"],
        "Only 10 min of this homework is left to plan, and a pasted session needs at least 15."
    );
}
