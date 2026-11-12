//! A homework session whose time has passed and was not finished is not "handled". Replan all moves
//! it to a time still ahead (or leaves it with no time); Plan keeps it as spec.md says ("keeps the
//! times already planned"); nothing is ever placed before now; a pinned or finished session is never
//! touched; and the count of homework that needs a time says so.
//!
//! The week is Monday 2 November 2026 and now is Thursday 5 November at 19:00, which a plan reads as
//! the limit (day 3, minute 1140). The essay was planned on Tuesday 3 November, 16:00 to 17:00. A
//! session counts as missed only once its end is at or before the real minute on the clock, never
//! because the plan's limit is rounded up to the quarter hour.

use flexweek_engine::desk::planning::{
    clock_point, missed_session_ids, screen_point, solve_request, solve_request_at,
    time_still_needed, without_missed_times,
};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-11-02";
const NOW: (i64, i64) = (3, 19 * 60);

fn not_before() -> Value {
    json!([NOW.0, NOW.1])
}

/// The real clock minute as a point of the week.
fn clock(day: i64, hour: i64, minute: i64) -> Value {
    json!([day, hour * 60 + minute])
}

/// What a plan reads at `clock`: the minute rounded up to the next quarter hour.
fn limit_at(clock: &Value) -> Value {
    let minute = clock[1].as_i64().expect("a minute");
    json!([clock[0], (minute + 14) / 15 * 15])
}

/// A planned session of the essay: `day` (0 is Monday), start "HH:MM", length in minutes.
fn session(id: &str, day: i64, start: &str, minutes: i64) -> Value {
    json!({
        "id": id,
        "title": "History essay",
        "kind": "flexible",
        "assignment_id": "essay-a",
        "duration_min": minutes,
        "days": [day],
        "start": start,
        "priority": 3,
        "energy": "medium",
        "completed": false,
    })
}

fn essay(estimate: i64, focus: i64, due: &str) -> Value {
    json!({
        "essay-a": {
            "id": "essay-a",
            "title": "History essay",
            "due": due,
            "estimate_min": estimate,
            "focus_minutes": focus,
            "unplanned_min": 0,
            "revision": 1,
        }
    })
}

fn request(blocks: Vec<Value>, assignments: &Value, everything: bool) -> (Vec<Value>, Vec<String>) {
    request_at(blocks, assignments, everything, &not_before())
}

fn request_at(
    blocks: Vec<Value>,
    assignments: &Value,
    everything: bool,
    now: &Value,
) -> (Vec<Value>, Vec<String>) {
    let (payload, targets) = solve_request_at(
        &Value::Array(blocks),
        assignments,
        WEEK,
        everything,
        None,
        Some(&limit_at(now)),
        false,
        Some(now),
    )
    .expect("a request");
    let targets = targets
        .iter()
        .map(|id| id.as_str().expect("an id").to_string())
        .collect();
    (payload, targets)
}

fn sent<'a>(payload: &'a [Value], id: &str) -> &'a Value {
    payload
        .iter()
        .find(|block| block["id"] == id)
        .unwrap_or_else(|| panic!("{id} in the request"))
}

fn needed(blocks: &[Value], assignments: &Value, now: Option<&Value>) -> i64 {
    let stripped = without_missed_times(blocks, assignments, now).expect("blocks");
    let map: &Map<String, Value> = assignments.as_object().expect("assignments");
    time_still_needed(map, &stripped, WEEK)
        .expect("a count")
        .iter()
        .map(|item| item["minutes"].as_i64().expect("minutes"))
        .sum()
}

#[test]
fn test_replan_all_moves_a_session_whose_time_passed_to_a_time_still_ahead() {
    // Tuesday 16:00-17:00 ended 26 h before Thursday 19:00. Due Saturday 23:59, so days Thursday to
    // Saturday (3, 4, 5) are open, and none of them starts before Thursday 19:00.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![session("essay", 1, "16:00", 60)], &assignments, true);
    assert_eq!(targets, ["essay"]);
    let essay = sent(&payload, "essay");
    assert_eq!(essay["kind"], "flexible", "sent to the solver, not held");
    assert!(essay.get("start").is_none(), "its old time is not kept");
    assert_eq!(essay["days"], json!([3, 4, 5]));
    assert_eq!(essay["earliest"], "Thursday 19:00");
    assert_eq!(essay["duration_min"], 60);
}

