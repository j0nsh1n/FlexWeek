//! Planner settings. Expected times are counted from the grid, not copied from a run.

mod common;

use common::{Dump, by_id, real_clock, work_span};
use flexweek_engine::plan::occupancy_from_windows;
use flexweek_engine::solver::{
    PlanRules, SOLVE_BUDGET_MS, SolveTrace, TimeBlock, WorkWindow, plan_rules_from_value, solve,
    solve_with_rules,
};
use serde_json::json;

fn flex(id: &str, minutes: i64, days: &[i64], energy: &str, latest: Option<&str>) -> TimeBlock {
    let mut block = Dump::flex(id, id, minutes, days).energy(energy);
    if let Some(latest) = latest {
        block = block.latest(latest);
    }
    block.into_block()
}

fn locked(id: &str, start: &str, minutes: i64, days: &[i64]) -> TimeBlock {
    Dump::locked(id, id, minutes, days, start).into_block()
}

fn plan(
    blocks: &[TimeBlock],
    windows: &[WorkWindow],
    extra: Option<&[u128]>,
    rules: PlanRules,
) -> SolveTrace {
    solve_with_rules(
        blocks,
        extra,
        Some(windows),
        None,
        None,
        SOLVE_BUDGET_MS,
        &real_clock(),
        rules,
    )
    .expect("plan")
}

fn start_of(trace: &SolveTrace, id: &str) -> (i64, String, i64) {
    let block = by_id(&trace.placed, id);
    (
        block.days[0],
        block.start.clone().expect("placed start"),
        block.duration_min,
    )
}

fn expect(day: i64, start: &str, minutes: i64) -> (i64, String, i64) {
    (day, start.to_string(), minutes)
}

fn rules() -> PlanRules {
    PlanRules::default()
}

#[test]
fn missing_keys_are_todays_planner() {
    let parsed = plan_rules_from_value(&json!({}));
    assert_eq!(parsed, PlanRules::default());
    assert_eq!(parsed.buffer_slots(), 0);
    let set = plan_rules_from_value(&json!({
        "weekend_homework_free": 1,
        "buffer_min": 15,
        "urgent_first": 0,
        "split_long_tasks": 1,
        "show_weekends": 0,
    }));
    assert_eq!(
        set,
        PlanRules {
            weekend_homework_free: true,
            buffer_min: 15,
            urgent_first: false,
            split_long_tasks: true,
        }
    );
    assert_eq!(
        plan_rules_from_value(&json!({"buffer_min": 10})).buffer_min,
        0
    );
}

#[test]
fn buffer_opens_a_gap_after_a_locked_class() {
    // Friday 15:00–16:00 is taken. Study is 16:00–20:00. A 60-minute medium task
    // wants the earliest matching start: 16:00, then 16:15, then 16:30.
    let class = locked("class", "15:00", 60, &[4]);
    let homework = flex("hw", 60, &[4], "medium", None);
    let windows = [work_span(&[4], "16:00", "20:00", None)];
    let blocks = [class, homework];
    let at = |buffer: i64| {
        let mut rules = rules();
        rules.buffer_min = buffer;
        let trace = plan(&blocks, &windows, None, rules);
        start_of(&trace, "hw")
    };
    assert_eq!(at(0), expect(4, "16:00", 60));
    assert_eq!(at(15), expect(4, "16:15", 60));
    assert_eq!(at(30), expect(4, "16:30", 60));
    let same = solve(
        &blocks,
        None,
        Some(&windows),
        None,
        None,
        SOLVE_BUDGET_MS,
        &real_clock(),
    )
    .unwrap();
    assert_eq!(start_of(&same, "hw"), expect(4, "16:00", 60));
}

#[test]
fn weekend_free_keeps_homework_on_a_weekday() {
    // Science finishes by Friday 18:00, so 16:00–17:00 is five starts and it is placed first.
    // Math likes a morning. Saturday 10:00 is one; Friday evening is not. With weekends closed,
    // Friday 17:00 is the first hour still open after Science.
    let science = flex("science", 60, &[4], "medium", Some("Friday 18:00"));
    let math = flex("math", 60, &[4, 5], "high", None);
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let blocks = [science, math];
    let open = plan(&blocks, &windows, None, rules());
    assert_eq!(start_of(&open, "science"), expect(4, "16:00", 60));
    assert_eq!(start_of(&open, "math"), expect(5, "10:00", 60));
    let mut closed = rules();
    closed.weekend_homework_free = true;
    let shut = plan(&blocks, &windows, None, closed);
    assert_eq!(start_of(&shut, "science"), expect(4, "16:00", 60));
    assert_eq!(start_of(&shut, "math"), expect(4, "17:00", 60));
}

