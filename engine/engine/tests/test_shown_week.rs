//! A week on screen that starts on another day than Monday covers two stored (Monday) weeks. The
//! server shows it as one week and splits a saved one back. Nothing may be lost or doubled across the
//! seam. Dates are read off the 2026 calendar: Wednesday 11 November starts the shown week, so Monday
//! 9 November's stored week gives its Wednesday to Sunday (days 2 to 6) and Monday 16 November's gives
//! its Monday and Tuesday (days 0 and 1).

use flexweek_engine::shown::{compose_shown_week, shown_parts, split_shown_week};
use serde_json::{Value, json};

const WED: &str = "2026-11-11";
const FIRST: &str = "2026-11-09";
const SECOND: &str = "2026-11-16";

fn fixed(id: &str, start: &str, days: &[i64]) -> Value {
    json!({"id": id, "title": id, "kind": "locked", "duration_min": 60, "days": days, "start": start})
}

fn waiting(id: &str, days: &[i64]) -> Value {
    json!({"id": id, "title": id, "kind": "flexible", "duration_min": 60, "days": days,
           "assignment_id": "hw1"})
}

fn by_id<'a>(blocks: &'a [Value], id: &str) -> Option<&'a Value> {
    blocks.iter().find(|block| block["id"] == id)
}

fn days(block: &Value) -> Vec<i64> {
    block["days"]
        .as_array()
        .unwrap()
        .iter()
        .map(|day| day.as_i64().unwrap())
        .collect()
}

/// Every (stored week, day) a block with this title happens or may happen on.
fn occurrences(first: &[Value], second: &[Value], title: &str) -> Vec<(String, i64)> {
    let mut seen = Vec::new();
    for (week, blocks) in [(FIRST, first), (SECOND, second)] {
        for block in blocks.iter().filter(|block| block["title"] == title) {
            for day in days(block) {
                seen.push((week.to_string(), day));
            }
        }
    }
    seen.sort();
    seen
}

#[test]
fn a_wednesday_week_covers_its_monday_week_and_the_next() {
    let parts = shown_parts(WED).unwrap();
    assert_eq!(parts, Some((FIRST.to_string(), SECOND.to_string(), 2)));
    // Sunday 8 November: the stored week of Monday 2 November gives its Sunday, the next its Monday to
    // Saturday.
    assert_eq!(
        shown_parts("2026-11-08").unwrap(),
        Some(("2026-11-02".to_string(), "2026-11-09".to_string(), 6))
    );
    // A Monday is the stored week itself.
    assert_eq!(shown_parts(FIRST).unwrap(), None);
}

#[test]
fn the_shown_days_come_from_both_stored_weeks_in_date_order() {
    let first = vec![
        fixed("tue10", "09:00", &[1]),
        fixed("thu12", "09:00", &[3]),
        fixed("sun15", "09:00", &[6]),
    ];
    let second = vec![
        fixed("mon16", "09:00", &[0]),
        fixed("tue17", "09:00", &[1]),
        fixed("wed18", "09:00", &[2]),
    ];
    let shown = compose_shown_week(WED, &first, &second).unwrap();
    // Tuesday 10 is the week before's, Wednesday 18 the week after's.
    assert!(by_id(&shown, "tue10").is_none());
    assert!(by_id(&shown, "wed18").is_none());
    assert_eq!(days(by_id(&shown, "thu12").unwrap()), vec![1]);
    assert_eq!(days(by_id(&shown, "sun15").unwrap()), vec![4]);
    assert_eq!(days(by_id(&shown, "mon16").unwrap()), vec![5]);
    assert_eq!(days(by_id(&shown, "tue17").unwrap()), vec![6]);
}

#[test]
fn a_new_block_on_thursday_is_stored_in_its_monday_week_and_one_on_monday_in_the_next() {
    let shown = vec![fixed("thu", "10:00", &[1]), fixed("mon", "10:00", &[5])];
    let (first, second) = split_shown_week(WED, &shown, &[], &[]).unwrap();
    assert_eq!(first, vec![fixed("thu", "10:00", &[3])]);
    assert_eq!(second, vec![fixed("mon", "10:00", &[0])]);
}

