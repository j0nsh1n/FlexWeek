//! The standing week (fix-specs item 1): School and activities from Setup stand in every week from
//! Setup's week on; a week's own version of a standing block wins for that week.

use flexweek_engine::desk::blocks::until_problem;
use flexweek_engine::desk::grid::{is_setup_block, is_standing_block};
use flexweek_engine::standing::{
    derive_standing, restand, restated, standing_body, trim_until, with_standing,
};
use flexweek_engine::validate;
use serde_json::{Value, json};

const WEEK: &str = "2026-10-05";

fn school() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "category": "class",
           "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
}

fn soccer() -> Value {
    json!({"id": "activity-1", "title": "Soccer", "kind": "locked", "category": "extra",
           "start": "16:00", "duration_min": 90, "days": [1, 3]})
}

fn gym() -> Value {
    json!({"id": "gym", "title": "Gym", "kind": "locked", "start": "18:00", "duration_min": 60, "days": [2]})
}

fn ids(week: &[Value]) -> Vec<&str> {
    week.iter().map(|b| b["id"].as_str().unwrap()).collect()
}

#[test]
fn an_unsaved_week_gets_every_standing_block() {
    let week = with_standing(&[], &[school(), soccer()], WEEK).unwrap();
    assert_eq!(week, vec![school(), soccer()]);
}

#[test]
fn a_weeks_own_version_of_a_standing_block_wins() {
    let mut missed_wednesday = school();
    missed_wednesday["missed_days"] = json!([2]);
    let week = with_standing(
        &[missed_wednesday.clone(), gym()],
        &[school(), soccer()],
        WEEK,
    )
    .unwrap();
    assert_eq!(week, vec![missed_wednesday, gym(), soccer()]);
}

#[test]
fn the_standing_body_drops_missed_days() {
    let mut block = school();
    block["missed_days"] = json!([2]);
    assert_eq!(standing_body(&block), school());
}

#[test]
fn restand_moves_school_to_the_new_times_and_keeps_missed_days_still_school_days() {
    let mut stored = school();
    stored["missed_days"] = json!([2, 4]);
    let mut new = school();
    new["start"] = json!("09:00");
    new["duration_min"] = json!(360);
    new["days"] = json!([0, 1, 2, 3]);
    let week = restand(&[stored, gym()], &[new.clone(), soccer()], WEEK).unwrap();
    let mut expected = new;
    expected["missed_days"] = json!([2]);
    // Soccer is not written in: the read path adds it, and Gym is not Setup's.
    assert_eq!(week, vec![expected, gym()]);
}

#[test]
fn restand_keeps_a_block_removed_just_this_week_removed() {
    let mut stored = soccer();
    stored["missed_days"] = json!([1, 3]);
    let mut new = soccer();
    new["days"] = json!([0, 2, 4]);
    let week = restand(&[stored], &[new], WEEK).unwrap();
    assert_eq!(week[0]["missed_days"], json!([0, 2, 4]));
}

#[test]
fn restand_removes_a_setup_block_that_no_longer_stands() {
    let week = restand(&[school(), soccer(), gym()], &[school()], WEEK).unwrap();
    assert_eq!(ids(&week), vec!["school", "gym"]);
}

#[test]
fn derive_takes_the_newest_week_with_setup_blocks() {
    let mut old_school = school();
    old_school["start"] = json!("08:00");
    let mut missed = school();
    missed["missed_days"] = json!([0]);
    let weeks = vec![
        ("2026-09-28".to_string(), vec![old_school]),
        ("2026-10-12".to_string(), vec![gym()]),
        ("2026-10-05".to_string(), vec![missed, soccer(), gym()]),
    ];
    let (from, blocks) = derive_standing(&weeks).unwrap().unwrap();
    assert_eq!(from, "2026-10-05");
    assert_eq!(blocks, vec![school(), soccer()]);
}

#[test]
fn derive_finds_nothing_without_setup_blocks() {
    let weeks = vec![("2026-10-05".to_string(), vec![gym()])];
    assert_eq!(derive_standing(&weeks).unwrap(), None);
}

#[test]
fn the_first_week_cards_sport_counts_as_standing() {
    let sport = json!({"id": "sport", "title": "Swim", "kind": "locked", "start": "17:00",
                       "duration_min": 60, "days": [0]});
    let weeks = vec![("2026-10-05".to_string(), vec![sport.clone()])];
    assert_eq!(derive_standing(&weeks).unwrap().unwrap().1, vec![sport]);
}

// Dec 2026: Mon 30 Nov, Mon 7 Dec, Tue 8 Dec, Wed 9 Dec, Thu 10 Dec, Sat 12 Dec, Mon 14 Dec, Mon 28 Dec.
fn piano(until: Option<&str>) -> Value {
    let mut block = json!({"id": "weekly-piano", "title": "Piano", "kind": "locked", "category": "extra",
                           "start": "16:00", "duration_min": 60, "days": [1, 3]});
    if let Some(until) = until {
        block["until"] = json!(until);
    }
    block
}

