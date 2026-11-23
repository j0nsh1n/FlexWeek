//! Comfort and focus-timer preferences (Settings > Sounds, Window and Focus timer): defaults left off the
//! answer, range limits, the timer split preview, the timer presets, the reminder notes, and the screen the
//! app opens on. The Rust twins of backend/tests/test_comfort_and_timer_preferences_api.py (its "the routes
//! need a session" goes with the server in P2).
//!
//! The reminder notes follow the copy rule approved 2026-10-13 (the app's own words use contractions): the
//! Spotify note says "doesn't play" and the duplicate note "it's handled". The route serves these words from
//! the engine since P1; backend/comfort.py had kept its own older copy.

use flexweek_engine::plan::{reminder_limits, timer_presets};
use flexweek_service::comfort::split_preview;
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn defaults() -> Value {
    json!({
        "theme": "system", "reminders_enabled": true, "reminder_lead_min": 5, "reminder_sound": true,
        "reminder_dnd_override": false, "timer_work_min": 30, "timer_break_min": 15, "timer_long_break_min": 30,
        "timer_long_break_every": 4, "auto_split_pomodoro": false, "default_spotify_url": null, "alarms": [],
    })
}

fn with(changes: Value) -> Value {
    let mut prefs = defaults();
    for (key, value) in changes.as_object().unwrap() {
        prefs[key] = value.clone();
    }
    prefs
}

fn refused(result: Result<Value, ServiceError>) -> bool {
    matches!(result, Err(ServiceError::Refused(Refusal::Invalid(_))))
}

#[test]
fn a_new_account_answers_no_comfort_defaults() {
    let db = TestDb::new("comfort-new");
    let ana = db.account("ana");
    assert_eq!(read_preferences(&db.path, ana).unwrap(), defaults());
}

#[test]
fn comfort_choices_are_kept_and_values_out_of_range_are_refused() {
    let db = TestDb::new("comfort-round-trip");
    let ana = db.account("ana");
    let chosen = with(json!({
        "alert_volume": 40, "end_chime": true, "tray_notifications": false, "start_at_login": true,
        "preferred_view": "day", "sidebar_collapsed": true, "sidebar_width_px": 280,
    }));
    assert_eq!(write_preferences(&db.path, ana, &chosen).unwrap(), chosen);
    assert_eq!(read_preferences(&db.path, ana).unwrap(), chosen);
    assert_eq!(
        write_preferences(&db.path, ana, &defaults()).unwrap(),
        defaults()
    );
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(json!({ "alert_volume": 101 }))
    )));
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(json!({ "sidebar_width_px": 50 }))
    )));
}

#[test]
fn splitting_into_pomodoros_refuses_a_25_minute_work_length() {
    let db = TestDb::new("comfort-auto-split");
    let ana = db.account("ana");
    assert!(refused(write_preferences(
        &db.path,
        ana,
        &with(json!({ "timer_work_min": 25, "auto_split_pomodoro": true }))
    )));
    write_preferences(
        &db.path,
        ana,
        &with(json!({ "timer_work_min": 45, "auto_split_pomodoro": true })),
    )
    .unwrap();
    let loaded = read_preferences(&db.path, ana).unwrap();
    assert_eq!(
        (&loaded["timer_work_min"], &loaded["auto_split_pomodoro"]),
        (&json!(45), &json!(true))
    );
}

#[test]
fn the_timer_split_preview_rounds_to_the_grid_and_plans_a_90_minute_task_without_saving() {
    let db = TestDb::new("comfort-split-preview");
    let ana = db.account("ana");
    let preview = split_preview(&json!({
        "duration_min": 90, "timer_work_min": 25, "timer_break_min": 5, "timer_long_break_min": 15,
        "timer_long_break_every": 4,
    }))
    .unwrap();
    assert_eq!(
        preview,
        json!({
            "timer_work_min": 30, "timer_break_min": 15, "timer_long_break_min": 15, "timer_long_break_every": 4,
            "rounded": true,
            "message": "Work length 25 minutes becomes 30 on the 15-minute grid. Break length 5 minutes becomes 15 on the 15-minute grid.",
            "segments": [
                { "role": "work", "duration_min": 30, "index": 1 },
                { "role": "break", "duration_min": 15, "index": 1 },
                { "role": "work", "duration_min": 30, "index": 2 },
                { "role": "break", "duration_min": 15, "index": 2 },
                { "role": "work", "duration_min": 30, "index": 3 },
            ],
            "total_min": 120,
        })
    );
    let unchanged = read_preferences(&db.path, ana).unwrap();
    assert_eq!(unchanged["timer_work_min"], 30);
    assert!(unchanged.get("alert_volume").is_none());
}

#[test]
fn the_timer_presets_and_the_reminder_notes_are_the_contracts() {
    let preset = |id: &str, label: &str, work: i64| {
        json!({ "id": id, "label": label, "timer_work_min": work, "timer_break_min": 15, "timer_long_break_min": 30,
                "timer_long_break_every": 4 })
    };
    assert_eq!(
        timer_presets(),
        [
            preset("short", "Short", 15),
            preset("standard", "Standard", 30),
            preset("long", "Long", 45)
        ]
    );
    let notes: Value = serde_json::to_value(reminder_limits()).unwrap();
    assert_eq!(
        notes,
        json!({
            "web_open": "Reminders fire in this browser only while FlexWeek is open in a tab.",
            "desktop_background": "The desktop app can still alert from the tray after the window is closed.",
            "spotify": "A Spotify link is best-effort. FlexWeek plays a built-in sound if the track doesn't play.",
            "duplicate": "The same block start fires at most one reminder until it's handled or the day changes.",
        })
    );
}

#[test]
fn open_on_keeps_each_of_the_four_screens() {
    let db = TestDb::new("comfort-open-on");
    let ana = db.account("ana");
    for view in ["week", "day", "month", "myday"] {
        write_preferences(&db.path, ana, &with(json!({ "preferred_view": view }))).unwrap();
        assert_eq!(
            read_preferences(&db.path, ana).unwrap()["preferred_view"],
            view
        );
    }
}

#[test]
fn open_on_still_refuses_other_screens() {
    let db = TestDb::new("comfort-open-on-refused");
    let ana = db.account("ana");
    for view in ["year", "settings", ""] {
        assert!(
            refused(write_preferences(
                &db.path,
                ana,
                &with(json!({ "preferred_view": view }))
            )),
            "{view}"
        );
    }
}