#[test]
fn a_repeat_with_the_same_times_in_both_weeks_shows_once_and_saves_back_unchanged() {
    // Gym on Monday, Wednesday and Friday in both weeks: Wednesday 11 and Friday 13 from the first,
    // Monday 16 from the second.
    let first = vec![
        fixed("gym", "17:00", &[0, 2, 4]),
        fixed("other", "08:00", &[1]),
    ];
    let second = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let shown = compose_shown_week(WED, &first, &second).unwrap();
    assert_eq!(shown.len(), 1);
    assert_eq!(days(by_id(&shown, "gym").unwrap()), vec![0, 2, 5]);
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    assert_eq!(first_back, first);
    assert_eq!(second_back, second);
}

#[test]
fn deleting_a_shown_repeat_keeps_its_days_in_the_weeks_before_and_after() {
    let first = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let second = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let (first_back, second_back) = split_shown_week(WED, &[], &first, &second).unwrap();
    // Monday 9 belongs to the week before, Wednesday 18 and Friday 20 to the week after.
    assert_eq!(first_back, vec![fixed("gym", "17:00", &[0])]);
    assert_eq!(second_back, vec![fixed("gym", "17:00", &[2, 4])]);
}

#[test]
fn a_changed_time_on_the_shown_days_leaves_the_other_days_at_the_old_time() {
    let first = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let second = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let mut shown = compose_shown_week(WED, &first, &second).unwrap();
    shown[0]["start"] = json!("18:00");
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    let at = |blocks: &[Value], start: &str| -> Vec<i64> {
        blocks
            .iter()
            .filter(|block| block["start"] == start)
            .flat_map(days)
            .collect()
    };
    assert_eq!(at(&first_back, "17:00"), vec![0]);
    assert_eq!(at(&first_back, "18:00"), vec![2, 4]);
    assert_eq!(at(&second_back, "17:00"), vec![2, 4]);
    assert_eq!(at(&second_back, "18:00"), vec![0]);
    // The old block keeps its id on the days it still has; shown again, the moved days are one block.
    assert_eq!(days(by_id(&first_back, "gym").unwrap()), vec![0]);
    let again = compose_shown_week(WED, &first_back, &second_back).unwrap();
    assert_eq!(again.len(), 1);
    assert_eq!(again[0]["start"], "18:00");
    assert_eq!(days(&again[0]), vec![0, 2, 5]);
    // Saved again unchanged, nothing moves.
    let (first_twice, second_twice) =
        split_shown_week(WED, &again, &first_back, &second_back).unwrap();
    assert_eq!(first_twice, first_back);
    assert_eq!(second_twice, second_back);
}

#[test]
fn a_session_the_planner_places_after_the_seam_moves_weeks_and_leaves_no_copy_waiting() {
    // A session with no time yet may go on any day of its stored week (the days it may go on). Shown
    // from Wednesday it may go on Wednesday 11 to Sunday 15. Placed on Monday 16 it happens once, there.
    let first = vec![waiting("s1", &[0, 1, 2, 3, 4, 5, 6])];
    let shown = compose_shown_week(WED, &first, &[]).unwrap();
    assert_eq!(days(by_id(&shown, "s1").unwrap()), vec![0, 1, 2, 3, 4]);
    let mut placed = shown.clone();
    placed[0]["days"] = json!([5]);
    placed[0]["start"] = json!("16:00");
    let (first_back, second_back) = split_shown_week(WED, &placed, &first, &[]).unwrap();
    assert!(by_id(&first_back, "s1").is_none());
    let moved = by_id(&second_back, "s1").unwrap();
    assert_eq!(days(moved), vec![0]);
    assert_eq!(moved["start"], "16:00");
    assert_eq!(
        occurrences(&first_back, &second_back, "s1"),
        vec![(SECOND.to_string(), 0)]
    );
}

