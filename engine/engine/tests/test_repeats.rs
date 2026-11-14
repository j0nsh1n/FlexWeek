//! Repeating blocks changed by what the student meant (`flexweek_engine::repeats`): a change names
//! a date and only what it changes, and a week's own changes survive a change to the repeat.
//! Dates are real: Monday 9 November 2026 is the open week, 16 and 23 November are later weeks.

use flexweek_engine::repeats::{
    Intent, Kept, NEW_NEEDS_ALL, NOTHING_LEFT, RULE, apply_to_week, edit_intent, edited_weeks_line,
    intents_between, kept_notice, leaves_week, one_day_note, own_changes, parse_intent, patched,
    pieces_after_replace, restated_copy, restated_version, this_week_line, three_way,
};
use serde_json::{Value, json};

const OPEN_WEEK: &str = "2026-11-09";

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

fn with(base: Value, changes: Value) -> Value {
    let mut out = base;
    for (key, value) in changes.as_object().unwrap() {
        out[key] = value.clone();
    }
    out
}

fn intent(value: Value) -> Intent {
    parse_intent(&value).unwrap()
}

// --- what a change may say ---------------------------------------------------------------------

#[test]
fn a_change_names_a_repeat_a_date_and_only_fields_a_form_edits() {
    let refused = [
        json!({"id": "gym", "scope": "from", "from_date": OPEN_WEEK, "set": {"start": "09:00"}}),
        json!({"id": "school", "scope": "date", "from_date": OPEN_WEEK}),
        json!({"id": "school", "scope": "from", "from_date": "2026-11-31"}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "set": {"days": [1]}}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "set": {"missed_days": [1]}}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "add_days": [7]}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "add_days": [1], "remove_days": [1]}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "stop": true, "set": {"start": "09:00"}}),
        json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "body": school()}),
    ];
    for value in refused {
        assert_eq!(parse_intent(&value), Err(RULE.to_string()), "{value}");
    }
    let taken = intent(
        json!({"id": "activity-3f2a9c01", "scope": "from", "from_date": "2026-11-12",
                              "set": {"start": "17:00"}, "add_days": [5]}),
    );
    // Thursday 12 November is in the week of Monday 9 November.
    assert_eq!(taken.from_week().unwrap(), OPEN_WEEK);
}

#[test]
fn a_patch_changes_only_what_it_names() {
    let changed = patched(
        Some(&school()),
        &intent(
            json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK,
                       "set": {"duration_min": 360}, "add_days": [5], "remove_days": [2]}),
        ),
    )
    .unwrap();
    assert_eq!(
        changed,
        Some(with(
            school(),
            json!({"duration_min": 360, "days": [0, 1, 3, 4, 5]})
        ))
    );
}

#[test]
fn a_new_repeat_needs_everything_and_a_change_cannot_leave_no_day() {
    let new = json!({"id": "activity-2", "scope": "from", "from_date": OPEN_WEEK,
                     "set": {"title": "Piano", "start": "17:00", "duration_min": 45}, "add_days": [1]});
    assert_eq!(
        patched(None, &intent(new)).unwrap(),
        Some(
            json!({"id": "activity-2", "kind": "locked", "title": "Piano", "start": "17:00",
                    "duration_min": 45, "days": [1]})
        )
    );
    let no_start = json!({"id": "activity-2", "scope": "from", "from_date": OPEN_WEEK,
                          "set": {"title": "Piano", "duration_min": 45}, "add_days": [1]});
    assert_eq!(
        patched(None, &intent(no_start)),
        Err(NEW_NEEDS_ALL.to_string())
    );
    let empties = json!({"id": "activity-1", "scope": "from", "from_date": OPEN_WEEK,
                         "remove_days": [1, 3]});
    assert_eq!(
        patched(Some(&soccer()), &intent(empties)),
        Err(NOTHING_LEFT.to_string())
    );
    let stop = json!({"id": "activity-1", "scope": "from", "from_date": OPEN_WEEK, "stop": true});
    assert_eq!(patched(Some(&soccer()), &intent(stop)), Ok(None));
}

