//! Tests for `flexweek_app::views::focus` (P5-F1). Expected values come from the rules the
//! Material Focus bridge held in Python and from the desktop Focus tests that pin them
//! (`test_material_focus_screen.py`, `test_focus_returns_to_its_opener.py`), never from the code
//! under test.

use flexweek_app::views::focus::{
    STEP_CONFIRM_END, STEP_HIDE, STEP_REQUEST_END, STEP_STAY, active, after_start_step, back_step,
    block_for_start, can_finish_homework, end_question, ended, finish_step, leave_step, note,
    offered, pause_text, paused, phase, phase_text, ready, refresh_open, remembers_origin,
    restores_origin, running, skip_hint, time_text, title,
};
use flexweek_engine::ErrorKind;
use serde_json::{Value, json};

fn none() -> Value {
    Value::Null
}

fn running_work() -> Value {
    json!({"phase": "work", "running": true, "endsAt": 2_000_000, "title": "Geography"})
}

fn paused_work() -> Value {
    json!({"phase": "work", "running": false, "remainingMs": 300_000, "title": "Geography"})
}

fn ended_state() -> Value {
    json!({"phase": "ended", "running": true, "assignmentId": "essay2", "title": "Essay"})
}

#[test]
fn no_timer_is_ready_and_nothing_else() {
    let state = none();
    assert_eq!(phase(&state).unwrap(), "ready");
    assert!(ready(&state));
    assert!(!ended(&state).unwrap());
    assert!(!active(&state).unwrap());
    assert!(!running(&state).unwrap());
    assert!(!paused(&state).unwrap());
}

#[test]
fn a_running_work_timer_is_active_and_running_but_not_paused() {
    let state = running_work();
    assert_eq!(phase(&state).unwrap(), "work");
    assert!(!ready(&state));
    assert!(!ended(&state).unwrap());
    assert!(active(&state).unwrap());
    assert!(running(&state).unwrap());
    assert!(!paused(&state).unwrap());
}

#[test]
fn a_timer_that_is_not_running_is_paused() {
    let state = paused_work();
    assert!(active(&state).unwrap());
    assert!(!running(&state).unwrap());
    assert!(paused(&state).unwrap());
}

#[test]
fn an_ended_session_is_never_running_active_or_paused_even_if_its_flag_says_running() {
    let state = ended_state();
    assert_eq!(phase(&state).unwrap(), "ended");
    assert!(ended(&state).unwrap());
    assert!(!active(&state).unwrap());
    assert!(!running(&state).unwrap());
    assert!(!paused(&state).unwrap());
}

#[test]
fn a_missing_or_empty_phase_reads_as_work() {
    for state in [
        json!({}),
        json!({"phase": null}),
        json!({"phase": ""}),
        json!({"phase": 0}),
    ] {
        assert_eq!(phase(&state).unwrap(), "work", "{state}");
    }
    assert_eq!(phase(&json!({"phase": "break"})).unwrap(), "break");
    assert_eq!(phase(&json!({"phase": 7})).unwrap(), "7");
}

#[test]
fn a_state_with_no_fields_is_active_but_never_running() {
    // A state with no fields is not None (a timer exists) but is falsy, so it never counts as running.
    let state = json!({"running": true});
    assert!(running(&state).unwrap());
    let empty = json!({});
    assert!(active(&empty).unwrap());
    assert!(!running(&empty).unwrap());
    assert!(paused(&empty).unwrap());
}

#[test]
fn the_phase_text_names_the_phase_and_adds_paused() {
    assert_eq!(phase_text(&none()).unwrap(), "Ready when you are");
    assert_eq!(phase_text(&running_work()).unwrap(), "Focus");
    assert_eq!(phase_text(&paused_work()).unwrap(), "Focus · Paused");
    assert_eq!(
        phase_text(&json!({"phase": "break", "running": true})).unwrap(),
        "Break"
    );
    assert_eq!(
        phase_text(&json!({"phase": "break", "running": false})).unwrap(),
        "Break · Paused"
    );
    assert_eq!(
        phase_text(&json!({"phase": "long_break", "running": true})).unwrap(),
        "Long break"
    );
    assert_eq!(phase_text(&ended_state()).unwrap(), "Session finished");
    assert_eq!(
        phase_text(&json!({"phase": "ended", "running": false})).unwrap(),
        "Session finished"
    );
}

#[test]
fn an_unknown_phase_has_no_words_but_still_says_paused() {
    assert_eq!(
        phase_text(&json!({"phase": "mystery", "running": true})).unwrap(),
        ""
    );
    assert_eq!(
        phase_text(&json!({"phase": "mystery", "running": false})).unwrap(),
        " · Paused"
    );
}

#[test]
fn ready_names_the_offered_homework_or_says_quick_focus() {
    assert_eq!(title(&none(), &none()).unwrap(), "Quick focus");
    let offer = json!({"title": "History", "blockId": "b1"});
    assert_eq!(title(&none(), &offer).unwrap(), "History");
    assert!(offered(&none(), &offer));
    assert!(!offered(&none(), &none()));
}

