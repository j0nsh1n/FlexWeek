//! The hour decisions, pinned to the numbers the desktop tests and today's Python helpers use.

use flexweek_app::views::hours::{
    BlockWords, Frame, Lane, Moment, Pixel, Ring, WEEK_STARTS, accepted_week_start, dial_contains,
    dial_minute, dial_point, dial_turn, drag_step, end_after_start_words, homework_time_sentence,
    length_words, linear_contains, linear_minute_at, linear_point, linear_rect, nearest, next_slot,
    opening_minute, overdue_indexes, overlap_columns, plan_placed, read_clock, sanitize_zoom,
    scale_check, short_length, snap, span_minutes, step, tag_words, tail_words, track_length,
    week_start_day,
};

fn column() -> Frame {
    Frame {
        x: 50.0,
        y: 100.0,
        width: 200.0,
        height: 1020.0,
    }
}

fn lane_of(column: i64, columns: i64) -> Lane {
    Lane { column, columns }
}

fn block<'a>(
    done: bool,
    missed: bool,
    pinned: bool,
    history: &'a str,
    history_due: Option<&'a str>,
    placed_by_plan: bool,
) -> BlockWords<'a> {
    BlockWords {
        done,
        missed,
        pinned,
        history,
        history_due,
        placed_by_plan,
    }
}

fn moment(hour: i32, minute: i32, second: i32, micro: i32, day: i32) -> Moment {
    Moment {
        year: 2026,
        month: 10,
        day,
        hour,
        minute,
        second,
        micro,
    }
}

#[test]
fn snapping_rounds_halves_to_even() {
    assert_eq!(snap(7.5, 15).unwrap(), 0);
    assert_eq!(snap(22.5, 15).unwrap(), 30);
    assert_eq!(snap(37.5, 15).unwrap(), 30);
    assert_eq!(snap(0.5, 1).unwrap(), 0);
    assert_eq!(snap(1.5, 1).unwrap(), 2);
    assert_eq!(snap(2.5, 1).unwrap(), 2);
    assert_eq!(snap(3.5, 1).unwrap(), 4);
    assert_eq!(snap(-0.5, 1).unwrap(), 0);
    assert_eq!(snap(-1.5, 1).unwrap(), -2);
    assert_eq!(snap(-2.5, 1).unwrap(), -2);
    assert_eq!(
        [1147.0, 1148.0, 1152.4, 1153.0].map(|minute| snap(minute, 15).unwrap()),
        [1140, 1155, 1155, 1155]
    );
    assert_eq!(
        [1057.0, 1057.6, 1102.4, 1103.0].map(|minute| snap(minute, 5).unwrap()),
        [1055, 1060, 1100, 1105]
    );
    assert_eq!(snap(10.0, 0).unwrap_err().message, "division by zero");
}

#[test]
fn the_next_slot_rounds_up_and_rolls_to_tomorrow() {
    let cases = [
        (0, 0, 1425, 15, (0, 0)),
        (1, 0, 1425, 15, (0, 15)),
        (15, 0, 1425, 15, (0, 15)),
        (16 * 60 + 7, 0, 1425, 15, (0, 16 * 60 + 15)),
        (23 * 60 + 33, 0, 1425, 15, (0, 23 * 60 + 45)),
        (23 * 60 + 45, 0, 1425, 15, (0, 23 * 60 + 45)),
        (23 * 60 + 46, 0, 1425, 15, (1, 0)),
        (23 * 60 + 59, 0, 1425, 15, (1, 0)),
        (3 * 60 + 10, 6 * 60, 23 * 60, 15, (0, 6 * 60)),
        (23 * 60 + 1, 6 * 60, 23 * 60, 15, (1, 6 * 60)),
        (22 * 60 + 50, 6 * 60, 23 * 60, 15, (0, 23 * 60)),
        (-5, 0, 1425, 15, (0, 0)),
    ];
    for (minute, first, last, step_min, expect) in cases {
        assert_eq!(next_slot(minute, first, last, step_min).unwrap(), expect);
    }
    assert_eq!(
        next_slot(10, 0, 1425, 0).unwrap_err().message,
        "division by zero"
    );
}

