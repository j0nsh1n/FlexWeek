//! The planner on 18 real student weeks (fixtures/real_student_weeks.json, day 0 = Monday): it uses
//! the whole week and never drops a more important item for a less important one.
//!
//! The solver runs with a fixed-work clock in place of the wall clock: each clock read advances it by
//! a fixed step, so the 150 ms budget is the same amount of search on every machine and the plans are
//! deterministic. 0.001 ms per check matches the app's 150 ms on the machine the comparison ran on (the
//! placed counts equal the comparison report's "Today" column); 0.004 is a laptop four times slower.
//!
//! Guards: week 17's three items all get a time this week (with the weekend days offered), some of it on
//! the weekend, with Friday at most 150 minutes; no week places fewer items than the planner did when the
//! comparison was made; a priority 1 item is never dropped while a lower one is placed. With the tests
//! below, the Rust twins of backend/tests/regress184/test_regress_item1c_spread.py. Which days an item is
//! offered, and the fair share of long work, have their own test files (session days, fair share).
//!
//! Not true yet, and pinned below as known failures: a daily cap, the 30-minute gap after School, and
//! "nothing ends the day before it is due". The planner has no daily cap.

use std::cell::Cell;
use std::collections::HashMap;

use flexweek_engine::desk::planning::session_days;
use flexweek_engine::solver::{
    SOLVE_BUDGET_MS, SolveTrace, block_from_value, overrides_from, solve, work_window_from_value,
};
use flexweek_engine::time::hhmm_to_minutes;
use serde_json::{Value, json};

const WEEKS: &str = include_str!("fixtures/real_student_weeks.json");

// Items the planner placed in each week when the comparison was made, at 1x and at 4x slower.
const TODAY: [(&str, usize); 18] = [
    ("1", 3),
    ("2", 8),
    ("3", 22),
    ("4", 60),
    ("5", 8),
    ("6", 10),
    ("7", 6),
    ("8", 6),
    ("9", 9),
    ("10", 6),
    ("11", 25),
    ("12", 27),
    ("13", 30),
    ("14", 22),
    ("15", 15),
    ("16", 40),
    ("17", 3),
    ("17b", 3),
];
const TODAY_SLOW: [(&str, usize); 2] = [("10", 5), ("15", 14)];

fn weeks() -> Vec<Value> {
    serde_json::from_str::<Vec<Value>>(WEEKS).expect("the weeks file")
}

/// "17. First ..." -> "17"; "17b. Same, ..." -> "17b".
fn short_name(week: &Value) -> String {
    week["name"]
        .as_str()
        .expect("a name")
        .split('.')
        .next()
        .expect("a number")
        .to_string()
}

fn floor(name: &str, slow: bool) -> usize {
    if slow && let Some((_, count)) = TODAY_SLOW.iter().find(|(key, _)| *key == name) {
        return *count;
    }
    TODAY
        .iter()
        .find(|(key, _)| *key == name)
        .expect("a floor")
        .1
}

fn truthy_object(value: Option<&Value>) -> Option<&Value> {
    value.filter(|item| item.as_object().is_some_and(|map| !map.is_empty()))
}

fn solve_week(week: &Value, per_check_ms: f64) -> SolveTrace {
    let blocks: Vec<_> = week["blocks"]
        .as_array()
        .expect("blocks")
        .iter()
        .map(|item| block_from_value(item).expect("a block"))
        .collect();
    let overrides = overrides_from(
        truthy_object(week.get("deadlines")),
        truthy_object(week.get("slack")),
    );
    let extra_occ: Option<Vec<u128>> = week
        .get("extra_occ")
        .and_then(Value::as_array)
        .filter(|list| !list.is_empty())
        .map(|list| {
            list.iter()
                .map(|bits| bits.to_string().parse().expect("an occupancy mask"))
                .collect()
        });
    let work: Option<Vec<_>> = week
        .get("work_windows")
        .and_then(Value::as_array)
        .filter(|list| !list.is_empty())
        .map(|list| list.iter().map(work_window_from_value).collect());
    let checks = Cell::new(0u64);
    let clock = || {
        checks.set(checks.get() + 1);
        checks.get() as f64 * per_check_ms
    };
    solve(
        &blocks,
        extra_occ.as_deref(),
        work.as_deref(),
        Some(&overrides),
        None,
        SOLVE_BUDGET_MS,
        &clock,
    )
    .expect("solve")
}