#[test]
fn a_running_timer_has_already_chosen_so_the_offer_is_ignored() {
    let offer = json!({"title": "History"});
    assert_eq!(title(&running_work(), &offer).unwrap(), "Geography");
    assert!(!offered(&running_work(), &offer));
    assert_eq!(
        title(&json!({"phase": "work"}), &offer).unwrap(),
        "Quick focus"
    );
    assert_eq!(
        title(&json!({"phase": "work", "title": ""}), &none()).unwrap(),
        "Quick focus"
    );
}

#[test]
fn an_offer_without_a_title_is_a_key_error_as_it_was() {
    let error = title(&none(), &json!({"blockId": "b1"})).unwrap_err();
    assert_eq!(error.kind, ErrorKind::Key);
}

#[test]
fn the_time_text_is_a_full_work_phase_while_ready() {
    assert_eq!(time_text(&none(), &none(), 5).unwrap(), "30:00");
    assert_eq!(
        time_text(&none(), &json!({"timer_work_min": 25}), 5).unwrap(),
        "25:00"
    );
    assert_eq!(
        time_text(&none(), &json!({"timer_work_min": 0}), 5).unwrap(),
        "30:00"
    );
}

#[test]
fn a_running_timer_counts_down_to_its_end_rounding_a_part_second_up() {
    // 2_000_000 - 1_909_500 = 90_500 ms: 90.5 s shows as 91 s.
    assert_eq!(
        time_text(&running_work(), &none(), 1_909_500).unwrap(),
        "01:31"
    );
    assert_eq!(
        time_text(&running_work(), &none(), 2_000_000).unwrap(),
        "00:00"
    );
    assert_eq!(
        time_text(&running_work(), &none(), 2_500_000).unwrap(),
        "00:00"
    );
}

#[test]
fn a_paused_timer_shows_what_it_kept_and_an_ended_one_shows_zero() {
    assert_eq!(
        time_text(&paused_work(), &none(), 999_999_999).unwrap(),
        "05:00"
    );
    assert_eq!(time_text(&ended_state(), &none(), 1).unwrap(), "00:00");
}

#[test]
fn pause_text_follows_running_and_skip_hint_follows_the_phase() {
    assert_eq!(pause_text(&running_work()).unwrap(), "Pause");
    assert_eq!(pause_text(&paused_work()).unwrap(), "Resume");
    assert_eq!(pause_text(&none()).unwrap(), "Resume");
    assert_eq!(skip_hint(&running_work()).unwrap(), "Skip to the break");
    assert_eq!(
        skip_hint(&json!({"phase": "break"})).unwrap(),
        "Skip the break"
    );
    assert_eq!(
        skip_hint(&json!({"phase": "long_break"})).unwrap(),
        "Skip the break"
    );
    assert_eq!(skip_hint(&ended_state()).unwrap(), "Skip");
    assert_eq!(skip_hint(&none()).unwrap(), "Skip");
}

#[test]
fn the_note_lists_muted_alerts_and_the_sound_once_a_timer_exists() {
    let rain = json!({"focus_audio": "rain"});
    assert_eq!(
        note(&running_work(), &rain, true).unwrap(),
        "Alerts muted · Rain"
    );
    assert_eq!(note(&running_work(), &rain, false).unwrap(), "Rain");
    assert_eq!(
        note(&running_work(), &none(), true).unwrap(),
        "Alerts muted"
    );
    assert_eq!(note(&running_work(), &none(), false).unwrap(), "");
    // Ready has no timer yet: the sound is not on.
    assert_eq!(note(&none(), &rain, false).unwrap(), "");
    assert_eq!(note(&none(), &rain, true).unwrap(), "Alerts muted");
}

#[test]
fn every_sound_has_its_words_and_an_unknown_one_has_none() {
    for (key, words) in [
        ("rain", "Rain"),
        ("lo-fi", "Lo-Fi"),
        ("white-noise", "White noise"),
        ("spotify", "Spotify"),
    ] {
        assert_eq!(
            note(&running_work(), &json!({"focus_audio": key}), false).unwrap(),
            words
        );
    }
    for audio in [json!("off"), json!(""), json!(null), json!(5)] {
        assert_eq!(
            note(&running_work(), &json!({"focus_audio": audio}), false).unwrap(),
            "",
            "{audio}"
        );
    }
    assert_eq!(note(&running_work(), &json!({}), false).unwrap(), "");
}

