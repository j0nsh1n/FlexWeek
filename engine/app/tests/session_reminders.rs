//! The kept reminder cards and the alarm queue (P4 group 7): the rules of kept_alerts.py's
//! `KeptReminders` and controller.py's `_enqueue_alarm` and `finish_alarm`. The clock in these tests
//! is the minute of the day: Guitar practice starts at 18:45 (1125), its reminder is due from 18:35.

use flexweek_app::session::reminders::{Added, AlarmQueue, Cards};
use serde_json::{Value, json};

const FIVE_MINUTES_MS: i64 = 5 * 60 * 1000;

const M_1835: i64 = 18 * 60 + 35;
const M_1840: i64 = 18 * 60 + 40;
const M_1843: i64 = 18 * 60 + 43;
const M_1844: i64 = 18 * 60 + 44;
const M_1845: i64 = 18 * 60 + 45;

fn practice() -> String {
    "2026-11-05|practice|3|18:45".to_string()
}

fn chess() -> String {
    "2026-11-05|chess|3|18:50".to_string()
}

fn rows(entries: &[(String, &str)]) -> Value {
    let mut rows = serde_json::Map::new();
    for (key, title) in entries {
        rows.insert(key.clone(), json!(title));
    }
    Value::Object(rows)
}

fn soon(key: &str, name: &str) -> Value {
    json!({ "key": key, "title": format!("{name} starts soon"), "body": "6:45 PM \u{b7} Thu" })
}

fn titles(cards: &Cards) -> Vec<String> {
    cards
        .visible()
        .iter()
        .map(|card| card["title"].as_str().unwrap_or_default().to_string())
        .collect()
}

fn with_practice_card() -> (Cards, Value) {
    let mut cards = Cards::default();
    let week = rows(&[(practice(), "Guitar practice")]);
    let added = cards
        .add(&soon(&practice(), "Guitar practice"), Some(&week), M_1835)
        .unwrap();
    assert!(added.kept);
    (cards, week)
}

#[test]
fn a_card_stays_until_its_block_starts_and_is_then_released() {
    let (mut cards, week) = with_practice_card();
    let told = cards.sync(Some(&week), M_1844).unwrap();
    assert!(told.released.is_empty(), "released a minute early");
    assert_eq!(cards.visible().len(), 1);
    let told = cards.sync(Some(&week), M_1845).unwrap();
    assert_eq!(told.released, vec![practice()]);
    assert!(told.changed);
    assert!(cards.visible().is_empty());
    assert!(cards.is_empty());
}

#[test]
fn a_snoozed_card_is_not_visible_until_it_is_due() {
    let (mut cards, week) = with_practice_card();
    assert!(cards.snooze(&practice(), M_1835).unwrap());
    assert!(cards.visible().is_empty());
    assert_eq!(cards.len(), 1, "a snoozed card is held, not dropped");
    assert!(
        !cards.snooze(&practice(), M_1835).unwrap(),
        "snoozing a card already snoozed"
    );
    let told = cards.sync(Some(&week), M_1835 + 1).unwrap();
    assert!(!told.changed);
    assert!(cards.visible().is_empty());
}

#[test]
fn a_snoozed_card_comes_back_five_minutes_later() {
    let (mut cards, week) = with_practice_card();
    cards.snooze(&practice(), M_1835).unwrap();
    for minute in (M_1835 + 1)..M_1840 {
        let told = cards.sync(Some(&week), minute).unwrap();
        assert!(cards.visible().is_empty(), "back too early at {minute}");
        assert!(told.said.is_empty());
    }
    let told = cards.sync(Some(&week), M_1840).unwrap();
    assert_eq!(cards.visible().len(), 1);
    assert!(told.changed);
    assert_eq!(
        told.said,
        vec!["Guitar practice starts soon \u{2014} 6:45 PM \u{b7} Thu"]
    );
}

#[test]
fn a_snooze_near_the_start_comes_back_at_the_start_not_after_it() {
    // Five minutes before the start is the start itself; three minutes before, five minutes would pass it.
    for snoozed_at in [M_1840, M_1843] {
        let (mut cards, week) = with_practice_card();
        cards.snooze(&practice(), snoozed_at).unwrap();
        let told = cards.sync(Some(&week), M_1844).unwrap();
        assert!(told.released.is_empty());
        assert!(cards.visible().is_empty(), "back before the start");
        let told = cards.sync(Some(&week), M_1845).unwrap();
        assert_eq!(
            told.released,
            vec![practice()],
            "a snooze from minute {snoozed_at} did not hand over to starts now"
        );
        assert!(cards.visible().is_empty());
    }
}

