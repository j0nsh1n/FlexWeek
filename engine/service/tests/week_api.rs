//! The Week screen's saved weeks: each Monday is its own week with its own revision, a week nobody saved
//! reads empty, a save from an old revision is refused, saving the same week again changes nothing, and
//! each account lists only its own weeks. Dates are worked out from the calendar: 2026-09-07 is a Monday.
//! The Rust twins of backend/tests/test_week_api.py.

use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Map, Value, json};

const WEEK_ONE: &str = "2026-09-07";
const WEEK_TWO: &str = "2026-09-14";
const WEEK_THREE: &str = "2026-09-21";

fn flex(id: &str, changes: Value) -> Value {
    let mut block = json!({
        "id": id, "title": "Homework", "kind": "flexible", "duration_min": 60, "days": [0], "priority": 3,
        "energy": "medium", "earliest": null, "latest": null, "start": null, "course": null,
    });
    let fields: &mut Map<String, Value> = block.as_object_mut().unwrap();
    for (key, value) in changes.as_object().unwrap() {
        fields.insert(key.clone(), value.clone());
    }
    block
}

fn math() -> Value {
    flex("a-math", json!({ "title": "Algebra homework" }))
}

fn reading() -> Value {
    flex(
        "a-read",
        json!({ "title": "Reading", "duration_min": 30, "days": [3], "priority": 4 }),
    )
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

fn read(db: &TestDb, user: i64, week_start: &str) -> Result<Value, ServiceError> {
    weeks::read_week(&db.path, user, week_start)
}

fn saved(week_start: &str, blocks: Value, revision: i64) -> Value {
    json!({ "week_start": week_start, "blocks": blocks, "revision": revision })
}

fn listed(db: &TestDb, user: i64) -> Value {
    weeks::list_weeks(&db.path, user).unwrap()
}

fn refused(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn two_weeks_of_one_account_hold_their_own_blocks_and_revisions() {
    let db = TestDb::new("week-two");
    let ana = db.account("ana");
    assert_eq!(
        save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(
        save(&db, ana, WEEK_TWO, json!([reading()]), 0).unwrap(),
        saved(WEEK_TWO, json!([reading()]), 1)
    );
    assert_eq!(
        read(&db, ana, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(
        read(&db, ana, WEEK_TWO).unwrap(),
        saved(WEEK_TWO, json!([reading()]), 1)
    );
}

#[test]
fn a_block_at_any_minute_is_saved_as_it_was_typed() {
    let db = TestDb::new("week-minute");
    let ana = db.account("ana");
    let lesson = json!({ "id": "lesson", "title": "Lesson", "kind": "locked", "start": "17:37", "duration_min": 45, "days": [3] });
    save(&db, ana, WEEK_ONE, json!([lesson]), 0).unwrap();
    let back = read(&db, ana, WEEK_ONE).unwrap()["blocks"][0].clone();
    assert_eq!(
        (&back["start"], &back["duration_min"]),
        (&json!("17:37"), &json!(45))
    );
}

#[test]
fn a_save_to_a_week_that_does_not_start_on_monday_is_refused_and_changes_nothing() {
    let db = TestDb::new("week-tuesday");
    let ana = db.account("ana");
    save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap();
    assert!(matches!(
        refused(save(&db, ana, "2026-09-08", json!([math()]), 0)),
        Refusal::Invalid(_)
    ));
    assert_eq!(
        read(&db, ana, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(listed(&db, ana), json!({ "weeks": [WEEK_ONE] }));
}

#[test]
fn a_week_start_that_is_not_a_date_is_refused() {
    let db = TestDb::new("week-malformed");
    let ana = db.account("ana");
    for week_start in ["2026-9-7", "20260907", "2026-W37-1", "2026-02-30"] {
        assert!(
            matches!(refused(read(&db, ana, week_start)), Refusal::Invalid(_)),
            "{week_start}"
        );
    }
}

#[test]
fn a_week_from_another_day_shows_both_stored_weeks_revisions() {
    let db = TestDb::new("week-other-day");
    let ana = db.account("ana");
    // Tuesday 8 and Sunday 13 September cover the stored weeks of Monday 7 and Monday 14, unsaved.
    let parts = json!([
        saved("2026-09-07", json!([]), 0),
        saved("2026-09-14", json!([]), 0)
    ]);
    for week_start in ["2026-09-08", "2026-09-13"] {
        assert_eq!(
            read(&db, ana, week_start).unwrap(),
            json!({ "week_start": week_start, "blocks": [], "revision": [0, 0], "stored": parts })
        );
    }
}

#[test]
fn only_the_monday_that_holds_the_first_allowed_date_is_allowed_before_2000() {
    let db = TestDb::new("week-edges");
    let ana = db.account("ana");
    assert_eq!(
        read(&db, ana, "1999-12-27").unwrap(),
        saved("1999-12-27", json!([]), 0)
    );
    save(&db, ana, "1999-12-27", json!([]), 0).unwrap();
    assert!(matches!(
        refused(read(&db, ana, "1999-12-20")),
        Refusal::Invalid(_)
    ));
    assert!(matches!(
        refused(read(&db, ana, "2100-01-04")),
        Refusal::Invalid(_)
    ));
    // Saving an empty week stores no row.
    assert_eq!(listed(&db, ana), json!({ "weeks": [] }));
}

#[test]
fn a_week_nobody_saved_reads_empty_and_a_save_at_revision_0_creates_it() {
    let db = TestDb::new("week-create");
    let ana = db.account("ana");
    assert_eq!(
        read(&db, ana, WEEK_THREE).unwrap(),
        saved(WEEK_THREE, json!([]), 0)
    );
    assert_eq!(
        save(&db, ana, WEEK_THREE, json!([math()]), 0).unwrap(),
        saved(WEEK_THREE, json!([math()]), 1)
    );
    // A never-saved week with any other revision has nothing to match.
    assert_eq!(
        refused(save(&db, ana, WEEK_ONE, json!([math()]), 3)),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
    assert_eq!(
        read(&db, ana, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([]), 0)
    );
}

#[test]
fn saving_the_same_blocks_again_keeps_the_revision_even_from_an_old_one() {
    let db = TestDb::new("week-same");
    let ana = db.account("ana");
    assert_eq!(
        save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap()["revision"],
        1
    );
    assert_eq!(
        save(&db, ana, WEEK_ONE, json!([math()]), 1).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    // The same blocks are accepted before the revision is checked, so even an old revision gets them.
    assert_eq!(
        save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(
        read(&db, ana, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(listed(&db, ana), json!({ "weeks": [WEEK_ONE] }));
}

#[test]
fn an_old_revision_on_one_week_is_refused_and_leaves_the_other_week_alone() {
    let db = TestDb::new("week-stale");
    let ana = db.account("ana");
    save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap();
    save(&db, ana, WEEK_TWO, json!([reading()]), 0).unwrap();
    assert_eq!(
        refused(save(
            &db,
            ana,
            WEEK_ONE,
            json!([flex("a-other", json!({}))]),
            0
        )),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
    assert_eq!(
        read(&db, ana, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([math()]), 1)
    );
    assert_eq!(
        read(&db, ana, WEEK_TWO).unwrap(),
        saved(WEEK_TWO, json!([reading()]), 1)
    );
}

#[test]
fn the_saved_weeks_are_listed_oldest_first_and_only_for_their_account() {
    let db = TestDb::new("week-list");
    let ana = db.account("ana");
    let ben = db.account("ben");
    // The later week first, so the order is not the order they were saved in.
    save(&db, ana, WEEK_TWO, json!([reading()]), 0).unwrap();
    save(&db, ana, WEEK_ONE, json!([math()]), 0).unwrap();
    assert_eq!(listed(&db, ana), json!({ "weeks": [WEEK_ONE, WEEK_TWO] }));
    assert_eq!(listed(&db, ben), json!({ "weeks": [] }));
    assert_eq!(
        read(&db, ben, WEEK_ONE).unwrap(),
        saved(WEEK_ONE, json!([]), 0)
    );
}
