//! Tests for Running late, missed-commitment recovery, Allow splitting and Spread previews
//! (FlexWeek 2.0.0, P4 group 5B). Expected values come from the spec, the rules and the named
//! desktop parity tests, never from recording code output.

use flexweek_app::session::plan_previews::{
    AllowSplittingInput, LateAcceptDecision, LateAcceptInput, LateAnswerInput, LateInput,
    LatePreparation, PreviousSource, RecoverAnswerInput, RecoverInput, RecoverPreparation,
    SpreadAnswerInput, SpreadPreview, SpreadSelectionInput, accept_late, late_answer, late_blocks,
    late_payload_from_base, late_summary, prepare_allow_splitting, prepare_late, recover_answer,
    recover_payload_from_base, recover_request, spread_answer, spread_key, spread_ready_sentence,
    spread_selection,
};
use serde_json::{Value, json};

const WEEK: &str = "2026-09-21";

fn locked(id: &str, title: &str, days: Vec<i64>, start: &str, duration_min: i64) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "locked",
        "duration_min": duration_min,
        "days": days,
        "start": start,
        "category": "class",
        "priority": 1,
        "energy": "medium",
        "completed": false,
        "missed_days": [],
    })
}

fn homework_session(
    id: &str,
    assignment_id: &str,
    title: &str,
    days: Vec<i64>,
    start: Option<&str>,
    duration_min: i64,
) -> Value {
    json!({
        "id": id,
        "title": title,
        "kind": "flexible",
        "duration_min": duration_min,
        "days": days,
        "start": start,
        "category": "assignments",
        "assignment_id": assignment_id,
        "priority": 3,
        "energy": "medium",
        "completed": false,
        "missed_days": [],
    })
}

fn project_assignment() -> Value {
    json!({
        "id": "project",
        "title": "Project",
        "due": "2026-09-27T23:59",
        "estimate_min": 180,
        "category": "assignments",
        "priority": 3,
        "energy": "medium",
        "course": "History",
        "spotify_url": null,
        "focus_minutes": 0,
        "completed": false,
        "revision": 1,
    })
}

#[test]
fn spread_ready_sentence_uses_student_duration_and_date() {
    let text = spread_ready_sentence("Project", 180, "2026-09-27T23:59", WEEK).unwrap();
    assert_eq!(text, "Project: 3 h ready to add before Sun 27 Sep.");

    let mixed = spread_ready_sentence("Lab", 75, "2027-01-05T23:59", WEEK).unwrap();
    assert_eq!(mixed, "Lab: 1 h 15 min ready to add before Tue 5 Jan 2027.");
}

#[test]
fn late_summary_uses_singular_and_plural_words() {
    assert_eq!(late_summary(0), "Nothing needs to move.");
    assert_eq!(late_summary(1), "1 task moves");
    assert_eq!(late_summary(3), "3 tasks move");
}

#[test]
fn late_blocks_keeps_waiting_homework_out_of_running_late() {
    let timed = homework_session("essay-1", "essay", "Essay", vec![0], Some("16:00"), 60);
    let waiting = homework_session("essay-2", "essay", "Essay", vec![0], None, 60);
    let gym = locked("gym", "Gym", vec![0], "18:00", 60);
    let unlinked_waiting = json!({
        "id": "misc",
        "title": "Misc",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0],
        "start": null,
    });
    let kept = late_blocks(&[timed, waiting, gym, unlinked_waiting]);
    let ids: Vec<&str> = kept.iter().filter_map(|b| b["id"].as_str()).collect();
    assert_eq!(ids, ["essay-1", "gym", "misc"]);
}

#[test]
fn allow_splitting_computes_session_length_and_clamped_from_date() {
    // 180 min lab due 9 days out on Monday 2026-11-02: 60-min sessions starting today.
    let lab = json!({
        "id": "lab",
        "title": "Lab",
        "estimate_min": 180,
        "focus_minutes": 0,
        "due": "2026-11-11T23:59",
        "completed": false,
        "revision": 1,
    });
    let plan = prepare_allow_splitting(AllowSplittingInput {
        assignment: Some(&lab),
        done_min: 0,
        week_start: "2026-11-02",
        today_iso: "2026-11-02",
        selected_day: Some("2026-11-02"),
    })
    .unwrap()
    .expect("open homework should split");
    assert_eq!(plan.assignment["spread"], "spread");
    assert_eq!(plan.session_min, 60);
    assert_eq!(plan.from_date, "2026-11-02");

    // Done time is max(focus_minutes, done_min); non-grid remainder rounds down to 15 min.
    let partially_done = json!({
        "id": "lab",
        "title": "Lab",
        "estimate_min": 180,
        "focus_minutes": 130,
        "due": "2026-11-11T23:59",
        "completed": false,
    });
    let plan = prepare_allow_splitting(AllowSplittingInput {
        assignment: Some(&partially_done),
        done_min: 60,
        week_start: "2026-11-02",
        today_iso: "2026-11-02",
        selected_day: Some("2026-11-05"),
    })
    .unwrap()
    .unwrap();
    // 180 - max(130, 60) = 50 -> 50 - (50 % 15) = 45.
    assert_eq!(plan.session_min, 45);
    assert_eq!(plan.from_date, "2026-11-05");

    // Small remaining clamps up to 15; overdue clamps from_date to due date.
    let almost_done = json!({
        "id": "lab",
        "title": "Lab",
        "estimate_min": 60,
        "focus_minutes": 55,
        "due": "2026-11-01T23:59",
        "completed": false,
    });
    let plan = prepare_allow_splitting(AllowSplittingInput {
        assignment: Some(&almost_done),
        done_min: 0,
        week_start: "2026-11-02",
        today_iso: "2026-11-04",
        selected_day: None,
    })
    .unwrap()
    .unwrap();
    assert_eq!(plan.session_min, 15);
    assert_eq!(plan.from_date, "2026-11-01");
}

