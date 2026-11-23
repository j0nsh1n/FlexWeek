//! The standing week: School and activities from Setup are in every week from Setup's week on, in Week, Day
//! and Month alike; a change (sent as what it changes, from a date) reaches the open week on and leaves
//! earlier weeks as they were; an export carries it; an account from 0.18 gets one built from its weeks.
//! The Rust twins of backend/tests/test_standing_week_api.py.

use flexweek_engine::plan::parse_moment;
use flexweek_service::accounts::{self, Asker, SignedIn};
use flexweek_service::changes::apply_changes;
use flexweek_service::records::{create_restore_point, restore, restore_preview};
use flexweek_service::transfer::{export_account, import_account, import_preview};
use flexweek_service::{Refusal, ServiceError, views, week_saves, weeks};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const NOW: &str = "2026-11-05T19:00";
const SETUP_WEEK: &str = "2026-10-05";
const WEEK_BEFORE: &str = "2026-09-28";
const NEXT_WEEK: &str = "2026-10-12";
const WEEK_AFTER: &str = "2026-10-19";

fn school() -> Value {
    json!({ "id": "school", "title": "School", "kind": "locked", "category": "class", "start": "08:30",
            "duration_min": 405, "days": [0, 1, 2, 3, 4] })
}

fn soccer() -> Value {
    json!({ "id": "activity-1", "title": "Soccer", "kind": "locked", "category": "extra", "start": "16:00",
            "duration_min": 90, "days": [1, 3] })
}

fn gym() -> Value {
    json!({ "id": "gym", "title": "Gym", "kind": "locked", "start": "18:00", "duration_min": 60, "days": [2] })
}

