//! The paste preview that Duplicate and Ctrl+V open over Material is Material's own sheet:
//! desktop/tests/week/test_material_preview_dialog_keys.py ported (P3). Esc closes it and adds nothing, a number
//! key does not change the screen behind it, and the keyboard comes back to the window once it is closed.
//!
//! Club is a fixed time on Thursday 5 November 2026, 17:30 for an hour, on the week of Monday 2 November; Day
//! opens on that Thursday. A fixed block's menu reads Edit, Duplicate, Move to day..., Copy, Delete; the 3 key
//! opens Month.
//!
//! Each test starts the app, so they are left out of a plain `cargo test`; run them with
//! `cargo test -p flexweek-testkit --test week_paste_preview_keys -- --ignored --test-threads 2`.

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, block, named};
use serde_json::{Value, json};

const FIXED: [&str; 5] = ["Edit", "Duplicate", "Move to day...", "Copy", "Delete"];

#[derive(Clone, Copy)]
enum Screen {
    Week,
    Day,
}

#[derive(Clone, Copy)]
enum Opened {
    Duplicate,
    CtrlV,
}

fn sheet(app: &mut Door) -> Value {
    app.app()["sheet"].clone()
}

fn clubs(app: &mut Door) -> usize {
    app.app()["blocks"]
        .as_array()
        .map(|blocks| {
            blocks
                .iter()
                .filter(|block| block["title"] == json!("Club"))
                .count()
        })
        .unwrap_or(0)
}

/// Material on Week, or on Day for Thursday, with Club there.
fn on_screen(name: &str, screen: Screen) -> Door {
    let mut app = Door::start(name);
    app.seed("material_week");
    app.block(json!({
        "id": "club", "title": "Club", "kind": "locked", "category": "extra",
        "start": "17:30", "duration_min": 60, "days": [3]
    }));
    if let Screen::Day = screen {
        app.open_day("2026-11-05");
        app.wait_until("Club on the Day screen", |app| {
            app.read_all(&block("Club")).iter().any(|seen| seen.visible)
        });
    }
    app
}

/// Shift+F10 on Club, then the entry `label` chosen with the arrows and Enter.
fn choose_from_the_menu(app: &mut Door, label: &str) {
    app.focus(&block("Club"));
    app.key("shift+F10");
    app.wait_until("Club's menu to open", |app| {
        app.property(&named("blockMenu"), "open") == json!(true)
    });
    let entries: Vec<String> = app
        .property(&named("blockMenu"), "entries")
        .as_array()
        .map(|entries| {
            entries
                .iter()
                .map(|entry| entry["label"].as_str().unwrap_or_default().to_string())
                .collect()
        })
        .unwrap_or_default();
    assert_eq!(entries, FIXED);
    let index = FIXED.iter().position(|entry| *entry == label).unwrap();
    for _ in 0..index {
        app.key("Down");
    }
    app.key("Return");
}

fn open_the_preview(app: &mut Door, opened: Opened) {
    match opened {
        Opened::Duplicate => choose_from_the_menu(app, "Duplicate"),
        Opened::CtrlV => {
            choose_from_the_menu(app, "Copy");
            app.key("ctrl+V");
        }
    }
    app.wait_until("the preview sheet", |app| sheet(app) == json!("preview"));
    app.pump(20);
}

fn escape_closes_and_adds_nothing(screen: Screen, opened: Opened, name: &str) {
    let mut app = on_screen(name, screen);
    open_the_preview(&mut app, opened);
    app.key("Escape");
    app.wait_until("Esc to close the preview", |app| sheet(app) == json!(""));
    app.wait_until("the session to settle", |app| {
        let state = app.app();
        state["busy"] == json!(false) && state["dirty"] == json!(false)
    });
    assert_eq!(clubs(&mut app), 1);
}

fn a_number_key_leaves_the_screen_behind(screen: Screen, opened: Opened, name: &str) {
    let mut app = on_screen(name, screen);
    open_the_preview(&mut app, opened);
    let expected = match screen {
        Screen::Week => "week",
        Screen::Day => "day",
    };
    assert_eq!(app.app()["screen"], json!(expected));
    app.key("3");
    app.pump(10);
    assert_eq!(
        app.app()["screen"],
        json!(expected),
        "3 changed the screen behind the preview"
    );
    assert_eq!(sheet(&mut app), json!("preview"));
}

fn the_keyboard_comes_back(opened: Opened, name: &str) {
    let mut app = on_screen(name, Screen::Week);
    open_the_preview(&mut app, opened);
    app.key("Escape");
    app.wait_until("Esc to close the preview", |app| sheet(app) == json!(""));
    app.wait_until("the keyboard to come back", |app| {
        app.app()["window_has_keyboard"] == json!(true)
    });
    app.pump(20);
    // Material's own keys work again.
    app.key("3");
    app.pump(10);
    assert_eq!(app.app()["screen"], json!("month"));
}

macro_rules! door_test {
    ($name:ident, $body:expr) => {
        #[test]
        #[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
        fn $name() {
            $body(stringify!($name));
        }
    };
}

door_test!(
    escape_closes_the_duplicate_preview_on_week_and_adds_nothing,
    |name| { escape_closes_and_adds_nothing(Screen::Week, Opened::Duplicate, name) }
);
door_test!(
    escape_closes_the_duplicate_preview_on_day_and_adds_nothing,
    |name| { escape_closes_and_adds_nothing(Screen::Day, Opened::Duplicate, name) }
);
door_test!(
    escape_closes_the_ctrl_v_preview_on_week_and_adds_nothing,
    |name| { escape_closes_and_adds_nothing(Screen::Week, Opened::CtrlV, name) }
);
door_test!(
    escape_closes_the_ctrl_v_preview_on_day_and_adds_nothing,
    |name| { escape_closes_and_adds_nothing(Screen::Day, Opened::CtrlV, name) }
);
door_test!(
    a_number_key_does_not_change_week_behind_the_duplicate_preview,
    |name| { a_number_key_leaves_the_screen_behind(Screen::Week, Opened::Duplicate, name) }
);
door_test!(
    a_number_key_does_not_change_day_behind_the_duplicate_preview,
    |name| { a_number_key_leaves_the_screen_behind(Screen::Day, Opened::Duplicate, name) }
);
door_test!(
    a_number_key_does_not_change_week_behind_the_ctrl_v_preview,
    |name| { a_number_key_leaves_the_screen_behind(Screen::Week, Opened::CtrlV, name) }
);
door_test!(
    a_number_key_does_not_change_day_behind_the_ctrl_v_preview,
    |name| { a_number_key_leaves_the_screen_behind(Screen::Day, Opened::CtrlV, name) }
);
door_test!(
    the_keyboard_comes_back_when_the_duplicate_preview_closes,
    |name| { the_keyboard_comes_back(Opened::Duplicate, name) }
);
door_test!(
    the_keyboard_comes_back_when_the_ctrl_v_preview_closes,
    |name| { the_keyboard_comes_back(Opened::CtrlV, name) }
);
