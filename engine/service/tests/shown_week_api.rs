//! A week on screen can start on any day: read from another day it shows the seven days from it, taken
//! from the two stored (Monday) weeks it covers, and a save splits it back. Its revision is the two stored
//! weeks' revisions, first week first. Dates are read off the 2026 calendar: Wednesday 11 November to
//! Tuesday 17 November covers the weeks of Monday 9 and Monday 16 November. The Rust twins of
//! backend/tests/test_shown_week_api.py.

use flexweek_engine::plan::parse_moment;
use flexweek_engine::repeats::parse_intents;
use flexweek_engine::shown::apply_repeats_to_shown_week;
use flexweek_service::changes::apply_changes;
use flexweek_service::homework_saves::save_homework;
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::week_saves::WEEK_CONFLICT;
use flexweek_service::{Refusal, ServiceError, views, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WED: &str = "2026-11-11";
const FIRST: &str = "2026-11-09";
const SECOND: &str = "2026-11-16";

fn school() -> Value {
    json!([{
        "id": "school", "scope": "from", "from_date": "2026-11-02",
        "set": { "title": "School", "category": "class", "start": "08:30", "duration_min": 405 },
        "add_days": [0, 1, 2, 3, 4],
    }])
}

fn fixed(id: &str, start: &str, days: Value) -> Value {
    json!({ "id": id, "title": id, "kind": "locked", "duration_min": 60, "days": days, "start": start })
}

fn week(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

fn post(db: &TestDb, user: i64, given: Value) -> Result<Value, ServiceError> {
    apply_changes(
        &db.path,
        user,
        &given,
        "0123456789abcdef",
        "2026-11-05T19:00",
    )
}

fn save(db: &TestDb, user: i64, week_start: &str, blocks: Value, revision: Value) -> Value {
    post(
        db,
        user,
        json!({ "weeks": [{ "week_start": week_start, "blocks": blocks, "revision": revision }] }),
    )
    .unwrap()
}

fn save_with_repeats(
    db: &TestDb,
    user: i64,
    week_start: &str,
    blocks: Value,
    revision: Value,
    repeats: Value,
) {
    post(
        db,
        user,
        json!({ "weeks": [{ "week_start": week_start, "blocks": blocks, "revision": revision }], "repeats": repeats }),
    )
    .unwrap();
}

/// Each block's days by id, in the order the week lists them.
fn days_of(blocks: &Value) -> Vec<(String, Value)> {
    blocks
        .as_array()
        .unwrap()
        .iter()
        .map(|block| {
            (
                block["id"].as_str().unwrap().to_string(),
                block["days"].clone(),
            )
        })
        .collect()
}

fn days(pairs: &[(&str, Value)]) -> Vec<(String, Value)> {
    pairs
        .iter()
        .map(|(id, days)| ((*id).to_string(), days.clone()))
        .collect()
}

fn refused(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn a_wednesday_week_nobody_saved_is_empty_with_both_revisions() {
    let db = TestDb::new("shown-empty");
    let ana = db.account("ana");
    let shown = week(&db, ana, WED);
    assert_eq!(
        (&shown["week_start"], &shown["blocks"], &shown["revision"]),
        (&json!(WED), &json!([]), &json!([0, 0]))
    );
}

#[test]
fn a_thursday_block_is_stored_in_its_monday_week_and_a_monday_block_in_the_next() {
    let db = TestDb::new("shown-split");
    let ana = db.account("ana");
    let saved = save(
        &db,
        ana,
        WED,
        json!([
            fixed("thu12", "10:00", json!([1])),
            fixed("mon16", "10:00", json!([5]))
        ]),
        json!([0, 0]),
    );
    assert_eq!(
        (
            &saved["weeks"][0]["week_start"],
            &saved["weeks"][0]["revision"]
        ),
        (&json!(WED), &json!([1, 1]))
    );
    assert_eq!(
        days_of(&week(&db, ana, FIRST)["blocks"]),
        days(&[("thu12", json!([3]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, SECOND)["blocks"]),
        days(&[("mon16", json!([0]))])
    );
    let shown = week(&db, ana, WED);
    assert_eq!(
        days_of(&shown["blocks"]),
        days(&[("thu12", json!([1])), ("mon16", json!([5]))])
    );
    assert_eq!(shown["revision"], json!([1, 1]));
}

#[test]
fn a_change_on_one_side_of_the_week_on_screen_leaves_the_other_stored_week_unwritten() {
    let db = TestDb::new("shown-one-side");
    let ana = db.account("ana");
    save(
        &db,
        ana,
        WED,
        json!([fixed("thu12", "10:00", json!([1]))]),
        json!([0, 0]),
    );
    assert_eq!(week(&db, ana, WED)["revision"], json!([1, 0]));
    assert_eq!(week(&db, ana, SECOND)["revision"], 0);
}

#[test]
fn a_block_deleted_from_the_week_on_screen_stays_on_the_days_before_and_after() {
    let db = TestDb::new("shown-delete");
    let ana = db.account("ana");
    let gym = fixed("gym", "17:00", json!([0, 2, 4]));
    save(&db, ana, FIRST, json!([gym]), json!(0));
    save(&db, ana, SECOND, json!([gym]), json!(0));
    let shown = week(&db, ana, WED);
    assert_eq!(
        days_of(&shown["blocks"]),
        days(&[("gym", json!([0, 2, 5]))])
    );
    save(&db, ana, WED, json!([]), shown["revision"].clone());
    // Monday 9 is the week before's; Wednesday 18 and Friday 20 the week after's.
    assert_eq!(
        days_of(&week(&db, ana, FIRST)["blocks"]),
        days(&[("gym", json!([0]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, SECOND)["blocks"]),
        days(&[("gym", json!([2, 4]))])
    );
}

#[test]
fn a_session_placed_after_the_seam_is_stored_once() {
    let db = TestDb::new("shown-seam");
    let ana = db.account("ana");
    let waiting = json!({ "id": "s1", "title": "Read", "kind": "flexible", "duration_min": 60, "days": [0, 1, 2, 3, 4, 5, 6] });
    save(&db, ana, FIRST, json!([waiting]), json!(0));
    let shown = week(&db, ana, WED);
    assert_eq!(
        days_of(&shown["blocks"]),
        days(&[("s1", json!([0, 1, 2, 3, 4]))])
    );
    let mut placed = shown["blocks"][0].clone();
    placed["days"] = json!([5]);
    placed["start"] = json!("16:00");
    save(&db, ana, WED, json!([placed]), shown["revision"].clone());
    assert_eq!(week(&db, ana, FIRST)["blocks"], json!([]));
    let stored = week(&db, ana, SECOND)["blocks"].clone();
    assert_eq!(days_of(&stored), days(&[("s1", json!([0]))]));
    assert_eq!(stored[0]["start"], "16:00");
}

#[test]
fn a_stale_revision_on_either_stored_week_refuses_the_whole_save() {
    let db = TestDb::new("shown-stale");
    let ana = db.account("ana");
    let shown = week(&db, ana, WED);
    // Another device saves the second week meanwhile.
    save(
        &db,
        ana,
        SECOND,
        json!([fixed("phone", "12:00", json!([0]))]),
        json!(0),
    );
    let given = json!({ "weeks": [{ "week_start": WED, "blocks": [fixed("thu12", "10:00", json!([1]))],
                                    "revision": shown["revision"] }] });
    assert_eq!(
        refused(post(&db, ana, given)),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
    // Nothing was written to the first week either.
    let first = week(&db, ana, FIRST);
    assert_eq!(
        (&first["blocks"], &first["revision"]),
        (&json!([]), &json!(0))
    );
    assert_eq!(
        days_of(&week(&db, ana, WED)["blocks"]),
        days(&[("phone", json!([5]))])
    );
}

#[test]
fn a_save_sent_again_lands_once() {
    let db = TestDb::new("shown-retry");
    let ana = db.account("ana");
    let given = json!({
        "weeks": [{ "week_start": WED, "blocks": [fixed("mon16", "10:00", json!([5]))], "revision": [0, 0] }],
        "operation_id": "op-1",
    });
    let first = post(&db, ana, given.clone()).unwrap();
    assert_eq!(post(&db, ana, given).unwrap(), first);
    assert_eq!(week(&db, ana, SECOND)["revision"], 1);
    assert_eq!(
        days_of(&week(&db, ana, SECOND)["blocks"]),
        days(&[("mon16", json!([0]))])
    );
}

#[test]
fn a_monday_week_keeps_a_plain_revision() {
    let db = TestDb::new("shown-monday");
    let ana = db.account("ana");
    let saved = save(
        &db,
        ana,
        FIRST,
        json!([fixed("mon9", "10:00", json!([0]))]),
        json!(0),
    );
    assert_eq!(saved["weeks"][0]["revision"], 1);
    assert_eq!(week(&db, ana, FIRST)["revision"], 1);
}

#[test]
fn a_week_on_screen_names_both_stored_weeks_revisions_and_a_monday_one_revision() {
    let db = TestDb::new("shown-revision");
    let ana = db.account("ana");
    for (week_start, revision) in [
        (WED, json!(0)),
        (WED, json!([0])),
        (WED, json!([0, 0, 0])),
        (FIRST, json!([0, 0])),
    ] {
        let given =
            json!({ "weeks": [{ "week_start": week_start, "blocks": [], "revision": revision }] });
        assert!(
            matches!(refused(post(&db, ana, given)), Refusal::Invalid(_)),
            "{week_start} {revision}"
        );
    }
}

#[test]
fn a_week_from_sunday_takes_its_sunday_from_the_week_before() {
    let db = TestDb::new("shown-sunday");
    let ana = db.account("ana");
    save(
        &db,
        ana,
        "2026-11-08",
        json!([
            fixed("sun8", "10:00", json!([0])),
            fixed("sat14", "10:00", json!([6]))
        ]),
        json!([0, 0]),
    );
    assert_eq!(
        days_of(&week(&db, ana, "2026-11-02")["blocks"]),
        days(&[("sun8", json!([6]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, FIRST)["blocks"]),
        days(&[("sat14", json!([5]))])
    );
}

#[test]
fn a_week_over_the_year_end_stores_its_january_days_in_january() {
    let db = TestDb::new("shown-year-end");
    let ana = db.account("ana");
    // Wednesday 30 December 2026 to Tuesday 5 January 2027.
    save(
        &db,
        ana,
        "2026-12-30",
        json!([
            fixed("dec31", "10:00", json!([1])),
            fixed("jan4", "10:00", json!([5]))
        ]),
        json!([0, 0]),
    );
    assert_eq!(
        days_of(&week(&db, ana, "2026-12-28")["blocks"]),
        days(&[("dec31", json!([3]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, "2027-01-04")["blocks"]),
        days(&[("jan4", json!([0]))])
    );
    // And one over a month end: Wednesday 25 November to Tuesday 1 December.
    save(
        &db,
        ana,
        "2026-11-25",
        json!([fixed("dec1", "10:00", json!([6]))]),
        json!([0, 0]),
    );
    assert_eq!(
        days_of(&week(&db, ana, "2026-11-30")["blocks"]),
        days(&[("dec1", json!([1]))])
    );
}

#[test]
fn school_stopped_from_the_week_on_screen_on_stays_on_the_days_before_it() {
    let db = TestDb::new("shown-school-stop");
    let ana = db.account("ana");
    post(&db, ana, json!({ "weeks": [], "repeats": school() })).unwrap();
    let shown = week(&db, ana, WED);
    assert_eq!(
        days_of(&shown["blocks"]),
        days(&[("school", json!([0, 1, 2, 5, 6]))])
    );
    let stop = json!([{ "id": "school", "scope": "from", "from_date": WED, "stop": true }]);
    save_with_repeats(&db, ana, WED, json!([]), shown["revision"].clone(), stop);
    // Monday 9 and Tuesday 10 belong to the week before the shown one and keep School.
    assert_eq!(
        days_of(&week(&db, ana, FIRST)["blocks"]),
        days(&[("school", json!([0, 1]))])
    );
    assert_eq!(week(&db, ana, SECOND)["blocks"], json!([]));
    assert_eq!(week(&db, ana, "2026-11-23")["blocks"], json!([]));
    assert_eq!(
        week(&db, ana, "2026-11-02")["blocks"][0]["days"],
        json!([0, 1, 2, 3, 4])
    );
}

#[test]
fn school_taken_out_of_the_week_on_screen_only_is_missed_on_its_days_and_kept_on_the_others() {
    let db = TestDb::new("shown-school-missed");
    let ana = db.account("ana");
    post(&db, ana, json!({ "weeks": [], "repeats": school() })).unwrap();
    let shown = week(&db, ana, WED);
    let mut missed = shown["blocks"][0].clone();
    missed["missed_days"] = missed["days"].clone();
    save(&db, ana, WED, json!([missed]), shown["revision"].clone());
    let first = week(&db, ana, FIRST)["blocks"][0].clone();
    let second = week(&db, ana, SECOND)["blocks"][0].clone();
    assert_eq!(
        (&first["days"], &first["missed_days"]),
        (&json!([0, 1, 2, 3, 4]), &json!([2, 3, 4]))
    );
    assert_eq!(
        (&second["days"], &second["missed_days"]),
        (&json!([0, 1, 2, 3, 4]), &json!([0, 1]))
    );
    assert!(
        week(&db, ana, "2026-11-23")["blocks"][0]
            .get("missed_days")
            .is_none()
    );
}

#[test]
fn homework_counts_minutes_planned_from_the_first_day_of_the_week_on_screen() {
    let db = TestDb::new("shown-homework");
    let ana = db.account("ana");
    let homework = json!({ "id": "hw", "title": "Essay", "due": "2026-11-20T23:59", "estimate_min": 180, "revision": 0 });
    save_homework(&db.path, ana, "hw", &homework).unwrap();
    let session = |id: &str, day: i64| {
        let mut block = fixed(id, "16:00", json!([day]));
        block["kind"] = json!("flexible");
        block["duration_min"] = json!(30);
        block["assignment_id"] = json!("hw");
        block
    };
    // Tuesday 10 November is before the week from Wednesday 11; Wednesday 11 and Monday 16 are in it.
    save(
        &db,
        ana,
        FIRST,
        json!([session("tue10", 1), session("wed11", 2)]),
        json!(0),
    );
    save(&db, ana, SECOND, json!([session("mon16", 0)]), json!(0));
    let planned = |week_start: &str, now: &str| {
        let now = parse_moment(now).unwrap();
        views::homework(&db.path, ana, week_start, true, now).unwrap()["assignments"][0]["planned_min"].clone()
    };
    // On Thursday 5 November, Tuesday's 16:00 session is ahead of now, so it holds its 30 minutes too.
    assert_eq!(planned(WED, "2026-11-05T19:00"), 90);
    // Once Tuesday 10 November is over (its session ended at 16:30) it holds nothing.
    assert_eq!(planned(WED, "2026-11-10T17:00"), 60);
    assert_eq!(planned(FIRST, "2026-11-05T19:00"), 90);
}

#[test]
fn plan_on_a_week_from_wednesday_uses_each_days_own_hours_and_keeps_its_weekend_free() {
    let db = TestDb::new("shown-plan");
    let ana = db.account("ana");
    let mut prefs = read_preferences(&db.path, ana).unwrap();
    prefs["work_windows"] = json!([{ "days": [5], "start": "10:00", "end": "12:00" },
                                   { "days": [0], "start": "16:00", "end": "18:00" }]);
    prefs["buffer_min"] = json!(0);
    write_preferences(&db.path, ana, &prefs).unwrap();
    // From Wednesday 11 November, day 3 is Saturday 14 and day 5 Monday 16.
    let math = json!({ "id": "math", "title": "math", "kind": "flexible", "duration_min": 60, "days": [3, 5],
                       "priority": 3, "energy": "high" });
    let placed = || {
        let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
        let trace = plan(
            &db.path,
            ana,
            &json!({ "blocks": [math], "week_start": WED }),
            &start_clock,
        )
        .unwrap();
        let found = trace["placed"]
            .as_array()
            .unwrap()
            .iter()
            .find(|item| item["id"] == "math")
            .unwrap()
            .clone();
        (found["days"][0].clone(), found["start"].clone())
    };
    assert_eq!(placed(), (json!(3), json!("10:00")));
    let mut prefs = read_preferences(&db.path, ana).unwrap();
    prefs["weekend_homework_free"] = json!(true);
    write_preferences(&db.path, ana, &prefs).unwrap();
    assert_eq!(placed(), (json!(5), json!("16:00")));
}

/// School's start and days in a week, earliest start first, whatever ids hold it.
fn school_rows(blocks: &Value) -> Vec<(String, Value)> {
    let mut rows: Vec<(String, Value)> = blocks
        .as_array()
        .unwrap()
        .iter()
        .filter(|block| block["title"] == "School")
        .map(|block| {
            (
                block["start"].as_str().unwrap().to_string(),
                block["days"].clone(),
            )
        })
        .collect();
    rows.sort_by(|a, b| a.0.cmp(&b.0));
    rows
}

fn rows(pairs: &[(&str, Value)]) -> Vec<(String, Value)> {
    days(pairs)
}

#[test]
fn school_changed_twice_from_a_wednesday_week_on_then_from_the_next_monday_stays_school() {
    let db = TestDb::new("shown-school-twice");
    let ana = db.account("ana");
    post(&db, ana, json!({ "weeks": [], "repeats": school() })).unwrap();
    let from_this_week_on = |start: &str| {
        let shown = week(&db, ana, WED);
        let blocks = shown["blocks"].as_array().unwrap();
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0]["id"], "school");
        let mut moved = blocks[0].clone();
        moved["start"] = json!(start);
        let change = json!([{ "id": "school", "scope": "from", "from_date": WED, "set": { "start": start } }]);
        save_with_repeats(
            &db,
            ana,
            WED,
            json!([moved]),
            shown["revision"].clone(),
            change,
        );
    };
    from_this_week_on("10:00");
    from_this_week_on("09:00");
    let shown = week(&db, ana, WED);
    let only: Vec<(Value, Value, Value)> = shown["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| (row["id"].clone(), row["start"].clone(), row["days"].clone()))
        .collect();
    assert_eq!(
        only,
        [(json!("school"), json!("09:00"), json!([0, 1, 2, 5, 6]))]
    );
    // Monday 9 and Tuesday 10 come before the week on screen and keep 08:30; from Monday 16 the repeat
    // itself is 09:00, so that week holds School whole, by its own id.
    let first = week(&db, ana, FIRST)["blocks"].clone();
    assert_eq!(
        school_rows(&first),
        rows(&[("08:30", json!([0, 1])), ("09:00", json!([2, 3, 4]))])
    );
    assert!(
        first
            .as_array()
            .unwrap()
            .iter()
            .any(|block| block["id"] == "school" && block["start"] == "08:30")
    );
    let second: Vec<(Value, Value, Value)> = week(&db, ana, SECOND)["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| (row["id"].clone(), row["start"].clone(), row["days"].clone()))
        .collect();
    assert_eq!(
        second,
        [(json!("school"), json!("09:00"), json!([0, 1, 2, 3, 4]))]
    );
    // Setup changed from Monday 16 on reaches every day of that week, Monday 16 and Tuesday 17 included.
    let from_monday = json!([{ "id": "school", "scope": "from", "from_date": SECOND, "set": { "start": "07:45" } }]);
    post(&db, ana, json!({ "weeks": [], "repeats": from_monday })).unwrap();
    assert_eq!(
        school_rows(&week(&db, ana, SECOND)["blocks"]),
        rows(&[("07:45", json!([0, 1, 2, 3, 4]))])
    );
    assert_eq!(
        school_rows(&week(&db, ana, "2026-11-23")["blocks"]),
        rows(&[("07:45", json!([0, 1, 2, 3, 4]))])
    );
    assert_eq!(
        school_rows(&week(&db, ana, FIRST)["blocks"]),
        rows(&[("08:30", json!([0, 1])), ("09:00", json!([2, 3, 4]))])
    );
    let shown = week(&db, ana, WED);
    assert_eq!(
        school_rows(&shown["blocks"]),
        rows(&[("07:45", json!([5, 6])), ("09:00", json!([0, 1, 2]))])
    );
    assert!(
        shown["blocks"]
            .as_array()
            .unwrap()
            .iter()
            .any(|row| row["id"] == "school")
    );
}

#[test]
fn a_week_on_screen_carries_its_stored_weeks_so_undo_puts_them_back_exactly() {
    let db = TestDb::new("shown-undo");
    let ana = db.account("ana");
    // A session waiting for a time may go on Thursday 29 or Friday 30 October. Shown from Friday 30
    // October, the screen holds Friday only; Thursday is the week before's.
    let waiting = json!({ "id": "hw", "title": "Read", "kind": "flexible", "duration_min": 60, "days": [3, 4] });
    save(&db, ana, "2026-10-26", json!([waiting]), json!(0));
    let shown = week(&db, ana, "2026-10-30");
    assert_eq!(days_of(&shown["blocks"]), days(&[("hw", json!([0]))]));
    let parts: Vec<(Value, Value)> = shown["stored"]
        .as_array()
        .unwrap()
        .iter()
        .map(|part| (part["week_start"].clone(), part["revision"].clone()))
        .collect();
    assert_eq!(
        parts,
        [
            (json!("2026-10-26"), json!(1)),
            (json!("2026-11-02"), json!(0))
        ]
    );
    assert_eq!(
        days_of(&shown["stored"][0]["blocks"]),
        days(&[("hw", json!([3, 4]))])
    );
    assert!(week(&db, ana, "2026-10-26").get("stored").is_none());
    let deleted =
        save(&db, ana, "2026-10-30", json!([]), shown["revision"].clone())["weeks"][0].clone();
    assert_eq!(week(&db, ana, "2026-10-26")["blocks"], json!([]));
    // Undo sends each stored week as it was, then the week on screen as it was.
    let mut back: Vec<Value> = deleted["stored"]
        .as_array()
        .unwrap()
        .iter()
        .zip(shown["stored"].as_array().unwrap())
        .map(|(part, before)| json!({ "week_start": part["week_start"], "blocks": before["blocks"], "revision": part["revision"] }))
        .collect();
    back.push(json!({ "week_start": "2026-10-30", "blocks": shown["blocks"], "revision": deleted["revision"] }));
    post(&db, ana, json!({ "weeks": back })).unwrap();
    assert_eq!(
        days_of(&week(&db, ana, "2026-10-26")["blocks"]),
        days(&[("hw", json!([3, 4]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, "2026-10-30")["blocks"]),
        days(&[("hw", json!([0]))])
    );
}

#[test]
fn until_moved_later_from_a_wednesday_week_brings_back_the_day_it_hid() {
    let db = TestDb::new("shown-until");
    let ana = db.account("ana");
    // Guitar on Thursday and Saturday ends Friday 13 Nov, so the week on screen from Wednesday 11 shows
    // Thursday only. Until moved to the end of December from that week on: Saturday 14 is back on screen,
    // in its stored week and in every later week.
    let made = json!([{ "id": "weekly-3f2a9c01", "scope": "from", "from_date": "2026-11-02",
                        "set": { "title": "Guitar", "start": "17:00", "duration_min": 60, "until": "2026-11-13" },
                        "add_days": [3, 5] }]);
    post(&db, ana, json!({ "weeks": [], "repeats": made })).unwrap();
    let shown = week(&db, ana, WED);
    assert_eq!(
        days_of(&shown["blocks"]),
        days(&[("weekly-3f2a9c01", json!([1]))])
    );
    let later = json!([{ "id": "weekly-3f2a9c01", "scope": "from", "from_date": WED, "set": { "until": "2026-12-31" } }]);
    // The client changes the week on screen by the engine's rule, as the desktop does, and saves it.
    let (blocks, _) = apply_repeats_to_shown_week(
        WED,
        shown["blocks"].as_array().unwrap(),
        shown["repeats"].as_array().unwrap(),
        &parse_intents(&later).unwrap(),
    )
    .unwrap();
    let blocks = Value::Array(blocks);
    assert_eq!(
        days_of(&blocks),
        days(&[("weekly-3f2a9c01", json!([1, 3]))])
    );
    save_with_repeats(&db, ana, WED, blocks, shown["revision"].clone(), later);
    assert_eq!(
        days_of(&week(&db, ana, WED)["blocks"]),
        days(&[("weekly-3f2a9c01", json!([1, 3]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, FIRST)["blocks"]),
        days(&[("weekly-3f2a9c01", json!([3, 5]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, SECOND)["blocks"]),
        days(&[("weekly-3f2a9c01", json!([3, 5]))])
    );
    assert_eq!(
        days_of(&week(&db, ana, "2026-12-28")["blocks"]),
        days(&[("weekly-3f2a9c01", json!([3]))])
    );
    assert_eq!(week(&db, ana, "2027-01-04")["blocks"], json!([]));
}
