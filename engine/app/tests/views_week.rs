//! Material Week view-model and navigation rules (P5-W1), pinned to the desktop Week tests and
//! `bridge_week.py` contract.

use std::collections::HashSet;
use std::sync::{Mutex, MutexGuard};

static CLOCK_LOCK: Mutex<()> = Mutex::new(());

fn lock_clock() -> MutexGuard<'static, ()> {
    CLOCK_LOCK
        .lock()
        .unwrap_or_else(|poison| poison.into_inner())
}

use flexweek_app::views::theme::paint_for_category;
use flexweek_app::views::week::{
    EVERYTHING_TIMED, FRESH_S, MovePlan, OccurrenceInput, PLAN_WINDOW_S, ReloadInput, SLACK_DANGER,
    SLACK_OK, SLACK_PLAIN, SLACK_TIGHT, ToggleDonePlan, UncoveredInput, WEEKEND_SAVE_FAILED,
    WaitingInput, WeekNavState, WeekView, bool_pref, hand_move_problem, has_copied, left_line,
    non_breaking_length, occurrence_row, optional_day, overlapped, parse_iso_date, plan_label,
    tag_for,
};
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

fn fixed_occ(
    block_id: &str,
    title: &str,
    category: &str,
    day: i64,
    start: i64,
    end: i64,
) -> OccurrenceInput {
    OccurrenceInput {
        block_id: block_id.to_string(),
        title: title.to_string(),
        category: category.to_string(),
        day,
        start,
        end,
        work: false,
        done: false,
        assignment_id: String::new(),
    }
}

fn hw_occ(
    block_id: &str,
    title: &str,
    day: i64,
    span: (i64, i64),
    done: bool,
    assignment_id: &str,
) -> OccurrenceInput {
    OccurrenceInput {
        block_id: block_id.to_string(),
        title: title.to_string(),
        category: "assignments".to_string(),
        day,
        start: span.0,
        end: span.1,
        work: true,
        done,
        assignment_id: assignment_id.to_string(),
    }
}

fn waiting(
    block_id: &str,
    title: &str,
    minutes: i64,
    assignment_id: &str,
    due: Option<&str>,
    reason: &str,
) -> WaitingInput {
    WaitingInput {
        block_id: block_id.to_string(),
        title: title.to_string(),
        minutes,
        assignment_id: assignment_id.to_string(),
        due: due.map(str::to_string),
        reason: reason.to_string(),
    }
}

#[test]
fn bool_pref_accepts_only_explicit_booleans() {
    let prefs = json!({
        "show_weekends": false,
        "dim_completed": true,
        "int_zero": 0,
        "int_one": 1,
        "text": "false",
        "empty": null,
    });
    assert!(!bool_pref(&prefs, "show_weekends", true));
    assert!(bool_pref(&prefs, "dim_completed", false));
    assert!(bool_pref(&prefs, "missing", true));
    assert!(!bool_pref(&prefs, "missing", false));
    assert!(bool_pref(&prefs, "int_zero", true));
    assert!(!bool_pref(&prefs, "int_one", false));
    assert!(bool_pref(&prefs, "text", true));
    assert!(bool_pref(&prefs, "empty", true));
    assert!(bool_pref(&Value::Null, "show_weekends", true));
}

