//! The kept reminder cards and the alarm queue (P4 group 7): the rules of kept_alerts.py's
//! `KeptReminders` and controller.py's `_enqueue_alarm` and `finish_alarm`. The clock in these tests
//! is the minute of the day: Guitar practice starts at 18:45 (1125), its reminder is due from 18:35.

use flexweek_app::session::reminders::{
    Added, AlarmClock, AlarmPlan, AlarmQueue, AlarmSeen, AlertStrip, BlockAlerts, Cards,
    FetchApply, FetchBegin, Membership, OpenWeek, block_notices, block_songs, cached_reminders_due,
    check_alerts_begin, due_alarm_plan, due_block_alerts, open_reminder_source,
    parked_or_cached_source, prepare_block_alerts, reminder_fetch_apply, reminder_fetch_begin,
    reminder_fetch_failed, reminder_fetch_gate, resolve_spotify_url, todays_reminder_blocks,
};
use flexweek_engine::ErrorKind;
use flexweek_engine::desk::weekmodel::set_clock_24h;
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

const MONDAY: &str = "2026-11-02";
const THURSDAY: &str = "2026-11-05";
const TRACK: &str = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT";
const OTHER: &str = "https://open.spotify.com/track/1301WleyT98MSxVHPZCA6M";
const SOCCER_KEY: &str = "2026-11-02|soccer|0|16:00";
/// Monday of 2026-11-05, the block id, Thursday's day index, and the start.
const PRACTICE_KEY: &str = "2026-11-02|practice|3|18:45";

fn notice(title: &str, body: &str) -> Value {
    json!({ "title": title, "body": body, "kind": "reminder" })
}

fn practice_block() -> Value {
    json!({
        "id": "practice",
        "title": "Guitar practice",
        "kind": "locked",
        "category": "class",
        "duration_min": 30,
        "days": [3],
        "start": "18:45",
    })
}

fn soccer_block() -> Value {
    json!({
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "16:00",
    })
}

fn reminding(extra: Value) -> Value {
    let mut prefs = json!({ "reminders_enabled": true, "reminder_lead_min": 5 });
    if let (Value::Object(prefs), Value::Object(extra)) = (&mut prefs, extra) {
        for (key, value) in extra {
            prefs.insert(key, value);
        }
    }
    prefs
}

fn members(values: &Value) -> Membership<'_> {
    Membership {
        values,
        is_set: true,
    }
}

fn block_due(
    blocks: &Value,
    trace: &Value,
    today: &str,
    minute: i64,
    prefs: &Value,
    fired: &Value,
    played: &Value,
) -> BlockAlerts {
    due_block_alerts(
        blocks,
        trace,
        today,
        minute,
        prefs,
        members(fired),
        members(played),
    )
    .unwrap()
}

fn wall_ms(hour: i64, minute: i64) -> i64 {
    hour * 3_600_000 + minute * 60_000
}

fn alarm_row(id: &str, name: &str) -> Value {
    json!({ "id": id, "name": name, "time": "07:00", "days": [0], "enabled": true })
}

fn alarms_due(
    prefs: &Value,
    songs: &Value,
    now_ms: i64,
    last: Option<i64>,
    fired: &Value,
    snoozed: &Value,
) -> (AlarmPlan, Vec<String>) {
    let mut added = Vec::new();
    let plan = due_alarm_plan(
        prefs,
        songs,
        AlarmClock {
            today_iso: MONDAY,
            weekday: 0,
            now_ms,
            last_check_ms: last,
        },
        &mut AlarmSeen {
            fired,
            is_set: true,
            added: &mut added,
        },
        snoozed,
        &mut |hour, minute| Ok(wall_ms(hour, minute)),
    )
    .unwrap();
    (plan, added)
}