#[test]
fn a_form_sends_only_what_differs_from_the_repeat() {
    // School hours showing the usual days, with only the end moved from 15:15 to 14:30.
    let edited = with(school(), json!({"duration_min": 360}));
    let made = edit_intent("school", OPEN_WEEK, Some(&school()), Some(&edited)).unwrap();
    assert_eq!(
        made.set,
        json!({"duration_min": 360}).as_object().unwrap().clone()
    );
    assert!(made.add_days.is_empty() && made.remove_days.is_empty() && !made.stop);
    assert_eq!(
        edit_intent("school", OPEN_WEEK, Some(&school()), Some(&school())),
        None
    );
    // No day ticked takes the repeat away from this week on.
    assert!(
        edit_intent("school", OPEN_WEEK, Some(&school()), None)
            .unwrap()
            .stop
    );
    assert_eq!(edit_intent("school", OPEN_WEEK, None, None), None);
    let created = edit_intent("activity-1", OPEN_WEEK, None, Some(&soccer())).unwrap();
    assert_eq!(created.add_days, vec![1, 3]);
    assert_eq!(
        patched(None, &created).unwrap().unwrap()["title"],
        json!("Soccer")
    );
}

// --- the three-way merge ------------------------------------------------------------------------

#[test]
fn a_copy_takes_the_new_times_keeps_missed_days_still_school_days_and_drops_a_day_it_shared() {
    let copy = with(school(), json!({"missed_days": [2, 4]}));
    let new = with(
        school(),
        json!({"start": "09:00", "duration_min": 360, "days": [0, 1, 2, 3]}),
    );
    let merged = three_way(&school(), &new, &copy);
    assert_eq!(merged, with(new, json!({"missed_days": [2]})));
}

#[test]
fn a_block_taken_out_just_this_week_stays_out_when_its_days_change() {
    let copy = with(soccer(), json!({"missed_days": [1, 3]}));
    let new = with(soccer(), json!({"days": [0, 2, 4]}));
    let merged = three_way(&soccer(), &new, &copy);
    assert_eq!(merged["days"], json!([0, 2, 4]));
    assert_eq!(merged["missed_days"], json!([0, 2, 4]));
}

#[test]
fn a_repeat_that_stops_leaves_the_week_and_a_week_own_block_stays() {
    assert_eq!(restated_copy(Some(&soccer()), None, &soccer()), None);
    assert_eq!(restated_copy(None, Some(&gym()), &gym()), Some(gym()));
}

#[test]
fn a_day_deleted_this_week_stays_deleted_when_the_repeat_changes() {
    // P2: Wednesday deleted in a later week, then School hours change from an earlier week.
    let copy = with(school(), json!({"days": [0, 1, 3, 4]}));
    let new = with(school(), json!({"duration_min": 360}));
    let merged = three_way(&school(), &new, &copy);
    assert_eq!(
        merged,
        with(school(), json!({"days": [0, 1, 3, 4], "duration_min": 360}))
    );
}

#[test]
fn a_name_and_start_set_this_week_survive_a_change_to_the_end() {
    // P4: "School trip" at 07:00 for one week, then the end changes every week.
    let trip = with(school(), json!({"title": "School trip", "start": "07:00"}));
    let new = with(school(), json!({"duration_min": 360}));
    let merged = three_way(&school(), &new, &trip);
    assert_eq!(merged["title"], json!("School trip"));
    assert_eq!(merged["start"], json!("07:00"));
    assert_eq!(merged["duration_min"], json!(360));
}

#[test]
fn a_day_the_repeat_gains_reaches_a_copy_unless_that_week_already_decided_it() {
    let new = with(soccer(), json!({"days": [1, 3, 5]}));
    assert_eq!(
        three_way(&soccer(), &new, &soccer())["days"],
        json!([1, 3, 5])
    );
    // That week already had Soccer on Saturday as its own extra day: still there, once.
    let own_saturday = with(soccer(), json!({"days": [1, 3, 5]}));
    assert_eq!(
        three_way(&soccer(), &new, &own_saturday)["days"],
        json!([1, 3, 5])
    );
}

