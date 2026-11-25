//! Rust twin of `desktop/tests/test_history.py`: undo snapshots for the native week.

use flexweek_engine::EngineError;
use flexweek_engine::desk::history::{self, HISTORY_LIMIT, capture_step};
use serde_json::{Value, json};
use std::cell::RefCell;

fn ids(names: &[&str]) -> Vec<String> {
    names.iter().map(|name| (*name).to_string()).collect()
}

fn push_step(stack: &mut Vec<Value>, step: Value) {
    let stack = RefCell::new(stack);
    history::push_step(
        step,
        |step| {
            stack.borrow_mut().push(step);
            Ok::<_, EngineError>(())
        },
        || Ok(stack.borrow().len()),
        || {
            stack.borrow_mut().remove(0);
            Ok(())
        },
    )
    .expect("a push");
}

fn mark_stale(steps: &mut [Value], week_start: &str) {
    let items = steps
        .iter_mut()
        .map(|step| Ok::<_, EngineError>((step.clone(), json!(week_start), step)));
    history::mark_stale(
        items,
        |step| {
            step["stale"] = json!(true);
            Ok(())
        },
        |error| error,
    )
    .expect("a verdict");
}

#[test]
fn test_capture_step_records_only_what_changed() {
    let before = json!([{"id": "soccer", "title": "Soccer"}]);
    let after = json!([
        {"id": "soccer", "title": "Soccer"},
        {"id": "piano", "title": "Piano"},
    ]);
    let step = capture_step(
        "editing Piano",
        "2026-09-07",
        &before,
        &after,
        &json!({}),
        &json!({}),
        &ids(&[]),
    )
    .expect("a verdict")
    .expect("a step");
    assert_eq!(step["label"], "editing Piano");
    assert_eq!(step["weeks"][0]["before"], before);
    assert_eq!(step["weeks"][0]["after"], after);
    assert_eq!(step["assignments"], json!([]));
}

#[test]
fn test_capture_step_skips_an_unchanged_week() {
    let blocks = json!([{"id": "soccer", "title": "Soccer"}]);
    assert_eq!(
        capture_step(
            "editing",
            "2026-09-07",
            &blocks,
            &blocks,
            &json!({}),
            &json!({}),
            &ids(&[]),
        )
        .expect("a verdict"),
        None
    );
}

#[test]
fn test_capture_step_records_a_new_assignment() {
    let homework = json!({"id": "lab", "title": "Lab", "due": "2026-09-11T08:10"});
    let step = capture_step(
        "editing Lab",
        "2026-09-07",
        &json!([]),
        &json!([]),
        &json!({}),
        &json!({"lab": homework}),
        &ids(&["lab"]),
    )
    .expect("a verdict")
    .expect("a step");
    assert_eq!(
        step["assignments"],
        json!([{"id": "lab", "before": null, "after": homework}])
    );
}

#[test]
fn test_push_step_drops_the_oldest_past_the_limit() {
    let mut stack: Vec<Value> = Vec::new();
    for index in 0..HISTORY_LIMIT + 2 {
        push_step(
            &mut stack,
            json!({"label": index.to_string(), "weeks": [], "assignments": [], "stale": false}),
        );
    }
    assert_eq!(stack.len(), HISTORY_LIMIT);
    assert_eq!(stack[0]["label"], "2");
    assert_eq!(
        stack[stack.len() - 1]["label"],
        (HISTORY_LIMIT + 1).to_string()
    );
}

#[test]
fn test_mark_stale_only_touches_steps_for_that_week() {
    let mut steps = vec![
        json!({"weeks": [{"week_start": "2026-09-07"}], "stale": false}),
        json!({"weeks": [{"week_start": "2026-09-14"}], "stale": false}),
    ];
    mark_stale(&mut steps, "2026-09-07");
    assert_eq!(steps[0]["stale"], json!(true));
    assert_eq!(steps[1]["stale"], json!(false));
}

// The rules the session's Undo and its saves follow (desktop/native/controller.py forwards to them).
mod session_rules {
    use flexweek_engine::desk::history::{
        keep_step_revisions, keep_stored_weeks, request_without_homework, revision_after_deletes,
        stale_words, step_without_homework, travel_refusal,
    };
    use serde_json::{Map, Value, json};

