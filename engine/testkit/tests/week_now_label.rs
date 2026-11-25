//! The time label beside the now line in Material Week and Day (Jonathan, 2026-11-10):
//! desktop/tests/week/test_material_now_label.py ported (P3). The current time, in the account's clock format,
//! sits in the hour column at the line's height, never covers a block, moves with the line on the clock tick and
//! with zoom, says "Current time, <time>" to a screen reader, and hides only the hour number it sits on. Its
//! colour, size and corners are judged in the picture review.
//!
//! Expected values come from the fake clock (Thursday 5 November 2026 at 19:00, then twenty-five minutes later)
//! and from the layout: the hour column ends where the first day's blocks begin. Hour 11's number is 14 px tall
//! and starts 8 px above its line; the label is about 21 px tall and centred on the time's line, so at 10:58,
//! 11:00 and 11:03 the two overlap and at 11:30 they do not.
//!
//! Each test starts the app, so they are left out of a plain `cargo test`; run them with
//! `cargo test -p flexweek-testkit --test week_now_label -- --ignored --test-threads 2`.

#![cfg(unix)]

use flexweek_testkit::door::{Door, Driver, Rect, Seen, named, named_within};
use serde_json::json;

#[derive(Clone, Copy)]
enum Screen {
    Week,
    Day,
}

impl Screen {
    fn page(self) -> &'static str {
        match self {
            Screen::Week => "materialWeek",
            Screen::Day => "materialDay",
        }
    }

    fn scroller(self) -> &'static str {
        match self {
            Screen::Week => "weekScroller",
            Screen::Day => "dayScroller",
        }
    }
}

/// Material on Week, or on Day for Thursday the 5th.
fn on_screen(name: &str, screen: Screen) -> Door {
    let mut app = Door::start(name);
    app.seed("material_week");
    if let Screen::Day = screen {
        app.open_day("2026-11-05");
        app.wait_until("the Day screen", |app| {
            app.read(&named("materialDay")).found
        });
    }
    app
}

fn label(app: &mut Door, screen: Screen) -> Seen {
    let found = app.read_all(&named_within("nowLabel", screen.page()));
    assert_eq!(found.len(), 1, "one time label on the screen: {found:?}");
    found.into_iter().next().unwrap()
}

fn words(app: &mut Door, screen: Screen) -> String {
    app.read(&named_within("nowLabelText", screen.page())).text
}

fn line(app: &mut Door, screen: Screen) -> Rect {
    app.read(&named_within("nowLine", screen.page())).rect
}

fn shown(seen: &Seen) -> bool {
    seen.visible && seen.opacity > 0.0
}

fn shows_the_24_hour_time(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    let label = label(&mut app, screen);
    assert!(label.visible);
    assert_eq!(words(&mut app, screen), "19:00");
    assert_eq!(label.accessible, "Current time, 19:00");
}

fn shows_the_12_hour_time(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    app.preferences(json!({ "clock_24h": false }));
    assert_eq!(words(&mut app, screen), "7:00 PM");
    assert_eq!(label(&mut app, screen).accessible, "Current time, 7:00 PM");
}

fn sits_at_the_line_in_the_hour_column(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    let label = label(&mut app, screen).rect;
    let line = line(&mut app, screen);
    assert!(
        (label.middle_y() - line.middle_y()).abs() <= 2.0,
        "at the line's height: label {label:?}, line {line:?}"
    );
    let blocks = app.read_all(&named_within("weekBlock", screen.page()));
    assert!(!blocks.is_empty());
    for block in &blocks {
        assert!(
            !label.overlaps(&block.rect),
            "the label is over the block {:?}",
            block.title
        );
    }
    assert!(label.left >= app.read(&named(screen.scroller())).rect.left);
}

fn moves_with_the_tick_and_with_zoom(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    app.clock("2026-11-05T19:25:00");
    app.wait_until("the label to show the new time", |app| {
        words(app, screen) == "19:25"
    });
    assert_eq!(label(&mut app, screen).accessible, "Current time, 19:25");
    let before = line(&mut app, screen);
    app.key("ctrl+Equal");
    app.pump(20);
    let label = label(&mut app, screen).rect;
    let line = line(&mut app, screen);
    assert_ne!(
        before, line,
        "the zoom did not move the line, so the test says nothing"
    );
    assert!(
        (label.middle_y() - line.middle_y()).abs() <= 2.0,
        "at the line's height after zoom: label {label:?}, line {line:?}"
    );
}

/// The hour numbers the zoom pill does not sit on (it hides those by its own rule, not the label's), by hour.
fn uncovered(app: &mut Door, screen: Screen) -> Vec<(usize, Seen)> {
    let pills: Vec<Rect> = app
        .read_all(&named_within("weekZoom", screen.page()))
        .iter()
        .map(|pill| pill.rect)
        .collect();
    let numbers = app.read_all(&named_within("hourLabel", screen.page()));
    assert_eq!(numbers.len(), 24, "{numbers:?}");
    let out: Vec<(usize, Seen)> = numbers
        .into_iter()
        .enumerate()
        .filter(|(_, number)| {
            !pills
                .iter()
                .any(|pill| number.rect.grown(2.0).overlaps(pill))
        })
        .collect();
    assert!(
        out.len() >= 20,
        "the pill hides too many numbers for this test to prove anything"
    );
    out
}