#[test]
fn occurrence_row_dims_finished_and_past_blocks_but_not_missed_sessions() {
    let _guard = lock_clock();
    set_clock_24h(true);
    let school = fixed_occ("School", "School", "class", 1, 16 * 60, 17 * 60);
    let maths = hw_occ("Maths", "Maths", 1, (16 * 60, 17 * 60), true, "a");
    let essay = hw_occ("Essay", "Essay", 1, (16 * 60, 17 * 60), false, "a");

    let row_school = occurrence_row(&school, "light", true, true, false, false).unwrap();
    let (fill, ink) = paint_for_category("class", "light").unwrap();
    assert_eq!(row_school["title"], "School");
    assert_eq!(row_school["day"], 1);
    assert_eq!(row_school["start"], 960);
    assert_eq!(row_school["end"], 1020);
    assert_eq!(row_school["fill"], fill);
    assert_eq!(row_school["ink"], ink);
    assert_eq!(row_school["category"], "class");
    assert_eq!(row_school["detail"], "16:00–17:00");
    assert_eq!(row_school["detailStart"], "16:00");
    assert_eq!(row_school["past"], true);
    assert_eq!(row_school["homework"], false);
    assert_eq!(row_school["assignmentId"], "");
    assert_eq!(row_school["indent"], 0);
    assert_eq!(row_school["under"], json!([]));

    assert_eq!(
        occurrence_row(&maths, "light", true, true, false, false).unwrap()["past"],
        true
    );
    assert_eq!(
        occurrence_row(&essay, "light", true, true, false, false).unwrap()["past"],
        true
    );
    assert_eq!(
        occurrence_row(&essay, "light", true, true, false, true).unwrap()["past"],
        false
    );
    assert_eq!(
        occurrence_row(&essay, "light", true, false, false, true).unwrap()["past"],
        false
    );
    assert_eq!(
        occurrence_row(&maths, "light", false, true, false, false).unwrap()["past"],
        false
    );

    let unknown_cat = OccurrenceInput {
        category: "meals".to_string(),
        ..hw_occ("u", "Lunch", 2, (12 * 60, 12 * 60 + 30), false, "")
    };
    let row_unknown = occurrence_row(&unknown_cat, "dark", true, false, true, false).unwrap();
    assert_eq!(row_unknown["category"], "other");
    assert_eq!(row_unknown["homework"], false);
    assert_eq!(row_unknown["fresh"], true);
}

#[test]
fn overlapped_orders_by_day_start_longest_first_and_computes_indent_and_under() {
    let rows = vec![
        json!({"title": "Short", "day": 3, "start": 960, "end": 1020}),
        json!({"title": "Long", "day": 3, "start": 960, "end": 1050}),
        json!({"title": "After", "day": 3, "start": 1050, "end": 1080}),
        json!({"title": "Middle", "day": 3, "start": 990, "end": 1020}),
        json!({"title": "Monday", "day": 0, "start": 960, "end": 1050}),
    ];
    let placed = overlapped(rows).unwrap();
    let titles: Vec<&str> = placed
        .iter()
        .map(|row| row["title"].as_str().unwrap())
        .collect();
    assert_eq!(titles, vec!["Monday", "Long", "Short", "Middle", "After"]);

    let by_title = |name: &str| placed.iter().find(|row| row["title"] == name).unwrap();
    assert_eq!(by_title("Monday")["indent"], 0);
    assert_eq!(by_title("Long")["indent"], 0);
    assert_eq!(by_title("Short")["indent"], 1);
    assert_eq!(by_title("Middle")["indent"], 2);
    assert_eq!(by_title("After")["indent"], 0);

    assert_eq!(by_title("Monday")["under"], json!([]));
    assert_eq!(by_title("Long")["under"], json!([]));
    assert_eq!(by_title("Short")["under"], json!([1]));
    assert_eq!(by_title("Middle")["under"], json!([1, 2]));
    assert_eq!(by_title("After")["under"], json!([]));
}

#[test]
fn overlapped_rejects_wrong_shaped_rows() {
    assert!(overlapped(vec![json!("not-an-object")]).is_err());
    assert!(overlapped(vec![json!({"day": 0, "start": 60})]).is_err());
}

