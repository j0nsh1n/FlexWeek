use flexweek_app::session::Status;
use flexweek_app::session::changes::{
    Acknowledgment, Refusal, SaveAnswer, SaveDraft, SaveFailure, SaveFailureKind, SavedWeek,
    StepPlace, TRAVEL_REFUSED, Travel, acknowledge_repeats, acknowledge_save, classify_failure,
    freeze_save, prepare_post, refuse_save, retry_needs_new_id, save_step,
};
use serde_json::{Map, Value, json};

const MONDAY: &str = "2026-11-02";
const WEDNESDAY: &str = "2026-11-04";
const NEXT_MONDAY: &str = "2026-11-09";
const OFF_SCREEN: &str = "2026-11-16";

fn empty_draft<'a>(assignments: &'a Map<String, Value>) -> SaveDraft<'a> {
    SaveDraft {
        week_start: MONDAY,
        blocks: &[],
        revision: &Value::Null,
        committed_blocks: &[],
        assignments,
        committed_assignments: assignments,
        dirty_assignments: &[],
        travel_weeks: &[],
        undo: false,
        stored_parts: &[],
        saved_repeats: &[],
        repeats: &[],
        queued_repeats: &[],
    }
}

#[test]
fn assignments_are_sorted_and_keep_the_revision_of_the_live_or_deleted_item() {
    let current = json!({
        "read": {
            "id": "read", "title": "Reading", "due": "2026-11-08", "estimate_min": 30,
            "revision": 4, "planned_min": 10, "session_weeks": [MONDAY]
        },
        "untouched": {"id": "untouched"}
    });
    let committed = json!({"z-delete": {"revision": 9}, "read": {"revision": 3}});
    let committed_blocks = [
        json!({"assignment_id": "z-delete"}),
        json!({"assignment_id": "z-delete"}),
    ];
    let draft = SaveDraft {
        revision: &json!(5),
        assignments: current.as_object().unwrap(),
        committed_assignments: committed.as_object().unwrap(),
        committed_blocks: &committed_blocks,
        dirty_assignments: &["z-delete".into(), "read".into(), "missing".into()],
        ..empty_draft(current.as_object().unwrap())
    };

    let body = freeze_save(&draft, "op-1", Some("Before changes")).unwrap();
    let expected = json!({
        "weeks": [{"week_start": MONDAY, "blocks": [], "revision": 6}],
        "assignments": [
            {"id": "missing", "assignment": null, "revision": 0},
            {"id": "read", "assignment": {
                "id": "read", "title": "Reading", "course": null, "category": null,
                "priority": 3, "energy": "medium", "spotify_url": null, "due": "2026-11-08",
                "estimate_min": 30, "focus_minutes": 0, "focus_sessions": 0, "completed": false,
                "completed_at": null
            }, "revision": 4},
            {"id": "z-delete", "assignment": null, "revision": 9}
        ],
        "operation_id": "op-1",
        "snapshot_label": "Before changes"
    });
    assert_eq!(body.to_string(), expected.to_string());
}

#[test]
fn a_shifted_week_keeps_both_stored_revisions_and_the_block_write_format() {
    let assignments = Map::new();
    let blocks = [
        json!({"id": "club", "title": "Club", "kind": "locked", "days": [5],
               "start": "16:00", "duration_min": 60, "category": "extra"}),
    ];
    let draft = SaveDraft {
        week_start: WEDNESDAY,
        revision: &json!([7, 2]),
        blocks: &blocks,
        committed_blocks: &[json!({"assignment_id": "gone"})],
        dirty_assignments: &["gone".into()],
        ..empty_draft(&assignments)
    };
    let body = freeze_save(&draft, "op-seam", Some("")).unwrap();
    let expected = json!({
        "weeks": [{
            "week_start": WEDNESDAY,
            "blocks": [{
                "id": "club", "title": "Club", "kind": "locked", "duration_min": 60,
                "days": [5], "priority": 3, "energy": "medium", "earliest": null,
                "latest": null, "start": "16:00", "course": null, "category": "extra"
            }],
            "revision": [7, 2]
        }],
        "assignments": [{"id": "gone", "assignment": null, "revision": 0}],
        "operation_id": "op-seam"
    });
    assert_eq!(body.to_string(), expected.to_string());
}