#[test]
fn allow_splitting_ignores_missing_or_completed_homework() {
    assert_eq!(
        prepare_allow_splitting(AllowSplittingInput {
            assignment: None,
            done_min: 0,
            week_start: WEEK,
            today_iso: WEEK,
            selected_day: None,
        })
        .unwrap(),
        None
    );
    let done = json!({"id": "a", "title": "Done", "completed": true, "estimate_min": 60});
    assert_eq!(
        prepare_allow_splitting(AllowSplittingInput {
            assignment: Some(&done),
            done_min: 0,
            week_start: WEEK,
            today_iso: WEEK,
            selected_day: None,
        })
        .unwrap(),
        None
    );
}

#[test]
fn recover_request_guards_and_chooses_previous_source() {
    let school = locked("school", "School", vec![0, 1, 2, 3, 4], "08:00", 420);
    let essay_placed = homework_session("essay-1", "essay", "Essay", vec![0], Some("16:00"), 60);
    let essay_waiting = homework_session("essay-2", "essay", "Essay", vec![0, 1], None, 60);

    // Unknown block, flexible block, or non-member day are ignored.
    assert_eq!(
        recover_request(RecoverInput {
            week_start: WEEK,
            blocks: std::slice::from_ref(&school),
            trace: None,
            block_id: "missing",
            day: 0,
        })
        .unwrap(),
        RecoverPreparation::Ignore
    );
    assert_eq!(
        recover_request(RecoverInput {
            week_start: WEEK,
            blocks: std::slice::from_ref(&essay_placed),
            trace: None,
            block_id: "essay-1",
            day: 0,
        })
        .unwrap(),
        RecoverPreparation::Ignore
    );
    assert_eq!(
        recover_request(RecoverInput {
            week_start: WEEK,
            blocks: std::slice::from_ref(&school),
            trace: None,
            block_id: "school",
            day: 6,
        })
        .unwrap(),
        RecoverPreparation::Ignore
    );

    // Already missed day only saves.
    let mut missed_school = school.clone();
    missed_school["missed_days"] = json!([0]);
    assert_eq!(
        recover_request(RecoverInput {
            week_start: WEEK,
            blocks: &[missed_school],
            trace: None,
            block_id: "school",
            day: 0,
        })
        .unwrap(),
        RecoverPreparation::SaveOnly
    );

    // 1. Non-empty trace.placed -> Trace source.
    let trace = json!({"placed": [essay_placed.clone()]});
    let from_trace = recover_request(RecoverInput {
        week_start: WEEK,
        blocks: &[school.clone(), essay_placed.clone()],
        trace: Some(&trace),
        block_id: "school",
        day: 0,
    })
    .unwrap();
    match from_trace {
        RecoverPreparation::Ready {
            status,
            previous_source,
            payload,
        } => {
            assert_eq!(status, "Replanning after the miss…");
            assert_eq!(previous_source, PreviousSource::Trace);
            assert_eq!(payload["recover"]["missed_block_id"], "school");
            assert_eq!(payload["recover"]["missed_day"], 0);
            assert_eq!(
                payload["recover"]["previous_placed"]
                    .as_array()
                    .unwrap()
                    .len(),
                1
            );
            assert_eq!(payload["recover"]["previous_placed"][0]["id"], "essay-1");
        }
        other => panic!("expected Ready from trace, got {other:?}"),
    }

    // 2. No trace, but a planned flexible block exists -> Scheduled source.
    let from_scheduled = recover_request(RecoverInput {
        week_start: WEEK,
        blocks: &[school.clone(), essay_placed.clone(), essay_waiting.clone()],
        trace: None,
        block_id: "school",
        day: 0,
    })
    .unwrap();
    match from_scheduled {
        RecoverPreparation::Ready {
            previous_source,
            payload,
            ..
        } => {
            assert_eq!(previous_source, PreviousSource::Scheduled);
            let prev_ids: Vec<&str> = payload["recover"]["previous_placed"]
                .as_array()
                .unwrap()
                .iter()
                .filter_map(|b| b["id"].as_str())
                .collect();
            assert_eq!(prev_ids, ["school", "essay-1"]);
        }
        other => panic!("expected Ready from scheduled, got {other:?}"),
    }

    // 3. No trace and no planned flexible block -> NeedsBase, then recover_payload_from_base.
    let needs_base = recover_request(RecoverInput {
        week_start: WEEK,
        blocks: &[school.clone(), essay_waiting.clone()],
        trace: None,
        block_id: "school",
        day: 0,
    })
    .unwrap();
    match needs_base {
        RecoverPreparation::NeedsBase {
            status,
            previous_source,
            base_payload,
        } => {
            assert_eq!(status, "Replanning after the miss…");
            assert_eq!(previous_source, PreviousSource::BaseSolve);
            assert_eq!(base_payload["week_start"], WEEK);
            assert_eq!(base_payload["blocks"].as_array().unwrap().len(), 2);
        }
        other => panic!("expected NeedsBase, got {other:?}"),
    }

    let second = recover_payload_from_base(
        WEEK,
        &[school, essay_waiting],
        "school",
        0,
        &json!({"placed": [essay_placed]}),
    )
    .unwrap();
    assert_eq!(second["recover"]["missed_block_id"], "school");
    assert_eq!(second["recover"]["missed_day"], 0);
    assert_eq!(second["recover"]["previous_placed"][0]["id"], "essay-1");
}