#[test]
fn slack_tags_follow_room_and_24_hour_guard() {
    assert_eq!(
        tag_for(None, 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_PLAIN
    );
    assert_eq!(
        tag_for(Some(""), 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_PLAIN
    );
    assert_eq!(
        tag_for(Some("not-a-date"), 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_OK
    );
    // Thursday 19:00: 120 - 60 = 60 min room -> danger.
    assert_eq!(
        tag_for(Some("2026-11-05T21:00"), 60, "2026-11-05", 19 * 60).unwrap(),
        SLACK_DANGER
    );
    // Thursday 19:00: 180 - 30 = 150 min room -> tight.
    assert_eq!(
        tag_for(Some("2026-11-05T22:00"), 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_TIGHT
    );
    // Within 24h (23h left): tight even with plenty of room.
    assert_eq!(
        tag_for(Some("2026-11-06T18:00"), 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_TIGHT
    );
    // 25h left: plenty of time.
    assert_eq!(
        tag_for(Some("2026-11-06T20:00"), 30, "2026-11-05", 19 * 60).unwrap(),
        SLACK_OK
    );
    // All-day Friday due at 19:00 Friday -> 5h left -> tight.
    assert_eq!(
        tag_for(Some("2026-11-06"), 30, "2026-11-06", 19 * 60).unwrap(),
        SLACK_TIGHT
    );
    // Friday 23:59 (canonical 24:00) at 00:00 Friday -> exactly 24h left -> ok.
    assert_eq!(
        tag_for(Some("2026-11-06T23:59"), 30, "2026-11-06", 0).unwrap(),
        SLACK_OK
    );
    // After Sunday into next week: same 24h guard.
    assert_eq!(
        tag_for(Some("2026-11-09T18:00"), 30, "2026-11-08", 19 * 60).unwrap(),
        SLACK_TIGHT
    );
    assert_eq!(
        tag_for(Some("2026-11-09T20:00"), 30, "2026-11-08", 19 * 60).unwrap(),
        SLACK_OK
    );
}

#[test]
fn left_line_and_plan_label_and_simple_helpers_match_contract() {
    assert_eq!(left_line(&[]), "");
    assert_eq!(
        left_line(&[json!({"left_over_state": "overdue"})]),
        "1 overdue"
    );
    assert_eq!(
        left_line(&[json!({"left_over_state": "left_from_last_week"})]),
        "1 left from last week"
    );
    assert_eq!(
        left_line(&[
            json!({"left_over_state": "overdue"}),
            json!({"left_over_state": "left_from_last_week"}),
            json!({"left_over_state": "overdue"}),
        ]),
        "2 overdue · 1 left from last week"
    );

    assert_eq!(
        plan_label(&json!({"planning_style": "manual"})),
        "Suggest times"
    );
    assert_eq!(
        plan_label(&json!({"planning_style": "balanced"})),
        "Plan my homework"
    );
    assert_eq!(plan_label(&Value::Null), "Plan my homework");

    assert_eq!(optional_day(0), Some(0));
    assert_eq!(optional_day(4), Some(4));
    assert_eq!(optional_day(-1), None);
    assert!(has_copied(true, false));
    assert!(!has_copied(true, true));
    assert!(!has_copied(false, false));

    assert_eq!(parse_iso_date("2026-11-17"), Some("2026-11-17".to_string()));
    assert_eq!(parse_iso_date("20261117"), Some("2026-11-17".to_string()));
    assert_eq!(parse_iso_date("bad-date"), None);

    assert_eq!(
        hand_move_problem(&json!({"moved": true, "problem": ""})).unwrap(),
        None
    );
    assert_eq!(
        hand_move_problem(&json!({"moved": false, "problem": "That time has passed."})).unwrap(),
        Some("That time has passed.".to_string())
    );
    assert!(hand_move_problem(&json!("not-an-object")).is_err());

    assert_eq!(non_breaking_length(30), "30\u{00a0}min");
    assert_eq!(non_breaking_length(60), "1\u{00a0}h");
    assert_eq!(non_breaking_length(90), "1\u{00a0}h 30\u{00a0}min");
}

#[test]
fn reload_builds_days_blocks_drawer_counts_leftovers_and_fresh_tracking() {
    let _guard = lock_clock();
    let mut view = WeekView::new();
    let prefs = json!({
        "clock_24h": true,
        "show_weekends": true,
        "dim_completed": true,
        "drag_step_min": 5,
    });
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    let occurrences = vec![
        fixed_occ("school", "School", "class", 0, 8 * 60, 14 * 60 + 30),
        hw_occ("past-hw", "Missed lab", 1, (16 * 60, 17 * 60), false, "lab"),
        hw_occ(
            "now-hw",
            "History essay",
            3,
            (18 * 60 + 45, 19 * 60 + 45),
            false,
            "essay",
        ),
    ];
    let waiting_items = vec![
        waiting(
            "w1",
            "Cut one",
            60,
            "cut",
            Some("2026-11-05T21:00"),
            "Not placed yet.",
        ),
        waiting(
            "w2",
            "Tight one",
            30,
            "tight",
            Some("2026-11-05T22:00"),
            "Not placed yet.",
        ),
        waiting(
            "w3",
            "Plenty one",
            30,
            "plenty",
            Some("2026-11-08"),
            "Not placed yet.",
        ),
    ];
    let missed: HashSet<String> = HashSet::from(["past-hw".to_string()]);
    let needed = vec![
        json!({"assignment_id": "cut", "title": "Cut one", "minutes": 60}),
        json!({"assignment_id": "lab", "title": "Missed lab", "minutes": 60, "missed_min": 60, "pinned_min": 30}),
    ];
    let uncovered = vec![
        // Shares id "cut" with waiting card -> counted once in listed_count!
        UncoveredInput {
            title: "Cut one".to_string(),
            minutes: 15,
            assignment_id: json!("cut"),
        },
        UncoveredInput {
            title: "Science poster".to_string(),
            minutes: 60,
            assignment_id: json!("poster"),
        },
    ];
    let unfinished = vec![
        json!({"left_over_state": "overdue"}),
        json!({"left_over_state": "left_from_last_week"}),
    ];

    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &occurrences,
        waiting: &waiting_items,
        missed: &missed,
        needed: &needed,
        plan_can_place: false,
        uncovered: &uncovered,
        unfinished: &unfinished,
        today_iso: "2026-11-05",
        clock_minute: 19 * 60,
        steady_ms: 10_000,
        fresh_s: FRESH_S,
    })
    .unwrap();

    assert_eq!(view.hour_labels.len(), 24);
    assert_eq!(view.hour_labels[0], "00:00");
    assert_eq!(view.hour_labels[16], "16:00");
    assert_eq!(view.columns, 7);
    assert_eq!(view.drag_step, 5);
    assert_eq!(view.now_day, 3);
    assert_eq!(view.now_column, 3);
    assert_eq!(view.now_minute, 19 * 60);
    assert_eq!(view.day_headers[0], "Mon 2");
    assert_eq!(view.day_rows[0]["date"], "2");
    assert_eq!(view.day_rows[3]["today"], true);
    assert_eq!(view.day_rows[0]["today"], false);

    // First reload: nothing is fresh yet.
    assert!(view.block_rows.iter().all(|row| row["fresh"] == false));
    // School (Mon) is past -> dimmed; Missed lab (Tue) is missed -> NOT dimmed; History essay ends 19:45 > 19:00 -> NOT dimmed.
    let by_id = |id: &str| view.block_rows.iter().find(|r| r["blockId"] == id).unwrap();
    assert_eq!(by_id("school")["past"], true);
    assert_eq!(by_id("past-hw")["past"], false);
    assert_eq!(by_id("now-hw")["past"], false);

    // Waiting cards: details use non-breaking spaces before h/min and exact slack tags.
    assert_eq!(view.homework_rows.len(), 3);
    assert_eq!(
        view.homework_rows[0]["detail"],
        "Due Thu 5 Nov, 21:00 · 1\u{00a0}h"
    );
    assert_eq!(view.homework_rows[0]["tag"], "Cutting it close");
    assert_eq!(view.homework_rows[0]["tagKind"], "cutting");
    assert_eq!(
        view.homework_rows[1]["detail"],
        "Due Thu 5 Nov, 22:00 · 30\u{00a0}min"
    );
    assert_eq!(view.homework_rows[1]["tag"], "Tight");
    assert_eq!(
        view.homework_rows[2]["detail"],
        "Due Sun 8 Nov · 30\u{00a0}min"
    );
    assert_eq!(view.homework_rows[2]["tag"], "Plenty of time");

    // Listed count deduplicates cut (card + uncovered) + tight + plenty + poster + lab = 5.
    assert_eq!(view.listed_count, 5);
    assert_eq!(
        view.leftover_words,
        "Cut one · 15 min with no time\nScience poster · 1 h with no time\nMissed lab · 1 h missed\nMissed lab · 30 min pinned, in the past"
    );
    assert_eq!(view.left_words, "1 overdue · 1 left from last week");
    assert!(!view.all_timed);
    assert!(view.can_plan);

    // Second reload on the same week with a newly landed block: marked fresh for FRESH_S (1000 ms).
    let mut with_new = occurrences.clone();
    with_new.push(hw_occ(
        "new-hw",
        "Math worksheet",
        4,
        (16 * 60, 16 * 60 + 30),
        false,
        "sheet",
    ));
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &with_new,
        waiting: &[],
        missed: &missed,
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-05",
        clock_minute: 19 * 60,
        steady_ms: 10_500,
        fresh_s: FRESH_S,
    })
    .unwrap();
    let fresh_titles: Vec<&str> = view
        .block_rows
        .iter()
        .filter(|row| row["fresh"] == true)
        .map(|row| row["title"].as_str().unwrap())
        .collect();
    assert_eq!(fresh_titles, vec!["Math worksheet"]);
    assert_eq!(view.time_words, EVERYTHING_TIMED);
    assert!(view.all_timed);
    assert!(!view.can_plan);

    // Still fresh at 11_499 ms (< 10_500 + 1_000), no longer fresh at 11_500 ms.
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &with_new,
        waiting: &[],
        missed: &missed,
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-05",
        clock_minute: 19 * 60,
        steady_ms: 11_499,
        fresh_s: FRESH_S,
    })
    .unwrap();
    assert!(
        view.block_rows
            .iter()
            .any(|row| row["blockId"] == "new-hw" && row["fresh"] == true)
    );

    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &with_new,
        waiting: &[],
        missed: &missed,
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-05",
        clock_minute: 19 * 60,
        steady_ms: 11_500,
        fresh_s: FRESH_S,
    })
    .unwrap();
    assert!(view.block_rows.iter().all(|row| row["fresh"] == false));
}