#[test]
fn a_session_placed_before_the_seam_drops_the_days_it_could_have_gone_on() {
    let first = vec![waiting("s1", &[0, 1, 2, 3, 4, 5, 6])];
    let mut placed = compose_shown_week(WED, &first, &[]).unwrap();
    placed[0]["days"] = json!([1]);
    placed[0]["start"] = json!("16:00");
    let (first_back, second_back) = split_shown_week(WED, &placed, &first, &[]).unwrap();
    // Thursday 12 only: not also Monday 9 and Tuesday 10 again with no time.
    assert_eq!(
        occurrences(&first_back, &second_back, "s1"),
        vec![(FIRST.to_string(), 3)]
    );
    assert_eq!(by_id(&first_back, "s1").unwrap()["start"], "16:00");
}

#[test]
fn a_session_still_waiting_keeps_the_days_the_shown_week_cannot_see() {
    let first = vec![waiting("s1", &[0, 1, 2, 3, 4, 5, 6])];
    let shown = compose_shown_week(WED, &first, &[]).unwrap();
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &[]).unwrap();
    assert_eq!(first_back, first);
    assert!(second_back.is_empty());
    // Narrowed on screen to Thursday and Friday, it keeps Monday and Tuesday 9 and 10 as well.
    let mut narrowed = shown.clone();
    narrowed[0]["days"] = json!([1, 2]);
    let (first_back, _) = split_shown_week(WED, &narrowed, &first, &[]).unwrap();
    assert_eq!(days(by_id(&first_back, "s1").unwrap()), vec![0, 1, 3, 4]);
    // Deleted on screen, it is gone from every day.
    let (first_back, second_back) = split_shown_week(WED, &[], &first, &[]).unwrap();
    assert!(first_back.is_empty() && second_back.is_empty());
}

#[test]
fn a_new_waiting_session_that_runs_over_the_seam_waits_in_one_week_only() {
    let shown = vec![waiting("s1", &[0, 1, 2, 3, 4, 5, 6])];
    let (first_back, second_back) = split_shown_week(WED, &shown, &[], &[]).unwrap();
    assert_eq!(days(by_id(&first_back, "s1").unwrap()), vec![2, 3, 4, 5, 6]);
    assert!(by_id(&second_back, "s1").is_none());
    // Only after the seam: it waits in the second week.
    let later = vec![waiting("s2", &[5, 6])];
    let (first_back, second_back) = split_shown_week(WED, &later, &[], &[]).unwrap();
    assert!(first_back.is_empty());
    assert_eq!(days(by_id(&second_back, "s2").unwrap()), vec![0, 1]);
}

#[test]
fn a_missed_day_on_monday_after_the_seam_is_kept_in_the_second_week_only() {
    let first = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let second = vec![fixed("gym", "17:00", &[0, 2, 4])];
    let mut shown = compose_shown_week(WED, &first, &second).unwrap();
    shown[0]["missed_days"] = json!([5]);
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    assert_eq!(first_back, first);
    assert_eq!(
        by_id(&second_back, "gym").unwrap()["missed_days"],
        json!([0])
    );
    assert_eq!(days(by_id(&second_back, "gym").unwrap()), vec![0, 2, 4]);
    // A missed day the shown week cannot see stays as it was.
    let first = vec![
        json!({"id": "gym", "title": "gym", "kind": "locked", "duration_min": 60,
                            "days": [0, 2, 4], "start": "17:00", "missed_days": [0]}),
    ];
    let shown = compose_shown_week(WED, &first, &[]).unwrap();
    assert!(shown[0].get("missed_days").is_none());
    let (first_back, _) = split_shown_week(WED, &shown, &first, &[]).unwrap();
    assert_eq!(first_back, first);
}

#[test]
fn the_same_id_with_other_times_in_each_week_shows_as_two_blocks_and_saves_back_to_each() {
    let first = vec![fixed("club", "15:00", &[3])];
    let second = vec![fixed("club", "16:00", &[0])];
    let shown = compose_shown_week(WED, &first, &second).unwrap();
    assert_eq!(shown.len(), 2);
    assert_eq!(days(by_id(&shown, "club").unwrap()), vec![1]);
    let other = shown.iter().find(|block| block["id"] != "club").unwrap();
    assert_eq!(other["start"], "16:00");
    assert_eq!(days(other), vec![5]);
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &second).unwrap();
    assert_eq!(first_back, first);
    assert_eq!(second_back, second);
    // The second week's copy, moved on screen, keeps its own id in its own week.
    let mut moved = shown.clone();
    for block in &mut moved {
        if block["id"] != "club" {
            block["start"] = json!("17:00");
        }
    }
    let (first_back, second_back) = split_shown_week(WED, &moved, &first, &second).unwrap();
    assert_eq!(first_back, first);
    assert_eq!(second_back, vec![fixed("club", "17:00", &[0])]);
}

