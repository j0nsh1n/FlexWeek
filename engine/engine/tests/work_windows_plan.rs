//! Where the planner puts homework relative to the student's work windows. Expected values come
//! from the requirement, not from a recorded run.
mod common;

use common::{Dump, by_id, ids, solve_open, solve_with, work_span};
use flexweek_engine::solver::{SolveTrace, TimeBlock, WorkWindow};

fn flex(id: &str, duration_min: i64, days: &[i64]) -> Dump {
    Dump::flex(id, "Essay", duration_min, days)
}

fn solve_in(blocks: &[TimeBlock], windows: &[WorkWindow]) -> SolveTrace {
    solve_with(blocks, None, Some(windows), &common::real_clock())
}

fn has_explanation(trace: &SolveTrace, reason: &str, message: &str) -> bool {
    trace
        .explanations
        .iter()
        .any(|item| item.reason.as_deref() == Some(reason) && item.message == message)
}

#[test]
fn the_planner_places_nothing_outside_work_windows() {
    let windows = [work_span(&[0], "15:00", "17:00", None)];
    let trace = solve_in(&[flex("hw", 60, &[0, 1]).into_block()], &windows);
    let placed = by_id(&trace.placed, "hw");
    assert_eq!(placed.days, vec![0]);
    assert_eq!(placed.start.as_deref(), Some("15:00"));
    assert!(!trace.work_windows_defaulted);
    assert_eq!(trace.work_windows[0].start, "15:00");
}

#[test]
fn the_planner_leaves_work_unplaced_rather_than_using_the_night() {
    let windows = [work_span(&[0], "15:00", "16:00", None)];
    let trace = solve_in(&[flex("hw", 90, &[0]).into_block()], &windows);
    assert_eq!(ids(&trace.unplaced), ["hw"]);
    assert!(by_id(&trace.unplaced, "hw").start.is_none());
    assert!(
        trace
            .failed_constraints
            .iter()
            .any(|item| item == "WORK_WINDOW_MISS")
    );
    assert!(has_explanation(
        &trace,
        "WORK_WINDOW_MISS",
        "That doesn't fit in the times you set aside for work."
    ));
}

#[test]
fn touching_work_windows_are_one_span_for_a_long_session() {
    let windows = [
        work_span(&[0], "16:00", "18:00", None),
        work_span(&[0], "18:00", "20:00", None),
    ];
    let hw = flex("hw", 180, &[0]).energy("medium").into_block();
    let trace = solve_in(std::slice::from_ref(&hw), &windows);
    let placed = by_id(&trace.placed, "hw");
    assert_eq!(placed.start.as_deref(), Some("16:00"));
    assert_eq!(placed.duration_min, 180);
    let one = solve_in(&[hw], &[work_span(&[0], "16:00", "20:00", None)]);
    assert_eq!(by_id(&one.placed, "hw").start.as_deref(), Some("16:00"));
}

#[test]
fn a_gap_between_work_windows_still_refuses_a_session_that_needs_both() {
    let windows = [
        work_span(&[0], "16:00", "18:00", None),
        work_span(&[0], "19:00", "21:00", None),
    ];
    let trace = solve_in(
        &[flex("hw", 180, &[0]).energy("medium").into_block()],
        &windows,
    );
    assert_eq!(ids(&trace.unplaced), ["hw"]);
    assert!(
        trace
            .failed_constraints
            .iter()
            .any(|item| item == "WORK_WINDOW_MISS")
    );
}

#[test]
fn no_windows_leaves_the_whole_day_open() {
    let morning = flex("am", 60, &[0])
        .earliest("Monday 06:30")
        .energy("high")
        .into_block();
    let evening = flex("pm", 60, &[0])
        .earliest("Monday 22:30")
        .energy("low")
        .into_block();
    let trace = solve_open(&[morning, evening]);
    assert_eq!(by_id(&trace.placed, "am").start.as_deref(), Some("06:30"));
    assert_eq!(by_id(&trace.placed, "pm").start.as_deref(), Some("22:30"));
    assert!(trace.work_windows_defaulted);
    assert_eq!(trace.work_windows.len(), 1);
    assert_eq!(trace.work_windows[0].days, vec![0, 1, 2, 3, 4, 5, 6]);
    assert_eq!(trace.work_windows[0].start, "00:00");
    assert_eq!(trace.work_windows[0].end, "24:00");
}

#[test]
fn a_session_too_long_for_the_day_is_a_sleep_guard_miss() {
    let late = flex("late", 120, &[0])
        .earliest("Monday 23:00")
        .into_block();
    let trace = solve_open(&[late]);
    assert_eq!(ids(&trace.unplaced), ["late"]);
    assert!(
        trace
            .failed_constraints
            .iter()
            .any(|item| item == "SLEEP_GUARD")
    );
    assert!(has_explanation(
        &trace,
        "SLEEP_GUARD",
        "It doesn't fit in the day on the days left for it."
    ));
}

#[test]
fn a_hand_placed_night_block_is_left_alone() {
    let night = flex("hw", 60, &[0])
        .start("03:00")
        .pinned()
        .energy("low")
        .into_block();
    let other = flex("other", 30, &[0]).energy("high").into_block();
    let trace = solve_open(&[night, other]);
    let kept = by_id(&trace.placed, "hw");
    assert_eq!(
        (kept.start.as_deref(), kept.days.clone(), kept.pinned),
        (Some("03:00"), vec![0], true)
    );
    assert_eq!(
        by_id(&trace.placed, "other").start.as_deref(),
        Some("06:00")
    );
}

#[test]
fn a_subject_window_does_not_admit_other_homework() {
    let windows = [work_span(&[0], "15:00", "17:00", Some("Math"))];
    let reading = flex("read", 60, &[0]).course("Reading").into_block();
    let trace = solve_in(&[reading], &windows);
    assert_eq!(ids(&trace.unplaced), ["read"]);
}

#[test]
fn a_subject_merges_only_the_windows_that_apply_to_it() {
    let windows = [
        work_span(&[0], "16:00", "18:00", Some("Math")),
        work_span(&[0], "18:00", "20:00", None),
    ];
    let math = flex("math", 180, &[0])
        .course("Math")
        .energy("medium")
        .into_block();
    let trace = solve_in(&[math], &windows);
    assert_eq!(by_id(&trace.placed, "math").start.as_deref(), Some("16:00"));
    let reading = flex("read", 180, &[0])
        .course("Reading")
        .energy("medium")
        .into_block();
    let trace = solve_in(&[reading], &windows);
    assert_eq!(ids(&trace.unplaced), ["read"]);
}