#[test]
fn a_drag_step_is_five_or_fifteen() {
    assert_eq!(drag_step(Some(5)), 5);
    assert_eq!(drag_step(Some(15)), 15);
    assert_eq!(drag_step(Some(10)), 15);
    assert_eq!(drag_step(None), 15);
}

#[test]
fn overlapping_spans_share_a_width_and_a_touch_does_not() {
    assert_eq!(
        overlap_columns(&[(420, 480), (450, 510), (720, 750)]).unwrap(),
        vec![(0, 2), (1, 2), (0, 1)]
    );
    assert_eq!(
        overlap_columns(&[(480, 540), (480, 540)]).unwrap(),
        vec![(0, 2), (1, 2)]
    );
    assert_eq!(
        overlap_columns(&[(100, 200), (50, 80), (80, 90)]).unwrap(),
        vec![(0, 1), (0, 1), (0, 1)]
    );
    assert_eq!(
        overlap_columns(&[(10, 10)]).unwrap_err().message,
        "max() iterable argument is empty"
    );
    assert!(overlap_columns(&[]).unwrap().is_empty());
}

#[test]
fn a_column_reads_minutes_down_from_its_top_edge() {
    let frame = column();
    assert_eq!(
        linear_minute_at(frame, "down", 6 * 60, 23 * 60, 0.0, 120.0, 100.0).unwrap(),
        360.0
    );
    let frame = column();
    assert_eq!(
        linear_minute_at(
            frame,
            "down",
            6 * 60,
            23 * 60,
            0.0,
            120.0,
            100.0 + 13.0 * 60.0
        )
        .unwrap(),
        19.0 * 60.0
    );
    let frame = column();
    assert_eq!(
        linear_minute_at(frame, "down", 6 * 60, 23 * 60, 0.0, 120.0, 40.0).unwrap(),
        300.0
    );
    let frame = column();
    assert_eq!(
        linear_point(frame, "down", 6 * 60, 23 * 60, 0.0, 19 * 60).unwrap(),
        (150.0, 880.0)
    );
}

#[test]
fn a_lane_reads_minutes_across_from_its_left_edge() {
    let frame = Frame {
        x: 72.0,
        y: 10.0,
        width: 2040.0,
        height: 60.0,
    };
    assert_eq!(
        linear_minute_at(
            frame,
            "across",
            6 * 60,
            23 * 60,
            0.0,
            72.0 + 2.0 * 13.0 * 60.0,
            30.0
        )
        .unwrap(),
        19.0 * 60.0
    );
    let frame = Frame {
        x: 72.0,
        y: 10.0,
        width: 2040.0,
        height: 60.0,
    };
    assert_eq!(
        linear_point(frame, "across", 6 * 60, 23 * 60, 0.0, 12 * 60).unwrap(),
        (792.0, 40.0)
    );
}

#[test]
fn blocks_back_to_back_are_three_apart() {
    let alone = linear_rect(
        column(),
        "down",
        6 * 60,
        23 * 60,
        19 * 60,
        20 * 60,
        lane_of(0, 1),
    )
    .unwrap();
    assert_eq!((alone.y, alone.height), (100.0 + 13.0 * 60.0 + 1.0, 57.0));
    assert_eq!((alone.x, alone.width), (52.0, 194.0));
    let second = linear_rect(
        column(),
        "down",
        6 * 60,
        23 * 60,
        19 * 60,
        20 * 60,
        lane_of(1, 2),
    )
    .unwrap();
    assert_eq!((second.x, second.width), (150.0, 96.0));
    assert_eq!(second.height, 57.0);
}