#[test]
fn reload_hides_weekend_columns_and_resets_when_signed_out() {
    let _guard = lock_clock();
    let mut view = WeekView::new();
    let prefs = json!({"clock_24h": false, "show_weekends": false});
    // Wednesday-starting week 2026-11-04: Wed(0), Thu(1), Fri(2), Sat(3 hidden), Sun(4 hidden), Mon(5), Tue(6).
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-04"), true)
            .unwrap()
    );
    let occurrences = vec![
        fixed_occ("sat", "Saturday club", "extra", 3, 10 * 60, 11 * 60),
        fixed_occ("mon", "Monday school", "class", 5, 8 * 60, 12 * 60),
    ];
    // Today is Saturday (offset = 3): hidden from shown_days, so now_day=3, now_column=-1!
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &occurrences,
        waiting: &[],
        missed: &HashSet::new(),
        needed: &[],
        plan_can_place: true,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-07",
        clock_minute: 10 * 60 + 30,
        steady_ms: 1_000,
        fresh_s: FRESH_S,
    })
    .unwrap();

    assert_eq!(view.hour_labels[0], "12:00 AM");
    assert_eq!(view.hour_labels[13], "1:00 PM");
    assert_eq!(view.shown_days, vec![0, 1, 2, 5, 6]);
    assert_eq!(view.columns, 5);
    assert_eq!(view.now_day, 3);
    assert_eq!(view.now_column, -1);
    assert_eq!(view.now_minute, 10 * 60 + 30);
    assert_eq!(view.block_rows.len(), 1);
    assert_eq!(view.block_rows[0]["blockId"], "mon");
    assert_eq!(view.block_rows[0]["column"], 3);
    assert!(view.can_plan);

    // Sign out clears rows, counts, and seen so re-sign-in does not mark seed blocks fresh.
    assert!(
        !view
            .prepare_reload(&prefs, Some("2026-11-04"), false)
            .unwrap()
    );
    assert!(view.block_rows.is_empty());
    assert!(view.day_rows.is_empty());
    assert_eq!(view.listed_count, 0);
    assert_eq!(view.now_day, -1);
    assert_eq!(view.now_column, -1);
    assert_eq!(view.now_minute, 0);

    // Re-sign-in on same week: seen was cleared, so Monday school is NOT fresh.
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-04"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &occurrences,
        waiting: &[],
        missed: &HashSet::new(),
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-07",
        clock_minute: 10 * 60 + 30,
        steady_ms: 2_000,
        fresh_s: FRESH_S,
    })
    .unwrap();
    assert_eq!(view.block_rows[0]["fresh"], false);
}

