//! The count of what a homework's sessions hold (`planned_min`): a session in ANY week holds its time
//! when its time is still ahead of now; a ticked-done session is counted as done time instead (never
//! here); a session whose time passed unfinished, pinned or not, and a session with no time hold
//! nothing. Weeks from the open one on count as they always did.
//!
//! Calendar (2026): Monday 16 November, so Thursday 19 November is day 3. The clock reads Thursday 19
//! at 15:40. The open week is the one starting Monday 23 November.

use flexweek_engine::plan::{parse_moment, planned_minutes_by_id, planned_minutes_from_day};
use serde_json::{Value, json};

const NOW: &str = "2026-11-19T15:40";
const THIS_WEEK: &str = "2026-11-16";
const OLDER_WEEK: &str = "2026-11-09";
const NEXT_WEEK: &str = "2026-11-23";

fn session(id: &str, day: i64, start: Option<&str>, minutes: i64) -> Value {
    let mut block = json!({
        "id": id, "assignment_id": "hw", "title": "hw", "kind": "flexible",
        "duration_min": minutes, "days": [day], "completed": false,
    });
    if let Some(start) = start {
        block["start"] = json!(start);
    }
    block
}

fn held(weeks: &[(&str, Vec<Value>)], from_week: &str, now: Option<&str>) -> i64 {
    let weeks: Vec<(String, Vec<Value>)> = weeks
        .iter()
        .map(|(start, blocks)| (start.to_string(), blocks.clone()))
        .collect();
    let now = now.map(|stamp| parse_moment(stamp).unwrap());
    planned_minutes_by_id(&weeks, from_week, now)
        .get("hw")
        .copied()
        .unwrap_or(0)
}

#[test]
fn an_earlier_week_session_still_ahead_of_now_holds_its_time() {
    // Friday 14:00 (60) is ahead; Thursday 16:00 (45) starts after now; Thursday 15:00 (60) ends 16:00,
    // after 15:40, so it is on now. 60 + 45 + 60 = 165. Nothing else is in the open week.
    let weeks = [(
        THIS_WEEK,
        vec![
            session("fri", 4, Some("14:00"), 60),
            session("later", 3, Some("16:00"), 45),
            session("on-now", 3, Some("15:00"), 60),
        ],
    )];
    assert_eq!(held(&weeks, NEXT_WEEK, Some(NOW)), 165);
}

#[test]
fn an_earlier_week_session_that_passed_unfinished_holds_nothing() {
    // Wednesday 14:00 ended at 15:00 two days ago; Thursday 14:00 for 30 min ended at 14:30 today. A
    // pinned one that passed is the same: its minutes are still needed.
    let mut pinned = session("pinned-past", 2, Some("09:00"), 60);
    pinned["pinned"] = json!(true);
    let weeks = [
        (
            THIS_WEEK,
            vec![
                session("wed", 2, Some("14:00"), 60),
                session("thu", 3, Some("14:00"), 30),
                pinned,
            ],
        ),
        (OLDER_WEEK, vec![session("old", 4, Some("10:00"), 60)]),
    ];
    assert_eq!(held(&weeks, NEXT_WEEK, Some(NOW)), 0);
}

#[test]
fn an_earlier_week_session_with_no_time_or_ticked_done_holds_nothing() {
    // A waiting session has no time to hold; a ticked-done one is done time, counted by
    // done_minutes_by_id, not as planned.
    let mut done = session("done", 4, Some("14:00"), 60);
    done["completed"] = json!(true);
    let weeks = [(THIS_WEEK, vec![session("waiting", 4, None, 60), done])];
    assert_eq!(held(&weeks, NEXT_WEEK, Some(NOW)), 0);
}

#[test]
fn without_a_clock_an_earlier_week_holds_nothing_as_before() {
    let weeks = [(THIS_WEEK, vec![session("fri", 4, Some("14:00"), 60)])];
    assert_eq!(held(&weeks, NEXT_WEEK, None), 0);
}

#[test]
fn the_open_week_and_later_ones_count_every_open_session_as_before() {
    // Next week's passed-looking Monday session and the week after's waiting one: 30 + 20, whatever the
    // clock says; only weeks before the open one read it.
    let weeks = [
        (NEXT_WEEK, vec![session("mon", 0, Some("08:00"), 30)]),
        ("2026-11-30", vec![session("waiting", 1, None, 20)]),
    ];
    assert_eq!(held(&weeks, NEXT_WEEK, Some(NOW)), 50);
}

#[test]
fn a_week_on_screen_from_another_day_counts_the_sessions_before_it_the_same_way() {
    // The week on screen starts Wednesday 25 November. Monday 23 at 10:00 is before it but ahead of now
    // (held); Monday 23 at 09:00 is also ahead. Sessions on or after Wednesday count as always.
    // 60 (Mon 10:00) + 30 (Mon 09:00) + 45 (Thu 26) = 135 with the clock; 45 without.
    let weeks: Vec<(String, Vec<Value>)> = vec![(
        NEXT_WEEK.to_string(),
        vec![
            session("mon-a", 0, Some("10:00"), 60),
            session("mon-b", 0, Some("09:00"), 30),
            session("thu", 3, Some("10:00"), 45),
        ],
    )];
    let with_clock =
        planned_minutes_from_day(&weeks, "2026-11-25", Some(parse_moment(NOW).unwrap())).unwrap();
    assert_eq!(with_clock.get("hw"), Some(&135));
    let without = planned_minutes_from_day(&weeks, "2026-11-25", None).unwrap();
    assert_eq!(without.get("hw"), Some(&45));
}

#[test]
fn a_week_on_screen_from_another_day_does_not_hold_a_passed_session_before_it() {
    // Now is Tuesday 24 November 12:00; Monday 23 at 10:00 for 60 ended at 11:00, so it passed.
    let weeks: Vec<(String, Vec<Value>)> = vec![(
        NEXT_WEEK.to_string(),
        vec![session("mon", 0, Some("10:00"), 60)],
    )];
    let now = parse_moment("2026-11-24T12:00").unwrap();
    let planned = planned_minutes_from_day(&weeks, "2026-11-25", Some(now)).unwrap();
    assert_eq!(planned.get("hw"), None);
}
