//! Two accounts that hold rows under the same ids: each reads, plans and saves only its own. Each test makes
//! two accounts, acts as one of them, and checks that no read shows rows of the other. The Rust twins of
//! backend/tests/test_two_accounts_stay_apart.py (its "a request with no session is asked to sign in" checks
//! go with the server in P2).

use flexweek_engine::plan::parse_moment;
use flexweek_service::homework_saves::{SPREAD_DONE, save_homework, spread_preview};
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::records::HOMEWORK_UNKNOWN;
use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const THIS_WEEK: &str = "2026-11-02";
const WEEK_1: &str = "2026-09-14";
const WEEK_2: &str = "2026-09-21";
const NOW: &str = "2026-11-05T19:00";

fn flex(id: &str, changes: Value) -> Value {
    let mut block = json!({ "id": id, "title": "Homework", "kind": "flexible", "duration_min": 60, "days": [0],
                            "priority": 3, "energy": "medium", "earliest": null, "latest": null, "start": null,
                            "course": null });
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

/// How a saved flexible block reads back: linked to the homework the save made for it.
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

fn homework(title: &str, estimate: i64, due: &str, revision: i64) -> Value {
    json!({ "id": "hw", "title": title, "course": null, "category": "Homework", "priority": 3, "energy": "medium",
            "spotify_url": null, "due": due, "estimate_min": estimate, "focus_minutes": 0, "focus_sessions": 0,
            "completed": false, "completed_at": null, "revision": revision })
}

fn monday_school(title: &str) -> Value {
    json!({ "id": "school", "title": title, "kind": "locked", "duration_min": 390, "days": [0], "priority": 1,
            "energy": "medium", "start": "08:00", "category": "School" })
}

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

fn titles(items: &Value) -> Vec<String> {
    items
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["title"].as_str().unwrap().to_string())
        .collect()
}

/// The school weeks and homework both accounts hold under the same ids.
fn two_filled(db: &TestDb) -> (i64, i64) {
    let ana = db.account("alice");
    let ben = db.account("bob");
    save(db, ana, WEEK_1, json!([monday_school("Alice school")]), 0).unwrap();
    assert_eq!(
        save(
            db,
            ana,
            WEEK_1,
            json!([monday_school("Alice school, later")]),
            1
        )
        .unwrap()["revision"],
        2
    );
    save(db, ana, WEEK_2, json!([monday_school("Alice again")]), 0).unwrap();
    assert_eq!(
        save(db, ben, WEEK_1, json!([monday_school("Bob school")]), 0).unwrap()["revision"],
        1
    );
    save_homework(
        &db.path,
        ana,
        "hw",
        &homework("Alice essay", 120, "2026-09-15T23:59", 0),
    )
    .unwrap();
    save_homework(
        &db.path,
        ben,
        "hw",
        &homework("Bob lab", 60, "2026-09-22T12:00", 0),
    )
    .unwrap();
    (ana, ben)
}

#[test]
fn two_accounts_keep_their_own_weeks_and_preferences() {
    let db = TestDb::new("apart-weeks");
    let ana = db.account("alice");
    let mine = flex("a-hw", json!({ "title": "Alice homework" }));
    assert_eq!(
        save(&db, ana, THIS_WEEK, json!([mine]), 0).unwrap()["revision"],
        1
    );
    // Bob opening the app in a second window starts it again, and starting runs the one-time change that
    // links Alice's saved flexible block to a homework of its own; Bob's block, saved after, stays as typed.
    flexweek_store::initialize(&db.path, THIS_WEEK).unwrap();
    let ben = db.account("bob");
    assert_eq!(
        read(&db, ben, THIS_WEEK),
        json!({ "week_start": THIS_WEEK, "blocks": [], "revision": 0 })
    );
    let theirs = flex(
        "b-hw",
        json!({ "title": "Bob homework", "duration_min": 30, "days": [1] }),
    );
    save(&db, ben, THIS_WEEK, json!([theirs]), 0).unwrap();
    assert!(matches!(
        save(&db, ana, THIS_WEEK, json!([flex("a-x", json!({}))]), 0),
        Err(ServiceError::Refused(Refusal::Conflict(ref words))) if words == WEEK_CONFLICT
    ));
    assert_eq!(
        read(&db, ana, THIS_WEEK),
        json!({ "week_start": THIS_WEEK, "blocks": [migrated(&mine, THIS_WEEK)], "revision": 1 })
    );
    assert_eq!(
        read(&db, ben, THIS_WEEK),
        json!({ "week_start": THIS_WEEK, "blocks": [theirs], "revision": 1 })
    );
    let mut slate = read_preferences(&db.path, ana).unwrap();
    let defaults = slate.clone();
    slate["theme"] = json!("slate");
    write_preferences(&db.path, ana, &slate).unwrap();
    assert_eq!(read_preferences(&db.path, ana).unwrap(), slate);
    assert_eq!(read_preferences(&db.path, ben).unwrap(), defaults);
    let extra = flex("a-second", json!({ "duration_min": 30, "days": [2] }));
    assert_eq!(
        save(&db, ana, THIS_WEEK, json!([mine, extra]), 1).unwrap()["revision"],
        2
    );
    assert_eq!(read(&db, ben, THIS_WEEK)["blocks"], json!([theirs]));
}

