//! The session's clipboard, copy rows and relocation decisions (P4 slice 4C): the rules of
//! controller.py's `_fixed_copy_rows` and its empty words, `date_problem`, `_commit_move_to_date`'s
//! decision, `paste_destination`, `copy_block`, `copy_day`, the destination half of
//! `paste_proposals`, and the head of `confirm_preview`, with the words a student reads. Expected
//! values come from those rules and the desktop tests they keep green.

use flexweek_app::session::copies::{
    CommitGroupsBatch, CommitGroupsBatchInput, ConfirmPreviewInput, ConfirmPreviewPlan, CopyDay,
    CopyDayPlan, CopySelectedPlan, DateProblemInput, DateSpan, DuplicatePrep, MoveToDateBatch,
    MoveToDateBatchInput, MoveToDateInput, MoveToDatePlan, PasteProposalsPrep, PasteReady,
    PasteSelection, PreviewGroups, PreviousWeekCopy, Relocation, RelocationInput, block_on_week,
    build_move_to_date_batch, clipboard_block, commit_groups_batch, commit_groups_order,
    confirm_preview_plan, copy_day_items, copy_day_plan, copy_empty_words, copy_selected_plan,
    date_problem, duplicate_selected_prepare, fixed_copy_rows, move_to_date_needed,
    paste_destination, paste_proposals_build, paste_proposals_prepare, paste_ready,
    prepare_move_to_date, preview_groups, previous_week_for_copy, relocate, resolve_date_span,
};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-09-21";
const TODAY: &str = "2026-09-23";

fn locked(id: &str, days: Vec<i64>, start: &str) -> Value {
    json!({"id": id, "title": "Title", "kind": "locked", "duration_min": 60,
           "days": days, "start": start, "category": "extra"})
}

fn school() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "duration_min": 390,
           "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "class"})
}

fn weekly() -> Value {
    json!({"id": "weekly-guitar", "title": "Guitar", "kind": "locked", "duration_min": 60,
           "days": [4], "start": "17:00", "category": "extra"})
}

fn selection<'a>(
    block: Option<&'a str>,
    day: Option<i64>,
    view: &'a str,
    selected_day: &'a str,
) -> PasteSelection<'a> {
    PasteSelection {
        selected_block_id: block,
        selected_occurrence_day: day,
        planner_view: view,
        first_weekday: 0,
        selected_day,
        today_iso: TODAY,
    }
}

fn no_selection() -> PasteSelection<'static> {
    selection(None, None, "week", WEEK)
}

#[test]
fn fixed_rows_copy_a_plain_fixed_time() {
    let source = json!({"blocks": [locked("gym", vec![5], "19:00")]});
    let mut ids = vec!["id-1".to_string()].into_iter();
    let rows = fixed_copy_rows(Some(&source), WEEK, &mut ids).unwrap();
    let rows = rows.rows.expect("one row is offered");
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0]["week_start"], json!(WEEK));
    assert_eq!(rows[0]["day"], json!(5));
    assert_eq!(rows[0]["fixed"], json!(true));
    assert_eq!(rows[0]["checked"], json!(true));
    assert_eq!(rows[0]["invalid"], json!(""));
    assert_eq!(rows[0]["group_id"], json!("id-1"));
    assert_eq!(rows[0]["block"]["id"], json!("id-1"));
    assert_eq!(rows[0]["block"]["days"], json!([5]));
    assert_eq!(rows[0]["block"]["kind"], json!("locked"));
}

#[test]
fn fixed_rows_skip_setup_school_and_standing_weekly_times() {
    // The desktop parity case: the weekly time already stands in this week, so the copy sheet
    // offers the gym row alone and leaves the weekly time out.
    let source = json!({"blocks": [school(), weekly(), locked("gym", vec![5], "19:00")]});
    let mut ids = vec!["id-1".to_string()].into_iter();
    let rows = fixed_copy_rows(Some(&source), WEEK, &mut ids).unwrap();
    let rows = rows.rows.expect("the gym row is offered");
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0]["block"]["id"], json!("id-1"));
}

#[test]
fn fixed_rows_skip_blocks_without_a_kind_start_or_days() {
    let source = json!({"blocks": [
        {"id": "a", "kind": "flexible", "days": [1], "start": "10:00", "duration_min": 60},
        {"id": "b", "kind": "locked", "days": [1], "duration_min": 60},
        {"id": "c", "kind": "locked", "days": [], "start": "10:00", "duration_min": 60},
    ]});
    let mut ids = Vec::new().into_iter();
    let rows = fixed_copy_rows(Some(&source), WEEK, &mut ids).unwrap();
    assert!(rows.rows.is_none());
    assert_eq!(
        rows.words.as_deref(),
        Some("There's nothing to copy from last week yet.")
    );
}

#[test]
fn fixed_rows_without_a_source_offer_nothing() {
    let mut ids = Vec::new().into_iter();
    let rows = fixed_copy_rows(None, WEEK, &mut ids).unwrap();
    assert!(rows.rows.is_none());
    assert_eq!(
        rows.words.as_deref(),
        Some("There's nothing to copy from last week yet.")
    );
}

#[test]
fn empty_words_name_setup_when_only_it_is_left() {
    let source = json!({"blocks": [school()]});
    assert_eq!(
        copy_empty_words(Some(&source)).unwrap(),
        "Nothing to copy: School and the fixed times you added in Setup are already in every week."
    );
    let source = json!({"blocks": []});
    assert_eq!(
        copy_empty_words(Some(&source)).unwrap(),
        "There's nothing to copy from last week yet."
    );
}

fn problem_input<'a>(
    block: Option<&'a Value>,
    from_day: i64,
    to_day: i64,
    assignments: Option<&'a Value>,
) -> DateProblemInput<'a> {
    DateProblemInput {
        block_id: "soccer",
        from_iso: "2026-09-24",
        to_iso: "2026-09-22",
        from_week: WEEK,
        to_week: WEEK,
        from_day,
        to_day,
        block,
        start: None,
        duration_min: None,
        assignment_id: None,
        assignments: assignments.unwrap_or(&Value::Null),
        now_iso: TODAY,
        now_minute: 8 * 60,
        time_step: 15,
    }
}