#[test]
fn reload_marks_past_and_future_weeks_gone_correctly() {
    let _guard = lock_clock();
    let mut view = WeekView::new();
    let prefs = json!({"clock_24h": true});
    let occurrences = vec![fixed_occ("b1", "Class", "class", 6, 20 * 60, 21 * 60)];

    // Past week (today is 2026-11-12, week starts 2026-11-02 -> offset = 10 > 6): all gone.
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &occurrences,
        waiting: &[],
        missed: &HashSet::new(),
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-12",
        clock_minute: 9 * 60,
        steady_ms: 1_000,
        fresh_s: FRESH_S,
    })
    .unwrap();
    assert_eq!(view.block_rows[0]["past"], true);
    assert_eq!(view.now_day, -1);
    assert_eq!(view.now_minute, 0);

    // Future week (today is 2026-11-01, week starts 2026-11-02 -> offset = -1 < 0): none gone.
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    view.finish_reload(ReloadInput {
        mode: "light",
        occurrences: &occurrences,
        waiting: &[],
        missed: &HashSet::new(),
        needed: &[],
        plan_can_place: false,
        uncovered: &[],
        unfinished: &[],
        today_iso: "2026-11-01",
        clock_minute: 23 * 60,
        steady_ms: 2_000,
        fresh_s: FRESH_S,
    })
    .unwrap();
    assert_eq!(view.block_rows[0]["past"], false);
}

