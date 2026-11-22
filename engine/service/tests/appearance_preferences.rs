//! Preference fields beyond the basics, as spec.md describes them: theme pack, accent, chips, motion,
//! alarm tone, planning style, time step, setup progress and the 24-hour clock. A value left at its
//! default stays off the answer, so an older app reads the account as before; a value outside its set is
//! refused. The Rust twins of backend/tests/test_appearance_preferences.py.

use std::path::PathBuf;

use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError, with_db};
use serde_json::{Map, Value, json};

const APPEARANCE: [&str; 4] = ["theme_pack", "accent", "accent_chips", "motion"];
const SETUP: [&str; 4] = ["alarm_tone", "planning_style", "drag_step_min", "setup"];

struct Db {
    dir: PathBuf,
    path: PathBuf,
    user: i64,
}

impl Drop for Db {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

/// A database with one account, made as sign-up makes it (its preferences row at today's version).
fn fresh(name: &str) -> Db {
    let dir = std::env::temp_dir().join(format!("flexweek-looks-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("looks.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    let user = with_db(&path, |conn| {
        let user = flexweek_store::insert_user(conn, "alice", "hash")?;
        flexweek_store::insert_preferences(conn, user, flexweek_store::PREFS_VERSION)?;
        Ok(user)
    })
    .unwrap();
    Db { dir, path, user }
}

/// What a new account's preferences answer holds.
fn defaults() -> Value {
    json!({
        "theme": "system", "reminders_enabled": true, "reminder_lead_min": 5, "reminder_sound": true,
        "reminder_dnd_override": false, "timer_work_min": 30, "timer_break_min": 15,
        "timer_long_break_min": 30, "timer_long_break_every": 4, "auto_split_pomodoro": false,
        "default_spotify_url": null, "alarms": [],
    })
}

fn with(changes: Value) -> Value {
    let mut out: Map<String, Value> = defaults().as_object().unwrap().clone();
    for (key, value) in changes.as_object().unwrap() {
        out.insert(key.clone(), value.clone());
    }
    Value::Object(out)
}

fn read(db: &Db) -> Value {
    read_preferences(&db.path, db.user).unwrap()
}

fn write(db: &Db, given: &Value) -> Value {
    write_preferences(&db.path, db.user, given).unwrap()
}

fn refused(db: &Db, given: &Value) {
    match write_preferences(&db.path, db.user, given) {
        Err(ServiceError::Refused(Refusal::Invalid(_))) => {}
        other => panic!("{given} was not refused: {other:?}"),
    }
}

fn lacks(answer: &Value, keys: &[&str]) {
    for key in keys {
        assert!(
            answer.get(*key).is_none(),
            "{key} is on the answer: {answer}"
        );
    }
}

#[test]
fn a_new_account_answers_the_defaults_without_the_appearance_or_setup_fields() {
    let db = fresh("new");
    let answer = read(&db);
    assert_eq!(answer, defaults());
    lacks(&answer, &APPEARANCE);
    lacks(&answer, &SETUP);
}

#[test]
fn an_older_app_saving_only_the_basics_still_gets_no_appearance_fields() {
    let db = fresh("old-app");
    assert_eq!(write(&db, &defaults()), defaults());
    assert_eq!(read(&db), defaults());
}

#[test]
fn an_unknown_field_an_accent_outside_the_set_and_an_unknown_motion_are_refused() {
    let db = fresh("unknown");
    refused(&db, &with(json!({ "linen": "graphite" })));
    refused(&db, &with(json!({ "accent": "indigo" })));
    refused(&db, &with(json!({ "motion": "more" })));
}

#[test]
fn appearance_fields_are_kept_and_going_back_to_the_defaults_drops_them() {
    let db = fresh("round-trip");
    let chosen = with(json!({
        "theme": "nocturne", "theme_pack": "dark-frost", "accent": "gold", "accent_chips": true,
        "motion": "extra",
    }));
    assert_eq!(write(&db, &chosen), chosen);
    assert_eq!(read(&db), chosen);
    assert_eq!(write(&db, &defaults()), defaults());
    lacks(&read(&db), &APPEARANCE);
}

#[test]
fn normal_motion_chosen_on_purpose_and_reduce_motion_are_kept() {
    let db = fresh("motion");
    write(&db, &with(json!({ "motion": "normal" })));
    assert_eq!(read(&db)["motion"], "normal");
    write(&db, &with(json!({ "motion": "reduce" })));
    assert_eq!(read(&db)["motion"], "reduce");
}

#[test]
fn a_theme_pack_keeps_the_theme_on_its_own_light_or_dark_side() {
    let db = fresh("pack");
    refused(
        &db,
        &with(json!({ "theme": "slate", "theme_pack": "dark-frost" })),
    );
    refused(
        &db,
        &with(json!({ "theme": "nocturne", "theme_pack": "light-frost" })),
    );
    let dark = write(
        &db,
        &with(json!({ "theme": "nocturne", "theme_pack": "dark-frost" })),
    );
    assert_eq!(
        (&dark["theme"], &dark["theme_pack"]),
        (&json!("nocturne"), &json!("dark-frost"))
    );
    let light = write(
        &db,
        &with(json!({ "theme": "slate", "theme_pack": "light-frost" })),
    );
    assert_eq!(light["theme_pack"], "light-frost");
}

#[test]
fn the_alarm_tone_planning_style_time_step_and_setup_progress_are_kept() {
    let db = fresh("setup");
    let chosen = with(json!({
        "alarm_tone": "glass", "planning_style": "manual", "drag_step_min": 5,
        "setup": { "version": 1, "step": 3, "finished_at": null },
    }));
    write(&db, &chosen);
    assert_eq!(read(&db), chosen);
    let finished = with(json!({
        "alarm_tone": "glass", "planning_style": "manual", "drag_step_min": 5,
        "setup": { "version": 1, "step": 6, "finished_at": "2026-09-22T16:30" },
    }));
    write(&db, &finished);
    assert_eq!(read(&db)["setup"]["finished_at"], "2026-09-22T16:30");
}

/// The answer leaves out a step of 15 (the app reads a missing step as 15); a chosen 5 is sent back,
/// also from a database opened again, and choosing 15 again takes it off the answer.
#[test]
fn a_chosen_5_minute_step_is_kept_and_15_stays_off_the_answer() {
    let db = fresh("step");
    lacks(&read(&db), &["drag_step_min"]);
    write(&db, &with(json!({ "drag_step_min": 5 })));
    assert_eq!(read(&db)["drag_step_min"], 5);
    write(&db, &with(json!({ "drag_step_min": 15 })));
    lacks(&read(&db), &["drag_step_min"]);
}

#[test]
fn a_setup_preference_outside_its_values_is_refused() {
    let db = fresh("setup-bad");
    for change in [
        json!({ "alarm_tone": "siren" }),
        json!({ "planning_style": "sometimes" }),
        json!({ "drag_step_min": 10 }),
        json!({ "drag_step_min": 1 }),
        json!({ "setup": { "version": 0, "step": 0 } }),
        json!({ "setup": { "version": 1, "step": 99 } }),
        json!({ "setup": { "version": 1, "step": 0, "finished_at": "yesterday" } }),
        json!({ "setup": { "version": 1, "step": 0, "extra": true } }),
    ] {
        refused(&db, &with(change));
    }
    assert_eq!(read(&db), defaults(), "a refused save changed something");
}

#[test]
fn the_clock_is_12_hour_unless_chosen_and_a_value_that_is_not_true_or_false_is_refused() {
    let db = fresh("clock");
    lacks(&read(&db), &["clock_24h"]);
    let twenty_four = with(json!({ "clock_24h": true }));
    write(&db, &twenty_four);
    assert_eq!(read(&db), twenty_four);
    write(&db, &with(json!({ "clock_24h": false })));
    lacks(&read(&db), &["clock_24h"]);
    refused(&db, &with(json!({ "clock_24h": "sometimes" })));
}