#[test]
fn the_strip_says_the_oldest_notice_and_counts_the_rest() {
    let mut strip = AlertStrip::default();
    let first = strip
        .add(&[notice("Guitar practice starts soon", "7:15 PM \u{b7} Thu")])
        .unwrap();
    assert!(!first.handled);
    assert_eq!(
        first.text,
        "Guitar practice starts soon \u{2014} 7:15 PM \u{b7} Thu"
    );
    assert_eq!(strip.pending(), 1);
    assert_eq!(strip.text(), first.text);
    let second = strip
        .add(&[notice("Soccer starts soon", "4:00 PM \u{b7} Mon")])
        .unwrap();
    assert_eq!(
        second.text,
        "Guitar practice starts soon \u{2014} 7:15 PM \u{b7} Thu  (+1 more)"
    );
    let dropped = strip.drop().unwrap();
    assert!(!dropped.handled);
    assert_eq!(
        dropped.text,
        "Soccer starts soon \u{2014} 4:00 PM \u{b7} Mon"
    );
    let last = strip.drop().unwrap();
    assert!(last.handled);
    assert_eq!(last.text, "");
    assert_eq!(strip.pending(), 0);
}

#[test]
fn a_missing_title_says_flexweek_and_an_empty_body_has_no_dash() {
    let mut strip = AlertStrip::default();
    let missing = strip
        .add(&[json!({ "body": "4:00 PM \u{b7} Mon" })])
        .unwrap();
    assert_eq!(missing.text, "FlexWeek \u{2014} 4:00 PM \u{b7} Mon");
    strip.clear();
    let empty_body = strip
        .add(&[json!({ "title": "Soccer starts soon", "body": "" })])
        .unwrap();
    assert_eq!(empty_body.text, "Soccer starts soon");
    strip.clear();
    let empty_title = strip.add(&[json!({ "title": "", "body": "" })]).unwrap();
    assert_eq!(empty_title.text, "FlexWeek");
}

#[test]
fn dropping_or_clearing_an_empty_strip_still_renders_and_a_drop_is_handled() {
    let mut strip = AlertStrip::default();
    let dropped = strip.drop().unwrap();
    assert!(dropped.handled);
    assert_eq!(dropped.text, "");
    let cleared = strip.clear();
    assert!(!cleared.handled);
    assert_eq!(cleared.text, "");
    strip
        .add(&[notice("Soccer starts soon", "4:00 PM \u{b7} Mon")])
        .unwrap();
    let same = strip.add(&[]).unwrap();
    assert_eq!(same.text, "Soccer starts soon \u{2014} 4:00 PM \u{b7} Mon");
    assert_eq!(strip.pending(), 1);
    strip.clear();
    assert_eq!(strip.text(), "");
    assert_eq!(strip.pending(), 0);
}

#[test]
fn a_notice_that_is_not_an_object_cannot_be_read() {
    let mut strip = AlertStrip::default();
    let error = strip.add(&[json!("nope")]).unwrap_err();
    assert_eq!(error.kind, ErrorKind::Attribute);
    assert_eq!(error.message, "'str' object has no attribute 'get'");
    assert_eq!(strip.pending(), 1);
    assert_eq!(strip.text(), "");
}

#[test]
fn today_comes_from_the_open_week_then_the_parked_week_then_the_cache() {
    let open = json!([{ "id": "open" }]);
    let open_trace = json!({ "from": "open" });
    let parked = json!({
        "blocks": [{ "id": "parked" }],
        "trace": { "from": "parked" },
    });
    let cached = json!([{ "id": "cached" }]);
    let cached_trace = json!({ "from": "cached" });
    let found = open_reminder_source(
        OpenWeek {
            week_start: Some(MONDAY),
            blocks: &open,
            trace: &open_trace,
        },
        MONDAY,
    )
    .unwrap();
    assert_eq!(found.0, &open);
    assert_eq!(found.1, &open_trace);
    assert!(
        open_reminder_source(
            OpenWeek {
                week_start: Some("2026-11-09"),
                blocks: &open,
                trace: &open_trace,
            },
            MONDAY,
        )
        .is_none()
    );
    let found = parked_or_cached_source(&parked, Some(MONDAY), &cached, &cached_trace, MONDAY)
        .unwrap()
        .unwrap();
    assert_eq!(found.0, &parked["blocks"]);
    assert_eq!(found.1, &parked["trace"]);
    let found = parked_or_cached_source(&Value::Null, Some(MONDAY), &cached, &cached_trace, MONDAY)
        .unwrap()
        .unwrap();
    assert_eq!(found.0, &cached);
    assert!(
        parked_or_cached_source(
            &Value::Null,
            Some("2026-11-09"),
            &cached,
            &cached_trace,
            MONDAY,
        )
        .unwrap()
        .is_none()
    );
    assert!(
        parked_or_cached_source(&Value::Null, None, &cached, &cached_trace, MONDAY)
            .unwrap()
            .is_none()
    );
}

