//! FIX-SPEC v1.3 PR 4: spread pieces on different days, earlier free days, 15-minute buffer.

mod common;

use std::collections::BTreeMap;

use common::{Dump, by_id, real_clock, work_span};
use flexweek_engine::plan::prepare_solve;
use flexweek_engine::solver::{
    DeadlineOverrides, PlanRules, SOLVE_BUDGET_MS, SolveTrace, TimeBlock, WorkWindow,
    block_from_value, plan_rules_from_value, solve_with_rules,
};
use serde_json::{Value, json};

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

fn assignment(id: &str, title: &str, due: &str) -> Value {
    json!({"id": id, "title": title, "due": due, "completed": false, "course": null})
}

/// Real Plan: assignment sessions carry no `latest`; due dates arrive as overrides.
fn plan_assignments(
    school: TimeBlock,
    sessions: &[Value],
    assignments: &BTreeMap<String, Value>,
    week_start: &str,
    windows: &[WorkWindow],
    rules: PlanRules,
) -> SolveTrace {
    let (keep, deadlines, slack) =
        prepare_solve(sessions, week_start, assignments).expect("prepare");
    let mut blocks: Vec<TimeBlock> = keep
        .iter()
        .map(|block| block_from_value(block).expect("session"))
        .collect();
    blocks.push(school);
    let overrides = DeadlineOverrides {
        deadlines: deadlines.into_iter().collect(),
        slack_deadlines: slack.into_iter().collect(),
    };
    solve_with_rules(
        &blocks,
        None,
        Some(windows),
        Some(&overrides),
        None,
        SOLVE_BUDGET_MS,
        &real_clock(),
        rules,
    )
    .expect("plan")
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
fn three_assignment_sessions_due_friday_use_earlier_free_evenings() {
    // School fills Mon–Thu until 17:00. Evenings and Friday afternoon are free.
    // Real homework has no `latest`; Plan supplies Friday 21:00 through overrides.
    const WEEK: &str = "2026-09-14";
    const DUE: &str = "2026-09-18T21:00";
    let school = locked("school", "08:00", 9 * 60, &[0, 1, 2, 3]);
    let windows = [work_span(&[0, 1, 2, 3, 4], "12:00", "21:00", None)];
    let sessions = [
        Dump::flex("math", "Math", 60, &[0, 1, 2, 3, 4])
            .energy("medium")
            .assignment_id("hw-math")
            .into_value(),
        Dump::flex("science", "Science", 60, &[0, 1, 2, 3, 4])
            .energy("medium")
            .assignment_id("hw-science")
            .into_value(),
        Dump::flex("history", "History", 60, &[0, 1, 2, 3, 4])
            .energy("medium")
            .assignment_id("hw-history")
            .into_value(),
    ];
    let mut assignments = BTreeMap::new();
    assignments.insert("hw-math".into(), assignment("hw-math", "Math", DUE));
    assignments.insert(
        "hw-science".into(),
        assignment("hw-science", "Science", DUE),
    );
    assignments.insert(
        "hw-history".into(),
        assignment("hw-history", "History", DUE),
    );
    let trace = plan_assignments(
        school,
        &sessions,
        &assignments,
        WEEK,
        &windows,
        plan_rules_from_value(&json!({})),
    );
    let days = homework_days(&trace);
    assert_eq!(days.len(), 3, "all three sessions are placed: {days:?}");
    assert!(
        days.iter().any(|(_, day)| *day < 4),
        "at least one session must land before Friday, got {days:?}"
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
    const SPEC_REASONS: &[&str] = &[
        "LOCKED_OVERLAP",
        "DEADLINE_MISS",
        "DEADLINE_PASSED",
        "NO_SLOT_LEFT",
        "PRIORITY_PREEMPT",
        "ENERGY_MISMATCH",
        "SLEEP_GUARD",
        "WORK_WINDOW_MISS",
        "NO_STUDY_TIME_TODAY",
        "RESHUFFLE_AFTER_MISS",
    ];
    assert!(
        trace.explanations.iter().all(|item| item
            .reason
            .as_deref()
            .is_none_or(|reason| SPEC_REASONS.contains(&reason))),
        "explanations must use spec reason codes, got {:?}",
        trace
            .explanations
            .iter()
            .map(|item| item.reason.as_deref())
            .collect::<Vec<_>>()
    );
    assert!(
        trace.notices.iter().any(|item| {
            item.kind == "spread_same_day"
                && item.message
                    == "Couldn't spread History essay over separate days, so two parts share Wednesday."
        }),
        "expected a same-day spread notice, got {:?}",
        trace.notices
    );
}