/// The homework the plan gave a time: id -> (day, start, end).
fn placed(week: &Value, trace: &SolveTrace) -> HashMap<String, (i64, i64, i64)> {
    let items = homework(week);
    let mut out = HashMap::new();
    for block in &trace.placed {
        let Some(item) = items.get(block.id.as_str()) else {
            continue;
        };
        let Some(start) = block.start.as_deref().filter(|text| !text.is_empty()) else {
            continue;
        };
        let start = hhmm_to_minutes(start).expect("a time");
        let length = item["duration_min"].as_i64().expect("a length");
        out.insert(block.id.clone(), (block.days[0], start, start + length));
    }
    out
}

fn homework(week: &Value) -> HashMap<&str, &Value> {
    week["blocks"]
        .as_array()
        .expect("blocks")
        .iter()
        .filter(|block| {
            block["kind"] == "flexible" && !block.get("pinned").is_some_and(|p| p == &json!(true))
        })
        .map(|block| (block["id"].as_str().expect("an id"), block))
        .collect()
}

fn week17_as_the_app_asks() -> Value {
    // Each item's days are rebuilt the way the app builds them: the days up to its due date, then only
    // today and later (Friday).
    let mut week = weeks()
        .into_iter()
        .find(|week| short_name(week) == "17")
        .expect("week 17");
    let due = [
        ("n1", "2026-10-14T23:59"),
        ("n2", "2026-10-15T23:59"),
        ("n3", "2026-10-16T23:59"),
    ];
    let now_day = 4;
    for block in week["blocks"].as_array_mut().expect("blocks") {
        let id = block["id"].as_str().expect("an id").to_string();
        if let Some((_, when)) = due.iter().find(|(key, _)| *key == id) {
            let offered = session_days("2026-10-05", &json!(when)).expect("days");
            let days: Vec<i64> = offered.into_iter().filter(|day| *day >= now_day).collect();
            block["days"] = json!(days);
        }
    }
    week
}

#[test]
fn week_17_offers_plan_friday_at_least() {
    let week = week17_as_the_app_asks();
    let trace = solve_week(&week, 0.001);
    assert_eq!(placed(&week, &trace).len(), 3);
}

fn every_week_keeps_its_floor(per_check_ms: f64, slow: bool) {
    let mut short = Vec::new();
    for week in weeks() {
        let name = short_name(&week);
        let count = placed(&week, &solve_week(&week, per_check_ms)).len();
        let wanted = floor(&name, slow);
        if count < wanted {
            short.push(format!("{}: {count} placed, before {wanted}", week["name"]));
        }
    }
    assert!(short.is_empty(), "{short:#?}");
}

#[test]
fn no_week_places_fewer_items_than_before() {
    every_week_keeps_its_floor(0.001, false);
}

#[test]
fn no_week_places_fewer_items_than_before_on_a_slower_laptop() {
    every_week_keeps_its_floor(0.004, true);
}

fn priority_1_is_kept_over_lower(per_check_ms: f64) {
    let mut wrong = Vec::new();
    for week in weeks() {
        let items = homework(&week);
        let got = placed(&week, &solve_week(&week, per_check_ms));
        let dropped: Vec<&str> = items
            .iter()
            .filter(|(id, block)| block["priority"] == json!(1) && !got.contains_key(**id))
            .map(|(id, _)| *id)
            .collect();
        let lower = got
            .keys()
            .filter(|id| items[id.as_str()]["priority"].as_i64().unwrap_or(3) > 1)
            .count();
        if !dropped.is_empty() && lower > 0 {
            wrong.push(format!(
                "{}: priority 1 {dropped:?} dropped, {lower} lower placed",
                week["name"]
            ));
        }
    }
    assert!(wrong.is_empty(), "{wrong:#?}");
}

#[test]
fn a_priority_1_item_is_never_dropped_for_a_lower_one() {
    priority_1_is_kept_over_lower(0.001);
}

#[test]
fn a_priority_1_item_is_never_dropped_for_a_lower_one_on_a_slower_laptop() {
    priority_1_is_kept_over_lower(0.004);
}

/// The most homework per day the app plans by default (fix-specs item 1c.B, "Most homework per day").
const CAP_MIN: i64 = 150;
const AFTER_SCHOOL_GAP: i64 = 30;
const DAYS: [&str; 7] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
];

fn per_day(times: &HashMap<String, (i64, i64, i64)>) -> HashMap<i64, i64> {
    let mut load = HashMap::new();
    for (day, start, end) in times.values() {
        *load.entry(*day).or_insert(0) += end - start;
    }
    load
}

fn week_named(name: &str) -> Value {
    weeks()
        .into_iter()
        .find(|week| short_name(week) == name)
        .expect("a week")
}

