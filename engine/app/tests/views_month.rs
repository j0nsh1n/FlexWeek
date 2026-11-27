//! Tests for Month cells and the Material Month screen view-model (`views::month`, P5-M1).
//!
//! Expected dates and wording come from the calendar (1 November 2026 is a Sunday; 1 February 2027
//! is a Monday) and the pinning desktop tests, not from running the code under test.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::month::{
    ActivatePlan, MonthChip, MonthView, OpenOccurrence, OpenWeek, ShiftPlan, access_name,
    activate_plan, build_rows, cell_row, chip_carried, chip_flag, chip_kind, chip_words,
    day_number, go_to_date_month, heading, month_cells, pane_line, picker_anchor, prepare_read,
    shift_plan, study_share, today_month, weekday_names,
};
use flexweek_engine::ErrorKind;
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

// `set_clock_24h` flips a process-wide atomic in `flexweek_engine::desk::weekmodel`.
static CLOCK_LOCK: Mutex<()> = Mutex::new(());

fn with_clock(clock_24h: bool) -> MutexGuard<'static, ()> {
    let guard = CLOCK_LOCK.lock().expect("clock lock");
    set_clock_24h(clock_24h);
    guard
}

fn snapshot(month: &str, days: Vec<Value>, deadlines: Vec<Value>, overdue: Vec<Value>) -> Value {
    json!({
        "month": month,
        "days": days,
        "deadlines": deadlines,
        "overdue": overdue,
    })
}

fn deadlines_snapshot() -> Value {
    snapshot(
        "2026-11",
        vec![
            json!({"date": "2026-11-05", "in_month": true, "due_ids": ["essay", "oral"]}),
            json!({"date": "2026-11-03", "in_month": true, "due_ids": ["late"]}),
            json!({
                "date": "2026-11-06",
                "in_month": true,
                "blocks": [{"id": "school", "title": "School", "start": "08:00", "duration_min": 390}],
            }),
        ],
        vec![
            json!({"id": "essay", "title": "History essay", "category": "assignments", "due": "2026-11-05T19:00"}),
            json!({"id": "oral", "title": "French oral", "category": "assignments", "due": "2026-11-05"}),
        ],
        vec![
            json!({"id": "late", "title": "Reading", "category": "assignments", "due": "2026-11-03"}),
        ],
    )
}

fn find_row<'a>(rows: &'a [Value], iso: &str) -> &'a Value {
    rows.iter()
        .find(|row| row["iso"].as_str() == Some(iso))
        .unwrap_or_else(|| panic!("missing row for {iso}"))
}

fn chips_of(row: &Value) -> Vec<Value> {
    let text = row["chipsJson"].as_str().expect("chipsJson string");
    serde_json::from_str(text).expect("valid chipsJson")
}