#[test]
fn test_plan_keeps_the_time_of_a_session_that_passed() {
    // spec.md: "Plan my homework" places only homework that has no time yet and keeps the times
    // already planned. The session has a time (a passed one), so Plan holds it where it is.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![session("essay", 1, "16:00", 60)], &assignments, false);
    assert!(targets.is_empty());
    let essay = sent(&payload, "essay");
    assert_eq!(essay["kind"], "locked");
    assert_eq!(essay["start"], "16:00");
}

#[test]
fn test_replan_all_still_moves_a_session_that_has_not_begun() {
    // Friday 16:00 is ahead of Thursday 19:00: Replan all offers every open day again, as before.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![session("essay", 4, "16:00", 60)], &assignments, true);
    assert_eq!(targets, ["essay"]);
    assert!(sent(&payload, "essay").get("start").is_none());
}

#[test]
fn test_replan_all_keeps_a_session_that_is_on_now() {
    // Thursday 18:30-19:30 has begun and not ended at 19:00: it is happening, not missed.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![session("essay", 3, "18:30", 60)], &assignments, true);
    assert!(targets.is_empty());
    assert_eq!(sent(&payload, "essay")["kind"], "locked");
    assert_eq!(
        needed(
            &[session("essay", 3, "18:30", 60)],
            &assignments,
            Some(&not_before())
        ),
        0
    );
}

#[test]
fn test_a_session_that_ends_exactly_now_has_passed() {
    // Thursday 18:00-19:00 ends at 19:00, the limit: over. One minute longer and it is still on.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (_, over) = request(vec![session("essay", 3, "18:00", 60)], &assignments, true);
    assert_eq!(over, ["essay"]);
    let (_, on) = request(vec![session("essay", 3, "18:00", 75)], &assignments, true);
    assert!(on.is_empty());
}

#[test]
fn test_replan_all_never_touches_a_pinned_session_that_passed() {
    let mut pinned = session("essay", 1, "16:00", 60);
    pinned["pinned"] = json!(true);
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![pinned.clone()], &assignments, true);
    assert!(targets.is_empty());
    assert_eq!(sent(&payload, "essay")["kind"], "locked");
    assert_eq!(sent(&payload, "essay")["start"], "16:00");
    assert_eq!(needed(&[pinned], &assignments, Some(&not_before())), 0);
}

#[test]
fn test_replan_all_never_touches_a_finished_session_in_the_past() {
    let mut done = session("essay", 1, "16:00", 60);
    done["completed"] = json!(true);
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let (payload, targets) = request(vec![done.clone()], &assignments, true);
    assert!(targets.is_empty());
    assert_eq!(sent(&payload, "essay"), &done, "passed along unchanged");
    assert_eq!(needed(&[done], &assignments, Some(&not_before())), 0);
}

#[test]
fn test_a_session_partly_done_by_the_timer_is_replanned_for_what_is_left() {
    // 60 min estimated, 15 min of focus logged: 45 min are still needed, so the 60-minute session
    // that passed comes back as 45.
    let assignments = essay(60, 15, "2026-11-07T23:59");
    let missed = session("essay", 1, "16:00", 60);
    let (payload, targets) = request(vec![missed.clone()], &assignments, true);
    assert_eq!(targets, ["essay"]);
    assert_eq!(sent(&payload, "essay")["duration_min"], 45);
    assert_eq!(needed(&[missed], &assignments, Some(&not_before())), 45);
}