#[test]
fn a_block_dragged_over_the_seam_moves_weeks_once() {
    let first = vec![fixed("read", "10:00", &[3])];
    let mut shown = compose_shown_week(WED, &first, &[]).unwrap();
    shown[0]["days"] = json!([6]);
    let (first_back, second_back) = split_shown_week(WED, &shown, &first, &[]).unwrap();
    assert!(first_back.is_empty());
    assert_eq!(second_back, vec![fixed("read", "10:00", &[1])]);
}

#[test]
fn a_sunday_week_takes_one_day_from_the_first_week_and_six_from_the_second() {
    // Sunday 8 November to Saturday 14 November.
    let first = vec![fixed("sat7", "09:00", &[5]), fixed("sun8", "09:00", &[6])];
    let second = vec![
        fixed("mon9", "09:00", &[0]),
        fixed("sat14", "09:00", &[5]),
        fixed("sun15", "09:00", &[6]),
    ];
    let shown = compose_shown_week("2026-11-08", &first, &second).unwrap();
    assert!(by_id(&shown, "sat7").is_none());
    assert!(by_id(&shown, "sun15").is_none());
    assert_eq!(days(by_id(&shown, "sun8").unwrap()), vec![0]);
    assert_eq!(days(by_id(&shown, "mon9").unwrap()), vec![1]);
    assert_eq!(days(by_id(&shown, "sat14").unwrap()), vec![6]);
    let (first_back, second_back) =
        split_shown_week("2026-11-08", &shown, &first, &second).unwrap();
    assert_eq!(first_back, first);
    assert_eq!(second_back, second);
}

#[test]
fn a_week_over_a_month_end_and_one_over_a_year_end_map_their_dates() {
    // Wednesday 25 November to Tuesday 1 December: Monday 30 November is the second week's Monday.
    assert_eq!(
        shown_parts("2026-11-25").unwrap(),
        Some(("2026-11-23".to_string(), "2026-11-30".to_string(), 2))
    );
    let shown = vec![
        fixed("tue1dec", "09:00", &[6]),
        fixed("sun29", "09:00", &[4]),
    ];
    let (first, second) = split_shown_week("2026-11-25", &shown, &[], &[]).unwrap();
    assert_eq!(first, vec![fixed("sun29", "09:00", &[6])]);
    assert_eq!(second, vec![fixed("tue1dec", "09:00", &[1])]);
    // Wednesday 30 December 2026 to Tuesday 5 January 2027: Monday 4 January is shown day 5.
    assert_eq!(
        shown_parts("2026-12-30").unwrap(),
        Some(("2026-12-28".to_string(), "2027-01-04".to_string(), 2))
    );
    let second = vec![fixed("jan4", "09:00", &[0])];
    let first = vec![fixed("dec31", "09:00", &[3])];
    let shown = compose_shown_week("2026-12-30", &first, &second).unwrap();
    assert_eq!(days(by_id(&shown, "jan4").unwrap()), vec![5]);
    assert_eq!(days(by_id(&shown, "dec31").unwrap()), vec![1]);
}

