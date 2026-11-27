//! Shared sheet rules, settings copy and the sign-in checks (P5-C1). Expected sentences are the
//! ones today's Python and the desktop tests already pin. Clock-reading tests share `CLOCK_LOCK`
//! and leave the engine on the 24-hour clock.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::copy::{
    self, ACCOUNT_SAVED, CREATE_NOTE, HELP_PLANNING, HELP_PLANNING_MATERIAL, RECOVERY_SAVE,
    RECOVERY_WAIT, RESET_NOTE, SPOTIFY_TONE_NOTE, WRITE_FAILED,
};
use flexweek_app::views::sheet_rules::{
    self, BLOCK_REFUSED, CUTOFFS, REPEAT_NOTE, SLOT_HINT, SPREAD_NOTHING,
};
use flexweek_engine::ErrorKind;
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

/// The engine clock is one process-wide flag. These tests take it in turn and put 24-hour time back.
struct ClockGuard {
    _held: MutexGuard<'static, ()>,
}

fn clock_lock() -> ClockGuard {
    static CLOCK_LOCK: Mutex<()> = Mutex::new(());
    let held = CLOCK_LOCK
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    set_clock_24h(true);
    ClockGuard { _held: held }
}

impl Drop for ClockGuard {
    fn drop(&mut self) {
        set_clock_24h(true);
    }
}

fn kind_message(error: flexweek_engine::EngineError) -> (ErrorKind, String) {
    (error.kind, error.message)
}

fn ids(count: usize) -> Value {
    Value::Array(
        (0..count)
            .map(|index| Value::String(format!("item-{index}")))
            .collect(),
    )
}

fn part(counts: [usize; 3]) -> Value {
    json!({
        "added": ids(counts[0]),
        "changed": ids(counts[1]),
        "removed": ids(counts[2]),
    })
}

fn changes(weeks: [usize; 3], homework: [usize; 3], routines: [usize; 3], settings: bool) -> Value {
    json!({
        "changes": {
            "weeks": part(weeks),
            "assignments": part(homework),
            "routines": part(routines),
            "preferences_changed": settings,
        }
    })
}

fn preset(category: Option<&str>, day: i64, start: &str, duration: i64, week: &str) -> Value {
    let category = match category {
        Some(name) => Value::String(name.to_string()),
        None => Value::Null,
    };
    json!({
        "id": "fresh-id",
        "category": category,
        "day": day,
        "start": start,
        "duration_min": duration,
        "week_start": week,
    })
}

#[test]
fn the_repeat_note_says_to_pick_every_day() {
    assert_eq!(REPEAT_NOTE, "Pick every day it happens.");
}

#[test]
fn a_start_in_a_meal_window_is_guessed_as_meals() {
    assert_eq!(
        sheet_rules::guess_locked_category("07:30").unwrap(),
        "meals"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("12:30").unwrap(),
        "meals"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("18:00").unwrap(),
        "meals"
    );
}

#[test]
fn a_start_in_school_hours_is_guessed_as_class() {
    assert_eq!(
        sheet_rules::guess_locked_category("09:00").unwrap(),
        "class"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("08:00").unwrap(),
        "class"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("14:29").unwrap(),
        "class"
    );
}

#[test]
fn three_days_in_a_row_are_named_as_a_range() {
    assert_eq!(
        sheet_rules::day_range_words(&[1, 2, 3], "").unwrap(),
        "Tue\u{2013}Thu"
    );
}

#[test]
fn the_reset_note_names_recovery_codes() {
    assert_eq!(
        RESET_NOTE,
        "Use one of the recovery codes you saved when you made your account. Lost them too? Create a new account and import a backup file, or start fresh."
    );
}

#[test]
fn the_create_note_reminds_the_student_to_export_a_backup() {
    assert_eq!(
        CREATE_NOTE,
        "FlexWeek fits homework around school and sports. Your week is saved on this computer, under this account. Export a backup file now and then (Settings > This computer > Manage account)."
    );
}