fn days_in(week_start: &str, standing: &[Value]) -> Option<Value> {
    with_standing(&[], standing, week_start)
        .unwrap()
        .into_iter()
        .find(|block| block["id"] == "weekly-piano")
        .map(|block| block["days"].clone())
}

#[test]
fn a_weekly_block_without_until_stands_in_every_later_week() {
    let standing = [piano(None)];
    for week in ["2026-11-30", "2026-12-07", "2026-12-14", "2026-12-28"] {
        assert_eq!(days_in(week, &standing), Some(json!([1, 3])), "{week}");
    }
}

#[test]
fn until_is_inclusive_so_a_saturday_keeps_the_thursday_before_it() {
    let standing = [piano(Some("2026-12-12"))];
    assert_eq!(days_in("2026-12-07", &standing), Some(json!([1, 3])));
    assert_eq!(days_in("2026-12-14", &standing), None);
}

#[test]
fn until_on_a_wednesday_leaves_only_the_tuesday_of_that_week() {
    let standing = [piano(Some("2026-12-09"))];
    assert_eq!(days_in("2026-11-30", &standing), Some(json!([1, 3])));
    assert_eq!(days_in("2026-12-07", &standing), Some(json!([1])));
    assert_eq!(days_in("2026-12-14", &standing), None);
}

#[test]
fn until_on_the_last_day_still_shows_that_day() {
    let standing = [piano(Some("2026-12-10"))];
    assert_eq!(days_in("2026-12-07", &standing), Some(json!([1, 3])));
}

#[test]
fn trim_until_cuts_the_days_after_until_in_the_given_week_and_keeps_the_rest_of_the_block() {
    let trimmed = trim_until(&piano(Some("2026-12-08")), "2026-12-07")
        .unwrap()
        .unwrap();
    assert_eq!(trimmed["days"], json!([1]));
    assert_eq!(trimmed["until"], json!("2026-12-08"));
    assert_eq!(trimmed["start"], json!("16:00"));
}

#[test]
fn trim_until_leaves_a_block_with_no_until_or_with_every_day_inside_it_as_it_is() {
    assert_eq!(
        trim_until(&piano(None), "2026-12-07").unwrap(),
        Some(piano(None))
    );
    let whole = piano(Some("2026-12-10"));
    assert_eq!(
        trim_until(&whole, "2026-12-07").unwrap(),
        Some(whole.clone())
    );
}

#[test]
fn trim_until_drops_the_block_when_no_day_is_left_in_that_week() {
    assert_eq!(
        trim_until(&piano(Some("2026-12-09")), "2026-12-14").unwrap(),
        None
    );
}

#[test]
fn a_trimmed_block_keeps_its_until_so_the_sheet_can_show_it() {
    let week = with_standing(&[], &[piano(Some("2026-12-09"))], "2026-12-07").unwrap();
    assert_eq!(week[0]["until"], json!("2026-12-09"));
}

#[test]
fn a_weeks_own_copy_is_shown_as_stored_even_past_until() {
    let own = piano(Some("2026-12-09"));
    let week = with_standing(
        std::slice::from_ref(&own),
        std::slice::from_ref(&own),
        "2026-12-14",
    )
    .unwrap();
    assert_eq!(week, vec![own]);
}

#[test]
fn restand_trims_a_saved_later_week_to_until_and_drops_a_week_past_it() {
    let stored = piano(None);
    let new = piano(Some("2026-12-09"));
    let inside = restand(
        std::slice::from_ref(&stored),
        std::slice::from_ref(&new),
        "2026-12-07",
    )
    .unwrap();
    assert_eq!(inside[0]["days"], json!([1]));
    assert_eq!(inside[0]["until"], json!("2026-12-09"));
    let past = restand(&[stored], &[new], "2026-12-14").unwrap();
    assert!(past.is_empty());
}

#[test]
fn restand_keeps_a_weekly_block_removed_just_this_week_removed_within_until() {
    let mut stored = piano(None);
    stored["missed_days"] = json!([1, 3]);
    let week = restand(&[stored], &[piano(Some("2026-12-09"))], "2026-12-07").unwrap();
    assert_eq!(week[0]["missed_days"], json!([1]));
}

#[test]
fn a_weekly_block_stands_but_is_not_a_setup_block() {
    assert!(is_standing_block(&piano(None)).unwrap());
    assert!(!is_setup_block(&piano(None)).unwrap());
    assert!(is_standing_block(&school()).unwrap());
    assert!(is_standing_block(&soccer()).unwrap());
    assert!(!is_standing_block(&gym()).unwrap());
}

#[test]
fn restand_moves_and_drops_weekly_blocks_like_setup_ones() {
    let mut moved = piano(None);
    moved["start"] = json!("17:00");
    let week = restand(&[piano(None), gym()], &[moved.clone()], "2026-12-07").unwrap();
    assert_eq!(week, vec![moved, gym()]);
    let dropped = restand(&[piano(None), gym()], &[], "2026-12-07").unwrap();
    assert_eq!(ids(&dropped), vec!["gym"]);
}