    fn revisions(pairs: &[(&str, i64)]) -> Map<String, Value> {
        pairs
            .iter()
            .map(|(week, number)| ((*week).to_string(), json!(number)))
            .collect()
    }

    fn block(id: &str, homework: Option<&str>) -> Value {
        match homework {
            Some(homework) => json!({"id": id, "assignment_id": homework}),
            None => json!({"id": id}),
        }
    }

    #[test]
    fn each_deleted_homework_with_blocks_in_the_week_moves_its_revision_by_one() {
        let stored = [
            block("s1", Some("essay")),
            block("s2", Some("math")),
            block("club", None),
        ];
        let deleted = [
            "essay".to_string(),
            "math".to_string(),
            "elsewhere".to_string(),
        ];
        assert_eq!(
            revision_after_deletes(&stored, &json!(4), &deleted).unwrap(),
            json!(6)
        );
        assert_eq!(
            revision_after_deletes(&stored, &json!(4), &[]).unwrap(),
            json!(4)
        );
    }

    #[test]
    fn a_week_from_another_day_keeps_the_revisions_it_names() {
        let stored = [block("s1", Some("essay"))];
        let deleted = ["essay".to_string()];
        assert_eq!(
            revision_after_deletes(&stored, &json!([3, 8]), &deleted).unwrap(),
            json!([3, 8])
        );
    }

    #[test]
    fn a_step_loses_the_deleted_homework_and_its_sessions_on_both_sides() {
        let step = json!({
            "label": "moving",
            "weeks": [{
                "week_start": "2026-11-23",
                "before": [block("s1", Some("essay")), json!({"id": "club", "start": "16:00"})],
                "after": [block("s1", Some("essay")), json!({"id": "club", "start": "17:00"})],
                "revision": 4,
            }],
            "assignments": [{"id": "essay"}, {"id": "math"}],
        });
        let cleaned =
            step_without_homework(&step, "essay", &revisions(&[("2026-11-23", 5)])).expect("kept");
        assert_eq!(cleaned["label"], "moving");
        assert_eq!(
            cleaned["weeks"][0]["before"],
            json!([{"id": "club", "start": "16:00"}])
        );
        assert_eq!(
            cleaned["weeks"][0]["after"],
            json!([{"id": "club", "start": "17:00"}])
        );
        assert_eq!(cleaned["weeks"][0]["revision"], 5);
        assert_eq!(cleaned["assignments"], json!([{"id": "math"}]));
    }

    #[test]
    fn a_step_that_only_changed_the_deleted_homework_is_gone() {
        // Otherwise Undo would bring the deleted homework back.
        let step = json!({
            "weeks": [{"week_start": "w", "before": [], "after": [block("s1", Some("essay"))]}],
            "assignments": [{"id": "essay"}],
        });
        assert_eq!(step_without_homework(&step, "essay", &Map::new()), None);
    }

    #[test]
    fn a_week_with_no_revision_yet_gets_none_from_the_delete() {
        let step = json!({
            "weeks": [{"week_start": "w", "before": [block("a", None)], "after": [block("b", None)]}],
        });
        let cleaned = step_without_homework(&step, "essay", &revisions(&[("w", 9)])).expect("kept");
        assert!(cleaned["weeks"][0].get("revision").is_none());
    }

    #[test]
    fn a_failed_save_keeps_its_lead_over_the_drafts_revision_after_a_delete() {
        let request = json!({
            "weeks": [
                {"week_start": "2026-11-23", "blocks": [block("s1", Some("essay")), block("club", None)], "revision": 5},
                {"week_start": "2026-11-30", "blocks": [], "revision": 2},
                {"week_start": "2026-12-07", "blocks": [], "revision": 1},
            ],
            "assignments": [{"id": "essay"}, {"id": "math"}],
            "operation_id": "op",
        });
        let draft = json!({"week_start": "2026-11-23", "revision": 3});
        let moved = revisions(&[("2026-11-23", 7), ("2026-11-30", 4)]);
        let rebuilt = request_without_homework(&request, &draft, "essay", &moved).unwrap();
        assert_eq!(rebuilt["operation_id"], "op");
        // The draft's week led by 2 (5 over 3), so it stays 2 ahead of the moved revision.
        assert_eq!(rebuilt["weeks"][0]["revision"], 9);
        assert_eq!(rebuilt["weeks"][0]["blocks"], json!([{"id": "club"}]));
        assert_eq!(rebuilt["weeks"][1]["revision"], 4);
        assert_eq!(rebuilt["weeks"][2]["revision"], 1);
        assert_eq!(rebuilt["assignments"], json!([{"id": "math"}]));
    }