#[test]
fn a_failed_save_says_to_choose_another_folder() {
    assert_eq!(
        WRITE_FAILED,
        "Couldn't save there. Choose another folder, like Documents."
    );
}

#[test]
fn a_saved_backup_says_to_keep_it_private() {
    assert_eq!(
        ACCOUNT_SAVED,
        "Saved your backup file to {path}. Keep it private: it has all your weeks and homework."
    );
}

#[test]
fn one_added_week_is_singular() {
    let said = copy::transfer_summary(&changes([1, 0, 0], [0, 0, 0], [0, 0, 0], false)).unwrap();
    assert_eq!(said, "adds 1 week.");
}

#[test]
fn replaced_weeks_say_of_your() {
    let said = copy::transfer_summary(&changes([0, 2, 0], [0, 0, 0], [0, 0, 0], false)).unwrap();
    assert_eq!(said, "replaces 2 of your weeks.");
}

#[test]
fn deleted_weeks_say_deletes() {
    let said = copy::transfer_summary(&changes([0, 0, 1], [0, 0, 0], [0, 0, 0], false)).unwrap();
    assert_eq!(said, "deletes 1 of your weeks that isn't in the backup.");
}

#[test]
fn deleted_homework_says_deletes() {
    let said = copy::transfer_summary(&changes([0, 0, 0], [0, 0, 2], [0, 0, 0], false)).unwrap();
    assert_eq!(
        said,
        "It also deletes 2 of your homework that aren't in the backup."
    );
}

#[test]
fn a_backup_that_changes_nothing_says_so() {
    let said = copy::transfer_summary(&changes([0, 0, 0], [0, 0, 0], [0, 0, 0], false)).unwrap();
    assert_eq!(said, "Nothing in it is different from your account.");
}

#[test]
fn an_empty_password_is_named_before_the_server() {
    assert_eq!(
        copy::sign_in_problem("sam", "").unwrap(),
        "Type your password."
    );
}

#[test]
fn a_start_outside_meals_and_school_is_an_extra() {
    assert_eq!(
        sheet_rules::guess_locked_category("15:00").unwrap(),
        "extra"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("14:30").unwrap(),
        "extra"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("19:30").unwrap(),
        "extra"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("21:00").unwrap(),
        "extra"
    );
    assert_eq!(
        sheet_rules::guess_locked_category("13:00").unwrap(),
        "class"
    );
}

#[test]
fn day_ranges_join_the_last_piece_with_and() {
    assert_eq!(
        sheet_rules::day_range_words(&[0, 1, 2, 3, 4], "").unwrap(),
        "Mon\u{2013}Fri"
    );
    assert_eq!(
        sheet_rules::day_range_and_words(&[4, 5], "").unwrap(),
        "Fri and Sat"
    );
    assert_eq!(
        sheet_rules::day_range_and_words(&[0, 2, 4], "").unwrap(),
        "Mon, Wed and Fri"
    );
    assert_eq!(
        sheet_rules::day_range_and_words(&[0, 1, 2, 4], "").unwrap(),
        "Mon\u{2013}Wed and Fri"
    );
    assert_eq!(sheet_rules::day_range_words(&[], "").unwrap(), "");
    assert_eq!(
        sheet_rules::day_range_words(&[0, 1, 2], "2026-10-07").unwrap(),
        "Wed\u{2013}Fri"
    );
}

#[test]
fn a_day_past_the_week_is_an_index_error_and_the_last_day_wraps() {
    let error = sheet_rules::short_day_name("", 7).unwrap_err();
    assert_eq!(
        kind_message(error),
        (ErrorKind::Index, "tuple index out of range".to_string())
    );
    assert_eq!(sheet_rules::short_day_name("", -1).unwrap(), "Sun");
    assert_eq!(sheet_rules::full_day_name("", -1).unwrap(), "Sunday");
    assert_eq!(sheet_rules::short_day_name("2026-10-07", 0).unwrap(), "Wed");
}

