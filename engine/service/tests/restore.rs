//! Restore points, as spec.md promises them: a point holds the account's weeks and homework; restoring it
//! after a preview puts them back and first keeps a "Before restore" point of the account as it was; a
//! preview that is out of date is refused and changes nothing; only the newest 20 points are kept, but the
//! one being restored is never the one dropped; and points belong to one account. These are the Rust twins
//! of backend/tests/test_restore_points.py's restore-point tests (its `/api/changes` tests wait for that
//! route to move).

use flexweek_service::records::{self, RESTORE_STALE, RESTORE_UNKNOWN};
use flexweek_service::{Refusal, ServiceError, views, weeks, with_db};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-14";
const NOW: &str = "2026-09-15T18:30";

type Db = TestDb;

fn fresh(name: &str) -> Db {
    TestDb::new(name)
}

fn account(db: &Db, name: &str) -> i64 {
    db.account(name)
}

fn school(title: &str) -> Value {
    json!({
        "id": "school", "title": title, "kind": "locked", "duration_min": 390,
        "days": [0, 1, 2, 3, 4], "priority": 1, "energy": "medium", "start": "08:00",
        "category": "School",
    })
}

fn essay(title: &str) -> Value {
    json!({
        "category": "Homework", "completed": false, "completed_at": null, "course": null,
        "due": "2026-09-16T23:59", "energy": "medium", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "id": "hw-essay", "priority": 3, "spotify_url": null, "title": title,
    })
}

fn save_week(db: &Db, user: i64, blocks: Value, revision: i64) {
    with_db(&db.path, |conn| {
        flexweek_store::save_week(conn, user, WEEK, &blocks.to_string(), revision)?;
        Ok(())
    })
    .unwrap();
}

fn save_essay(db: &Db, user: i64, title: &str, revision: i64) {
    with_db(&db.path, |conn| {
        flexweek_store::save_assignment(
            conn,
            user,
            "hw-essay",
            &essay(title).to_string(),
            revision,
            1000,
        )?;
        Ok(())
    })
    .unwrap();
}

fn point(db: &Db, user: i64, label: &str, operation: &str, token: &str) -> Value {
    let given = json!({ "label": label, "operation_id": operation });
    records::create_restore_point(&db.path, user, &given, token, NOW).unwrap()
}

fn listed(db: &Db, user: i64) -> Vec<Value> {
    views::restore_points(&db.path, user).unwrap()["restore_points"]
        .as_array()
        .unwrap()
        .clone()
}

fn ids(db: &Db, user: i64) -> Vec<String> {
    listed(db, user)
        .iter()
        .map(|item| item["id"].as_str().unwrap().to_string())
        .collect()
}

fn restore(
    db: &Db,
    user: i64,
    id: &str,
    state: &str,
    operation: &str,
) -> Result<Value, ServiceError> {
    let given = json!({ "state_token": state, "operation_id": operation });
    records::restore(&db.path, user, id, &given, "after", NOW)
}

fn state(db: &Db, user: i64, id: &str) -> String {
    let preview = records::restore_preview(&db.path, user, id).unwrap();
    preview["state_token"].as_str().unwrap().to_string()
}

