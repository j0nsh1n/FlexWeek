//! Making an account and signing in: what a new account starts with, names and passwords that make no
//! account, a sign-up the database refuses, the throttle on one name, and what a restart keeps. With
//! accounts.rs, the Rust twins of backend/tests/test_sign_up_and_sign_in.py. accounts.rs already holds the
//! twins of its "names are lower-cased and unique", "a taken name keeps the one account", "a wrong password
//! or an unknown name", "signing in after signing out" and "nine wrong passwords wait" tests. A body with an
//! extra field, and a refusal that never echoes the password back, are read by the server and go with it in
//! P2.

use flexweek_service::accounts::{self, Asker, INVALID_INPUT, SignedIn, TOO_MANY_TRIES};
use flexweek_service::preferences::read_preferences;
use flexweek_service::week_saves::save_week;
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const THIS_WEEK: &str = "2026-11-02";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn register(
    db: &TestDb,
    entropy: &mut Counting,
    name: &str,
    password: &str,
) -> Result<SignedIn, ServiceError> {
    accounts::register(&db.path, at(), entropy, name, password, false, "")
}

fn login(
    db: &TestDb,
    entropy: &mut Counting,
    name: &str,
    password: &str,
) -> Result<SignedIn, ServiceError> {
    accounts::login(&db.path, at(), entropy, name, password, false, "")
}

fn rows(db: &TestDb, table: &str) -> i64 {
    db.sql()
        .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
            row.get(0)
        })
        .unwrap()
}

fn flex(id: &str) -> Value {
    json!({ "id": id, "title": "Homework", "kind": "flexible", "duration_min": 60, "days": [0], "priority": 3,
            "energy": "medium", "earliest": null, "latest": null, "start": null, "course": null })
}

/// How a saved flexible block reads back after a restart: linked to the homework item made for it.
fn migrated(block: &Value, week_start: &str) -> Value {
    let mut body = block.clone();
    let id = block["id"].as_str().unwrap();
    body["latest"] = Value::Null;
    body["assignment_id"] = json!(format!(
        "a-{}",
        &flexweek_store::digest(&format!("{week_start}:{id}"))[..32]
    ));
    body
}

#[test]
fn a_new_account_starts_with_an_empty_week_and_the_default_preferences() {
    let db = TestDb::new("signup-new");
    let alice = register(&db, &mut Counting(0), "alice", PASSWORD).unwrap();
    assert_eq!(alice.account.username, "alice");
    assert_eq!(
        weeks::read_week(&db.path, alice.account.id, THIS_WEEK).unwrap(),
        json!({ "week_start": THIS_WEEK, "blocks": [], "revision": 0 })
    );
    assert_eq!(
        read_preferences(&db.path, alice.account.id).unwrap(),
        json!({
            "theme": "system", "reminders_enabled": true, "reminder_lead_min": 5, "reminder_sound": true,
            "reminder_dnd_override": false, "timer_work_min": 30, "timer_break_min": 15,
            "timer_long_break_min": 30, "timer_long_break_every": 4, "auto_split_pomodoro": false,
            "default_spotify_url": null, "alarms": [],
        })
    );
}

#[test]
fn a_bad_name_or_password_is_refused_and_makes_no_account() {
    let db = TestDb::new("signup-bad");
    let mut entropy = Counting(0);
    for (name, password) in [
        ("ab", PASSWORD),
        ("bad name", PASSWORD),
        ("okname", "short12"),
    ] {
        assert!(
            matches!(
                register(&db, &mut entropy, name, password),
                Err(ServiceError::Refused(Refusal::Invalid(ref words))) if words == INVALID_INPUT
            ),
            "{name:?} {password:?}"
        );
    }
    assert_eq!(rows(&db, "users"), 0);
}

#[test]
fn a_sign_up_the_database_refuses_at_the_preferences_leaves_no_rows() {
    let db = TestDb::new("signup-refused");
    db.sql()
        .execute_batch(
            "CREATE TRIGGER reject_preferences BEFORE INSERT ON preferences
             BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END",
        )
        .unwrap();
    assert!(register(&db, &mut Counting(0), "student", PASSWORD).is_err());
    for table in ["users", "weeks", "sessions"] {
        assert_eq!(rows(&db, table), 0, "{table}");
    }
}

#[test]
fn a_name_that_waits_leaves_other_names_free_to_sign_up() {
    let db = TestDb::new("signup-throttle");
    let mut entropy = Counting(0);
    register(&db, &mut entropy, "carol", PASSWORD).unwrap();
    for _ in 0..9 {
        assert!(login(&db, &mut entropy, "carol", "wrong-password-12").is_err());
    }
    assert!(matches!(
        login(&db, &mut entropy, "carol", PASSWORD),
        Err(ServiceError::Refused(Refusal::TooMany(ref words))) if words == TOO_MANY_TRIES
    ));
    assert!(register(&db, &mut entropy, "dave", PASSWORD).is_ok());
}

#[test]
fn accounts_weeks_and_the_session_survive_a_restart() {
    let db = TestDb::new("signup-restart");
    let mut entropy = Counting(0);
    let alice = register(&db, &mut entropy, "alice", PASSWORD).unwrap();
    save_week(
        &db.path,
        alice.account.id,
        &json!({ "week_start": THIS_WEEK, "blocks": [flex("a")], "revision": 0 }),
    )
    .unwrap();
    // The app starting again on the same file.
    flexweek_store::initialize(&db.path, THIS_WEEK).unwrap();
    assert_eq!(
        accounts::signed_in(&db.path, &alice.token, at().now + 1, None).unwrap(),
        alice.account
    );
    assert_eq!(
        weeks::read_week(&db.path, alice.account.id, THIS_WEEK).unwrap(),
        json!({ "week_start": THIS_WEEK, "blocks": [migrated(&flex("a"), THIS_WEEK)], "revision": 1 })
    );
    assert!(login(&db, &mut entropy, "alice", PASSWORD).is_ok());
}