#[test]
fn a_drag_onto_its_own_date_has_no_problem() {
    // The start would be refused outside planned hours, so only the same-date guard keeps this
    // quiet.
    let block = locked("soccer", vec![3], "25:00");
    let mut input = problem_input(Some(&block), 3, 3, None);
    input.to_iso = input.from_iso;
    assert_eq!(date_problem(&input).unwrap(), None);
}

#[test]
fn a_block_that_is_there_moves_without_a_problem() {
    let block = locked("soccer", vec![3], "16:00");
    assert_eq!(
        date_problem(&problem_input(Some(&block), 3, 1, None)).unwrap(),
        None
    );
}

#[test]
fn a_block_that_is_not_on_the_from_date_has_no_problem() {
    // The start would be refused outside planned hours, so only the from-day guard keeps this
    // quiet.
    let block = locked("soccer", vec![3], "25:00");
    assert_eq!(
        date_problem(&problem_input(Some(&block), 0, 1, None)).unwrap(),
        None
    );
}

#[test]
fn a_start_outside_planned_hours_is_refused_in_words() {
    let block = locked("soccer", vec![3], "25:00");
    assert_eq!(
        date_problem(&problem_input(Some(&block), 3, 1, None)).unwrap(),
        Some("FlexWeek can't use that time, so the block stayed where it was.".to_string())
    );
}

#[test]
fn a_past_start_is_refused_with_the_next_time() {
    // A fixed time may start in the past, so the refusal needs a session without a start of its
    // own yet: one waiting homework session at 07:00 today is already over at 08:00.
    let block = json!({"id": "rest", "kind": "flexible", "days": [3], "duration_min": 60,
                       "start": "07:00"});
    let mut input = problem_input(Some(&block), 3, 2, None);
    input.to_iso = "2026-09-23";
    assert_eq!(
        date_problem(&input).unwrap(),
        Some("That time has passed. Choose 08:00 or later today, or another day.".to_string())
    );
}

#[test]
fn a_move_past_the_homework_deadline_is_refused() {
    let block = json!({"id": "soccer", "kind": "flexible", "days": [3], "start": "16:00",
               "duration_min": 120, "assignment_id": "essay"});
    let assignments = json!({"essay": {"id": "essay", "due": "2026-09-22T17:00"}});
    let mut input = problem_input(Some(&block), 3, 1, Some(&assignments));
    // The destination is tomorrow from here, so the past rule stays out of the due rule's way.
    input.now_iso = "2026-09-21";
    assert_eq!(
        date_problem(&input).unwrap(),
        Some("That ends after it's due, so it stayed where it was.".to_string())
    );
}

#[test]
fn a_dialog_start_without_a_block_is_judged_the_same_way() {
    // No block on the week: the dialog's own start is judged, and a past one is refused.
    let mut input = problem_input(None, 3, 2, None);
    input.to_iso = TODAY;
    input.start = Some("07:00");
    input.duration_min = Some(60);
    assert_eq!(
        date_problem(&input).unwrap(),
        Some("That time has passed. Choose 08:00 or later today, or another day.".to_string())
    );
    // A start with nothing to judge it by is quiet, as is later today.
    let input = problem_input(None, 3, 1, None);
    assert_eq!(date_problem(&input).unwrap(), None);
    let mut input = problem_input(None, 3, 2, None);
    input.to_iso = TODAY;
    input.start = Some("16:00");
    input.duration_min = Some(60);
    assert_eq!(date_problem(&input).unwrap(), None);
}

#[test]
fn a_dialog_homework_without_a_block_is_judged_against_its_due_time() {
    let assignments = json!({"essay": {"id": "essay", "due": "2026-09-22T17:00"}});
    let mut input = problem_input(None, 3, 1, Some(&assignments));
    input.now_iso = "2026-09-21";
    input.start = Some("16:00");
    input.duration_min = Some(120);
    input.assignment_id = Some("essay");
    assert_eq!(
        date_problem(&input).unwrap(),
        Some("That ends after it's due, so it stayed where it was.".to_string())
    );
}

fn relocation_input<'a>(
    source: &'a Value,
    dest: Option<&'a Value>,
    from_week: &'a str,
    to_week: &'a str,
    from_day: i64,
    to_day: i64,
    assignments: Option<&'a Value>,
) -> RelocationInput<'a> {
    RelocationInput {
        block_id: "soccer",
        from_day,
        to_day,
        from_week,
        to_week,
        source,
        dest,
        assignments: assignments.unwrap_or(&Value::Null),
        dest_words: "the week of 28 Sep",
    }
}

fn applied(relocation: Relocation) -> (Vec<Value>, Option<Vec<Value>>, String) {
    match relocation {
        Relocation::Apply {
            source_after,
            dest_after,
            title,
        } => (source_after, dest_after, title),
        Relocation::Say(words) => panic!("expected a move, it said: {words}"),
    }
}

fn said(relocation: Relocation) -> String {
    match relocation {
        Relocation::Say(words) => words,
        Relocation::Apply { .. } => panic!("expected words, the move went ahead"),
    }
}