#[test]
fn recover_answer_records_sorted_missed_day_and_keeps_series_days() {
    let mut school = locked("school", "School", vec![0, 1, 2, 3, 4], "08:00", 420);
    school["missed_days"] = json!([2]);
    let essay = homework_session("essay-1", "essay", "Essay", vec![0], Some("16:00"), 60);
    let trace = json!({
        "placed": [
            {"id": "essay-1", "days": [0], "start": "10:00", "duration_min": 60}
        ],
        "unplaced": [],
    });
    let applied = recover_answer(RecoverAnswerInput {
        week_start: WEEK,
        blocks: &[school, essay],
        assignments: &json!({}),
        block_id: "school",
        day: 0,
        trace: &trace,
    })
    .unwrap()
    .expect("target exists");
    assert_eq!(applied.label, "the replan");
    let updated_school = applied.blocks.iter().find(|b| b["id"] == "school").unwrap();
    assert_eq!(updated_school["days"], json!([0, 1, 2, 3, 4]));
    assert_eq!(updated_school["missed_days"], json!([0, 2]));
    let updated_essay = applied
        .blocks
        .iter()
        .find(|b| b["id"] == "essay-1")
        .unwrap();
    assert_eq!(updated_essay["start"], "10:00");

    // Missing target returns None.
    assert_eq!(
        recover_answer(RecoverAnswerInput {
            week_start: WEEK,
            blocks: &[],
            assignments: &json!({}),
            block_id: "school",
            day: 0,
            trace: &trace,
        })
        .unwrap(),
        None
    );
}

#[test]
fn prepare_late_enforces_refusals_and_excludes_waiting_homework() {
    let timed = homework_session("essay-1", "essay", "Essay", vec![3], Some("18:45"), 60);
    let waiting = homework_session("essay-2", "essay", "Essay", vec![3, 4], None, 60);
    let blocks = [timed.clone(), waiting];

    // Wrong week refused first.
    assert_eq!(
        prepare_late(LateInput {
            week_start: "2026-09-28",
            today_iso: "2026-09-24",
            now_hour: 19,
            now_minute: 0,
            minutes: 30,
            dirty: false,
            conflict: false,
            blocks: &blocks,
            trace: None,
        })
        .unwrap(),
        LatePreparation::Refused("Open this week before using Running late.".into())
    );

    // Conflict outranks dirty.
    assert_eq!(
        prepare_late(LateInput {
            week_start: WEEK,
            today_iso: "2026-09-24",
            now_hour: 19,
            now_minute: 0,
            minutes: 30,
            dirty: true,
            conflict: true,
            blocks: &blocks,
            trace: None,
        })
        .unwrap(),
        LatePreparation::Refused(
            "This week changed in another window. Choose More > Reload this week, then try again."
                .into()
        )
    );

    // Dirty blocks Running late.
    assert_eq!(
        prepare_late(LateInput {
            week_start: WEEK,
            today_iso: "2026-09-24",
            now_hour: 19,
            now_minute: 0,
            minutes: 30,
            dirty: true,
            conflict: false,
            blocks: &blocks,
            trace: None,
        })
        .unwrap(),
        LatePreparation::Refused(
            "Saving your last change… Running late will work in a moment.".into()
        )
    );

    // Invalid delay minutes refused.
    assert_eq!(
        prepare_late(LateInput {
            week_start: WEEK,
            today_iso: "2026-09-24",
            now_hour: 19,
            now_minute: 0,
            minutes: 45,
            dirty: false,
            conflict: false,
            blocks: &blocks,
            trace: None,
        })
        .unwrap(),
        LatePreparation::Refused("Choose 15, 30 or 60 minutes.".into())
    );

    // Valid delay: snaps 14:07 down to 14:00, excludes waiting homework from payload.blocks,
    // and sets now_floor = [day, 840].
    let ready = prepare_late(LateInput {
        week_start: WEEK,
        today_iso: "2026-09-24",
        now_hour: 14,
        now_minute: 7,
        minutes: 30,
        dirty: false,
        conflict: false,
        blocks: &blocks,
        trace: None,
    })
    .unwrap();
    match ready {
        LatePreparation::Ready {
            day,
            from_start,
            minutes,
            status,
            previous_source,
            payload,
        } => {
            assert_eq!(day, 3);
            assert_eq!(from_start, "14:00");
            assert_eq!(minutes, 30);
            assert_eq!(status, "Replanning…");
            assert_eq!(previous_source, PreviousSource::Scheduled);
            let sent_ids: Vec<&str> = payload["blocks"]
                .as_array()
                .unwrap()
                .iter()
                .filter_map(|b| b["id"].as_str())
                .collect();
            assert_eq!(sent_ids, ["essay-1"]);
            assert_eq!(payload["running_late"]["day"], 3);
            assert_eq!(payload["running_late"]["minutes"], 30);
            assert_eq!(payload["running_late"]["from_start"], "14:00");
            assert_eq!(payload["running_late"]["now_floor"], json!([3, 14 * 60]));
        }
        other => panic!("expected Ready, got {other:?}"),
    }

    // NeedsBase also excludes waiting homework and late_payload_from_base keeps it out.
    let only_waiting = [homework_session(
        "essay-2",
        "essay",
        "Essay",
        vec![3],
        None,
        60,
    )];
    let needs_base = prepare_late(LateInput {
        week_start: WEEK,
        today_iso: "2026-09-24",
        now_hour: 14,
        now_minute: 7,
        minutes: 15,
        dirty: false,
        conflict: false,
        blocks: &only_waiting,
        trace: None,
    })
    .unwrap();
    match needs_base {
        LatePreparation::NeedsBase {
            previous_source,
            base_payload,
            ..
        } => {
            assert_eq!(previous_source, PreviousSource::BaseSolve);
            assert_eq!(base_payload["blocks"], json!([]));
        }
        other => panic!("expected NeedsBase, got {other:?}"),
    }

    let from_base = late_payload_from_base(
        WEEK,
        &only_waiting,
        3,
        "14:00",
        15,
        &json!({"placed": [timed]}),
    )
    .unwrap();
    assert_eq!(from_base["blocks"], json!([]));
    assert_eq!(from_base["running_late"]["now_floor"], json!([3, 840]));
    assert_eq!(
        from_base["running_late"]["previous_placed"][0]["id"],
        "essay-1"
    );
}