#[test]
fn renaming_a_block_renames_its_card() {
    let (mut cards, _) = with_practice_card();
    let renamed = rows(&[(practice(), "Piano lesson")]);
    let told = cards.sync(Some(&renamed), M_1840).unwrap();
    assert!(told.changed);
    assert_eq!(
        cards.visible(),
        vec![json!({
            "key": practice(),
            "title": "Piano lesson starts soon",
            "body": "6:45 PM \u{b7} Thu",
        })]
    );
    let told = cards.sync(Some(&renamed), M_1840 + 1).unwrap();
    assert!(!told.changed, "told a second time");
}

#[test]
fn renaming_a_snoozed_block_renames_its_card_without_showing_it() {
    let (mut cards, _) = with_practice_card();
    cards.snooze(&practice(), M_1835).unwrap();
    let renamed = rows(&[(practice(), "Piano lesson")]);
    let told = cards.sync(Some(&renamed), M_1835 + 1).unwrap();
    assert!(!told.changed, "a hidden card changed nothing on screen");
    cards.sync(Some(&renamed), M_1840).unwrap();
    assert_eq!(titles(&cards), vec!["Piano lesson starts soon"]);
}

#[test]
fn a_notice_with_no_key_or_a_block_that_started_is_not_added() {
    let week = rows(&[(practice(), "Guitar practice")]);
    let mut cards = Cards::default();
    let no_key = json!({ "title": "Guitar practice starts soon" });
    assert_eq!(
        cards.add(&no_key, Some(&week), M_1835).unwrap(),
        Added::default()
    );
    let number_key = json!({ "key": 7, "title": "x" });
    assert!(!cards.add(&number_key, Some(&week), M_1835).unwrap().kept);
    let unknown = soon(&chess(), "Chess");
    assert!(!cards.add(&unknown, Some(&week), M_1835).unwrap().kept);
    assert!(!cards.add(&unknown, None, M_1835).unwrap().kept);
    let started = soon(&practice(), "Guitar practice");
    assert!(!cards.add(&started, Some(&week), M_1845).unwrap().kept);
    assert!(!cards.add(&started, Some(&week), M_1845 + 10).unwrap().kept);
    assert!(cards.is_empty());
}

#[test]
fn a_notice_with_no_title_gets_the_app_name_and_its_words_are_said() {
    let week = rows(&[(practice(), "Guitar practice")]);
    let mut cards = Cards::default();
    let added = cards
        .add(&json!({ "key": practice() }), Some(&week), M_1835)
        .unwrap();
    assert_eq!(
        added,
        Added {
            kept: true,
            changed: true,
            said: Some("FlexWeek".to_string()),
        }
    );
    assert_eq!(titles(&cards), vec!["FlexWeek"]);
}

#[test]
fn a_reminder_already_on_screen_is_not_added_twice() {
    let (mut cards, week) = with_practice_card();
    let again = cards
        .add(&soon(&practice(), "Guitar practice"), Some(&week), M_1840)
        .unwrap();
    assert!(again.kept);
    assert!(!again.changed);
    assert_eq!(again.said, None);
    assert_eq!(cards.len(), 1);
}

#[test]
fn two_cards_show_newest_first() {
    let (mut cards, _) = with_practice_card();
    let week = rows(&[(practice(), "Guitar practice"), (chess(), "Chess")]);
    cards
        .add(&soon(&chess(), "Chess"), Some(&week), M_1840)
        .unwrap();
    assert_eq!(
        titles(&cards),
        vec!["Chess starts soon", "Guitar practice starts soon"]
    );
}

#[test]
fn a_card_whose_block_moved_or_went_is_dropped() {
    let (mut cards, _) = with_practice_card();
    let gone = rows(&[(chess(), "Chess")]);
    let told = cards.sync(Some(&gone), M_1840).unwrap();
    assert!(told.changed);
    assert!(
        told.released.is_empty(),
        "a moved block is not a started one"
    );
    assert!(cards.is_empty());
}

#[test]
fn a_week_that_is_not_known_changes_nothing() {
    let (mut cards, _) = with_practice_card();
    let told = cards.sync(None, M_1845).unwrap();
    assert!(!told.changed && told.released.is_empty());
    assert_eq!(cards.len(), 1);
}

#[test]
fn close_drops_one_card_and_clear_drops_all() {
    let (mut cards, _) = with_practice_card();
    let week = rows(&[(practice(), "Guitar practice"), (chess(), "Chess")]);
    cards
        .add(&soon(&chess(), "Chess"), Some(&week), M_1840)
        .unwrap();
    assert!(!cards.close("2026-11-05|nothing|3|18:00"));
    assert!(cards.close(&chess()));
    assert_eq!(titles(&cards), vec!["Guitar practice starts soon"]);
    assert!(!cards.close(&chess()), "closed twice");
    assert!(cards.clear());
    assert!(cards.is_empty());
    assert!(!cards.clear(), "cleared when there was nothing");
}