#[test]
fn a_turned_card_reads_minutes_along_the_card() {
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1020.0,
    };
    let (x, y) = linear_point(frame, "down", 6 * 60, 23 * 60, 90.0, 6 * 60).unwrap();
    assert_eq!((x.round(), y.round()), (560.0, 510.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1020.0,
    };
    let minute = linear_minute_at(frame, "down", 6 * 60, 23 * 60, 90.0, 260.0, 510.0).unwrap();
    assert_eq!(minute.round(), 11.0 * 60.0);
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1020.0,
    };
    assert!(linear_contains(frame, 90.0, 300.0, 510.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1020.0,
    };
    assert!(!linear_contains(frame, 90.0, 50.0, 100.0));
}

#[test]
fn a_thirty_degree_card_matches_the_track_turn() {
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 20.0,
        height: 40.0,
    };
    let minute = linear_minute_at(
        frame,
        "down",
        0,
        40,
        30.0,
        5.980762113533167,
        86.96152422706632,
    )
    .unwrap();
    assert_eq!(minute, 80.0);
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 20.0,
        height: 40.0,
    };
    let (x, y) = linear_point(frame, "down", 0, 40, 30.0, 0).unwrap();
    assert_eq!(x, 20.0);
    assert!((y - 2.6794919243112245).abs() < 1e-9, "{y}");
}