#[test]
fn derive_leaves_weekly_blocks_to_their_own_rows() {
    let weeks = vec![("2026-12-07".to_string(), vec![piano(None), school()])];
    assert_eq!(derive_standing(&weeks).unwrap().unwrap().1, vec![school()]);
}

#[test]
fn until_before_the_first_day_is_refused_with_the_date_in_words() {
    // Saved from the week of Mon 7 Dec, a Tue and Thu block first occurs on Tue 8 Dec.
    let problem = until_problem(&piano(Some("2026-12-07")), "2026-12-07", "2026-12-07").unwrap();
    assert_eq!(
        problem.as_deref(),
        Some("Until can't be before the first day, Tue 8 Dec.")
    );
}

#[test]
fn until_on_the_first_day_or_later_or_none_is_allowed() {
    for until in [Some("2026-12-08"), Some("2026-12-12"), Some(""), None] {
        assert_eq!(
            until_problem(&piano(until), "2026-12-07", "2026-12-07").unwrap(),
            None,
            "{until:?}"
        );
    }
}

#[test]
fn the_first_day_is_the_earliest_day_the_block_holds() {
    let mut block = piano(Some("2026-12-09"));
    block["days"] = json!([3, 1]);
    assert_eq!(
        until_problem(&block, "2026-12-07", "2026-12-07").unwrap(),
        None
    );
    block["until"] = json!("2026-12-07");
    assert!(
        until_problem(&block, "2026-12-07", "2026-12-07")
            .unwrap()
            .is_some()
    );
}

#[test]
fn a_row_saved_by_1_3_0_loads_and_writes_back_unchanged() {
    let old = r#"{"id":"school","title":"School","kind":"locked","duration_min":405,"days":[0,1,2,3,4],"priority":3,"energy":"medium","earliest":null,"latest":null,"start":"08:30","course":null,"category":"class","missed_days":[2]}"#;
    let value: Value = serde_json::from_str(old).unwrap();
    let block = validate::time_block(&value).unwrap();
    assert_eq!(serde_json::to_string(&block.to_value()).unwrap(), old);
}

#[test]
fn until_is_written_right_after_missed_days_and_must_be_a_date() {
    let mut block = piano(Some("2026-12-12"));
    block["missed_days"] = json!([1]);
    block["spotify_url"] = json!("https://open.spotify.com/track/abc");
    let written = serde_json::to_string(&validate::time_block(&block).unwrap().to_value()).unwrap();
    let at = |key: &str| written.find(&format!("\"{key}\"")).unwrap();
    assert!(
        at("missed_days") < at("until") && at("until") < at("spotify_url"),
        "{written}"
    );
    let mut bad = piano(Some("12 Dec"));
    bad["until"] = json!("12 Dec");
    assert!(validate::time_block(&bad).is_err());
}

fn piano_on(days: &[i64], until: Option<&str>) -> Value {
    let mut block = piano(until);
    block["days"] = json!(days);
    block
}

#[test]
fn a_change_from_a_week_until_cut_keeps_the_days_the_block_stood_on() {
    // Piano stands on Tuesday and Thursday until Wednesday 9 December, so the week of 7 December holds
    // Tuesday alone. Moving Until to 15 December from that week sends Tuesday; Thursday must survive.
    let before = piano_on(&[1, 3], Some("2026-12-09"));
    let change = piano_on(&[1], Some("2026-12-15"));
    assert_eq!(
        restated(&before, &change, "2026-12-07").unwrap(),
        piano_on(&[1, 3], Some("2026-12-15"))
    );
}

#[test]
fn a_change_from_a_cut_week_that_picks_other_days_keeps_them() {
    let before = piano_on(&[1, 3], Some("2026-12-09"));
    let change = piano_on(&[2], Some("2026-12-15"));
    assert_eq!(restated(&before, &change, "2026-12-07").unwrap(), change);
    let more = piano_on(&[1, 3, 4], Some("2026-12-15"));
    assert_eq!(restated(&before, &more, "2026-12-07").unwrap(), more);
}

#[test]
fn a_change_from_a_week_until_did_not_cut_is_kept_as_sent() {
    // The week of 30 November has both days, so dropping Thursday there is the student's choice.
    let before = piano_on(&[1, 3], Some("2026-12-09"));
    let tuesday_only = piano_on(&[1], Some("2026-12-09"));
    assert_eq!(
        restated(&before, &tuesday_only, "2026-11-30").unwrap(),
        tuesday_only
    );
    let open_ended = piano_on(&[1, 3], None);
    let cut_short = piano_on(&[1], Some("2026-12-09"));
    assert_eq!(
        restated(&open_ended, &cut_short, "2026-12-07").unwrap(),
        cut_short
    );
}

#[test]
fn a_change_sent_after_until_has_passed_is_kept_as_sent() {
    // Nothing is left of the block in the week of 14 December, so no days there were cut from view.
    let before = piano_on(&[1, 3], Some("2026-12-09"));
    let again = piano_on(&[1], None);
    assert_eq!(restated(&before, &again, "2026-12-14").unwrap(), again);
}