#[test]
fn grid_runs_from_the_week_start_across_month_edges() {
    let _guard = with_clock(false);
    // 1 Nov 2026 is a Sunday, 30 Nov a Monday; 1 Dec 2026 is a Tuesday; 1 Feb 2027 is a Monday.
    let cases = [
        (
            "2026-11",
            0_u32,
            "Mon",
            "2026-10-26",
            "2026-12-06",
            42_usize,
            30_usize,
        ),
        (
            "2026-11",
            6_u32,
            "Sun",
            "2026-11-01",
            "2026-12-05",
            35_usize,
            30_usize,
        ),
        (
            "2026-12",
            0_u32,
            "Mon",
            "2026-11-30",
            "2027-01-03",
            35_usize,
            31_usize,
        ),
        (
            "2026-12",
            6_u32,
            "Sun",
            "2026-11-29",
            "2027-01-02",
            35_usize,
            31_usize,
        ),
        (
            "2027-02",
            0_u32,
            "Mon",
            "2027-02-01",
            "2027-02-28",
            28_usize,
            28_usize,
        ),
        (
            "2027-02",
            6_u32,
            "Sun",
            "2027-01-31",
            "2027-03-06",
            35_usize,
            28_usize,
        ),
        (
            "2026-11",
            2_u32,
            "Wed",
            "2026-10-28",
            "2026-12-01",
            35_usize,
            30_usize,
        ),
        (
            "2026-11",
            5_u32,
            "Sat",
            "2026-10-31",
            "2026-12-04",
            35_usize,
            30_usize,
        ),
        (
            "2026-12",
            2_u32,
            "Wed",
            "2026-11-25",
            "2027-01-05",
            42_usize,
            31_usize,
        ),
        (
            "2026-12",
            5_u32,
            "Sat",
            "2026-11-28",
            "2027-01-01",
            35_usize,
            31_usize,
        ),
    ];

    for (month, first_weekday, first_name, first_iso, last_iso, count, inside_count) in cases {
        let snap = snapshot(month, vec![], vec![], vec![]);
        let rows = build_rows(&snap, &[], "2026-11-02", Some(month), first_weekday).unwrap();
        let names = weekday_names(first_weekday).unwrap();
        assert_eq!(rows.len(), count, "{month} start={first_weekday}");
        assert_eq!(rows.first().unwrap()["iso"], first_iso);
        assert_eq!(rows.last().unwrap()["iso"], last_iso);
        assert_eq!(names.len(), 7);
        assert_eq!(names[0], first_name);
        let inside: Vec<&str> = rows
            .iter()
            .filter(|row| row["inMonth"].as_bool() == Some(true))
            .map(|row| row["iso"].as_str().unwrap())
            .collect();
        assert_eq!(inside.len(), inside_count);
        assert_eq!(inside[0], format!("{month}-01"));
    }
}