#[test]
fn a_copy_left_with_no_day_shows_nothing_rather_than_the_repeat() {
    let only_wednesday = with(school(), json!({"days": [2]}));
    let new = with(school(), json!({"days": [0, 1, 3, 4]}));
    let merged = three_way(&school(), &new, &only_wednesday);
    assert_eq!(merged["days"], json!([0, 1, 3, 4]));
    assert_eq!(merged["missed_days"], json!([0, 1, 3, 4]));
}

#[test]
fn a_later_stop_stays_a_stop_and_a_later_change_keeps_what_it_set() {
    // P5 at the level of versions: Soccer ended from a later week.
    let new = with(soccer(), json!({"start": "17:00"}));
    assert_eq!(restated_version(Some(&soccer()), Some(&new), None), None);
    let later = with(soccer(), json!({"title": "Football"}));
    assert_eq!(
        restated_version(Some(&soccer()), Some(&new), Some(&later)),
        Some(with(
            soccer(),
            json!({"title": "Football", "start": "17:00"})
        ))
    );
}

// --- the open week ------------------------------------------------------------------------------

#[test]
fn school_hours_in_a_week_with_wednesday_skipped_keeps_wednesday_in_the_repeat() {
    // P1: Wednesday deleted this week, then School hours (showing the usual days) moves the end.
    let week = vec![with(school(), json!({"days": [0, 1, 3, 4]})), gym()];
    let edited = with(school(), json!({"duration_min": 360}));
    let change = edit_intent("school", OPEN_WEEK, Some(&school()), Some(&edited)).unwrap();
    let (shown, repeats) =
        apply_to_week(&week, &[school()], std::slice::from_ref(&change)).unwrap();
    assert_eq!(repeats, vec![with(school(), json!({"duration_min": 360}))]);
    assert_eq!(
        shown,
        vec![
            with(school(), json!({"days": [0, 1, 3, 4], "duration_min": 360})),
            gym()
        ]
    );
    // The store's own pass over the saved open week then changes nothing.
    let (again, _) = apply_to_week(&shown, &[school()], &[change]).unwrap();
    assert_eq!(again, shown);
}

#[test]
fn setup_again_keeps_school_deleted_for_this_week_only() {
    // Item 7: School deleted this week only, then Setup changes School's start every week.
    let gone = with(school(), json!({"missed_days": [0, 1, 2, 3, 4]}));
    let edited = with(school(), json!({"start": "08:00", "duration_min": 435}));
    let change = edit_intent("school", OPEN_WEEK, Some(&school()), Some(&edited)).unwrap();
    let (shown, _) = apply_to_week(&[gone], &[school()], &[change]).unwrap();
    assert_eq!(shown[0]["missed_days"], json!([0, 1, 2, 3, 4]));
    assert_eq!(shown[0]["start"], json!("08:00"));
}

#[test]
fn a_new_repeat_shows_in_the_open_week_and_a_stopped_one_leaves_it() {
    let piano = json!({"id": "activity-2", "title": "Piano", "kind": "locked", "start": "17:00",
                       "duration_min": 45, "days": [1]});
    let add = edit_intent("activity-2", OPEN_WEEK, None, Some(&piano)).unwrap();
    let stop = edit_intent("activity-1", OPEN_WEEK, Some(&soccer()), None).unwrap();
    let (shown, repeats) =
        apply_to_week(&[school(), soccer()], &[school(), soccer()], &[add, stop]).unwrap();
    let ids: Vec<&str> = shown.iter().map(|b| b["id"].as_str().unwrap()).collect();
    assert_eq!(ids, vec!["school", "activity-2"]);
    assert_eq!(repeats.len(), 2);
}

// --- words --------------------------------------------------------------------------------------

#[test]
fn the_school_hours_line_names_this_weeks_own_changes() {
    let week = vec![with(school(), json!({"days": [0, 1, 3, 4]})), soccer()];
    assert_eq!(
        this_week_line(&week, &[school(), soccer()], false).as_deref(),
        Some("This week: no School on Wednesday.")
    );
    assert_eq!(
        this_week_line(&[school(), soccer()], &[school(), soccer()], false),
        None
    );
    let gone = vec![with(school(), json!({"missed_days": [0, 1, 2, 3, 4]}))];
    assert_eq!(
        this_week_line(&gone, &[school()], false).as_deref(),
        Some("This week: no School that week.")
    );
}