#[test]
fn turning_days_keeps_the_weekday_and_names_only_dates_that_moved() {
    let (kept, moved) =
        sheet_rules::turn_days_keeping_weekdays(&[0, 2], "2026-10-05", "2026-10-07").unwrap();
    assert_eq!(kept, vec![0, 5]);
    assert_eq!(moved, vec![(0, 5)]);
    assert!(sheet_rules::first_day_changed("2026-10-05", "2026-10-07").unwrap());
    assert!(!sheet_rules::first_day_changed("2026-10-05", "2026-10-12").unwrap());
    assert!(!sheet_rules::first_day_changed("", "2026-10-07").unwrap());
    assert_eq!(
        sheet_rules::same_weekday(0, "2026-10-05", "2026-10-07").unwrap(),
        5
    );
    let (same, none) =
        sheet_rules::turn_days_keeping_weekdays(&[2, 0], "2026-10-05", "2026-10-05").unwrap();
    assert_eq!(same, vec![0, 2]);
    assert!(none.is_empty());
}

#[test]
fn moved_day_names_hide_the_month_until_the_month_changes() {
    assert_eq!(
        sheet_rules::moved_day_names(0, "2026-10-05", 5, "2026-10-07").unwrap(),
        ("Monday 5".to_string(), "Monday 12".to_string())
    );
    assert_eq!(
        sheet_rules::moved_day_names(5, "2026-10-26", 0, "2026-11-02").unwrap(),
        (
            "Saturday 31 October".to_string(),
            "Monday 2 November".to_string()
        )
    );
    assert!(sheet_rules::moved_across_months(5, "2026-10-26", 0, "2026-11-02").unwrap());
    assert!(!sheet_rules::moved_across_months(0, "2026-10-05", 5, "2026-10-07").unwrap());
}

#[test]
fn a_moved_days_note_is_empty_for_none_and_joins_several() {
    assert_eq!(sheet_rules::moved_days_note(&[]), "");
    assert_eq!(
        sheet_rules::moved_days_note(&[("Monday 5".into(), "Monday 12".into())]),
        "Monday 5 isn't in this week any more, so it moved to Monday 12."
    );
    assert_eq!(
        sheet_rules::moved_days_note(&[
            ("Monday 5".into(), "Monday 12".into()),
            ("Wednesday 7".into(), "Friday 14".into()),
        ]),
        "Monday 5 and Wednesday 7 aren't in this week any more, so they moved to Monday 12 and Friday 14."
    );
}

#[test]
fn a_preset_keeps_the_callers_id_and_applies_the_category_table() {
    let class = sheet_rules::preset_locked(&preset(Some("class"), 3, "16:00", 60, "")).unwrap();
    assert_eq!(
        class,
        json!({
            "id": "fresh-id",
            "kind": "locked",
            "title": "School",
            "days": [0, 1, 2, 3, 4],
            "start": "08:00",
            "duration_min": 390,
            "category": "class",
        })
    );
    let wednesday =
        sheet_rules::preset_locked(&preset(Some("class"), 3, "16:00", 60, "2026-10-07")).unwrap();
    assert_eq!(wednesday["days"], json!([0, 1, 2, 5, 6]));
    let meals = sheet_rules::preset_locked(&preset(Some("meals"), 3, "16:00", 60, "")).unwrap();
    assert_eq!(meals["title"], json!("Meals"));
    assert_eq!(meals["start"], json!("18:00"));
    assert_eq!(meals["duration_min"], json!(30));
    assert_eq!(meals["days"], json!([3]));
    let homework =
        sheet_rules::preset_locked(&preset(Some("assignments"), 2, "16:00", 45, "")).unwrap();
    assert_eq!(homework["title"], json!("Homework"));
    assert_eq!(homework["start"], json!("16:00"));
    assert_eq!(homework["duration_min"], json!(60));
    assert_eq!(homework["days"], json!([2]));
    let unknown = sheet_rules::preset_locked(&preset(None, 1, "10:00", 30, "")).unwrap();
    assert_eq!(unknown["title"], json!(""));
    assert_eq!(unknown["category"], Value::Null);
    assert_eq!(unknown["start"], json!("10:00"));
    assert_eq!(unknown["duration_min"], json!(30));
    assert_eq!(unknown["days"], json!([1]));
    let kept = sheet_rules::preset_locked(&preset(Some("class"), 1, "10:00", 60, "")).unwrap();
    assert_eq!(kept["title"], json!("School"));
    assert_eq!(kept["start"], json!("10:00"));
    assert_eq!(kept["duration_min"], json!(60));
    assert_eq!(kept["days"], json!([1]));
}