#[test]
fn travel_uses_the_selected_side_and_live_stored_revisions_where_held() {
    let assignments = Map::new();
    let step = [
        json!({"week_start": WEDNESDAY}),
        json!({
            "week_start": MONDAY, "revision": 2, "before": [],
            "after": [{"id": "club", "title": "Club", "kind": "locked", "duration_min": 30,
                       "days": [0], "start": "15:00"}]
        }),
        json!({"week_start": OFF_SCREEN, "revision": 12, "before": [], "after": []}),
    ];
    let stored = [json!({
        "week_start": MONDAY, "revision": 7, "blocks": [{"assignment_id": "gone"}]
    })];
    let mut draft = SaveDraft {
        week_start: WEDNESDAY,
        revision: &json!([7, 2]),
        dirty_assignments: &["gone".into()],
        stored_parts: &stored,
        travel_weeks: &step,
        undo: true,
        queued_repeats: &[json!({"id": "weekly-chess", "stop": true})],
        ..empty_draft(&assignments)
    };
    let undo = freeze_save(&draft, "op-undo", Some("Before undo")).unwrap();
    assert_eq!(
        undo,
        json!({
            "weeks": [
                {"week_start": WEDNESDAY, "blocks": [], "revision": [7, 2]},
                {"week_start": MONDAY, "blocks": [], "revision": 8},
                {"week_start": OFF_SCREEN, "blocks": [], "revision": 12}
            ],
            "assignments": [{"id": "gone", "assignment": null, "revision": 0}],
            "operation_id": "op-undo", "stay": true, "snapshot_label": "Before undo"
        })
    );
    draft.undo = false;
    let redo = freeze_save(&draft, "op-redo", None).unwrap();
    assert_eq!(redo["weeks"][1]["blocks"][0]["id"], "club");
    assert_eq!(redo["operation_id"], "op-redo");
}

#[test]
fn a_queued_repeat_takes_precedence_over_the_calculated_repeat_diff() {
    let assignments = Map::new();
    let saved = [json!({"id": "weekly-chess", "days": [0], "title": "Chess",
                       "duration_min": 60, "start": "16:00"})];
    let queued = [json!({"id": "weekly-club", "stop": true})];
    let mut draft = SaveDraft {
        revision: &json!(1),
        saved_repeats: &saved,
        queued_repeats: &queued,
        ..empty_draft(&assignments)
    };
    let with_queue = freeze_save(&draft, "op-1", None).unwrap();
    assert_eq!(with_queue["repeats"], json!(queued));

    draft.queued_repeats = &[];
    let with_diff = freeze_save(&draft, "op-2", None).unwrap();
    assert_eq!(
        with_diff["repeats"],
        json!([{"id": "weekly-chess", "scope": "from", "from_date": MONDAY,
                "set": {}, "add_days": [], "remove_days": [], "stop": true}])
    );
}

#[test]
fn a_retry_renews_its_id_only_when_the_body_changes() {
    let last = json!({
        "weeks": [{"week_start": MONDAY, "revision": 3, "blocks": []}],
        "assignments": [], "operation_id": "op-first"
    });
    let mut rebuilt = json!({
        "operation_id": "op-first", "assignments": [],
        "weeks": [{"blocks": [], "revision": 3, "week_start": MONDAY}]
    });
    assert!(!retry_needs_new_id(&last, &rebuilt));
    rebuilt["weeks"][0]["revision"] = json!(4);
    assert!(retry_needs_new_id(&last, &rebuilt));
}

fn post(weeks: &[&str], stay: bool, shown: &str, shifted: bool) -> (Value, Option<String>) {
    let writes: Vec<_> = weeks
        .iter()
        .map(|week| json!({"week_start": week, "revision": 0, "blocks": []}))
        .collect();
    let request = json!({"weeks": writes, "stay": stay, "operation_id": "op-1"});
    let written: Vec<_> = weeks.iter().map(|week| week.to_string()).collect();
    prepare_post(
        request.as_object().unwrap().clone(),
        &written,
        shown,
        shifted,
    )
    .unwrap()
}

