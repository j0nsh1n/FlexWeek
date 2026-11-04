//! FIX-SPEC v1.3 PR 4: spread pieces on different days, earlier free days, 15-minute buffer.

mod common;

use common::{Dump, by_id, real_clock, work_span};
use flexweek_engine::solver::{
    PlanRules, SOLVE_BUDGET_MS, SolveTrace, TimeBlock, WorkWindow, plan_rules_from_value,
    solve_with_rules,
};
use serde_json::json;

fn flex(
    id: &str,
    title: &str,
    minutes: i64,
    days: &[i64],
    energy: &str,
    latest: Option<&str>,
    assignment: Option<&str>,
) -> TimeBlock {
    let mut block = Dump::flex(id, title, minutes, days).energy(energy);
    if let Some(latest) = latest {
        block = block.latest(latest);
    }
    if let Some(assignment) = assignment {
        block = block.assignment_id(assignment);
    }
    block.into_block()
}

fn locked(id: &str, start: &str, minutes: i64, days: &[i64]) -> TimeBlock {
    Dump::locked(id, id, minutes, days, start).into_block()
}

fn plan(blocks: &[TimeBlock], windows: &[WorkWindow], rules: PlanRules) -> SolveTrace {
    solve_with_rules(
        blocks,
        None,
        Some(windows),
        None,
        None,
        SOLVE_BUDGET_MS,
        &real_clock(),
        rules,
    )
    .expect("plan")
}

fn placed_day(trace: &SolveTrace, id: &str) -> i64 {
    by_id(&trace.placed, id).days[0]
}

fn placed_start(trace: &SolveTrace, id: &str) -> String {
    by_id(&trace.placed, id)
        .start
        .clone()
        .expect("placed start")
}

fn homework_days(trace: &SolveTrace) -> Vec<(String, i64)> {
    let mut rows: Vec<_> = trace
        .placed
        .iter()
        .filter(|block| block.kind == "flexible")
        .map(|block| (block.id.clone(), block.days.first().copied().unwrap_or(-1)))
        .collect();
    rows.sort();
    rows
}

#[test]
fn a_spread_task_of_60_and_30_minutes_lands_on_two_different_days() {
    // Mon–Thu evenings are free. The homework is due Friday and is spread as 60 + 30.
    let windows = [work_span(&[0, 1, 2, 3], "16:00", "21:00", None)];
    let pieces = [
        flex(
            "essay-a",
            "History essay",
            60,
            &[0, 1, 2, 3, 4],
            "low",
            Some("Friday 21:00"),
            Some("essay"),
        ),
        flex(
            "essay-b",
            "History essay",
            30,
            &[0, 1, 2, 3, 4],
            "low",
            Some("Friday 21:00"),
            Some("essay"),
        ),
    ];
    let trace = plan(&pieces, &windows, PlanRules::default());
    let day_a = placed_day(&trace, "essay-a");
    let day_b = placed_day(&trace, "essay-b");
    assert_ne!(
        day_a, day_b,
        "spread pieces {day_a} and {day_b} must land on different days"
    );
}

#[test]
fn three_tasks_due_friday_are_not_all_placed_on_friday() {
    // School fills Mon–Thu until 17:00. Evenings and Friday afternoon are free.
    let school = locked("school", "08:00", 9 * 60, &[0, 1, 2, 3]);
    let windows = [work_span(&[0, 1, 2, 3, 4], "12:00", "21:00", None)];
    let tasks = [
        school,
        flex(
            "math",
            "Math",
            60,
            &[0, 1, 2, 3, 4],
            "medium",
            Some("Friday 21:00"),
            None,
        ),
        flex(
            "science",
            "Science",
            60,
            &[0, 1, 2, 3, 4],
            "medium",
            Some("Friday 21:00"),
            None,
        ),
        flex(
            "history",
            "History",
            60,
            &[0, 1, 2, 3, 4],
            "medium",
            Some("Friday 21:00"),
            None,
        ),
    ];
    let trace = plan(&tasks, &windows, PlanRules::default());
    let days = homework_days(&trace);
    assert_eq!(days.len(), 3, "all three tasks are placed: {days:?}");
    assert!(
        days.iter().any(|(_, day)| *day < 4),
        "at least one task must land before Friday, got {days:?}"
    );
}

#[test]
fn no_homework_starts_the_minute_an_event_ends_with_default_settings() {
    let event = locked("club", "16:00", 90, &[4]);
    let homework = flex("hw", "Math", 60, &[4], "medium", None, None);
    let windows = [work_span(&[4], "16:00", "20:00", None)];
    let rules = plan_rules_from_value(&json!({}));
    let trace = plan(&[event, homework], &windows, rules);
    assert_ne!(placed_start(&trace, "hw"), "17:30");
}

#[test]
fn a_saved_none_buffer_stays_none() {
    assert_eq!(
        plan_rules_from_value(&json!({"buffer_min": 0})).buffer_min,
        0
    );
    assert_eq!(plan_rules_from_value(&json!({})).buffer_min, 15);
}

#[test]
fn a_spread_task_with_room_on_only_one_day_shares_it_and_says_so() {
    let windows = [work_span(&[2], "16:00", "21:00", None)];
    let pieces = [
        flex(
            "essay-a",
            "History essay",
            60,
            &[2],
            "medium",
            Some("Friday 21:00"),
            Some("essay"),
        ),
        flex(
            "essay-b",
            "History essay",
            30,
            &[2],
            "medium",
            Some("Friday 21:00"),
            Some("essay"),
        ),
    ];
    let trace = plan(&pieces, &windows, PlanRules::default());
    assert_eq!(placed_day(&trace, "essay-a"), 2);
    assert_eq!(placed_day(&trace, "essay-b"), 2);
    assert!(
        trace.explanations.iter().any(|item| {
            item.message.contains("Couldn't spread History essay over separate days")
                && item.message.contains("Wednesday")
        }),
        "expected a same-day spread note, got {:?}",
        trace
            .explanations
            .iter()
            .map(|item| &item.message)
            .collect::<Vec<_>>()
    );
}
