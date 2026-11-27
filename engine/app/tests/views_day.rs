//! Material Day and My day view-model (P5-D1), pinned to the desktop Day tests and the rules
//! `day_board.py` and `bridge_day.py` held before the move. Expected values come from those rules and
//! from the clock set in each test, not from what the code prints.

use std::collections::HashSet;
use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::day::{
    BeginInput, BoardInput, DayBoard, DayItem, DayView, FinishInput, FocusHooks, LOAD_FAILED,
    SAVING_FIRST, TimerWords, WeekLookups, board_for, finish_plan, finish_refreshes, focus_ended,
    read_flag, timer_words, waiting_for_a_time,
};
use flexweek_app::views::week::OccurrenceInput;
use flexweek_engine::EngineResult;
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

static CLOCK_LOCK: Mutex<()> = Mutex::new(());

fn clock(twenty_four: bool) -> MutexGuard<'static, ()> {
    let guard = CLOCK_LOCK
        .lock()
        .unwrap_or_else(|poison| poison.into_inner());
    set_clock_24h(twenty_four);
    guard
}

// Thursday 2026-11-05 is the day under test; the Day tests' fake clock starts there.
const TODAY: &str = "2026-11-05";
const SCHOOL: (i64, i64) = (8 * 60, 12 * 60);
const ESSAY: (i64, i64) = (18 * 60 + 45, 19 * 60 + 45);
const SOCCER: (i64, i64) = (16 * 60, 17 * 60 + 30);

fn block(title: &str, span: (i64, i64)) -> DayItem {
    DayItem {
        base: OccurrenceInput {
            block_id: title.to_lowercase().replace(' ', "-"),
            title: title.to_string(),
            category: "class".to_string(),
            day: 3,
            start: span.0,
            end: span.1,
            work: false,
            done: false,
            assignment_id: String::new(),
        },
        missed: false,
        pinned: false,
        due: None,
        slack: None,
    }
}

fn homework(title: &str, span: (i64, i64), assignment: &str) -> DayItem {
    let mut item = block(title, span);
    item.base.work = true;
    item.base.assignment_id = assignment.to_string();
    item
}

fn board_with(
    items: &[DayItem],
    minute: i64,
    when: &str,
    nudges: bool,
    missed: &[&str],
    unplaced: (i64, Option<(&str, &str)>),
) -> DayBoard {
    let missed: HashSet<String> = missed.iter().map(ToString::to_string).collect();
    board_for(&BoardInput {
        items,
        minute,
        when,
        nudges,
        dim: true,
        mode: "light",
        on: TODAY,
        now: None,
        missed: &missed,
        unplaced: unplaced.0,
        unplaced_words: unplaced.1,
    })
    .expect("a board")
}

fn board(items: &[DayItem], minute: i64) -> DayBoard {
    board_with(items, minute, "today", true, &[], (0, None))
}

fn titles(rows: &[flexweek_app::views::day::DayRow]) -> Vec<&str> {
    rows.iter().map(|row| row.title.as_str()).collect()
}

fn day_of_soccer() -> Vec<DayItem> {
    let mut soccer = block("Soccer", SOCCER);
    soccer.base.category = "exercise".to_string();
    vec![
        block("School", SCHOOL),
        soccer,
        homework("History essay", ESSAY, "a1"),
    ]
}

#[test]
fn the_count_line_says_things_left_today() {
    let _clock = clock(true);
    let day = [
        block("School", SCHOOL),
        block("Soccer", SOCCER),
        homework("Essay", ESSAY, "a1"),
    ];
    assert_eq!(board(&day, 15 * 60).left_line, "2 things left today");
    assert_eq!(board(&day, 17 * 60 + 40).left_line, "1 thing left today");
    assert_eq!(board(&day, 20 * 60).left_line, "Nothing left today");
    assert_eq!(board(&[], 9 * 60).left_line, "Nothing left today");
    let other = board_with(&day, 0, "future", true, &[], (0, None));
    assert_eq!(other.left_line, "3 things left");
    assert_eq!(
        board_with(&[], 0, "past", true, &[], (0, None)).left_line,
        "Nothing left"
    );
}

#[test]
fn lists_split_by_the_clock_and_by_finishing() {
    let _clock = clock(true);
    let mut essay = homework("Essay", ESSAY, "a1");
    essay.due = Some("2026-11-08T23:59".to_string());
    let mut over = homework("Maths", (17 * 60, 18 * 60), "a2");
    over.base.done = true;
    let day = board(&[block("School", SCHOOL), over, essay], 15 * 60);
    assert_eq!(titles(&day.up_next), ["Essay"]);
    assert_eq!(titles(&day.done), ["School", "Maths"]);
    assert_eq!(day.ring_count, 1);
    assert!((day.ring_share - 2.0 / 3.0).abs() < 1e-12);
    assert!(day.up_next[0].can_finish);
    assert!(!day.done[0].can_finish);
    assert!(day.up_next[0].subtitle.starts_with("18:45–19:45"));
    assert!(day.up_next[0].subtitle.contains("Due"));
    assert_eq!(day.up_next[0].assignment_id, "a1");
    assert!(day.done[0].dim, "finished rows dim when the switch is on");
    assert!(!day.up_next[0].dim);
}

#[test]
fn each_kind_of_row_wears_its_icon() {
    let _clock = clock(true);
    let mut soccer = block("Soccer", SOCCER);
    soccer.base.category = "exercise".to_string();
    let mut essay = homework("Essay", ESSAY, "a1");
    essay.base.category = "assignments".to_string();
    let day = board_with(
        &[block("School", SCHOOL), soccer, essay],
        9 * 60,
        "future",
        true,
        &[],
        (0, None),
    );
    let icons: Vec<&str> = day.up_next.iter().map(|row| row.icon.as_str()).collect();
    assert_eq!(icons, ["school", "schedule", "edit_note"]);
}

#[test]
fn free_time_wears_the_sofa_and_unknown_kinds_the_clock() {
    let _clock = clock(true);
    let mut free = block("Free time", SOCCER);
    free.base.category = "free".to_string();
    let mut club = block("Club", ESSAY);
    club.base.category = "extra".to_string();
    let mut study = block("Reading", (20 * 60, 21 * 60));
    study.base.category = "study".to_string();
    let mut meal = block("Dinner", (21 * 60, 22 * 60));
    meal.base.category = "meals".to_string();
    let day = board_with(
        &[free, club, study, meal],
        9 * 60,
        "future",
        true,
        &[],
        (0, None),
    );
    let icons: Vec<&str> = day.up_next.iter().map(|row| row.icon.as_str()).collect();
    assert_eq!(icons, ["weekend", "schedule", "edit_note", "schedule"]);
}

#[test]
fn pinned_shows_in_the_row_note() {
    let _clock = clock(true);
    let mut soccer = block("Soccer", SOCCER);
    soccer.pinned = true;
    assert_eq!(
        board(&[soccer], 9 * 60).up_next[0].subtitle,
        "16:00–17:30 · Pinned"
    );
}

