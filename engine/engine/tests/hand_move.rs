//! The rule for a block moved by hand. Expected values are worked out from the rule (homework the
//! student moves stays where they put it; nothing else is pinned), not recorded from the output.

mod common;

use common::desk::{fresh_ids, with};
use common::{Dump, solve_legacy};
use flexweek_engine::desk::hand_move::{HandDrop, HandMove, WeekClock, hand_move};
use flexweek_engine::solver::block_from_value;
use serde_json::{Value, json};

const WEEK: &str = "2026-10-19";
const MONDAY: i64 = 0;
const TUESDAY: i64 = 1;
const THURSDAY: i64 = 3;
const SATURDAY: i64 = 5;
const EARLY_MONDAY: &str = "2026-10-19";
const EARLY_MIN: i64 = 8 * 60;
const AFTERNOON: i64 = 14 * 60 + 30;
const HOMEWORK_MIN: i64 = 90;
const MINUTES_IN_DAY: i64 = 1440;

fn homework() -> Value {
    json!({
        "id": "alg", "title": "Algebra set 4", "kind": "flexible", "days": [MONDAY],
        "start": "14:30", "duration_min": HOMEWORK_MIN, "category": "assignments",
        "assignment_id": "algebra-4",
    })
}

fn assignments() -> Value {
    json!({"algebra-4": {"id": "algebra-4", "title": "Algebra set 4", "due": "2026-10-23T23:59"}})
}

fn drop_of(id: &str, from: i64, to: i64, start: i64, end: i64) -> HandDrop<'_> {
    HandDrop {
        block_id: id,
        from_day: from,
        to_day: to,
        start_min: start,
        end_min: end,
    }
}

fn move_at(
    blocks: &[Value],
    drop: &HandDrop<'_>,
    now_iso: &str,
    now_min: i64,
    assignments: &Value,
) -> HandMove {
    let clock = WeekClock {
        week_start: WEEK,
        now_iso,
        now_min,
    };
    hand_move(&json!(blocks), drop, &clock, assignments, &mut fresh_ids()).expect("the rule runs")
}

fn moved(blocks: &[Value], drop: &HandDrop<'_>) -> HandMove {
    move_at(blocks, drop, EARLY_MONDAY, EARLY_MIN, &assignments())
}

fn landed(result: HandMove, id: &str) -> Value {
    match result {
        HandMove::Moved { blocks, .. } => blocks
            .into_iter()
            .find(|block| block["id"] == id)
            .unwrap_or_else(|| panic!("no block {id} after the move")),
        HandMove::Refused(words) => panic!("the move was refused: {words}"),
    }
}

fn refusal(result: HandMove) -> String {
    match result {
        HandMove::Refused(words) => words,
        HandMove::Moved { .. } => String::new(),
    }
}

#[test]
fn homework_moved_to_another_day_keeps_its_time_and_length_and_is_pinned() {
    let block = landed(
        moved(
            &[homework()],
            &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
        ),
        "alg",
    );
    assert_eq!(block["days"], json!([TUESDAY]), "the day changed");
    assert_eq!(block["start"], json!("14:30"), "the time stayed");
    assert_eq!(
        block["duration_min"],
        json!(HOMEWORK_MIN),
        "the length stayed"
    );
    assert_eq!(
        block["pinned"],
        json!(true),
        "homework moved by hand is pinned"
    );
}

#[test]
fn a_fixed_one_off_block_moved_by_hand_is_not_pinned() {
    let soccer = json!({
        "id": "soccer", "title": "Soccer", "kind": "locked", "days": [MONDAY],
        "start": "17:00", "duration_min": 60, "category": "sport",
    });
    let block = landed(
        moved(
            &[soccer],
            &drop_of("soccer", MONDAY, THURSDAY, 17 * 60, 18 * 60),
        ),
        "soccer",
    );
    assert_eq!(block["days"], json!([THURSDAY]), "the fixed block moved");
    assert_ne!(block["pinned"], json!(true), "a fixed block is not pinned");
}