#[test]
fn a_plain_block_moves_days_in_its_own_week() {
    let source = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let input = relocation_input(&source, None, WEEK, WEEK, 3, 1, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    let (after, dest, title) = applied(relocate(&input, &mut ids).unwrap());
    assert_eq!(dest, None);
    assert_eq!(after.len(), 1);
    assert_eq!(after[0]["days"], json!([1]));
    assert_eq!(title, "Title");
}

#[test]
fn a_move_into_another_week_keeps_what_was_there() {
    // The desktop parity case: the other week is rewritten whole, so piano arrives beside soccer.
    let source = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let dest = json!({"blocks": [locked("piano", vec![2], "18:00")], "revision": 7});
    let input = relocation_input(&source, Some(&dest), WEEK, "2026-09-28", 3, 1, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    let (after, dest_after, _) = applied(relocate(&input, &mut ids).unwrap());
    assert!(after.is_empty());
    let dest_after = dest_after.expect("another week is rewritten");
    assert_eq!(dest_after.len(), 2);
    assert_eq!(dest_after[0]["id"], json!("piano"));
    assert_eq!(dest_after[1]["days"], json!([1]));
}

#[test]
fn a_move_from_the_wrong_date_is_refused() {
    let source = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let input = relocation_input(&source, None, WEEK, WEEK, 0, 1, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    assert_eq!(
        said(relocate(&input, &mut ids).unwrap()),
        "That block isn't on that date."
    );
    let source = json!({"blocks": [], "revision": 4});
    let input = relocation_input(&source, None, WEEK, WEEK, 3, 1, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    assert_eq!(
        said(relocate(&input, &mut ids).unwrap()),
        "That block isn't on that date."
    );
}

#[test]
fn a_relocation_past_the_homework_deadline_is_refused() {
    let source = json!({"blocks": [{
        "id": "soccer", "kind": "flexible", "days": [3], "start": "16:00", "duration_min": 120,
        "assignment_id": "essay"}], "revision": 4});
    let assignments = json!({"essay": {"id": "essay", "due": "2026-09-22T17:00"}});
    let input = relocation_input(&source, None, WEEK, WEEK, 3, 1, Some(&assignments));
    let mut ids = vec!["made-1".to_string()].into_iter();
    assert_eq!(
        said(relocate(&input, &mut ids).unwrap()),
        "That ends after it's due, so it stayed where it was."
    );
}

#[test]
fn a_move_into_a_full_week_is_refused_with_its_words() {
    let source = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let mut dest_blocks = Vec::new();
    for index in 0..100 {
        dest_blocks.push(locked(&format!("b{index}"), vec![0], "10:00"));
    }
    let dest = json!({"blocks": dest_blocks, "revision": 7});
    let input = relocation_input(&source, Some(&dest), WEEK, "2026-09-28", 3, 1, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    assert_eq!(
        said(relocate(&input, &mut ids).unwrap()),
        "the week of 28 Sep would exceed 100 blocks. Uncheck an item or remove a block first."
    );
}

#[test]
fn fixed_rows_treat_a_missing_or_null_blocks_field_as_empty() {
    let mut ids = Vec::new().into_iter();
    for source in [json!({}), json!({"blocks": Value::Null})] {
        let rows = fixed_copy_rows(Some(&source), WEEK, &mut ids).unwrap();
        assert!(rows.rows.is_none());
        assert_eq!(
            rows.words.as_deref(),
            Some("There's nothing to copy from last week yet.")
        );
        assert_eq!(
            copy_empty_words(Some(&source)).unwrap(),
            "There's nothing to copy from last week yet."
        );
    }
    for bad in [json!({"blocks": "not-a-list"}), json!([])] {
        assert!(fixed_copy_rows(Some(&bad), WEEK, &mut ids).is_err());
        assert!(copy_empty_words(Some(&bad)).is_err());
    }
}

#[test]
fn copying_without_a_selection_names_what_to_do() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    let copied = clipboard_block(&blocks, None, None, "auto", "group-1").unwrap();
    assert!(copied.clipboard.is_none());
    assert_eq!(
        copied.words.as_deref(),
        Some("Select a block before copying it.")
    );
    let copied = clipboard_block(&blocks, Some("missing"), None, "auto", "group-1").unwrap();
    assert!(copied.clipboard.is_none());
    assert!(copied.words.is_none());
}

#[test]
fn a_stale_or_empty_selection_falls_through_to_the_day_or_today() {
    let blocks = json!([locked("gym", vec![2], "19:00")]);
    // Even if the trace still mentions the stale id, a missing block does not decide.
    let trace = json!({"placed": [{"id": "missing", "days": [1], "start": "14:00"}]});
    // Gone from the week: the planner day still decides.
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("missing"), Some(1), "day", "2026-09-23"),
        WEEK,
    )
    .unwrap()
    .expect("the planner day decides");
    assert_eq!((found.day, found.start), (Some(2), None));
    // Gone from the week: today still decides.
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("missing"), Some(1), "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("today decides");
    assert_eq!((found.day, found.start), (Some(2), None));
    // An empty id is no selection.
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some(""), Some(1), "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("today decides");
    assert_eq!((found.day, found.start), (Some(2), None));
}

#[test]
fn an_empty_placed_start_is_no_start() {
    let blocks = json!([{"id": "rest", "kind": "flexible", "days": [2], "duration_min": 60}]);
    let trace = json!({"placed": [{"id": "rest", "days": [2], "start": ""}]});
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("rest"), Some(2), "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("the occurrence decides");
    assert_eq!((found.day, found.start), (Some(2), None));
}

#[test]
fn copying_a_plain_block_copies_its_day() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    let copied = clipboard_block(&blocks, Some("piano"), None, "auto", "group-1").unwrap();
    let clipboard = copied.clipboard.expect("the block copies");
    assert_eq!(clipboard["kind"], json!("block"));
    assert_eq!(clipboard["label"], json!("Title"));
    assert_eq!(
        copied.words.as_deref(),
        Some("Title copied. Choose a destination and paste.")
    );
    let items = clipboard["items"].as_array().expect("one item");
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["scope"], json!("block"));
    assert_eq!(items[0]["group_id"], json!("group-1"));
    assert_eq!(items[0]["source_day"], json!(2));
}

#[test]
fn copying_a_series_copies_one_occurrence() {
    let blocks = json!([locked("band", vec![0, 2, 4], "17:00")]);
    let copied = clipboard_block(&blocks, Some("band"), Some(2), "auto", "group-1").unwrap();
    let clipboard = copied.clipboard.expect("the occurrence copies");
    assert_eq!(clipboard["items"][0]["scope"], json!("occurrence"));
    assert_eq!(clipboard["label"], json!("Title (Wednesday only)"));
    let copied = clipboard_block(&blocks, Some("band"), Some(2), "series", "group-1").unwrap();
    let clipboard = copied.clipboard.expect("the series copies");
    assert_eq!(clipboard["label"], json!("Title (all days)"));
}

