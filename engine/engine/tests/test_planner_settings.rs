//! Planner settings. Expected times are counted from the grid, not copied from a run.

mod common;

use common::{Dump, by_id, real_clock, work_span};
use flexweek_engine::plan::occupancy_from_windows;
use flexweek_engine::solver::{
    DeadlineOverrides, PlanRules, SOLVE_BUDGET_MS, SolveTrace, TimeBlock, WorkWindow,
    plan_rules_from_value, solve, solve_with_rules,
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

fn rows(trace: &SolveTrace) -> Vec<(String, i64, String, i64)> {
    let mut rows: Vec<_> = trace
        .placed
        .iter()
        .map(|block| {
            (
                block.id.clone(),
                block.days.first().copied().unwrap_or(-1),
                block.start.clone().unwrap_or_default(),
                block.duration_min,
            )
        })
        .collect();
    rows.sort();
    rows
}

fn plan_deadlines(
    blocks: &[TimeBlock],
    windows: &[WorkWindow],
    overrides: &DeadlineOverrides,
    rules: PlanRules,
) -> SolveTrace {
    solve_with_rules(
        blocks,
        None,
        Some(windows),
        Some(overrides),
        None,
        SOLVE_BUDGET_MS,
        &real_clock(),
        rules,
    )
    .expect("plan")
}

fn rules() -> PlanRules {
    PlanRules::default()
}

#[test]
fn missing_keys_are_todays_planner() {
    // A missing buffer_min is 15 minutes (FIX-SPEC v1.3). PlanRules::default() stays 0.
    let parsed = plan_rules_from_value(&json!({}));
    assert_eq!(
        (
            parsed.weekend_homework_free,
            parsed.buffer_min,
            parsed.urgent_first,
            parsed.split_long_tasks,
            parsed.buffer_slots(),
        ),
        (false, 15, true, false, 1)
    );
    let afternoon = [work_span(&[4], "16:00", "20:00", None)];
    let both = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let touched = plan(
        &[
            locked("class", "15:00", 60, &[4]),
            flex("hw", 60, &[4], "medium", None),
        ],
        &afternoon,
        None,
        parsed,
    );
    assert_eq!(start_of(&touched, "hw"), expect(4, "16:15", 60));
    let open = plan(
        &[
            flex("science", 60, &[4], "medium", Some("Friday 18:00")),
            flex("math", 60, &[4, 5], "high", None),
        ],
        &both,
        None,
        parsed,
    );
    assert_eq!(start_of(&open, "science"), expect(4, "16:00", 60));
    assert_eq!(start_of(&open, "math"), expect(5, "10:00", 60));
    let urgent = plan(
        &[
            flex("a-math", 60, &[4], "medium", Some("Sunday 20:00")),
            flex("b-science", 60, &[4], "medium", Some("Friday 20:00")),
        ],
        &[work_span(&[4], "16:00", "18:00", None)],
        None,
        parsed,
    );
    assert_eq!(start_of(&urgent, "b-science"), expect(4, "16:00", 60));
    assert!(
        urgent.unplaced.iter().any(|block| block.id == "a-math"),
        "a 15-minute buffer leaves no second hour in 16:00–18:00"
    );
    let whole = plan(
        std::slice::from_ref(&flex("essay", 120, &[4, 5], "medium", None)),
        &both,
        None,
        parsed,
    );
    assert_eq!(start_of(&whole, "essay"), expect(4, "16:00", 120));
    assert!(by_id_missing(&whole, "essay~2"));
    let kept = plan(
        std::slice::from_ref(&flex("odd", 61, &[4], "medium", None)),
        &afternoon,
        None,
        parsed,
    );
    assert_eq!(start_of(&kept, "odd"), expect(4, "16:00", 61));
    let night = [flex("hw", 60, &[4], "low", None)];
    let late = [work_span(&[4], "21:00", "23:00", None)];
    let until_ten = occupancy_from_windows(&[], Some("22:00")).unwrap();
    assert_eq!(
        start_of(&plan(&night, &late, Some(&until_ten), parsed), "hw"),
        expect(4, "21:00", 60)
    );
    let until_nine = occupancy_from_windows(&[], Some("21:00")).unwrap();
    assert!(
        plan(&night, &late, Some(&until_nine), parsed)
            .unplaced
            .iter()
            .any(|block| block.id == "hw")
    );
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
            first_weekday: 0,
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
fn an_hour_stays_one_block() {
    // 60 minutes is not over 60, so it stays one block.
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
}

#[test]
fn sixty_one_minutes_is_over_an_hour_and_splits() {
    // Over 60 splits. 61 is over 60, so it becomes 30 and 31, which add up to 61.
    // 31 minutes occupies three grid slots and 30 occupies two: five slots, the same
    // as one 61-minute block. The stored lengths stay 30 and 31.
    let windows = [work_span(&[4], "16:00", "20:00", None)];
    let mut split = rules();
    split.split_long_tasks = true;
    let odd = flex("odd", 61, &[4], "medium", None);
    let parts = plan(std::slice::from_ref(&odd), &windows, None, split);
    assert_eq!(
        rows(&parts),
        vec![
            ("odd".into(), 4, "16:45".into(), 30),
            ("odd~2".into(), 4, "16:00".into(), 31),
        ]
    );
}

#[test]
fn a_split_half_keeps_the_original_deadline() {
    // Due Friday 17:00. Friday 16:00–17:00 holds one hour and ends on the deadline.
    // Saturday 10:00–11:00 is later, so the second half is unplaced.
    let essay = flex("essay", 120, &[4, 5], "medium", None);
    let windows = [
        work_span(&[4], "16:00", "17:00", None),
        work_span(&[5], "10:00", "11:00", None),
    ];
    let mut split = rules();
    split.split_long_tasks = true;
    let overrides = DeadlineOverrides {
        deadlines: vec![("essay".into(), Some((4, 17 * 60)))],
        slack_deadlines: vec![],
    };
    let trace = plan_deadlines(std::slice::from_ref(&essay), &windows, &overrides, split);
    assert_eq!(rows(&trace), vec![("essay".into(), 4, "16:00".into(), 60)]);
    assert_eq!(
        trace
            .unplaced
            .iter()
            .map(|block| (block.id.clone(), block.duration_min))
            .collect::<Vec<_>>(),
        vec![("essay~2".into(), 60)]
    );
}

#[test]
fn a_split_half_keeps_the_original_slack_deadline() {
    let essay = flex("essay", 120, &[4, 5], "medium", None);
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let mut split = rules();
    split.split_long_tasks = true;
    let overrides = DeadlineOverrides {
        deadlines: vec![],
        slack_deadlines: vec![("essay".into(), (4, 20 * 60))],
    };
    let trace = plan_deadlines(std::slice::from_ref(&essay), &windows, &overrides, split);
    assert_eq!(
        rows(&trace),
        vec![
            ("essay".into(), 4, "16:00".into(), 60),
            ("essay~2".into(), 5, "10:00".into(), 60),
        ]
    );
    let status = |id: &str| {
        trace
            .explanations
            .iter()
            .find(|item| item.block_id == id && item.slack_status.is_some())
            .and_then(|item| item.slack_status.clone())
    };
    assert_eq!(status("essay").as_deref(), Some("tight"));
    assert_eq!(status("essay~2").as_deref(), Some("danger"));
}

#[test]
fn buffer_does_not_pull_the_cutoff_earlier() {
    // Friday 21:00–22:00, cutoff 22:00. A 60-minute block ends on the cutoff.
    // The buffer is only a gap between tasks, so 15 and 30 still leave 21:00 open.
    let homework = flex("hw", 60, &[4], "low", None);
    let windows = [work_span(&[4], "21:00", "22:00", None)];
    let occ = occupancy_from_windows(&[], Some("22:00")).unwrap();
    for buffer in [0, 15, 30] {
        let mut spaced = rules();
        spaced.buffer_min = buffer;
        let trace = plan(
            std::slice::from_ref(&homework),
            &windows,
            Some(&occ),
            spaced,
        );
        assert_eq!(
            rows(&trace),
            vec![("hw".into(), 4, "21:00".into(), 60)],
            "buffer {buffer}"
        );
    }
}

#[test]
fn a_taken_half_id_keeps_the_task_whole() {
    // Rule: when `{id}~2` is already the id of any block, the flexible task stays one piece.
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let mut split = rules();
    split.split_long_tasks = true;
    let essay = flex("essay", 120, &[4, 5], "medium", None);
    let mut pinned = flex("essay~2", 60, &[5], "medium", None);
    pinned.pinned = true;
    pinned.start = Some("10:00".into());
    let mut done = flex("essay~2", 60, &[5], "medium", None);
    done.completed = true;
    done.completed_day = Some(5);
    done.start = Some("10:00".into());
    let siblings = [
        ("locked", locked("essay~2", "10:00", 60, &[5])),
        ("pinned", pinned),
        ("completed", done),
    ];
    for (label, sibling) in siblings {
        let trace = plan(&[essay.clone(), sibling], &windows, None, split);
        let mut ids: Vec<_> = trace
            .placed
            .iter()
            .chain(&trace.unplaced)
            .map(|block| block.id.clone())
            .collect();
        ids.sort();
        assert_eq!(
            ids,
            vec!["essay".to_string(), "essay~2".to_string()],
            "{label}"
        );
        assert_eq!(
            start_of(&trace, "essay"),
            expect(4, "16:00", 120),
            "{label}"
        );
    }
}

#[test]
fn splitting_a_task_again_leaves_the_halves_whole() {
    // 240 minutes is cut once into 120 and 120. Planning those halves again must not cut them.
    let windows = [
        work_span(&[4], "16:00", "20:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let mut split = rules();
    split.split_long_tasks = true;
    let essay = flex("essay", 240, &[4, 5], "medium", None);
    let first = plan(std::slice::from_ref(&essay), &windows, None, split);
    assert_eq!(start_of(&first, "essay"), expect(4, "16:00", 120));
    assert_eq!(start_of(&first, "essay~2"), expect(5, "10:00", 120));
    let again = plan(&first.placed, &windows, None, split);
    assert_eq!(start_of(&again, "essay"), expect(4, "16:00", 120));
    assert_eq!(start_of(&again, "essay~2"), expect(5, "10:00", 120));
    assert!(by_id_missing(&again, "essay~2~2"));
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

#[test]
fn weekends_homework_free_keeps_saturday_and_sunday_free_wherever_the_week_starts() {
    // A week shown from Wednesday: days 3 and 4 are Saturday and Sunday, days 5 and 6 Monday and
    // Tuesday. Study hours on Saturday (day 3) and Monday (day 5) only.
    let windows = [
        work_span(&[3], "10:00", "12:00", None),
        work_span(&[5], "16:00", "18:00", None),
    ];
    let blocks = [flex("math", 60, &[3, 5], "high", None)];
    let mut closed =
        plan_rules_from_value(&json!({"weekend_homework_free": 1, "first_weekday": 2}));
    closed.buffer_min = 0;
    assert_eq!(closed.first_weekday, 2);
    let shut = plan(&blocks, &windows, None, closed);
    assert_eq!(start_of(&shut, "math"), expect(5, "16:00", 60));
    let mut open = closed;
    open.weekend_homework_free = false;
    assert_eq!(
        start_of(&plan(&blocks, &windows, None, open), "math"),
        expect(3, "10:00", 60)
    );
    // From Monday, day 5 is Saturday again.
    assert_eq!(plan_rules_from_value(&json!({})).first_weekday, 0);
}

#[test]
fn a_named_day_in_latest_or_earliest_is_that_day_of_the_week_on_screen() {
    // A week shown from Wednesday: day 1 is Thursday, day 2 Friday, day 3 Saturday, day 5 Monday.
    let shown_from_wednesday = || {
        let mut rules = rules();
        rules.first_weekday = 2;
        rules
    };
    // Due Friday 18:00, with study hours only on Saturday: nothing before Friday evening fits.
    let saturday = [work_span(&[3], "10:00", "12:00", None)];
    let due_friday = Dump::flex("math", "math", 60, &[0, 1, 2, 3, 4, 5, 6])
        .latest("Friday 18:00")
        .into_block();
    let trace = plan(
        std::slice::from_ref(&due_friday),
        &saturday,
        None,
        shown_from_wednesday(),
    );
    assert!(
        trace.placed.iter().all(|block| block.id != "math"),
        "{:?}",
        trace.placed
    );
    // Not before Monday 09:00, with study hours on Thursday and on Monday: Monday.
    let thursday_and_monday = [
        work_span(&[1], "16:00", "18:00", None),
        work_span(&[5], "16:00", "18:00", None),
    ];
    let from_monday = Dump::flex("read", "read", 60, &[0, 1, 2, 3, 4, 5, 6])
        .earliest("Monday 09:00")
        .into_block();
    let trace = plan(
        std::slice::from_ref(&from_monday),
        &thursday_and_monday,
        None,
        shown_from_wednesday(),
    );
    assert_eq!(start_of(&trace, "read"), expect(5, "16:00", 60));
    // From Monday the same names are days 4 and 0, as before.
    let monday_hours = [
        work_span(&[0], "16:00", "18:00", None),
        work_span(&[5], "10:00", "12:00", None),
    ];
    let trace = plan(
        std::slice::from_ref(&due_friday),
        &monday_hours,
        None,
        rules(),
    );
    assert_eq!(start_of(&trace, "math"), expect(0, "16:00", 60));
}
