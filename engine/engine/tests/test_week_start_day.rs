//! A week on screen can start on any day (0 Monday to 6 Sunday). Stored weeks stay keyed by their
//! Monday; these are the dates a shown week and a month's rows run over. Expected dates are read
//! off the 2026 calendar: 1 November 2026 is a Sunday, 1 January 2027 a Friday.

use flexweek_engine::ErrorKind;
use flexweek_engine::time::{month_grid, month_grid_from, week_start_on, weekday_order};

const MONDAY: u32 = 0;
const WEDNESDAY: u32 = 2;
const SATURDAY: u32 = 5;
const SUNDAY: u32 = 6;

#[test]
fn a_wednesday_week_holds_the_tuesday_after_it_and_starts_on_its_wednesday() {
    assert_eq!(
        week_start_on("2026-11-05", WEDNESDAY).unwrap(),
        "2026-11-04"
    );
    assert_eq!(
        week_start_on("2026-11-04", WEDNESDAY).unwrap(),
        "2026-11-04"
    );
    assert_eq!(
        week_start_on("2026-11-10", WEDNESDAY).unwrap(),
        "2026-11-04"
    );
    assert_eq!(
        week_start_on("2026-11-11", WEDNESDAY).unwrap(),
        "2026-11-11"
    );
}

#[test]
fn a_monday_week_is_the_stored_week_and_a_sunday_week_starts_the_day_before() {
    assert_eq!(week_start_on("2026-11-05", MONDAY).unwrap(), "2026-11-02");
    assert_eq!(week_start_on("2026-11-08", MONDAY).unwrap(), "2026-11-02");
    assert_eq!(week_start_on("2026-11-05", SUNDAY).unwrap(), "2026-11-01");
    assert_eq!(week_start_on("2026-11-08", SUNDAY).unwrap(), "2026-11-08");
}

#[test]
fn a_shown_week_can_start_in_the_month_or_year_before() {
    // Sunday 1 November belongs to the Saturday week that began on 31 October.
    assert_eq!(week_start_on("2026-11-01", SATURDAY).unwrap(), "2026-10-31");
    // Friday 1 January 2027 belongs to the Wednesday week that began on 30 December 2026.
    assert_eq!(
        week_start_on("2027-01-01", WEDNESDAY).unwrap(),
        "2026-12-30"
    );
}

#[test]
fn a_start_day_past_sunday_or_a_bad_date_is_refused() {
    assert_eq!(
        week_start_on("2026-11-05", 7).unwrap_err().kind,
        ErrorKind::Value
    );
    assert_eq!(
        week_start_on("2026-13-05", MONDAY).unwrap_err().kind,
        ErrorKind::Value
    );
    assert_eq!(weekday_order(7).unwrap_err().kind, ErrorKind::Value);
}

#[test]
fn the_days_run_from_the_start_day_round_to_the_day_before_it() {
    assert_eq!(weekday_order(MONDAY).unwrap(), [0, 1, 2, 3, 4, 5, 6]);
    assert_eq!(weekday_order(WEDNESDAY).unwrap(), [2, 3, 4, 5, 6, 0, 1]);
    assert_eq!(weekday_order(SATURDAY).unwrap(), [5, 6, 0, 1, 2, 3, 4]);
    assert_eq!(weekday_order(SUNDAY).unwrap(), [6, 0, 1, 2, 3, 4, 5]);
}

#[test]
fn november_2026_rows_start_on_the_chosen_day_and_end_the_day_before_it() {
    let rows = |first| month_grid_from("2026-11-01", "2026-11-30", first).unwrap();
    assert_eq!(rows(MONDAY), ("2026-10-26".into(), "2026-12-06".into()));
    assert_eq!(rows(WEDNESDAY), ("2026-10-28".into(), "2026-12-01".into()));
    assert_eq!(rows(SATURDAY), ("2026-10-31".into(), "2026-12-04".into()));
    assert_eq!(rows(SUNDAY), ("2026-11-01".into(), "2026-12-05".into()));
    assert_eq!(
        rows(MONDAY),
        month_grid("2026-11-01", "2026-11-30").unwrap()
    );
}

#[test]
fn december_2026_rows_with_a_wednesday_start_run_into_january() {
    assert_eq!(
        month_grid_from("2026-12-01", "2026-12-31", WEDNESDAY).unwrap(),
        ("2026-11-25".into(), "2027-01-05".into())
    );
}

#[test]
fn month_rows_stay_inside_the_supported_dates() {
    assert_eq!(
        month_grid_from("2000-01-01", "2000-01-31", WEDNESDAY).unwrap(),
        ("2000-01-01".into(), "2000-02-01".into())
    );
    assert_eq!(
        month_grid_from("2099-12-01", "2099-12-31", WEDNESDAY).unwrap(),
        ("2099-11-25".into(), "2099-12-31".into())
    );
    assert_eq!(
        month_grid_from("2026-11-01", "2026-11-30", 7)
            .unwrap_err()
            .kind,
        ErrorKind::Value
    );
}