#[test]
fn late_answer_and_accept_late_preserve_operation_id_and_check_guards() {
    let essay = homework_session("essay-1", "essay", "Essay", vec![3], Some("18:45"), 60);
    let mut school = locked("school", "School", vec![0, 1, 2, 3, 4], "08:00", 420);
    school["missed_days"] = json!([0]);
    let trace = json!({
        "placed": [
            {"id": "essay-1", "days": [3], "start": "19:15", "duration_min": 60}
        ],
        "unplaced": [],
        "moves": [{"block_id": "essay-1", "from_start": "18:45", "to_start": "19:15"}],
    });
    let op_id = "11111111-2222-3333-4444-555555555555";
    let answered = late_answer(LateAnswerInput {
        week_start: WEEK,
        day: 3,
        from_start: "19:00",
        minutes: 30,
        operation_id: op_id,
        trace: &trace,
    })
    .unwrap();
    assert_eq!(answered.summary, "1 task moves");
    assert_eq!(answered.preview["operation_id"], op_id);
    assert_eq!(answered.preview["week_start"], WEEK);
    assert_eq!(answered.preview["stale"], false);
    assert_eq!(answered.preview["block"]["title"], "Running late");
    assert_eq!(answered.preview["block"]["kind"], "locked");
    assert_eq!(answered.preview["block"]["start"], "19:00");
    assert_eq!(answered.preview["block"]["duration_min"], 30);
    assert_eq!(answered.preview["block"]["days"], json!([3]));
    assert_eq!(
        answered.preview["block"]["id"],
        "b-late-111111112222333344445555"
    );

    // Stale or wrong week preview is ignored.
    let mut stale = answered.preview.clone();
    stale["stale"] = json!(true);
    assert_eq!(
        accept_late(LateAcceptInput {
            preview: Some(&stale),
            week_start: WEEK,
            blocks: &[school.clone(), essay.clone()],
            assignments: &json!({}),
        })
        .unwrap(),
        LateAcceptDecision::Ignore
    );
    assert_eq!(
        accept_late(LateAcceptInput {
            preview: Some(&answered.preview),
            week_start: "2026-09-28",
            blocks: &[school.clone(), essay.clone()],
            assignments: &json!({}),
        })
        .unwrap(),
        LateAcceptDecision::Ignore
    );

    // 100 blocks refused on accept.
    let full: Vec<Value> = (0..100)
        .map(|i| locked(&format!("b-{i}"), "Item", vec![0], "08:00", 15))
        .collect();
    assert_eq!(
        accept_late(LateAcceptInput {
            preview: Some(&answered.preview),
            week_start: WEEK,
            blocks: &full,
            assignments: &json!({}),
        })
        .unwrap(),
        LateAcceptDecision::Refused(
            "This week already has 100 blocks. Remove one before recording a late start.".into()
        )
    );

    // Accepting applies the locked late block and new placement while preserving school's days and op_id.
    let accepted = accept_late(LateAcceptInput {
        preview: Some(&answered.preview),
        week_start: WEEK,
        blocks: &[school, essay],
        assignments: &json!({}),
    })
    .unwrap();
    match accepted {
        LateAcceptDecision::Accept {
            blocks,
            trace: out_trace,
            operation_id,
            label,
        } => {
            assert_eq!(operation_id, op_id);
            assert_eq!(label, "running late");
            assert_eq!(out_trace, trace);
            assert_eq!(blocks.len(), 3);
            let moved_essay = blocks.iter().find(|b| b["id"] == "essay-1").unwrap();
            assert_eq!(moved_essay["start"], "19:15");
            let kept_school = blocks.iter().find(|b| b["id"] == "school").unwrap();
            assert_eq!(kept_school["days"], json!([0, 1, 2, 3, 4]));
            let late_block = blocks
                .iter()
                .find(|b| b["title"] == "Running late")
                .unwrap();
            assert_eq!(late_block["duration_min"], 30);
        }
        other => panic!("expected Accept, got {other:?}"),
    }
}