#[test]
fn a_bad_key_is_an_error_not_a_card() {
    let week = rows(&[("practice".to_string(), "Guitar practice")]);
    let mut cards = Cards::default();
    let result = cards.add(&json!({ "key": "practice" }), Some(&week), M_1835);
    assert!(result.is_err());
    assert!(cards.is_empty());
}

fn alarm(id: &str) -> Value {
    json!({ "id": id, "name": id, "time": "07:00" })
}

fn song(id: &str) -> Value {
    json!({ "id": id, "name": id, "block": true })
}

fn id_of(alarm: Option<&Value>) -> Option<&str> {
    alarm.and_then(|alarm| alarm["id"].as_str())
}

#[test]
fn the_first_alarm_rings_at_once_and_the_next_after_it_is_finished() {
    let mut queue = AlarmQueue::default();
    assert!(queue.enqueue(alarm("early")));
    assert!(!queue.enqueue(alarm("also")));
    assert_eq!(id_of(queue.active()), Some("early"));
    assert_eq!(queue.waiting(), [alarm("also")]);
    let finished = queue.finish(false, 0);
    assert_eq!(finished.next, Some(alarm("also")));
    assert_eq!(id_of(queue.active()), Some("also"));
    assert!(queue.waiting().is_empty());
    let finished = queue.finish(false, 0);
    assert_eq!(finished.next, None);
    assert!(queue.active().is_none());
}

#[test]
fn an_alarm_already_ringing_or_waiting_is_not_queued_again() {
    let mut queue = AlarmQueue::default();
    assert!(queue.enqueue(alarm("a1")));
    assert!(!queue.enqueue(alarm("a1")), "the ringing one rang twice");
    assert!(!queue.enqueue(alarm("a2")));
    assert!(!queue.enqueue(alarm("a2")), "a waiting one queued twice");
    assert_eq!(queue.waiting().len(), 1);
}

#[test]
fn finishing_with_nothing_ringing_does_nothing() {
    let mut queue = AlarmQueue::default();
    let finished = queue.finish(true, 5);
    assert_eq!(finished.snoozed, None);
    assert_eq!(finished.next, None);
}

#[test]
fn a_snooze_records_when_that_alarm_comes_back() {
    let mut queue = AlarmQueue::default();
    queue.enqueue(alarm("a1"));
    let finished = queue.finish(true, 1_000);
    assert_eq!(
        finished.snoozed,
        Some(("a1".to_string(), 1_000 + FIVE_MINUTES_MS))
    );
    queue.enqueue(alarm("a2"));
    assert_eq!(queue.finish(false, 1_000).snoozed, None);
}

#[test]
fn finishing_a_block_song_with_snooze_keeps_it_and_without_forgets_it() {
    let mut queue = AlarmQueue::default();
    queue.enqueue(song("s1"));
    queue.finish(true, 0);
    assert_eq!(queue.songs().get("s1"), Some(&song("s1")));
    queue.enqueue(song("s1"));
    queue.finish(false, 0);
    assert!(
        queue.songs().is_empty(),
        "a dismissed song would ring again"
    );
}

#[test]
fn an_alarm_that_is_not_a_block_song_is_not_kept_by_a_snooze() {
    let mut queue = AlarmQueue::default();
    queue.enqueue(alarm("a1"));
    queue.finish(true, 0);
    assert!(queue.songs().is_empty());
}

#[test]
fn kept_songs_come_back_in_the_order_they_were_first_kept() {
    let mut queue = AlarmQueue::default();
    for id in ["s1", "s2"] {
        queue.enqueue(song(id));
        queue.finish(true, 0);
    }
    queue.enqueue(song("s1"));
    queue.finish(true, 0);
    let order: Vec<_> = queue.songs().keys().cloned().collect();
    assert_eq!(order, vec!["s1", "s2"]);
}

#[test]
fn clearing_forgets_the_ringing_alarm_the_waiting_ones_and_the_songs() {
    let mut queue = AlarmQueue::default();
    queue.enqueue(song("s1"));
    queue.enqueue(alarm("a2"));
    queue.finish(true, 0);
    queue.enqueue(alarm("a3"));
    queue.clear();
    assert!(queue.active().is_none());
    assert!(queue.waiting().is_empty());
    assert!(queue.songs().is_empty());
}