#[test]
fn posting_keeps_stay_local_to_the_window() {
    let (payload, destination) = post(&[OFF_SCREEN], true, MONDAY, false);
    assert_eq!(
        payload.to_string(),
        r#"{"weeks":[{"week_start":"2026-11-16","revision":0,"blocks":[]}],"operation_id":"op-1"}"#
    );
    assert_eq!(destination, None);
}

#[test]
fn posting_only_navigates_when_the_open_week_is_untouched() {
    assert_eq!(post(&[OFF_SCREEN, MONDAY], false, MONDAY, false).1, None);
    for stored in [MONDAY, NEXT_MONDAY] {
        assert_eq!(post(&[OFF_SCREEN, stored], false, WEDNESDAY, true).1, None);
    }
    assert_eq!(
        post(&[OFF_SCREEN, NEXT_MONDAY], false, MONDAY, false)
            .1
            .as_deref(),
        Some(OFF_SCREEN)
    );
    assert_eq!(post(&[], false, MONDAY, false).1, None);
}

#[test]
fn a_lost_connection_says_changes_are_kept_and_offers_retry() {
    assert_eq!(
        classify_failure(0, "Ignored"),
        SaveFailure {
            kind: SaveFailureKind::Unreachable,
            words: "Not saved: FlexWeek can't be reached. Your changes are still here. Choose Retry save."
                .into(),
        }
    );
}

#[test]
fn a_conflict_is_distinct_from_a_server_refusal() {
    assert_eq!(
        classify_failure(409, "The week changed elsewhere."),
        SaveFailure {
            kind: SaveFailureKind::Conflict,
            words: "Not saved. The week changed elsewhere.".into()
        }
    );
    assert_eq!(
        classify_failure(503, "The planner is unavailable."),
        SaveFailure {
            kind: SaveFailureKind::Refused,
            words: "Not saved. The planner is unavailable.".into()
        }
    );
}

#[test]
fn a_save_records_one_step_from_the_saved_week_to_the_draft() {
    let assignments = Map::new();
    let piano = [json!({"id": "piano", "title": "Piano"})];
    let mut draft = SaveDraft {
        blocks: &piano,
        ..empty_draft(&assignments)
    };
    assert_eq!(
        save_step(&draft, "adding Piano").unwrap(),
        Some(json!({
            "label": "adding Piano",
            "weeks": [{"week_start": MONDAY, "before": [], "after": piano}],
            "assignments": [],
            "stale": false
        }))
    );
    draft.committed_blocks = &piano;
    assert_eq!(save_step(&draft, "adding Piano").unwrap(), None);
}

fn answer<'a>(
    data: &'a Value,
    assignments: &'a Map<String, Value>,
    committed: &'a Map<String, Value>,
) -> SaveAnswer<'a> {
    SaveAnswer {
        data,
        week_start: MONDAY,
        shifted_week: false,
        now: "2026-11-03T12:00",
        sent_repeats: false,
        assignments,
        committed_assignments: committed,
        stored_parts: &[],
        traveling: None,
        travel_step: None,
        pending_step: None,
        plan_step_id: None,
        join: false,
        held_words: None,
        sent_intents: None,
        waiting_intents: None,
    }
}

#[test]
fn a_save_answer_refuses_malformed_pending_history_lists() {
    let data = json!({});
    let held = Map::new();
    for (step, words) in [
        (json!({"weeks": false}), "step weeks must be a list"),
        (
            json!({"assignments": "bad"}),
            "step assignments must be a list",
        ),
    ] {
        let input = SaveAnswer {
            pending_step: Some(&step),
            ..answer(&data, &held, &held)
        };
        assert_eq!(acknowledge_save(&input).unwrap_err().message, words);
    }
}

