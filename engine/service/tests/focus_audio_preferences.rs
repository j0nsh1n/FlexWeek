//! Focus audio and the two focus rules, as spec.md describes them: "off", mute-on and complete-off are the
//! defaults and stay off the answer; a chosen sound or rule is kept, in the comfort column; anything else is
//! refused. The Rust twins of backend/tests/test_focus_audio.py.

use std::path::PathBuf;

use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError, with_db};
use serde_json::{Map, Value, json};

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

fn fresh(name: &str) -> Db {
    let dir = std::env::temp_dir().join(format!("flexweek-focus-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("focus.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    let user = with_db(&path, |conn| {
        let user = flexweek_store::insert_user(conn, "alice", "hash")?;
        flexweek_store::insert_preferences(conn, user, flexweek_store::PREFS_VERSION)?;
        Ok(user)
    })
    .unwrap();
    Db { dir, path, user }
}

fn with(changes: Value) -> Value {
    let mut out: Map<String, Value> = json!({
        "theme": "system", "reminders_enabled": true, "reminder_lead_min": 5, "reminder_sound": true,
        "reminder_dnd_override": false, "timer_work_min": 30, "timer_break_min": 15,
        "timer_long_break_min": 30, "timer_long_break_every": 4, "auto_split_pomodoro": false,
        "default_spotify_url": null, "alarms": [],
    })
    .as_object()
    .unwrap()
    .clone();
    out.extend(changes.as_object().unwrap().clone());
    Value::Object(out)
}

fn comfort(db: &Db) -> String {
    rusqlite::Connection::open(&db.path)
        .unwrap()
        .query_row("SELECT comfort_json FROM preferences", [], |row| row.get(0))
        .unwrap()
}

fn read(db: &Db) -> Value {
    read_preferences(&db.path, db.user).unwrap()
}

fn write(db: &Db, given: Value) -> Value {
    write_preferences(&db.path, db.user, &given).unwrap()
}

fn refused(db: &Db, given: Value) {
    match write_preferences(&db.path, db.user, &given) {
        Err(ServiceError::Refused(Refusal::Invalid(_))) => {}
        other => panic!("{given} was not refused: {other:?}"),
    }
}

#[test]
fn off_stays_off_the_answer_and_a_chosen_sound_is_kept() {
    let db = fresh("off");
    assert!(read(&db).get("focus_audio").is_none());
    refused(&db, with(json!({ "focus_audio": "vinyl" })));
    let saved = write(&db, with(json!({ "focus_audio": "spotify" })));
    assert_eq!(saved["focus_audio"], "spotify");
    assert_eq!(read(&db)["focus_audio"], "spotify");
    assert!(
        comfort(&db).contains(r#""focus_audio":"spotify""#),
        "{}",
        comfort(&db)
    );
    let quiet = write(&db, with(json!({ "focus_audio": "off" })));
    assert!(quiet.get("focus_audio").is_none());
    assert!(read(&db).get("focus_audio").is_none());
}

#[test]
fn each_ambient_sound_is_kept() {
    let db = fresh("sounds");
    for sound in ["rain", "lo-fi", "white-noise"] {
        assert_eq!(
            write(&db, with(json!({ "focus_audio": sound })))["focus_audio"],
            sound
        );
        assert_eq!(read(&db)["focus_audio"], sound);
    }
}

#[test]
fn the_focus_rules_default_to_mute_on_and_complete_off_and_a_choice_is_kept() {
    let db = fresh("rules");
    let fresh_answer = read(&db);
    assert!(fresh_answer.get("focus_auto_mute").is_none());
    assert!(fresh_answer.get("focus_auto_complete").is_none());
    let saved = write(
        &db,
        with(json!({ "focus_auto_mute": false, "focus_auto_complete": true })),
    );
    assert_eq!(
        (&saved["focus_auto_mute"], &saved["focus_auto_complete"]),
        (&json!(false), &json!(true))
    );
    let again = read(&db);
    assert_eq!(
        (&again["focus_auto_mute"], &again["focus_auto_complete"]),
        (&json!(false), &json!(true))
    );
    let stored = comfort(&db);
    assert!(
        stored.contains(r#""focus_auto_mute":false"#)
            && stored.contains(r#""focus_auto_complete":true"#),
        "{stored}"
    );
    let back = write(&db, with(json!({})));
    assert!(back.get("focus_auto_mute").is_none() && back.get("focus_auto_complete").is_none());
    refused(&db, with(json!({ "focus_auto_mute": "maybe" })));
}