#[test]
fn the_paste_lands_on_the_selected_occurrence_with_its_start() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    let trace = json!({});
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("piano"), Some(2), "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("the occurrence decides");
    assert_eq!(found.day, Some(2));
    assert_eq!(found.start.as_deref(), Some("18:00"));
}

#[test]
fn the_paste_falls_back_to_the_placed_trace_start() {
    let blocks = json!([{"id": "rest", "kind": "flexible", "days": [2], "duration_min": 60}]);
    let trace = json!({"placed": [{"id": "rest", "days": [2], "start": "18:30"}]});
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("rest"), Some(2), "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("the trace decides");
    assert_eq!(found.day, Some(2));
    assert_eq!(found.start.as_deref(), Some("18:30"));
}

#[test]
fn the_paste_lands_on_the_planner_day_or_today() {
    let blocks = json!([]);
    let trace = json!({});
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(None, None, "day", "2026-09-23"),
        WEEK,
    )
    .unwrap()
    .expect("the planner day decides");
    assert_eq!((found.day, found.start), (Some(2), None));
    let found = paste_destination(&blocks, &trace, &no_selection(), WEEK)
        .unwrap()
        .expect("today decides");
    assert_eq!((found.day, found.start), (Some(2), None));
    // A block without its occurrence day does not decide: today still does.
    let found = paste_destination(
        &blocks,
        &trace,
        &selection(Some("gym"), None, "week", WEEK),
        WEEK,
    )
    .unwrap()
    .expect("today decides without an occurrence");
    assert_eq!((found.day, found.start), (Some(2), None));
    let outside = PasteSelection {
        today_iso: "2026-10-05",
        ..no_selection()
    };
    assert!(
        paste_destination(&blocks, &trace, &outside, WEEK)
            .unwrap()
            .is_none()
    );
}

#[test]
fn copying_a_day_takes_what_is_on_it_but_not_finished_homework() {
    let blocks = json!([
        locked("gym", vec![2], "19:00"),
        {"id": "done", "kind": "flexible", "days": [2], "start": "10:00", "duration_min": 60,
         "assignment_id": "essay", "completed": true},
    ]);
    let mut ids = vec!["a".to_string(), "b".to_string()].into_iter();
    let copied = copy_day_items(&blocks, &json!({}), Some(2), WEEK, &mut ids).unwrap();
    let (clipboard, words) = match copied {
        CopyDay::Copied { clipboard, words } => (clipboard, words),
        CopyDay::Say(words) => panic!("expected a day copy, it said: {words}"),
    };
    assert_eq!(clipboard["kind"], json!("day"));
    assert_eq!(clipboard["items"].as_array().map(Vec::len), Some(1));
    assert_eq!(
        words,
        "Wednesday · 1 item copied. Choose a destination and paste."
    );
}

#[test]
fn copying_an_empty_day_says_so() {
    let blocks = json!([locked("gym", vec![2], "19:00")]);
    let mut ids = vec!["a".to_string()].into_iter();
    let copied = copy_day_items(&blocks, &json!({}), Some(4), WEEK, &mut ids).unwrap();
    match copied {
        CopyDay::Say(words) => assert_eq!(words, "Friday has nothing to copy."),
        CopyDay::Copied { .. } => panic!("an empty day copies nothing"),
    }
}

#[test]
fn copying_a_day_without_a_day_is_refused_like_the_index_was() {
    let blocks = json!([locked("gym", vec![2], "19:00")]);
    let mut ids = Vec::new().into_iter();
    let refused = copy_day_items(&blocks, &json!({}), None, WEEK, &mut ids);
    assert!(refused.is_err(), "no day cannot index the week");
}

#[test]
fn a_paste_needs_a_clipboard_and_a_destination() {
    let blocks = json!([locked("gym", vec![2], "19:00")]);
    let trace = json!({});
    let ready = paste_ready(None, Some(2), None, &blocks, &trace, &no_selection(), WEEK).unwrap();
    match ready {
        PasteReady::Say(words) => assert_eq!(words, "Copy a block or day before pasting."),
        PasteReady::Ready { .. } => panic!("nothing is copied"),
    }
    let clipboard = json!({"kind": "block", "label": "Title", "items": [], "fingerprint": "x"});
    let ready = paste_ready(
        Some(&clipboard),
        Some(3),
        Some("17:00"),
        &blocks,
        &trace,
        &no_selection(),
        WEEK,
    )
    .unwrap();
    match ready {
        PasteReady::Ready { day, start } => assert_eq!((day, start.as_deref()), (3, Some("17:00"))),
        PasteReady::Say(words) => panic!("a target is chosen, it said: {words}"),
    }
    let outside = PasteSelection {
        today_iso: "2026-10-05",
        ..no_selection()
    };
    let ready = paste_ready(
        Some(&clipboard),
        None,
        None,
        &blocks,
        &trace,
        &outside,
        WEEK,
    )
    .unwrap();
    match ready {
        PasteReady::Say(words) => assert_eq!(
            words,
            "Select a block or open Day view before pasting into this week."
        ),
        PasteReady::Ready { .. } => panic!("nowhere to paste"),
    }
}

fn preview_row(day: i64, checked: bool, invalid: &str) -> Value {
    json!({
        "week_start": WEEK,
        "day": day,
        "fixed": false,
        "block": locked("piano", vec![day], "18:00"),
        "group_id": "group-1",
        "checked": checked,
        "invalid": invalid,
    })
}

#[test]
fn the_preview_refuses_an_empty_or_invalid_choice() {
    let rows = json!([preview_row(2, false, "")]);
    match preview_groups(&rows, "op-1").unwrap() {
        PreviewGroups::Say(words) => assert_eq!(words, "Select at least one item before saving."),
        PreviewGroups::Groups { .. } => panic!("nothing is checked"),
    }
    let rows = json!([preview_row(2, true, "taken")]);
    match preview_groups(&rows, "op-1").unwrap() {
        PreviewGroups::Say(words) => {
            assert_eq!(words, "Uncheck what can't be added before saving.")
        }
        PreviewGroups::Groups { .. } => panic!("a refused row is checked"),
    }
}

