//! The keyboard goes back to the week after a sheet closes, a drop, Plan, Undo and redo, so the next arrow, Tab
//! or Enter works on the week and not on a control that is gone: desktop/tests/week/
//! test_material_keyboard_returns_to_week.py ported (P3). "On the week" is the grid (`weekScroller`) or one of
//! its blocks (`weekBlock`).
//!
//! The account opens on the week of Monday 2 November 2026 with the clock at Thursday 19:00; the seed puts
//! School on Monday to Friday mornings and the History essay at 18:45 on Thursday. The Math worksheet is due
//! Sunday the 8th. Club sits on Friday at 16:00; the week's rows are 56 px an hour, so a drag 5 rows up lands
//! it at 11:00.
//!
//! Each test starts the app, so they are left out of a plain `cargo test`; run them with
//! `cargo test -p flexweek-testkit --test week_keyboard_returns -- --ignored --test-threads 2`.

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, block, named, reading, titled};
use serde_json::json;

const ROW: i32 = 56;

fn on_the_week(app: &mut Door) -> bool {
    let focus = app.focused();
    focus.inside("weekBlock") || focus.inside("weekScroller")
}

fn where_it_is(app: &mut Door) -> String {
    app.focused().path()
}

fn not_busy(app: &mut Door) -> bool {
    app.app()["busy"] == json!(false)
}

fn snack(app: &mut Door) -> String {
    app.app()["snack"].as_str().unwrap_or_default().to_string()
}

fn week(name: &str) -> Door {
    let mut app = Door::start(name);
    app.seed("material_week");
    app
}

fn waiting_homework(app: &mut Door) {
    app.homework("math", "Math worksheet", 30, "2026-11-08");
}

/// Places the worksheet with "Place now" from its card's menu (the menu key opens it).
fn plan_from_the_card(app: &mut Door) {
    app.focus(&titled("homeworkCard", "Math worksheet"));
    app.key("Menu");
    app.wait_until("the card's menu to open", |app| {
        app.read(&reading("Place now")).visible
    });
    app.click(&reading("Place now"));
    app.wait_until("the worksheet to be placed", |app| {
        snack(app).starts_with("Placed") && not_busy(app)
    });
    app.pump(40);
}

fn focus_school(app: &mut Door) {
    app.focus(&block("School"));
    assert!(
        on_the_week(app),
        "the test could not put the keyboard on School"
    );
}

fn worksheet_on_the_week(app: &mut Door) -> bool {
    app.read_all(&named("weekBlock"))
        .iter()
        .any(|seen| seen.title == "Math worksheet")
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_sheet_that_closes_gives_the_keyboard_back_to_the_block_that_opened_it() {
    let mut app = week("keys-sheet");
    focus_school(&mut app);
    app.key("Return");
    app.pump(30);
    assert_eq!(app.app()["sheet"], json!("block"));
    assert!(
        !on_the_week(&mut app),
        "the sheet did not take the keyboard, so the test says nothing"
    );
    app.key("Escape");
    app.pump(40);
    assert_eq!(app.app()["sheet"], json!(""));
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn after_plan_by_keyboard_the_keyboard_is_on_the_week() {
    let mut app = week("keys-plan");
    waiting_homework(&mut app);
    app.focus(&named("planHomework"));
    app.key("Return");
    app.wait_until("Plan to place the worksheet", |app| {
        snack(app).starts_with("Placed") && not_busy(app)
    });
    app.pump(60);
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn ctrl_z_from_a_block_leaves_the_keyboard_on_the_week() {
    let mut app = week("keys-undo");
    waiting_homework(&mut app);
    plan_from_the_card(&mut app);
    focus_school(&mut app);
    app.key("ctrl+Z");
    app.wait_until("Undo to finish", not_busy);
    app.pump(40);
    assert!(
        !worksheet_on_the_week(&mut app),
        "Undo did not take the plan back, so the test says nothing"
    );
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
    assert_eq!(
        app.focused().title_of("weekBlock"),
        Some("School"),
        "the block acted on keeps the keyboard"
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn redo_leaves_the_keyboard_on_the_week() {
    let mut app = week("keys-redo");
    waiting_homework(&mut app);
    plan_from_the_card(&mut app);
    focus_school(&mut app);
    app.key("ctrl+Z");
    app.wait_until("Undo to finish", not_busy);
    app.pump(40);
    focus_school(&mut app);
    app.key("ctrl+Y");
    app.wait_until("Redo to finish", not_busy);
    app.pump(40);
    assert!(
        worksheet_on_the_week(&mut app),
        "redo did not put the plan back, so the test says nothing"
    );
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_notices_undo_by_keyboard_leaves_the_keyboard_on_the_week() {
    let mut app = week("keys-notice-undo");
    waiting_homework(&mut app);
    plan_from_the_card(&mut app);
    app.focus(&named("materialSnackbar"));
    app.key("Return");
    app.wait_until("Undo to finish", not_busy);
    app.pump(60);
    assert!(
        snack(&mut app).starts_with("Undid"),
        "the notice's Undo did not run, so the test says nothing"
    );
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_dropped_block_keeps_the_keyboard_on_the_week() {
    let mut app = week("keys-drop");
    app.block(json!({
        "id": "club", "title": "Club", "kind": "locked", "category": "extra",
        "start": "16:00", "duration_min": 60, "days": [4]
    }));
    app.reveal(&block("Club"));
    app.focus(&block("Club"));
    assert!(
        on_the_week(&mut app),
        "the test could not put the keyboard on Club"
    );
    app.drag(&block("Club"), (0, 0), (0, -5 * ROW));
    let club = app.app()["blocks"]
        .as_array()
        .and_then(|blocks| {
            blocks
                .iter()
                .find(|block| block["id"] == json!("club"))
                .cloned()
        })
        .expect("Club is still in the week");
    assert_eq!(
        club["start"],
        json!("11:00"),
        "the block was not moved, so the test says nothing"
    );
    app.pump(40);
    assert!(
        on_the_week(&mut app),
        "the keyboard is on {}, not on the week",
        where_it_is(&mut app)
    );
    assert_eq!(
        app.focused().title_of("weekBlock"),
        Some("Club"),
        "the dropped block keeps the keyboard"
    );
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn the_notices_undo_is_still_a_tab_away_after_plan() {
    let mut app = week("keys-tab-to-undo");
    waiting_homework(&mut app);
    plan_from_the_card(&mut app);
    focus_school(&mut app);
    let mut reached = false;
    for _ in 0..60 {
        app.key("Tab");
        if app.focused().inside("materialSnackbar") {
            reached = true;
            break;
        }
    }
    assert!(
        reached,
        "Tab never reached the notice's Undo; the keyboard ended on {}",
        where_it_is(&mut app)
    );
    app.key("Return");
    app.wait_until("Undo to finish", not_busy);
    app.pump(60);
    let said = snack(&mut app);
    assert!(said.starts_with("Undid"), "{said}");
}
