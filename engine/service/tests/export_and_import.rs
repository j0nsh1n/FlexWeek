//! Exporting an account to a file and importing it into another one (on another computer or server), and the
//! limits on both. The Rust twins of backend/tests/test_account_export_and_import.py (its hosted-server origin
//! goes with the server in P2; two separate databases stand for the two computers here).

use flexweek_service::accounts::{self, Asker, PASSWORD_WRONG, SignedIn};
use flexweek_service::homework_saves::save_homework;
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::records::save_routine;
use flexweek_service::transfer::{
    IMPORT_STALE, TRANSFER_TOO_LARGE, export_account, import_account, import_preview,
};
use flexweek_service::week_saves::save_week;
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const WEEK: &str = "2026-09-14";
const NOW: &str = "2026-11-05T19:00";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

/// Each account draws its own randomness, as the app's would be; `seed` keeps two accounts' draws apart.
fn sign_up(db: &TestDb, name: &str, seed: u64) -> SignedIn {
    accounts::register(
        &db.path,
        at(),
        &mut Counting(seed),
        name,
        PASSWORD,
        false,
        "",
    )
    .unwrap()
}

fn assignment(id: &str, title: &str, notes: Option<&str>) -> Value {
    let mut body = json!({
        "id": id, "title": title, "course": null, "category": "Homework", "priority": 3, "energy": "medium",
        "spotify_url": null, "due": "2026-09-16T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    });
    if let Some(notes) = notes {
        body["notes"] = json!(notes);
    }
    body
}

fn school() -> Value {
    json!({ "id": "school", "title": "School", "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
            "priority": 1, "energy": "medium", "start": "08:00", "category": "School" })
}

fn export(db: &TestDb, who: &SignedIn) -> Result<Value, ServiceError> {
    export_account(
        &db.path,
        at(),
        &who.account,
        &json!({ "password": PASSWORD }),
        NOW,
    )
}

fn listed(db: &TestDb, user: i64) -> Value {
    let now = flexweek_engine::plan::parse_moment(NOW).unwrap();
    views::homework(&db.path, user, WEEK, false, now).unwrap()
}

#[test]
fn an_export_needs_the_password_and_can_be_imported_on_another_computer() {
    let local = TestDb::new("transfer-local");
    let hosted = TestDb::new("transfer-hosted");
    let alice = sign_up(&local, "alice", 0);
    let user = alice.account.id;
    let mut prefs = read_preferences(&local.path, user).unwrap();
    prefs["theme"] = json!("nocturne");
    prefs["reminders_enabled"] = json!(false);
    prefs["alert_volume"] = json!(40);
    write_preferences(&local.path, user, &prefs).unwrap();
    save_homework(
        &local.path,
        user,
        "hw-essay",
        &assignment("hw-essay", "Essay", None),
    )
    .unwrap();
    let session = json!({ "id": "w1", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                          "priority": 3, "energy": "medium", "assignment_id": "hw-essay" });
    save_week(
        &local.path,
        user,
        &json!({ "week_start": WEEK, "blocks": [school(), session], "revision": 0 }),
    )
    .unwrap();
    let routine = json!({ "id": "r-1", "name": "School week", "revision": 0, "blocks": [{
        "template_id": "school", "title": "School", "days": [0, 1, 2, 3, 4], "start": "08:00", "duration_min": 390,
        "category": "School", "course": null, "priority": 1, "energy": "medium", "spotify_url": null }] });
    save_routine(&local.path, user, "r-1", &routine, NOW).unwrap();
    assert!(matches!(
        export_account(&local.path, at(), &alice.account, &json!({ "password": "wrong-password-12" }), NOW),
        Err(ServiceError::Refused(Refusal::Unauthorized(ref words))) if words == PASSWORD_WRONG
    ));
    let snapshot = export(&local, &alice).unwrap();
    assert_eq!(
        (
            &snapshot["format"],
            &snapshot["exported_at"],
            &snapshot["username"]
        ),
        (&json!(3), &json!(NOW), &json!("alice"))
    );
    let there = sign_up(&hosted, "hosted_alice", 100).account.id;
    let preview = import_preview(&hosted.path, there, &json!({ "snapshot": snapshot })).unwrap();
    assert_eq!(preview["source_username"], "alice");
    assert_eq!(preview["changes"]["weeks"]["added"], json!([WEEK]));
    assert_eq!(preview["changes"]["preferences_changed"], true);
    let given = json!({ "snapshot": snapshot, "state_token": preview["state_token"], "operation_id": "op-import-1" });
    let applied = import_account(&hosted.path, there, &given, "0123456789abcdef", NOW).unwrap();
    let theirs = read_preferences(&hosted.path, there).unwrap();
    assert_eq!(
        (&theirs["theme"], &theirs["alert_volume"]),
        (&json!("nocturne"), &json!(40))
    );
    assert_eq!(
        weeks::read_week(&hosted.path, there, WEEK).unwrap()["blocks"][0]["id"],
        "school"
    );
    assert_eq!(listed(&hosted, there)["assignments"][0]["title"], "Essay");
    assert_eq!(
        views::routines(&hosted.path, there).unwrap()["routines"][0]["name"],
        "School week"
    );
    assert_eq!(
        import_account(&hosted.path, there, &given, "fedcba9876543210", NOW).unwrap(),
        applied
    );
    let eve = sign_up(&hosted, "eve", 200).account.id;
    assert_eq!(listed(&hosted, eve), json!({ "assignments": [] }));
    assert_eq!(listed(&local, user)["assignments"][0]["title"], "Essay");
}

#[test]
fn an_import_preview_goes_stale_when_the_account_changes_before_applying() {
    let db = TestDb::new("transfer-stale");
    let alice = sign_up(&db, "alice", 0);
    let user = alice.account.id;
    let snapshot = export(&db, &alice).unwrap();
    let preview = import_preview(&db.path, user, &json!({ "snapshot": snapshot })).unwrap();
    save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK, "blocks": [school()], "revision": 0 }),
    )
    .unwrap();
    let given = json!({ "snapshot": snapshot, "state_token": preview["state_token"], "operation_id": "op-stale" });
    assert!(matches!(
        import_account(&db.path, user, &given, "0123456789abcdef", NOW),
        Err(ServiceError::Refused(Refusal::Conflict(ref words))) if words == IMPORT_STALE
    ));
}