#[test]
fn an_undo_answer_refuses_malformed_history_lists() {
    let data = json!({});
    let held = Map::new();
    for (step, words) in [
        (
            json!({"label": "moving Piano", "weeks": {}}),
            "step weeks must be a list",
        ),
        (
            json!({"label": "moving Piano", "assignments": 0}),
            "step assignments must be a list",
        ),
    ] {
        let input = SaveAnswer {
            traveling: Some(Travel::Undo),
            travel_step: Some(&step),
            ..answer(&data, &held, &held)
        };
        assert_eq!(acknowledge_save(&input).unwrap_err().message, words);
    }
}

fn session(id: &str, day: i64, start: &str) -> Value {
    json!({"id": id, "title": "Essay", "kind": "flexible", "assignment_id": "essay",
           "duration_min": 30, "days": [day], "start": start})
}

#[test]
fn a_save_that_moves_a_session_off_screen_shifts_the_held_counts_of_both_copies() {
    let moved = session("s1", 0, "16:00");
    let step = json!({
        "label": "moving Essay to another date",
        "weeks": [
            {"week_start": MONDAY, "before": [session("s1", 1, "16:00")], "after": []},
            {"week_start": NEXT_MONDAY, "before": [], "after": [moved]}
        ],
        "assignments": [], "stale": false
    });
    let data = json!({"weeks": [
        {"week_start": MONDAY, "revision": 4, "blocks": []},
        {"week_start": NEXT_MONDAY, "revision": 2, "blocks": [moved]}
    ], "assignments": []});
    let live = json!({"essay": {"id": "essay", "planned_min": 60, "done_min": 15,
                                "session_weeks": [MONDAY]},
                      "art": {"id": "art", "session_weeks": [OFF_SCREEN]}});
    let saved = json!({"essay": {"id": "essay", "planned_min": "60", "done_min": 15}});
    let (live, saved) = (live.as_object().unwrap(), saved.as_object().unwrap());
    let input = SaveAnswer {
        pending_step: Some(&step),
        plan_step_id: Some("plan-1"),
        ..answer(&data, live, saved)
    };
    let acknowledged = acknowledge_save(&input).unwrap();
    // The open week's own change is in the counts already; the next week gained 30 planned minutes, and
    // no session there is done.
    assert_eq!(
        acknowledged,
        Acknowledgment {
            session_weeks: json!({"essay": [NEXT_MONDAY], "art": [OFF_SCREEN]})
                .as_object()
                .unwrap()
                .clone(),
            live_counts: json!({"essay": {"planned_min": 90}})
                .as_object()
                .unwrap()
                .clone(),
            saved_counts: json!({"essay": {"planned_min": 90}})
                .as_object()
                .unwrap()
                .clone(),
            open_week: Some(SavedWeek {
                blocks: vec![],
                revision: json!(4),
                stored: vec![],
                repeats: None,
            }),
            homework: vec![],
            step: Some((
                StepPlace::Undo,
                json!({
                    "label": "moving Essay to another date",
                    "weeks": [
                        {"week_start": MONDAY, "before": [session("s1", 1, "16:00")],
                         "after": [], "revision": 4},
                        {"week_start": NEXT_MONDAY, "before": [], "after": [moved], "revision": 2}
                    ],
                    "assignments": [], "stale": false
                })
            )),
            clear_redo: true,
            planned: false,
            words: "Saved.".into(),
            waiting_intents: None,
        }
    );
}

#[test]
fn a_week_on_screen_from_another_day_counts_from_its_first_day() {
    // Wednesday's week is stored in two Mondays; a session moved into the week after them counts.
    let moved = session("s1", 2, "16:00");
    let step = json!({"label": "x", "weeks": [
        {"week_start": OFF_SCREEN, "before": [], "after": [moved]}
    ], "assignments": []});
    let data = json!({"weeks": [{"week_start": OFF_SCREEN, "revision": 1, "blocks": [moved]}]});
    let live = json!({"essay": {"id": "essay", "planned_min": 0}});
    let live = live.as_object().unwrap();
    let input = SaveAnswer {
        week_start: WEDNESDAY,
        shifted_week: true,
        pending_step: Some(&step),
        ..answer(&data, live, live)
    };
    let acknowledged = acknowledge_save(&input).unwrap();
    assert_eq!(
        acknowledged.live_counts,
        *json!({"essay": {"planned_min": 30}}).as_object().unwrap()
    );
    assert_eq!(acknowledged.open_week, None);
}

