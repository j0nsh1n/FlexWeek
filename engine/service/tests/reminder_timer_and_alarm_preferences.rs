//! Preferences a student sets, as spec.md describes them: the theme, reminders, the focus timer, alarms and
//! the Spotify link, and the old databases they upgrade. The Rust twins of
//! backend/tests/test_reminder_timer_and_alarm_preferences.py.

use std::path::{Path, PathBuf};

use flexweek_engine::model::valid_spotify_url;
use flexweek_service::accounts::{self, Asker};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Map, Value, json};

const NOW: i64 = 1_793_000_000;
const WEEK: &str = "2026-11-16";

fn folder(name: &str) -> (TestDb, PathBuf) {
    let folder = TestDb::empty(name);
    let path = folder.path.clone();
    (folder, path)
}

fn sign_up(path: &Path, name: &str) -> i64 {
    let asker = Asker {
        address: "127.0.0.1",
        now: NOW,
    };
    accounts::register(
        path,
        asker,
        &mut Counting(0),
        name,
        "a-long-test-password",
        false,
        "",
    )
    .unwrap()
    .account
    .id
}

/// A new database with one account, as sign-up makes it.
fn account(name: &str) -> (TestDb, PathBuf, i64) {
    let (keep, path) = folder(name);
    flexweek_store::initialize(&path, WEEK).unwrap();
    let user = sign_up(&path, "alice");
    (keep, path, user)
}

/// A new account's preferences with the theme a test wants.
fn preferences(theme: &str) -> Value {
    json!({
        "theme": theme, "reminders_enabled": true, "reminder_lead_min": 5, "reminder_sound": true,
        "reminder_dnd_override": false, "timer_work_min": 30, "timer_break_min": 15,
        "timer_long_break_min": 30, "timer_long_break_every": 4, "auto_split_pomodoro": false,
        "default_spotify_url": null, "alarms": [],
    })
}

fn with(base: &Value, changes: Value) -> Value {
    let mut out: Map<String, Value> = base.as_object().unwrap().clone();
    out.extend(changes.as_object().unwrap().clone());
    Value::Object(out)
}

fn refused(path: &Path, user: i64, given: &Value) {
    match write_preferences(path, user, given) {
        Err(ServiceError::Refused(Refusal::Invalid(_))) => {}
        other => panic!("{given} was not refused: {other:?}"),
    }
}

#[test]
fn a_new_account_has_the_default_preferences() {
    let (_keep, path, user) = account("new");
    assert_eq!(
        read_preferences(&path, user).unwrap(),
        preferences("system")
    );
}

#[test]
fn reminder_choices_are_kept_and_a_lead_time_over_two_hours_is_refused() {
    let (_keep, path, user) = account("reminders");
    let chosen = with(
        &preferences("slate"),
        json!({ "reminders_enabled": false, "reminder_lead_min": 15, "reminder_sound": false }),
    );
    write_preferences(&path, user, &chosen).unwrap();
    assert_eq!(read_preferences(&path, user).unwrap(), chosen);
    refused(
        &path,
        user,
        &with(&chosen, json!({ "reminder_lead_min": 121 })),
    );
    assert_eq!(read_preferences(&path, user).unwrap(), chosen);
}

#[test]
fn the_theme_starts_as_system_and_only_system_slate_or_nocturne_are_kept() {
    let (_keep, path, user) = account("theme");
    assert_eq!(read_preferences(&path, user).unwrap()["theme"], "system");
    for theme in ["slate", "nocturne", "system"] {
        write_preferences(&path, user, &preferences(theme)).unwrap();
        assert_eq!(read_preferences(&path, user).unwrap()["theme"], theme);
    }
    for label in ["light", "dark", ""] {
        refused(&path, user, &preferences(label));
    }
}

#[test]
fn timer_alarm_and_spotify_choices_are_kept() {
    let (_keep, path, user) = account("timer");
    let chosen = with(
        &preferences("system"),
        json!({
            "timer_work_min": 45, "timer_break_min": 15, "auto_split_pomodoro": true,
            "reminder_dnd_override": true,
            "default_spotify_url": "https://open.spotify.com/playlist/abc123",
            "alarms": [{
                "id": "wake", "name": "Wake up", "time": "07:30", "days": [0, 2, 4], "enabled": true,
                "sound": "spotify", "spotify_url": "https://open.spotify.com/track/track123",
            }],
        }),
    );
    assert_eq!(write_preferences(&path, user, &chosen).unwrap(), chosen);
    assert_eq!(read_preferences(&path, user).unwrap(), chosen);
}