#[test]
fn weekday_names_reject_out_of_range_weekday() {
    assert!(weekday_names(7).is_err());
    assert_eq!(
        weekday_names(6).unwrap(),
        vec!["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    );
    assert_eq!(
        weekday_names(2).unwrap(),
        vec!["Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]
    );
}

#[test]
fn prepare_read_stays_empty_until_signed_in_and_month_open() {
    let _guard = with_clock(true);
    let signed_out = prepare_read(
        false,
        &json!({"clock_24h": false}),
        None,
        Some("2026-11"),
        &Value::Null,
        &Value::Null,
        Some("2026-11-02"),
        0,
    )
    .unwrap();
    assert_eq!(signed_out.clock_24h, None);
    assert!(!signed_out.ready);
    assert_eq!(signed_out.weekday_names[0], "Mon");

    let no_month = prepare_read(
        true,
        &json!({"clock_24h": false}),
        None,
        None,
        &Value::Null,
        &Value::Null,
        Some("2026-11-02"),
        0,
    )
    .unwrap();
    assert_eq!(no_month.clock_24h, Some(false));
    assert!(!no_month.ready);
    assert!(!no_month.include_built_week);

    // A snapshot belonging to a different month is discarded, while the chosen month still builds a grid.
    let mismatch = prepare_read(
        true,
        &json!({"clock_24h": true}),
        Some("2026-12"),
        Some("2026-11"),
        &Value::Null,
        &snapshot("2026-11", vec![], vec![], vec![]),
        Some("2026-11-02"),
        0,
    )
    .unwrap();
    assert!(mismatch.ready);
    assert_eq!(mismatch.chosen_month.as_deref(), Some("2026-12"));
    assert!(mismatch.chosen_snapshot.is_null());
    assert!(mismatch.include_built_week);
}

#[test]
fn today_and_quiet_days_carry_markers_and_access_names() {
    let _guard = with_clock(false);
    let snap = snapshot("2026-11", vec![], vec![], vec![]);
    let rows = build_rows(&snap, &[], "2026-11-02", Some("2026-11"), 0).unwrap();
    let today_rows: Vec<&str> = rows
        .iter()
        .filter(|row| row["today"].as_bool() == Some(true))
        .map(|row| row["iso"].as_str().unwrap())
        .collect();
    assert_eq!(today_rows, vec!["2026-11-02"]);
    assert_eq!(find_row(&rows, "2026-10-31")["inMonth"], false);
    assert_eq!(find_row(&rows, "2026-11-01")["inMonth"], true);
    assert_eq!(
        find_row(&rows, "2026-11-02")["accessName"],
        "Monday 2 November, today"
    );
    assert_eq!(
        find_row(&rows, "2026-10-31")["accessName"],
        "Saturday 31 October, not in this month"
    );
    assert_eq!(
        access_name("2026-10-31", true, false).unwrap(),
        "Saturday 31 October, today, not in this month"
    );
}

#[test]
fn chips_follow_12h_and_24h_clocks() {
    let _guard = with_clock(false);
    let rows_12 = build_rows(&deadlines_snapshot(), &[], "2026-11-04", Some("2026-11"), 0).unwrap();
    let nov5_12 = chips_of(find_row(&rows_12, "2026-11-05"));
    assert_eq!(
        nov5_12
            .iter()
            .map(|c| c["text"].as_str().unwrap())
            .collect::<Vec<_>>(),
        vec!["Due 7:00 PM History essay", "Due French oral"]
    );
    assert_eq!(
        nov5_12
            .iter()
            .map(|c| c["kind"].as_str().unwrap())
            .collect::<Vec<_>>(),
        vec!["due", "due"]
    );
    let nov6_12 = chips_of(find_row(&rows_12, "2026-11-06"));
    assert_eq!(nov6_12[0]["text"], "8:00 AM School");
    assert_eq!(nov6_12[0]["kind"], "plain");

    set_clock_24h(true);
    let rows_24 = build_rows(&deadlines_snapshot(), &[], "2026-11-04", Some("2026-11"), 0).unwrap();
    assert_eq!(
        chips_of(find_row(&rows_24, "2026-11-05"))[0]["text"],
        "Due 19:00 History essay"
    );
    assert_eq!(
        chips_of(find_row(&rows_24, "2026-11-06"))[0]["text"],
        "08:00 School"
    );
}

#[test]
fn the_open_week_is_read_from_what_the_student_has_now_not_from_the_reply() {
    let _guard = with_clock(true);
    let reply = snapshot(
        "2026-11",
        vec![
            json!({
                "date": "2026-11-05",
                "in_month": true,
                "blocks": [{"id": "essay-1", "title": "History essay", "start": "19:00", "duration_min": 60}],
            }),
            json!({
                "date": "2026-11-12",
                "in_month": true,
                "blocks": [{"id": "piano", "title": "Piano", "start": "18:00", "duration_min": 45}],
            }),
        ],
        vec![],
        vec![],
    );
    // The student moved the essay to 20:15 in the open week without saving; the reply still says 19:00.
    let open = vec![OpenWeek {
        week_start: "2026-11-02".to_string(),
        occurrences: vec![OpenOccurrence {
            block_id: "essay-1".to_string(),
            title: "History essay".to_string(),
            category: "homework".to_string(),
            day: 3,
            start: 20 * 60 + 15,
            end: 21 * 60 + 15,
            done: false,
            history: String::new(),
        }],
    }];
    let rows = build_rows(&reply, &open, "2026-11-02", Some("2026-11"), 0).unwrap();
    assert_eq!(
        chips_of(find_row(&rows, "2026-11-05"))
            .iter()
            .map(|c| c["text"].as_str().unwrap())
            .collect::<Vec<_>>(),
        vec!["20:15 History essay"]
    );
    assert_eq!(
        chips_of(find_row(&rows, "2026-11-12"))
            .iter()
            .map(|c| c["text"].as_str().unwrap())
            .collect::<Vec<_>>(),
        vec!["18:00 Piano"]
    );
}

#[test]
fn overdue_and_finished_deadlines_follow_date_and_completion() {
    let _guard = with_clock(false);
    let rows_after =
        build_rows(&deadlines_snapshot(), &[], "2026-11-04", Some("2026-11"), 0).unwrap();
    let chip_after = &chips_of(find_row(&rows_after, "2026-11-03"))[0];
    assert_eq!(chip_after["text"], "Overdue Reading");
    assert_eq!(chip_after["kind"], "overdue");

    let rows_same =
        build_rows(&deadlines_snapshot(), &[], "2026-11-03", Some("2026-11"), 0).unwrap();
    let chip_same = &chips_of(find_row(&rows_same, "2026-11-03"))[0];
    assert_eq!(chip_same["text"], "Due Reading");
    assert_eq!(chip_same["kind"], "due");

    let mut finished = deadlines_snapshot();
    finished["overdue"][0]["completed"] = json!(true);
    let rows_done = build_rows(&finished, &[], "2026-11-04", Some("2026-11"), 0).unwrap();
    let chip_done = &chips_of(find_row(&rows_done, "2026-11-03"))[0];
    assert_eq!(chip_done["text"], "Due Reading");
    assert_eq!(chip_done["kind"], "due");
}

#[test]
fn study_time_shares_and_date_bar_totals_count_homework_sessions() {
    let _guard = with_clock(false);
    let snap = snapshot(
        "2026-11",
        vec![json!({
            "date": "2026-11-04",
            "in_month": true,
            "blocks": [
                {
                    "id": "a",
                    "title": "Essay",
                    "start": "18:00",
                    "duration_min": 60,
                    "assignment_id": "essay",
                    "completed": true,
                },
                {
                    "id": "b",
                    "title": "Maths",
                    "start": "19:30",
                    "duration_min": 120,
                    "assignment_id": "maths",
                },
                {
                    "id": "c",
                    "title": "School",
                    "category": "class",
                    "start": "08:00",
                    "duration_min": 390,
                },
            ],
        })],
        vec![],
        vec![],
    );
    let rows = build_rows(&snap, &[], "2026-11-02", Some("2026-11"), 0).unwrap();
    let row = find_row(&rows, "2026-11-04");
    assert_eq!(row["plannedMin"], 180);
    assert_eq!(row["completedMin"], 60);
    assert!((row["plannedShare"].as_f64().unwrap() - 1.0).abs() < 1e-9);
    assert!((row["completedShare"].as_f64().unwrap() - (60.0 / 180.0)).abs() < 1e-9);
    let lines: Vec<&str> = row["lines"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();
    assert_eq!(
        lines,
        vec![
            "8:00 AM School · 6 h 30 min",
            "✓ 6:00 PM Essay · 1 h",
            "7:30 PM Maths · 2 h",
            "3 h homework planned · 1 h completed",
        ]
    );
    assert_eq!(study_share(0), 0.0);
    assert_eq!(study_share(-10), 0.0);
    assert_eq!(study_share(360), 1.0);
}

#[test]
fn chip_helpers_and_pane_line_cover_history_and_carried_rules() {
    let _guard = with_clock(true);
    assert!(chip_carried(Some("b1"), Some(480), false));
    assert!(!chip_carried(None, Some(480), false));
    assert!(!chip_carried(Some("b1"), None, false));
    assert!(!chip_carried(Some("b1"), Some(480), true));

    assert_eq!(
        chip_flag("Left from last week", false, false, None).unwrap(),
        "Left from last week"
    );
    assert_eq!(chip_flag("", false, false, None).unwrap(), "");
    assert_eq!(chip_flag("", true, true, Some("19:00")).unwrap(), "Overdue");
    assert_eq!(
        chip_flag("", true, false, Some("19:00")).unwrap(),
        "Due 19:00"
    );
    assert_eq!(chip_flag("", true, false, None).unwrap(), "Due");

    assert_eq!(
        chip_words(
            "Essay",
            Some(9 * 60),
            false,
            false,
            None,
            "Left from last week"
        )
        .unwrap(),
        "Left from last week 09:00 Essay"
    );
    assert_eq!(
        chip_words("Essay", None, true, false, Some("19:00"), "").unwrap(),
        "Due 19:00 Essay"
    );
    assert_eq!(
        chip_words("School", Some(8 * 60), false, false, None, "").unwrap(),
        "08:00 School"
    );

    let history_chip = MonthChip {
        key: "block:b1".to_string(),
        title: "Essay".to_string(),
        category: "homework".to_string(),
        block_id: Some("b1".to_string()),
        start: Some(9 * 60),
        minutes: 60,
        due: false,
        due_time: None,
        done: true,
        late: false,
        history: "Left from last week".to_string(),
    };
    assert_eq!(
        pane_line(&history_chip).unwrap(),
        "Left from last week 09:00 Essay"
    );
    assert_eq!(chip_kind(true, true), "overdue");
    assert_eq!(chip_kind(true, false), "due");
    assert_eq!(chip_kind(false, false), "plain");
    assert_eq!(day_number("2026-11-05").unwrap(), 5);
    assert!(day_number("bad").is_err());
    assert_eq!(heading("2026-11-05").unwrap(), "Thursday 5 November");
}

#[test]
fn month_cells_infers_month_from_days_and_sorts_blocks_stably() {
    let _guard = with_clock(true);
    let snap = json!({
        "days": [
            {
                "date": "2026-11-05",
                "in_month": true,
                "blocks": [
                    {"id": "b2", "title": "Zebra", "start": "09:00", "duration_min": 30},
                    {"id": "b1", "title": "Alpha", "start": "09:00", "duration_min": 45},
                    {"id": "bad", "title": "Skip", "start": "9:00", "duration_min": 30},
                    {"id": "b0", "title": "Early", "start": "08:00", "duration_min": 60},
                ],
            }
        ]
    });
    let cells = month_cells(&snap, &[], "2026-11-02", None, 0).unwrap();
    assert_eq!(cells.len(), 42);
    let nov5 = cells.iter().find(|c| c.iso == "2026-11-05").unwrap();
    let titles: Vec<&str> = nov5.chips.iter().map(|c| c.title.as_str()).collect();
    assert_eq!(titles, vec!["Early", "Alpha", "Zebra"]);
    let row = cell_row(nov5).unwrap();
    assert_eq!(row["day"], 5);
}

#[test]
fn month_view_selection_date_bar_and_navigation_state() {
    let _guard = with_clock(false);
    let mut view = MonthView::new();
    let plan = view
        .prepare_reload(
            true,
            &json!({"clock_24h": false}),
            Some("2026-11"),
            &deadlines_snapshot(),
            Some(""),
            0,
        )
        .unwrap();
    assert!(plan.ready);
    assert!(!plan.include_built_week);
    view.finish_reload(&[], "2026-11-04").unwrap();

    assert_eq!(view.snapshot()["barOpen"], false);
    assert!(view.select_date("2026-11-05"));
    assert_eq!(view.snapshot()["barOpen"], true);
    assert_eq!(view.selected, "2026-11-05");
    assert_eq!(view.heading, "Thursday 5 November");
    assert_eq!(view.lines.len(), 2);
    assert_eq!(view.open_day_target().as_deref(), Some("2026-11-05"));

    // Selecting the same date closes the bar; unknown dates are ignored.
    assert!(view.select_date("2026-11-05"));
    assert_eq!(view.snapshot()["barOpen"], false);
    assert_eq!(view.open_day_target(), None);
    assert!(!view.select_date("2030-01-01"));

    // Empty date says "Nothing planned".
    assert!(view.select_date("2026-11-10"));
    assert_eq!(view.heading, "Tuesday 10 November");
    assert_eq!(view.lines, vec!["Nothing planned"]);

    // Switching to another month closes a date that left the grid.
    view.prepare_reload(
        true,
        &json!({"clock_24h": false}),
        Some("2027-02"),
        &snapshot("2027-02", vec![], vec![], vec![]),
        Some(""),
        0,
    )
    .unwrap();
    view.finish_reload(&[], "2026-11-04").unwrap();
    assert_eq!(view.snapshot()["barOpen"], false);
    assert_eq!(view.cell_rows[0]["iso"], "2027-02-01");

    // Study time switch toggles only on change.
    assert!(!view.show_study);
    assert!(view.set_show_study_time(true));
    assert!(!view.set_show_study_time(true));
    assert!(view.show_study);
    assert!(view.set_show_study_time(false));
    assert!(!view.show_study);

    // Close date returns false when already closed.
    assert!(!view.close_date());
    assert!(view.select_date("2027-02-05"));
    assert!(view.close_date());
    assert_eq!(view.snapshot()["barOpen"], false);
}

#[test]
fn month_navigation_helpers_match_bridge_rules() {
    assert_eq!(picker_anchor(Some("2026-12"), "2026-11-04"), "2026-12-01");
    assert_eq!(picker_anchor(None, "2026-11-04"), "2026-11-01");
    assert_eq!(picker_anchor(Some(""), "2026-11-04"), "2026-11-01");

    assert_eq!(
        go_to_date_month("2026-12-15", true).as_deref(),
        Some("2026-12")
    );
    assert_eq!(go_to_date_month("not-a-date", true), None);
    assert_eq!(go_to_date_month("2026-12-15", false), None);

    assert_eq!(today_month(true, "2026-11-04").as_deref(), Some("2026-11"));
    assert_eq!(today_month(false, "2026-11-04"), None);
    assert_eq!(today_month(true, "1995-05-01").as_deref(), Some("2000-01"));

    assert_eq!(
        activate_plan(false, "week"),
        ActivatePlan {
            open_month: false,
            reload: false
        }
    );
    assert_eq!(
        activate_plan(true, "week"),
        ActivatePlan {
            open_month: true,
            reload: false
        }
    );
    assert_eq!(
        activate_plan(true, "month"),
        ActivatePlan {
            open_month: false,
            reload: true
        }
    );

    assert_eq!(shift_plan(false, "month", 1), None);
    assert_eq!(
        shift_plan(true, "month", 1),
        Some(ShiftPlan {
            open_month: false,
            amount: 1
        })
    );
    assert_eq!(
        shift_plan(true, "week", -1),
        Some(ShiftPlan {
            open_month: true,
            amount: -1
        })
    );
}

#[test]
fn open_week_empty_day_clears_reply_and_later_week_overlay_wins() {
    let _guard = with_clock(true);
    let reply = snapshot(
        "2026-11",
        vec![json!({
            "date": "2026-11-05",
            "in_month": true,
            "blocks": [{"id": "old", "title": "Stale", "start": "17:00", "duration_min": 60}],
        })],
        vec![],
        vec![],
    );
    // Unsaved open week has one occurrence on Thursday; built week for the same week clears it.
    let open = vec![
        OpenWeek {
            week_start: "2026-11-02".to_string(),
            occurrences: vec![OpenOccurrence {
                block_id: "unsaved".to_string(),
                title: "Earlier".to_string(),
                category: "homework".to_string(),
                day: 3,
                start: 18 * 60,
                end: 19 * 60,
                done: false,
                history: String::new(),
            }],
        },
        OpenWeek {
            week_start: "2026-11-02".to_string(),
            occurrences: vec![],
        },
    ];
    let rows = build_rows(&reply, &open, "2026-11-02", Some("2026-11"), 0).unwrap();
    let nov5 = find_row(&rows, "2026-11-05");
    assert!(chips_of(nov5).is_empty());
    assert_eq!(nov5["plannedMin"], 0);
    assert_eq!(nov5["lines"], json!(["Nothing planned"]));
}

#[test]
fn due_2359_omits_clock_and_zero_completed_renders_summary_and_categories() {
    let _guard = with_clock(false);
    let snap = snapshot(
        "2026-11",
        vec![
            json!({"date": "2026-11-08", "in_month": true, "due_ids": ["essay", "missing-id"]}),
            json!({
                "date": "2026-11-09",
                "in_month": true,
                "blocks": [
                    {
                        "id": "hw1",
                        "title": "Lab",
                        "start": "16:00",
                        "duration_min": 60,
                        "assignment_id": "lab",
                    },
                    {
                        "id": "misc",
                        "title": "Walk",
                        "category": "custom-unknown",
                        "start": "17:30",
                        "duration_min": 30,
                    },
                ],
            }),
        ],
        vec![json!({
            "id": "essay",
            "title": "History essay",
            "category": "assignments",
            "due": "2026-11-08T23:59",
        })],
        vec![],
    );
    let rows = build_rows(&snap, &[], "2026-11-05", Some("2026-11"), 0).unwrap();
    let nov8_chips = chips_of(find_row(&rows, "2026-11-08"));
    assert_eq!(nov8_chips[0]["text"], "Due History essay");
    assert_eq!(nov8_chips[0]["category"], "assignments");
    assert_eq!(nov8_chips[1]["text"], "Due missing-id");
    assert_eq!(nov8_chips[1]["category"], "assignments");

    let nov9 = find_row(&rows, "2026-11-09");
    let nov9_chips = chips_of(nov9);
    assert_eq!(nov9_chips[0]["category"], "assignments");
    assert_eq!(nov9_chips[1]["category"], "other");
    assert_eq!(
        nov9["lines"],
        json!([
            "4:00 PM Lab · 1 h",
            "5:30 PM Walk · 30 min",
            "1 h homework planned · 0 completed",
        ])
    );
}

#[test]
fn sign_out_reload_clears_selection_and_rows_while_updating_weekdays() {
    let _guard = with_clock(false);
    let mut view = MonthView::new();
    view.prepare_reload(
        true,
        &json!({"clock_24h": false}),
        Some("2026-11"),
        &deadlines_snapshot(),
        None,
        0,
    )
    .unwrap();
    view.finish_reload(&[], "2026-11-04").unwrap();
    assert!(view.select_date("2026-11-05"));
    assert_eq!(view.snapshot()["barOpen"], true);

    let plan = view
        .prepare_reload(false, &Value::Null, Some("2026-11"), &Value::Null, None, 6)
        .unwrap();
    assert!(!plan.ready);
    assert!(view.cell_rows.is_empty());
    assert!(view.date_rows.is_empty());
    assert!(view.selected.is_empty());
    assert!(view.heading.is_empty());
    assert!(view.lines.is_empty());
    assert_eq!(view.weekday_names[0], "Sun");
}

#[test]
fn month_cells_rejects_wrong_shaped_inputs() {
    let _guard = with_clock(true);
    let array_err = month_cells(&json!([]), &[], "2026-11-02", Some("2026-11"), 0).unwrap_err();
    assert_eq!(array_err.kind, ErrorKind::Value);

    let bad_duration = snapshot(
        "2026-11",
        vec![json!({
            "date": "2026-11-05",
            "in_month": true,
            "blocks": [{"id": "b1", "title": "Bad", "start": "09:00", "duration_min": {"x": 1}}],
        })],
        vec![],
        vec![],
    );
    let type_err = month_cells(&bad_duration, &[], "2026-11-02", Some("2026-11"), 0).unwrap_err();
    assert_eq!(type_err.kind, ErrorKind::Type);

    let bad_day = month_cells(
        &snapshot("2026-11", vec![], vec![], vec![]),
        &[],
        "2026-11-02",
        Some("2026-11"),
        7,
    )
    .unwrap_err();
    assert_eq!(bad_day.kind, ErrorKind::Value);
}