#[test]
fn a_parked_week_without_blocks_is_a_missing_key() {
    let error = parked_or_cached_source(
        &json!({ "trace": null }),
        None,
        &json!([]),
        &Value::Null,
        MONDAY,
    )
    .unwrap_err();
    assert_eq!(error.kind, ErrorKind::Key);
    assert_eq!(error.message, "blocks");
}

#[test]
fn todays_blocks_are_keyed_for_the_day_being_asked_about() {
    let blocks = json!([soccer_block(), practice_block()]);
    let monday = todays_reminder_blocks(&blocks, &Value::Null, MONDAY).unwrap();
    assert_eq!(monday.len(), 1);
    assert_eq!(monday[SOCCER_KEY]["title"], "Soccer");
    let thursday = todays_reminder_blocks(&blocks, &Value::Null, THURSDAY).unwrap();
    assert_eq!(thursday.len(), 1);
    assert_eq!(thursday[PRACTICE_KEY]["title"], "Guitar practice");
}

#[test]
fn a_block_inside_its_lead_is_announced_once_in_twelve_hour_form() {
    set_clock_24h(false);
    let blocks = json!([soccer_block()]);
    let due = block_due(
        &blocks,
        &Value::Null,
        MONDAY,
        15 * 60 + 55,
        &reminding(json!({})),
        &json!([]),
        &json!([]),
    );
    assert_eq!(due.notices.len(), 1);
    assert_eq!(due.notices[0]["title"], "Soccer starts soon");
    assert_eq!(due.notices[0]["body"], "4:00 PM \u{b7} Mon");
    assert_eq!(due.notices[0]["kind"], "reminder");
    assert_eq!(due.notices[0]["key"], SOCCER_KEY);
    assert_eq!(due.fired, vec![SOCCER_KEY.to_string()]);
    assert!(due.songs.is_empty());
    let again = block_due(
        &blocks,
        &Value::Null,
        MONDAY,
        15 * 60 + 55,
        &reminding(json!({})),
        &json!([SOCCER_KEY]),
        &json!([]),
    );
    assert!(again.notices.is_empty());
    assert!(again.fired.is_empty());
}

#[test]
fn a_block_with_no_link_says_it_starts_now_and_plays_nothing() {
    set_clock_24h(false);
    let blocks = json!([practice_block()]);
    let due = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 45,
        &reminding(json!({})),
        &json!([]),
        &json!([]),
    );
    assert_eq!(due.notices[0]["title"], "Guitar practice starts now");
    assert_eq!(due.notices[0]["body"], "6:45 PM \u{b7} Thu");
    assert!(due.songs.is_empty());
    let early = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 39,
        &reminding(json!({})),
        &json!([]),
        &json!([]),
    );
    assert!(early.notices.is_empty());
}

#[test]
fn a_stored_block_link_is_not_played_and_the_block_keeps_it() {
    set_clock_24h(false);
    let mut block = practice_block();
    block["spotify_url"] = json!(TRACK);
    let blocks = json!([block]);
    let due = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 45,
        &reminding(json!({ "alarm_tone": "soft", "default_spotify_url": TRACK })),
        &json!([]),
        &json!([]),
    );
    assert_eq!(due.notices[0]["title"], "Guitar practice starts now");
    assert!(due.songs.is_empty());
    assert_eq!(blocks[0]["spotify_url"], TRACK);
}