#[test]
fn status_tags_use_the_slack_words() {
    let _clock = clock(true);
    let mut tight = homework("Essay", ESSAY, "a1");
    tight.slack = Some("tight".to_string());
    let mut plenty = homework("Poster", (20 * 60, 21 * 60), "a2");
    plenty.slack = Some("ok".to_string());
    let mut cutting = homework("Quiz", (21 * 60, 22 * 60), "a3");
    cutting.slack = Some("danger".to_string());
    let day = board(&[tight, plenty, cutting], 9 * 60);
    let tags: Vec<(&str, &str)> = day
        .up_next
        .iter()
        .map(|row| (row.tag.as_str(), row.tag_kind.as_str()))
        .collect();
    assert_eq!(
        tags,
        [
            ("Tight", "tight"),
            ("Plenty of time", "plenty"),
            ("Cutting it close", "cutting")
        ]
    );
    let mut finished = homework("Essay", ESSAY, "a1");
    finished.base.done = true;
    finished.slack = Some("tight".to_string());
    let done = board(&[finished], 9 * 60);
    assert_eq!(done.done[0].tag, "");
    assert_eq!(done.done[0].tag_kind, "");
}

#[test]
fn plenty_of_time_is_never_due_within_24_hours() {
    let _clock = clock(true);
    // Thursday 19:00: 18:00 on Friday is 23 hours away, 20:00 is 25.
    let mut soon = homework("Soon", (20 * 60, 20 * 60 + 30), "a1");
    soon.slack = Some("ok".to_string());
    soon.due = Some("2026-11-06T18:00".to_string());
    let mut later = homework("Later", (20 * 60, 20 * 60 + 30), "a2");
    later.slack = Some("ok".to_string());
    later.due = Some("2026-11-06T20:00".to_string());
    let day = board(&[soon, later], 19 * 60);
    let tags: Vec<(&str, &str)> = day
        .up_next
        .iter()
        .map(|row| (row.title.as_str(), row.tag.as_str()))
        .collect();
    assert_eq!(tags, [("Later", "Plenty of time"), ("Soon", "Tight")]);
}

#[test]
fn an_all_day_due_is_tight_five_hours_before_midnight() {
    let _clock = clock(true);
    let mut soon = homework("Soon", (20 * 60, 20 * 60 + 30), "a1");
    soon.slack = Some("ok".to_string());
    soon.due = Some("2026-11-06".to_string());
    let missed = HashSet::new();
    let day = board_for(&BoardInput {
        items: &[soon],
        minute: 19 * 60,
        when: "today",
        nudges: true,
        dim: true,
        mode: "light",
        on: "2026-11-06",
        now: Some("2026-11-06T19:00"),
        missed: &missed,
        unplaced: 0,
        unplaced_words: None,
    })
    .expect("a board");
    assert_eq!(day.up_next[0].tag, "Tight");
}

#[test]
fn another_day_reads_its_tags_from_the_real_clock_when_given() {
    let _clock = clock(true);
    let mut item = homework("Essay", (2 * 60, 2 * 60 + 30), "a1");
    item.slack = Some("ok".to_string());
    item.due = Some("2026-11-06T20:00".to_string());
    let missed = HashSet::new();
    // Viewing Friday at minute 0 would put the due 20 hours off and call it Tight; the real clock is
    // Thursday 17:00, 27 hours off.
    let day = board_for(&BoardInput {
        items: &[item],
        minute: 0,
        when: "future",
        nudges: true,
        dim: true,
        mode: "light",
        on: "2026-11-06",
        now: Some("2026-11-05T17:00"),
        missed: &missed,
        unplaced: 0,
        unplaced_words: None,
    })
    .expect("a board");
    assert_eq!(day.up_next[0].tag, "Plenty of time");
}

#[test]
fn without_a_real_clock_minutes_past_midnight_roll_the_date() {
    let _clock = clock(true);
    let mut item = homework("Essay", (26 * 60, 26 * 60 + 30), "a1");
    item.slack = Some("ok".to_string());
    item.due = Some("2026-11-06T02:00".to_string());
    // 25:00 on Thursday is 01:00 on Friday: one hour before the due, so Tight.
    let day = board(&[item], 25 * 60);
    assert_eq!(day.up_next[0].tag, "Tight");
}

#[test]
fn free_time_says_how_long_then_what_is_next() {
    let _clock = clock(false);
    let day = day_of_soccer();
    let at = board(&day, 15 * 60 + 40);
    assert!(at.show_now);
    assert_eq!(at.now_title, "Free for 20 min");
    assert_eq!(at.now_line, "Next: Soccer at 4:00 PM");
    assert!(!format!("{}{}", at.now_title, at.now_line).contains("History essay"));
    let later = board(&day, 15 * 60 + 47);
    assert_eq!(later.now_title, "Free for 13 min");
    assert_eq!(later.ring_count, 2);
    drop(_clock);
    let _clock = clock(true);
    let longer = board(&day, 13 * 60);
    assert_eq!(longer.now_title, "Free for 3 h");
    assert_eq!(longer.now_line, "Next: Soccer at 16:00");
}

#[test]
fn the_start_button_names_the_homework_it_starts() {
    let _clock = clock(true);
    let day = day_of_soccer();
    let at = board(&day, 15 * 60 + 40);
    assert_eq!(at.focus_title, "History essay");
    assert_eq!(at.focus_block_id, "history-essay");
    assert_eq!(at.focus_day, 3);
    let none = board(&[block("School", SCHOOL)], 15 * 60 + 40);
    assert_eq!(
        (none.focus_title.as_str(), none.focus_block_id.as_str()),
        ("", "")
    );
    assert_eq!(none.focus_day, -1);
}

#[test]
fn homework_happening_now_is_named_with_its_time_left() {
    let _clock = clock(true);
    let day = board(
        &[block("School", SCHOOL), homework("Essay", ESSAY, "a1")],
        19 * 60,
    );
    assert!(day.show_now);
    assert_eq!(day.now_title, "Essay");
    assert_eq!(day.now_line, "45 min left");
    assert_eq!(day.now_minutes, 45);
    assert_eq!(day.focus_block_id, "essay");
}

#[test]
fn nothing_left_today_has_no_now_card() {
    let _clock = clock(true);
    let mut essay = homework("Essay", ESSAY, "a1");
    essay.base.done = true;
    let day = board(&[block("School", SCHOOL), essay], 15 * 60);
    assert_eq!(day.left_line, "Nothing left today");
    assert!(!day.show_now);
    assert_eq!((day.now_title.as_str(), day.now_line.as_str()), ("", ""));
    assert_eq!(day.now_minutes, 0);
}