#[test]
fn the_preview_groups_checked_rows_by_week() {
    // A later week comes first and the rows of one group are split up, as `merge_preview_rows` sees
    // them from the preview: weeks keep the order they were first seen in, one group's days merge
    // (sorted, unchecked rows left out), and the ids carry the operation id without dashes and the
    // group's place in that order.
    let later = |day: i64| {
        let mut row = preview_row(day, true, "");
        row["week_start"] = json!("2026-09-28");
        row["group_id"] = json!("group-2");
        row
    };
    let rows = json!([
        later(0),
        preview_row(4, true, ""),
        preview_row(3, false, ""),
        later(1),
        preview_row(2, true, ""),
    ]);
    match preview_groups(&rows, "op-1").unwrap() {
        PreviewGroups::Say(words) => panic!("rows are checked, it said: {words}"),
        PreviewGroups::Groups { by_week } => {
            let weeks: Vec<&str> = by_week
                .as_object()
                .map(|weeks| weeks.keys().map(String::as_str).collect())
                .unwrap_or_default();
            assert_eq!(weeks, vec!["2026-09-28", WEEK]);
            assert_eq!(by_week["2026-09-28"].as_array().map(Vec::len), Some(1));
            assert_eq!(by_week[WEEK].as_array().map(Vec::len), Some(1));
            assert_eq!(by_week["2026-09-28"][0]["id"], json!("b-stage3-op1-0"));
            assert_eq!(by_week["2026-09-28"][0]["days"], json!([0, 1]));
            assert_eq!(by_week[WEEK][0]["id"], json!("b-stage3-op1-1"));
            assert_eq!(by_week[WEEK][0]["days"], json!([2, 4]));
        }
    }
}

#[test]
fn a_length_too_large_for_an_end_time_is_refused_not_wrapped() {
    // The old Python handed start + length to the engine as a 64-bit integer, which refused it.
    let block = json!({"id": "soccer", "kind": "fixed", "days": [3], "start": "00:01",
                       "duration_min": i64::MAX});
    let mut input = problem_input(Some(&block), 3, 4, None);
    input.to_iso = "2026-09-25";
    input.now_iso = "2026-09-21";
    let error = date_problem(&input).unwrap_err();
    assert_eq!(error.kind, flexweek_engine::ErrorKind::Overflow);

    let source = json!({"blocks": [block], "revision": 4});
    let input = relocation_input(&source, None, WEEK, WEEK, 3, 4, None);
    let mut ids = vec!["made-1".to_string()].into_iter();
    match relocate(&input, &mut ids) {
        Err(error) => assert_eq!(error.kind, flexweek_engine::ErrorKind::Overflow),
        Ok(_) => panic!("an end past the largest integer went ahead"),
    }
}

#[test]
fn a_null_or_empty_homework_record_falls_back_to_the_blocks_own_record() {
    // `get(homework_id) or get(block_id)`: an empty record under the homework id does not stop the
    // lookup, so the due time under the block's own id still refuses a late end.
    let block = json!({"id": "soccer", "kind": "flexible", "days": [3], "start": "16:00",
               "duration_min": 120, "assignment_id": "essay"});
    for empty in [Value::Null, json!({})] {
        let assignments =
            json!({"essay": empty, "soccer": {"id": "soccer", "due": "2026-09-22T17:00"}});
        let mut input = problem_input(Some(&block), 3, 1, Some(&assignments));
        input.now_iso = "2026-09-21";
        assert_eq!(
            date_problem(&input).unwrap(),
            Some("That ends after it's due, so it stayed where it was.".to_string())
        );
    }
}

#[test]
fn a_series_moves_one_day_and_keeps_the_rest() {
    let source = json!({"blocks": [locked("band", vec![0, 2, 4], "17:00")], "revision": 4});
    let mut input = relocation_input(&source, None, WEEK, WEEK, 0, 1, None);
    input.block_id = "band";
    let mut ids = vec!["made-1".to_string()].into_iter();
    let (after, dest, _) = applied(relocate(&input, &mut ids).unwrap());
    assert_eq!(dest, None);
    let mut days: Vec<Vec<i64>> = after
        .iter()
        .map(|block| {
            block["days"]
                .as_array()
                .map(|days| days.iter().filter_map(Value::as_i64).collect())
                .unwrap_or_default()
        })
        .collect();
    days.sort();
    assert_eq!(days, vec![vec![1], vec![2, 4]]);
}

#[test]
fn a_fixed_block_sharing_a_homework_id_is_not_judged_by_its_due_time() {
    let source = json!({"blocks": [{
        "id": "essay", "title": "Essay Club", "kind": "locked",
        "days": [3], "start": "16:00", "duration_min": 120
    }], "revision": 4});
    let assignments = json!({"essay": {"id": "essay", "due": "2026-09-22T17:00"}});
    let mut input = relocation_input(&source, None, WEEK, WEEK, 3, 1, Some(&assignments));
    input.block_id = "essay";
    let mut ids = Vec::new().into_iter();
    let (after, dest, title) = applied(relocate(&input, &mut ids).unwrap());
    assert_eq!(dest, None);
    assert_eq!(after[0]["days"], json!([1]));
    assert_eq!(title, "Essay Club");
}

#[test]
fn days_contain_requires_an_exact_day_number() {
    // `"3"` and `3.7` are not `3` in Python's `3 in days`, so a block with those is not on day 3.
    for bad_days in [json!(["3"]), json!([3.7])] {
        let block = json!({"id": "soccer", "title": "Title", "kind": "locked",
                           "duration_min": 60, "days": bad_days, "start": "25:00"});
        assert_eq!(
            date_problem(&problem_input(Some(&block), 3, 1, None)).unwrap(),
            None
        );
        let source = json!({"blocks": [block], "revision": 4});
        let input = relocation_input(&source, None, WEEK, WEEK, 3, 1, None);
        let mut ids = Vec::new().into_iter();
        assert_eq!(
            said(relocate(&input, &mut ids).unwrap()),
            "That block isn't on that date."
        );
    }
}