#[test]
fn urgent_off_lets_the_later_deadline_take_the_first_hour() {
    // Both fit Friday 16:00–18:00 and neither deadline cuts that window.
    // Friday 20:00 is sooner than Sunday 20:00, so it goes first while urgent is on.
    // Off, `a-math` is before `b-science`.
    let plenty = flex("a-math", 60, &[4], "medium", Some("Sunday 20:00"));
    let tight = flex("b-science", 60, &[4], "medium", Some("Friday 20:00"));
    let windows = [work_span(&[4], "16:00", "18:00", None)];
    let blocks = [plenty, tight];
    let on = plan(&blocks, &windows, None, rules());
    assert_eq!(start_of(&on, "b-science"), expect(4, "16:00", 60));
    assert_eq!(start_of(&on, "a-math"), expect(4, "17:00", 60));
    let mut off = rules();
    off.urgent_first = false;
    let swapped = plan(&blocks, &windows, None, off);
    assert_eq!(start_of(&swapped, "a-math"), expect(4, "16:00", 60));
    assert_eq!(start_of(&swapped, "b-science"), expect(4, "17:00", 60));
}

#[test]
fn a_long_task_splits_once_onto_another_day() {
    // 120 minutes of medium work. Friday 16:00 matches that energy; Saturday 10:00 does not.
    // Whole, it stays Friday. Split, the first half takes Friday and the other half Saturday.
    let essay = flex("essay", 120, &[4, 5], "medium", None);
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let whole = plan(std::slice::from_ref(&essay), &windows, None, rules());
    assert_eq!(start_of(&whole, "essay"), expect(4, "16:00", 120));
    assert!(by_id_missing(&whole, "essay~2"));
    let mut split = rules();
    split.split_long_tasks = true;
    let parts = plan(std::slice::from_ref(&essay), &windows, None, split);
    assert_eq!(start_of(&parts, "essay"), expect(4, "16:00", 60));
    assert_eq!(start_of(&parts, "essay~2"), expect(5, "10:00", 60));
}

#[test]
fn an_hour_or_an_off_grid_length_stays_one_block() {
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let mut split = rules();
    split.split_long_tasks = true;
    let hour = flex("hour", 60, &[4, 5], "medium", None);
    let one = plan(std::slice::from_ref(&hour), &windows, None, split);
    assert_eq!(start_of(&one, "hour"), expect(4, "16:00", 60));
    assert!(by_id_missing(&one, "hour~2"));
    let odd = flex("odd", 61, &[4], "medium", None);
    let kept = plan(std::slice::from_ref(&odd), &windows, None, split);
    assert_eq!(start_of(&kept, "odd"), expect(4, "16:00", 61));
    assert!(by_id_missing(&kept, "odd~2"));
}

#[test]
fn study_cutoff_blocks_the_only_hour_that_would_run_past_it() {
    // The only study hour is Friday 21:00–23:00. A 60-minute block at 21:00 ends at 22:00.
    // Cutoff 22:00 leaves that hour. Cutoff 21:00 or 20:00 covers it.
    let homework = flex("hw", 60, &[4], "low", None);
    let windows = [work_span(&[4], "21:00", "23:00", None)];
    let at = |cutoff: &str| {
        let occ = occupancy_from_windows(&[], Some(cutoff)).unwrap();
        plan(
            std::slice::from_ref(&homework),
            &windows,
            Some(&occ),
            rules(),
        )
    };
    assert_eq!(start_of(&at("22:00"), "hw"), expect(4, "21:00", 60));
    assert!(at("21:00").unplaced.iter().any(|block| block.id == "hw"));
    assert!(at("20:00").unplaced.iter().any(|block| block.id == "hw"));
    let open = plan(std::slice::from_ref(&homework), &windows, None, rules());
    assert_eq!(start_of(&open, "hw"), expect(4, "21:00", 60));
}

#[test]
fn show_weekends_is_not_a_planner_rule() {
    // Saturday 10:00–12:00 is the only window. The flag lives on the row and is ignored here.
    let math = flex("math", 60, &[5], "high", None);
    let windows = [work_span(&[5], "10:00", "12:00", None)];
    let trace = plan(std::slice::from_ref(&math), &windows, None, rules());
    assert_eq!(start_of(&trace, "math"), expect(5, "10:00", 60));
}

fn by_id_missing(trace: &SolveTrace, id: &str) -> bool {
    trace.placed.iter().all(|block| block.id != id)
        && trace.unplaced.iter().all(|block| block.id != id)
}