#[test]
fn spread_answer_keeps_assignment_identity_and_reports_leftovers() {
    let project = project_assignment();

    // Empty with no leftover.
    assert_eq!(
        spread_answer(SpreadAnswerInput {
            assignment_id: "project",
            assignment: &project,
            data: &json!({"sessions": [], "remaining_min": 0}),
            from_date: WEEK,
            session_min: 60,
            today_iso: WEEK,
            id_prefix: "tok",
        })
        .unwrap(),
        SpreadPreview::Empty {
            message: "All of this homework is already focused or planned.".into()
        }
    );

    // Empty with sub-grid leftover.
    assert_eq!(
        spread_answer(SpreadAnswerInput {
            assignment_id: "project",
            assignment: &project,
            data: &json!({"sessions": [], "remaining_min": 10}),
            from_date: WEEK,
            session_min: 60,
            today_iso: WEEK,
            id_prefix: "tok",
        })
        .unwrap(),
        SpreadPreview::Empty {
            message: "10 min remains, but it doesn't fit the 15-minute planning grid.".into()
        }
    );

    // Three 60-minute sessions with 0 leftover.
    let ready = spread_answer(SpreadAnswerInput {
        assignment_id: "project",
        assignment: &project,
        data: &json!({
            "sessions": [
                {"week_start": WEEK, "days": [0], "duration_min": 60},
                {"week_start": WEEK, "days": [2], "duration_min": 60},
                {"week_start": WEEK, "days": [4], "duration_min": 60},
            ],
            "remaining_min": 0,
        }),
        from_date: WEEK,
        session_min: 60,
        today_iso: WEEK,
        id_prefix: "abc",
    })
    .unwrap();
    match ready {
        SpreadPreview::Ready { preview, summary } => {
            assert_eq!(summary, "Project: 3 h ready to add before Sun 27 Sep.");
            assert_eq!(preview["summary"], summary);
            assert_eq!(preview["assignment_id"], "project");
            assert_eq!(preview["from_date"], WEEK);
            assert_eq!(preview["session_min"], 60);
            let rows = preview["rows"].as_array().unwrap();
            assert_eq!(rows.len(), 3);
            assert!(
                rows.iter()
                    .all(|r| r["block"]["assignment_id"] == "project")
            );
            assert_eq!(rows[0]["group_id"], "spread-abc-0");
            assert_eq!(rows[1]["group_id"], "spread-abc-1");
            assert_eq!(rows[2]["group_id"], "spread-abc-2");
            assert!(
                rows.iter()
                    .all(|r| r["checked"] == true && r["fixed"] == false)
            );
        }
        other => panic!("expected Ready, got {other:?}"),
    }

    // Leftover minutes appended to ready summary.
    let with_leftover = spread_answer(SpreadAnswerInput {
        assignment_id: "project",
        assignment: &project,
        data: &json!({
            "sessions": [{"week_start": WEEK, "days": [0], "duration_min": 60}],
            "remaining_min": 10,
        }),
        from_date: WEEK,
        session_min: 60,
        today_iso: WEEK,
        id_prefix: "abc",
    })
    .unwrap();
    match with_leftover {
        SpreadPreview::Ready { summary, .. } => {
            assert_eq!(
                summary,
                "Project: 1 h ready to add before Sun 27 Sep. 10 min can't fit the 15-minute grid and has not been dropped from the homework total."
            );
        }
        other => panic!("expected Ready, got {other:?}"),
    }
}