#[test]
fn week_homework_day_and_month_reads_stay_with_their_account() {
    let db = TestDb::new("apart-reads");
    let (ana, ben) = two_filled(&db);
    let week_a = read(&db, ana, WEEK_1);
    let week_b = read(&db, ben, WEEK_1);
    assert_eq!(
        (&week_a["revision"], titles(&week_a["blocks"])),
        (&json!(2), vec!["Alice school, later".to_string()])
    );
    assert_eq!(
        (&week_b["revision"], titles(&week_b["blocks"])),
        (&json!(1), vec!["Bob school".to_string()])
    );
    assert_eq!(
        read(&db, ben, WEEK_2),
        json!({ "week_start": WEEK_2, "blocks": [], "revision": 0 })
    );
    assert_eq!(
        weeks::list_weeks(&db.path, ana).unwrap(),
        json!({ "weeks": [WEEK_1, WEEK_2] })
    );
    assert_eq!(
        weeks::list_weeks(&db.path, ben).unwrap(),
        json!({ "weeks": [WEEK_1] })
    );
    let now = parse_moment(NOW).unwrap();
    let listed = |user: i64| -> Vec<(Value, Value)> {
        views::homework(&db.path, user, WEEK_1, false, now).unwrap()["assignments"]
            .as_array()
            .unwrap()
            .iter()
            .map(|item| (item["title"].clone(), item["estimate_min"].clone()))
            .collect()
    };
    assert_eq!(listed(ana), [(json!("Alice essay"), json!(120))]);
    assert_eq!(listed(ben), [(json!("Bob lab"), json!(60))]);
    // Monday 14 September: Alice's essay is due the next day, Bob's lab a week later.
    let day_a = views::day(&db.path, ana, "2026-09-14", now).unwrap();
    let day_b = views::day(&db.path, ben, "2026-09-14", now).unwrap();
    assert_eq!(titles(&day_a["due_soon"]), ["Alice essay"]);
    assert_eq!(day_b["due_soon"], json!([]));
    assert_eq!(titles(&day_a["locked"]), ["Alice school, later"]);
    assert_eq!(titles(&day_b["locked"]), ["Bob school"]);
    assert_eq!(
        day_a["next_action"],
        json!({ "kind": "plan", "assignment_id": "hw" })
    );
    assert_eq!(day_b["next_action"], json!({ "kind": "add" }));
    // Bob's week 2 is empty.
    assert_eq!(
        views::day(&db.path, ben, "2026-09-21", now).unwrap()["locked"],
        json!([])
    );
    assert_eq!(
        titles(&views::day(&db.path, ana, "2026-09-21", now).unwrap()["locked"]),
        ["Alice again"]
    );
    let month_a = views::month(&db.path, ana, "2026-09", 0, now).unwrap();
    let month_b = views::month(&db.path, ben, "2026-09", 0, now).unwrap();
    let due_days = |month: &Value| -> Vec<String> {
        month["days"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|day| day["due_ids"].as_array().is_some_and(|ids| !ids.is_empty()))
            .map(|day| day["date"].as_str().unwrap().to_string())
            .collect()
    };
    assert_eq!(due_days(&month_a), ["2026-09-15"]);
    assert_eq!(due_days(&month_b), ["2026-09-22"]);
    assert_eq!(titles(&month_a["deadlines"]), ["Alice essay"]);
    assert_eq!(titles(&month_b["deadlines"]), ["Bob lab"]);
    let locked = |month: &Value| -> Vec<(String, i64)> {
        month["days"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|day| day["locked_count"].as_i64().unwrap_or(0) > 0)
            .map(|day| {
                (
                    day["date"].as_str().unwrap().to_string(),
                    day["locked_count"].as_i64().unwrap(),
                )
            })
            .collect()
    };
    assert_eq!(
        locked(&month_a),
        [("2026-09-14".to_string(), 1), ("2026-09-21".to_string(), 1)]
    );
    assert_eq!(locked(&month_b), [("2026-09-14".to_string(), 1)]);
}