#[test]
fn spread_words_name_the_sessions_and_the_due_day() {
    let due = "2026-10-11";
    let today = "2026-10-09";
    assert_eq!(
        sheet_rules::spread_words(&json!([]), due, today).unwrap(),
        SPREAD_NOTHING
    );
    assert_eq!(
        sheet_rules::spread_words(
            &json!([
                {"duration_min": 60, "date": "2026-10-09"},
                {"duration_min": 60, "date": "2026-10-10"}
            ]),
            due,
            today
        )
        .unwrap(),
        "2 \u{00d7} 60 min on different days before it's due Sun 11 Oct."
    );
    assert_eq!(
        sheet_rules::spread_words(&json!([{"duration_min": 60}]), due, today).unwrap(),
        "60 min in one session before it's due Sun 11 Oct."
    );
    assert_eq!(
        sheet_rules::spread_words(
            &json!([
                {"duration_min": 60, "date": "2026-10-09"},
                {"duration_min": 60, "date": "2026-10-09"},
                {"duration_min": 45, "date": "2026-10-10"}
            ]),
            due,
            today
        )
        .unwrap(),
        "2 \u{00d7} 60 min and 45 min over 2 days before it's due Sun 11 Oct."
    );
    let missing = sheet_rules::spread_words(&json!([{}]), due, today).unwrap_err();
    assert_eq!(
        kind_message(missing),
        (ErrorKind::Key, "duration_min".to_string())
    );
    let number = sheet_rules::spread_words(&json!(3), due, today).unwrap_err();
    assert_eq!(
        kind_message(number),
        (ErrorKind::Type, "'int' object is not iterable".to_string())
    );
}

#[test]
fn today_from_words_rounds_up_to_the_next_quarter_hour() {
    let _clock = clock_lock();
    assert_eq!(
        sheet_rules::today_from_words(15 * 60 + 7),
        "Today from 15:15 onward."
    );
    assert_eq!(
        sheet_rules::today_from_words(15 * 60 + 15),
        "Today from 15:15 onward."
    );
    assert_eq!(
        sheet_rules::today_from_words(5 * 60 + 10),
        "Today from 05:15 onward."
    );
    assert_eq!(sheet_rules::today_from_words(23 * 60 + 50), "");
}

#[test]
fn only_a_times_own_am_or_pm_keeps_a_no_break_space() {
    assert_eq!(
        sheet_rules::unbroken_time("PM club AMERICAN: Mon 4:45\u{2013}5:45 PM \u{2192} Tue 7 AM"),
        "PM club AMERICAN: Mon 4:45\u{2013}5:45\u{00a0}PM \u{2192} Tue 7\u{00a0}AM"
    );
}

#[test]
fn late_summary_treats_only_zero_as_nothing() {
    assert_eq!(sheet_rules::late_summary(0), "Nothing needs to move.");
    assert_eq!(sheet_rules::late_summary(1), "1 task moves");
    assert_eq!(sheet_rules::late_summary(2), "2 tasks move");
    assert_eq!(sheet_rules::late_summary(-1), "-1 tasks move");
}