#[test]
fn splitting_a_series_without_a_fresh_id_is_refused() {
    let source = json!({"blocks": [locked("band", vec![0, 2, 4], "17:00")], "revision": 4});
    let mut input = relocation_input(&source, None, WEEK, WEEK, 0, 1, None);
    input.block_id = "band";
    let mut empty = Vec::new().into_iter();
    assert!(relocate(&input, &mut empty).is_err());

    // A single-day move splits nothing and needs no fresh id.
    let single = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let input = relocation_input(&single, None, WEEK, WEEK, 3, 1, None);
    let mut empty = Vec::new().into_iter();
    let (after, _, _) = applied(relocate(&input, &mut empty).unwrap());
    assert_eq!(after[0]["days"], json!([1]));
}

#[test]
fn day_view_pastes_onto_the_day_it_shows_not_today() {
    // Today is Wednesday (day 2); Day view shows Friday of the open week, so the paste lands on day 4.
    let blocks = json!([]);
    let trace = json!({});
    let friday = PasteSelection {
        planner_view: "day",
        selected_day: "2026-09-25",
        ..no_selection()
    };
    let found = paste_destination(&blocks, &trace, &friday, WEEK)
        .unwrap()
        .expect("the planner day decides");
    assert_eq!((found.day, found.start), (Some(4), None));
}

#[test]
fn day_view_on_another_week_falls_back_to_today() {
    // Day view shows a date in the next week: it is not the open week, so today's column decides.
    let blocks = json!([]);
    let trace = json!({});
    let later = PasteSelection {
        planner_view: "day",
        selected_day: "2026-09-30",
        ..no_selection()
    };
    let found = paste_destination(&blocks, &trace, &later, WEEK)
        .unwrap()
        .expect("today decides");
    assert_eq!((found.day, found.start), (Some(2), None));
}

#[test]
fn copying_a_series_with_removed_days_takes_only_the_days_still_there() {
    let mut school = school();
    school["removed_days"] = json!([1, 4]);
    let blocks = json!([school]);
    let copied = clipboard_block(&blocks, Some("school"), Some(0), "occurrence", "g1").unwrap();
    let clipboard = copied.clipboard.expect("a copy");
    let item = &clipboard["items"][0];
    assert_eq!(item["block"]["days"], json!([0, 2, 3]));
    assert!(item["block"].get("removed_days").is_none(), "{item}");
}

#[test]
fn a_removed_day_cannot_be_copied() {
    let mut school = school();
    school["removed_days"] = json!([1]);
    let blocks = json!([school]);
    let copied = clipboard_block(&blocks, Some("school"), Some(1), "occurrence", "g1").unwrap();
    assert!(copied.clipboard.is_none());
    let mut all_gone = weekly();
    all_gone["removed_days"] = json!([4]);
    let blocks = json!([all_gone]);
    let copied = clipboard_block(&blocks, Some("weekly-guitar"), None, "auto", "g1").unwrap();
    assert!(
        copied.clipboard.is_none(),
        "a block with every day removed is not there to copy"
    );
}

#[test]
fn previous_week_for_copy_subtracts_seven_days_and_handles_invalid_or_signed_out() {
    assert_eq!(
        previous_week_for_copy(false, WEEK, 0),
        PreviousWeekCopy::Absent
    );
    assert_eq!(
        previous_week_for_copy(true, WEEK, 0),
        PreviousWeekCopy::Ready {
            week_start: "2026-09-14".to_string(),
            path: "/api/week?week_start=2026-09-14".to_string(),
        }
    );
    // Wednesday-starting week maps seven days earlier to the previous Wednesday.
    assert_eq!(
        previous_week_for_copy(true, "2026-09-23", 2),
        PreviousWeekCopy::Ready {
            week_start: "2026-09-16".to_string(),
            path: "/api/week?week_start=2026-09-16".to_string(),
        }
    );
    assert_eq!(
        previous_week_for_copy(true, "not-a-date", 0),
        PreviousWeekCopy::Say("There's nothing to copy from last week yet.")
    );
}

#[test]
fn block_on_week_and_resolve_date_span_handle_present_missing_and_invalid() {
    let state = json!({"blocks": [locked("soccer", vec![0], "16:00")], "revision": 2});
    assert_eq!(
        block_on_week(Some(&state), "soccer").unwrap().unwrap()["id"],
        json!("soccer")
    );
    assert_eq!(block_on_week(Some(&state), "missing").unwrap(), None);
    assert_eq!(block_on_week(None, "soccer").unwrap(), None);

    assert_eq!(
        resolve_date_span("2026-09-24", "2026-09-29", 0),
        Some(DateSpan {
            from_week: WEEK.to_string(),
            to_week: "2026-09-28".to_string(),
            from_day: 3,
            to_day: 1,
        })
    );
    assert_eq!(resolve_date_span("bad", "2026-09-29", 0), None);
}

#[test]
fn prepare_move_to_date_guards_state_short_circuits_same_date_and_builds_key() {
    let base =
        |account_id: Option<i64>, from_iso: &'static str, to_iso: &'static str| MoveToDateInput {
            account_id,
            conflict: false,
            busy: false,
            pending_save: false,
            block_id: "soccer",
            from_iso,
            to_iso,
            first_weekday: 0,
        };
    assert_eq!(
        prepare_move_to_date(&base(None, "2026-09-21", "2026-09-23")),
        MoveToDatePlan::Stop { result: false }
    );
    let mut busy = base(Some(7), "2026-09-21", "2026-09-23");
    busy.busy = true;
    assert_eq!(
        prepare_move_to_date(&busy),
        MoveToDatePlan::Stop { result: false }
    );
    assert_eq!(
        prepare_move_to_date(&base(Some(7), "2026-09-21", "2026-09-21")),
        MoveToDatePlan::Stop { result: true }
    );
    assert_eq!(
        prepare_move_to_date(&base(Some(7), "2026-09-21", "2026-09-29")),
        MoveToDatePlan::Ready {
            from_week: WEEK.to_string(),
            to_week: "2026-09-28".to_string(),
            key: "move-to-date|7|soccer|2026-09-21|2026-09-29".to_string(),
        }
    );
    assert_eq!(
        move_to_date_needed(WEEK, WEEK, false, false),
        vec![WEEK.to_string()]
    );
    assert_eq!(
        move_to_date_needed(WEEK, "2026-09-28", true, false),
        vec!["2026-09-28".to_string()]
    );
    assert!(move_to_date_needed(WEEK, "2026-09-28", true, true).is_empty());
}