#[test]
fn no_now_card_after_the_last_one_off_today_or_with_nudges_off() {
    let _clock = clock(true);
    let day = [block("School", SCHOOL), block("Soccer", SOCCER)];
    assert!(!board(&day, 18 * 60).show_now);
    assert!(!board_with(&day, 13 * 60, "future", true, &[], (0, None)).show_now);
    assert!(!board_with(&day, 13 * 60, "past", true, &[], (0, None)).show_now);
    assert!(!board_with(&day, 13 * 60, "today", false, &[], (0, None)).show_now);
}

#[test]
fn a_finished_homework_block_does_not_end_the_gap() {
    let _clock = clock(true);
    let mut early = homework("Maths", (14 * 60, 15 * 60), "a2");
    early.base.done = true;
    let day = board(&[early, block("Soccer", SOCCER)], 14 * 60 + 30);
    assert!(day.show_now);
    assert_eq!(day.now_minutes, 90);
}

#[test]
fn inside_a_fixed_block_the_card_says_until_when_and_what_is_next() {
    let _clock = clock(true);
    let mut soccer = block("Soccer", SOCCER);
    soccer.base.category = "exercise".to_string();
    let day = vec![
        block("School", SCHOOL),
        soccer,
        homework("Essay", ESSAY, "a1"),
    ];
    let busy = board(&day, 16 * 60 + 11);
    assert!(busy.show_now && busy.now_busy);
    assert_eq!(busy.now_title, "Soccer until 17:30");
    assert_eq!(busy.now_line, "Next: Essay at 18:45");
    assert_eq!(busy.now_minutes, 79);
    let school = board(&day, 10 * 60);
    assert_eq!(school.now_title, "School until 12:00");
    assert_eq!(school.now_line, "Next: Soccer at 16:00");
    let last = board(&[block("Soccer", SOCCER)], 16 * 60 + 11);
    assert_eq!(last.now_title, "Soccer until 17:30");
    assert_eq!(last.now_line, "");
    let free = board(&day, 17 * 60 + 40);
    assert!(!free.now_busy);
    assert_eq!(free.now_title, "Free for 1 h 5 min");
    let mut over = [
        day.clone(),
        vec![homework("Maths", (16 * 60 + 30, 17 * 60), "a2")],
    ]
    .concat();
    over.sort_by_key(|item| item.base.start);
    let doing = board(&over, 16 * 60 + 40);
    assert!(!doing.now_busy);
    assert_eq!(doing.now_title, "Maths");
}

#[test]
fn a_finished_homework_block_inside_soccer_leaves_the_soccer_card() {
    let _clock = clock(true);
    let mut poster = homework("Science poster", (16 * 60, 16 * 60 + 30), "a3");
    poster.base.done = true;
    let day = board(
        &[
            poster,
            block("Soccer", SOCCER),
            homework("Essay", ESSAY, "a1"),
        ],
        16 * 60 + 11,
    );
    assert_eq!(day.now_title, "Soccer until 17:30");
    assert_eq!(day.now_line, "Next: Essay at 18:45");
}

#[test]
fn a_fixed_block_card_is_only_for_today_with_nudges_on_and_follows_the_12_hour_clock() {
    let at = 16 * 60 + 11;
    let day = [block("Soccer", SOCCER), homework("Essay", ESSAY, "a1")];
    {
        let _clock = clock(true);
        assert!(!board_with(&day, at, "past", true, &[], (0, None)).show_now);
        assert!(!board_with(&day, at, "future", true, &[], (0, None)).show_now);
        assert!(!board_with(&day, at, "today", false, &[], (0, None)).show_now);
    }
    let _clock = clock(false);
    let words = board(&day, at);
    assert_eq!(words.now_title, "Soccer until 5:30 PM");
    assert_eq!(words.now_line, "Next: Essay at 6:45 PM");
}

#[test]
fn where_fixed_blocks_overlap_the_card_names_the_one_that_ends_last() {
    let _clock = clock(true);
    let day = [
        block("A", (8 * 60, 9 * 60)),
        block("B", (8 * 60 + 30, 12 * 60)),
        block("Soccer", SOCCER),
    ];
    let busy = board(&day, 8 * 60 + 45);
    assert_eq!(busy.now_title, "B until 12:00");
    assert_eq!(busy.now_line, "Next: Soccer at 16:00");
    assert_eq!(busy.now_minutes, 3 * 60 + 15);
}

#[test]
fn where_two_fixed_blocks_end_together_the_card_names_the_earlier_one_in_the_list() {
    let _clock = clock(true);
    // Python's max() keeps the first of equals; the list is in start order, so A comes first.
    let day = [block("B", (9 * 60, 10 * 60)), block("A", (8 * 60, 10 * 60))];
    let busy = board(&day, 9 * 60 + 30);
    assert_eq!(busy.now_title, "A until 10:00");
}

#[test]
fn rows_with_the_same_start_sort_by_title() {
    let _clock = clock(true);
    let day = [block("Zed", SOCCER), block("Abe", SOCCER)];
    let both = board_with(&day, 0, "future", true, &[], (0, None));
    assert_eq!(titles(&both.up_next), ["Abe", "Zed"]);
}

#[test]
fn homework_the_planner_calls_missed_is_still_to_do_not_done() {
    let _clock = clock(true);
    let mut missed = homework("Essay", (16 * 60, 17 * 60), "a1");
    missed.due = Some("2026-11-08T23:59".to_string());
    let mut maths = homework("Maths", (17 * 60, 18 * 60), "a2");
    maths.base.done = true;
    let day = board_with(
        &[block("School", SCHOOL), missed, maths],
        19 * 60,
        "today",
        true,
        &["essay"],
        (0, None),
    );
    assert_eq!(titles(&day.up_next), ["Essay"]);
    assert_eq!(titles(&day.done), ["School", "Maths"]);
    assert!(!day.up_next[0].dim);
    assert!(day.up_next[0].can_finish, "it can still be finished");
    assert_eq!(day.ring_count, 1);
    assert_eq!(day.left_line, "1 thing left today");
}

#[test]
fn an_ended_session_the_planner_does_not_call_missed_is_done() {
    let _clock = clock(true);
    let covered = homework("Essay", (16 * 60, 17 * 60), "a1");
    let day = board(&[covered], 19 * 60);
    assert_eq!(titles(&day.done), ["Essay"]);
    assert!(day.up_next.is_empty());
    assert_eq!(day.left_line, "Nothing left today");
}

#[test]
fn a_session_flagged_missed_by_the_week_is_not_up_next() {
    let _clock = clock(true);
    let mut flagged = homework("Essay", (16 * 60, 17 * 60), "a1");
    flagged.missed = true;
    // The item's own missed flag settles it: Done, even when the planner list names it.
    let day = board_with(&[flagged], 19 * 60, "today", true, &["essay"], (0, None));
    assert!(day.up_next.is_empty());
    assert_eq!(titles(&day.done), ["Essay"]);
}

#[test]
fn start_focus_stays_on_homework_that_is_not_over() {
    let _clock = clock(true);
    let over = homework("Essay", (16 * 60, 17 * 60), "a1");
    let ahead = homework("Reading", (20 * 60, 21 * 60), "a2");
    let day = board_with(
        &[over, ahead],
        19 * 60,
        "today",
        true,
        &["essay"],
        (0, None),
    );
    assert_eq!(day.focus_title, "Reading");
}