#[test]
fn a_late_move_on_the_24_hour_clock_names_both_ends() {
    let _clock = clock_lock();
    let said = sheet_rules::late_move(
        &json!({"from_start": "16:45", "to_start": "07:00", "from_day": 0, "to_day": 1}),
        &json!({"duration_min": 60}),
        "Club",
        "",
    )
    .unwrap();
    assert_eq!(
        said,
        "Club: Mon 16:45\u{2013}17:45 \u{2192} Tue 07:00\u{2013}08:00"
    );
    assert_eq!(
        sheet_rules::late_move(
            &json!({"from_start": "16:45", "to_start": "07:00"}),
            &json!({}),
            "Club",
            ""
        )
        .unwrap(),
        "Club: from 16:45 to 07:00"
    );
    assert_eq!(
        sheet_rules::late_move(
            &json!({"to_start": "07:00", "to_day": 1}),
            &json!({}),
            "Club",
            ""
        )
        .unwrap(),
        "Club, placed Tue 07:00"
    );
    assert_eq!(
        sheet_rules::late_move(&json!({"to_start": "07:00"}), &json!({}), "Club", "").unwrap(),
        "Club: placed at 07:00"
    );
    assert_eq!(
        sheet_rules::late_move(&json!({"from_start": "16:45"}), &json!({}), "Club", "").unwrap(),
        "Club: moves off 16:45 and isn't placed"
    );
    assert_eq!(
        sheet_rules::late_move(&json!({}), &json!({}), "Club", "").unwrap(),
        "Club: not placed"
    );
}

#[test]
fn the_twelve_hour_clock_keeps_am_and_pm_with_the_time() {
    let _clock = clock_lock();
    set_clock_24h(false);
    assert_eq!(
        sheet_rules::today_from_words(15 * 60 + 7),
        "Today from 3:15 PM onward."
    );
    assert_eq!(
        sheet_rules::today_from_words(5 * 60 + 10),
        "Today from 5:15 AM onward."
    );
    assert_eq!(
        sheet_rules::spread_words(
            &json!([{"duration_min": 60, "date": "2026-10-09"}]),
            "2026-10-11T15:00",
            "2026-10-09"
        )
        .unwrap(),
        "60 min in one session before it's due Sun 11 Oct, 3:00 PM."
    );
    assert_eq!(
        sheet_rules::late_move(
            &json!({"from_start": "11:30", "to_start": "23:00", "from_day": 0, "to_day": 1}),
            &json!({"duration_min": 60}),
            "Club",
            ""
        )
        .unwrap(),
        "Club: Mon 11:30\u{00a0}AM\u{2013}12:30\u{00a0}PM \u{2192} Tue 11\u{00a0}PM\u{2013}12\u{00a0}AM"
    );
    assert_eq!(
        sheet_rules::late_move(
            &json!({"from_start": "16:45", "to_start": "07:00"}),
            &json!({}),
            "Club",
            ""
        )
        .unwrap(),
        "Club: from 4:45\u{00a0}PM to 7:00\u{00a0}AM"
    );
    assert_eq!(
        sheet_rules::late_move(
            &json!({"to_start": "07:00", "to_day": 1}),
            &json!({}),
            "Club",
            ""
        )
        .unwrap(),
        "Club, placed Tue 7:00\u{00a0}AM"
    );
    assert_eq!(
        sheet_rules::late_move(&json!({"to_start": "15:00"}), &json!({}), "Club", "").unwrap(),
        "Club: placed at 3:00\u{00a0}PM"
    );
    assert_eq!(
        sheet_rules::late_move(&json!({"from_start": "23:00"}), &json!({}), "Club", "").unwrap(),
        "Club: moves off 11:00\u{00a0}PM and isn't placed"
    );
}

#[test]
fn restore_points_are_singular_only_for_one_week() {
    for (count, words) in [
        (0, "0 weeks"),
        (1, "1 week"),
        (2, "2 weeks"),
        (12, "12 weeks"),
    ] {
        let point = json!({"label": "Before import", "created_at": "2026-11-01 09:00", "weeks_count": count});
        assert_eq!(
            copy::restore_parts(&point).unwrap(),
            (
                "Before import".to_string(),
                format!("2026-11-01 09:00 \u{00b7} {words}")
            )
        );
        assert_eq!(
            copy::restore_row(&point).unwrap(),
            format!("Before import \u{00b7} 2026-11-01 09:00 \u{00b7} {words}")
        );
    }
    let missing = json!({});
    assert_eq!(
        copy::restore_parts(&missing).unwrap(),
        ("None".to_string(), " \u{00b7} 0 weeks".to_string())
    );
    let present_null = json!({"weeks_count": null, "week_count": 4});
    assert_eq!(
        copy::restore_parts(&present_null).unwrap().1,
        " \u{00b7} None weeks"
    );
}