    #[test]
    fn a_failed_save_of_a_week_from_another_day_takes_each_stored_weeks_new_revision() {
        // A Wednesday week covers the Mondays 2026-11-23 and 2026-11-30.
        let request = json!({
            "weeks": [{"week_start": "2026-11-25", "blocks": [], "revision": [3, 6]}],
            "assignments": [],
        });
        let draft = json!({"week_start": "2026-11-25", "revision": [3, 6]});
        let moved = revisions(&[("2026-11-30", 8)]);
        let rebuilt = request_without_homework(&request, &draft, "essay", &moved).unwrap();
        assert_eq!(rebuilt["weeks"][0]["revision"], json!([3, 8]));
    }

    #[test]
    fn a_save_from_another_day_keeps_each_stored_week_it_changed_in_the_step() {
        let step = json!({"weeks": [{"week_start": "2026-11-25", "before": [], "after": []}]});
        let before = [
            json!({"week_start": "2026-11-23", "blocks": [block("a", None)], "revision": 3}),
            json!({"week_start": "2026-11-30", "blocks": [block("b", None)], "revision": 6}),
        ];
        let after = [
            json!({"week_start": "2026-11-23", "blocks": [block("a", None)], "revision": 3}),
            json!({"week_start": "2026-11-30", "blocks": [block("c", None)], "revision": 7}),
        ];
        let weeks = keep_stored_weeks(&step, &before, &after);
        assert_eq!(weeks.len(), 2);
        assert_eq!(
            weeks[1],
            json!({"week_start": "2026-11-30", "before": [{"id": "b"}], "after": [{"id": "c"}], "revision": 7})
        );
        // Different stored weeks before and after (the week moved): nothing is added.
        let other = [
            json!({"week_start": "2026-12-07", "blocks": [], "revision": 1}),
            after[1].clone(),
        ];
        assert_eq!(keep_stored_weeks(&step, &before, &other).len(), 1);
        // A week the step holds already is not added twice.
        let held = json!({"weeks": [{"week_start": "2026-11-30", "before": [], "after": []}]});
        assert_eq!(keep_stored_weeks(&held, &before, &after).len(), 1);
    }

    #[test]
    fn a_steps_weeks_take_the_revisions_the_save_replied_with() {
        let step = json!({"weeks": [
            {"week_start": "w1", "before": [], "after": [], "revision": 1},
            {"week_start": "w2", "before": [], "after": []},
        ]});
        let data = json!({"weeks": [{"week_start": "w2", "revision": 5}]});
        let weeks = keep_step_revisions(&step, &data);
        assert_eq!(weeks[0]["revision"], 1);
        assert_eq!(weeks[1]["revision"], 5);
    }

    #[test]
    fn undo_and_redo_apply_only_from_a_week_the_step_saved() {
        let step = json!({"weeks": [{"week_start": "2026-11-23"}, {"week_start": "2026-11-30"}]});
        assert_eq!(travel_refusal(&step, "2026-11-30", false), None);
        assert_eq!(
            travel_refusal(&step, "2026-12-07", false),
            Some("Undo applies to the week where that change was saved.")
        );
        assert_eq!(
            travel_refusal(&step, "2026-12-07", true),
            Some("Redo applies to the week where that change was saved.")
        );
        // A step with no weeks (homework only) applies anywhere.
        assert_eq!(
            travel_refusal(&json!({"assignments": []}), "2026-12-07", false),
            None
        );
    }

    #[test]
    fn a_stale_step_says_to_reload() {
        assert_eq!(
            stale_words(false),
            "That change can't be undone. Reload and try again."
        );
        assert_eq!(
            stale_words(true),
            "That change can't be redone. Reload and try again."
        );
    }
}