#[test]
fn a_block_start_plays_the_settings_link_only_when_the_sound_is_spotify() {
    set_clock_24h(false);
    let mut block = practice_block();
    block["spotify_url"] = json!(TRACK);
    let blocks = json!([block]);
    let due = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 45,
        &reminding(json!({ "alarm_tone": "spotify", "default_spotify_url": OTHER })),
        &json!([]),
        &json!([]),
    );
    assert!(due.notices.is_empty());
    assert_eq!(due.songs.len(), 1);
    assert_eq!(due.songs[0]["spotify_url"], OTHER);
    assert_eq!(due.songs[0]["id"], PRACTICE_KEY);
    assert_eq!(due.played, vec![PRACTICE_KEY.to_string()]);
    assert_eq!(blocks[0]["spotify_url"], TRACK);
    let again = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 45,
        &reminding(json!({ "alarm_tone": "spotify", "default_spotify_url": OTHER })),
        &json!([]),
        &json!([PRACTICE_KEY]),
    );
    assert!(again.songs.is_empty());
}

#[test]
fn a_bad_settings_link_is_left_out_so_the_start_is_still_announced() {
    set_clock_24h(false);
    let blocks = json!([practice_block()]);
    let due = block_due(
        &blocks,
        &Value::Null,
        THURSDAY,
        18 * 60 + 45,
        &reminding(json!({ "alarm_tone": "spotify", "default_spotify_url": "http://evil" })),
        &json!([]),
        &json!([]),
    );
    assert_eq!(due.notices[0]["title"], "Guitar practice starts now");
    assert!(due.songs.is_empty());
}

#[test]
fn a_link_on_a_placed_block_is_cleared_on_the_copy_only() {
    set_clock_24h(false);
    let blocks = json!([{
        "id": "soccer",
        "title": "Soccer",
        "kind": "flexible",
        "days": [0],
        "start": "16:00",
    }]);
    let trace = json!({
        "placed": [{
            "id": "soccer",
            "title": "Soccer",
            "kind": "flexible",
            "days": [0],
            "start": "16:00",
            "spotify_url": TRACK,
        }],
    });
    let due = block_due(
        &blocks,
        &trace,
        MONDAY,
        16 * 60,
        &reminding(json!({ "alarm_tone": "soft" })),
        &json!([]),
        &json!([]),
    );
    assert_eq!(due.notices[0]["title"], "Soccer starts now");
    assert!(due.songs.is_empty());
    assert_eq!(trace["placed"][0]["spotify_url"], TRACK);
}

#[test]
fn notice_keys_are_known_before_a_song_check_can_fail() {
    set_clock_24h(false);
    let blocks = json!([soccer_block()]);
    let prefs = reminding(json!({ "alarm_tone": "spotify", "default_spotify_url": OTHER }));
    let prepared = prepare_block_alerts(&blocks, &Value::Null, &prefs).unwrap();
    let (notices, fired) =
        block_notices(&prepared, MONDAY, 15 * 60 + 55, members(&json!([]))).unwrap();
    assert_eq!(fired, vec![SOCCER_KEY.to_string()]);
    assert_eq!(notices[0]["title"], "Soccer starts soon");
    let error = block_songs(
        &prepared,
        MONDAY,
        15 * 60 + 55,
        Membership {
            values: &json!(1),
            is_set: true,
        },
    )
    .unwrap_err();
    assert_eq!(error.kind, ErrorKind::Type);
    assert_eq!(error.message, "'int' object is not iterable");
}

#[test]
fn a_fetch_for_the_monday_already_in_flight_is_not_sent_again() {
    let first = reminder_fetch_begin(None, 0, MONDAY).unwrap();
    assert_eq!(
        first,
        FetchBegin {
            send: true,
            fetching: MONDAY.to_string(),
            ticket: 1,
        }
    );
    let second = reminder_fetch_begin(Some(&first.fetching), first.ticket, MONDAY).unwrap();
    assert!(!second.send);
    assert_eq!(second.ticket, 1);
    let third = reminder_fetch_begin(Some(MONDAY), 1, "2026-11-09").unwrap();
    assert!(third.send);
    assert_eq!(third.ticket, 2);
    assert_eq!(third.fetching, "2026-11-09");
}

