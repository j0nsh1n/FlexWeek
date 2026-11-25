//! Setup's write queue and the preference request bodies (P4 group 8): the rules of controller.py's
//! `keep_setup`, `flush_setup`, `save_preferences`, `save_availability` and `follow_first_weekday`.

use flexweek_app::session::preferences::{
    SetupQueue, SetupStep, availability_body, follow_first_weekday, pack_axis, preferences_body,
};
use serde_json::{Map, Value, json};

fn object(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(fields) => fields,
        other => panic!("not an object: {other}"),
    }
}

fn kept(queue: &mut SetupQueue, updates: Value, windows: Option<Value>, week: bool) {
    queue.keep(&object(updates), windows, week);
}

#[test]
fn the_queue_sends_preferences_then_study_hours_then_the_week() {
    let mut queue = SetupQueue::default();
    let hours = json!([{ "days": [0], "start": "09:00", "end": "11:00" }]);
    kept(&mut queue, json!({ "clock_24h": true }), Some(hours.clone()), true);

    assert_eq!(
        queue.next(true, false, true),
        SetupStep::Preferences(object(json!({ "clock_24h": true })))
    );
    assert_eq!(queue.next(true, false, true), SetupStep::Windows(hours));
    assert_eq!(queue.next(true, false, true), SetupStep::Week);
    assert_eq!(queue.next(true, false, true), SetupStep::Nothing);
}

#[test]
fn nothing_is_sent_while_busy_or_signed_out_and_it_is_still_there_after() {
    let mut queue = SetupQueue::default();
    kept(&mut queue, json!({ "clock_24h": true }), None, true);

    assert_eq!(queue.next(true, true, true), SetupStep::Nothing);
    assert_eq!(queue.next(false, false, true), SetupStep::Nothing);
    assert_eq!(queue.prefs(), &object(json!({ "clock_24h": true })));
    assert!(queue.week());
    assert_eq!(
        queue.next(true, false, true),
        SetupStep::Preferences(object(json!({ "clock_24h": true })))
    );
}

#[test]
fn a_second_keep_merges_by_key_and_keeps_the_latest_study_hours() {
    let mut queue = SetupQueue::default();
    kept(
        &mut queue,
        json!({ "planning_style": "manual", "clock_24h": false }),
        Some(json!([{ "days": [0], "start": "08:00", "end": "09:00" }])),
        false,
    );
    kept(
        &mut queue,
        json!({ "clock_24h": true }),
        Some(json!([{ "days": [1], "start": "13:00", "end": "14:00" }])),
        false,
    );

    assert_eq!(
        queue.next(true, false, true),
        SetupStep::Preferences(object(
            json!({ "planning_style": "manual", "clock_24h": true })
        ))
    );
    assert_eq!(
        queue.next(true, false, true),
        SetupStep::Windows(json!([{ "days": [1], "start": "13:00", "end": "14:00" }]))
    );
}

#[test]
fn a_keep_without_hours_or_week_leaves_those_already_kept() {
    let mut queue = SetupQueue::default();
    kept(&mut queue, json!({}), Some(json!([])), true);
    kept(&mut queue, json!({ "clock_24h": true }), None, false);

    assert_eq!(queue.windows(), Some(&json!([])));
    assert!(queue.week());
}

#[test]
fn preferences_and_study_hours_wait_for_the_stored_preferences_but_the_week_does_not() {
    let mut queue = SetupQueue::default();
    kept(&mut queue, json!({ "clock_24h": true }), Some(json!([])), true);

    assert_eq!(queue.next(true, false, false), SetupStep::Week);
    assert_eq!(queue.next(true, false, false), SetupStep::Nothing);
    assert_eq!(queue.prefs(), &object(json!({ "clock_24h": true })));
    assert_eq!(queue.windows(), Some(&json!([])));
    assert_eq!(
        queue.next(true, false, true),
        SetupStep::Preferences(object(json!({ "clock_24h": true })))
    );
}

#[test]
fn clearing_forgets_everything_kept() {
    let mut queue = SetupQueue::default();
    kept(&mut queue, json!({ "clock_24h": true }), Some(json!([])), true);
    queue.clear();

    assert!(queue.prefs().is_empty());
    assert_eq!(queue.windows(), None);
    assert!(!queue.week());
    assert_eq!(queue.next(true, false, true), SetupStep::Nothing);
}