/// The clock moved, and the hours scrolled to the top so only the label can hide an hour number.
fn clock_at(app: &mut Door, screen: Screen, hour: u32, minute: u32) -> Seen {
    app.clock(&format!("2026-11-05T{hour:02}:{minute:02}:00"));
    let expected = format!("{hour}:{minute:02}");
    app.wait_until("the label to show the new time", |app| {
        words(app, screen) == expected
    });
    app.set_property(&named(screen.scroller()), "contentY", json!(0));
    app.pump(20);
    label(app, screen)
}

fn hides_only_the_number_under_it(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    for (hour, minute) in [(11, 0), (10, 58), (11, 3)] {
        let label = clock_at(&mut app, screen, hour, minute);
        assert!(shown(&label));
        let numbers = app.read_all(&named_within("hourLabel", screen.page()));
        assert_eq!(numbers[11].text, "11:00");
        assert!(
            label.rect.overlaps(&numbers[11].rect),
            "at {hour}:{minute:02} the fixture no longer overlaps"
        );
        assert!(
            !shown(&numbers[11]),
            "at {hour}:{minute:02} the hour number under the label is still drawn"
        );
        for (index, number) in uncovered(&mut app, screen) {
            if index != 11 {
                assert!(
                    shown(&number),
                    "at {hour}:{minute:02} the number for {index}:00 was hidden"
                );
            }
        }
    }
}

fn every_number_shows_between_two_hours(screen: Screen, name: &str) {
    let mut app = on_screen(name, screen);
    let label = clock_at(&mut app, screen, 11, 30);
    for (_, number) in uncovered(&mut app, screen) {
        assert!(
            !label.rect.overlaps(&number.rect),
            "the fixture overlaps the number {}",
            number.text
        );
        assert!(shown(&number), "the number {} was hidden", number.text);
    }
}

macro_rules! on_week_and_day {
    ($check:ident, $week:ident, $day:ident) => {
        #[test]
        #[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
        fn $week() {
            $check(Screen::Week, stringify!($week));
        }

        #[test]
        #[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
        fn $day() {
            $check(Screen::Day, stringify!($day));
        }
    };
}

on_week_and_day!(
    shows_the_24_hour_time,
    week_label_shows_the_time_in_the_24_hour_clock,
    day_label_shows_the_time_in_the_24_hour_clock
);
on_week_and_day!(
    shows_the_12_hour_time,
    week_label_shows_the_time_in_the_12_hour_clock,
    day_label_shows_the_time_in_the_12_hour_clock
);
on_week_and_day!(
    sits_at_the_line_in_the_hour_column,
    week_label_sits_in_the_hour_column_at_the_lines_height_and_covers_no_block,
    day_label_sits_in_the_hour_column_at_the_lines_height_and_covers_no_block
);
on_week_and_day!(
    moves_with_the_tick_and_with_zoom,
    week_label_moves_with_the_line_on_the_clock_tick_and_with_zoom,
    day_label_moves_with_the_line_on_the_clock_tick_and_with_zoom
);
on_week_and_day!(
    hides_only_the_number_under_it,
    week_hour_number_under_the_label_is_hidden_and_the_others_stay,
    day_hour_number_under_the_label_is_hidden_and_the_others_stay
);
on_week_and_day!(
    every_number_shows_between_two_hours,
    week_every_hour_number_shows_when_the_label_is_between_two_hours,
    day_every_hour_number_shows_when_the_label_is_between_two_hours
);

/// The preview week in Settings' Advanced look page is passive: it has the hours but no time label. (The
/// Python original looked on the Settings screen itself, where no preview is loaded, so it could not fail.)
#[test]
#[ignore = "starts the Python app through the test door (desktop/tests/door_app.py)"]
fn there_is_no_label_in_the_settings_preview_without_a_line() {
    let mut app = on_screen("now-label-settings", Screen::Week);
    app.click(&named("navSettings"));
    app.wait_until("the Settings screen", |app| {
        app.app()["screen"] == json!("settings")
    });
    app.reveal(&named("openAdvanced"));
    app.click(&named("openAdvanced"));
    app.wait_until("the preview week", |app| {
        app.read(&named("settingsPreviewWeek")).visible
    });
    app.pump(20);
    let labels = app.read_all(&named_within("nowLabel", "settingsPreviewWeek"));
    assert_eq!(
        labels.len(),
        1,
        "the preview week has its hours: {labels:?}"
    );
    assert!(!labels[0].visible, "a time label shows in the preview week");
}
