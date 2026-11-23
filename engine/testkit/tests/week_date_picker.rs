//! The Week title's date picker, through the Driver, run against the Python app's test door: the first screen
//! tests ported from desktop/tests/week/test_material_go_to_date.py (P3). Expected values come from the
//! calendar: the account opens on the week of Monday 2 November 2026, so the picker opens on November, one
//! week down from Monday the 2nd is Monday the 9th, and picking it shows the week of 9 November.
//!
//! Each test starts the app (a few seconds), so they are left out of a plain `cargo test`; run them with
//! `cargo test -p flexweek-testkit --test week_date_picker -- --ignored --test-threads 2`.

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, named};
use serde_json::json;

fn is_open(app: &mut Door) -> bool {
    app.property(&named("datePicker"), "open") == json!(true)
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_week_title_opens_the_month_picker_on_the_week_on_view() {
    let mut app = Door::start("picker-opens");
    assert!(!is_open(&mut app));
    app.click(&named("materialTitle"));
    app.wait_until("the date picker to open", is_open);
    assert_eq!(app.property(&named("datePickerMonth"), "month"), json!(11));
    assert_eq!(app.property(&named("datePickerMonth"), "year"), json!(2026));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_day_picked_with_the_keyboard_shows_its_week_and_the_title_keeps_the_keyboard() {
    let mut app = Door::start("picker-keyboard");
    app.click(&named("materialTitle"));
    app.wait_until("the date picker to open", is_open);
    app.key("Down");
    app.key("Return");
    app.wait_until("the week of 9 November", |app| {
        app.app()["week_start"] == json!("2026-11-09")
    });
    assert!(!is_open(&mut app));
    assert!(app.read(&named("materialTitle")).focused);
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn escape_closes_the_picker_keeps_the_week_and_gives_the_keyboard_back_to_the_title() {
    let mut app = Door::start("picker-escape");
    app.click(&named("materialTitle"));
    app.wait_until("the date picker to open", is_open);
    app.key("Escape");
    assert!(!is_open(&mut app));
    assert!(app.read(&named("materialTitle")).focused);
    assert_eq!(app.app()["week_start"], json!("2026-11-02"));
}