#[test]
fn place_homework_and_move_block_validate_and_snap() {
    let _guard = lock_clock();
    let mut view = WeekView::new();
    let prefs = json!({"show_weekends": false, "drag_step_min": 15});
    assert!(
        view.prepare_reload(&prefs, Some("2026-11-02"), true)
            .unwrap()
    );
    let blocks = vec![
        json!({"id": "hw1", "duration_min": 30}),
        json!({"id": "zero", "duration_min": 0}),
    ];

    // Hidden day (Saturday = 5) is refused for drawer drop, allowed for moveBlock.
    assert_eq!(
        view.place_homework_plan(&blocks, "hw1", 5, 960, false)
            .unwrap(),
        None
    );
    assert_eq!(
        view.move_block_plan(&blocks, "hw1", 5, 960, 990, false),
        Some(MovePlan {
            start: 960,
            end: 990,
            judge: true
        })
    );

    // Snaps 16:20 (980) to 16:15 (975) on a 15-min step.
    assert_eq!(
        view.place_homework_plan(&blocks, "hw1", 4, 980, false)
            .unwrap(),
        Some(MovePlan {
            start: 975,
            end: 1005,
            judge: true
        })
    );
    // Clamps to [0, 1440 - length].
    assert_eq!(
        view.place_homework_plan(&blocks, "hw1", 4, -40, true)
            .unwrap(),
        Some(MovePlan {
            start: 0,
            end: 30,
            judge: false
        })
    );
    assert_eq!(
        view.place_homework_plan(&blocks, "hw1", 4, 1435, false)
            .unwrap(),
        Some(MovePlan {
            start: 1410,
            end: 1440,
            judge: true
        })
    );

    // Unknown id or non-positive duration refused.
    assert_eq!(
        view.place_homework_plan(&blocks, "missing", 0, 600, false)
            .unwrap(),
        None
    );
    assert_eq!(
        view.place_homework_plan(&blocks, "zero", 0, 600, false)
            .unwrap(),
        None
    );

    // moveBlock refuses out-of-range day, non-increasing span, or unknown block.
    assert_eq!(
        view.move_block_plan(&blocks, "hw1", -1, 600, 660, false),
        None
    );
    assert_eq!(
        view.move_block_plan(&blocks, "hw1", 7, 600, 660, false),
        None
    );
    assert_eq!(
        view.move_block_plan(&blocks, "hw1", 2, 660, 660, false),
        None
    );
    assert_eq!(
        view.move_block_plan(&blocks, "hw1", 2, 700, 660, false),
        None
    );
    assert_eq!(
        view.move_block_plan(&blocks, "missing", 2, 600, 660, false),
        None
    );
}