#[test]
fn every_start_day_saves_an_unchanged_week_back_exactly() {
    let first = vec![
        fixed("a", "08:00", &[0, 1, 2, 3, 4]),
        fixed("b", "12:00", &[5, 6]),
        waiting("w", &[0, 3, 6]),
        json!({"id": "c", "title": "c", "kind": "locked", "duration_min": 30, "days": [2],
               "start": "07:00", "completed": true, "completed_day": 2}),
    ];
    let second = vec![
        fixed("a", "08:00", &[0, 1, 2, 3, 4]),
        fixed("d", "19:00", &[1, 6]),
    ];
    // 9 to 15 November are Monday to Sunday.
    for (start, offset) in [
        ("2026-11-10", 1),
        ("2026-11-11", 2),
        ("2026-11-12", 3),
        ("2026-11-13", 4),
        ("2026-11-14", 5),
        ("2026-11-15", 6),
    ] {
        let parts = shown_parts(start).unwrap().unwrap();
        assert_eq!(parts.2, offset);
        let shown = compose_shown_week(start, &first, &second).unwrap();
        for block in &shown {
            assert!(days(block).iter().all(|day| (0..7).contains(day)));
        }
        let (first_back, second_back) = split_shown_week(start, &shown, &first, &second).unwrap();
        assert_eq!(first_back, first, "start {start}");
        assert_eq!(second_back, second, "start {start}");
    }
}

#[test]
fn a_done_mark_follows_its_day() {
    let first = vec![
        json!({"id": "c", "title": "c", "kind": "locked", "duration_min": 30,
                            "days": [3], "start": "07:00", "completed": true, "completed_day": 3}),
    ];
    let shown = compose_shown_week(WED, &first, &[]).unwrap();
    assert_eq!(shown[0]["completed_day"], 1);
}

#[test]
fn a_change_to_a_repeat_from_a_wednesday_week_on_holds_from_the_next_monday() {
    use flexweek_engine::shown::repeat_changes_from_shown_week;
    let changes = vec![
        json!({"id": "school", "scope": "from", "from_date": WED, "set": {"start": "09:00"}}),
        json!({"id": "sport", "scope": "from", "from_date": "2026-11-02", "stop": true}),
    ];
    let moved = repeat_changes_from_shown_week(&changes, WED).unwrap();
    assert_eq!(moved[0]["from_date"], SECOND);
    assert_eq!(moved[1]["from_date"], "2026-11-02");
    assert_eq!(
        repeat_changes_from_shown_week(&changes, FIRST).unwrap(),
        changes
    );
}

#[test]
fn a_shown_week_names_the_stored_weeks_it_covers() {
    use flexweek_engine::shown::stored_weeks;
    assert_eq!(
        stored_weeks(WED).unwrap(),
        vec![FIRST.to_string(), SECOND.to_string()]
    );
    assert_eq!(stored_weeks(FIRST).unwrap(), vec![FIRST.to_string()]);
}

#[test]
fn homework_minutes_from_a_wednesday_count_the_sessions_on_and_after_it() {
    use flexweek_engine::plan::planned_minutes_from_day;
    let session = |id: &str, day: i64| {
        json!({"id": id, "title": id, "kind": "flexible", "duration_min": 30, "days": [day],
               "start": "16:00", "assignment_id": "hw"})
    };
    let weeks = vec![
        // Tuesday 3 November is before the week on screen; Wednesday 4 is its first day.
        (
            "2026-11-02".to_string(),
            vec![session("tue3", 1), session("wed4", 2)],
        ),
        (
            "2026-11-09".to_string(),
            vec![session("mon9", 0), session("wed11", 2)],
        ),
        ("2026-10-26".to_string(), vec![session("oct", 4)]),
    ];
    assert_eq!(
        planned_minutes_from_day(&weeks, "2026-11-04")
            .unwrap()
            .get("hw"),
        Some(&90)
    );
    assert_eq!(
        planned_minutes_from_day(&weeks, "2026-11-11")
            .unwrap()
            .get("hw"),
        Some(&30)
    );
}

#[test]
fn hidden_weekends_are_saturday_and_sunday_wherever_they_fall() {
    use flexweek_engine::shown::shown_columns;
    // Wednesday 11 to Tuesday 17 November: Saturday 14 and Sunday 15 are days 3 and 4.
    assert_eq!(shown_columns(WED, false).unwrap(), vec![0, 1, 2, 5, 6]);
    assert_eq!(shown_columns(WED, true).unwrap(), vec![0, 1, 2, 3, 4, 5, 6]);
    // Sunday 8 to Saturday 14: Sunday is day 0, Saturday day 6.
    assert_eq!(
        shown_columns("2026-11-08", false).unwrap(),
        vec![1, 2, 3, 4, 5]
    );
    assert_eq!(shown_columns(FIRST, false).unwrap(), vec![0, 1, 2, 3, 4]);
}