#[test]
fn test_other_sessions_of_the_homework_count_against_what_is_left() {
    // 120 estimated, 30 of focus, a Friday session of 60 already holds part of what is left: the
    // missed one needs 120 - 30 - 60 = 30 min.
    let assignments = essay(120, 30, "2026-11-07T23:59");
    let blocks = vec![session("a", 1, "16:00", 60), session("b", 4, "16:00", 60)];
    let (payload, targets) = request(blocks, &assignments, true);
    assert!(targets.contains(&"a".to_string()));
    assert_eq!(sent(&payload, "a")["duration_min"], 30);
}

#[test]
fn test_a_session_the_timer_already_covered_stays_where_it_was() {
    // All 60 min of the homework are logged as focus: nothing is left to plan, so the missed session
    // is not moved and the homework does not ask for a time. (Focus never completes anything.)
    let assignments = essay(60, 60, "2026-11-07T23:59");
    let missed = session("essay", 1, "16:00", 60);
    let (payload, targets) = request(vec![missed.clone()], &assignments, true);
    assert!(targets.is_empty());
    assert_eq!(sent(&payload, "essay")["kind"], "locked");
    assert_eq!(needed(&[missed], &assignments, Some(&not_before())), 0);
}

#[test]
fn test_every_session_sent_to_the_solver_starts_no_earlier_than_now() {
    // A missed session, and one planned ahead: both are sent with the day limit and the earliest
    // time, so the solver cannot place either before Thursday 19:00.
    let assignments = essay(120, 0, "2026-11-07T23:59");
    let blocks = vec![session("a", 1, "16:00", 60), session("b", 4, "16:00", 60)];
    let (payload, targets) = request(blocks, &assignments, true);
    assert_eq!(targets.len(), 2);
    for id in ["a", "b"] {
        let block = sent(&payload, id);
        assert_eq!(block["earliest"], "Thursday 19:00");
        assert!(
            block["days"]
                .as_array()
                .expect("days")
                .iter()
                .all(|day| day.as_i64().expect("a day") >= NOW.0)
        );
    }
}

#[test]
fn test_the_count_reads_a_missed_session_as_time_that_needs_a_time() {
    // Before: the session had a start, so the homework had "a time" and the count was 0, and the
    // status said "Everything has a time". Now the missed session is 60 min that need a time.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let missed = vec![session("essay", 1, "16:00", 60)];
    assert_eq!(needed(&missed, &assignments, Some(&not_before())), 60);
    let ahead = vec![session("essay", 4, "16:00", 60)];
    assert_eq!(needed(&ahead, &assignments, Some(&not_before())), 0);
}

#[test]
fn test_the_count_is_unchanged_with_no_clock() {
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let missed = vec![session("essay", 1, "16:00", 60)];
    assert_eq!(needed(&missed, &assignments, None), 0);
    let (_, targets) = solve_request(
        &Value::Array(missed),
        &assignments,
        WEEK,
        true,
        None,
        Some(&not_before()),
        false,
    )
    .expect("a request");
    assert!(
        targets.is_empty(),
        "without a clock nothing has passed: Replan all keeps the session that has begun"
    );
}

#[test]
fn test_the_clock_is_a_point_of_this_week_only() {
    // Thursday 5 November 18:50 of the week of Monday 2 November is day 3, minute 1130, not rounded.
    assert_eq!(
        clock_point(WEEK, "2026-11-05", 18, 50).unwrap(),
        Some((3, 1130))
    );
    assert_eq!(clock_point(WEEK, "2026-11-02", 0, 0).unwrap(), Some((0, 0)));
    assert_eq!(
        clock_point(WEEK, "2026-11-08", 23, 59).unwrap(),
        Some((6, 1439))
    );
    assert_eq!(
        clock_point(WEEK, "2026-11-01", 23, 59).unwrap(),
        None,
        "the week is ahead"
    );
    assert_eq!(
        clock_point(WEEK, "2026-11-09", 0, 0).unwrap(),
        None,
        "the week is over"
    );
}

