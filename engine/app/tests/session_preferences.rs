//! Setup's write queue and the preference request bodies (P4 group 8): the rules of controller.py's
//! `keep_setup`, `flush_setup`, `save_preferences`, `save_availability` and `follow_first_weekday`.

use flexweek_app::session::preferences::{
    FlushSetupAction, HOURS_REFUSED, MAX_WORK_WINDOWS, PreferencesQueue, SAVED_AVAILABILITY,
    SAVED_PREFERENCES, SAVING_AVAILABILITY, SAVING_PREFERENCES, SaveAvailability, SavePreferences,
    SavePreferencesAction, SetupQueue, SetupStep, TimerSplitPreview, WORK_WINDOW_PRESETS,
    WORK_WINDOW_PRESETS_NOTE, availability_body, flush_setup_action, follow_first_weekday,
    keep_setup_merged_prefs, pack_axis, parse_recovery_status, parse_reminder_limits,
    parse_timer_presets, preferences_body, prepare_save_availability, prepare_save_preferences,
    prepare_timer_split_preview,
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
    kept(
        &mut queue,
        json!({ "clock_24h": true }),
        Some(hours.clone()),
        true,
    );

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
    kept(
        &mut queue,
        json!({ "clock_24h": true }),
        Some(json!([])),
        true,
    );

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
    kept(
        &mut queue,
        json!({ "clock_24h": true }),
        Some(json!([])),
        true,
    );
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

#[test]
fn drop_if_other_account_clears_for_none_or_different_id_and_keeps_same_id() {
    let mut queue = SetupQueue::default();
    kept(
        &mut queue,
        json!({ "clock_24h": true }),
        Some(json!([])),
        true,
    );

    assert!(!queue.drop_if_other_account(Some(&json!(7)), &json!(7)));
    assert!(queue.has_pending());
    assert_eq!(queue.prefs(), &object(json!({ "clock_24h": true })));

    assert!(queue.drop_if_other_account(Some(&json!(7)), &json!(8)));
    assert!(!queue.has_pending());
    assert!(queue.prefs().is_empty());

    kept(&mut queue, json!({ "clock_24h": true }), None, false);
    assert!(queue.drop_if_other_account(None, &json!(7)));
    assert!(!queue.has_pending());
}

#[test]
fn keep_setup_merged_prefs_overlays_kept_keys_and_preserves_none() {
    let current = json!({ "clock_24h": false, "planning_style": "suggest", "theme": "system" });
    let merged = keep_setup_merged_prefs(Some(&current), &object(json!({ "clock_24h": true })));
    assert_eq!(
        merged,
        Some(json!({ "clock_24h": true, "planning_style": "suggest", "theme": "system" }))
    );
    assert_eq!(
        keep_setup_merged_prefs(None, &object(json!({ "clock_24h": true }))),
        None
    );

    let mut queue = SetupQueue::default();
    let first = queue.keep_and_merge(
        &object(json!({ "planning_style": "auto" })),
        None,
        false,
        Some(&current),
    );
    assert_eq!(first.as_ref().unwrap()["planning_style"], "auto");
    let second = queue.keep_and_merge(
        &object(json!({ "clock_24h": true })),
        None,
        false,
        Some(&current),
    );
    assert_eq!(
        second,
        Some(json!({ "clock_24h": true, "planning_style": "auto", "theme": "system" }))
    );
}

#[test]
fn flush_setup_action_fills_protected_and_day_cutoff_defaults_for_windows() {
    let hours = json!([{ "days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00" }]);
    let mut queue = SetupQueue::default();
    kept(&mut queue, json!({}), Some(hours.clone()), false);

    let bare_prefs = json!({ "clock_24h": false });
    assert_eq!(
        queue.next_action(true, false, Some(&bare_prefs)),
        FlushSetupAction::Windows {
            protected: json!([]),
            day_cutoff: Value::Null,
            work_windows: hours.clone(),
        }
    );

    let meal = json!([{ "kind": "meal", "days": [0], "start": "18:00", "duration_min": 30 }]);
    let rich_prefs = json!({ "protected": meal, "day_cutoff": "21:30" });
    assert_eq!(
        flush_setup_action(&SetupStep::Windows(hours.clone()), Some(&rich_prefs)),
        FlushSetupAction::Windows {
            protected: meal,
            day_cutoff: json!("21:30"),
            work_windows: hours,
        }
    );
    assert_eq!(
        flush_setup_action(&SetupStep::Week, None),
        FlushSetupAction::Week
    );
    assert_eq!(
        flush_setup_action(&SetupStep::Nothing, None),
        FlushSetupAction::Nothing
    );
}

#[test]
fn prepare_save_availability_validates_windows_and_builds_request() {
    let prefs = json!({ "clock_24h": false, "theme": "system" });
    let meal =
        json!({ "kind": "meal", "days": [0, 1, 2, 3, 4], "start": "18:00", "duration_min": 30 });
    let hours = json!([{ "days": [0, 1, 2, 3, 4], "start": "08:00", "end": "21:00" }]);

    assert_eq!(
        prepare_save_availability(
            false,
            Some(&prefs),
            &json!([meal]),
            &json!("21:00"),
            Some(&hours)
        ),
        SaveAvailability::Absent
    );
    assert_eq!(
        prepare_save_availability(true, None, &json!([meal]), &json!("21:00"), Some(&hours)),
        SaveAvailability::Absent
    );

    let bad_kind = json!([{ "kind": "nap", "days": [0], "start": "18:00", "duration_min": 30 }]);
    assert_eq!(
        prepare_save_availability(true, Some(&prefs), &bad_kind, &json!("21:00"), Some(&hours)),
        SaveAvailability::Refused { say: HOURS_REFUSED }
    );

    let bad_grid = json!([{ "kind": "meal", "days": [0], "start": "18:07", "duration_min": 30 }]);
    assert_eq!(
        prepare_save_availability(true, Some(&prefs), &bad_grid, &json!("21:00"), None),
        SaveAvailability::Refused { say: HOURS_REFUSED }
    );

    let bad_hours = json!([{ "days": [0], "start": "21:00", "end": "08:00" }]);
    assert_eq!(
        prepare_save_availability(
            true,
            Some(&prefs),
            &json!([meal]),
            &json!("21:00"),
            Some(&bad_hours)
        ),
        SaveAvailability::Refused { say: HOURS_REFUSED }
    );

    let bad_day = json!([{ "days": [7], "start": "08:00", "end": "21:00" }]);
    assert_eq!(
        prepare_save_availability(
            true,
            Some(&prefs),
            &json!([meal]),
            &json!("21:00"),
            Some(&bad_day)
        ),
        SaveAvailability::Refused { say: HOURS_REFUSED }
    );

    assert_eq!(
        prepare_save_availability(
            true,
            Some(&prefs),
            &json!([meal]),
            &json!("21:00"),
            Some(&hours)
        ),
        SaveAvailability::Ready {
            method: "PUT",
            path: "/api/preferences",
            body: json!({
                "clock_24h": false,
                "theme": "system",
                "protected": [meal],
                "day_cutoff": "21:00",
                "work_windows": hours,
            }),
            progress: SAVING_AVAILABILITY,
            done: SAVED_AVAILABILITY,
        }
    );
}

#[test]
fn prepare_save_preferences_guards_and_applies_pack_axis() {
    let prefs = json!({ "theme": "system", "theme_pack": "system", "clock_24h": false });
    assert_eq!(
        prepare_save_preferences(false, Some(&prefs), &json!({ "clock_24h": true })),
        SavePreferences::Absent
    );
    assert_eq!(
        prepare_save_preferences(true, None, &json!({ "clock_24h": true })),
        SavePreferences::Absent
    );
    assert_eq!(
        prepare_save_preferences(
            true,
            Some(&prefs),
            &json!({ "theme_pack": "nocturne", "clock_24h": true })
        ),
        SavePreferences::Ready {
            method: "PUT",
            path: "/api/preferences",
            body: json!({
                "theme": "nocturne",
                "theme_pack": "nocturne",
                "clock_24h": true,
            }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
        }
    );
}

#[test]
fn preferences_queue_keeps_two_quick_switches_by_applying_second_on_first_result() {
    let mut queue = PreferencesQueue::default();
    let initial = json!({ "reminder_sound": true, "end_chime": false, "theme": "system" });

    assert!(queue.enqueue(true, true, &object(json!({ "reminder_sound": false }))));
    let first = queue.next(true, false, 0, Some(&initial));
    assert_eq!(
        first,
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({ "reminder_sound": false, "end_chime": false, "theme": "system" }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 1,
        }
    );
    queue.mark_in_flight(1);

    // Second switch flipped before the first PUT answers: waits without overwriting the first.
    assert!(queue.enqueue(true, true, &object(json!({ "end_chime": true }))));
    assert!(queue.has_pending());
    assert_eq!(
        queue.next(true, true, 1, Some(&initial)),
        SavePreferencesAction::Wait
    );

    // First PUT answers with reminder_sound=false; second applies on top of that result.
    let after_first = json!({ "reminder_sound": false, "end_chime": false, "theme": "system" });
    queue.finish(1);
    let second = queue.next(true, false, 1, Some(&after_first));
    assert_eq!(
        second,
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({ "reminder_sound": false, "end_chime": true, "theme": "system" }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 1,
        }
    );
    assert!(!queue.has_pending());
}

#[test]
fn preferences_queue_coalesces_multiple_waiting_changes_with_latest_winning() {
    let mut queue = PreferencesQueue::default();
    let initial = json!({ "reminder_sound": true, "end_chime": false, "tray_notifications": true });

    assert!(queue.enqueue(true, true, &object(json!({ "reminder_sound": false }))));
    let _ = queue.next(true, false, 0, Some(&initial));
    queue.mark_in_flight(1);

    // Three changes while PUT #1 is in flight: coalesced into one PUT with batch_len = 3.
    assert!(queue.enqueue(true, true, &object(json!({ "end_chime": true }))));
    assert!(queue.enqueue(true, true, &object(json!({ "tray_notifications": false }))));
    assert!(queue.enqueue(true, true, &object(json!({ "end_chime": false }))));
    assert_eq!(queue.pending_count(), 3);

    let after_first =
        json!({ "reminder_sound": false, "end_chime": false, "tray_notifications": true });
    queue.finish(1);
    assert_eq!(
        queue.next(true, false, 1, Some(&after_first)),
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({
                "reminder_sound": false,
                "end_chime": false,
                "tray_notifications": false,
            }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 3,
        }
    );
    assert_eq!(queue.pending_count(), 0);
}

#[test]
fn preferences_queue_after_failed_first_save_applies_later_change_on_last_saved_prefs() {
    let mut queue = PreferencesQueue::default();
    let saved = json!({ "reminder_sound": true, "end_chime": false });

    assert!(queue.enqueue(true, true, &object(json!({ "reminder_sound": false }))));
    let _ = queue.next(true, false, 0, Some(&saved));
    queue.mark_in_flight(1);

    assert!(queue.enqueue(true, true, &object(json!({ "end_chime": true }))));

    // First PUT fails, so stored preferences stay `saved`. Queued second change still flushes
    // cleanly on top of `saved` (not carrying the failed change).
    queue.finish(1);
    assert_eq!(
        queue.next(true, false, 1, Some(&saved)),
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({ "reminder_sound": true, "end_chime": true }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 1,
        }
    );
}

#[test]
fn preferences_queue_guards_signed_out_empty_updates_busy_and_account_switch() {
    let mut queue = PreferencesQueue::default();
    let prefs = json!({ "clock_24h": false });

    assert!(!queue.enqueue(false, true, &object(json!({ "clock_24h": true }))));
    assert!(!queue.enqueue(true, false, &object(json!({ "clock_24h": true }))));
    assert!(!queue.has_pending());

    // An empty `{}` save is still sent so its callback is invoked.
    assert!(queue.enqueue(true, true, &object(json!({}))));
    assert!(queue.has_pending());
    assert_eq!(
        queue.next(true, false, 0, Some(&prefs)),
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({ "clock_24h": false }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 1,
        }
    );

    // Preempted in-flight ticket cannot wedge once the session goes idle again.
    queue.mark_in_flight(1);
    assert!(queue.enqueue(true, true, &object(json!({ "clock_24h": true }))));
    assert_eq!(
        queue.next(true, true, 2, Some(&prefs)),
        SavePreferencesAction::Wait
    );
    assert_eq!(
        queue.next(true, false, 2, Some(&prefs)),
        SavePreferencesAction::Send {
            method: "PUT",
            path: "/api/preferences",
            body: json!({ "clock_24h": true }),
            progress: SAVING_PREFERENCES,
            done: SAVED_PREFERENCES,
            batch_len: 1,
        }
    );

    // Account switch drops queued updates and invalidates any earlier fetch ticket.
    let token = queue.begin_fetch(true).unwrap();
    assert!(queue.accept_fetch(token, true));
    assert!(queue.enqueue(true, true, &object(json!({ "clock_24h": true }))));
    assert!(!queue.drop_if_other_account(Some(&json!(1)), &json!(1)));
    assert!(queue.has_pending());
    assert!(queue.drop_if_other_account(Some(&json!(1)), &json!(2)));
    assert!(!queue.has_pending());
    assert!(!queue.accept_fetch(token, true));
}

#[test]
fn preferences_fetch_ticket_rejects_signed_out_and_stale_replies() {
    let mut queue = PreferencesQueue::default();
    assert_eq!(queue.begin_fetch(false), None);

    let first = queue.begin_fetch(true).unwrap();
    assert_eq!(first, 1);
    assert!(queue.accept_fetch(first, true));
    assert!(!queue.accept_fetch(first, false));

    let second = queue.begin_fetch(true).unwrap();
    assert_eq!(second, 2);
    assert!(!queue.accept_fetch(first, true));
    assert!(queue.accept_fetch(second, true));
}

#[test]
fn prepare_timer_split_preview_builds_five_field_body_or_absent() {
    let prefs = json!({
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
        "clock_24h": true,
    });
    assert_eq!(
        prepare_timer_split_preview(false, Some(&prefs), 90),
        TimerSplitPreview::Absent
    );
    assert_eq!(
        prepare_timer_split_preview(true, None, 90),
        TimerSplitPreview::Absent
    );
    assert_eq!(
        prepare_timer_split_preview(true, Some(&prefs), 90),
        TimerSplitPreview::Ready {
            method: "POST",
            path: "/api/timer-split-preview",
            body: json!({
                "duration_min": 90,
                "timer_work_min": 30,
                "timer_break_min": 15,
                "timer_long_break_min": 30,
                "timer_long_break_every": 4,
            }),
        }
    );

    // Missing timer fields travel as null, matching dict.get().
    assert_eq!(
        prepare_timer_split_preview(true, Some(&json!({})), 45),
        TimerSplitPreview::Ready {
            method: "POST",
            path: "/api/timer-split-preview",
            body: json!({
                "duration_min": 45,
                "timer_work_min": null,
                "timer_break_min": null,
                "timer_long_break_min": null,
                "timer_long_break_every": null,
            }),
        }
    );
}

#[test]
fn parse_timer_tools_and_recovery_status_match_python_rules() {
    assert_eq!(
        parse_timer_presets(&json!({ "presets": [{ "id": "short" }] })).unwrap(),
        vec![json!({ "id": "short" })]
    );
    assert_eq!(
        parse_timer_presets(&json!({})).unwrap(),
        Vec::<Value>::new()
    );
    assert_eq!(
        parse_timer_presets(&json!({ "presets": null })).unwrap(),
        Vec::<Value>::new()
    );
    assert!(parse_timer_presets(&json!({ "presets": 7 })).is_err());

    assert_eq!(
        parse_reminder_limits(&json!({ "spotify": "Best effort." })).unwrap(),
        object(json!({ "spotify": "Best effort." }))
    );
    assert!(parse_reminder_limits(&json!([])).is_err());

    assert_eq!(
        parse_recovery_status(&json!({ "remaining": 8 })).unwrap(),
        8
    );
    assert_eq!(
        parse_recovery_status(&json!({ "remaining": "5" })).unwrap(),
        5
    );
    assert_eq!(
        parse_recovery_status(&json!({ "remaining": null })).unwrap(),
        0
    );
    assert_eq!(parse_recovery_status(&json!({})).unwrap(), 0);
    assert!(parse_recovery_status(&json!({ "remaining": "eight" })).is_err());
}

#[test]
fn work_window_constants_match_contract() {
    assert_eq!(MAX_WORK_WINDOWS, 21);
    assert_eq!(
        WORK_WINDOW_PRESETS,
        &[
            ("After school", &[0, 1, 2, 3, 4][..], "15:30", "18:00"),
            ("Evenings", &[0, 1, 2, 3, 4][..], "19:00", "21:00"),
            ("Weekend mornings", &[5, 6][..], "10:00", "12:00"),
        ]
    );
    assert_eq!(
        WORK_WINDOW_PRESETS_NOTE,
        "Each adds a row of hours you can change."
    );
    assert_eq!(
        HOURS_REFUSED,
        "Check the days and times in Study hours and Protected time."
    );
}