#[test]
fn spread_selection_maps_stored_mondays_into_shown_wednesday_week() {
    // Open week starts Wednesday 2026-11-04 (first_weekday = 2) through Tuesday 2026-11-10.
    // Stored weeks are Monday 2026-11-02 (days 2..=6 fall in the shown week) and Monday 2026-11-09
    // (days 0..=1 fall in the shown week; day 2 = Wed 2026-11-11 is in the NEXT shown week).
    let lab = json!({
        "id": "lab",
        "title": "Lab",
        "due": "2026-11-13T23:59",
        "estimate_min": 180,
        "category": "assignments",
    });
    let SpreadPreview::Ready { preview, .. } = spread_answer(SpreadAnswerInput {
        assignment_id: "lab",
        assignment: &lab,
        data: &json!({
            "sessions": [
                {"week_start": "2026-11-02", "days": [2], "duration_min": 60},
                {"week_start": "2026-11-09", "days": [0], "duration_min": 60},
                {"week_start": "2026-11-09", "days": [2], "duration_min": 60},
            ],
            "remaining_min": 0,
        }),
        from_date: "2026-11-04",
        session_min: 60,
        today_iso: "2026-11-04",
        id_prefix: "wed",
    })
    .unwrap() else {
        panic!("expected Ready preview");
    };

    let assignments = json!({ "lab": lab });
    assert_eq!(
        spread_key(7, "lab", "2026-11-04", 60),
        "spread|7|lab|2026-11-04|60"
    );

    // Allow splitting pending for "lab": both Wed Nov 4 and Mon Nov 9 belong to shown week 2026-11-04,
    // while Wed Nov 11 belongs to 2026-11-11 and is NOT in made_ids or plan_ids.
    let allow = spread_selection(SpreadSelectionInput {
        preview: &preview,
        assignments: &assignments,
        week_start: "2026-11-04",
        first_weekday: 2,
        operation_id: "op-wed-1",
        allow_split_pending: Some("lab"),
    })
    .unwrap();
    assert_eq!(allow.label, "spreading Lab");
    // Group index 0 is Nov 2 + Wed, index 1 is Nov 9 + Mon; index 2 (Nov 11) is the next shown week.
    assert_eq!(allow.made_ids, ["b-stage3-opwed1-0", "b-stage3-opwed1-1"]);
    assert_eq!(allow.plan_ids, ["b-stage3-opwed1-0", "b-stage3-opwed1-1"]);

    // Ordinary Spread by hand (no allow_split_pending): made_ids stays the same (so stale
    // _split_whole entries are cleared), while plan_ids is empty (no plan promise).
    let ordinary = spread_selection(SpreadSelectionInput {
        preview: &preview,
        assignments: &assignments,
        week_start: "2026-11-04",
        first_weekday: 2,
        operation_id: "op-wed-1",
        allow_split_pending: None,
    })
    .unwrap();
    assert_eq!(ordinary.made_ids, allow.made_ids);
    assert!(ordinary.plan_ids.is_empty());

    // Missing assignment falls back to "spreading homework".
    let fallback = spread_selection(SpreadSelectionInput {
        preview: &preview,
        assignments: &json!({}),
        week_start: "2026-11-04",
        first_weekday: 2,
        operation_id: "op-wed-1",
        allow_split_pending: None,
    })
    .unwrap();
    assert_eq!(fallback.label, "spreading homework");

    // Unchecked rows and rows of another homework do not enter made_ids.
    let mut mixed_preview = preview.clone();
    let rows = mixed_preview["rows"].as_array_mut().unwrap();
    rows[0]["checked"] = json!(false);
    rows[1]["block"]["assignment_id"] = json!("other");
    let mixed = spread_selection(SpreadSelectionInput {
        preview: &mixed_preview,
        assignments: &assignments,
        week_start: "2026-11-04",
        first_weekday: 2,
        operation_id: "op-wed-1",
        allow_split_pending: Some("lab"),
    })
    .unwrap();
    assert!(mixed.made_ids.is_empty());
    assert!(mixed.plan_ids.is_empty());
}

#[test]
fn prepare_late_and_recover_match_scheduled_blocks_when_trace_is_non_empty_with_empty_placed() {
    let school = locked("school", "School", vec![0, 1, 2, 3, 4], "08:00", 420);
    let essay = homework_session("essay-1", "essay", "Essay", vec![3], Some("18:45"), 60);
    let empty_placed_trace = json!({"placed": [], "unplaced": [{"id": "other"}]});

    // Matches controller.py: trace is truthy dict with empty placed, so scheduled_blocks() returns [].
    let rec = recover_request(RecoverInput {
        week_start: WEEK,
        blocks: &[school.clone(), essay.clone()],
        trace: Some(&empty_placed_trace),
        block_id: "school",
        day: 0,
    })
    .unwrap();
    match rec {
        RecoverPreparation::Ready {
            previous_source,
            payload,
            ..
        } => {
            assert_eq!(previous_source, PreviousSource::Scheduled);
            assert_eq!(payload["recover"]["previous_placed"], json!([]));
        }
        other => panic!("expected Ready, got {other:?}"),
    }

    // 100 blocks refused up front by prepare_late too; trace.placed picks Trace source.
    let full: Vec<Value> = (0..100)
        .map(|i| locked(&format!("b-{i}"), "Item", vec![0], "08:00", 15))
        .collect();
    assert_eq!(
        prepare_late(LateInput {
            week_start: WEEK,
            today_iso: "2026-09-24",
            now_hour: 14,
            now_minute: 0,
            minutes: 30,
            dirty: false,
            conflict: false,
            blocks: &full,
            trace: None,
        })
        .unwrap(),
        LatePreparation::Refused(
            "This week already has 100 blocks. Remove one before recording a late start.".into()
        )
    );

    let with_placed = json!({"placed": [essay.clone()]});
    let late = prepare_late(LateInput {
        week_start: WEEK,
        today_iso: "2026-09-24",
        now_hour: 14,
        now_minute: 0,
        minutes: 60,
        dirty: false,
        conflict: false,
        blocks: &[school, essay],
        trace: Some(&with_placed),
    })
    .unwrap();
    assert_eq!(late.to_json()["kind"], "ready");
    assert_eq!(late.to_json()["previous_source"], "trace");
    assert_eq!(
        late.to_json()["payload"]["running_late"]["previous_placed"][0]["id"],
        "essay-1"
    );
}