#[test]
fn a_stale_or_signed_out_reply_is_ignored_and_an_open_week_is_not_replaced() {
    assert!(reminder_fetch_gate(1, 2, &json!({ "id": 1 }), &json!(MONDAY), MONDAY).ignore);
    assert!(reminder_fetch_gate(1, 1, &Value::Null, &json!(MONDAY), MONDAY).ignore);
    let open = reminder_fetch_gate(1, 1, &json!({ "id": 1 }), &json!(MONDAY), MONDAY);
    assert!(!open.ignore);
    assert!(!open.need_parked);
    let away = reminder_fetch_gate(1, 1, &json!({ "id": 1 }), &json!("2026-11-09"), MONDAY);
    assert!(away.need_parked);
    assert!(matches!(
        reminder_fetch_apply(false, &Value::Null, &json!({}), MONDAY).unwrap(),
        FetchApply::Reuse
    ));
    assert!(matches!(
        reminder_fetch_apply(true, &json!({ "blocks": [] }), &json!({}), MONDAY).unwrap(),
        FetchApply::Reuse
    ));
}

#[test]
fn a_reply_keeps_the_server_week_when_today_is_not_already_here() {
    match reminder_fetch_apply(true, &Value::Null, &json!({}), MONDAY).unwrap() {
        FetchApply::Cache { week, blocks } => {
            assert_eq!(week, json!(MONDAY));
            assert!(blocks.is_empty());
        }
        FetchApply::Reuse => panic!("an unknown week was treated as already open"),
    }
    match reminder_fetch_apply(true, &Value::Null, &json!({ "week_start": "" }), MONDAY).unwrap() {
        FetchApply::Cache { week, .. } => assert_eq!(week, json!(MONDAY)),
        FetchApply::Reuse => panic!("an empty week start was kept"),
    }
    match reminder_fetch_apply(
        true,
        &Value::Null,
        &json!({ "week_start": 3, "blocks": "ab" }),
        MONDAY,
    )
    .unwrap()
    {
        FetchApply::Cache { week, blocks } => {
            assert_eq!(week, json!(3));
            assert_eq!(blocks, vec![json!("a"), json!("b")]);
        }
        FetchApply::Reuse => panic!("a numbered week start was replaced"),
    }
    assert!(reminder_fetch_failed(2, 2));
    assert!(!reminder_fetch_failed(1, 2));
}

#[test]
fn two_alarms_in_the_same_minute_are_both_due_and_a_late_one_is_missed() {
    let prefs = json!({
        "alarms": [alarm_row("early", "Early"), alarm_row("also", "Also")],
    });
    let (plan, added) = alarms_due(
        &prefs,
        &json!({}),
        wall_ms(7, 0),
        None,
        &json!([]),
        &json!({}),
    );
    assert_eq!(
        added,
        vec![
            "2026-11-02|early|07:00".to_string(),
            "2026-11-02|also|07:00".to_string(),
        ]
    );
    assert_eq!(plan.queued[0]["id"], "early");
    assert_eq!(plan.queued[1]["id"], "also");
    assert_eq!(plan.last_alarm_check, wall_ms(7, 0));
    assert!(plan.snoozed.is_empty());
    let (late, late_added) = alarms_due(
        &prefs,
        &json!({}),
        wall_ms(7, 3),
        None,
        &json!([]),
        &json!({}),
    );
    assert!(late.queued.is_empty());
    assert!(late_added.is_empty());
    assert_eq!(late.last_alarm_check, wall_ms(7, 3));
    let (repeat, repeat_added) = alarms_due(
        &prefs,
        &json!({}),
        wall_ms(7, 0),
        None,
        &json!(["2026-11-02|early|07:00", "2026-11-02|also|07:00"]),
        &json!({}),
    );
    assert!(repeat.queued.is_empty());
    assert!(repeat_added.is_empty());
}