#[test]
fn build_move_to_date_batch_builds_writes_step_weeks_and_stay_flag() {
    let source = json!({"blocks": [locked("soccer", vec![3], "16:00")], "revision": 4});
    let dest = json!({"blocks": [locked("piano", vec![2], "18:00")], "revision": 7});
    let mut fetched = Map::new();
    fetched.insert("2026-09-28".to_string(), dest.clone());
    let input = MoveToDateBatchInput {
        block_id: "soccer",
        from_iso: "2026-09-24",
        to_iso: "2026-09-29",
        from_week: WEEK,
        to_week: "2026-09-28",
        source_local: Some(&source),
        dest_local: None,
        fetched: &fetched,
        assignments: &json!({}),
        today_iso: TODAY,
        operation_id: "op-move",
        attempt_key: "move-to-date|1|soccer|2026-09-24|2026-09-29",
    };
    let batch = build_move_to_date_batch(&input, "made-1").unwrap();
    match batch {
        MoveToDateBatch::Submit {
            pending_step,
            history_label,
            move_attempt,
            pending_save,
        } => {
            assert_eq!(history_label, "moving Title to another date");
            assert_eq!(move_attempt, "move-to-date|1|soccer|2026-09-24|2026-09-29");
            assert_eq!(pending_step["label"], json!("moving Title to another date"));
            assert_eq!(pending_step["stale"], json!(false));
            assert_eq!(pending_step["weeks"].as_array().map(Vec::len), Some(2));
            assert_eq!(pending_save["operation_id"], json!("op-move"));
            assert_eq!(pending_save["stay"], json!(true));
            assert_eq!(pending_save["weeks"].as_array().map(Vec::len), Some(2));
            assert_eq!(pending_save["weeks"][0]["week_start"], json!(WEEK));
            assert_eq!(pending_save["weeks"][0]["revision"], json!(4));
            assert_eq!(pending_save["weeks"][1]["week_start"], json!("2026-09-28"));
            assert_eq!(pending_save["weeks"][1]["revision"], json!(7));
        }
        MoveToDateBatch::Say(words) => panic!("expected batch submit, got: {words}"),
    }
}

#[test]
fn copy_selected_and_copy_day_enforce_guards_and_words() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    assert_eq!(
        copy_selected_plan(true, &blocks, None, None, "auto", "g1").unwrap(),
        CopySelectedPlan::Say("Select a block before copying it.".to_string())
    );
    assert_eq!(
        copy_selected_plan(false, &blocks, Some("piano"), Some(2), "auto", "g1").unwrap(),
        CopySelectedPlan::Absent
    );
    match copy_selected_plan(true, &blocks, Some("piano"), Some(2), "auto", "g1").unwrap() {
        CopySelectedPlan::Copied { clipboard, say } => {
            assert_eq!(clipboard["label"], json!("Title"));
            assert_eq!(say, "Title copied. Choose a destination and paste.");
        }
        other => panic!("expected copied, got {other:?}"),
    }

    let outside = PasteSelection {
        today_iso: "2026-10-05",
        ..no_selection()
    };
    let mut ids = vec!["a".to_string()].into_iter();
    assert_eq!(
        copy_day_plan(true, &blocks, &json!({}), None, &outside, WEEK, &mut ids).unwrap(),
        CopyDayPlan::Say(
            "Select a block or open Day view before copying a day from this week.".to_string()
        )
    );
    let mut ids = vec!["a".to_string()].into_iter();
    assert_eq!(
        copy_day_plan(
            false,
            &blocks,
            &json!({}),
            Some(2),
            &no_selection(),
            WEEK,
            &mut ids
        )
        .unwrap(),
        CopyDayPlan::Absent
    );
}

#[test]
fn paste_proposals_handles_signed_out_empty_clipboard_and_available_minutes() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    let trace = json!({});
    assert_eq!(
        paste_proposals_prepare(
            false,
            None,
            Some(0),
            Some("16:00"),
            &blocks,
            &trace,
            &no_selection(),
            WEEK,
            false,
        )
        .unwrap(),
        PasteProposalsPrep::Say("Copy a block or day before pasting.".to_string())
    );
    let copied = clipboard_block(&blocks, Some("piano"), Some(2), "auto", "g1")
        .unwrap()
        .clipboard
        .unwrap();
    assert_eq!(
        paste_proposals_prepare(
            false,
            Some(&copied),
            Some(0),
            Some("16:00"),
            &blocks,
            &trace,
            &no_selection(),
            WEEK,
            false,
        )
        .unwrap(),
        PasteProposalsPrep::Absent
    );
    assert_eq!(
        paste_proposals_prepare(
            true,
            Some(&copied),
            Some(1),
            None,
            &blocks,
            &trace,
            &no_selection(),
            WEEK,
            false,
        )
        .unwrap(),
        PasteProposalsPrep::Ready {
            day: 1,
            start: None,
            needs_minutes: false,
        }
    );

    let hw_blocks = json!([{
        "id": "s1", "title": "Essay", "kind": "flexible", "duration_min": 60,
        "days": [0], "assignment_id": "essay", "category": "assignments"
    }]);
    let hw_clip = clipboard_block(&hw_blocks, Some("s1"), Some(0), "auto", "g1")
        .unwrap()
        .clipboard
        .unwrap();
    let assignments = json!({
        "essay": {"id": "essay", "title": "Essay", "due": "2026-09-27T23:59", "estimate_min": 90}
    });
    let minutes = json!({"essay": {"uncovered_min": 30}});
    let rows = paste_proposals_build(&hw_clip, WEEK, 3, None, &assignments, &minutes).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0]["block"]["duration_min"], json!(30));
    assert_eq!(rows[0]["block"]["assignment_id"], json!("essay"));
}