#[test]
fn wrong_shaped_inputs_are_refused_with_errors() {
    assert!(
        prepare_allow_splitting(AllowSplittingInput {
            assignment: Some(&json!("not an object")),
            done_min: 0,
            week_start: WEEK,
            today_iso: WEEK,
            selected_day: None,
        })
        .is_err()
    );
    assert!(
        late_answer(LateAnswerInput {
            week_start: WEEK,
            day: 3,
            from_start: "19:00",
            minutes: 30,
            operation_id: "op",
            trace: &json!({"moves": "not a list"}),
        })
        .is_err()
    );
    assert!(
        accept_late(LateAcceptInput {
            preview: Some(&json!({"week_start": WEEK, "stale": false})),
            week_start: WEEK,
            blocks: &[],
            assignments: &json!({}),
        })
        .is_err()
    );
    assert!(
        spread_answer(SpreadAnswerInput {
            assignment_id: "p",
            assignment: &project_assignment(),
            data: &json!({"sessions": "bad"}),
            from_date: WEEK,
            session_min: 60,
            today_iso: WEEK,
            id_prefix: "x",
        })
        .is_err()
    );
    assert!(
        spread_selection(SpreadSelectionInput {
            preview: &json!({"assignment_id": "p", "rows": "bad"}),
            assignments: &json!({}),
            week_start: WEEK,
            first_weekday: 0,
            operation_id: "op",
            allow_split_pending: None,
        })
        .is_err()
    );
}

fn late_input<'a>(today_iso: &'a str, now_hour: i64, blocks: &'a [Value]) -> LateInput<'a> {
    LateInput {
        week_start: WEEK,
        today_iso,
        now_hour,
        now_minute: 0,
        minutes: 30,
        dirty: false,
        conflict: false,
        blocks,
        trace: None,
    }
}

#[test]
fn running_late_needs_a_plain_date_for_today_and_a_real_clock() {
    // A timestamp, a week date and a date without dashes are not today's date: the refusal checks
    // would skip them and the solve would run for a week that is not open.
    for bad in [
        "2026-09-24T14:07:00",
        "2026-W39-4",
        "20260924",
        "2026-9-24",
        "",
    ] {
        assert!(prepare_late(late_input(bad, 14, &[])).is_err(), "{bad}");
    }
    assert!(prepare_late(late_input("2026-09-24", 14, &[])).is_ok());
    assert!(prepare_late(late_input("2026-09-24", 24, &[])).is_err());
    assert!(prepare_late(late_input("2026-09-24", -1, &[])).is_err());
    let mut late_minute = late_input("2026-09-24", 14, &[]);
    late_minute.now_minute = 60;
    assert!(prepare_late(late_minute).is_err());
    // A bad clock is an error even when a normal refusal (unsaved changes) would also apply.
    let mut dirty_hour = late_input("2026-09-24", 24, &[]);
    dirty_hour.dirty = true;
    assert!(prepare_late(dirty_hour).is_err());
    let mut dirty_minute = late_input("2026-09-24", 14, &[]);
    dirty_minute.dirty = true;
    dirty_minute.now_minute = 60;
    assert!(prepare_late(dirty_minute).is_err());
}

#[test]
fn running_late_snaps_the_clock_to_the_quarter_hour() {
    // 14:07 is inside the 14:00 slot; the hour times sixty plus the minute is the minute of the day.
    let late = prepare_late(LateInput {
        now_minute: 7,
        ..late_input("2026-09-24", 14, &[])
    })
    .unwrap();
    assert_eq!(late.to_json()["from_start"], "14:00");
    let later = prepare_late(LateInput {
        now_minute: 52,
        ..late_input("2026-09-24", 16, &[])
    })
    .unwrap();
    assert_eq!(later.to_json()["from_start"], "16:45");
}