#[test]
fn reminders_that_are_off_do_not_ask_for_today_and_alarms_still_queue() {
    let prefs = json!({
        "reminders_enabled": false,
        "alarms": [alarm_row("early", "Early")],
    });
    assert_eq!(check_alerts_begin(&prefs, THURSDAY).unwrap(), None);
    assert!(!cached_reminders_due(&prefs, THURSDAY, MONDAY).unwrap());
    let (plan, added) = alarms_due(
        &prefs,
        &json!({}),
        wall_ms(7, 0),
        None,
        &json!([]),
        &json!({}),
    );
    assert_eq!(added, vec!["2026-11-02|early|07:00".to_string()]);
    assert_eq!(plan.queued[0]["id"], "early");
    assert_eq!(
        check_alerts_begin(&json!({ "reminders_enabled": true }), THURSDAY).unwrap(),
        Some(MONDAY.to_string())
    );
    assert!(cached_reminders_due(&json!({ "reminders_enabled": true }), THURSDAY, MONDAY).unwrap());
    assert!(
        !cached_reminders_due(&json!({ "reminders_enabled": true }), MONDAY, "2026-11-09").unwrap()
    );
    assert_eq!(check_alerts_begin(&Value::Null, THURSDAY).unwrap(), None);
}

#[test]
fn a_snoozed_block_song_is_due_with_the_alarms() {
    let song = json!({ "id": "s1", "enabled": true, "name": "Soccer", "block": true });
    let (plan, _) = alarms_due(
        &json!({ "alarms": [] }),
        &json!({ "s1": song.clone() }),
        wall_ms(7, 0),
        None,
        &json!([]),
        &json!({ "s1": wall_ms(7, 0) }),
    );
    assert_eq!(plan.queued, vec![song]);
    assert!(plan.snoozed.is_empty());
}

#[test]
fn an_alarms_value_that_cannot_be_unpacked_is_refused() {
    let mut added = Vec::new();
    let error = due_alarm_plan(
        &json!({ "alarms": 5 }),
        &json!({}),
        AlarmClock {
            today_iso: MONDAY,
            weekday: 0,
            now_ms: wall_ms(7, 0),
            last_check_ms: None,
        },
        &mut AlarmSeen {
            fired: &json!([]),
            is_set: true,
            added: &mut added,
        },
        &json!({}),
        &mut |hour, minute| Ok(wall_ms(hour, minute)),
    )
    .unwrap_err();
    assert_eq!(error.kind, ErrorKind::Type);
    assert_eq!(error.message, "Value after * must be an iterable, not int");
}

#[test]
fn the_spotify_link_is_the_one_handed_in_or_the_settings_link() {
    let prefs = json!({ "default_spotify_url": OTHER });
    assert_eq!(resolve_spotify_url(&prefs, &Value::Null).unwrap(), OTHER);
    assert_eq!(resolve_spotify_url(&json!({}), &Value::Null).unwrap(), "");
    assert_eq!(resolve_spotify_url(&prefs, &json!("")).unwrap(), "");
    assert_eq!(
        resolve_spotify_url(&prefs, &json!("http://evil")).unwrap(),
        ""
    );
    assert_eq!(
        resolve_spotify_url(&json!({ "default_spotify_url": "nope" }), &Value::Null).unwrap(),
        ""
    );
    assert_eq!(resolve_spotify_url(&prefs, &json!(TRACK)).unwrap(), TRACK);
    let handed = resolve_spotify_url(&json!({ "default_spotify_url": true }), &Value::Null);
    assert_eq!(handed.unwrap_err().kind, ErrorKind::Type);
    assert_eq!(
        handed_message(&json!(1)),
        "expected string or bytes-like object, got 'int'"
    );
}

fn handed_message(value: &Value) -> String {
    resolve_spotify_url(&json!({}), value).unwrap_err().message
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