#[test]
fn a_file_that_links_a_session_to_homework_it_does_not_hold_is_refused() {
    let db = TestDb::new("transfer-missing-homework");
    let alice = sign_up(&db, "alice", 0);
    let mut snapshot = export(&db, &alice).unwrap();
    snapshot["weeks"] = json!([{ "week_start": WEEK, "revision": 1, "blocks": [{
        "id": "w1", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0], "priority": 3,
        "energy": "medium", "assignment_id": "missing" }] }]);
    assert!(matches!(
        import_preview(&db.path, alice.account.id, &json!({ "snapshot": snapshot })),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

#[test]
fn an_export_holds_more_than_four_hundred_small_weeks() {
    let db = TestDb::new("transfer-many-weeks");
    let alice = sign_up(&db, "alice", 0);
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    let mut monday = chrono::NaiveDate::from_ymd_opt(2018, 1, 1).unwrap();
    for _ in 0..401 {
        conn.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[]', 0)",
            rusqlite::params![alice.account.id, monday.to_string()],
        )
        .unwrap();
        monday += chrono::Duration::weeks(1);
    }
    drop(conn);
    assert_eq!(
        export(&db, &alice).unwrap()["weeks"]
            .as_array()
            .unwrap()
            .len(),
        401
    );
}

#[test]
fn an_export_is_refused_when_importing_it_would_pass_the_transfer_limit() {
    let db = TestDb::new("transfer-too-large");
    let alice = sign_up(&db, "alice", 0);
    let notes = "n".repeat(4000);
    for index in 0..80 {
        let id = format!("hw-{index:03}");
        save_homework(
            &db.path,
            alice.account.id,
            &id,
            &assignment(&id, &format!("Item {index:03}"), Some(&notes)),
        )
        .unwrap();
    }
    assert!(matches!(
        export(&db, &alice),
        Err(ServiceError::Refused(Refusal::TooLarge(ref words))) if words == TRANSFER_TOO_LARGE
    ));
}