#[test]
fn homework_waiting_for_a_time_names_itself_when_nothing_else_is_on_or_ahead() {
    let _clock = clock(true);
    let words = Some(("Math worksheet", "Pick a time for it"));
    let day = board_with(&[], 14 * 60, "today", true, &[], (1, words));
    assert!(day.show_now);
    assert_eq!(day.now_title, "Math worksheet");
    assert_eq!(day.now_line, "Pick a time for it");
    assert_eq!(day.ring_count, 1);
    assert_eq!(day.ring_caption, "thing left");
    assert_eq!(day.left_line, "1 thing left today");
    assert_eq!(day.ring_share, 0.0);
    // Something still ahead keeps its own card.
    let busy = board_with(
        &[block("Soccer", SOCCER)],
        14 * 60,
        "today",
        true,
        &[],
        (1, words),
    );
    assert_eq!(busy.now_title, "Free for 2 h");
    assert_eq!(busy.ring_count, 2);
    // Another day does not count homework due today.
    let future = board_with(&[], 0, "future", true, &[], (1, words));
    assert!(!future.show_now);
    assert_eq!(future.ring_count, 0);
    // Without the week's words the card stays hidden, but the count stays.
    let silent = board_with(&[], 14 * 60, "today", true, &[], (2, None));
    assert!(!silent.show_now);
    assert_eq!(silent.left_count, 2);
    assert_eq!(silent.ring_caption, "things left");
}

#[test]
fn the_nudge_and_dim_preferences_read_defensively() {
    let keys = ["free_time_nudges", "nudges"];
    assert!(read_flag(&Value::Null, &keys, true));
    assert!(read_flag(&json!({}), &keys, true));
    assert!(!read_flag(&json!({"free_time_nudges": false}), &keys, true));
    assert!(!read_flag(&json!({"nudges": false}), &keys, true));
    assert!(read_flag(&json!({"free_time_nudges": "no"}), &keys, true));
    // A real bool under the later name still counts when the first holds something else.
    assert!(!read_flag(
        &json!({"free_time_nudges": "no", "nudges": false}),
        &keys,
        true
    ));
    assert!(!read_flag(&json!([true]), &keys, false));
}

#[test]
fn the_board_serialises_with_the_dataclass_field_names() {
    let _clock = clock(true);
    let shown = board(&[homework("Essay", ESSAY, "a1")], 9 * 60).to_json();
    let mut names: Vec<&str> = shown
        .as_object()
        .expect("an object")
        .keys()
        .map(String::as_str)
        .collect();
    names.sort_unstable();
    assert_eq!(
        names,
        [
            "done",
            "focus_block_id",
            "focus_day",
            "focus_title",
            "left_count",
            "left_line",
            "now_busy",
            "now_line",
            "now_minutes",
            "now_title",
            "ring_caption",
            "ring_count",
            "ring_share",
            "show_now",
            "up_next"
        ]
    );
    let mut row_names: Vec<&str> = shown["up_next"][0]
        .as_object()
        .expect("a row")
        .keys()
        .map(String::as_str)
        .collect();
    row_names.sort_unstable();
    assert_eq!(
        row_names,
        [
            "assignment_id",
            "bar",
            "can_finish",
            "dim",
            "fill",
            "icon",
            "ink",
            "subtitle",
            "tag",
            "tag_kind",
            "title"
        ]
    );
}

// ---- the timer card ----

#[test]
fn a_running_timer_says_its_time_left_rounded_up() {
    let _clock = clock(true);
    let state = json!({"title": "History essay", "phase": "work", "running": true, "endsAt": 1_000_000 + 12 * 60_000 + 30_000});
    let words = timer_words(&state, 1_000_000, None).expect("words");
    assert_eq!(
        words,
        TimerWords {
            title: "History essay".into(),
            line: "13 min left".into(),
            ended: false,
            open: false,
            done: false
        }
    );
    // Less than a minute left still says one minute, never zero.
    let last = json!({"title": "x", "phase": "work", "running": true, "endsAt": 1_000_000 + 5_000});
    assert_eq!(
        timer_words(&last, 1_000_000, None).unwrap().line,
        "1 min left"
    );
    let over = json!({"title": "x", "phase": "work", "running": true, "endsAt": 10});
    assert_eq!(
        timer_words(&over, 1_000_000, None).unwrap().line,
        "1 min left"
    );
    let hour =
        json!({"title": "x", "phase": "work", "running": true, "endsAt": 1_000_000 + 90 * 60_000});
    assert_eq!(
        timer_words(&hour, 1_000_000, None).unwrap().line,
        "1 h 30 min left"
    );
}

#[test]
fn a_break_and_a_paused_timer_say_so() {
    let _clock = clock(true);
    let pause = json!({"title": "x", "phase": "break", "running": false, "remainingMs": 300_000});
    assert_eq!(
        timer_words(&pause, 5, None).unwrap().line,
        "Break, 5 min left"
    );
    let long =
        json!({"title": "x", "phase": "long_break", "running": false, "remainingMs": 899_000});
    assert_eq!(
        timer_words(&long, 5, None).unwrap().line,
        "Break, 15 min left"
    );
    let paused = json!({"title": "x", "phase": "work", "running": false, "remainingMs": 600_000});
    assert_eq!(timer_words(&paused, 5, None).unwrap().line, "10 min left");
}

#[test]
fn a_timer_without_a_title_is_a_quick_focus_and_no_timer_is_blank() {
    let _clock = clock(true);
    let quick = json!({"phase": "work", "running": false, "remainingMs": 60_000});
    assert_eq!(timer_words(&quick, 0, None).unwrap().title, "Quick focus");
    let empty = json!({"title": "", "phase": "work", "running": false, "remainingMs": 60_000});
    assert_eq!(timer_words(&empty, 0, None).unwrap().title, "Quick focus");
    assert_eq!(
        timer_words(&Value::Null, 0, None).unwrap(),
        TimerWords::default()
    );
    assert_eq!(
        timer_words(&json!([1]), 0, None).unwrap(),
        TimerWords::default()
    );
}

#[test]
fn a_timer_that_ran_out_says_so_by_what_became_of_its_homework() {
    let ended = json!({"title": "Essay", "phase": "ended", "assignmentId": "a1"});
    let open = timer_words(&ended, 0, Some(false)).unwrap();
    assert_eq!(
        (open.line.as_str(), open.ended, open.open, open.done),
        ("Session finished", true, true, false)
    );
    let finished = timer_words(&ended, 0, Some(true)).unwrap();
    assert_eq!(
        (
            finished.line.as_str(),
            finished.ended,
            finished.open,
            finished.done
        ),
        ("Finished", true, false, true)
    );
    let quick = timer_words(&json!({"phase": "ended"}), 0, None).unwrap();
    assert_eq!(
        (
            quick.title.as_str(),
            quick.line.as_str(),
            quick.open,
            quick.done
        ),
        ("Quick focus", "Session finished", false, false)
    );
}