#[test]
fn the_preferences_body_leaves_keys_it_was_not_given_alone() {
    let current = json!({ "clock_24h": false, "planning_style": "auto", "day_cutoff": "22:00" });
    let body = preferences_body(&current, &json!({ "clock_24h": true }));

    assert_eq!(
        body,
        json!({ "clock_24h": true, "planning_style": "auto", "day_cutoff": "22:00" })
    );
}

#[test]
fn a_packs_theme_comes_from_the_pack_not_from_the_caller() {
    let current = json!({ "theme": "system", "theme_pack": "system" });
    let body = preferences_body(
        &current,
        &json!({ "theme_pack": "light-frost", "theme": "nocturne" }),
    );
    assert_eq!(body["theme_pack"], "light-frost");
    assert_eq!(body["theme"], "slate");

    let body = preferences_body(&current, &json!({ "theme_pack": "dark-frost" }));
    assert_eq!(body["theme"], "nocturne");
}

#[test]
fn every_pack_has_its_axis_and_an_unknown_pack_is_system() {
    for (pack, axis) in [
        ("light-frost", "slate"),
        ("slate", "slate"),
        ("dark-frost", "nocturne"),
        ("nocturne", "nocturne"),
        ("system", "system"),
    ] {
        assert_eq!(pack_axis(&json!(pack)), axis, "{pack}");
    }
    assert_eq!(pack_axis(&json!("neon")), "system");
    assert_eq!(pack_axis(&Value::Null), "system");
}

#[test]
fn a_pack_already_stored_still_sets_the_theme_on_an_unrelated_update() {
    let current = json!({ "theme": "system", "theme_pack": "nocturne" });
    let body = preferences_body(&current, &json!({ "clock_24h": true }));

    assert_eq!(body["theme"], "nocturne");
}

#[test]
fn a_body_without_a_pack_keeps_the_theme_it_has() {
    let body = preferences_body(&json!({ "theme": "slate" }), &json!({ "clock_24h": true }));

    assert_eq!(body["theme"], "slate");
}

#[test]
fn an_empty_day_cutoff_is_null() {
    let prefs = json!({ "day_cutoff": "22:00", "clock_24h": true });
    let protected = json!([{ "days": [0], "start": "12:00", "end": "13:00" }]);

    for empty in [json!(""), Value::Null] {
        let body = availability_body(&prefs, &protected, &empty, None);
        assert_eq!(body["day_cutoff"], Value::Null);
    }
    let body = availability_body(&prefs, &protected, &json!("21:30"), None);
    assert_eq!(body["day_cutoff"], "21:30");
    assert_eq!(body["protected"], protected);
    assert_eq!(body["clock_24h"], true);
}

#[test]
fn work_windows_are_in_the_body_only_when_given() {
    let prefs = json!({ "work_windows": [{ "days": [2] }], "clock_24h": true });
    let windows = json!([{ "days": [0], "start": "09:00", "end": "10:00" }]);

    let without = availability_body(&prefs, &json!([]), &json!("22:00"), None);
    assert_eq!(without["work_windows"], json!([{ "days": [2] }]));

    let with = availability_body(&prefs, &json!([]), &json!("22:00"), Some(&windows));
    assert_eq!(with["work_windows"], windows);

    let bare = availability_body(&json!({}), &json!([]), &json!("22:00"), None);
    assert!(bare.get("work_windows").is_none());
}

#[test]
fn a_new_first_day_signed_in_moves_the_focus_and_the_open_week() {
    let facts = follow_first_weekday(0, 6, true);

    assert!(facts.changed);
    assert!(facts.refollow);
    assert!(facts.rebase_focus);
}

#[test]
fn the_same_first_day_or_no_account_moves_nothing_to_follow() {
    let same = follow_first_weekday(6, 6, true);
    assert!(!same.changed && !same.refollow && !same.rebase_focus);

    let signed_out = follow_first_weekday(0, 6, false);
    assert!(signed_out.changed);
    assert!(!signed_out.refollow && !signed_out.rebase_focus);
}