#[test]
fn a_shown_week_names_its_days_from_their_dates() {
    use flexweek_engine::shown::day_names;
    assert_eq!(
        day_names(WED, false).unwrap(),
        vec!["Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]
    );
    assert_eq!(day_names("2026-11-08", true).unwrap()[0], "Sunday");
    assert_eq!(day_names(FIRST, false).unwrap()[0], "Mon");
}

#[test]
fn weekday_availability_lands_on_the_days_of_the_shown_week() {
    use flexweek_engine::shown::{
        occupancy_on_shown_week, weekdays_on_shown_week, windows_on_shown_week,
    };
    // From Wednesday 11 November, Monday 16 is day 5 and Saturday 14 day 3.
    assert_eq!(weekdays_on_shown_week(WED, &[0, 5]).unwrap(), vec![3, 5]);
    let occupancy: Vec<u128> = (0..7).map(|weekday| 1u128 << weekday).collect();
    let shown = occupancy_on_shown_week(WED, &occupancy).unwrap();
    assert_eq!(shown[0], 1 << 2);
    assert_eq!(shown[3], 1 << 5);
    assert_eq!(shown[5], 1);
    let windows = vec![json!({"days": [0, 4], "start": "16:00", "end": "18:00"})];
    let moved = windows_on_shown_week(WED, &windows).unwrap();
    assert_eq!(moved[0]["days"], json!([2, 5]));
    assert_eq!(moved[0]["start"], "16:00");
    // A week from Monday keeps the weekdays as they are.
    assert_eq!(
        occupancy_on_shown_week(FIRST, &occupancy).unwrap(),
        occupancy
    );
    assert_eq!(windows_on_shown_week(FIRST, &windows).unwrap(), windows);
    // From Sunday 8 November, Sunday (6) is day 0 and Saturday (5) day 6.
    assert_eq!(
        weekdays_on_shown_week("2026-11-08", &[5, 6]).unwrap(),
        vec![0, 6]
    );
}

#[test]
fn homework_in_a_week_from_wednesday_may_go_on_its_days_through_the_due_date() {
    use flexweek_engine::desk::grid::first_plannable_day;
    use flexweek_engine::desk::planning::session_days;
    // Due Tuesday 17 November, the last day of the week from Wednesday 11: every day of it.
    assert_eq!(
        session_days(WED, &json!("2026-11-17T23:59")).unwrap(),
        vec![0, 1, 2, 3, 4, 5, 6]
    );
    // Due Monday 16: Wednesday 11 to Monday 16, days 0 to 5.
    assert_eq!(
        session_days(WED, &json!("2026-11-16T18:00")).unwrap(),
        vec![0, 1, 2, 3, 4, 5]
    );
    // Thursday 12 is day 1 of that week, not its weekday 3.
    assert_eq!(first_plannable_day(WED, "2026-11-12").unwrap(), 1);
    assert_eq!(first_plannable_day(WED, "2026-11-17").unwrap(), 6);
    assert_eq!(first_plannable_day(FIRST, "2026-11-12").unwrap(), 3);
}

#[test]
fn a_waiting_session_shows_every_day_through_its_due_date_and_is_stored_once() {
    use flexweek_engine::shown::compose_shown_week_due;
    // Due Tuesday 17 November. Waiting in Monday 9's week on Wednesday 11 to Sunday 15, the days it
    // was given there; Monday 16 and Tuesday 17 come back from the due date.
    let dues = json!({"hw1": {"id": "hw1", "due": "2026-11-17T23:59"}});
    let dues = dues.as_object().unwrap();
    let first = vec![waiting("s1", &[2, 3, 4, 5, 6])];
    let shown = compose_shown_week_due(WED, &first, &[], dues).unwrap();
    assert_eq!(
        days(by_id(&shown, "s1").unwrap()),
        vec![0, 1, 2, 3, 4, 5, 6]
    );
    // Saved back as it shows, it stays in its own week on its own days, once.
    let (stored_first, stored_second) = split_shown_week(WED, &shown, &first, &[]).unwrap();
    assert_eq!(stored_first, first);
    assert!(stored_second.is_empty());
    // A session given one day keeps that day; one due before the seam keeps its days.
    let one_day = vec![waiting("s1", &[6])];
    let shown = compose_shown_week_due(WED, &one_day, &[], dues).unwrap();
    assert_eq!(days(by_id(&shown, "s1").unwrap()), vec![4]);
    let early = json!({"hw1": {"due": "2026-11-13T23:59"}});
    let shown = compose_shown_week_due(WED, &first, &[], early.as_object().unwrap()).unwrap();
    assert_eq!(days(by_id(&shown, "s1").unwrap()), vec![0, 1, 2, 3, 4]);
    // From Monday nothing changes.
    let monday = vec![waiting("s1", &[0, 1, 2, 3, 4, 5, 6])];
    assert_eq!(
        compose_shown_week_due(FIRST, &monday, &[], dues).unwrap(),
        monday
    );
}

#[test]
fn school_changed_from_a_wednesday_week_lands_on_its_own_weekdays() {
    use flexweek_engine::repeats::parse_intents;
    use flexweek_engine::shown::{
        apply_repeats_to_shown_week, one_day_note_on_shown_week, this_week_line_on_shown_week,
    };
    // School stands Monday to Friday. From Wednesday 11 it shows on days 0, 1, 2 (Wed, Thu, Fri)
    // and 5, 6 (Mon 16, Tue 17).
    let school = json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
                        "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]});
    let shown = vec![
        json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
                            "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 5, 6]}),
    ];
    // School on Friday stops from this week on.
    let intents = parse_intents(&json!([{"id": "school", "scope": "from", "from_date": WED,
                                         "remove_days": [4]}]))
    .unwrap();
    let (week, standing) =
        apply_repeats_to_shown_week(WED, &shown, std::slice::from_ref(&school), &intents).unwrap();
    assert_eq!(days(by_id(&week, "school").unwrap()), vec![0, 1, 5, 6]);
    assert_eq!(days(by_id(&standing, "school").unwrap()), vec![0, 1, 2, 3]);
    // The week shows School with no Friday: said by its name.
    let line =
        this_week_line_on_shown_week(WED, &week, std::slice::from_ref(&school), false).unwrap();
    assert_eq!(line.as_deref(), Some("This week: no School on Friday."));
    // Moving day 5 (Monday 16) of School is about Monday.
    let note = one_day_note_on_shown_week(WED, &school, 5, true)
        .unwrap()
        .unwrap();
    assert!(note.starts_with("Only this Monday changed."), "{note}");
    // From Monday nothing turns.
    let monday = vec![school.clone()];
    let (same, _) = apply_repeats_to_shown_week(FIRST, &monday, &monday, &[]).unwrap();
    assert_eq!(same, monday);
}

#[test]
fn a_routine_keeps_weekdays_whichever_day_the_week_starts_on() {
    use flexweek_engine::shown::{blocks_by_weekday, routine_on_shown_week};
    // Club on day 5 of the week from Wednesday 11 is Monday 16: the routine keeps Monday.
    let shown = vec![fixed("club", "16:00", &[5, 0])];
    assert_eq!(
        days(&blocks_by_weekday(WED, &shown).unwrap()[0]),
        vec![0, 2]
    );
    // Copied into a week from Wednesday, Monday is day 5 again.
    let routine = json!({"id": "r", "name": "Clubs", "blocks": [
        {"template_id": "t1", "title": "Club", "days": [0, 2], "start": "16:00", "duration_min": 60}]});
    let turned = routine_on_shown_week(WED, &routine).unwrap();
    assert_eq!(turned["blocks"][0]["days"], json!([0, 5]));
    assert_eq!(turned["name"], "Clubs");
    // From Monday both leave the days alone.
    assert_eq!(blocks_by_weekday(FIRST, &shown).unwrap(), shown);
    assert_eq!(routine_on_shown_week(FIRST, &routine).unwrap(), routine);
}
