//! Go to a date from the Week and Month titles, through the Driver, run against the Python app's test door:
//! desktop/tests/week/test_material_go_to_date.py ported (P3). Expected values come from the calendar: the
//! account opens on the week of Monday 2 November 2026, so the picker opens on November; one week down from
//! Monday the 2nd is Monday the 9th; Friday the 20th is in the week of Monday the 16th; and the Month screen
//! opens on 2026-11.
//!
//! Each test starts the app (a few seconds), so they are left out of a plain `cargo test`; run them with
//! `cargo test -p flexweek-testkit --test week_date_picker -- --ignored --test-threads 2`.

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, named, reading_within};
use serde_json::json;

fn is_open(app: &mut Door) -> bool {
    app.property(&named("datePicker"), "open") == json!(true)
}

fn week_start(app: &mut Door) -> serde_json::Value {
    app.app()["week_start"].clone()
}

fn month_on_screen(app: &mut Door) -> serde_json::Value {
    app.app()["selected_month"].clone()
}

fn open_from_title(app: &mut Door) {
    app.click(&named("materialTitle"));
    app.wait_until("the date picker to open", is_open);
}

fn picker_month(app: &mut Door) -> (serde_json::Value, serde_json::Value) {
    (
        app.property(&named("datePickerMonth"), "year"),
        app.property(&named("datePickerMonth"), "month"),
    )
}

/// The Month screen, as the rail opens it.
fn to_month(app: &mut Door) {
    app.click(&named("navMonth"));
    app.wait_until("the Month screen on November", |app| {
        app.app()["screen"] == json!("month") && month_on_screen(app) == json!("2026-11")
    });
}

/// Opened with the mouse, closed with Escape (which gives the title the keyboard), then opened with `key`.
fn open_with_key(app: &mut Door, key: &str) {
    open_from_title(app);
    app.key("Escape");
    assert!(!is_open(app));
    app.key(key);
    app.wait_until("the date picker to open from the keyboard", is_open);
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

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn enter_and_space_on_the_title_open_the_picker_too() {
    let mut app = Door::start("picker-keys");
    for key in ["Return", "Space"] {
        open_with_key(&mut app, key);
        assert_eq!(picker_month(&mut app), (json!(2026), json!(11)));
        app.key("Escape");
    }
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_day_picked_with_the_mouse_shows_its_week() {
    let mut app = Door::start("picker-mouse");
    open_from_title(&mut app);
    app.click(&reading_within("20", "datePickerMonth"));
    app.wait_until("the week of 16 November", |app| {
        week_start(app) == json!("2026-11-16")
    });
    assert!(!is_open(&mut app));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_month_buttons_and_page_keys_change_the_pickers_month() {
    let mut app = Door::start("picker-pages");
    open_from_title(&mut app);
    app.click(&named("datePickerNext"));
    assert_eq!(picker_month(&mut app), (json!(2026), json!(12)));
    app.key("PageUp");
    app.key("PageUp");
    assert_eq!(picker_month(&mut app), (json!(2026), json!(10)));
    app.click(&named("datePickerPrevious"));
    assert_eq!(picker_month(&mut app), (json!(2026), json!(9)));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn tab_reaches_the_title_on_week_and_month() {
    let mut app = Door::start("picker-tab");
    for rail in ["navWeek", "navMonth"] {
        app.click(&named(rail));
        app.pump(30);
        // Keys start from the rail's Day item; Tab moves on from there to the title.
        app.focus(&named("navDay"));
        let reached = (0..12).any(|_| {
            app.key("Tab");
            app.read(&named("materialTitle")).focused
        });
        assert!(reached, "Tab never reached the title on {rail}");
    }
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_day_title_opens_no_picker() {
    let mut app = Door::start("picker-day");
    app.click(&named("navDay"));
    app.wait_until("the Day screen", |app| app.app()["screen"] == json!("day"));
    app.click(&named("materialTitle"));
    app.pump(10);
    assert!(!is_open(&mut app));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_keyboard_pick_in_the_month_title_shows_that_month() {
    let mut app = Door::start("picker-month-keys");
    to_month(&mut app);
    open_from_title(&mut app);
    app.click(&named("datePickerNext"));
    // The picker opens December on its 1st; Enter picks it.
    app.key("Return");
    app.wait_until("December on the Month screen", |app| {
        month_on_screen(app) == json!("2026-12")
    });
    assert!(!is_open(&mut app));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_mouse_pick_in_the_month_title_shows_that_month() {
    let mut app = Door::start("picker-month-mouse");
    to_month(&mut app);
    open_with_key(&mut app, "Return");
    app.click(&named("datePickerPrevious"));
    app.click(&reading_within("15", "datePickerMonth"));
    app.wait_until("October on the Month screen", |app| {
        month_on_screen(app) == json!("2026-10")
    });
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn escape_in_the_month_picker_gives_the_keyboard_back_and_keeps_the_month() {
    let mut app = Door::start("picker-month-escape");
    to_month(&mut app);
    open_with_key(&mut app, "Space");
    app.key("Escape");
    assert!(!is_open(&mut app));
    assert!(app.read(&named("materialTitle")).focused);
    assert_eq!(month_on_screen(&mut app), json!("2026-11"));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_picker_closes_when_the_rail_changes_the_screen() {
    // Left open over Day, a pick would quietly change another screen's date and keep keys switched off.
    let mut app = Door::start("picker-rail");
    open_from_title(&mut app);
    app.click(&named("navDay"));
    app.pump(20);
    assert_eq!(app.app()["screen"], json!("day"));
    assert!(!is_open(&mut app));
}
