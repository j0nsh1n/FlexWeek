//! School changed on screen in a week that does not start on Monday reaches only some days of a
//! stored week, so that week holds School twice: `school` on the days it kept and
//! `school@20261111` on the days the change reached (a stored week holds one block per id). Both are
//! School: every check that asks "is this School or a Setup activity, and which one" reads the
//! family, so Setup, the delete choices, the repeat and the standing week reach both pieces.
//! Monday 9 November 2026's stored week: `school` on Monday and Tuesday at 08:30, the piece on
//! Wednesday to Friday at 10:00.

use flexweek_engine::desk::blocks::delete_block;
use flexweek_engine::desk::grid::is_setup_block;
use flexweek_engine::repeats::{apply_to_week, one_day_note, parse_intent, this_week_line};
use flexweek_engine::shown::family_id;
use flexweek_engine::standing::{derive_standing, with_standing};
use serde_json::{Map, Value, json};

fn school() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
           "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
}

fn kept() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
           "start": "08:30", "duration_min": 405, "days": [0, 1]})
}

fn piece() -> Value {
    json!({"id": "school@20261111", "title": "School", "kind": "locked", "category": "class",
           "start": "10:00", "duration_min": 405, "days": [2, 3, 4]})
}

fn week() -> Vec<Value> {
    vec![kept(), piece()]
}

fn by_id<'a>(blocks: &'a [Value], id: &str) -> &'a Value {
    blocks.iter().find(|block| block["id"] == id).unwrap()
}

#[test]
fn a_piece_of_school_or_an_activity_is_still_school_or_that_activity() {
    for id in [
        "school@20261111",
        "school@20261111-2",
        "sport@20261111",
        "activity-1a2b3c4d@20261231",
    ] {
        assert!(is_setup_block(&json!({"id": id})).unwrap(), "{id}");
    }
    for id in [
        "school@2026111",
        "school@20261111-",
        "school@2026111a",
        "schoolwork",
        "@20261111",
        "read@20261111",
    ] {
        assert!(!is_setup_block(&json!({"id": id})).unwrap(), "{id}");
    }
    assert_eq!(
        family_id("activity-1a2b3c4d@20261231-3"),
        "activity-1a2b3c4d"
    );
    assert_eq!(family_id("school"), "school");
    assert_eq!(family_id("a@b"), "a@b");
}

#[test]
fn a_change_from_this_week_on_reaches_every_piece_of_school() {
    let renamed = parse_intent(&json!({"id": "school", "scope": "from",
                                       "from_date": "2026-11-09", "set": {"title": "Classes"}}))
    .unwrap();
    let (blocks, _) = apply_to_week(&week(), &[school()], &[renamed]).unwrap();
    assert_eq!(by_id(&blocks, "school")["title"], "Classes");
    assert_eq!(by_id(&blocks, "school@20261111")["title"], "Classes");
    // A new start reaches the days that kept School's time; the piece keeps the time it was given.
    let earlier = parse_intent(&json!({"id": "school", "scope": "from",
                                       "from_date": "2026-11-09", "set": {"start": "08:00"}}))
    .unwrap();
    let (blocks, _) = apply_to_week(&week(), &[school()], &[earlier]).unwrap();
    assert_eq!(by_id(&blocks, "school")["start"], "08:00");
    assert_eq!(by_id(&blocks, "school@20261111")["start"], "10:00");
    let stop = parse_intent(&json!({"id": "school", "scope": "from",
                                    "from_date": "2026-11-09", "stop": true}))
    .unwrap();
    let (blocks, repeats) = apply_to_week(&week(), &[school()], &[stop]).unwrap();
    assert!(blocks.is_empty(), "{blocks:?}");
    assert!(repeats.is_empty());
}

#[test]
fn a_change_named_by_a_piece_changes_school() {
    let intent = parse_intent(&json!({"id": "school@20261111", "scope": "from",
                                      "from_date": "2026-11-11", "stop": true}))
    .unwrap();
    assert_eq!(intent.id, "school");
}

#[test]
fn the_school_hours_line_says_the_piece_is_school_at_another_time() {
    assert_eq!(
        this_week_line(&week(), &[school()], false).as_deref(),
        Some("This week: School at 10:00 AM–4:45 PM on Wednesday, Thursday and Friday.")
    );
}

#[test]
fn moving_a_day_of_a_piece_points_to_school_hours() {
    let note = one_day_note(&piece(), 3, true).unwrap().unwrap();
    assert_eq!(
        note,
        "Only this Thursday changed. To change every week, open School hours."
    );
}

#[test]
fn a_week_holding_only_a_piece_of_school_does_not_get_school_again() {
    let only_piece = vec![piece()];
    assert_eq!(with_standing(&only_piece, &[school()]), only_piece);
    // An account from before the standing week stands School once, by its own id.
    let weeks = vec![("2026-11-09".to_string(), week())];
    let (_, standing) = derive_standing(&weeks).unwrap().unwrap();
    assert_eq!(standing.len(), 1, "{standing:?}");
    assert_eq!(standing[0]["id"], "school");
}

#[test]
fn deleting_any_piece_of_school_deletes_school() {
    let delete = |id: &str, every_week: bool| {
        delete_block(
            &week(),
            &Map::new(),
            "2026-11-09",
            id,
            "series",
            None,
            "2026-11-09",
            8 * 60,
            every_week,
        )
        .unwrap()
        .blocks
    };
    // This week only: every piece stays, missed on each of its days.
    let this_week = delete("school@20261111", false);
    assert_eq!(this_week.len(), 2, "{this_week:?}");
    for block in &this_week {
        assert_eq!(block["missed_days"], block["days"], "{block}");
    }
    // This week and later: every piece goes.
    assert!(delete("school@20261111", true).is_empty());
    assert!(delete("school", true).is_empty());
}