#[test]
fn the_other_ended_timer_actions() {
    assert!(finish_refreshes(Some("finished")));
    assert!(finish_refreshes(Some("queued")));
    assert!(!finish_refreshes(Some("ignored")));
    assert!(!finish_refreshes(None));
    assert!(focus_ended(&json!({"phase": "ended"})));
    assert!(!focus_ended(&json!({"phase": "work"})));
    assert!(!focus_ended(&Value::Null));
    assert!(!focus_ended(&json!("ended")));
}

#[test]
fn the_finish_button_guards_and_words() {
    assert_eq!(
        finish_plan("", false, false, Some("Essay")),
        flexweek_app::views::day::FinishPlan {
            say_now: None,
            finished: None
        }
    );
    let saving = finish_plan("a1", true, false, Some("Essay"));
    assert_eq!(saving.say_now.as_deref(), Some(SAVING_FIRST));
    assert_eq!(saving.finished, None);
    assert_eq!(
        finish_plan("a1", false, true, None).say_now.as_deref(),
        Some(SAVING_FIRST)
    );
    let done = finish_plan("a1", false, false, Some("Essay"));
    assert_eq!(
        (done.say_now, done.finished.as_deref()),
        (None, Some("Finished Essay"))
    );
    assert_eq!(
        finish_plan("a1", false, false, None).finished.as_deref(),
        Some("Finished Homework")
    );
    assert_eq!(
        finish_plan("a1", false, false, Some(""))
            .finished
            .as_deref(),
        Some("Finished Homework")
    );
}

// ---- which week and day, and what Today and the buttons do ----

struct Facts<'a> {
    selected: Option<&'a str>,
    week_start: Option<&'a str>,
    needed: &'a str,
    busy: bool,
    fetch: bool,
    screen: &'a str,
    message: Option<&'a str>,
}

impl<'a> Facts<'a> {
    fn day(selected: Option<&'a str>, week_start: Option<&'a str>) -> Self {
        Self {
            selected,
            week_start,
            needed: "2026-11-02",
            busy: false,
            fetch: false,
            screen: "day",
            message: None,
        }
    }

    fn my_day(week_start: Option<&'a str>) -> Self {
        Self::day(None, week_start)
    }

    fn begin(&self, view: &mut DayView) -> flexweek_app::views::day::BeginOutcome {
        view.begin_reload(&BeginInput {
            mode: "dark",
            prefs: &json!({"clock_24h": true}),
            today_iso: TODAY,
            clock_minute: 17 * 60 + 5,
            selected_day: self.selected,
            signed_in: true,
            week_start: self.week_start,
            needed_week: self.needed,
            busy: self.busy,
            message: self.message,
            fetch: self.fetch,
            screen: self.screen,
            can_load: true,
        })
        .expect("a reload")
    }
}

// A week that knows nothing of homework waiting for a time.
static QUIET: Fake = Fake {
    api: false,
    count: 0,
    kind: "",
};

fn publish(
    view: &mut DayView,
    items: &[DayItem],
    prefs: &Value,
    timer: TimerWords,
    week: Option<&dyn WeekLookups>,
) -> flexweek_app::views::day::Published {
    let missed = HashSet::new();
    view.finish_reload(&FinishInput {
        items,
        missed: &missed,
        prefs,
        timer,
        week,
        now: "2026-11-05T17:05",
    })
    .expect("a published day")
}

fn finish(
    view: &mut DayView,
    items: &[DayItem],
    prefs: &Value,
    timer: TimerWords,
) -> flexweek_app::views::day::Published {
    publish(view, items, prefs, timer, Some(&QUIET))
}

#[test]
fn day_follows_the_chosen_date_and_falls_back_to_today() {
    let mut view = DayView::new(false);
    let outcome = Facts::day(Some("2026-11-06"), Some("2026-11-02")).begin(&mut view);
    assert!(outcome.proceed && outcome.read_week && outcome.clock_24h);
    assert_eq!(outcome.day, Some(4));
    let shown = view.snapshot();
    assert_eq!(shown["iso"], "2026-11-06");
    assert_eq!(
        (
            shown["year"].as_i64(),
            shown["month"].as_i64(),
            shown["miniDay"].as_i64()
        ),
        (Some(2026), Some(11), Some(6))
    );
    assert_eq!(shown["dayIndex"], 4);
    assert_eq!(view.mode(), "dark");
    for odd in [None, Some(""), Some("not a date"), Some("2026-13-40")] {
        let mut other = DayView::new(false);
        let outcome = Facts::day(odd, Some("2026-11-02")).begin(&mut other);
        assert_eq!(other.snapshot()["iso"], TODAY, "{odd:?}");
        assert_eq!(outcome.day, Some(3));
    }
}

#[test]
fn a_day_outside_the_shown_week_has_no_index_and_a_missing_week_reads_nothing() {
    let mut view = DayView::new(false);
    let outcome = Facts::day(Some("2026-11-09"), Some("2026-11-02")).begin(&mut view);
    assert_eq!(
        (outcome.proceed, outcome.day, outcome.read_week),
        (true, None, true)
    );
    assert_eq!(view.snapshot()["dayIndex"], -1);
    for week_start in [None, Some("")] {
        let mut bare = DayView::new(false);
        let outcome = Facts::day(None, week_start).begin(&mut bare);
        assert_eq!(
            (outcome.proceed, outcome.day, outcome.read_week),
            (true, None, false)
        );
    }
    let mut unsigned = DayView::new(false);
    let outcome = unsigned
        .begin_reload(&BeginInput {
            mode: "light",
            prefs: &Value::Null,
            today_iso: TODAY,
            clock_minute: 0,
            selected_day: None,
            signed_in: false,
            week_start: Some("2026-11-02"),
            needed_week: "2026-11-02",
            busy: false,
            message: None,
            fetch: false,
            screen: "day",
            can_load: true,
        })
        .unwrap();
    assert!(!outcome.read_week && !outcome.clock_24h && outcome.day.is_none());
    assert_eq!(unsigned.mode(), "light");
}

#[test]
fn an_odd_mode_reads_as_light() {
    let mut view = DayView::new(false);
    view.begin_reload(&BeginInput {
        mode: "sepia",
        prefs: &Value::Null,
        today_iso: TODAY,
        clock_minute: 0,
        selected_day: None,
        signed_in: true,
        week_start: Some("2026-11-02"),
        needed_week: "2026-11-02",
        busy: false,
        message: None,
        fetch: false,
        screen: "day",
        can_load: true,
    })
    .unwrap();
    assert_eq!(view.mode(), "light");
}