/// (day, minute) an item is due: its slack deadline, or its "Thursday 21:00".
fn due_point(week: &Value, block: &Value) -> (i64, i64) {
    if let Some(slack) = week["slack"].get(block["id"].as_str().expect("an id")) {
        return (
            slack[0].as_i64().expect("a day"),
            slack[1].as_i64().expect("a minute"),
        );
    }
    let latest = block["latest"].as_str().expect("a due time");
    let (day, at) = latest.split_once(' ').expect("day and time");
    let day = DAYS.iter().position(|name| *name == day).expect("a day") as i64;
    (day, hhmm_to_minutes(at).expect("a time"))
}

#[test]
fn week_17_uses_the_weekend_and_friday_stays_under_the_cap() {
    let week = week17_as_the_app_asks();
    let times = placed(&week, &solve_week(&week, 0.001));
    let load = per_day(&times);
    let weekend = load.get(&5).copied().unwrap_or(0) + load.get(&6).copied().unwrap_or(0);
    assert!(weekend > 0, "nothing on Sat/Sun: {times:?}");
    let friday = load.get(&4).copied().unwrap_or(0);
    assert!(friday <= CAP_MIN, "Friday has {friday} min");
}

// Known failures (fix-specs item 1c.B), kept as backend/tests/regress184/test_regress_item1c_spread.py kept
// them, as strict expected failures: each asserts the failure still happens, so the day the planner learns
// the rule the test fails and is turned into the guard it names.

/// Week 2: a day goes over the cap while a lighter day before the item's due date had room.
#[test]
fn known_failure_week_2_puts_a_day_over_the_cap_while_a_lighter_day_has_room() {
    let week = week_named("2");
    let items = homework(&week);
    let times = placed(&week, &solve_week(&week, 0.001));
    let load = per_day(&times);
    let crammed: Vec<&String> = times
        .iter()
        .filter(|(id, (day, start, end))| {
            if load[day] <= CAP_MIN {
                return false;
            }
            let item = items[id.as_str()];
            let (due_day, _) = due_point(&week, item);
            item["days"].as_array().expect("days").iter().any(|other| {
                let other = other.as_i64().expect("a day");
                other < due_day
                    && other != *day
                    && load.get(&other).copied().unwrap_or(0) + end - start <= CAP_MIN
            })
        })
        .map(|(id, _)| id)
        .collect();
    assert!(
        !crammed.is_empty(),
        "the cap now holds in week 2: turn this into its guard"
    );
}

/// Week 2: something ends less than a day before its due date though it was due two or more days out.
#[test]
fn known_failure_week_2_ends_work_less_than_a_day_before_its_due_date() {
    let week = week_named("2");
    let items = homework(&week);
    let now_day = week["now"][0].as_i64().expect("a day");
    let now_min = hhmm_to_minutes(week["now"][1].as_str().expect("a time")).expect("a time");
    // The rule is not empty: an item is due Thursday or later.
    assert!(items.values().any(|item| due_point(&week, item).0 >= 3));
    let late = placed(&week, &solve_week(&week, 0.001))
        .into_iter()
        .filter(|(id, (day, _, end))| {
            let (due_day, due_min) = due_point(&week, items[id.as_str()]);
            let lead = (due_day - now_day) * 1440 + due_min - now_min;
            lead >= 2 * 1440 && (due_day - day) * 1440 + due_min - end < 1440
        })
        .count();
    assert!(
        late > 0,
        "a day's buffer now holds in week 2: turn this into its guard"
    );
}

/// Week 2: homework starts within 30 minutes of School's end.
#[test]
fn known_failure_homework_starts_right_when_school_ends() {
    let week = week_named("2");
    let school = week["blocks"]
        .as_array()
        .expect("blocks")
        .iter()
        .find(|block| block["id"] == "school")
        .expect("school");
    let ends = hhmm_to_minutes(school["start"].as_str().expect("a start")).expect("a time")
        + school["duration_min"].as_i64().expect("a length");
    let school_days: Vec<i64> = school["days"]
        .as_array()
        .expect("days")
        .iter()
        .map(|day| day.as_i64().expect("a day"))
        .collect();
    let too_soon = placed(&week, &solve_week(&week, 0.001))
        .values()
        .filter(|(day, start, _)| {
            school_days.contains(day) && ends <= *start && *start < ends + AFTER_SCHOOL_GAP
        })
        .count();
    assert!(
        too_soon > 0,
        "the gap after School now holds: turn this into its guard"
    );
}