#[test]
fn a_restore_summary_counts_weeks_and_homework_and_refuses_a_number() {
    assert_eq!(copy::restore_summary(&json!({})).unwrap(), "");
    assert_eq!(copy::restore_summary(&Value::Null).unwrap(), "");
    let zeros = json!({"changes": {"weeks": {"added": [], "changed": [], "removed": []}, "assignments": {}}});
    assert_eq!(
        copy::restore_summary(&zeros).unwrap(),
        "0 added, 0 changed, 0 removed."
    );
    let bad = json!({"changes": {"weeks": {"added": 1}}});
    assert_eq!(
        kind_message(copy::restore_summary(&bad).unwrap_err()),
        (
            ErrorKind::Type,
            "object of type 'int' has no len()".to_string()
        )
    );
}

#[test]
fn transfer_sentences_match_the_import_question() {
    assert_eq!(
        copy::transfer_summary(&changes([3, 0, 0], [0, 0, 0], [0, 0, 0], false)).unwrap(),
        "adds 3 weeks."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 4], [0, 0, 0], [0, 0, 0], false)).unwrap(),
        "deletes 4 of your weeks that aren't in the backup."
    );
    assert_eq!(
        copy::transfer_summary(&changes([1, 2, 0], [0, 0, 0], [0, 0, 0], false)).unwrap(),
        "adds 1 week and replaces 2 of your weeks."
    );
    assert_eq!(
        copy::transfer_summary(&changes([2, 1, 3], [0, 0, 0], [0, 0, 0], false)).unwrap(),
        "adds 2 weeks, replaces 1 of your weeks, and deletes 3 of your weeks that aren't in the backup."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [1, 0, 0], [0, 0, 0], false)).unwrap(),
        "1 homework changes."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [1, 1, 0], [0, 0, 0], false)).unwrap(),
        "2 homework change."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [0, 0, 0], [0, 1, 0], false)).unwrap(),
        "1 routine changes."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [0, 0, 0], [1, 2, 0], false)).unwrap(),
        "3 routines change."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [0, 0, 0], [0, 0, 1], false)).unwrap(),
        "It also deletes 1 of your routines that isn't in the backup."
    );
    assert_eq!(
        copy::transfer_summary(&changes([0, 0, 0], [0, 0, 0], [0, 0, 0], true)).unwrap(),
        "Your settings will be replaced."
    );
}

#[test]
fn seen_words_use_the_weekday_the_caller_passes() {
    let seen = "1";
    assert_eq!(
        copy::seen_words(None, 0, "Friday").unwrap(),
        "Not synced yet"
    );
    assert_eq!(
        copy::seen_words(Some(""), 0, "Friday").unwrap(),
        "Not synced yet"
    );
    assert_eq!(
        copy::seen_words(Some(seen), 1 + 30_000, "Friday").unwrap(),
        "Synced just now"
    );
    assert_eq!(
        copy::seen_words(Some(seen), 1 + 2 * 60_000, "Friday").unwrap(),
        "Synced 2 min ago"
    );
    assert_eq!(
        copy::seen_words(Some(seen), 1 + 3 * 3_600_000, "Friday").unwrap(),
        "Synced 3 h ago"
    );
    assert_eq!(
        copy::seen_words(Some(seen), 1 + 3 * 86_400_000, "Friday").unwrap(),
        "Last seen on Friday"
    );
}