#[test]
fn a_flexible_block_with_no_homework_behind_it_is_not_pinned() {
    let chore = json!({
        "id": "chore", "title": "Tidy up", "kind": "flexible", "days": [MONDAY],
        "start": "10:00", "duration_min": 30,
    });
    let block = landed(
        moved(
            &[chore],
            &drop_of("chore", MONDAY, TUESDAY, 10 * 60, 10 * 60 + 30),
        ),
        "chore",
    );
    assert_eq!(block["days"], json!([TUESDAY]), "the block moved");
    assert_ne!(block["pinned"], json!(true), "no homework, no pin");
}

#[test]
fn waiting_homework_is_placed_where_it_is_let_go_and_pinned() {
    let waiting = json!({
        "id": "alg", "title": "Algebra set 4", "kind": "flexible", "days": [0, 1, 2, 3, 4],
        "duration_min": HOMEWORK_MIN, "category": "assignments", "assignment_id": "algebra-4",
    });
    let at = 14 * 60;
    let block = landed(
        moved(&[waiting], &drop_of("alg", -1, THURSDAY, at, at + 45)),
        "alg",
    );
    assert_eq!(
        block["start"],
        json!("14:00"),
        "it starts where it was let go"
    );
    assert_eq!(block["days"], json!([THURSDAY]), "it is on that day only");
    assert_eq!(
        block["duration_min"],
        json!(45),
        "it lasts as long as the drop"
    );
    assert_eq!(block["pinned"], json!(true), "placed by hand, so pinned");
}

#[test]
fn finished_homework_is_refused() {
    let done = with(homework(), json!({"completed": true}));
    let words = refusal(moved(
        &[done],
        &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
    ));
    assert_eq!(words, "That's finished, so it stayed where it was.");
}

#[test]
fn a_block_that_is_not_in_the_week_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of(
            "nothing",
            MONDAY,
            TUESDAY,
            AFTERNOON,
            AFTERNOON + HOMEWORK_MIN,
        ),
    ));
    assert_eq!(words, "That block is not in this week, so nothing moved.");
}

#[test]
fn a_day_outside_the_week_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of("alg", MONDAY, 7, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
    ));
    assert_eq!(
        words,
        "That day is not in this week, so it stayed where it was."
    );
}

#[test]
fn an_end_that_is_not_after_the_start_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON),
    ));
    assert_eq!(
        words,
        "The end has to come after the start, so it stayed where it was."
    );
}

#[test]
fn a_start_before_midnight_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of("alg", MONDAY, TUESDAY, -5, 55),
    ));
    assert_eq!(
        words,
        "That's outside the hours FlexWeek plans in, so it stayed where it was."
    );
}

#[test]
fn an_end_past_midnight_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of(
            "alg",
            MONDAY,
            TUESDAY,
            MINUTES_IN_DAY - 60,
            MINUTES_IN_DAY + 1,
        ),
    ));
    assert_eq!(
        words,
        "That's outside the hours FlexWeek plans in, so it stayed where it was."
    );
}

#[test]
fn an_end_after_the_due_time_is_refused() {
    let words = refusal(moved(
        &[homework()],
        &drop_of("alg", MONDAY, SATURDAY, 10 * 60, 11 * 60),
    ));
    assert_eq!(
        words,
        "That ends after it's due, so it stayed where it was."
    );
}

#[test]
fn a_start_that_has_already_passed_is_refused_in_the_words_of_the_calendar() {
    let wednesday_noon = 12 * 60;
    let words = refusal(move_at(
        &[homework()],
        &drop_of("alg", MONDAY, 2, 11 * 60, 12 * 60 + 30),
        "2026-10-21",
        wednesday_noon,
        &assignments(),
    ));
    assert_eq!(
        words,
        "That time has passed. Choose 12:00 or later today, or another day."
    );
}