#[test]
fn a_rectangle_keeps_every_edge() {
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(linear_contains(frame, 0.0, 0.0, 0.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(linear_contains(frame, 0.0, 100.0, 0.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(linear_contains(frame, 0.0, 0.0, 50.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(linear_contains(frame, 0.0, 100.0, 50.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(!linear_contains(frame, 0.0, -0.1, 0.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 50.0,
    };
    assert!(!linear_contains(frame, 0.0, 100.1, 0.0));
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 0.0,
        height: 50.0,
    };
    assert!(!linear_contains(frame, 0.0, 0.0, 0.0));
}

#[test]
fn a_midnight_track_puts_00_00_at_its_top_edge() {
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1440.0,
    };
    assert_eq!(
        linear_minute_at(frame, "down", 0, 1440, 0.0, 50.0, 0.0).unwrap(),
        0.0
    );
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 1440.0,
    };
    assert_eq!(
        linear_minute_at(frame, "down", 0, 1440, 0.0, 50.0, 1440.0).unwrap(),
        1440.0
    );
    let frame = Frame {
        x: 0.0,
        y: 0.0,
        width: 100.0,
        height: 10.0,
    };
    assert_eq!(
        linear_minute_at(frame, "down", 0, 0, 0.0, 0.0, 0.0)
            .unwrap_err()
            .message,
        "division by zero"
    );
}

#[test]
fn a_dial_reads_clockwise_from_the_top() {
    let ring = Ring {
        x: 100.0,
        y: 100.0,
        inner: 40.0,
        outer: 80.0,
        first: 0,
        last: 1440,
        sweep: 300.0,
    };
    let (x, y) = dial_point(&ring, 0).unwrap();
    assert_eq!(x, 70.0);
    assert!((y - 151.96152422706632).abs() < 1e-9, "{y}");
    assert_eq!(dial_minute(&ring, x, y).unwrap(), 0.0);
    assert!(dial_contains(&ring, x, y));
    let (x, y) = dial_point(&ring, 720).unwrap();
    assert_eq!((x, y), (100.0, 40.0));
    assert_eq!(dial_minute(&ring, 100.0, 40.0).unwrap(), 720.0);
    assert_eq!(dial_turn(&ring, 100.0, 40.0), 0.0);
    let (x, y) = dial_point(&ring, 1440).unwrap();
    assert_eq!(x, 130.0);
    assert!((y - 151.96152422706632).abs() < 1e-9, "{y}");
    assert!(!dial_contains(&ring, 100.0, 100.0));
    assert!(!dial_contains(&ring, 100.0, 0.0));
    assert_eq!(span_minutes(360, 420), 60);
    assert_eq!(track_length(200.0, 1020.0, "down").unwrap(), 1020.0);
    assert_eq!(track_length(2040.0, 60.0, "across").unwrap(), 2040.0);
}

#[test]
fn the_nearest_level_breaks_a_tie_toward_the_smaller_one() {
    let levels = [32, 44, 56, 72, 96, 128, 192, 256];
    assert_eq!(nearest(&levels, 56, Pixel::Number(50)).unwrap(), 44);
    assert_eq!(step(&levels, 56, Pixel::Number(50), 1).unwrap(), 56);
    assert_eq!(nearest(&levels, 56, Pixel::Number(60)).unwrap(), 56);
    assert_eq!(step(&levels, 56, Pixel::Number(60), 1).unwrap(), 72);
    assert_eq!(nearest(&levels, 56, Pixel::Absent).unwrap(), 56);
    assert_eq!(nearest(&levels, 56, Pixel::High).unwrap(), 256);
    assert_eq!(step(&levels, 56, Pixel::High, 1).unwrap(), 256);
    assert_eq!(nearest(&levels, 56, Pixel::Low).unwrap(), 32);
    assert_eq!(step(&levels, 56, Pixel::Low, 1).unwrap(), 44);
    assert_eq!(
        nearest(&[], 56, Pixel::Number(10)).unwrap_err(),
        "min() iterable argument is empty"
    );
    assert_eq!(nearest(&[], 56, Pixel::Absent).unwrap(), 56);
    assert_eq!(
        step(&[], 56, Pixel::Absent, 1).unwrap_err(),
        "tuple.index(x): x not in tuple"
    );
    assert_eq!(
        step(&levels, 7, Pixel::Absent, 1).unwrap_err(),
        "tuple.index(x): x not in tuple"
    );
    assert_eq!(
        scale_check("Bad").unwrap_err(),
        "'Bad' cannot be kept in the look file: use design.surface, a to z"
    );
    assert!(scale_check("design.surface").is_ok());
    assert!(scale_check(&format!("a.{}", "b".repeat(40))).is_err());
}

#[test]
fn another_day_opens_at_its_first_block() {
    let starts = [14 * 60, 16 * 60];
    let day_starts = [14 * 60];
    assert_eq!(
        opening_minute(Some(0), Some(9 * 60), Some(1), &starts, Some(&day_starts)),
        14 * 60
    );
}

#[test]
fn today_opens_at_now_and_an_empty_day_opens_at_eight() {
    assert_eq!(
        opening_minute(Some(0), Some(495), None, &[14 * 60], None),
        495
    );
    assert_eq!(
        opening_minute(Some(0), Some(500), Some(0), &[14 * 60], Some(&[14 * 60])),
        500
    );
    assert_eq!(
        opening_minute(Some(0), Some(500), Some(2), &[9 * 60], Some(&[])),
        480
    );
}

#[test]
fn a_week_without_now_opens_at_its_first_block() {
    assert_eq!(
        opening_minute(Some(0), None, None, &[9 * 60, 14 * 60], None),
        540
    );
    assert_eq!(
        opening_minute(None, Some(500), None, &[9 * 60, 14 * 60], None),
        540
    );
}

#[test]
fn a_short_length_does_not_look_like_a_clock() {
    assert_eq!(short_length(135), "2h 15m");
    assert_eq!(short_length(90), "1h 30m");
    assert_eq!(short_length(60), "1h");
    assert_eq!(short_length(45), "45 min");
    assert_eq!(short_length(0), "0 min");
    assert_eq!(short_length(-5), "0 min");
    assert_eq!(short_length(61), "1h 1m");
}

#[test]
fn remembered_zoom_keeps_thirty_two_named_levels() {
    let pairs = vec![
        (Some("design.surface".to_string()), Some(56)),
        (Some("nope".to_string()), Some(10)),
        (Some("a.b".to_string()), Some(8)),
        (Some("a.c".to_string()), Some(7)),
        (Some("a.d".to_string()), Some(481)),
        (None, Some(20)),
        (Some("a.e".to_string()), None),
        (Some("a.f".to_string()), Some(480)),
        (Some("A.b".to_string()), Some(40)),
        (Some("ab".to_string()), Some(40)),
    ];
    assert_eq!(
        sanitize_zoom(&pairs),
        vec![
            ("design.surface".to_string(), 56),
            ("a.b".to_string(), 8),
            ("a.f".to_string(), 480),
        ]
    );
    let many: Vec<_> = (0..40)
        .map(|index| {
            let key = format!(
                "n.{}{}",
                char::from(b'a' + index / 26),
                char::from(b'a' + index % 26)
            );
            (Some(key), Some(10))
        })
        .collect();
    let cleaned = sanitize_zoom(&many);
    assert_eq!(cleaned.len(), 32);
    assert_eq!(cleaned[0].0, "n.aa");
    assert_eq!(cleaned[31].0, "n.bf");
}

#[test]
fn a_written_clock_reads_the_same_on_either_face() {
    let cases = [
        ("15:15", false, true, Some(915)),
        ("1515", false, true, Some(915)),
        ("3:15 pm", false, true, Some(915)),
        ("3:15pm", false, true, Some(915)),
        ("315p", false, true, Some(915)),
        ("3 pm", false, true, None),
        ("3 pm", false, false, Some(900)),
        ("15", false, true, None),
        ("15", false, false, Some(900)),
        ("24:00", false, true, None),
        ("24:00", true, true, Some(1440)),
        ("00:00", false, true, Some(0)),
        ("00:00", true, true, Some(1440)),
        ("12:00 am", true, true, Some(1440)),
        ("12:00 pm", false, true, Some(720)),
        ("13:00 pm", false, true, None),
        ("0:00 am", false, true, None),
        ("0:30 am", false, true, None),
        ("15:60", false, true, None),
        ("24:30", true, true, None),
        ("3:15 p.m.", false, true, Some(915)),
        ("3 : 15", false, true, None),
        ("123", false, true, Some(83)),
        ("12345", false, false, None),
        ("9am", false, true, None),
        ("9am", false, false, Some(540)),
        ("  3:15 PM  ", false, true, Some(915)),
        ("3:15 p.", false, true, Some(915)),
        ("3:15pmx", false, true, None),
        ("", false, false, None),
        ("3:1", false, false, None),
        ("3:", false, false, None),
        ("09:05", false, true, Some(545)),
        ("9:05 am", false, true, Some(545)),
        ("12:30 PM", false, true, Some(750)),
        ("24:00pm", true, true, None),
        ("1:00 a.m.", false, true, Some(60)),
        ("25:00", false, true, None),
        ("23:59", false, true, Some(1439)),
        ("12am", false, false, Some(0)),
        ("12am", true, false, Some(1440)),
        ("3:15 a", false, true, Some(195)),
        ("115", false, true, Some(75)),
        (" 9 ", false, false, Some(540)),
    ];
    for (text, end, whole, expect) in cases {
        assert_eq!(
            read_clock(text, end, whole),
            expect,
            "{text} end={end} whole={whole}"
        );
    }
}

#[test]
fn a_week_start_outside_the_seven_days_is_monday() {
    assert_eq!(accepted_week_start(Some("sunday")), "sunday");
    assert_eq!(accepted_week_start(Some("someday")), "monday");
    assert_eq!(accepted_week_start(None), "monday");
    assert_eq!(week_start_day("sunday"), 6);
    assert_eq!(week_start_day("monday"), 0);
    assert_eq!(
        WEEK_STARTS[week_start_day("wednesday") as usize],
        "wednesday"
    );
}

#[test]
fn a_block_says_its_length_its_tags_and_when_it_was_due() {
    assert!(plan_placed(true, false, false, false));
    assert!(!plan_placed(true, true, false, false));
    assert!(!plan_placed(true, false, true, false));
    assert_eq!(tag_words("Overdue", false), vec!["Overdue".to_string()]);
    assert_eq!(
        tag_words("Left from last week", true),
        vec![
            "Left from last week".to_string(),
            "Placed by Plan".to_string()
        ]
    );
    assert!(tag_words("", false).is_empty());
    assert_eq!(length_words(60, false, false), "1 h");
    assert_eq!(length_words(60, true, true), "1 h · Finished · Missed");
    assert_eq!(length_words(-30, false, false), "0 min");
    let overdue = block(false, false, true, "Overdue", Some("2026-10-15"), false);
    assert_eq!(
        tail_words("15:15–16:15 · 1 h", overdue),
        "15:15–16:15 · 1 h · Overdue, was due Thu 15 Oct · Pinned"
    );
    let bad = block(false, false, false, "Overdue", Some("not-a-date"), false);
    assert_eq!(tail_words("x", bad), "x · Overdue");
    let empty_due = block(true, false, true, "Overdue", Some(""), false);
    assert_eq!(tail_words("x", empty_due), "x · Overdue");
    let detail = block(
        false,
        false,
        true,
        "Overdue",
        Some("2026-10-15T15:00"),
        false,
    );
    assert_eq!(
        flexweek_app::views::hours::detail_words(15 * 60 + 15, 16 * 60 + 15, detail),
        "15:15–16:15 · 1 h · Overdue, was due Thu 15 Oct · Pinned"
    );
}

#[test]
fn an_end_that_is_not_later_names_the_start() {
    assert_eq!(
        end_after_start_words("3:30 PM"),
        "End needs to be later than Start (3:30 PM)."
    );
}

#[test]
fn homework_that_still_needs_a_time_says_so() {
    let left = r#"[{"left_over_state":"overdue"},{"left_over_state":"left_from_last_week"}]"#;
    let needed = r#"[{"assignment_id":1,"minutes":45}]"#;
    assert_eq!(
        homework_time_sentence(left, needed).unwrap(),
        "1 overdue · 1 left from last week · 45 min still needs a time"
    );
    assert_eq!(
        homework_time_sentence("[]", "[]").unwrap(),
        "Everything has a time."
    );
    assert_eq!(
        homework_time_sentence(r#"[{"left_over_state":"overdue"}]"#, "[]").unwrap(),
        "1 overdue"
    );
    let split = r#"[{"assignment_id":1,"minutes":90,"missed_min":60,"pinned_min":30}]"#;
    assert_eq!(
        homework_time_sentence("[]", split).unwrap(),
        "1 h missed · 30 min pinned, in the past"
    );
    let replaced = r#"[{"assignment_id":1,"minutes":15},{"assignment_id":1,"minutes":45}]"#;
    assert_eq!(
        homework_time_sentence("[]", replaced).unwrap(),
        "45 min still needs a time"
    );
    let distinct = r#"[{"assignment_id":1,"minutes":15},{"assignment_id":"1","minutes":30}]"#;
    assert_eq!(
        homework_time_sentence("[]", distinct).unwrap(),
        "45 min still needs a time"
    );
    assert_eq!(
        homework_time_sentence("[]", r#"[{"assignment_id":"a","minutes":-20}]"#).unwrap(),
        "0 min still needs a time"
    );
}

#[test]
fn a_deadline_is_overdue_once_its_minute_has_arrived() {
    let dues = [
        Some("2026-10-15"),
        Some("2026-10-15T15:00"),
        Some(""),
        None,
        Some("nope"),
        Some("2026-10-15T00:00"),
    ];
    let ids = |now: &Moment| overdue_indexes(&dues, now);
    assert_eq!(ids(&moment(23, 59, 0, 0, 15)), vec![1, 5]);
    assert_eq!(ids(&moment(0, 0, 0, 0, 16)), vec![0, 1, 5]);
    assert_eq!(ids(&moment(15, 0, 0, 0, 15)), vec![1, 5]);
    assert_eq!(ids(&moment(14, 59, 59, 999_999, 15)), vec![5]);
    assert_eq!(ids(&moment(0, 0, 0, 0, 15)), vec![5]);
}