#[test]
fn my_day_is_always_today_and_waits_for_the_week_that_holds_it() {
    let mut view = DayView::new(true);
    let mut facts = Facts::my_day(Some("2026-10-26"));
    facts.selected = Some("2026-11-20");
    facts.fetch = true;
    let outcome = facts.begin(&mut view);
    assert!(!outcome.proceed);
    assert_eq!(outcome.load.as_deref(), Some("2026-11-02"));
    let shown = view.snapshot();
    assert_eq!(shown["iso"], TODAY, "My day ignores the chosen date");
    assert_eq!(shown["waiting"], true);
    assert_eq!(shown["loadError"], "");
    assert_eq!(view.left_line("1 thing left today"), "Loading…");
}

#[test]
fn my_day_only_asks_for_the_week_when_it_is_on_screen_or_was_asked_before() {
    let mut view = DayView::new(true);
    let mut facts = Facts::my_day(Some("2026-10-26"));
    facts.screen = "week";
    assert_eq!(
        facts.begin(&mut view).load,
        None,
        "not showing and not asked: wait quietly"
    );
    assert_eq!(view.snapshot()["waiting"], true);
    facts.screen = "myday";
    assert_eq!(facts.begin(&mut view).load.as_deref(), Some("2026-11-02"));
    // A busy session is not asked to load on top of what it is doing.
    let mut busy = Facts::my_day(Some("2026-10-26"));
    busy.fetch = true;
    busy.busy = true;
    let mut other = DayView::new(true);
    assert_eq!(busy.begin(&mut other).load, None);
    // Without a way to load, nothing is asked.
    let mut mute = DayView::new(true);
    let outcome = mute
        .begin_reload(&BeginInput {
            mode: "light",
            prefs: &Value::Null,
            today_iso: TODAY,
            clock_minute: 0,
            selected_day: None,
            signed_in: true,
            week_start: Some("2026-10-26"),
            needed_week: "2026-11-02",
            busy: false,
            message: None,
            fetch: true,
            screen: "myday",
            can_load: false,
        })
        .unwrap();
    assert_eq!((outcome.proceed, outcome.load), (false, None));
}

#[test]
fn a_load_that_finished_without_the_week_says_why() {
    let mut view = DayView::new(true);
    let mut facts = Facts::my_day(Some("2026-10-26"));
    facts.fetch = true;
    assert!(facts.begin(&mut view).load.is_some());
    view.mark_load_started();
    // The session is idle again and still not on the week: the load failed.
    facts.fetch = false;
    facts.message = Some("No connection");
    let outcome = facts.begin(&mut view);
    assert!(!outcome.proceed && outcome.load.is_none());
    let shown = view.snapshot();
    assert_eq!(
        (shown["waiting"].as_bool(), shown["loadError"].as_str()),
        (Some(false), Some("No connection"))
    );
    assert_eq!(view.left_line("1 thing left today"), "No connection");
    // An empty or missing message gets the default words.
    for message in [None, Some("")] {
        let mut again = DayView::new(true);
        let mut ask = Facts::my_day(Some("2026-10-26"));
        ask.fetch = true;
        ask.begin(&mut again);
        again.mark_load_started();
        ask.fetch = false;
        ask.message = message;
        ask.begin(&mut again);
        assert_eq!(again.snapshot()["loadError"], LOAD_FAILED);
    }
    // A load still running is not a failure.
    let mut running = DayView::new(true);
    let mut ask = Facts::my_day(Some("2026-10-26"));
    ask.fetch = true;
    ask.begin(&mut running);
    running.mark_load_started();
    ask.busy = true;
    ask.begin(&mut running);
    assert_eq!(running.snapshot()["waiting"], true);
    assert_eq!(running.snapshot()["loadError"], "");
}

#[test]
fn reaching_the_week_clears_the_waiting_state() {
    let mut view = DayView::new(true);
    let mut facts = Facts::my_day(Some("2026-10-26"));
    facts.fetch = true;
    facts.begin(&mut view);
    view.mark_load_started();
    assert!(
        view.on_busy(false, "week"),
        "a load was started, so going idle reloads"
    );
    let arrived = Facts::my_day(Some("2026-11-02")).begin(&mut view);
    assert!(arrived.proceed && arrived.read_week);
    assert_eq!(arrived.day, Some(3));
    assert!(
        !view.on_busy(false, "week"),
        "nothing is being waited for any more"
    );
    let published = finish(&mut view, &[], &Value::Null, TimerWords::default());
    assert_eq!(published.board.left_line, "Nothing left today");
    let shown = view.snapshot();
    assert_eq!(
        (shown["waiting"].as_bool(), shown["loadError"].as_str()),
        (Some(false), Some(""))
    );
}

#[test]
fn going_idle_reloads_my_day_only_when_it_is_waiting_and_shown() {
    let mut view = DayView::new(true);
    let mut facts = Facts::my_day(Some("2026-10-26"));
    facts.screen = "week";
    facts.begin(&mut view);
    assert!(!view.on_busy(false, "week"), "waiting but not showing");
    assert!(view.on_busy(false, "myday"));
    assert!(!view.on_busy(true, "myday"), "still busy");
    assert!(
        !DayView::new(false).on_busy(false, "myday"),
        "Day has its own signal"
    );
}

#[test]
fn finishing_a_reload_publishes_the_day_the_begin_chose() {
    let _clock = clock(true);
    let mut view = DayView::new(false);
    Facts::day(None, Some("2026-11-02")).begin(&mut view);
    let mut soccer = block("Soccer", SOCCER);
    soccer.base.category = "exercise".to_string();
    let items = [block("School", SCHOOL), soccer];
    let published = finish(&mut view, &items, &Value::Null, TimerWords::default());
    // 17:05 on Thursday: School is over, Soccer is on until 17:30.
    assert_eq!(titles(&published.board.done), ["School"]);
    assert_eq!(published.board.now_title, "Soccer until 17:30");
    assert_eq!(published.board.now_minutes, 25);
    let rows: Vec<(&str, bool)> = published
        .block_rows
        .iter()
        .map(|row| {
            (
                row["title"].as_str().unwrap(),
                row["past"].as_bool().unwrap(),
            )
        })
        .collect();
    assert_eq!(rows, [("School", true), ("Soccer", false)]);
    assert_eq!(published.block_rows[0]["indent"], 0);
    // Opening the hours: now, on today.
    assert_eq!(view.snapshot()["openingMinute"], 17 * 60 + 5);
}

#[test]
fn another_day_shows_no_card_and_opens_on_its_first_block() {
    let _clock = clock(true);
    let mut view = DayView::new(false);
    Facts::day(Some("2026-11-06"), Some("2026-11-02")).begin(&mut view);
    let mut early = block("Chem", (9 * 60 + 30, 10 * 60 + 30));
    early.base.day = 4;
    let mut late = block("Soccer", SOCCER);
    late.base.day = 4;
    let published = finish(
        &mut view,
        &[late, early],
        &Value::Null,
        TimerWords::default(),
    );
    assert!(!published.board.show_now);
    assert_eq!(published.board.left_line, "2 things left");
    assert_eq!(view.snapshot()["openingMinute"], 9 * 60 + 30);
    assert!(
        published.block_rows.iter().all(|row| row["past"] == false),
        "tomorrow is not over"
    );
}

