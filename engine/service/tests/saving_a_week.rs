//! Saving a week: two saves at once, saving the same week twice, what is refused, the fields that must
//! survive a save, and what a restart keeps. The Rust twins of backend/tests/test_saving_a_week.py (its
//! request-size limit, its removed demo address and its hosted-server setup go with the server in P2; the
//! two-device conflict it checked is kept below).

use flexweek_service::accounts::{self, Asker};
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::transfer::export_account;
use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const THIS_WEEK: &str = "2026-11-02";
const OLD_WEEK: &str = "2026-09-07";
const PASSWORD: &str = "a-long-test-password";

fn save(
    db: &TestDb,
    user: i64,
    week_start: &str,
    blocks: Value,
    revision: i64,
) -> Result<Value, ServiceError> {
    save_week(
        &db.path,
        user,
        &json!({ "week_start": week_start, "blocks": blocks, "revision": revision }),
    )
}

fn read(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

fn with(block: &Value, changes: Value) -> Value {
    let mut block = block.clone();
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

fn task(title: &str) -> Value {
    json!({ "id": "task", "title": title, "kind": "flexible", "duration_min": 60, "days": [0] })
}

#[test]
fn two_different_saves_at_once_keep_one_and_refuse_the_other() {
    let db = TestDb::new("save-race");
    let shared = &db;
    let ana = db.account("ana");
    let results: Vec<(Result<Value, ServiceError>, &str)> = std::thread::scope(|scope| {
        let handles: Vec<_> = ["Math", "History"]
            .into_iter()
            .map(|title| {
                scope.spawn(move || (save(shared, ana, THIS_WEEK, json!([task(title)]), 0), title))
            })
            .collect();
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .collect()
    });
    let won: Vec<&str> = results
        .iter()
        .filter(|(result, _)| result.is_ok())
        .map(|(_, title)| *title)
        .collect();
    assert_eq!(won.len(), 1, "{results:?}");
    let lost = results.iter().find(|(result, _)| result.is_err()).unwrap();
    assert!(
        matches!(lost.0, Err(ServiceError::Refused(Refusal::Conflict(ref words))) if words == WEEK_CONFLICT)
    );
    let saved = read(&db, ana, THIS_WEEK);
    assert_eq!(saved["revision"], 1);
    assert_eq!(saved["blocks"][0]["title"], won[0]);
}

#[test]
fn saving_the_same_week_twice_is_one_revision_and_a_bad_save_never_replaces_it() {
    let db = TestDb::new("save-twice");
    let ana = db.account("ana");
    let block = task("Math");
    assert_eq!(
        save(&db, ana, THIS_WEEK, json!([block]), 0).unwrap()["revision"],
        1
    );
    assert_eq!(
        save(&db, ana, THIS_WEEK, json!([block]), 0).unwrap()["revision"],
        1
    );
    let hundred_and_one: Vec<Value> = (0..101)
        .map(|n| with(&block, json!({ "id": n.to_string() })))
        .collect();
    for blocks in [
        json!([with(&block, json!({ "days": [7] }))]),
        json!([with(&block, json!({ "title": "x".repeat(81) }))]),
        json!([with(&block, json!({ "latest": "invalid" }))]),
        json!([with(
            &block,
            json!({ "kind": "locked", "start": "23:30", "duration_min": 60 })
        )]),
        json!([block, block]),
        Value::Array(hundred_and_one),
    ] {
        assert!(matches!(
            save(&db, ana, THIS_WEEK, blocks, 1),
            Err(ServiceError::Refused(Refusal::Invalid(_)))
        ));
    }
    let saved = read(&db, ana, THIS_WEEK);
    assert_eq!(saved["revision"], 1);
    assert_eq!(saved["blocks"].as_array().unwrap().len(), 1);
    assert_eq!(saved["blocks"][0]["title"], "Math");
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    let empty = plan(&db.path, ana, &json!({ "blocks": [] }), &start_clock).unwrap();
    assert_eq!(
        (&empty["placed"], &empty["unplaced"]),
        (&json!([]), &json!([]))
    );
}

#[test]
fn a_done_block_keeps_its_done_day_and_category() {
    let db = TestDb::new("save-done");
    let ana = db.account("ana");
    let block = json!({ "id": "hw", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                        "priority": 3, "energy": "medium", "completed": true, "completed_day": 0,
                        "start": "09:00", "category": "assignments" });
    save(&db, ana, OLD_WEEK, json!([block]), 0).unwrap();
    let loaded = read(&db, ana, OLD_WEEK)["blocks"][0].clone();
    assert_eq!(
        (
            &loaded["completed"],
            &loaded["completed_day"],
            &loaded["category"]
        ),
        (&json!(true), &json!(0), &json!("assignments"))
    );
}

#[test]
fn a_weekly_times_until_date_survives_a_save_and_a_bad_one_is_refused() {
    let db = TestDb::new("save-until");
    let ana = db.account("ana");
    let guitar = json!({ "id": "weekly-3f2a9c01", "title": "Guitar", "kind": "locked", "duration_min": 60,
                         "days": [1, 3], "start": "17:00", "until": "2026-12-31" });
    save(&db, ana, OLD_WEEK, json!([guitar]), 0).unwrap();
    let loaded: Vec<(Value, Value)> = read(&db, ana, OLD_WEEK)["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| (block["id"].clone(), block["until"].clone()))
        .collect();
    assert_eq!(loaded, [(json!("weekly-3f2a9c01"), json!("2026-12-31"))]);
    let bad = with(&guitar, json!({ "until": "31/12/2026" }));
    assert!(matches!(
        save(&db, ana, OLD_WEEK, json!([bad]), 1),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
    assert_eq!(read(&db, ana, OLD_WEEK)["blocks"][0]["until"], "2026-12-31");
}

#[test]
fn focus_and_pomodoro_fields_survive_a_save_and_a_bad_link_or_overlap_is_refused() {
    let db = TestDb::new("save-focus");
    let ana = db.account("ana");
    let block = json!({
        "id": "essay-focus-1", "title": "Essay focus 1/2", "kind": "locked", "duration_min": 30, "days": [0],
        "priority": 3, "energy": "medium", "start": "16:00", "spotify_url": "https://open.spotify.com/album/album123",
        "focus_sessions": 2, "focus_minutes": 60, "pomodoro_parent_id": "essay", "pomodoro_role": "work",
        "pomodoro_index": 1,
    });
    save(&db, ana, OLD_WEEK, json!([block]), 0).unwrap();
    let loaded = read(&db, ana, OLD_WEEK)["blocks"][0].clone();
    for (key, value) in block.as_object().unwrap() {
        assert_eq!(&loaded[key], value, "{key}");
    }
    let unsafe_link = with(
        &block,
        json!({ "spotify_url": "https://evil.example/track/album123" }),
    );
    assert!(matches!(
        save(&db, ana, OLD_WEEK, json!([unsafe_link]), 1),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
    let parent = json!({ "id": "essay", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                         "priority": 3, "energy": "medium" });
    assert!(matches!(
        save(&db, ana, OLD_WEEK, json!([parent, block]), 1),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
    assert_eq!(read(&db, ana, OLD_WEEK)["blocks"][0]["id"], "essay-focus-1");
}

#[test]
fn a_17_minute_block_survives_a_restart_and_the_account_still_exports() {
    let db = TestDb::new("save-restart");
    let at = Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    };
    let mut entropy = Counting(0);
    let student =
        accounts::register(&db.path, at, &mut entropy, "student", PASSWORD, false, "").unwrap();
    let reading = json!({ "id": "b17", "title": "Reading", "kind": "flexible", "duration_min": 17, "days": [0] });
    save(&db, student.account.id, THIS_WEEK, json!([reading]), 0).unwrap();
    // The app opening the database again.
    flexweek_store::initialize(&db.path, THIS_WEEK).unwrap();
    let signed_in =
        accounts::login(&db.path, at, &mut entropy, "student", PASSWORD, false, "").unwrap();
    let snapshot = export_account(
        &db.path,
        at,
        &signed_in.account,
        &json!({ "password": PASSWORD }),
        "2026-11-05T19:00",
    )
    .unwrap();
    assert_eq!(snapshot["assignments"], json!([]));
    let as_typed = |blocks: &Value| -> Vec<Value> {
        blocks
            .as_array()
            .unwrap()
            .iter()
            .map(|block| {
                assert!(block["assignment_id"].is_null(), "{block}");
                let mut typed = serde_json::Map::new();
                for key in reading.as_object().unwrap().keys() {
                    typed.insert(key.clone(), block[key].clone());
                }
                Value::Object(typed)
            })
            .collect()
    };
    let week = snapshot["weeks"]
        .as_array()
        .unwrap()
        .iter()
        .find(|week| week["week_start"] == THIS_WEEK)
        .unwrap();
    assert_eq!(as_typed(&week["blocks"]), std::slice::from_ref(&reading));
    assert_eq!(
        as_typed(&read(&db, student.account.id, THIS_WEEK)["blocks"]),
        [reading]
    );
}

#[test]
fn two_devices_signed_in_to_one_account_share_a_week_and_the_stale_one_is_refused() {
    let db = TestDb::new("save-two-devices");
    let ana = db.account("ana");
    let school = json!({ "id": "school", "title": "School", "kind": "locked", "duration_min": 390,
                         "days": [0, 1, 2, 3, 4], "priority": 1, "energy": "medium", "start": "08:00",
                         "category": "School" });
    save(&db, ana, "2026-09-14", json!([school]), 0).unwrap();
    let seen = read(&db, ana, "2026-09-14");
    assert_eq!(
        (&seen["blocks"][0]["id"], &seen["revision"]),
        (&json!("school"), &json!(1))
    );
    assert_eq!(
        refused(save(&db, ana, "2026-09-14", json!([]), 0).unwrap_err()),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
}

fn refused(error: ServiceError) -> Refusal {
    match error {
        ServiceError::Refused(refusal) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}
