//! Showing weekends, as spec.md describes it: on by default and then off the answer; the choice lives in
//! the planner's own column, never in the comfort settings, and a refused write keeps the saved choice. The
//! Rust twins of backend/tests/test_weekend_preferences.py.

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
    let dir = std::env::temp_dir().join(format!("flexweek-weekend-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("weekend.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    let user = with_db(&path, |conn| {
        let user = flexweek_store::insert_user(conn, "alice", "hash")?;
        flexweek_store::insert_preferences(conn, user, flexweek_store::PREFS_VERSION)?;
        Ok(user)
    })
    .unwrap();
    Db { dir, path, user }
}

fn sql(db: &Db) -> rusqlite::Connection {
    rusqlite::Connection::open(&db.path).unwrap()
}

fn column(db: &Db) -> i64 {
    sql(db)
        .query_row("SELECT show_weekends FROM preferences", [], |row| {
            row.get(0)
        })
        .unwrap()
}

fn comfort(db: &Db) -> Value {
    let text: String = sql(db)
        .query_row("SELECT comfort_json FROM preferences", [], |row| row.get(0))
        .unwrap();
    serde_json::from_str(&text).unwrap()
}

fn read(db: &Db) -> Value {
    read_preferences(&db.path, db.user).unwrap()
}

fn with(base: &Value, changes: Value) -> Value {
    let mut out: Map<String, Value> = base.as_object().unwrap().clone();
    out.extend(changes.as_object().unwrap().clone());
    Value::Object(out)
}

#[test]
fn weekends_are_kept_in_their_column_and_a_refused_write_keeps_the_choice() {
    let db = fresh("round-trip");
    let defaults = read(&db);
    assert!(defaults.get("show_weekends").is_none());
    assert_eq!(column(&db), 1);
    let hidden = with(&defaults, json!({ "show_weekends": false }));
    assert_eq!(
        write_preferences(&db.path, db.user, &hidden).unwrap()["show_weekends"],
        false
    );
    assert_eq!(read(&db)["show_weekends"], false);
    assert_eq!(column(&db), 0);
    assert!(comfort(&db).get("show_weekends").is_none());
    let bad = with(&defaults, json!({ "show_weekends": [] }));
    assert!(matches!(
        write_preferences(&db.path, db.user, &bad),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
    assert_eq!(read(&db)["show_weekends"], false);
    assert_eq!(column(&db), 0);
    let shown = with(&defaults, json!({ "show_weekends": true }));
    assert!(
        write_preferences(&db.path, db.user, &shown)
            .unwrap()
            .get("show_weekends")
            .is_none()
    );
    assert!(read(&db).get("show_weekends").is_none());
    assert_eq!(column(&db), 1);
    assert!(comfort(&db).get("show_weekends").is_none());
}

#[test]
fn a_weekend_value_left_in_the_comfort_settings_does_not_override_the_column() {
    for invalid in [json!(null), json!(0), json!("false"), json!([]), json!({})] {
        let db = fresh("comfort");
        sql(&db)
            .execute(
                "UPDATE preferences SET comfort_json = ?1",
                [json!({ "show_weekends": invalid }).to_string()],
            )
            .unwrap();
        assert!(read(&db).get("show_weekends").is_none(), "{invalid}");
        assert_eq!(column(&db), 1);
    }
}

#[test]
fn the_column_hides_weekends_even_when_the_comfort_settings_say_otherwise() {
    let db = fresh("column");
    sql(&db)
        .execute(
            "UPDATE preferences SET show_weekends = 0, comfort_json = ?1",
            [json!({ "show_weekends": true }).to_string()],
        )
        .unwrap();
    assert_eq!(read(&db)["show_weekends"], false);
    assert_eq!(column(&db), 0);
}