#[test]
fn finished_is_offered_only_for_an_ended_session_on_homework_still_open() {
    let open = json!({"essay2": {"completed": false}});
    let done = json!({"essay2": {"completed": true}});
    assert!(can_finish_homework(&ended_state(), &open).unwrap());
    assert!(!can_finish_homework(&ended_state(), &done).unwrap());
    assert!(can_finish_homework(&ended_state(), &json!({"essay2": {}})).unwrap());
    assert!(!can_finish_homework(&ended_state(), &json!({"other": {}})).unwrap());
    assert!(!can_finish_homework(&ended_state(), &none()).unwrap());
    assert!(!can_finish_homework(&running_work(), &open).unwrap());
    assert!(!can_finish_homework(&none(), &open).unwrap());
    // A quick focus has no homework to mark.
    let quick = json!({"phase": "ended", "assignmentId": null});
    assert!(!can_finish_homework(&quick, &open).unwrap());
    assert!(!can_finish_homework(&json!({"phase": "ended"}), &open).unwrap());
}

#[test]
fn the_end_question_names_the_minutes_and_the_title() {
    assert_eq!(
        end_question(&none(), &none(), "Quick focus", 0).unwrap(),
        "You've done 0 min of Quick focus."
    );
    assert_eq!(
        end_question(&running_work(), &none(), "Geography", 12).unwrap(),
        "You've done 12 min of Geography."
    );
}

#[test]
fn the_end_question_adds_that_it_counts_toward_homework_the_session_holds() {
    let held = json!({"essay2": {"completed": false}});
    let state = json!({"phase": "work", "assignmentId": "essay2"});
    assert_eq!(
        end_question(&state, &held, "Essay", 25).unwrap(),
        "You've done 25 min of Essay. It counts toward the homework."
    );
    // Homework the session no longer holds, a quick focus and a null id add nothing.
    assert_eq!(
        end_question(&state, &json!({"other": {}}), "Essay", 25).unwrap(),
        "You've done 25 min of Essay."
    );
    assert_eq!(
        end_question(&json!({"phase": "work"}), &held, "Essay", 25).unwrap(),
        "You've done 25 min of Essay."
    );
    assert_eq!(
        end_question(&state, &none(), "Essay", 25).unwrap(),
        "You've done 25 min of Essay."
    );
}

#[test]
fn the_screen_closes_when_the_session_is_gone_and_otherwise_keeps_its_state() {
    assert!(!refresh_open(true, true));
    assert!(refresh_open(true, false));
    assert!(!refresh_open(false, false));
    assert!(!refresh_open(false, true));
}

#[test]
fn finish_asks_for_a_begun_timer_closes_a_ready_one_and_confirms_an_ended_one() {
    assert_eq!(leave_step(&running_work()).unwrap(), STEP_REQUEST_END);
    assert_eq!(leave_step(&paused_work()).unwrap(), STEP_REQUEST_END);
    assert_eq!(leave_step(&none()).unwrap(), STEP_HIDE);
    assert_eq!(leave_step(&ended_state()).unwrap(), STEP_CONFIRM_END);
}

#[test]
fn back_keeps_a_begun_timer_going_and_otherwise_leaves_as_finish_does() {
    assert_eq!(back_step(&running_work()).unwrap(), STEP_HIDE);
    assert_eq!(back_step(&paused_work()).unwrap(), STEP_HIDE);
    assert_eq!(back_step(&none()).unwrap(), STEP_HIDE);
    assert_eq!(back_step(&ended_state()).unwrap(), STEP_CONFIRM_END);
}

#[test]
fn only_a_finished_or_queued_homework_closes_the_screen() {
    assert_eq!(finish_step(Some("finished")), STEP_HIDE);
    assert_eq!(finish_step(Some("queued")), STEP_HIDE);
    assert_eq!(finish_step(Some("ignored")), STEP_STAY);
    assert_eq!(finish_step(Some("")), STEP_STAY);
    assert_eq!(finish_step(None), STEP_STAY);
}

#[test]
fn a_started_focus_opens_the_screen_and_a_refused_one_does_not() {
    assert_eq!(after_start_step(true), "show");
    assert_eq!(after_start_step(false), STEP_STAY);
    assert_eq!(block_for_start("b1"), Some("b1"));
    assert_eq!(block_for_start(""), None);
}

#[test]
fn the_opener_is_remembered_unless_it_is_the_focus_screen_itself() {
    assert!(remembers_origin("weekAddButton"));
    assert!(remembers_origin(""));
    assert!(!remembers_origin("materialFocus"));
}

#[test]
fn the_opener_gets_focus_back_only_while_shown_enabled_and_able_to_take_it() {
    assert!(restores_origin(true, true, true));
    assert!(!restores_origin(false, true, true));
    assert!(!restores_origin(true, false, true));
    assert!(!restores_origin(true, true, false));
}

#[test]
fn a_state_that_is_not_a_dict_raises_what_python_raised() {
    for call in [
        phase(&json!("x")).unwrap_err(),
        active(&json!(3)).unwrap_err(),
        running(&json!(["a"])).unwrap_err(),
    ] {
        assert_eq!(call.kind, ErrorKind::Attribute);
    }
    // An empty list is falsy, so `running` stops before it asks for `get`.
    assert!(!running(&json!([])).unwrap());
    assert!(phase(&json!(null)).is_ok());
}