#[test]
fn test_a_screen_reads_a_week_that_is_over_at_its_end() {
    // A screen showing an earlier week must still call its unfinished sessions missed, so it reads
    // that week at its end (day 7, minute 0). This week reads like the clock; a week ahead reads none.
    assert_eq!(
        screen_point(WEEK, "2026-11-05", 18, 50).unwrap(),
        Some((3, 1130))
    );
    assert_eq!(
        screen_point(WEEK, "2026-11-09", 0, 0).unwrap(),
        Some((7, 0))
    );
    assert_eq!(
        screen_point(WEEK, "2026-12-01", 9, 0).unwrap(),
        Some((7, 0))
    );
    assert_eq!(screen_point(WEEK, "2026-11-01", 23, 59).unwrap(), None);
    // Read at the week's end, the essay's Tuesday session is missed.
    // Two hours of essay, both sessions over by the week's end and neither done.
    let open = essay(120, 0, "2026-11-08T23:59");
    let blocks = [session("a", 1, "16:00", 60), session("b", 6, "22:00", 60)];
    assert_eq!(
        missed_session_ids(&blocks, &open, Some(&json!([7, 0]))).expect("ids"),
        [json!("a"), json!("b")]
    );
}

#[test]
fn test_a_session_ending_inside_the_current_quarter_hour_is_still_on() {
    // Thursday 18:00-19:00 at 18:50. The plan's limit rounds up to 19:00, but the clock has not
    // reached the end: the student is 50 minutes in. 18:44 is the control, and 19:00 is when it ends.
    let assignments = essay(60, 0, "2026-11-07T23:59");
    let on = vec![session("essay", 3, "18:00", 60)];
    for minute in [44, 50, 59] {
        let at = clock(3, 18, minute);
        let (payload, targets) = request_at(on.clone(), &assignments, true, &at);
        assert!(targets.is_empty(), "on at 18:{minute}");
        assert_eq!(sent(&payload, "essay")["kind"], "locked");
        assert_eq!(needed(&on, &assignments, Some(&at)), 0);
        assert!(
            missed_session_ids(&on, &assignments, Some(&at))
                .unwrap()
                .is_empty()
        );
    }
    let at = clock(3, 19, 0);
    let (_, over) = request_at(on.clone(), &assignments, true, &at);
    assert_eq!(over, ["essay"], "over at 19:00");
    assert_eq!(needed(&on, &assignments, Some(&at)), 60);
}

#[test]
fn test_a_session_that_ended_in_the_quarter_hour_before_the_clock_has_passed() {
    // Thursday 18:00-18:50 at 18:52, a plan limit of 19:00: it ended two minutes ago. It is missed
    // although its end is later than the quarter hour before the limit (18:45). At 18:49 it is on.
    let assignments = essay(50, 0, "2026-11-07T23:59");
    let blocks = vec![session("essay", 3, "18:00", 50)];
    let (_, moved) = request_at(blocks.clone(), &assignments, true, &clock(3, 18, 52));
    assert_eq!(moved, ["essay"]);
    let (_, on) = request_at(blocks, &assignments, true, &clock(3, 18, 49));
    assert!(on.is_empty());
}

#[test]
fn test_a_missed_session_never_comes_back_longer_than_itself() {
    // 180 estimated, nothing else this week (the 120 min that sit next week are in another week's
    // blocks, so this one does not see them): 180 are left, but the missed hour comes back as 60.
    let assignments = essay(180, 0, "2026-11-07T23:59");
    let blocks = vec![session("essay", 1, "16:00", 60)];
    let (payload, targets) = request(blocks.clone(), &assignments, true);
    assert_eq!(targets, ["essay"]);
    assert_eq!(sent(&payload, "essay")["duration_min"], 60);
    assert_eq!(needed(&blocks, &assignments, Some(&not_before())), 60);
}