fn week_titles(db: &Db, user: i64) -> Vec<String> {
    weeks::read_week(&db.path, user, WEEK).unwrap()["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["title"].as_str().unwrap().to_string())
        .collect()
}

fn refusal(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn a_new_account_has_no_restore_points() {
    let db = fresh("none");
    let ana = account(&db, "ana");
    assert_eq!(
        views::restore_points(&db.path, ana).unwrap(),
        json!({ "restore_points": [] })
    );
}

#[test]
fn a_restore_point_holds_the_weeks_and_homework_and_a_retry_makes_no_second() {
    let db = fresh("snapshot");
    let ana = account(&db, "ana");
    save_essay(&db, ana, "Essay", 0);
    save_week(&db, ana, json!([school("School")]), 0);
    let made = point(
        &db,
        ana,
        "Before finals week",
        "op-rp-1",
        "0123456789abcdef",
    );
    assert_eq!(
        made,
        json!({
            "id": "rp-0123456789abcdef", "label": "Before finals week", "created_at": NOW,
            "weeks": 1, "assignments": 1,
        })
    );
    assert_eq!(listed(&db, ana), vec![made.clone()]);
    let again = point(
        &db,
        ana,
        "Before finals week",
        "op-rp-1",
        "fedcba9876543210",
    );
    assert_eq!(again, made, "a retried request makes no second point");
    assert_eq!(listed(&db, ana).len(), 1);
}

#[test]
fn restoring_after_a_preview_puts_the_account_back_and_keeps_a_point_of_how_it_was() {
    let db = fresh("restore");
    let ana = account(&db, "ana");
    save_essay(&db, ana, "Essay", 0);
    save_week(&db, ana, json!([school("School")]), 0);
    let kept = point(&db, ana, "School week", "op-rp-school", "aaaa")["id"]
        .as_str()
        .unwrap()
        .to_string();
    save_essay(&db, ana, "Rewrite", 1);
    save_week(&db, ana, json!([]), 1);
    let preview = records::restore_preview(&db.path, ana, &kept).unwrap();
    assert_eq!(preview["id"], kept);
    assert_eq!(
        preview["changes"],
        json!({
            "weeks": { "added": [], "changed": [WEEK], "removed": [] },
            "assignments": {
                "added": [], "changed": [{ "id": "hw-essay", "title": "Essay" }], "removed": [],
            },
        })
    );
    let token = preview["state_token"].as_str().unwrap();
    let restored = restore(&db, ana, &kept, token, "op-restore-1").unwrap();
    assert_eq!(week_titles(&db, ana), ["School"]);
    let homework = views::homework(
        &db.path,
        ana,
        WEEK,
        true,
        flexweek_engine::plan::parse_moment(NOW).unwrap(),
    )
    .unwrap();
    assert_eq!(homework["assignments"][0]["title"], "Essay");
    let points = listed(&db, ana);
    assert_eq!(points[0]["id"], "rp-after");
    assert_eq!(points[0]["label"], format!("Before restore \u{2014} {NOW}"));
    assert_eq!(restored["recovery_id"], "rp-after");
    assert!(ids(&db, ana).contains(&kept));
    let retry = restore(&db, ana, &kept, token, "op-restore-1").unwrap();
    assert_eq!(retry, restored, "a retried restore gives its first answer");
    assert_eq!(
        listed(&db, ana).len(),
        2,
        "and makes no second Before restore point"
    );
}

#[test]
fn a_restore_from_an_out_of_date_preview_is_refused_and_changes_nothing() {
    let db = fresh("stale");
    let ana = account(&db, "ana");
    save_week(&db, ana, json!([school("School")]), 0);
    let kept = point(&db, ana, "School", "op-rp-stale", "aaaa")["id"]
        .as_str()
        .unwrap()
        .to_string();
    let token = state(&db, ana, &kept);
    save_week(&db, ana, json!([]), 1);
    assert_eq!(
        refusal(restore(&db, ana, &kept, &token, "op-restore-stale")),
        Refusal::Conflict(RESTORE_STALE.to_string())
    );
    assert!(week_titles(&db, ana).is_empty());
    assert_eq!(ids(&db, ana), [kept]);
}

#[test]
fn only_the_newest_20_points_are_kept() {
    let db = fresh("cap");
    let ana = account(&db, "ana");
    let made: Vec<String> = (0..20)
        .map(|at| {
            point(
                &db,
                ana,
                &format!("Point {at}"),
                &format!("op-{at}"),
                &format!("{at:04}"),
            )["id"]
                .as_str()
                .unwrap()
                .to_string()
        })
        .collect();
    let extra = point(&db, ana, "Point 20", "op-20", "0020")["id"]
        .as_str()
        .unwrap()
        .to_string();
    let remaining = ids(&db, ana);
    assert_eq!(remaining.len(), 20);
    assert!(!remaining.contains(&made[0]), "the oldest point stayed");
    assert!(remaining.contains(&extra));
}

#[test]
fn restoring_the_oldest_point_does_not_drop_it() {
    let db = fresh("oldest");
    let ana = account(&db, "ana");
    let made: Vec<String> = (0..20)
        .map(|at| {
            point(
                &db,
                ana,
                &format!("Point {at}"),
                &format!("op-{at}"),
                &format!("{at:04}"),
            )["id"]
                .as_str()
                .unwrap()
                .to_string()
        })
        .collect();
    let oldest = &made[0];
    let token = state(&db, ana, oldest);
    restore(&db, ana, oldest, &token, "op-keep-oldest").unwrap();
    let remaining = ids(&db, ana);
    assert_eq!(remaining.len(), 20);
    assert!(
        remaining.contains(oldest),
        "the point being restored was dropped"
    );
}

#[test]
fn the_same_operation_id_in_two_accounts_makes_two_points() {
    let db = fresh("two-ops");
    let (ana, ben) = (account(&db, "ana"), account(&db, "ben"));
    let first = point(&db, ana, "Ana's", "shared-op", "aaaa");
    let second = point(&db, ben, "Ben's", "shared-op", "bbbb");
    assert_eq!(second["label"], "Ben's");
    assert_ne!(second["id"], first["id"]);
    assert_eq!(listed(&db, ana)[0]["label"], "Ana's");
    assert_eq!(listed(&db, ben)[0]["label"], "Ben's");
}

#[test]
fn another_account_cannot_list_preview_or_restore_my_points() {
    let db = fresh("other");
    let (ana, ben) = (account(&db, "ana"), account(&db, "ben"));
    save_week(&db, ana, json!([school("School")]), 0);
    let kept = point(&db, ana, "Ana only", "op-ana", "aaaa")["id"]
        .as_str()
        .unwrap()
        .to_string();
    assert!(listed(&db, ben).is_empty());
    let not_found = Refusal::NotFound(RESTORE_UNKNOWN.to_string());
    assert_eq!(
        refusal(records::restore_preview(&db.path, ben, &kept)),
        not_found
    );
    assert_eq!(
        refusal(restore(&db, ben, &kept, "nope", "op-ben")),
        not_found
    );
    assert_eq!(ids(&db, ana), [kept]);
    assert_eq!(week_titles(&db, ana), ["School"]);
}

#[test]
fn points_with_the_same_id_stay_with_their_account() {
    let db = fresh("same-id");
    let (ana, ben) = (account(&db, "ana"), account(&db, "ben"));
    save_week(&db, ana, json!([school("Ana school")]), 0);
    save_week(&db, ben, json!([school("Ben school")]), 0);
    let shared = point(&db, ana, "Ana", "op-1", "aaaa")["id"]
        .as_str()
        .unwrap()
        .to_string();
    // Ben's point has Ana's point's id, another label, and no weeks at all.
    with_db(&db.path, |conn| {
        conn.execute(
            "INSERT INTO restore_points(user_id, id, label, created_at, weeks_count, assignments_count, body)
             VALUES (?1, ?2, 'Ben', '2026-09-14T08:00', 0, 0, '{\"weeks\":[],\"assignments\":[]}')",
            rusqlite::params![ben, shared],
        )
        .unwrap();
        Ok(())
    })
    .unwrap();
    assert_eq!(listed(&db, ana)[0]["label"], "Ana");
    assert_eq!(
        listed(&db, ben),
        vec![json!({
            "id": shared, "label": "Ben", "created_at": "2026-09-14T08:00", "weeks": 0,
            "assignments": 0,
        })]
    );
    let preview = records::restore_preview(&db.path, ben, &shared).unwrap();
    assert_eq!(
        preview["changes"],
        json!({
            "weeks": { "added": [], "changed": [], "removed": [WEEK] },
            "assignments": { "added": [], "changed": [], "removed": [] },
        }),
        "Ben's point holds no weeks, so his one week would go"
    );
    let token = preview["state_token"].as_str().unwrap();
    restore(&db, ben, &shared, token, "op-ben").unwrap();
    assert_eq!(
        weeks::read_week(&db.path, ben, WEEK).unwrap(),
        json!({ "week_start": WEEK, "blocks": [], "revision": 0 })
    );
    assert_eq!(week_titles(&db, ana), ["Ana school"]);
}