#[test]
fn a_saved_homework_keeps_its_held_counts_and_session_weeks_and_a_deleted_one_goes() {
    let data = json!({"assignments": [
        {"id": "essay", "revision": 7, "assignment": {"id": "essay", "title": "Essay v2"}},
        {"id": "gone", "revision": 3, "assignment": null},
        {"id": "new", "revision": 1, "assignment": {"id": "new"}}
    ]});
    let live = json!({
        "essay": {"id": "essay", "title": "Essay", "unplanned_min": 5, "planned_min": 40,
                  "done_min": 10, "session_weeks": [MONDAY]},
        "gone": {"id": "gone"}
    });
    let live = live.as_object().unwrap();
    let acknowledged = acknowledge_save(&answer(&data, live, live)).unwrap();
    assert_eq!(
        acknowledged.homework,
        vec![
            (
                "essay".into(),
                Some(json!({"id": "essay", "title": "Essay v2", "revision": 7,
                            "session_weeks": [MONDAY], "unplanned_min": 5, "planned_min": 40,
                            "done_min": 10}))
            ),
            ("gone".into(), None),
            (
                "new".into(),
                Some(json!({"id": "new", "revision": 1, "session_weeks": []}))
            ),
        ]
    );
    assert!(acknowledged.live_counts.is_empty());
    assert_eq!(acknowledged.step, None);
    assert!(!acknowledged.clear_redo);
}

#[test]
fn a_plan_step_is_reported_planned_only_when_the_save_holding_it_lands() {
    let data = json!({"weeks": [{"week_start": MONDAY, "revision": 2, "blocks": [],
                                 "repeats": [{"id": "weekly"}]}]});
    let held = Map::new();
    let plan =
        json!({"label": "planning the week", "id": "plan-1", "weeks": [], "assignments": []});
    let other = json!({"label": "adding Essay", "id": "add-1", "weeks": [], "assignments": []});
    let landed = SaveAnswer {
        pending_step: Some(&plan),
        plan_step_id: Some("plan-1"),
        held_words: Some(""),
        sent_repeats: true,
        ..answer(&data, &held, &held)
    };
    let acknowledged = acknowledge_save(&landed).unwrap();
    assert!(acknowledged.planned);
    // A Plan says Saved. quietly; its own notice carries the words and the Undo.
    assert_eq!(acknowledged.words, "Saved.");
    assert_eq!(acknowledged.step.unwrap().0, StepPlace::Undo);
    assert_eq!(
        acknowledged.open_week.unwrap().repeats,
        Some(vec![json!({"id": "weekly"})])
    );

    // Another step's save, or one with no Plan waiting, is no Plan's.
    for (step, plan_id) in [(&other, Some("plan-1")), (&plan, None)] {
        let input = SaveAnswer {
            pending_step: Some(step),
            plan_step_id: plan_id,
            held_words: Some(""),
            ..answer(&data, &held, &held)
        };
        let acknowledged = acknowledge_save(&input).unwrap();
        assert!(!acknowledged.planned);
        assert_eq!(acknowledged.words, "");
    }

    // Plan for me as I add it joins the add's step, so one Undo takes both back.
    let joined = SaveAnswer {
        pending_step: Some(&plan),
        plan_step_id: Some("plan-1"),
        join: true,
        ..answer(&data, &held, &held)
    };
    assert_eq!(
        acknowledge_save(&joined).unwrap().step.unwrap().0,
        StepPlace::JoinUndo
    );
}