fn with(block: Value, changes: Value) -> Value {
    let mut block = block;
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

/// Setup making a repeat: everything it needs, from that date on.
fn new(block: &Value, from_date: &str) -> Value {
    let mut set = serde_json::Map::new();
    for key in ["title", "category", "start", "duration_min"] {
        if let Some(value) = block.get(key) {
            set.insert(key.into(), value.clone());
        }
    }
    json!({ "id": block["id"], "scope": "from", "from_date": from_date, "set": set, "add_days": block["days"] })
}

fn change(id: &str, from_date: &str, set: Value, remove_days: Value) -> Value {
    json!({ "id": id, "scope": "from", "from_date": from_date, "set": set, "remove_days": remove_days })
}

fn stop(id: &str, from_date: &str) -> Value {
    json!({ "id": id, "scope": "from", "from_date": from_date, "stop": true })
}

/// The save Setup and School hours send: the open week's own blocks go in `weeks` (none here).
fn stand_request(db: &TestDb, user: i64, intents: Value) -> Result<Value, ServiceError> {
    apply_changes(
        &db.path,
        user,
        &json!({ "weeks": [], "repeats": intents }),
        "0123456789abcdef",
        NOW,
    )
}

fn stand(db: &TestDb, user: i64, intents: Value) -> Value {
    stand_request(db, user, intents).unwrap()
}

fn set_up(db: &TestDb, user: i64, blocks: &[Value]) -> Value {
    stand(
        db,
        user,
        Value::Array(blocks.iter().map(|block| new(block, SETUP_WEEK)).collect()),
    )
}

fn week(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

fn save(db: &TestDb, user: i64, week_start: &str, blocks: Value) -> Value {
    week_saves::save_week(
        &db.path,
        user,
        &json!({ "week_start": week_start, "blocks": blocks, "revision": 0 }),
    )
    .unwrap()
}

fn ids(week: &Value) -> Vec<String> {
    week["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["id"].as_str().unwrap().to_string())
        .collect()
}

/// Each block's start, length, days and missed days, by id.
fn times(blocks: &Value) -> std::collections::BTreeMap<String, (Value, Value, Value, Value)> {
    blocks
        .as_array()
        .unwrap()
        .iter()
        .map(|block| {
            let missed = match &block["missed_days"] {
                Value::Null => json!([]),
                days => days.clone(),
            };
            (
                block["id"].as_str().unwrap().to_string(),
                (
                    block["start"].clone(),
                    block["duration_min"].clone(),
                    block["days"].clone(),
                    missed,
                ),
            )
        })
        .collect()
}

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
        "2026-11-05T19:00",
    )
    .unwrap()
}

fn import(db: &TestDb, user: i64, snapshot: &Value) -> Result<Value, ServiceError> {
    let preview = import_preview(&db.path, user, &json!({ "snapshot": snapshot })).unwrap();
    import_account(
        &db.path,
        user,
        &json!({ "snapshot": snapshot, "state_token": preview["state_token"], "operation_id": "import-1" }),
        "fedcba9876543210",
        NOW,
    )
}

#[test]
fn every_week_from_setups_week_on_has_school_and_soccer() {
    let db = TestDb::new("standing-every");
    let ana = db.account("ana");
    set_up(&db, ana, &[school(), soccer()]);
    for later in [SETUP_WEEK, NEXT_WEEK, "2026-11-02"] {
        let got = week(&db, ana, later);
        assert_eq!(ids(&got), ["school", "activity-1"], "{later}");
        assert_eq!(got["revision"], 0, "{later}");
    }
    assert_eq!(week(&db, ana, WEEK_BEFORE)["blocks"], json!([]));
}

#[test]
fn day_and_month_see_the_standing_week() {
    let db = TestDb::new("standing-day-month");
    let ana = db.account("ana");
    set_up(&db, ana, &[school(), soccer()]);
    let now = parse_moment(NOW).unwrap();
    let tuesday = views::day(&db.path, ana, "2026-10-13", now).unwrap();
    let mut locked: Vec<&str> = tuesday["locked"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    locked.sort();
    assert_eq!(locked, ["activity-1", "school"]);
    let month = views::month(&db.path, ana, "2026-11", 0, now).unwrap();
    let chips = |date: &str| -> Vec<String> {
        let day = month["days"]
            .as_array()
            .unwrap()
            .iter()
            .find(|day| day["date"] == date)
            .unwrap();
        day["blocks"]
            .as_array()
            .unwrap()
            .iter()
            .map(|chip| chip["id"].as_str().unwrap().to_string())
            .collect()
    };
    assert_eq!(chips("2026-11-04"), ["school"], "a Wednesday");
    assert_eq!(chips("2026-11-05"), ["school", "activity-1"], "a Thursday");
    assert!(chips("2026-11-07").is_empty(), "a Saturday");
    let september = views::month(&db.path, ana, "2026-09", 0, now).unwrap();
    assert_eq!(september["days"][0]["blocks"], json!([]));
}

#[test]
fn a_weeks_own_missed_day_stays_in_that_week_only() {
    let db = TestDb::new("standing-missed");
    let ana = db.account("ana");
    set_up(&db, ana, &[school()]);
    save(
        &db,
        ana,
        NEXT_WEEK,
        json!([with(school(), json!({ "missed_days": [2] }))]),
    );
    assert_eq!(
        times(&week(&db, ana, NEXT_WEEK)["blocks"])["school"].3,
        json!([2])
    );
    assert_eq!(
        times(&week(&db, ana, WEEK_AFTER)["blocks"])["school"].3,
        json!([])
    );
}

#[test]
fn a_change_reaches_the_open_week_on_and_keeps_missed_days_still_school_days() {
    let db = TestDb::new("standing-change");
    let ana = db.account("ana");
    set_up(&db, ana, &[school(), soccer()]);
    save(
        &db,
        ana,
        WEEK_AFTER,
        json!([
            with(school(), json!({ "missed_days": [2, 4] })),
            soccer(),
            gym()
        ]),
    );
    let answer = stand(
        &db,
        ana,
        json!([change(
            "school",
            NEXT_WEEK,
            json!({ "start": "09:00", "duration_min": 360 }),
            json!([4])
        )]),
    );
    assert_eq!(answer["repeats"]["changed_weeks"], json!([WEEK_AFTER]));
    let setup = &times(&week(&db, ana, SETUP_WEEK)["blocks"])["school"];
    assert_eq!((&setup.0, &setup.1), (&json!("08:30"), &json!(405)));
    let next = &times(&week(&db, ana, NEXT_WEEK)["blocks"])["school"];
    assert_eq!((&next.0, &next.1), (&json!("09:00"), &json!(360)));
    let after = week(&db, ana, WEEK_AFTER);
    let after_times = times(&after["blocks"]);
    assert_eq!(
        after_times["school"],
        (json!("09:00"), json!(360), json!([0, 1, 2, 3]), json!([2]))
    );
    assert!(after_times.contains_key("gym"));
    assert_eq!(after["revision"], 2);
}

#[test]
fn a_change_to_the_standing_week_changes_only_the_blocks_it_names() {
    let db = TestDb::new("standing-only-named");
    let ana = db.account("ana");
    set_up(&db, ana, &[school(), soccer()]);
    let later = with(school(), json!({ "start": "09:00", "duration_min": 360 }));
    stand(
        &db,
        ana,
        json!([change(
            "school",
            NEXT_WEEK,
            json!({ "start": "09:00", "duration_min": 360 }),
            json!([])
        )]),
    );
    assert_eq!(
        times(&week(&db, ana, WEEK_AFTER)["blocks"]),
        times(&json!([later, soccer()]))
    );
    stand(&db, ana, json!([stop("activity-1", NEXT_WEEK)]));
    assert_eq!(
        times(&week(&db, ana, WEEK_AFTER)["blocks"]),
        times(&json!([later]))
    );
}

#[test]
fn only_setups_blocks_with_a_start_can_repeat_and_a_change_names_a_real_date() {
    let db = TestDb::new("standing-refused");
    let ana = db.account("ana");
    let mut with_body = new(&school(), SETUP_WEEK);
    with_body["body"] = school();
    for intents in [
        json!([new(&gym(), SETUP_WEEK)]),
        json!([new(&with(school(), json!({ "start": null })), SETUP_WEEK)]),
        json!([new(&school(), SETUP_WEEK), new(&school(), SETUP_WEEK)]),
        json!([new(&school(), "2026-10-32")]),
        json!([with_body]),
    ] {
        assert!(
            matches!(
                stand_request(&db, ana, intents.clone()),
                Err(ServiceError::Refused(Refusal::Invalid(_)))
            ),
            "{intents}"
        );
    }
    assert_eq!(week(&db, ana, NEXT_WEEK)["blocks"], json!([]));
    // A change names the date it holds from; weeks still start on Monday, so a Tuesday's change holds
    // from that week.
    stand(&db, ana, json!([new(&school(), "2026-10-06")]));
    assert_eq!(ids(&week(&db, ana, SETUP_WEEK)), ["school"]);
}

/// Setup's save: the open week holds School with Wednesday missed; School stands from it on, and the
/// answer shows the open week as Week would.
#[test]
fn the_open_weeks_save_and_the_standing_week_land_together() {
    let db = TestDb::new("standing-together");
    let ana = db.account("ana");
    let given = json!({
        "weeks": [{ "week_start": SETUP_WEEK, "blocks": [with(school(), json!({ "missed_days": [2] })), gym()],
                    "revision": 0 }],
        "repeats": [new(&school(), SETUP_WEEK), new(&soccer(), SETUP_WEEK)],
    });
    let saved =
        apply_changes(&db.path, ana, &given, "0123456789abcdef", NOW).unwrap()["weeks"][0].clone();
    assert_eq!(ids(&saved), ["school", "gym", "activity-1"]);
    assert_eq!(
        times(&week(&db, ana, NEXT_WEEK)["blocks"])["school"].3,
        json!([])
    );
}

#[test]
fn an_export_carries_the_standing_week_to_another_account() {
    let db = TestDb::new("standing-export");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let bea = sign_up(&db, &mut entropy, "bea");
    set_up(&db, ana.account.id, &[school(), soccer()]);
    stand(&db, ana.account.id, json!([stop("activity-1", WEEK_AFTER)]));
    let snapshot = export(&db, &ana);
    assert_eq!(snapshot["standing"].as_array().unwrap().len(), 3);
    import(&db, bea.account.id, &snapshot).unwrap();
    assert_eq!(
        ids(&week(&db, bea.account.id, NEXT_WEEK)),
        ["school", "activity-1"]
    );
    assert_eq!(ids(&week(&db, bea.account.id, WEEK_AFTER)), ["school"]);
}

/// Weekly fixed times (#118) join School and Setup's activities in the repeats; the export used to stop at
/// nine places, so the tenth repeat made an account that could not be exported or brought back.
#[test]
fn more_repeats_than_setup_makes_export_and_import_whole() {
    let db = TestDb::new("standing-many");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let bea = sign_up(&db, &mut entropy, "bea");
    let weekly: Vec<Value> = (0..12)
        .map(|n| json!({ "id": format!("weekly-{n:04}"), "title": format!("Practice {n}"), "kind": "locked",
                         "category": "extra", "start": "07:00", "duration_min": 30, "days": [n % 7] }))
        .collect();
    let mut blocks = vec![school()];
    blocks.extend(weekly.iter().cloned());
    set_up(&db, ana.account.id, &blocks);
    let snapshot = export(&db, &ana);
    assert_eq!(snapshot["standing"].as_array().unwrap().len(), 13);
    import(&db, bea.account.id, &snapshot).unwrap();
    let mut shown = ids(&week(&db, bea.account.id, NEXT_WEEK));
    shown.sort();
    let mut expected: Vec<String> = weekly
        .iter()
        .map(|block| block["id"].as_str().unwrap().to_string())
        .collect();
    expected.push("school".into());
    expected.sort();
    assert_eq!(shown, expected);
}

#[test]
fn an_import_with_more_than_two_hundred_repeats_at_once_is_refused() {
    let db = TestDb::new("standing-cap");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    set_up(&db, ana.account.id, &[school()]);
    let snapshot = export(&db, &ana);
    let school_row = snapshot["standing"][0].clone();
    let row = |n: usize, from_week: &str, body: bool| {
        let mut row = school_row.clone();
        let id = format!("weekly-{n:04}");
        row["id"] = json!(id);
        row["position"] = json!(n % 200);
        row["from_week"] = json!(from_week);
        row["body"] = if body {
            with(school_row["body"].clone(), json!({ "id": id }))
        } else {
            Value::Null
        };
        row
    };
    let rows: Vec<Value> = (0..200)
        .map(|n| row(n, school_row["from_week"].as_str().unwrap(), true))
        .collect();
    let preview = |standing: Vec<Value>| {
        let mut file = snapshot.clone();
        file["standing"] = Value::Array(standing);
        import_preview(&db.path, ana.account.id, &json!({ "snapshot": file }))
    };
    let mut at_the_limit = vec![school_row.clone()];
    at_the_limit.extend(rows[1..].iter().cloned());
    assert!(
        preview(at_the_limit).is_ok(),
        "200 at once is the limit itself"
    );
    let mut over = vec![school_row.clone()];
    over.extend(rows.iter().cloned());
    assert!(preview(over).is_err());
    // One that stops makes room for one that starts the same week.
    let mut stopped = rows[0].clone();
    stopped["from_week"] = json!(NEXT_WEEK);
    stopped["body"] = Value::Null;
    let starts = row(200, NEXT_WEEK, true);
    let mut swapped = rows.clone();
    swapped.extend([stopped, starts.clone()]);
    assert!(preview(swapped).is_ok());
    let mut added = rows.clone();
    added.push(starts);
    assert!(preview(added).is_err());
    // The 200th repeat takes place 199; a 201st place is refused.
    let mut place_200 = school_row.clone();
    place_200["position"] = json!(200);
    assert!(preview(vec![place_200]).is_err());
}

#[test]
fn an_export_from_before_the_standing_week_builds_one_on_import() {
    let db = TestDb::new("standing-old-file");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let bea = sign_up(&db, &mut entropy, "bea");
    save(
        &db,
        ana.account.id,
        SETUP_WEEK,
        json!([school(), soccer(), gym()]),
    );
    let mut snapshot = export(&db, &ana);
    snapshot.as_object_mut().unwrap().shift_remove("standing");
    import(&db, bea.account.id, &snapshot).unwrap();
    assert_eq!(
        ids(&week(&db, bea.account.id, NEXT_WEEK)),
        ["school", "activity-1"]
    );
}

#[test]
fn an_account_from_0_18_gets_its_standing_week_from_the_week_setup_ran_in() {
    let db = TestDb::new("standing-0-18");
    let ada = db.account("ada");
    save(&db, ada, WEEK_BEFORE, json!([gym()]));
    save(&db, ada, SETUP_WEEK, json!([school(), soccer()]));
    // As 0.18.5 left it: no standing table, preferences at version 2.
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    conn.execute_batch("DROP TABLE standing_blocks; UPDATE preferences SET prefs_version = 2;")
        .unwrap();
    drop(conn);
    // The app opening the database again.
    flexweek_store::initialize(&db.path, "2026-11-16").unwrap();
    assert_eq!(ids(&week(&db, ada, "2026-11-16")), ["school", "activity-1"]);
    assert_eq!(ids(&week(&db, ada, WEEK_BEFORE)), ["gym"]);
    assert_eq!(week(&db, ada, SETUP_WEEK)["revision"], 1);
}

fn restore_point(db: &TestDb, user: i64, label: &str, token: &str) -> String {
    let point = create_restore_point(
        &db.path,
        user,
        &json!({ "label": label, "operation_id": format!("point-{label}") }),
        token,
        NOW,
    )
    .unwrap();
    point["id"].as_str().unwrap().to_string()
}

fn restore_to(db: &TestDb, user: i64, point_id: &str, token: &str) -> Value {
    let preview = restore_preview(&db.path, user, point_id).unwrap();
    restore(
        &db.path,
        user,
        point_id,
        &json!({ "state_token": preview["state_token"], "operation_id": format!("restore-{point_id}") }),
        token,
        NOW,
    )
    .unwrap()
}

fn new_hours() -> Value {
    with(school(), json!({ "start": "09:00", "duration_min": 360 }))
}

fn new_hours_and_no_soccer() -> Value {
    json!([
        change(
            "school",
            NEXT_WEEK,
            json!({ "start": "09:00", "duration_min": 360 }),
            json!([])
        ),
        stop("activity-1", NEXT_WEEK)
    ])
}

#[test]
fn a_restore_point_brings_back_the_standing_week_it_was_made_with() {
    let db = TestDb::new("standing-restore");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let user = ana.account.id;
    set_up(&db, user, &[school(), soccer()]);
    let before = export(&db, &ana)["standing"].clone();
    let point = restore_point(&db, user, "Before new hours", "1111111111111111");
    stand(&db, user, new_hours_and_no_soccer());
    assert_eq!(
        times(&week(&db, user, WEEK_AFTER)["blocks"])
            .into_keys()
            .collect::<Vec<_>>(),
        ["school"]
    );
    let changed = export(&db, &ana)["standing"].clone();
    let recovery = restore_to(&db, user, &point, "2222222222222222")["recovery_id"]
        .as_str()
        .unwrap()
        .to_string();
    assert_eq!(export(&db, &ana)["standing"], before);
    assert_eq!(
        times(&week(&db, user, WEEK_AFTER)["blocks"]),
        times(&json!([school(), soccer()]))
    );
    // The point the restore made first holds the standing week the restore replaced.
    restore_to(&db, user, &recovery, "3333333333333333");
    assert_eq!(export(&db, &ana)["standing"], changed);
    assert_eq!(
        times(&week(&db, user, WEEK_AFTER)["blocks"]),
        times(&json!([new_hours()]))
    );
}

#[test]
fn a_restore_point_from_before_the_standing_week_leaves_the_current_one() {
    let db = TestDb::new("standing-old-point");
    let mut entropy = Counting(0);
    let ana = sign_up(&db, &mut entropy, "ana");
    let user = ana.account.id;
    set_up(&db, user, &[school(), soccer()]);
    let point = restore_point(&db, user, "Made by 0.18", "1111111111111111");
    // As 0.18.5 wrote a point: weeks and assignments, no standing rows.
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    let body: String = conn
        .query_row(
            "SELECT body FROM restore_points WHERE id = ?1",
            [&point],
            |row| row.get(0),
        )
        .unwrap();
    let mut snapshot: Value = serde_json::from_str(&body).unwrap();
    snapshot.as_object_mut().unwrap().shift_remove("standing");
    conn.execute(
        "UPDATE restore_points SET body = ?1 WHERE id = ?2",
        rusqlite::params![snapshot.to_string(), point],
    )
    .unwrap();
    drop(conn);
    stand(&db, user, new_hours_and_no_soccer());
    let changed = export(&db, &ana)["standing"].clone();
    restore_to(&db, user, &point, "2222222222222222");
    assert_eq!(export(&db, &ana)["standing"], changed);
    assert_eq!(
        times(&week(&db, user, WEEK_AFTER)["blocks"]),
        times(&json!([new_hours()]))
    );
}