#[test]
fn a_link_that_is_not_spotify_or_an_alarm_at_25_00_is_refused() {
    let (_keep, path, user) = account("refused");
    let base = preferences("system");
    refused(
        &path,
        user,
        &with(
            &base,
            json!({ "default_spotify_url": "javascript:alert(1)" }),
        ),
    );
    let bad_alarm = json!({
        "id": "bad", "name": "Bad", "time": "25:00", "days": [0], "enabled": true, "sound": "chime",
    });
    refused(&path, user, &with(&base, json!({ "alarms": [bad_alarm] })));
}

/// The link check and the app's own (`safeSpotifyUrl`) accept exactly the same forms, so a link the
/// app showed is never wiped by the next save.
#[test]
fn a_spotify_link_is_accepted_exactly_in_the_forms_the_app_accepts() {
    for good in [
        "https://open.spotify.com/track/abc123",
        "https://open.spotify.com/playlist/xyz789/",
        "https://open.spotify.com/episode/aZ09?si=token",
    ] {
        assert_eq!(
            valid_spotify_url(Some(good)).unwrap().as_deref(),
            Some(good)
        );
    }
    for bad in [
        "HTTPS://OPEN.SPOTIFY.COM/track/abc123",
        "https://OPEN.spotify.com/track/abc123",
        "https://open.spotify.com//track/abc123",
        "https://open.spotify.com/track/abc 123",
        "https://user:pw@open.spotify.com/track/abc123",
        "https://open.spotify.com:443/track/abc123",
        "https://open.spotify.com/podcast/abc123",
        "http://open.spotify.com/track/abc123",
        "https://evil.example/track/abc123",
    ] {
        assert!(valid_spotify_url(Some(bad)).is_err(), "{bad} was accepted");
    }
}

#[test]
fn a_database_from_before_reminders_gains_them_turned_on() {
    let (_keep, path) = folder("legacy");
    rusqlite::Connection::open(&path)
        .unwrap()
        .execute_batch(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
            );
            CREATE TABLE weeks (
                user_id INTEGER NOT NULL, week_start TEXT NOT NULL, blocks TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY (user_id, week_start)
            );
            CREATE TABLE preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                theme TEXT NOT NULL DEFAULT 'nocturne'
            );
            CREATE TABLE auth_attempts (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);",
        )
        .unwrap();
    flexweek_store::initialize(&path, WEEK).unwrap();
    let user = sign_up(&path, "migrated");
    let prefs = read_preferences(&path, user).unwrap();
    assert_eq!(
        (
            &prefs["reminders_enabled"],
            &prefs["reminder_lead_min"],
            &prefs["reminder_sound"]
        ),
        (&json!(true), &json!(5), &json!(true))
    );
}

#[test]
fn opening_an_old_database_twice_adds_the_timer_and_alarm_columns_once() {
    let (_keep, path) = folder("twice");
    rusqlite::Connection::open(&path)
        .unwrap()
        .execute_batch(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE weeks (user_id INTEGER NOT NULL, week_start TEXT NOT NULL, blocks TEXT NOT NULL,
                revision INTEGER NOT NULL, PRIMARY KEY (user_id, week_start));
            CREATE TABLE preferences (user_id INTEGER PRIMARY KEY, theme TEXT NOT NULL DEFAULT 'nocturne',
                reminders_enabled INTEGER NOT NULL DEFAULT 0, reminder_lead_min INTEGER NOT NULL DEFAULT 5,
                reminder_sound INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE auth_attempts (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);",
        )
        .unwrap();
    flexweek_store::initialize(&path, WEEK).unwrap();
    flexweek_store::initialize(&path, WEEK).unwrap();
    let conn = rusqlite::Connection::open(&path).unwrap();
    let mut info = conn.prepare("PRAGMA table_info(preferences)").unwrap();
    let columns: Vec<String> = info
        .query_map([], |row| row.get(1))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    for wanted in ["timer_work_min", "alarms_json", "default_spotify_url"] {
        assert_eq!(
            columns.iter().filter(|name| *name == wanted).count(),
            1,
            "{wanted} in {columns:?}"
        );
    }
}