#[test]
fn a_day_with_nothing_opens_at_eight_and_a_day_outside_the_week_too() {
    let mut empty = DayView::new(false);
    Facts::day(Some("2026-11-06"), Some("2026-11-02")).begin(&mut empty);
    finish(&mut empty, &[], &Value::Null, TimerWords::default());
    assert_eq!(empty.snapshot()["openingMinute"], 8 * 60);
    let mut outside = DayView::new(false);
    Facts::day(Some("2026-11-20"), Some("2026-11-02")).begin(&mut outside);
    finish(&mut outside, &[], &Value::Null, TimerWords::default());
    assert_eq!(outside.snapshot()["openingMinute"], 8 * 60);
    // Today with the week unknown still opens on now.
    let mut bare = DayView::new(false);
    Facts::day(None, None).begin(&mut bare);
    publish(&mut bare, &[], &Value::Null, TimerWords::default(), None);
    assert_eq!(bare.snapshot()["openingMinute"], 17 * 60 + 5);
}

#[test]
fn blocks_of_a_week_in_the_past_are_all_over_and_of_a_week_ahead_none() {
    let _clock = clock(true);
    let prefs = json!({"dim_completed": true});
    let mut past = DayView::new(false);
    Facts::day(Some("2026-11-05"), Some("2026-10-19")).begin(&mut past);
    // Week from 19 Oct: Thursday the 22nd is index 3, today (5 Nov) is 17 days on: offset > 6.
    let mut item = block("Soccer", SOCCER);
    item.base.day = 3;
    let shown = finish(&mut past, &[item.clone()], &prefs, TimerWords::default());
    assert_eq!(shown.block_rows[0]["past"], true);
    let mut ahead = DayView::new(false);
    Facts::day(Some("2026-11-05"), Some("2026-11-09")).begin(&mut ahead);
    let mut later = item;
    later.base.day = 0;
    let shown = finish(&mut ahead, &[later], &prefs, TimerWords::default());
    assert_eq!(
        shown.block_rows[0]["past"], false,
        "a week ahead is not over"
    );
}

#[test]
fn blocks_earlier_in_the_week_or_ended_today_are_over_and_the_dim_switch_can_turn_it_off() {
    let _clock = clock(true);
    let mut view = DayView::new(false);
    Facts::day(Some("2026-11-04"), Some("2026-11-02")).begin(&mut view);
    let mut wed = block("Chem", (9 * 60, 10 * 60));
    wed.base.day = 2;
    let shown = finish(
        &mut view,
        &[wed.clone()],
        &Value::Null,
        TimerWords::default(),
    );
    assert_eq!(shown.block_rows[0]["past"], true, "yesterday is over");
    let mut view = DayView::new(false);
    Facts::day(Some("2026-11-04"), Some("2026-11-02")).begin(&mut view);
    let shown = finish(
        &mut view,
        &[wed],
        &json!({"dim_completed": false}),
        TimerWords::default(),
    );
    assert_eq!(shown.block_rows[0]["past"], false, "dimming is off");
}

#[test]
fn finishing_without_beginning_is_refused() {
    let mut view = DayView::new(false);
    let missed = HashSet::new();
    let result = view.finish_reload(&FinishInput {
        items: &[],
        missed: &missed,
        prefs: &Value::Null,
        timer: TimerWords::default(),
        week: None,
        now: "2026-11-05T17:05",
    });
    assert!(result.is_err());
}

struct Fake {
    api: bool,
    count: usize,
    kind: &'static str,
}

impl WeekLookups for Fake {
    fn has_unplaced_api(&self) -> bool {
        self.api
    }

    fn unplaced_count(&self, _day: i64) -> EngineResult<usize> {
        Ok(self.count)
    }

    fn leftover_kind(&self, _day: i64) -> EngineResult<String> {
        Ok(self.kind.to_string())
    }

    fn leftover_title_line(&self, _day: i64) -> EngineResult<(String, String)> {
        Ok(("Math worksheet".to_string(), "Choose when".to_string()))
    }
}

#[test]
fn waiting_homework_is_asked_of_the_week_only_on_today() {
    let needs = Fake {
        api: true,
        count: 2,
        kind: "needs_time",
    };
    let some = waiting_for_a_time(Some(&needs), 3, true).unwrap();
    assert_eq!(
        some,
        (
            2,
            Some(("Math worksheet".to_string(), "Choose when".to_string()))
        )
    );
    let placed = Fake {
        api: true,
        count: 2,
        kind: "has_time",
    };
    assert_eq!(
        waiting_for_a_time(Some(&placed), 3, true).unwrap(),
        (2, None)
    );
    let none = Fake {
        api: true,
        count: 0,
        kind: "needs_time",
    };
    assert_eq!(waiting_for_a_time(Some(&none), 3, true).unwrap(), (0, None));
    assert_eq!(
        waiting_for_a_time(Some(&needs), 3, false).unwrap(),
        (0, None)
    );
    assert_eq!(
        waiting_for_a_time(Some(&needs), -1, true).unwrap(),
        (0, None)
    );
    assert_eq!(waiting_for_a_time(None, 3, true).unwrap(), (0, None));
    let old = Fake {
        api: false,
        count: 2,
        kind: "needs_time",
    };
    assert_eq!(waiting_for_a_time(Some(&old), 3, true).unwrap(), (0, None));
}

#[test]
fn the_week_decides_whether_homework_waiting_for_a_time_shows_on_the_card() {
    let _clock = clock(true);
    let mut view = DayView::new(true);
    Facts::my_day(Some("2026-11-02")).begin(&mut view);
    let week = Fake {
        api: true,
        count: 1,
        kind: "needs_time",
    };
    let missed = HashSet::new();
    let published = view
        .finish_reload(&FinishInput {
            items: &[],
            missed: &missed,
            prefs: &Value::Null,
            timer: TimerWords::default(),
            week: Some(&week),
            now: "2026-11-05T17:05",
        })
        .unwrap();
    assert!(published.board.show_now);
    assert_eq!(published.board.now_title, "Math worksheet");
    assert_eq!(published.board.now_line, "Choose when");
    assert_eq!(published.board.left_line, "1 thing left today");
}

