//! Reminders are on unless the student turns them off (spec.md). Accounts made before 0.15 had them off
//! only because setup never asked, so opening such a database turns them on once; each account records
//! that it has been, so a student who turns them off afterwards stays off. The Rust twins of
//! backend/tests/test_reminders_default.py.

use std::path::{Path, PathBuf};

use flexweek_service::ServiceResult;
use flexweek_service::accounts::{self, Asker, Entropy};
use flexweek_service::preferences::{read_preferences, write_preferences};
use serde_json::json;

const NOW: i64 = 1_793_000_000;
const WEEK: &str = "2026-11-16";

/// The preferences table 0.14 made. Nothing in it records a one-time change.
const PREFERENCES_0_14: &str = "
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
    CREATE TABLE preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        theme TEXT NOT NULL DEFAULT 'system' CHECK(theme IN ('system', 'slate', 'nocturne')),
        reminders_enabled INTEGER NOT NULL DEFAULT 0 CHECK(reminders_enabled IN (0, 1)),
        reminder_lead_min INTEGER NOT NULL DEFAULT 5
            CHECK(reminder_lead_min >= 0 AND reminder_lead_min <= 120),
        reminder_sound INTEGER NOT NULL DEFAULT 1 CHECK(reminder_sound IN (0, 1)),
        reminder_dnd_override INTEGER NOT NULL DEFAULT 0 CHECK(reminder_dnd_override IN (0, 1)),
        timer_work_min INTEGER NOT NULL DEFAULT 30,
        timer_break_min INTEGER NOT NULL DEFAULT 15,
        timer_long_break_min INTEGER NOT NULL DEFAULT 30,
        timer_long_break_every INTEGER NOT NULL DEFAULT 4,
        auto_split_pomodoro INTEGER NOT NULL DEFAULT 0 CHECK(auto_split_pomodoro IN (0, 1)),
        default_spotify_url TEXT,
        alarms_json TEXT NOT NULL DEFAULT '[]',
        availability_json TEXT NOT NULL DEFAULT '{}',
        comfort_json TEXT NOT NULL DEFAULT '{}'
    );
";

/// Counts up, so every token, salt and code is new.
struct Counting(u64);

impl Entropy for Counting {
    fn session_token(&mut self) -> ServiceResult<String> {
        self.0 += 1;
        Ok(format!("token-{:040}", self.0))
    }
    fn salt(&mut self) -> ServiceResult<String> {
        self.0 += 1;
        Ok(format!("{:032x}", self.0))
    }
    fn code_bytes(&mut self) -> ServiceResult<[u8; 8]> {
        self.0 += 1;
        Ok(self.0.to_be_bytes())
    }
}

struct Folder(PathBuf);

impl Drop for Folder {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn folder(name: &str) -> (Folder, PathBuf) {
    let dir =
        std::env::temp_dir().join(format!("flexweek-reminders-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("reminders.db");
    (Folder(dir), path)
}

fn sign_up(path: &Path, name: &str) -> i64 {
    let asker = Asker {
        address: "127.0.0.1",
        now: NOW,
    };
    let made = accounts::register(
        path,
        asker,
        &mut Counting(0),
        name,
        "a-long-test-password",
        false,
        "",
    )
    .unwrap();
    made.account.id
}

fn reminders_on(path: &Path, user: i64) -> bool {
    read_preferences(path, user).unwrap()["reminders_enabled"] == json!(true)
}

fn columns(path: &Path) -> Vec<(i64, i64)> {
    let conn = rusqlite::Connection::open(path).unwrap();
    let mut rows = conn
        .prepare("SELECT user_id, reminders_enabled FROM preferences ORDER BY user_id")
        .unwrap();
    rows.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
        .unwrap()
        .map(Result::unwrap)
        .collect()
}

fn turn_off(path: &Path, user: i64) {
    let mut prefs = read_preferences(path, user).unwrap();
    prefs["reminders_enabled"] = json!(false);
    write_preferences(path, user, &prefs).unwrap();
}

#[test]
fn a_new_account_has_reminders_on() {
    let (_keep, path) = folder("new");
    flexweek_store::initialize(&path, WEEK).unwrap();
    let user = sign_up(&path, "fresh");
    assert!(reminders_on(&path, user));
}

#[test]
fn a_preferences_save_without_the_switch_leaves_reminders_on() {
    let (_keep, path) = folder("partial");
    flexweek_store::initialize(&path, WEEK).unwrap();
    let user = sign_up(&path, "partial");
    let saved = write_preferences(&path, user, &json!({ "theme": "slate" })).unwrap();
    assert_eq!(saved["reminders_enabled"], true);
}

#[test]
fn accounts_from_0_14_are_turned_on_once_and_a_later_choice_stands() {
    let (_keep, path) = folder("old");
    {
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(PREFERENCES_0_14).unwrap();
        for (id, name) in [(1, "skipped_setup"), (2, "said_no")] {
            conn.execute(
                "INSERT INTO users VALUES (?1, ?2, 'scrypt$placeholder')",
                rusqlite::params![id, name],
            )
            .unwrap();
            conn.execute(
                "INSERT INTO preferences(user_id, reminder_lead_min) VALUES (?1, 10)",
                [id],
            )
            .unwrap();
        }
    }
    flexweek_store::initialize(&path, WEEK).unwrap();
    assert_eq!(columns(&path), [(1, 1), (2, 1)]);
    let conn = rusqlite::Connection::open(&path).unwrap();
    let lead: i64 = conn
        .query_row(
            "SELECT reminder_lead_min FROM preferences WHERE user_id = 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(lead, 10, "turning reminders on changed the lead time");
    conn.execute(
        "UPDATE preferences SET reminders_enabled = 0 WHERE user_id = 2",
        [],
    )
    .unwrap();
    drop(conn);
    flexweek_store::initialize(&path, WEEK).unwrap();
    flexweek_store::initialize(&path, WEEK).unwrap();
    assert_eq!(columns(&path), [(1, 1), (2, 0)]);
}

#[test]
fn an_account_made_after_the_update_is_never_turned_on_again() {
    let (_keep, path) = folder("upgraded");
    rusqlite::Connection::open(&path)
        .unwrap()
        .execute_batch(PREFERENCES_0_14)
        .unwrap();
    flexweek_store::initialize(&path, WEEK).unwrap();
    let user = sign_up(&path, "newcomer");
    assert!(reminders_on(&path, user));
    turn_off(&path, user);
    flexweek_store::initialize(&path, WEEK).unwrap();
    assert!(!reminders_on(&path, user));
}
