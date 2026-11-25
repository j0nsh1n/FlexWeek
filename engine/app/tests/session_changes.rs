use flexweek_app::session::changes::{
    SaveDraft, SaveFailure, SaveFailureKind, classify_failure, freeze_save, prepare_post,
    retry_needs_new_id,
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