#[test]
fn a_day_moved_to_its_own_block_reads_as_moved_and_times_follow_the_clock() {
    let split = json!({"id": "98f0907e", "title": "School", "kind": "locked", "category": "class",
                       "start": "10:00", "duration_min": 120, "days": [2]});
    let week = vec![with(school(), json!({"days": [0, 1, 3, 4]})), split];
    assert_eq!(
        own_changes(&week[0], &school(), &week, false),
        vec!["School at 10:00 AM–12:00 PM on Wednesday"]
    );
    assert_eq!(
        own_changes(&week[0], &school(), &week, true),
        vec!["School at 10:00–12:00 on Wednesday"]
    );
    let trip = with(school(), json!({"title": "School trip", "start": "07:00"}));
    assert_eq!(
        own_changes(&trip, &school(), std::slice::from_ref(&trip), true),
        vec!["called School trip", "School at 07:00–13:45"]
    );
    let saturday = with(soccer(), json!({"days": [1, 3, 5]}));
    assert_eq!(
        own_changes(&saturday, &soccer(), std::slice::from_ref(&saturday), true),
        vec!["Soccer on Saturday too"]
    );
}

#[test]
fn the_notice_names_each_later_week_that_kept_its_own_change() {
    let kept = vec![Kept {
        week_start: "2026-11-16".into(),
        id: "school".into(),
        changes: vec!["no School on Wednesday".into()],
    }];
    assert_eq!(
        kept_notice(&["School".into()], OPEN_WEEK, &kept)
            .unwrap()
            .as_deref(),
        Some(
            "School changed from this week on. The week of 16 Nov keeps its own change: no School on Wednesday."
        )
    );
    assert_eq!(
        kept_notice(&["School".into()], OPEN_WEEK, &[]).unwrap(),
        None
    );
    let many: Vec<Kept> = [
        "2026-11-16",
        "2026-11-23",
        "2026-11-30",
        "2026-12-07",
        "2027-01-04",
    ]
    .iter()
    .map(|week| Kept {
        week_start: (*week).into(),
        id: "activity-1".into(),
        changes: vec!["no Soccer that week".into()],
    })
    .collect();
    let said = kept_notice(&["School".into(), "Soccer".into()], OPEN_WEEK, &many)
        .unwrap()
        .unwrap();
    assert_eq!(
        said,
        "School and Soccer changed from this week on. \
         The week of 16 Nov keeps its own change: no Soccer that week. \
         The week of 23 Nov keeps its own change: no Soccer that week. \
         The week of 30 Nov keeps its own change: no Soccer that week. \
         2 more weeks keep their own changes too."
    );
}

#[test]
fn moving_one_day_of_a_repeat_says_only_that_day_changed_and_where_every_week_is_changed() {
    assert_eq!(
        one_day_note(&school(), 2, true).unwrap().as_deref(),
        Some("Only this Wednesday changed. To change every week, open School hours.")
    );
    assert_eq!(
        one_day_note(&school(), 2, false).unwrap().as_deref(),
        Some("Only this Wednesday changed. To change every week, run setup again from Settings.")
    );
    assert_eq!(
        one_day_note(&soccer(), 3, true).unwrap().as_deref(),
        Some("Only this Thursday changed. To change every week, run setup again from Settings.")
    );
    assert_eq!(one_day_note(&gym(), 2, true).unwrap(), None);
}