#[test]
fn spreading_homework_reads_the_callers_own_homework() {
    let db = TestDb::new("apart-spread");
    let (ana, ben) = two_filled(&db);
    let spread = json!({ "session_min": 60, "from_date": "2026-09-14" });
    let lengths = |preview: &Value| -> Vec<i64> {
        preview["sessions"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| s["duration_min"].as_i64().unwrap())
            .collect()
    };
    let spread_a = spread_preview(&db.path, ana, "hw", &spread).unwrap();
    let spread_b = spread_preview(&db.path, ben, "hw", &spread).unwrap();
    assert_eq!(lengths(&spread_a), [60, 60]);
    assert_eq!(lengths(&spread_b), [60]);
    assert_eq!(
        (&spread_a["remaining_min"], &spread_b["remaining_min"]),
        (&json!(0), &json!(0))
    );
    assert!(matches!(
        spread_preview(&db.path, ana, "nothing", &spread),
        Err(ServiceError::Refused(Refusal::NotFound(ref words))) if words == HOMEWORK_UNKNOWN
    ));
    let mut done = homework("Alice essay", 120, "2026-09-15T23:59", 1);
    done["completed"] = json!(true);
    done["completed_at"] = json!("2026-09-14T16:00");
    save_homework(&db.path, ana, "hw", &done).unwrap();
    assert!(matches!(
        spread_preview(&db.path, ana, "hw", &spread),
        Err(ServiceError::Refused(Refusal::Invalid(ref words))) if words == SPREAD_DONE
    ));
    assert!(spread_preview(&db.path, ben, "hw", &spread).is_ok());
}

#[test]
fn plan_uses_the_callers_end_of_day_and_not_anothers() {
    let db = TestDb::new("apart-cutoff");
    let ana = db.account("alice");
    let ben = db.account("bob");
    let mut prefs = read_preferences(&db.path, ana).unwrap();
    // Alice's day ends at 06:15; Bob has no end of day.
    prefs["day_cutoff"] = json!("06:15");
    write_preferences(&db.path, ana, &prefs).unwrap();
    let work = json!({ "id": "hw", "title": "Homework", "kind": "flexible", "duration_min": 60, "days": [0],
                       "priority": 3, "energy": "high" });
    let end_minute = |user: i64| -> i64 {
        let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
        let trace = plan(&db.path, user, &json!({ "blocks": [work] }), &start_clock).unwrap();
        let placed = trace["placed"]
            .as_array()
            .unwrap()
            .iter()
            .find(|b| b["id"] == "hw")
            .unwrap()
            .clone();
        let start: Vec<i64> = placed["start"]
            .as_str()
            .unwrap()
            .split(':')
            .map(|p| p.parse().unwrap())
            .collect();
        start[0] * 60 + start[1] + placed["duration_min"].as_i64().unwrap()
    };
    assert!(end_minute(ana) <= 6 * 60 + 15);
    assert!(end_minute(ben) > 6 * 60 + 15);
    assert!(
        read_preferences(&db.path, ben)
            .unwrap()
            .get("day_cutoff")
            .is_none_or(Value::is_null)
    );
}
