//! A session resized by hand and then let go again can be any length. The planner still starts it on a
//! quarter hour and keeps every quarter hour it touches for it.

mod common;

use common::{Dump, placed_interval, solve_open};

#[test]
fn a_session_of_any_length_starts_on_a_quarter_hour_and_keeps_the_quarter_hours_it_touches() {
    let short = Dump::flex("short", "Homework", 10, &[0]).into_block();
    let long = Dump::flex("long", "Homework", 50, &[0]).into_block();
    let trace = solve_open(&[short, long]);

    let mut spans: Vec<(i64, i64)> = trace
        .placed
        .iter()
        .map(|block| (placed_interval(block).1, block.duration_min))
        .collect();
    spans.sort();

    assert_eq!(spans.len(), 2);
    assert!(spans.iter().all(|(start, _)| start % 15 == 0), "{spans:?}");
    let [(first, length), (second, _)] = spans[..] else {
        panic!("two sessions were placed");
    };
    assert!(second >= first + (length + 14) / 15 * 15, "{spans:?}");
}