#[test]
fn accepting_running_late_refuses_malformed_blocks_and_traces() {
    let essay = homework_session("essay-1", "essay", "Essay", vec![3], Some("18:45"), 60);
    let good_block = json!({
        "id": "b-late-1", "kind": "locked", "title": "Running late",
        "days": [3], "start": "19:00", "duration_min": 30,
    });
    let good_trace = json!({"placed": [], "unplaced": [], "moves": []});
    let accept = |block: Value, trace: Value| {
        accept_late(LateAcceptInput {
            preview: Some(&json!({
                "week_start": WEEK, "stale": false, "operation_id": "op",
                "block": block, "trace": trace,
            })),
            week_start: WEEK,
            blocks: std::slice::from_ref(&essay),
            assignments: &json!({}),
        })
    };
    assert!(accept(good_block.clone(), good_trace.clone()).is_ok());
    // An empty object is not a block.
    assert!(accept(json!({}), good_trace.clone()).is_err());
    // A block without days or with a start that is not a time is refused too.
    assert!(
        accept(
            json!({"id": "b", "kind": "locked", "title": "x", "start": "99:99"}),
            good_trace.clone()
        )
        .is_err()
    );
    // Placements must be lists of objects that name a block.
    assert!(accept(good_block.clone(), json!({"placed": {}})).is_err());
    assert!(accept(good_block.clone(), json!({"placed": [{}]})).is_err());
    assert!(accept(good_block.clone(), json!({"placed": ["essay-1"]})).is_err());
    assert!(accept(good_block.clone(), json!({"unplaced": {"id": "essay-1"}})).is_err());
    assert!(
        accept(
            good_block.clone(),
            json!({"placed": [{"id": "essay-1", "days": "3"}]})
        )
        .is_err()
    );
    assert!(
        accept(
            good_block.clone(),
            json!({"placed": [{"id": "essay-1", "start": 5}]})
        )
        .is_err()
    );
}

#[test]
fn accepting_running_late_refuses_a_late_block_or_placement_the_week_cannot_hold() {
    let essay = homework_session("essay-1", "essay", "Essay", vec![3], Some("18:45"), 60);
    let good_trace = json!({"placed": [], "unplaced": [], "moves": []});
    let accept = |block: Value, trace: Value| {
        accept_late(LateAcceptInput {
            preview: Some(&json!({
                "week_start": WEEK, "stale": false, "operation_id": "op",
                "block": block, "trace": trace,
            })),
            week_start: WEEK,
            blocks: std::slice::from_ref(&essay),
            assignments: &json!({}),
        })
    };
    let late = |patch: Value| {
        let mut block = json!({
            "id": "b-late-1", "kind": "locked", "title": "Running late",
            "days": [3], "start": "19:00", "duration_min": 30,
        });
        for (key, value) in patch.as_object().unwrap() {
            block[key] = value.clone();
        }
        block
    };
    assert!(accept(late(json!({})), good_trace.clone()).is_ok());
    // Only the clock is wrong; every other field of the block is valid.
    assert!(accept(late(json!({"start": "99:99"})), good_trace.clone()).is_err());
    assert!(accept(late(json!({"start": "24:00"})), good_trace.clone()).is_err());
    assert!(accept(late(json!({"start": null})), good_trace.clone()).is_err());
    // A late block is a locked block on real days.
    assert!(accept(late(json!({"kind": "flexible"})), good_trace.clone()).is_err());
    assert!(accept(late(json!({"days": []})), good_trace.clone()).is_err());
    assert!(accept(late(json!({"days": [7]})), good_trace.clone()).is_err());
    assert!(accept(late(json!({"days": [-1]})), good_trace.clone()).is_err());
    // Placements: only the clock is wrong, then days and length.
    let placed = |item: Value| json!({"placed": [item], "unplaced": [], "moves": []});
    let item = |patch: Value| {
        let mut placement = json!({
            "id": "essay-1", "days": [3], "start": "19:15", "duration_min": 60,
        });
        for (key, value) in patch.as_object().unwrap() {
            placement[key] = value.clone();
        }
        placement
    };
    assert!(accept(late(json!({})), placed(item(json!({})))).is_ok());
    assert!(accept(late(json!({})), placed(item(json!({"start": null})))).is_ok());
    assert!(accept(late(json!({})), placed(item(json!({"start": "99:99"})))).is_err());
    assert!(accept(late(json!({})), placed(item(json!({"start": "7pm"})))).is_err());
    assert!(accept(late(json!({})), placed(item(json!({"days": [7]})))).is_err());
    assert!(accept(late(json!({})), placed(item(json!({"days": [-1]})))).is_err());
    assert!(accept(late(json!({})), placed(item(json!({"duration_min": 0})))).is_err());
    assert!(accept(late(json!({})), placed(item(json!({"duration_min": -15})))).is_err());
    let unplaced = |item: Value| json!({"placed": [], "unplaced": [item], "moves": []});
    assert!(accept(late(json!({})), unplaced(item(json!({"start": "99:99"})))).is_err());
}

#[test]
fn allow_splitting_refuses_minute_counts_a_homework_cannot_hold() {
    let split = |estimate: Value, focus: Value| {
        prepare_allow_splitting(AllowSplittingInput {
            assignment: Some(&json!({
                "id": "p", "title": "P", "due": "2026-09-25T23:59",
                "estimate_min": estimate, "focus_minutes": focus,
            })),
            done_min: 0,
            week_start: WEEK,
            today_iso: WEEK,
            selected_day: None,
        })
    };
    // A day is 1440 minutes: 90 minutes of 120 done leaves 30, the session length.
    let found = split(json!(120), json!(90)).unwrap().unwrap();
    assert_eq!(found.session_min, 30);
    assert!(split(json!(i64::MIN), json!(60)).is_err());
    assert!(split(json!(-1), json!(0)).is_err());
    assert!(split(json!(1441), json!(0)).is_err());
    assert!(split(json!(60), json!(-5)).is_err());
    assert!(split(json!(60), json!(71401)).is_err());
    assert!(split(json!(1440), json!(71400)).is_ok());
}