#[test]
fn sign_in_and_sign_up_name_the_first_problem() {
    assert_eq!(
        copy::sign_in_problem("", "long-enough-pw").unwrap(),
        "Type your username."
    );
    assert_eq!(
        copy::sign_in_problem("ab", "long-enough-pw").unwrap(),
        "No FlexWeek username looks like that. Usernames are 3\u{2013}32 letters, numbers or underscores."
    );
    assert_eq!(
        copy::sign_in_problem("sam", "short-pass").unwrap(),
        "Passwords have at least 12 characters. Try again, or choose Forgot password."
    );
    assert_eq!(copy::sign_in_problem("sam", "long-enough-pw").unwrap(), "");
    assert!(!copy::username_ok("ab"));
    assert!(copy::username_ok("abc"));
    assert!(copy::username_ok("a_b"));
    assert!(!copy::username_ok("a b"));
    assert!(!copy::username_ok(&"a".repeat(33)));
    assert!(copy::username_ok(&"a".repeat(32)));
    assert_eq!(
        copy::sign_up_problem("", "long-enough-pw").unwrap(),
        "Choose a username."
    );
    assert_eq!(
        copy::sign_up_problem("ab", "long-enough-pw").unwrap(),
        "Use 3 to 32 letters, numbers or underscores, with no spaces."
    );
    assert_eq!(
        copy::sign_up_problem("sam", "").unwrap(),
        "Choose a password with at least 12 characters."
    );
    assert_eq!(
        copy::sign_up_problem("sam", &"p".repeat(129)).unwrap(),
        "Use 128 characters or fewer."
    );
    assert_eq!(
        copy::sign_up_problem("sam", &"p".repeat(11)).unwrap(),
        "Add 1 more character. Passwords need at least 12 characters."
    );
    assert_eq!(
        copy::short_password_needed(2),
        "Add 2 more characters. Passwords need at least 12 characters."
    );
    assert_eq!(copy::sign_up_problem("sam", &"p".repeat(12)).unwrap(), "");
}

#[test]
fn help_keys_drop_only_the_other_rows_material_does_not_answer() {
    let material = copy::help_keys(true, true, true);
    assert!(material.iter().any(|row| row.0 == "[1] to [5]"));
    assert!(material.iter().any(|row| row.0 == "[T]"));
    assert!(material.iter().any(|row| row.0 == "[Ctrl]+[N]"));
    assert!(!material.iter().any(|row| row.0 == "[Ctrl]+[K]"));
    assert!(!material.iter().any(|row| row.0 == "[B] or [Esc]"));
    assert_eq!(copy::keys_words("[Ctrl]+[N]"), "Ctrl+N");
    assert_eq!(
        copy::key_parts("[B] or [Esc]"),
        vec![
            ("B".to_string(), true),
            ("or".to_string(), false),
            ("Esc".to_string(), true),
        ]
    );
}

#[test]
fn the_first_lines_of_notes_drop_markers() {
    let notes = "## What changed\n===\n\n- A thing\n**bold**\n-\n--\n---\n";
    assert_eq!(
        copy::first_lines(notes, 6),
        "What changed\n\u{2022}  A thing\nbold\n-\n--"
    );
    assert_eq!(copy::first_lines(notes, 1), "What changed");
    assert_eq!(
        copy::first_lines("- A thing\nSecond", 0),
        "\u{2022}  A thing\nSecond"
    );
}

#[test]
fn ring_days_use_the_whole_week_the_weekdays_and_the_weekend() {
    assert_eq!(
        copy::ring_days(&[0, 1, 2, 3, 4, 5, 6]).unwrap(),
        "every day"
    );
    assert_eq!(
        copy::ring_days(&[0, 1, 2, 3, 4]).unwrap(),
        "Monday to Friday"
    );
    assert_eq!(copy::ring_days(&[6, 5]).unwrap(), "Saturday and Sunday");
    assert_eq!(copy::ring_days(&[]).unwrap(), "no days");
    assert_eq!(copy::ring_days(&[-1]).unwrap(), "Sunday");
    assert_eq!(copy::ring_days(&[0, 0, 1]).unwrap(), "Mon and Tue");
    assert_eq!(
        kind_message(copy::ring_days(&[7]).unwrap_err()),
        (ErrorKind::Index, "tuple index out of range".to_string())
    );
}