#[test]
fn plan_one_prefers_unstarted_session_and_opens_plan_status_window() {
    let mut view = WeekView::new();
    let blocks = vec![
        json!({"id": "b-placed", "assignment_id": "essay", "start": "16:00"}),
        json!({"id": "b-waiting", "assignment_id": "essay", "start": null}),
    ];
    assert_eq!(
        view.plan_one_target(&blocks, "essay", 5_000),
        Some("b-waiting".to_string())
    );
    // Ellipsis status does not consume the plan window.
    assert!(!view.on_status("Planning…", 6_000, PLAN_WINDOW_S));
    // Non-ellipsis status within 30 s fires once and clears the window.
    assert!(view.on_status("Nothing could fit.", 34_999, PLAN_WINDOW_S));
    assert!(!view.on_status("Another status.", 35_000, PLAN_WINDOW_S));

    // Past the 30 s window: clears without firing.
    assert_eq!(
        view.plan_one_target(&blocks, "b-placed", 10_000),
        Some("b-placed".to_string())
    );
    assert!(!view.on_status("Too late.", 40_000, PLAN_WINDOW_S));

    // on_planned clears the window.
    assert_eq!(
        view.plan_one_target(&blocks, "b-waiting", 50_000),
        Some("b-waiting".to_string())
    );
    view.on_planned();
    assert!(!view.on_status("Saved.", 51_000, PLAN_WINDOW_S));

    // Missing identifier returns None.
    assert_eq!(view.plan_one_target(&blocks, "nope", 60_000), None);
}

#[test]
fn toggle_done_and_save_finished_notice_lifecycle() {
    let mut view = WeekView::new();
    let assignments = json!({
        "essay": {"title": "History essay", "completed": false},
        "blank": {"title": "", "completed": true},
    });
    assert_eq!(view.toggle_done_plan(&assignments, "missing", false), None);
    assert_eq!(view.toggle_done_plan(&assignments, "essay", true), None);

    let finish = view.toggle_done_plan(&assignments, "essay", false).unwrap();
    assert_eq!(
        finish,
        ToggleDonePlan {
            finished: true,
            notice: "Finished History essay.".to_string(),
        }
    );
    view.record_done_after_save(finish.notice.clone(), false);
    assert_eq!(view.on_save_finished(true), None);

    view.record_done_after_save(finish.notice, true);
    assert_eq!(
        view.on_save_finished(true),
        Some("Finished History essay.".to_string())
    );
    assert_eq!(view.on_save_finished(true), None);

    let reopen = view.toggle_done_plan(&assignments, "blank", false).unwrap();
    assert_eq!(
        reopen,
        ToggleDonePlan {
            finished: false,
            notice: "Homework is back.".to_string(),
        }
    );
    view.record_done_after_save(reopen.notice, true);
    // Failed save clears the pending notice without showing it.
    assert_eq!(view.on_save_finished(false), None);
    assert_eq!(view.on_save_finished(true), None);
}

