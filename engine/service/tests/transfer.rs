//! Account export and import (Settings > Export my account, and Import): the file says the clock, reads back
//! as written, and an import replaces the account only as previewed, after a restore point, once per
//! operation. Part of these moved here from backend/tests/test_clock_default.py.

use flexweek_service::accounts::{self, Asker, PASSWORD_WRONG, SignedIn};
use flexweek_service::records::OPERATION_CONFLICT;
use flexweek_service::transfer::{
    IMPORT_STALE, check_transfer, export_account, import_account, import_preview,
};
use flexweek_service::{Refusal, ServiceError, week_saves, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const NOW: &str = "2026-11-22T10:00";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn sign_up(db: &TestDb, entropy: &mut Counting, name: &str) -> SignedIn {
    accounts::register(&db.path, at(), entropy, name, PASSWORD, false, "").unwrap()
}

fn export(db: &TestDb, who: &SignedIn) -> Value {
    export_account(
        &db.path,
        at(),
        &who.account,
        &json!({ "password": PASSWORD }),
        NOW,
    )
    .unwrap()
}

fn refused(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn titles(db: &TestDb, user: i64, week_start: &str) -> Vec<String> {
    weeks::read_week(&db.path, user, week_start).unwrap()["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["title"].as_str().unwrap().to_string())
        .collect()
}

fn club(db: &TestDb, user: i64, title: &str, revision: i64) {
    week_saves::save_week(
        &db.path,
        user,
        &json!({ "week_start": "2026-11-16", "revision": revision, "blocks": [{
            "id": "club", "title": title, "kind": "locked", "duration_min": 60, "days": [3],
            "start": "16:00", "category": "Club",
        }] }),
    )
    .unwrap();
}

/// The old build left a 24-hour clock out of its export file, as it did off the wire.
#[test]
fn a_file_from_before_0_18_5_without_a_clock_reads_24_hour_and_a_12_hour_file_keeps_its_clock() {
    let file = json!({
        "format": 3, "exported_at": "2026-10-01T09:00", "username": "veteran", "weeks": [],
        "assignments": [], "preferences": { "theme": "system" }, "routines": [],
    });
    assert_eq!(
        check_transfer(&file).unwrap()["preferences"]["clock_24h"],
        true
    );
    let mut twelve = file;
    twelve["preferences"]["clock_24h"] = json!(false);
    let read = check_transfer(&twelve).unwrap();
    assert!(
        !read["preferences"]
            .get("clock_24h")
            .is_some_and(|clock| clock == true),
        "a 12-hour file read as 24-hour: {}",
        read["preferences"]
    );
}

#[test]
fn an_export_says_the_clock_and_reads_back_as_the_same_12_hour_account() {
    let db = TestDb::new("export");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    club(&db, ana.account.id, "Chess", 0);
    let file = export(&db, &ana);
    assert_eq!(file["preferences"]["clock_24h"], false);
    assert_eq!(
        (&file["format"], &file["username"]),
        (&json!(3), &json!("ana"))
    );
    // Read back, the file is the same account with a 12-hour clock, which the answer leaves off as the
    // default: the file is not mistaken for one from before 0.18.5.
    let mut back = check_transfer(&file).unwrap();
    assert!(
        back["preferences"].get("clock_24h").is_none(),
        "{}",
        back["preferences"]
    );
    back["preferences"]["clock_24h"] = json!(false);
    assert_eq!(back, file);
    assert_eq!(
        refused(export_account(
            &db.path,
            at(),
            &ana.account,
            &json!({ "password": "not-the-password" }),
            NOW
        )),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string())
    );
}

#[test]
fn an_import_replaces_the_account_as_previewed_once_and_a_stale_preview_is_refused() {
    let db = TestDb::new("import");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let ben = sign_up(&db, &mut entropy, "ben");
    club(&db, ana.account.id, "Chess", 0);
    club(&db, ben.account.id, "Drama", 0);
    let file = export(&db, &ana);
    let preview = import_preview(&db.path, ben.account.id, &json!({ "snapshot": file })).unwrap();
    assert_eq!(preview["source_username"], "ana");
    let given =
        json!({ "snapshot": file, "state_token": preview["state_token"], "operation_id": "op-1" });
    let first = import_account(&db.path, ben.account.id, &given, "0123456789abcdef", NOW).unwrap();
    assert_eq!(first["recovery_id"], "rp-0123456789abcdef");
    assert_eq!(titles(&db, ben.account.id, "2026-11-16"), ["Chess"]);
    assert_eq!(
        titles(&db, ana.account.id, "2026-11-16"),
        ["Chess"],
        "Ana's account changed"
    );
    let again = import_account(&db.path, ben.account.id, &given, "fedcba9876543210", NOW).unwrap();
    assert_eq!(again, first, "the import ran twice");
    let mut other = given.clone();
    other["snapshot"]["preferences"]["theme"] = json!("nocturne");
    assert_eq!(
        refused(import_account(
            &db.path,
            ben.account.id,
            &other,
            "1111111111111111",
            NOW
        )),
        Refusal::Conflict(OPERATION_CONFLICT.to_string())
    );
    // Ben changes his week after the preview: that preview no longer describes the account.
    club(&db, ben.account.id, "Debate", 1);
    let mut late = given;
    late["operation_id"] = json!("op-2");
    assert_eq!(
        refused(import_account(
            &db.path,
            ben.account.id,
            &late,
            "2222222222222222",
            NOW
        )),
        Refusal::Conflict(IMPORT_STALE.to_string())
    );
    assert_eq!(titles(&db, ben.account.id, "2026-11-16"), ["Debate"]);
}

/// A file from before 0.19.0 has no standing week: School and Soccer were copied into each saved week. The
/// import builds the standing week from the newest saved week's Setup blocks, so a later week shows them.
#[test]
fn a_file_from_before_the_standing_week_gets_one_from_its_setup_blocks() {
    let db = TestDb::new("adopt");
    let mut entropy = Counting(0);
    let ben = sign_up(&db, &mut entropy, "ben");
    let cases: Value =
        serde_json::from_str(include_str!("../../store/tests/fixtures/repeat_cases.json")).unwrap();
    let mut file = export(&db, &ben);
    file.as_object_mut().unwrap().shift_remove("standing");
    file["weeks"] = json!([{ "week_start": "2026-11-16", "revision": 1,
                             "blocks": [cases["school"], cases["soccer"]] }]);
    let preview = import_preview(&db.path, ben.account.id, &json!({ "snapshot": file })).unwrap();
    import_account(
        &db.path,
        ben.account.id,
        &json!({ "snapshot": file, "state_token": preview["state_token"], "operation_id": "op-old" }),
        "0123456789abcdef",
        NOW,
    )
    .unwrap();
    assert_eq!(
        titles(&db, ben.account.id, "2026-11-30"),
        ["School", "Soccer"]
    );
}