#[test]
fn sync_countdown_tries_and_the_clock_warning_use_todays_words() {
    assert_eq!(copy::sync_state(&json!({}), false).unwrap(), "off");
    let quiet = json!({"syncing": false, "last_error": null, "last_sync_ms": null});
    assert_eq!(copy::sync_state(&quiet, true).unwrap(), "idle");
    assert_eq!(
        copy::sync_state(
            &json!({"syncing": true, "last_error": null, "last_sync_ms": null}),
            true
        )
        .unwrap(),
        "syncing"
    );
    assert_eq!(
        copy::sync_state(
            &json!({"syncing": false, "last_error": "could not reach", "last_sync_ms": 5}),
            true
        )
        .unwrap(),
        "problem"
    );
    assert_eq!(
        copy::sync_state(
            &json!({"syncing": false, "last_error": null, "last_sync_ms": 5}),
            true
        )
        .unwrap(),
        "synced"
    );
    assert_eq!(
        kind_message(copy::sync_state(&json!({}), true).unwrap_err()),
        (ErrorKind::Key, "syncing".to_string())
    );
    assert_eq!(copy::countdown_words(65), "Code works for 1:05");
    assert_eq!(copy::countdown_words(-3), "Code works for 0:00");
    assert_eq!(copy::tries_words(1), "1 try left");
    assert_eq!(copy::tries_words(0), "0 tries left");
    assert_eq!(
        copy::pair_problem("expired"),
        "That code has expired. Start a new one."
    );
    assert_eq!(
        copy::pair_problem("too_many_tries"),
        "Too many wrong tries. Start a new code."
    );
    assert_eq!(copy::pair_problem("open"), "");
    assert_eq!(copy::clock_warning_words(0), "");
    assert_eq!(
        copy::clock_warning_words(1),
        "Your phone's clock looks wrong. 1 change was held back."
    );
    assert_eq!(
        copy::clock_warning_words(2),
        "Your phone's clock looks wrong. 2 changes were held back."
    );
}

#[test]
fn recovery_codes_and_the_shared_sentences_keep_their_marks() {
    assert_eq!(
        copy::recovery_status(&json!(0)),
        "No unused recovery codes remain. Replace them before signing out."
    );
    assert_eq!(
        copy::recovery_status(&json!(1)),
        "1 unused recovery code remains."
    );
    assert_eq!(
        copy::recovery_status(&json!(true)),
        "1 unused recovery code remains."
    );
    assert_eq!(
        copy::recovery_status(&json!(1.0)),
        "1 unused recovery code remains."
    );
    assert_eq!(
        copy::recovery_status(&json!(2)),
        "2 unused recovery codes remain."
    );
    assert_eq!(
        copy::recovery_status(&Value::Null),
        "Couldn't find out how many recovery codes are left."
    );
    assert_eq!(
        RECOVERY_WAIT,
        "Turn on \u{201c}I have saved these codes\u{201d} to continue."
    );
    assert_eq!(RECOVERY_SAVE, "Save\u{2026}");
    assert!(SLOT_HINT.contains('\u{00a0}'));
    assert_eq!(
        CUTOFFS,
        [
            "20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00"
        ]
    );
    assert!(BLOCK_REFUSED.contains("Check its title, days and times."));
    assert!(HELP_PLANNING.contains("From the keyboard, press Ctrl+K and type Plan."));
    assert_eq!(
        HELP_PLANNING_MATERIAL,
        "Add homework with its due date and length. Press Plan my homework and FlexWeek finds free time for it in your study hours, around your fixed times, before it's due. Homework that already has a time keeps it, unless that time has passed, the work isn't finished and you didn't pin it. Replan all starts fresh but keeps pinned homework. Anything that doesn't fit stays under Not placed yet, and Details says why."
    );
    assert!(!HELP_PLANNING_MATERIAL.contains("Ctrl+K"));
    assert_eq!(
        SPOTIFY_TONE_NOTE,
        "Plays when a block starts if the alarm sound is Spotify, or when focus starts if the focus sound is Spotify. It plays in your Spotify app, and stopping the alarm stops it. Reminders before a block and the end of a focus session play Chime. Without the Spotify app, the link opens and Chime rings too."
    );
}