#[test]
fn an_undo_answer_moves_the_step_to_redo_with_the_revisions_the_server_gave() {
    let step = json!({
        "label": "adding Piano",
        "weeks": [
            {"week_start": MONDAY, "before": [], "after": [{"id": "piano"}], "revision": 3},
            {"week_start": NEXT_MONDAY, "before": [session("s9", 0, "09:00")],
             "after": []}
        ],
        "assignments": [{"id": "essay", "before": {"id": "essay"}, "after": null, "basis": []}]
    });
    let data = json!({"weeks": [
        {"week_start": MONDAY, "revision": 5, "blocks": []},
        {"week_start": NEXT_MONDAY, "revision": 8, "blocks": [session("s9", 0, "09:00")]}
    ]});
    let live = json!({"essay": {"id": "essay", "planned_min": 0}});
    let live = live.as_object().unwrap();
    let plan = json!({"id": "plan-1"});
    let undo = SaveAnswer {
        traveling: Some(Travel::Undo),
        travel_step: Some(&step),
        pending_step: Some(&plan),
        plan_step_id: Some("plan-1"),
        ..answer(&data, live, live)
    };
    let acknowledged = acknowledge_save(&undo).unwrap();
    let (place, kept) = acknowledged.step.unwrap();
    assert_eq!(place, StepPlace::Redo);
    assert_eq!(kept["weeks"][0]["revision"], 5);
    assert_eq!(kept["weeks"][1]["revision"], 8);
    assert_eq!(acknowledged.words, "Undid adding Piano.");
    assert!(!acknowledged.planned && !acknowledged.clear_redo);
    // Homework Undo brings back from a delete has the numbers its step kept: no shift.
    assert!(acknowledged.live_counts.is_empty());

    let redo_data = json!({"weeks": [
        {"week_start": MONDAY, "revision": 6, "blocks": [{"id": "piano"}]},
        {"week_start": NEXT_MONDAY, "revision": 9, "blocks": []}
    ]});
    let held = json!({"essay": {"id": "essay", "planned_min": 30}});
    let held = held.as_object().unwrap();
    let redo = SaveAnswer {
        data: &redo_data,
        assignments: held,
        committed_assignments: held,
        traveling: Some(Travel::Redo),
        ..undo
    };
    let acknowledged = acknowledge_save(&redo).unwrap();
    assert_eq!(acknowledged.step.unwrap().0, StepPlace::Undo);
    assert_eq!(acknowledged.words, "Redid adding Piano.");
    // Redo takes the session back out of the next week. The essay is not brought back by this side, so
    // its count moves.
    assert_eq!(
        acknowledged.live_counts,
        *json!({"essay": {"planned_min": 0}}).as_object().unwrap()
    );
}

#[test]
fn repeat_intents_a_save_carried_are_acknowledged_and_later_choices_still_wait() {
    let chess = json!({"id": "weekly-chess", "stop": true});
    let chess_later = json!({"id": "weekly-chess", "scope": "from", "stop": false});
    let club = json!({"id": "weekly-club", "stop": true});
    let sent = [chess.clone()];
    assert_eq!(
        acknowledge_repeats(Some(&sent), Some(&[chess.clone(), club.clone()])).unwrap(),
        Some(vec![club.clone()])
    );
    assert_eq!(
        acknowledge_repeats(Some(&sent), Some(std::slice::from_ref(&chess_later))).unwrap(),
        Some(vec![chess_later])
    );
    assert_eq!(
        acknowledge_repeats(Some(&sent), Some(std::slice::from_ref(&chess))).unwrap(),
        None
    );
    assert_eq!(
        acknowledge_repeats(None, Some(std::slice::from_ref(&club))).unwrap(),
        Some(vec![club])
    );
    assert_eq!(acknowledge_repeats(Some(&[]), None).unwrap(), None);
}

#[test]
fn a_failed_undo_puts_the_saved_week_back_and_the_step_back_on_its_stack() {
    assert_eq!(
        refuse_save(0, "Ignored", Some(Travel::Undo), true),
        Refusal {
            failure: classify_failure(0, "Ignored"),
            conflict: false,
            roll_back: true,
            step_back: Some(Travel::Undo),
            reload_words: None,
        }
    );
    let refused = refuse_save(503, "Down.", Some(Travel::Redo), true);
    assert_eq!(
        (refused.roll_back, refused.step_back, refused.failure.kind),
        (true, Some(Travel::Redo), SaveFailureKind::Refused)
    );
    // With no step held there is nothing to put back.
    assert_eq!(
        refuse_save(503, "Down.", Some(Travel::Redo), false).step_back,
        None
    );
}