#[test]
fn the_timer_card_shows_on_today_only_and_changes_only_when_its_words_do() {
    let mut view = DayView::new(false);
    Facts::day(None, Some("2026-11-02")).begin(&mut view);
    let ended = TimerWords {
        title: "Essay".into(),
        line: "Session finished".into(),
        ended: true,
        open: true,
        done: false,
    };
    finish(&mut view, &[], &Value::Null, ended.clone());
    let shown = view.snapshot();
    assert_eq!(shown["timerTitle"], "Essay");
    assert_eq!(shown["timerLine"], "Session finished");
    assert_eq!(
        (
            shown["timerEnded"].as_bool(),
            shown["timerCanFinish"].as_bool(),
            shown["timerDone"].as_bool()
        ),
        (Some(true), Some(true), Some(false))
    );
    assert!(view.show_now(false), "a timer makes the card show");
    assert!(
        !view.refresh_timer(ended.clone()),
        "same words, nothing to redraw"
    );
    let done = TimerWords {
        open: false,
        done: true,
        line: "Finished".into(),
        ..ended.clone()
    };
    assert!(view.refresh_timer(done));
    assert_eq!(view.snapshot()["timerDone"], true);
    assert_eq!(view.snapshot()["timerCanFinish"], false);
    // Another day does not wear the timer.
    let mut other = DayView::new(false);
    Facts::day(Some("2026-11-06"), Some("2026-11-02")).begin(&mut other);
    finish(&mut other, &[], &Value::Null, ended);
    let shown = other.snapshot();
    assert_eq!(
        (
            shown["timerTitle"].as_str(),
            shown["timerLine"].as_str(),
            shown["timerEnded"].as_bool()
        ),
        (Some(""), Some(""), Some(false))
    );
    assert!(!other.show_now(false));
    assert!(other.show_now(true), "the board's own card still shows");
}

#[test]
fn today_means_something_only_on_day_and_only_with_a_session() {
    assert!(DayView::new(false).today_requested(true));
    assert!(!DayView::new(false).today_requested(false));
    assert!(!DayView::new(true).today_requested(true));
}

#[test]
fn a_wish_for_today_is_kept_until_the_session_is_idle_and_then_asks_once() {
    let mut view = DayView::new(false);
    assert!(!view.after_week(true, false), "nothing was wished");
    view.set_want_today(true);
    assert!(!view.after_week(true, true), "still loading");
    assert!(!view.after_week(false, false), "no session");
    assert!(view.after_week(true, false));
    assert!(!view.after_week(true, false), "the wish is spent");
    view.set_want_today(true);
    view.set_want_today(false);
    assert!(
        !view.after_week(true, false),
        "opening a date drops the wish"
    );
}

#[test]
fn a_landed_week_that_left_day_off_today_reopens_today() {
    let view = DayView::new(false);
    let holding = "2026-11-02";
    assert!(!view.reopen_today("day", Some(TODAY), Some(holding), holding, TODAY));
    assert!(view.reopen_today("day", Some("2026-11-06"), Some(holding), holding, TODAY));
    assert!(view.reopen_today("day", Some(TODAY), Some("2026-10-26"), holding, TODAY));
    assert!(view.reopen_today("day", None, Some(holding), holding, TODAY));
    assert!(view.reopen_today("day", Some(TODAY), None, holding, TODAY));
    assert!(!view.reopen_today("week", Some("2026-11-06"), Some(holding), holding, TODAY));
}

#[test]
fn picking_and_shifting_days_stay_inside_real_dates() {
    let mut view = DayView::new(false);
    Facts::day(Some("2026-02-10"), Some("2026-02-09")).begin(&mut view);
    assert_eq!(view.pick_target(14).as_deref(), Some("2026-02-14"));
    assert_eq!(view.pick_target(28).as_deref(), Some("2026-02-28"));
    assert_eq!(view.pick_target(29), None, "2026 is not a leap year");
    assert_eq!(view.pick_target(31), None);
    assert_eq!(view.pick_target(0), None);
    assert_eq!(view.pick_target(32), None);
    assert_eq!(view.shift_target(1).unwrap().as_deref(), Some("2026-02-11"));
    assert_eq!(
        view.shift_target(-10).unwrap().as_deref(),
        Some("2026-01-31")
    );
    let mut month_end = DayView::new(false);
    Facts::day(Some("2026-12-31"), Some("2026-12-28")).begin(&mut month_end);
    assert_eq!(
        month_end.shift_target(1).unwrap().as_deref(),
        Some("2027-01-01")
    );
    // My day never moves, and a Day that has shown nothing yet has nowhere to go.
    let mut mine = DayView::new(true);
    Facts::my_day(Some("2026-11-02")).begin(&mut mine);
    assert_eq!(mine.pick_target(10), None);
    assert_eq!(mine.shift_target(1).unwrap(), None);
    assert_eq!(DayView::new(false).shift_target(1).unwrap(), None);
}

#[test]
fn start_focus_goes_back_to_a_running_timer_else_the_first_hook_the_window_has() {
    let mut view = DayView::new(false);
    Facts::day(None, Some("2026-11-02")).begin(&mut view);
    let all = FocusHooks {
        opener: true,
        hook: true,
        starter: true,
    };
    let plan = view.start_focus_plan(&all, "essay", 3);
    assert_eq!(
        (plan.action, plan.block_id, plan.day),
        ("hook", Some("essay".to_string()), Some(3))
    );
    let running = TimerWords {
        title: "Essay".into(),
        line: "13 min left".into(),
        ..TimerWords::default()
    };
    finish(&mut view, &[], &Value::Null, running);
    assert_eq!(view.start_focus_plan(&all, "essay", 3).action, "open_focus");
    let no_opener = FocusHooks {
        opener: false,
        hook: true,
        starter: true,
    };
    assert_eq!(view.start_focus_plan(&no_opener, "essay", 3).action, "hook");
    let widgets = FocusHooks {
        opener: false,
        hook: false,
        starter: true,
    };
    let plan = view.start_focus_plan(&widgets, "essay", 3);
    assert_eq!(
        (plan.action, plan.block_id, plan.day),
        ("widgets", Some("essay".to_string()), Some(3))
    );
    let session = FocusHooks {
        opener: false,
        hook: false,
        starter: false,
    };
    let plan = view.start_focus_plan(&session, "essay", -1);
    assert_eq!(
        (plan.action, plan.block_id, plan.day),
        ("session", Some("essay".to_string()), None)
    );
    let plan = view.start_focus_plan(&session, "", -1);
    assert_eq!(
        (plan.block_id, plan.day),
        (None, None),
        "no block means the quick one"
    );
    let hook = view.start_focus_plan(&no_opener, "", -1);
    assert_eq!(
        (hook.action, hook.block_id, hook.day),
        ("hook", Some(String::new()), Some(-1)),
        "the hook is told as the board has it"
    );
    let widgets = view.start_focus_plan(&widgets, "", -1);
    assert_eq!((widgets.block_id, widgets.day), (Some(String::new()), None));
}

#[test]
fn a_timer_card_on_another_day_is_not_gone_back_to() {
    let mut view = DayView::new(false);
    Facts::day(Some("2026-11-06"), Some("2026-11-02")).begin(&mut view);
    let running = TimerWords {
        title: "Essay".into(),
        line: "13 min left".into(),
        ..TimerWords::default()
    };
    finish(&mut view, &[], &Value::Null, running);
    let all = FocusHooks {
        opener: true,
        hook: false,
        starter: false,
    };
    assert_eq!(view.start_focus_plan(&all, "essay", 3).action, "session");
}