#[test]
fn the_changes_between_two_lists_of_repeats_are_patches_new_repeats_and_stops() {
    let piano = json!({"id": "activity-7c1e", "title": "Piano", "kind": "locked", "start": "17:00",
                       "duration_min": 45, "days": [1]});
    let later_school = with(school(), json!({"start": "09:00"}));
    let made = intents_between(&[school(), soccer()], &[later_school, piano], OPEN_WEEK);
    let values: Vec<Value> = made.iter().map(Intent::to_value).collect();
    assert_eq!(
        values,
        vec![
            json!({"id": "school", "scope": "from", "from_date": OPEN_WEEK, "set": {"start": "09:00"},
                   "add_days": [], "remove_days": [], "stop": false}),
            json!({"id": "activity-7c1e", "scope": "from", "from_date": OPEN_WEEK,
                   "set": {"title": "Piano", "start": "17:00", "duration_min": 45},
                   "add_days": [1], "remove_days": [], "stop": false}),
            json!({"id": "activity-1", "scope": "from", "from_date": OPEN_WEEK, "set": {},
                   "add_days": [], "remove_days": [], "stop": true}),
        ]
    );
    assert!(intents_between(&[school()], &[school()], OPEN_WEEK).is_empty());
}

fn from_today(today: &str) -> Intent {
    intent(json!({
        "id": "school", "scope": "from", "from_date": "2026-11-02",
        "set": {"duration_min": 360}, "edited": "from_today", "today": today,
    }))
}

#[test]
fn a_change_may_say_how_edited_weeks_are_treated() {
    let keep = intent(json!({
        "id": "school", "scope": "from", "from_date": OPEN_WEEK,
        "set": {"duration_min": 360}, "edited": "keep",
    }));
    assert_eq!(keep.edited, flexweek_engine::repeats::Edited::Keep);
    assert!(keep.today.is_none());
    let replace = intent(json!({
        "id": "school", "scope": "from", "from_date": OPEN_WEEK,
        "set": {"duration_min": 360}, "edited": "replace",
    }));
    assert_eq!(replace.to_value()["edited"], json!("replace"));
    assert_eq!(
        parse_intent(&json!({
            "id": "school", "scope": "from", "from_date": OPEN_WEEK,
            "edited": "from_today",
        })),
        Err(RULE.to_string())
    );
    assert_eq!(
        parse_intent(&json!({
            "id": "school", "scope": "from", "from_date": OPEN_WEEK,
            "edited": "sideways", "set": {"duration_min": 360},
        })),
        Err(RULE.to_string())
    );
}

#[test]
fn from_today_leaves_this_week_and_every_earlier_week() {
    // Thursday 5 November 2026: today's week is Monday 2 November, so the next week is 9 November.
    let change = from_today("2026-11-05");
    assert!(leaves_week(&change, "2026-11-02").unwrap());
    assert!(!leaves_week(&change, "2026-11-09").unwrap());
    // A week on screen from Wednesday 4 November is still today's week (its Monday is 2 November).
    assert!(leaves_week(&change, "2026-11-04").unwrap());
    let keeping = intent(json!({
        "id": "school", "scope": "from", "from_date": OPEN_WEEK, "set": {"duration_min": 360},
    }));
    assert!(!leaves_week(&keeping, "2026-11-02").unwrap());
}

#[test]
fn replacing_drops_a_piece_split_off_at_another_weeks_start() {
    let monday = with(school(), json!({"days": [0, 1]}));
    let piece = json!({"id": "school@20261111", "title": "School", "kind": "locked",
                       "category": "class", "start": "10:00", "duration_min": 405, "days": [2, 3, 4]});
    let new = with(school(), json!({"duration_min": 360}));
    assert_eq!(
        pieces_after_replace(&[monday, piece], Some(&new)),
        vec![Some(new), None]
    );
}

#[test]
fn the_question_names_the_edited_weeks_by_their_dates() {
    assert_eq!(edited_weeks_line(&[], &["School".into()]).unwrap(), None);
    assert_eq!(
        edited_weeks_line(&["2026-11-16".into()], &["School".into()]).unwrap(),
        Some("The week of 16 November has its own School times.".to_string())
    );
    assert_eq!(
        edited_weeks_line(
            &["2026-11-23".into(), "2026-11-16".into()],
            &["School".into()]
        )
        .unwrap(),
        Some("The weeks of 16 and 23 November have their own School times.".to_string())
    );
    assert_eq!(
        edited_weeks_line(
            &["2026-11-16".into(), "2026-12-07".into()],
            &["School".into(), "Soccer".into()]
        )
        .unwrap(),
        Some(
            "The weeks of 16 November and 7 December have their own School and Soccer times."
                .to_string()
        )
    );
}