#[test]
fn a_refused_undo_reloads_the_saved_week_and_offers_undo_again() {
    assert_eq!(
        refuse_save(409, "Changed elsewhere.", Some(Travel::Undo), true),
        Refusal {
            failure: classify_failure(409, "Changed elsewhere."),
            conflict: true,
            roll_back: false,
            step_back: Some(Travel::Undo),
            reload_words: Some(TRAVEL_REFUSED),
        }
    );
    assert_eq!(
        TRAVEL_REFUSED,
        "Undo did not go through. Your week was reloaded as it's saved."
    );
    // An ordinary save keeps its batch and draft; a conflict waits for Reload.
    assert_eq!(
        refuse_save(409, "Changed elsewhere.", None, false),
        Refusal {
            failure: classify_failure(409, "Changed elsewhere."),
            conflict: true,
            roll_back: false,
            step_back: None,
            reload_words: None,
        }
    );
    let offline = refuse_save(0, "", None, false);
    assert!(!offline.roll_back && !offline.conflict && offline.step_back.is_none());
}

#[test]
fn a_late_answer_after_a_newer_save_gives_no_second_completion() {
    // A failed save is retried: the first request's late answer must not complete anything.
    let mut status = Status::default();
    let first = status.begin(false);
    let retry = status.begin(false);
    assert!(!status.idle(first));
    assert!(status.idle(retry));
    assert!(!status.idle(first));
}

#[test]
fn a_done_session_moved_off_screen_moves_its_done_minutes_with_it() {
    let mut moved = session("s1", 0, "16:00");
    moved["completed"] = json!(true);
    let mut was = session("s1", 1, "16:00");
    was["completed"] = json!(true);
    let step = json!({"label": "x", "weeks": [
        {"week_start": MONDAY, "before": [was], "after": []},
        {"week_start": NEXT_MONDAY, "before": [], "after": [moved]}
    ], "assignments": []});
    let data = json!({"weeks": [
        {"week_start": MONDAY, "revision": 4, "blocks": []},
        {"week_start": NEXT_MONDAY, "revision": 2, "blocks": [moved]}
    ]});
    let live = json!({"essay": {"id": "essay", "done_min": 15}});
    let live = live.as_object().unwrap();
    let input = SaveAnswer {
        pending_step: Some(&step),
        ..answer(&data, live, live)
    };
    let acknowledged = acknowledge_save(&input).unwrap();
    // The open week's own change is counted already; the 30 done minutes now in the next week are added.
    assert_eq!(acknowledged.live_counts["essay"]["done_min"], 45);
    assert_eq!(acknowledged.saved_counts["essay"]["done_min"], 45);
}

#[test]
fn a_week_on_screen_from_another_day_does_not_shift_counts_for_its_own_stored_weeks() {
    // Wednesday 2026-11-04's week is stored in the Mondays 2026-11-02 and 2026-11-09: a change in the
    // second one is the open week's own change, already in the counts.
    let moved = session("s1", 0, "16:00");
    let step = json!({"label": "x", "weeks": [
        {"week_start": NEXT_MONDAY, "before": [], "after": [moved]}
    ], "assignments": []});
    let data = json!({"weeks": [{"week_start": NEXT_MONDAY, "revision": 3, "blocks": [moved]}]});
    let live = json!({"essay": {"id": "essay", "planned_min": 0, "done_min": 0}});
    let live = live.as_object().unwrap();
    let input = SaveAnswer {
        week_start: WEDNESDAY,
        shifted_week: true,
        pending_step: Some(&step),
        ..answer(&data, live, live)
    };
    let acknowledged = acknowledge_save(&input).unwrap();
    assert!(
        acknowledged.live_counts.is_empty(),
        "{:?}",
        acknowledged.live_counts
    );
}