#[test]
fn duplicate_never_says_it_copied() {
    let blocks = json!([locked("piano", vec![2], "18:00")]);
    assert_eq!(
        duplicate_selected_prepare(true, &blocks, None, None, "auto", "g1", false).unwrap(),
        DuplicatePrep::Say("Select a block before duplicating it.".to_string())
    );
    match duplicate_selected_prepare(true, &blocks, Some("piano"), Some(2), "auto", "g1", false)
        .unwrap()
    {
        DuplicatePrep::Ready {
            clipboard,
            target_day,
            announce,
            needs_minutes,
        } => {
            assert_eq!(clipboard["label"], json!("Title"));
            assert_eq!(target_day, 2);
            assert_eq!(
                announce, None,
                "Duplicate leaves nothing copied, so it says nothing"
            );
            assert!(!needs_minutes);
        }
        other => panic!("expected duplicate ready, got {other:?}"),
    }
    // Missing occurrence day defaults to day 0, matching `day if day is not None else 0`.
    match duplicate_selected_prepare(true, &blocks, Some("piano"), None, "auto", "g1", true)
        .unwrap()
    {
        DuplicatePrep::Ready {
            target_day,
            announce,
            needs_minutes,
            ..
        } => {
            assert_eq!(target_day, 0);
            assert_eq!(announce, None);
            assert!(needs_minutes);
        }
        other => panic!("expected duplicate ready, got {other:?}"),
    }
}

#[test]
fn confirm_preview_refuses_without_reserving_attempt_and_checks_single_week_capacity() {
    let rows = json!([preview_row(2, false, "")]);
    let attempts = Map::new();
    let input = ConfirmPreviewInput {
        signed_in: true,
        conflict: false,
        rows: &rows,
        week_start: WEEK,
        blocks: &json!([]),
        today_iso: TODAY,
        operation_id: None,
        attempt_key: Some("paste-1"),
        attempts: &attempts,
        fresh_operation_id: "fresh-1",
    };
    assert_eq!(
        confirm_preview_plan(&input).unwrap(),
        ConfirmPreviewPlan::Say {
            say: "Select at least one item before saving.".to_string(),
            record_attempt: false,
            op_id: "fresh-1".to_string(),
        }
    );

    // 100 blocks already present -> single-week capacity refusal.
    let mut full = Vec::new();
    for index in 0..100 {
        full.push(locked(&format!("pad-{index}"), vec![6], "06:00"));
    }
    let full_blocks = Value::Array(full);
    let checked = json!([preview_row(2, true, "")]);
    let input = ConfirmPreviewInput {
        signed_in: true,
        conflict: false,
        rows: &checked,
        week_start: WEEK,
        blocks: &full_blocks,
        today_iso: TODAY,
        operation_id: None,
        attempt_key: Some("paste-1"),
        attempts: &attempts,
        fresh_operation_id: "fresh-2",
    };
    match confirm_preview_plan(&input).unwrap() {
        ConfirmPreviewPlan::Say {
            say,
            record_attempt,
            ..
        } => {
            assert!(say.contains("100 blocks"), "{say}");
            assert!(record_attempt);
        }
        other => panic!("expected capacity refusal, got {other:?}"),
    }
}

#[test]
fn commit_groups_preserves_reversed_get_order_and_builds_batch() {
    let mut by_week = Map::new();
    by_week.insert(WEEK.to_string(), json!([locked("a", vec![0], "10:00")]));
    by_week.insert(
        "2026-09-28".to_string(),
        json!([locked("b", vec![1], "11:00")]),
    );
    by_week.insert(
        "2026-10-05".to_string(),
        json!([locked("c", vec![2], "12:00")]),
    );
    // Python's `needed.pop()` fetches remote weeks from last to first.
    assert_eq!(
        commit_groups_order(&by_week, WEEK),
        vec!["2026-10-05".to_string(), "2026-09-28".to_string()]
    );

    let mut fetched = Map::new();
    fetched.insert(
        "2026-09-28".to_string(),
        json!({"blocks": [], "revision": 3}),
    );
    fetched.insert(
        "2026-10-05".to_string(),
        json!({"blocks": [], "revision": 5}),
    );
    let input = CommitGroupsBatchInput {
        by_week: &by_week,
        week_start: WEEK,
        current_blocks: &[locked("existing", vec![4], "09:00")],
        current_revision: &json!(2),
        fetched: &fetched,
        today_iso: TODAY,
        label: "the routine",
        snapshot_label: Some("Before applying"),
        operation_id: "op-9",
        said: Some("Applied."),
    };
    match commit_groups_batch(&input).unwrap() {
        CommitGroupsBatch::Submit {
            pending_save,
            blocks,
            history_label,
            capture_step,
            save_status,
        } => {
            assert_eq!(pending_save["operation_id"], json!("op-9"));
            assert_eq!(pending_save["snapshot_label"], json!("Before applying"));
            assert_eq!(pending_save["weeks"].as_array().map(Vec::len), Some(3));
            assert_eq!(blocks.as_ref().map(Vec::len), Some(2));
            assert_eq!(history_label.as_deref(), Some("the routine"));
            assert!(capture_step);
            assert_eq!(save_status.as_deref(), Some("Applied."));
        }
        CommitGroupsBatch::Say(words) => panic!("expected submit, got: {words}"),
    }

    // Remote week past 100 blocks is refused with capacity words.
    let mut full = Vec::new();
    for index in 0..100 {
        full.push(locked(&format!("pad-{index}"), vec![6], "06:00"));
    }
    fetched.insert(
        "2026-09-28".to_string(),
        json!({"blocks": full, "revision": 3}),
    );
    let input = CommitGroupsBatchInput {
        by_week: &by_week,
        week_start: WEEK,
        current_blocks: &[],
        current_revision: &json!(2),
        fetched: &fetched,
        today_iso: TODAY,
        label: "the routine",
        snapshot_label: None,
        operation_id: "op-10",
        said: None,
    };
    match commit_groups_batch(&input).unwrap() {
        CommitGroupsBatch::Say(words) => assert!(words.contains("100 blocks"), "{words}"),
        CommitGroupsBatch::Submit { .. } => panic!("full remote week must be refused"),
    }
}
