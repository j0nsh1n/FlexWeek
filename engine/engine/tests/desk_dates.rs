//! Rust twin of `desktop/tests/test_dates.py`: the sentences the app builds from dates. The short and
//! long day, the week range and the month title are checked beside the code in
//! `engine/engine/src/desk/datetext.rs`; the due label on both clocks is in `desk_clock.rs`
//! (`test_the_week_model_words`) and `desk_weekmodel.rs`; the planner title in `desk_reuse.rs`. These two
//! are the sentences that put a date into a toast.

mod common;

use chrono::NaiveDate;
use common::desk::clock_lock;
use flexweek_engine::desk::planning::capacity_problem;
use flexweek_engine::desk::reuse::week_label;
use flexweek_engine::desk::weekmodel::dated_words;
use serde_json::json;

fn this_year() -> NaiveDate {
    NaiveDate::from_ymd_opt(2026, 10, 9).expect("a date")
}

#[test]
fn test_the_toast_after_moving_homework_names_the_date_the_same_way() {
    let _clock = clock_lock();
    assert_eq!(
        dated_words(&json!("History essay"), &json!("2026-10-01"), this_year()).expect("words"),
        "Moved History essay to Thu 1 Oct."
    );
}

#[test]
fn test_the_capacity_toast_names_the_week_by_its_range_not_its_iso_date() {
    let label = week_label("2026-09-28", this_year()).expect("label");
    assert_eq!(
        capacity_problem(100, 1, &label),
        "Week of 28 Sep – 4 Oct would exceed 100 blocks. Uncheck an item or remove a block first."
    );
}