#[test]
fn toggle_weekends_handles_optimistic_flip_ticket_superseding_and_rollback() {
    let mut view = WeekView::new();

    // First toggle when show_weekends was absent: optimistic false, failure removes the key again.
    let first = view.toggle_weekends_start(&json!({"clock_24h": true}));
    assert_eq!(first.ticket, 1);
    assert!(!first.wanted);
    assert_eq!(
        first.preferences,
        json!({"clock_24h": true, "show_weekends": false})
    );

    let rollback = view
        .toggle_weekends_finish(
            first.ticket,
            false,
            &json!({"clock_24h": false, "show_weekends": false}),
        )
        .unwrap();
    assert_eq!(rollback.preferences, json!({"clock_24h": false}));
    assert_eq!(rollback.message, WEEKEND_SAVE_FAILED);

    // Explicit false -> optimistic true -> superseded by another toggle before first fails.
    let t2 = view.toggle_weekends_start(&json!({"show_weekends": false}));
    assert_eq!(t2.ticket, 2);
    assert!(t2.wanted);
    let t3 = view.toggle_weekends_start(&t2.preferences);
    assert_eq!(t3.ticket, 3);
    assert!(!t3.wanted);

    // Stale ticket 2 failing is ignored.
    assert_eq!(
        view.toggle_weekends_finish(t2.ticket, false, &t3.preferences),
        None
    );
    // Success on active ticket 3 does nothing.
    assert_eq!(
        view.toggle_weekends_finish(t3.ticket, true, &t3.preferences),
        None
    );
    // Failure on active ticket 3 restores explicit true from before t3.
    let rb3 = view
        .toggle_weekends_finish(t3.ticket, false, &t3.preferences)
        .unwrap();
    assert_eq!(rb3.preferences, json!({"show_weekends": true}));
}

#[test]
fn week_nav_state_queues_rapid_shifts_and_does_not_retry_failed_load() {
    let mut nav = WeekNavState::default();
    assert_eq!(nav.picker_anchor("2026-11-02"), "2026-11-02");

    // Step forward once: immediately flushes when idle.
    let next1 = nav.shift_target(7, "2026-11-02").unwrap().unwrap();
    assert_eq!(next1, "2026-11-09");
    assert!(nav.load_target(next1, false));
    assert_eq!(nav.picker_anchor("2026-11-02"), "2026-11-09");
    assert_eq!(
        nav.begin_flush("2026-11-02", false),
        Some("2026-11-09".to_string())
    );
    // Async load went busy: target & loading stay set.
    nav.finish_flush(true);
    assert_eq!(nav.loading_week.as_deref(), Some("2026-11-09"));
    // Load failed (week_start stayed 2026-11-02): settle clears target and does NOT retry!
    assert!(!nav.settle_navigation("2026-11-02", false));
    assert_eq!(nav.target_week, None);
    assert_eq!(nav.loading_week, None);

    // Rapid double next while busy: first starts 2026-11-09, second queues 2026-11-16.
    let first = nav.shift_target(7, "2026-11-02").unwrap().unwrap();
    assert!(nav.load_target(first, false));
    assert_eq!(
        nav.begin_flush("2026-11-02", false),
        Some("2026-11-09".to_string())
    );
    nav.finish_flush(true);
    let second = nav.shift_target(7, "2026-11-02").unwrap().unwrap();
    assert_eq!(second, "2026-11-16");
    assert!(!nav.load_target(second, true));
    // First settles -> still wants 2026-11-16 -> returns true to schedule singleShot flush!
    assert!(nav.settle_navigation("2026-11-02", false));
    assert_eq!(
        nav.begin_flush("2026-11-02", false),
        Some("2026-11-16".to_string())
    );
    // Sync load (stays not busy): clears both immediately.
    nav.finish_flush(false);
    assert_eq!(nav.target_week, None);
    assert_eq!(nav.loading_week, None);

    // Account change cancels any pending navigation.
    nav.load_target("2026-11-23".to_string(), true);
    nav.on_account_changed();
    assert_eq!(nav.target_week, None);
    assert_eq!(nav.loading_week, None);
    assert!(!nav.settle_navigation("2026-11-02", false));

    // Flushing to the already-open week clears target without loading.
    nav.load_target("2026-11-02".to_string(), false);
    assert_eq!(nav.begin_flush("2026-11-02", false), None);
    assert_eq!(nav.target_week, None);
}
