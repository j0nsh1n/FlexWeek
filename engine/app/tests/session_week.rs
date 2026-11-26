use std::collections::HashSet;

use flexweek_app::session::week::{
    self, DraftFlags, FailedRead, History, LoadFinish, LoadReply, LoadRoute, LocalWeek, ReadWeek,
    RemoteChange, Row,
};
use flexweek_store::Revision;
use serde_json::{Value, json};

const OPEN: &str = "2026-11-01";
const NEXT: &str = "2026-11-08";
const CLEAN: DraftFlags = DraftFlags {
    dirty: false,
    dirty_assignments: false,
    pending_save: false,
};
const DIRTY: DraftFlags = DraftFlags {
    dirty: true,
    ..CLEAN
};
const HOMEWORK: DraftFlags = DraftFlags {
    dirty_assignments: true,
    ..CLEAN
};
const PENDING: DraftFlags = DraftFlags {
    pending_save: true,
    ..CLEAN
};

fn row(value: Value) -> Row {
    let Value::Object(row) = value else {
        panic!("a homework or block row is an object")
    };
    row
}

fn ids(values: &[&str]) -> HashSet<String> {
    values.iter().map(|value| (*value).to_owned()).collect()
}

#[test]
fn held_weeks_follow_parking_order_but_only_dirty_blocks_feed_local_views() {
    let parked = [
        ("2026-11-15", CLEAN),
        (NEXT, PENDING),
        (OPEN, DIRTY),
        ("2026-10-25", HOMEWORK),
    ];
    assert_eq!(week::first_held(&parked), Some(&NEXT));
    assert_eq!(week::first_held(&parked[..1]), None);
    assert_eq!(
        week::dirty_parked(&parked).copied().collect::<Vec<_>>(),
        [OPEN]
    );
    assert_eq!(week::local_week(OPEN, OPEN, false), LocalWeek::Open);
    assert_eq!(week::local_week(NEXT, OPEN, true), LocalWeek::Parked);
    assert_eq!(week::local_week(NEXT, OPEN, false), LocalWeek::Missing);
    assert_eq!(
        week::block_index(&["other".into(), "match".into(), "match".into()], "match"),
        Some(1)
    );
    assert_eq!(week::block_index(&["other".into()], "match"), None);
}

#[test]
fn selection_keeps_the_open_draft_or_restores_a_parked_start_as_it_was() {
    let parked = [(NEXT.to_owned(), HOMEWORK)];
    assert_eq!(
        week::select_week(OPEN, OPEN, 0, false, PENDING, &parked).unwrap(),
        LoadRoute::KeepOpen
    );
    assert_eq!(
        week::select_week(NEXT, OPEN, 0, false, DIRTY, &parked).unwrap(),
        LoadRoute::Restore {
            start: NEXT.into(),
            park_open: true,
            words: "This week.",
        }
    );
    assert_eq!(
        week::select_week(NEXT, OPEN, 0, false, CLEAN, &parked).unwrap(),
        LoadRoute::Restore {
            start: NEXT.into(),
            park_open: false,
            words: "This week.",
        }
    );
    assert_eq!(
        week::select_week("2026-11-10", OPEN, 6, false, DIRTY, &parked).unwrap(),
        LoadRoute::Restore {
            start: NEXT.into(),
            park_open: true,
            words: "This week.",
        }
    );
    assert_eq!(
        week::select_week("2026-11-10", OPEN, 0, false, CLEAN, &parked).unwrap(),
        LoadRoute::Fetch {
            start: "2026-11-09".into(),
            discard_parked: false,
        }
    );
}

#[test]
fn reload_discards_the_parked_copy_and_says_what_happened() {
    let parked = [(OPEN.to_owned(), DIRTY)];
    assert_eq!(
        week::select_week(OPEN, OPEN, 0, true, PENDING, &parked).unwrap(),
        LoadRoute::Fetch {
            start: OPEN.into(),
            discard_parked: true,
        }
    );
    assert_eq!(
        week::load_words(Some(week::reload_words())),
        "Reloaded this week."
    );
    assert_eq!(week::load_words(None), "This week.");
    assert_eq!(week::load_words(Some("Restored.")), "Restored.");
}

#[test]
fn a_remote_change_waits_or_marks_a_held_week_without_reloading_it() {
    assert_eq!(
        week::remote_change(false, true, DIRTY, "your phone"),
        RemoteChange::Ignore
    );
    assert_eq!(
        week::remote_change(true, true, DIRTY, "your phone"),
        RemoteChange::Wait
    );
    for flags in [DIRTY, HOMEWORK, PENDING] {
        assert_eq!(
            week::remote_change(true, false, flags, "your phone"),
            RemoteChange::Conflict
        );
    }
    assert_eq!(
        week::remote_change(true, false, CLEAN, "your phone"),
        RemoteChange::Reload("Updated from your phone.".into())
    );
}

