//! The test door itself (desktop/tests/door.py): every step it is asked gets an answer, a refusal says why
//! instead of leaving the test waiting, and two doors started at once each have their own app.
//!
//! Each test starts the app, so they run with `-- --ignored` (see week_date_picker.rs).

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, named};
use serde_json::json;

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn a_step_the_door_cannot_do_is_refused_with_its_reason_not_left_unanswered() {
    let mut app = Door::start("door-refusals");
    for (asked, said) in [
        (json!(123), "a step is a JSON object"),
        (json!({ "step": "fly" }), "no step called"),
        (
            json!({ "step": "click", "target": 7 }),
            "a target is a JSON object",
        ),
        (
            json!({ "step": "click", "target": {} }),
            "a target names an item or its words",
        ),
        (json!({ "step": "key", "key": "Nope" }), "no key called"),
        // Any other error inside a step is an answer too, named by its kind.
        (json!({ "step": "pump", "turns": [1] }), "TypeError"),
        (
            json!({ "step": "click", "target": { "name": "noSuchItem" } }),
            "nothing on screen is",
        ),
    ] {
        let answer = app.ask(&asked);
        assert_eq!(answer["ok"], false, "{asked} -> {answer}");
        let error = answer["error"].as_str().unwrap_or_default();
        assert!(error.contains(said), "{asked} -> {error}");
    }
    // Still answering after all that.
    assert_eq!(app.app()["week_start"], json!("2026-11-02"));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn text_is_typed_into_the_item_that_has_the_keyboard() {
    let mut app = Door::start("door-typing");
    app.click(&named("materialTitle"));
    app.wait_until("the date picker to open", |app| {
        app.property(&named("datePicker"), "open") == json!(true)
    });
    // Typing reaches the open picker as keys do: a letter it does not use leaves it open.
    app.type_text("x");
    assert_eq!(app.property(&named("datePicker"), "open"), json!(true));
}

#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn two_doors_with_the_same_name_are_two_apps() {
    let mut first = Door::start("door-twins");
    let mut second = Door::start("door-twins");
    assert_ne!(first.folder(), second.folder());
    assert!(
        first.folder().join("door.sock").exists(),
        "the second start removed the first's folder"
    );
    first.click(&named("navMonth"));
    first.wait_until("the Month screen", |app| {
        app.app()["screen"] == json!("month")
    });
    assert_eq!(second.app()["screen"], json!("week"));
}
