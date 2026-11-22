//! Deleting an account (spec.md): it asks for that account's own password, removes every row the account
//! has and no other account's, ends its sessions, and frees the name for a new, empty account. The Rust
//! twins of backend/tests/test_delete_account.py.

use flexweek_engine::plan::parse_moment;
use flexweek_service::accounts::{self, Asker, PASSWORD_WRONG, SIGN_IN_WRONG, SignedIn};
use flexweek_service::{Refusal, ServiceError, records, views, weeks, with_db};
use flexweek_store::RoutineWrite;
use flexweek_testkit::{Counting, TestDb};
use serde_json::json;

const NOW: i64 = 1_793_000_000;
const WEEK: &str = "2026-09-14";
const ANA_PASSWORD: &str = "ana-long-password";
const BEN_PASSWORD: &str = "ben-long-password";

type Db = TestDb;

fn fresh(name: &str) -> Db {
    TestDb::new(name)
}

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: NOW,
    }
}

fn sign_up(db: &Db, entropy: &mut Counting, name: &str, password: &str) -> SignedIn {
    accounts::register(&db.path, at(), entropy, name, password, false, "").unwrap()
}

/// A week, a homework, a routine and a restore point, saved as the app saves them.
fn fill(db: &Db, user: i64, title: &str) {
    let block = json!([{
        "id": "school", "title": title, "kind": "locked", "duration_min": 390,
        "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "School",
    }]);
    let homework = json!({
        "id": "hw", "title": title, "course": null, "category": "Homework", "priority": 3,
        "energy": "medium", "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 60,
        "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
    });
    let routine = json!([{
        "template_id": "school", "title": "School", "days": [0, 1, 2, 3, 4], "start": "08:00",
        "duration_min": 390, "category": "School", "course": null, "priority": 1,
        "energy": "medium", "spotify_url": null,
    }]);
    with_db(&db.path, |conn| {
        flexweek_store::save_week(conn, user, WEEK, &block.to_string(), 0)?;
        flexweek_store::save_assignment(conn, user, "hw", &homework.to_string(), 0, 1000)?;
        flexweek_store::save_routine(
            conn,
            user,
            RoutineWrite {
                id: "r-1",
                name: "School week",
                body: &routine.to_string(),
                revision: 0,
                stamp: "2026-09-14T08:00",
                max_count: 50,
            },
        )?;
        Ok(())
    })
    .unwrap();
    let point = json!({ "label": "Keep me", "operation_id": "op-keep" });
    records::create_restore_point(
        &db.path,
        user,
        &point,
        &format!("p{user}"),
        "2026-09-14T08:00",
    )
    .unwrap();
}

fn rows(db: &Db, table: &str, user: i64) -> i64 {
    rusqlite::Connection::open(&db.path)
        .unwrap()
        .query_row(
            &format!("SELECT count(*) FROM {table} WHERE user_id = ?1"),
            [user],
            |row| row.get(0),
        )
        .unwrap()
}

fn week_titles(db: &Db, user: i64) -> Vec<String> {
    weeks::read_week(&db.path, user, WEEK).unwrap()["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["title"].as_str().unwrap().to_string())
        .collect()
}

fn homework_titles(db: &Db, user: i64) -> Vec<String> {
    let now = parse_moment("2026-09-14T08:00").unwrap();
    views::homework(&db.path, user, WEEK, true, now).unwrap()["assignments"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["title"].as_str().unwrap().to_string())
        .collect()
}

fn refusal<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn deleting_an_account_removes_all_of_its_rows_and_only_its_rows() {
    let db = fresh("rows");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana", ANA_PASSWORD);
    let ben = sign_up(&db, &mut entropy, "ben", BEN_PASSWORD);
    fill(&db, ana.account.id, "Ana school");
    fill(&db, ben.account.id, "Ben school");
    accounts::delete_account(&db.path, at(), &ana.account, ANA_PASSWORD).unwrap();
    assert!(accounts::signed_in(&db.path, &ana.token, NOW + 1, None).is_err());
    for table in [
        "weeks",
        "assignments",
        "routines",
        "restore_points",
        "sessions",
        "recovery_codes",
        "preferences",
    ] {
        assert_eq!(
            rows(&db, table, ana.account.id),
            0,
            "{table} kept Ana's rows"
        );
        assert!(
            rows(&db, table, ben.account.id) > 0,
            "{table} lost Ben's rows"
        );
    }
    let users: i64 = rusqlite::Connection::open(&db.path)
        .unwrap()
        .query_row("SELECT count(*) FROM users", [], |row| row.get(0))
        .unwrap();
    assert_eq!(users, 1);
    assert!(accounts::signed_in(&db.path, &ben.token, NOW + 1, None).is_ok());
    assert_eq!(week_titles(&db, ben.account.id), ["Ben school"]);
    let again = sign_up(&db, &mut entropy, "ana", ANA_PASSWORD);
    assert!(homework_titles(&db, again.account.id).is_empty());
}

#[test]
fn deleting_asks_for_the_accounts_own_password_and_frees_the_name_for_an_empty_account() {
    let db = fresh("password");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana", ANA_PASSWORD);
    let ben = sign_up(&db, &mut entropy, "ben", BEN_PASSWORD);
    fill(&db, ana.account.id, "Ana school");
    fill(&db, ben.account.id, "Ben school");
    assert_eq!(
        refusal(accounts::delete_account(
            &db.path,
            at(),
            &ben.account,
            ANA_PASSWORD
        )),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string()),
        "another account's password deleted Ben"
    );
    assert!(accounts::signed_in(&db.path, &ben.token, NOW + 1, None).is_ok());
    accounts::delete_account(&db.path, at(), &ben.account, BEN_PASSWORD).unwrap();
    assert!(accounts::signed_in(&db.path, &ben.token, NOW + 1, None).is_err());
    assert_eq!(
        refusal(accounts::login(
            &db.path,
            at(),
            &mut entropy,
            "ben",
            BEN_PASSWORD,
            false,
            ""
        )),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
    assert!(accounts::signed_in(&db.path, &ana.token, NOW + 1, None).is_ok());
    assert_eq!(week_titles(&db, ana.account.id), ["Ana school"]);
    assert_eq!(homework_titles(&db, ana.account.id), ["Ana school"]);
    let again = sign_up(&db, &mut entropy, "ben", BEN_PASSWORD);
    assert_eq!(
        weeks::read_week(&db.path, again.account.id, WEEK).unwrap(),
        json!({ "week_start": WEEK, "blocks": [], "revision": 0 })
    );
    assert!(homework_titles(&db, again.account.id).is_empty());
}