#[test]
fn a_piece_of_another_block_leaves_school_alone() {
    let read = json!({"id": "read@20261111", "title": "Read", "kind": "locked",
                      "start": "19:00", "duration_min": 30, "days": [2]});
    let blocks: Vec<Value> = [week(), vec![read.clone()]].concat();
    let left = delete_block(
        &blocks,
        &Map::new(),
        "2026-11-09",
        "read@20261111",
        "series",
        None,
        "2026-11-09",
        8 * 60,
        false,
    )
    .unwrap()
    .blocks;
    assert_eq!(left, week());
}

/// The days of `week` on which School shows (not missed), one entry per piece that holds the day.
fn school_days(week: &[Value]) -> Vec<i64> {
    let mut days: Vec<i64> = week
        .iter()
        .filter(|block| family_id(block["id"].as_str().unwrap()) == "school")
        .flat_map(|block| {
            let missed: Vec<i64> = block["missed_days"]
                .as_array()
                .map(|items| items.iter().map(|day| day.as_i64().unwrap()).collect())
                .unwrap_or_default();
            block["days"]
                .as_array()
                .unwrap()
                .iter()
                .map(|day| day.as_i64().unwrap())
                .filter(move |day| !missed.contains(day))
                .collect::<Vec<_>>()
        })
        .collect();
    days.sort_unstable();
    days
}

#[test]
fn a_day_added_to_school_in_two_pieces_is_school_once_that_day() {
    // School on Saturday too, from 9 November on. Saturday 14 November is School once, on the days
    // that follow the repeat (`school`, 08:30); the piece keeps Wednesday to Friday at 10:00.
    let saturday = parse_intent(&json!({"id": "school", "scope": "from",
                                        "from_date": "2026-11-09", "add_days": [5]}))
    .unwrap();
    let (blocks, _) = apply_to_week(&week(), &[school()], &[saturday]).unwrap();
    assert_eq!(school_days(&blocks), vec![0, 1, 2, 3, 4, 5], "{blocks:?}");
    assert_eq!(by_id(&blocks, "school")["days"], json!([0, 1, 5]));
    assert_eq!(by_id(&blocks, "school@20261111")["days"], json!([2, 3, 4]));
    // A week holding only a piece gives that piece the new day.
    let (blocks, _) = apply_to_week(
        &[piece()],
        &[school()],
        &[parse_intent(&json!({"id": "school", "scope": "from",
                               "from_date": "2026-11-09", "add_days": [5]}))
        .unwrap()],
    )
    .unwrap();
    assert_eq!(school_days(&blocks), vec![2, 3, 4, 5], "{blocks:?}");
}

#[test]
fn a_day_added_to_school_takes_the_repeats_time_when_schools_own_piece_was_changed() {
    // This time `school` is the piece the week changed (Monday and Tuesday at 10:00) and the tagged
    // piece follows the repeat (Wednesday to Friday at 08:30). Saturday 14 November is School once,
    // at the repeat's 08:30, and Monday and Tuesday keep their 10:00.
    let mut changed = kept();
    changed["start"] = json!("10:00");
    let mut follows = piece();
    follows["start"] = json!("08:30");
    let saturday = parse_intent(&json!({"id": "school", "scope": "from",
                                        "from_date": "2026-11-09", "add_days": [5]}))
    .unwrap();
    let (blocks, _) = apply_to_week(&[changed, follows], &[school()], &[saturday]).unwrap();
    assert_eq!(school_days(&blocks), vec![0, 1, 2, 3, 4, 5], "{blocks:?}");
    let own = by_id(&blocks, "school");
    assert_eq!(
        (&own["days"], &own["start"]),
        (&json!([0, 1]), &json!("10:00"))
    );
    let tagged = by_id(&blocks, "school@20261111");
    assert_eq!(
        (&tagged["days"], &tagged["start"]),
        (&json!([2, 3, 4, 5]), &json!("08:30"))
    );
    // When both pieces follow the repeat, School's own id takes the day wherever it sits in the week.
    let mut follows = piece();
    follows["start"] = json!("08:30");
    let (blocks, _) = apply_to_week(
        &[follows, kept()],
        &[school()],
        &[parse_intent(&json!({"id": "school", "scope": "from",
                               "from_date": "2026-11-09", "add_days": [5]}))
        .unwrap()],
    )
    .unwrap();
    assert_eq!(by_id(&blocks, "school")["days"], json!([0, 1, 5]));
    assert_eq!(by_id(&blocks, "school@20261111")["days"], json!([2, 3, 4]));
}

#[test]
fn a_standing_school_built_from_pieces_keeps_every_day_at_the_time_most_of_them_have() {
    // School on Monday and Tuesday at 08:30 and on Wednesday to Friday at 10:00 stands on all five
    // days at 10:00, the time of the piece that holds the most days.
    let weeks = vec![("2026-11-09".to_string(), week())];
    let (from, standing) = derive_standing(&weeks).unwrap().unwrap();
    assert_eq!(from, "2026-11-09");
    assert_eq!(
        standing,
        vec![
            json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
                    "start": "10:00", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
        ]
    );
    // Pieces holding as many days each: School's own id gives the time.
    let mut two = kept();
    two["days"] = json!([0, 1]);
    let mut other = piece();
    other["days"] = json!([3, 4]);
    let weeks = vec![("2026-11-09".to_string(), vec![other, two])];
    let (_, standing) = derive_standing(&weeks).unwrap().unwrap();
    assert_eq!(standing[0]["start"], "08:30");
    assert_eq!(standing[0]["days"], json!([0, 1, 3, 4]));
}