#[test]
fn a_second_read_failure_does_not_commit_navigation() {
    let route = week::select_week(NEXT, OPEN, 6, false, DIRTY, &[]).unwrap();
    assert_eq!(
        route,
        LoadRoute::Fetch {
            start: NEXT.into(),
            discard_parked: false
        }
    );
    let failed = |read, selected_day| {
        week::finish_load(
            OPEN,
            LoadReply::Failed {
                read,
                selected_day,
                first_weekday: 6,
            },
        )
        .unwrap()
    };
    assert_eq!(
        failed(FailedRead::Assignments, "2026-11-10"),
        LoadFinish::Failed {
            clear_waiting_plan: true,
            refresh_selected_day: true,
        }
    );
    assert_eq!(
        failed(FailedRead::Week, "2026-11-10"),
        LoadFinish::Failed {
            clear_waiting_plan: false,
            refresh_selected_day: true,
        }
    );
    assert_eq!(
        failed(FailedRead::Assignments, "2026-11-02"),
        LoadFinish::Failed {
            clear_waiting_plan: true,
            refresh_selected_day: false,
        }
    );
}

fn read_week(start: &str, revision: Revision) -> ReadWeek {
    ReadWeek {
        start: start.into(),
        revision,
        blocks: vec![row(json!({"id": "school"}))],
        stored: vec![row(json!({"week_start": "2026-10-26", "revision": 2}))],
        repeats: vec![row(json!({"id": "weekly"}))],
    }
}

#[test]
fn both_reads_install_the_week_and_only_a_move_parks_the_draft() {
    let original_revision = Revision::Shown(2, 3);
    let assignments = || {
        vec![row(
            json!({"id": "essay", "title": "Essay", "done_min": 20}),
        )]
    };
    let installed = |start, revision, current| {
        week::finish_load(
            OPEN,
            LoadReply::Read {
                week: read_week(start, revision),
                assignments: assignments(),
                revision: original_revision,
                current,
            },
        )
        .unwrap()
    };
    for (start, revision, current, expected_park, expected_history) in [
        (NEXT, Revision::Shown(3, 4), DIRTY, true, History::Clear),
        (NEXT, Revision::Shown(3, 4), CLEAN, false, History::Clear),
        (
            OPEN,
            Revision::Shown(2, 4),
            DIRTY,
            false,
            History::MarkStale,
        ),
        (OPEN, original_revision, CLEAN, false, History::Keep),
    ] {
        assert_eq!(
            installed(start, revision, current),
            LoadFinish::Install {
                week: read_week(start, revision),
                assignments: row(
                    json!({"essay": {"id": "essay", "title": "Essay", "done_min": 20}})
                ),
                park_open: expected_park,
                history: expected_history,
            }
        );
    }
}

#[test]
fn a_write_through_a_stored_monday_rereads_a_clean_shifted_week() {
    for monday in ["2026-10-26", "2026-11-02"] {
        assert!(week::wrote_open_weeks(OPEN, CLEAN, &ids(&[monday])));
        assert!(!week::wrote_open_weeks(OPEN, HOMEWORK, &ids(&[monday])));
        assert!(!week::wrote_open_weeks(OPEN, CLEAN, &ids(&[monday, OPEN])));
        assert!(!week::wrote_open_weeks(monday, CLEAN, &ids(&[monday])));
    }
    assert!(!week::wrote_open_weeks(OPEN, CLEAN, &ids(&["2026-11-09"])));
    assert!(!week::wrote_open_weeks("invalid", CLEAN, &ids(&[OPEN])));
}

#[test]
fn refresh_keeps_dirty_edits_and_saved_fields_and_applies_server_counts() {
    let refresh = week::refresh_assignments(
        vec![
            row(json!({"id": "essay", "title": "Server title", "planned_min": 40, "done_min": 20})),
            row(json!({"id": "deleted", "title": "Still on server", "unplanned_min": 45})),
            row(json!({"id": "new", "title": "New homework", "revision": 1})),
            row(json!({"id": "clean", "title": "Updated homework", "revision": 4})),
        ],
        &ids(&["essay", "clean"]),
        &ids(&["essay", "deleted", "clean"]),
        &ids(&["essay", "deleted"]),
    )
    .unwrap();
    assert_eq!(
        refresh.saved_counts,
        row(json!({
            "essay": {"unplanned_min": null, "planned_min": 40, "done_min": 20},
            "deleted": {"unplanned_min": 45, "planned_min": null, "done_min": null},
            "clean": {"unplanned_min": null, "planned_min": null, "done_min": null},
        }))
    );
    assert_eq!(
        refresh.dirty_counts,
        row(json!({
            "essay": {"unplanned_min": null, "planned_min": 40, "done_min": 20},
        }))
    );
    assert_eq!(
        refresh.clean_rows,
        row(json!({
            "new": {"id": "new", "title": "New homework", "revision": 1},
            "clean": {"id": "clean", "title": "Updated homework", "revision": 4},
        }))
    );
}

#[test]
fn assignment_rows_without_text_ids_are_refused() {
    let invalid = || vec![row(json!({"id": 42}))];
    let result = week::finish_load(
        OPEN,
        LoadReply::Read {
            week: read_week(OPEN, Revision::Shown(2, 3)),
            assignments: invalid(),
            revision: Revision::Shown(2, 3),
            current: CLEAN,
        },
    );
    assert_eq!(result.unwrap_err().message, "assignment id must be text");
    let result = week::refresh_assignments(invalid(), &ids(&[]), &ids(&[]), &ids(&[]));
    assert_eq!(result.unwrap_err().message, "assignment id must be text");
}