#[test]
fn test_focus_time_is_taken_off_once_with_two_missed_sessions() {
    // 120 estimated and 60 of focus: 60 min are left, and two hours (Tuesday, Wednesday) have passed.
    // The earlier one takes all 60; the later one has nothing left to do and stays as it is.
    let assignments = essay(120, 60, "2026-11-07T23:59");
    let blocks = vec![session("a", 1, "16:00", 60), session("b", 2, "16:00", 60)];
    let (payload, targets) = request(blocks.clone(), &assignments, true);
    assert_eq!(targets, ["a"]);
    assert_eq!(sent(&payload, "a")["duration_min"], 60);
    assert_eq!(sent(&payload, "b")["kind"], "locked");
    assert_eq!(needed(&blocks, &assignments, Some(&not_before())), 60);
}

#[test]
fn test_two_missed_sessions_share_the_minutes_left_in_time_order() {
    // 120 estimated and 30 of focus: 90 min are left. Tuesday takes 60, Wednesday the other 30.
    let assignments = essay(120, 30, "2026-11-07T23:59");
    let blocks = vec![session("b", 2, "16:00", 60), session("a", 1, "16:00", 60)];
    let (payload, targets) = request(blocks.clone(), &assignments, true);
    assert_eq!(targets.len(), 2);
    assert_eq!(sent(&payload, "a")["duration_min"], 60);
    assert_eq!(sent(&payload, "b")["duration_min"], 30);
    assert_eq!(needed(&blocks, &assignments, Some(&not_before())), 90);
}

#[test]
fn test_one_missed_session_with_focus_comes_back_for_what_is_left() {
    // The control of the two above: 60 estimated, 30 of focus, one missed hour: it comes back as 30.
    let assignments = essay(60, 30, "2026-11-07T23:59");
    let blocks = vec![session("essay", 1, "16:00", 60)];
    let (payload, _) = request(blocks.clone(), &assignments, true);
    assert_eq!(sent(&payload, "essay")["duration_min"], 30);
    assert_eq!(needed(&blocks, &assignments, Some(&not_before())), 30);
}

#[test]
fn test_a_screen_calls_a_session_missed_when_a_plan_would_move_it_or_it_is_pinned() {
    let now = not_before();
    let open = essay(60, 0, "2026-11-07T23:59");
    let ids = |blocks: &[Value], assignments: &Value| {
        missed_session_ids(blocks, assignments, Some(&now)).expect("ids")
    };
    // Unfinished and passed: missed.
    assert_eq!(ids(&[session("a", 1, "16:00", 60)], &open), [json!("a")]);
    // Still ahead, or finished: not.
    assert!(ids(&[session("a", 4, "16:00", 60)], &open).is_empty());
    let mut done = session("a", 1, "16:00", 60);
    done["completed"] = json!(true);
    assert!(ids(&[done], &open).is_empty());
    // Covered by its homework's focus time: nothing is needed, so it is not missed.
    assert!(
        ids(
            &[session("a", 1, "16:00", 60)],
            &essay(60, 60, "2026-11-07T23:59")
        )
        .is_empty()
    );
    // Pinned: no plan moves it, and it is still missed on screen.
    let mut pinned = session("a", 1, "16:00", 60);
    pinned["pinned"] = json!(true);
    assert_eq!(ids(&[pinned.clone()], &open), [json!("a")]);
    let mut finished = essay(60, 0, "2026-11-07T23:59");
    finished["essay-a"]["completed"] = json!(true);
    assert!(ids(&[pinned], &finished).is_empty());
    // No clock: none.
    assert!(
        missed_session_ids(&[session("a", 1, "16:00", 60)], &open, None)
            .unwrap()
            .is_empty()
    );
}

#[test]
fn test_a_session_of_finished_homework_is_not_moved() {
    // The homework is finished, though its Tuesday session was never ticked: nothing is left to plan.
    let mut assignments = essay(60, 0, "2026-11-07T23:59");
    assignments["essay-a"]["completed"] = json!(true);
    let blocks = vec![session("essay", 1, "16:00", 60)];
    let (payload, targets) = request(blocks.clone(), &assignments, true);
    assert!(targets.is_empty());
    assert_eq!(sent(&payload, "essay")["kind"], "locked");
    assert_eq!(needed(&blocks, &assignments, Some(&not_before())), 0);
}
