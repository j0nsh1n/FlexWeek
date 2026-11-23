//! The clock in Settings is 12-hour for a new account, and 24-hour for every account that never chose before
//! the clock choice existed (24-hour used to be the default and was never stored). The update stamps 24-hour
//! onto each such account once, at start. With appearance_preferences.rs, transfer.rs and the store's
//! test_time_step_default.rs, the Rust twins of backend/tests/test_clock_default.py.

use flexweek_service::accounts::{self, Asker, SignedIn};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::transfer::export_account;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const THIS_WEEK: &str = "2026-11-02";
const NOW: &str = "2026-11-05T19:00";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn register(db: &TestDb, entropy: &mut Counting, name: &str) -> SignedIn {
    accounts::register(&db.path, at(), entropy, name, PASSWORD, false, "").unwrap()
}

/// A 12-hour clock is the default, so the answer leaves it off.
fn clock_of(db: &TestDb, user: i64) -> bool {
    read_preferences(&db.path, user).unwrap()["clock_24h"]
        .as_bool()
        .unwrap_or(false)
}

fn save_clock(db: &TestDb, user: i64, on: bool) {
    let mut prefs = read_preferences(&db.path, user).unwrap();
    prefs["clock_24h"] = json!(on);
    write_preferences(&db.path, user, &prefs).unwrap();
}

/// The account as the version before the clock choice left it: version 1, and comfort text that holds the
/// clock only when the student had saved Settings (which wrote every comfort key).
fn as_saved_before_the_clock_choice(db: &TestDb, user: i64, comfort: Option<Value>) {
    db.sql()
        .execute(
            "UPDATE preferences SET prefs_version = 1, comfort_json = ?1 WHERE user_id = ?2",
            rusqlite::params![comfort.unwrap_or(json!({})).to_string(), user],
        )
        .unwrap();
}

fn restart(db: &TestDb) {
    flexweek_store::initialize(&db.path, THIS_WEEK).unwrap();
}

#[test]
fn an_account_that_never_chose_before_the_update_keeps_24_hour() {
    let db = TestDb::new("clock-veteran");
    let veteran = register(&db, &mut Counting(0), "veteran").account.id;
    as_saved_before_the_clock_choice(&db, veteran, None);
    restart(&db);
    assert!(clock_of(&db, veteran));
}

#[test]
fn an_old_account_that_chose_12_hour_keeps_it_and_the_stamp_is_applied_once() {
    let db = TestDb::new("clock-chose");
    let mut entropy = Counting(0);
    let twelve = register(&db, &mut entropy, "twelve").account.id;
    let never = register(&db, &mut entropy, "never").account.id;
    as_saved_before_the_clock_choice(
        &db,
        twelve,
        Some(json!({ "clock_24h": false, "end_chime": true })),
    );
    as_saved_before_the_clock_choice(&db, never, None);
    restart(&db);
    restart(&db);
    assert!(!clock_of(&db, twelve));
    assert!(clock_of(&db, never));
    // A choice made after the update is not undone by the next start, and an account made after it keeps
    // its 12-hour clock. (The Python original checked only the first.)
    save_clock(&db, never, false);
    let fresh = register(&db, &mut entropy, "fresh").account.id;
    restart(&db);
    assert!(!clock_of(&db, never));
    assert!(!clock_of(&db, fresh));
}

#[test]
fn an_export_always_says_the_clock() {
    let db = TestDb::new("clock-export");
    let exporter = register(&db, &mut Counting(0), "exporter");
    let exported = || {
        export_account(
            &db.path,
            at(),
            &exporter.account,
            &json!({ "password": PASSWORD }),
            NOW,
        )
        .unwrap()["preferences"]["clock_24h"]
            .clone()
    };
    assert_eq!(exported(), false);
    save_clock(&db, exporter.account.id, true);
    assert_eq!(exported(), true);
}