#[test]
fn a_day_already_over_offers_no_time_later_today() {
    let words = refusal(move_at(
        &[homework()],
        &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
        "2026-10-21",
        12 * 60,
        &assignments(),
    ));
    assert_eq!(
        words,
        "That time has passed. The day is over, so choose another day."
    );
}

#[test]
fn another_block_there_is_allowed_and_named() {
    let soccer = json!({
        "id": "soccer", "title": "Soccer", "kind": "locked", "days": [TUESDAY],
        "start": "15:00", "duration_min": 60, "category": "sport",
    });
    let result = moved(
        &[homework(), soccer],
        &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
    );
    match result {
        HandMove::Moved { beside, .. } => assert_eq!(beside.as_deref(), Some("Soccer")),
        HandMove::Refused(words) => panic!("a clash is allowed, but it was refused: {words}"),
    }
}

#[test]
fn a_repeating_block_moved_on_one_day_splits_off_only_that_day() {
    let school = json!({
        "id": "school", "title": "School", "kind": "locked", "days": [0, 1, 2],
        "start": "08:00", "duration_min": 390, "category": "class",
    });
    let result = moved(
        &[school],
        &drop_of("school", MONDAY, THURSDAY, 9 * 60, 15 * 60),
    );
    let HandMove::Moved {
        blocks, block_id, ..
    } = result
    else {
        panic!("the move was refused");
    };
    assert_eq!(blocks.len(), 2, "the series and the one day split from it");
    let series = blocks.iter().find(|block| block["id"] == "school").unwrap();
    assert_eq!(series["days"], json!([1, 2]), "the others keep the series");
    assert_eq!(series["start"], json!("08:00"), "the series keeps its time");
    assert_ne!(block_id, "school", "the moved day is a block of its own");
    let copy = blocks
        .iter()
        .find(|block| block["id"] == block_id.as_str())
        .unwrap();
    assert_eq!(
        copy["days"],
        json!([THURSDAY]),
        "the copy is on the new day"
    );
    assert_eq!(copy["start"], json!("09:00"), "the copy has the new start");
    assert_eq!(
        copy["duration_min"],
        json!(360),
        "the copy has the new length"
    );
    assert_ne!(copy["pinned"], json!(true), "a fixed block is not pinned");
}

#[test]
fn the_plan_leaves_homework_moved_by_hand_where_it_is() {
    let rival = Dump::flex("rival", "Chemistry", HOMEWORK_MIN, &[TUESDAY])
        .priority(1)
        .earliest("14:30")
        .latest("16:00")
        .into_value();
    let blocks = match moved(
        &[homework(), rival],
        &drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN),
    ) {
        HandMove::Moved { blocks, .. } => blocks,
        HandMove::Refused(words) => panic!("the move was refused: {words}"),
    };
    assert!(!blocks.is_empty(), "there are blocks to plan");
    let parsed: Vec<_> = blocks
        .iter()
        .map(|b| block_from_value(b).unwrap())
        .collect();
    let trace = solve_legacy(&parsed);
    let kept = trace
        .placed
        .iter()
        .find(|block| block.id == "alg")
        .expect("the homework is still placed");
    assert_eq!(kept.start.as_deref(), Some("14:30"), "Plan kept the time");
    assert_eq!(kept.days, vec![TUESDAY], "Plan kept the day");
}

#[test]
fn the_answer_for_the_bindings_says_moved_or_why_not() {
    let drop = drop_of("alg", MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN);
    let answer = moved(&[homework()], &drop).to_value();
    assert_eq!(answer["moved"], json!(true));
    assert_eq!(answer["block_id"], json!("alg"));
    assert_eq!(answer["beside"], Value::Null);
    assert_eq!(answer["blocks"][0]["days"], json!([TUESDAY]));
    let nothing = moved(&[], &drop).to_value();
    assert_eq!(nothing["moved"], json!(false));
    assert_eq!(
        nothing["problem"],
        json!("That block is not in this week, so nothing moved.")
    );
}
