//! Tests for `flexweek_app::views::account_auth` (P5-A1). Expected values come from the Material
//! account bridge requirements and the pinning desktop tests
//! (`test_material_sign_in_and_create_account.py`, `test_material_account_screen_words.py`,
//! `test_material_recovery_save.py`, `test_keep_signed_in_across_launches.py`), never from the code
//! under test.

use flexweek_app::session::words::{
    SESSION_ENDED, SIGN_IN_AGAIN, SIGN_IN_WRONG, TOO_MANY_TRIES, USERNAME_ERROR, USERNAME_TAKEN,
    WRONG_RECOVERY_CODE,
};
use flexweek_app::views::account_auth::{
    AUTH_PHASES, AuthPhase, AuthState, FINISH_DONE, FINISH_WAIT, PHASES, ProblemField,
    PromptAction, RECOVERY_ACK, RECOVERY_CONTINUE, RECOVERY_COPIED, RECOVERY_HEADING,
    RECOVERY_NOTE, RECOVERY_SAVED, RECOVERY_WRITE_FAILED, SubmitAction, WHY_TITLE,
    edited_prompt_choice, field_for, initial_phase, recovery_problem, words_json,
};
use flexweek_engine::ErrorKind;
use serde_json::{Map, Value, json};

fn json_map(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(map) => map,
        _ => panic!("expected JSON object"),
    }
}

#[test]
fn initial_phase_chooses_app_then_opening_then_sign_in() {
    assert_eq!(initial_phase(true, false), AuthPhase::App);
    assert_eq!(initial_phase(true, true), AuthPhase::App);
    assert_eq!(initial_phase(false, true), AuthPhase::Opening);
    assert_eq!(initial_phase(false, false), AuthPhase::SignIn);

    let signed_in = AuthState::new(true, true, true);
    assert_eq!(signed_in.phase(), "app");

    let opening = AuthState::new(false, true, true);
    assert_eq!(opening.phase(), "opening");

    let fresh = AuthState::new(false, false, false);
    assert_eq!(fresh.phase(), "sign-in");
    assert!(!fresh.keep_signed_in());
}

#[test]
fn resume_failed_moves_opening_to_sign_in_and_ignores_other_phases() {
    let mut state = AuthState::new(false, true, true);
    assert_eq!(state.phase(), "opening");
    assert!(state.on_resume_failed());
    assert_eq!(state.phase(), "sign-in");
    // Already on sign-in: a second failure does not emit again.
    assert!(!state.on_resume_failed());

    let mut app = AuthState::new(true, false, true);
    assert!(!app.on_resume_failed());
    assert_eq!(app.phase(), "app");
}

#[test]
fn show_sign_in_clear_drops_typed_fields_and_keeps_them_otherwise() {
    let mut state = AuthState::new(false, false, true);
    state.set_username("alice".into());
    state.set_password("long-secret-password".into());
    state.set_recovery_code("aaaa-bbbb".into());
    state.set_new_password("another-long-password".into());
    state.on_status(SIGN_IN_WRONG);
    assert!(state.explain_why());
    assert!(state.why_open());

    state.show_create();
    assert_eq!(state.phase(), "create");
    assert_eq!(state.username(), "alice");
    assert_eq!(state.password(), "long-secret-password");
    assert_eq!(state.password_problem(), "");
    assert_eq!(state.status_line(), "");
    assert!(!state.why_open());

    state.show_sign_in(false);
    assert_eq!(state.phase(), "sign-in");
    assert_eq!(state.username(), "alice");
    assert_eq!(state.password(), "long-secret-password");
    assert_eq!(state.recovery_code(), "aaaa-bbbb");
    assert_eq!(state.new_password(), "another-long-password");

    state.show_sign_in(true);
    assert_eq!(state.phase(), "sign-in");
    assert_eq!(state.username(), "");
    assert_eq!(state.password(), "");
    assert_eq!(state.recovery_code(), "");
    assert_eq!(state.new_password(), "");
}

#[test]
fn heading_note_and_hints_match_every_phase() {
    let mut state = AuthState::new(false, false, true);
    assert_eq!(state.heading(None).unwrap(), "Sign in");
    assert_eq!(state.note(None).unwrap(), "");
    assert_eq!(state.username_hint(), "");
    assert_eq!(state.password_hint(), "");

    state.show_create();
    assert_eq!(state.heading(None).unwrap(), "Create your account");
    assert_eq!(
        state.note(None).unwrap(),
        "FlexWeek fits homework around school and sports. Your week is saved on this computer, under this account. Export a backup file now and then (Settings > This computer > Manage account)."
    );
    assert_eq!(
        state.username_hint(),
        "3 to 32 letters, numbers or underscores."
    );
    assert_eq!(state.password_hint(), "At least 12 characters.");

    state.show_reset();
    assert_eq!(state.heading(None).unwrap(), "Reset your password");
    assert_eq!(
        state.note(None).unwrap(),
        "Use one of the recovery codes you saved when you made your account. Lost them too? Create a new account and import a backup file, or start fresh."
    );
    assert_eq!(state.username_hint(), "");
    assert_eq!(state.password_hint(), "");

    state.show_recovery(vec!["aaaa-bbbb".into()]);
    assert_eq!(state.heading(None).unwrap(), RECOVERY_HEADING);
    assert_eq!(state.note(None).unwrap(), RECOVERY_NOTE);

    state.set_phase("setup").unwrap();
    assert_eq!(state.heading(Some("School hours")).unwrap(), "School hours");
    assert_eq!(
        state.note(Some("Pick your school hours")).unwrap(),
        "Pick your school hours"
    );
    assert_eq!(state.heading(None).unwrap_err().kind, ErrorKind::Key);
    assert_eq!(state.note(None).unwrap_err().kind, ErrorKind::Key);

    state.show_app();
    assert_eq!(state.heading(None).unwrap(), "");
    assert_eq!(state.note(None).unwrap(), "");

    let opening = AuthState::new(false, true, true);
    assert_eq!(opening.heading(None).unwrap(), "");
    assert_eq!(opening.note(None).unwrap(), "");
}

#[test]
fn set_phase_rejects_unknown_names() {
    let mut state = AuthState::new(false, false, true);
    let err = state.set_phase("bogus").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Value);
    assert_eq!(state.phase(), "sign-in");
}

#[test]
fn sign_in_submit_validates_then_trims_username_only() {
    let mut state = AuthState::new(false, false, true);
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(state.username_problem(), "Type your username.");
    assert_eq!(state.password_problem(), "");

    state.set_username("  sam  ".into());
    assert_eq!(state.username_problem(), "");
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(state.password_problem(), "Type your password.");

    state.set_password(" short ".into());
    assert_eq!(state.password_problem(), "");
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(
        state.password_problem(),
        "Passwords have at least 12 characters. Try again, or choose Forgot password."
    );

    // Leading/trailing spaces in the password are preserved; username is stripped.
    state.set_password(" a-long-password ".into());
    assert_eq!(
        state.submit().unwrap(),
        SubmitAction::Login {
            username: "sam".into(),
            password: " a-long-password ".into(),
        }
    );
}

#[test]
fn create_submit_validates_username_and_password_length_then_registers() {
    let mut state = AuthState::new(false, false, true);
    state.show_create();
    state.set_username("ab".into());
    state.set_password("a-long-test-password".into());
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(state.username_problem(), USERNAME_ERROR);

    state.set_username("new_student".into());
    state.set_password("short".into());
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(
        state.password_problem(),
        "Add 7 more characters. Passwords need at least 12 characters."
    );

    state.set_password("eleven_char".into());
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(
        state.password_problem(),
        "Add 1 more character. Passwords need at least 12 characters."
    );

    state.set_password("valid_password_12".into());
    assert_eq!(
        state.submit().unwrap(),
        SubmitAction::Register {
            username: "new_student".into(),
            password: "valid_password_12".into(),
        }
    );
}

#[test]
fn reset_submit_validates_recovery_fields_and_strips_username_and_code() {
    assert_eq!(recovery_problem("   ", "", ""), "Type your username.");
    assert_eq!(recovery_problem("alex", "  ", ""), "Type a recovery code.");
    assert_eq!(
        recovery_problem("alex", "aaaa-bbbb", ""),
        "Choose a password with at least 12 characters."
    );
    assert_eq!(
        recovery_problem("alex", "aaaa-bbbb", "short"),
        "Add 7 more characters. Passwords need at least 12 characters."
    );
    assert_eq!(recovery_problem("alex", "aaaa-bbbb", "twelve_chars"), "");

    let mut state = AuthState::new(false, false, true);
    state.show_reset();
    state.set_username("  forgetful_student  ".into());
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(state.recovery_problem_text(), "Type a recovery code.");

    state.set_recovery_code("  code-1234  ".into());
    assert_eq!(state.recovery_problem_text(), "");
    state.set_new_password("short".into());
    assert_eq!(state.submit().unwrap(), SubmitAction::Problem);
    assert_eq!(
        state.new_password_problem(),
        "Add 7 more characters. Passwords need at least 12 characters."
    );

    state.set_new_password("  other-password-ok  ".into());
    assert_eq!(state.new_password_problem(), "");
    assert_eq!(
        state.submit().unwrap(),
        SubmitAction::Recover {
            username: "forgetful_student".into(),
            code: "code-1234".into(),
            new_password: "  other-password-ok  ".into(),
        }
    );
}

#[test]
fn submit_does_nothing_outside_auth_phases() {
    for phase in ["opening", "recovery", "setup", "app"] {
        let mut state = AuthState::new(false, false, true);
        state.set_phase(phase).unwrap();
        assert_eq!(state.submit().unwrap(), SubmitAction::None, "{phase}");
    }
}

#[test]
fn field_for_classifies_server_messages_with_exact_precedence() {
    // SIGN_IN_AGAIN names both username and password, yet stays on the general status line.
    assert_eq!(field_for(AuthPhase::SignIn, SIGN_IN_AGAIN), None);
    assert_eq!(field_for(AuthPhase::Reset, SIGN_IN_AGAIN), None);
    assert_eq!(field_for(AuthPhase::SignIn, SESSION_ENDED), None);

    // TOO_MANY_TRIES goes to password on sign-in/create and recovery on reset.
    assert_eq!(
        field_for(AuthPhase::SignIn, TOO_MANY_TRIES),
        Some(ProblemField::Password)
    );
    assert_eq!(
        field_for(AuthPhase::Create, TOO_MANY_TRIES),
        Some(ProblemField::Password)
    );
    assert_eq!(
        field_for(AuthPhase::Reset, TOO_MANY_TRIES),
        Some(ProblemField::Recovery)
    );

    // USERNAME_ERROR goes to username even though it does not contain the word "username".
    assert_eq!(
        field_for(AuthPhase::Create, USERNAME_ERROR),
        Some(ProblemField::Username)
    );

    // Wrong username or password starts with that phrase and must route to password, not username.
    assert_eq!(
        field_for(AuthPhase::SignIn, SIGN_IN_WRONG),
        Some(ProblemField::Password)
    );

    // Recovery code wording wins over "username" inside the same sentence.
    assert_eq!(
        field_for(AuthPhase::Reset, WRONG_RECOVERY_CODE),
        Some(ProblemField::Recovery)
    );
    assert_eq!(
        field_for(AuthPhase::Reset, "Each code works only once."),
        Some(ProblemField::Recovery)
    );

    // General username and password keyword fallbacks.
    assert_eq!(
        field_for(AuthPhase::Create, USERNAME_TAKEN),
        Some(ProblemField::Username)
    );
    assert_eq!(
        field_for(
            AuthPhase::SignIn,
            "Choose a password with at least 12 characters."
        ),
        Some(ProblemField::Password)
    );
    assert_eq!(
        field_for(
            AuthPhase::Reset,
            "Choose a password with at least 12 characters."
        ),
        Some(ProblemField::New)
    );
    assert_eq!(
        field_for(
            AuthPhase::SignIn,
            "FlexWeek can't open its saved data right now. Wait a minute, then sign in."
        ),
        None
    );
}

#[test]
fn on_status_respects_auth_phases_ellipsis_empty_and_unclassified_messages() {
    let mut opening = AuthState::new(false, true, true);
    assert!(!opening.on_status(SIGN_IN_AGAIN));
    assert_eq!(opening.status_line(), "");

    let mut state = AuthState::new(false, false, true);
    assert!(state.on_status(SIGN_IN_WRONG));
    assert_eq!(state.password_problem(), SIGN_IN_WRONG);
    assert_eq!(state.status_line(), "");

    // Progress messages ending in U+2026 update statusLine without clearing field problems.
    assert!(state.on_status("Signing in\u{2026}"));
    assert_eq!(state.status_line(), "Signing in\u{2026}");
    assert_eq!(state.password_problem(), SIGN_IN_WRONG);

    // Unclassified messages also leave existing field problems intact (distinct from show_problem).
    assert!(state.on_status(SIGN_IN_AGAIN));
    assert_eq!(state.status_line(), SIGN_IN_AGAIN);
    assert_eq!(state.password_problem(), SIGN_IN_WRONG);

    // Empty message clears both field problems and status line.
    assert!(state.on_status(""));
    assert_eq!(state.status_line(), "");
    assert_eq!(state.password_problem(), "");

    // show_problem clears previous field problems even for an unclassified message.
    state.show_problem(USERNAME_TAKEN);
    assert_eq!(state.username_problem(), USERNAME_TAKEN);
    state.show_problem(SIGN_IN_AGAIN);
    assert_eq!(state.username_problem(), "");
    assert_eq!(state.status_line(), SIGN_IN_AGAIN);
}

#[test]
fn why_visible_and_why_open_follow_wrong_sign_in_and_typing() {
    let mut state = AuthState::new(false, false, true);
    assert!(!state.why_visible());
    assert!(!state.explain_why());
    assert!(!state.why_open());

    // Other password errors must not expose the "Why doesn't it say which?" link.
    state.on_status("Type your password.");
    assert_eq!(state.password_problem(), "Type your password.");
    assert!(!state.why_visible());
    assert!(!state.explain_why());

    state.on_status(TOO_MANY_TRIES);
    assert_eq!(state.password_problem(), TOO_MANY_TRIES);
    assert!(!state.why_visible());

    state.on_status(SIGN_IN_WRONG);
    assert!(state.why_visible());
    assert!(state.explain_why());
    assert!(state.why_open());

    // Typing a username leaves the password problem and whyOpen untouched.
    state.set_username("alice".into());
    assert!(state.why_visible());
    assert!(state.why_open());

    // Typing a password clears the password problem and closes the explanation.
    state.set_password("new-guess".into());
    assert!(!state.why_visible());
    assert!(!state.why_open());

    // dismiss_why closes an open explanation without clearing the error line.
    state.on_status(SIGN_IN_WRONG);
    assert!(state.explain_why());
    state.dismiss_why();
    assert!(state.why_visible());
    assert!(!state.why_open());
}

#[test]
fn recovery_codes_ack_copy_save_and_finish_rules() {
    let mut state = AuthState::new(false, false, true);
    state.show_recovery(vec!["aaaa-bbbb".into(), "cccc-dddd".into()]);
    assert_eq!(state.phase(), "recovery");
    assert_eq!(state.codes(), vec!["aaaa-bbbb", "cccc-dddd"]);
    assert_eq!(state.recovery_codes_text(), "aaaa-bbbb\ncccc-dddd");
    assert!(!state.recovery_ack());
    assert!(!state.recovery_ready(false));
    assert_eq!(state.copy_label(), "Copy");
    assert_eq!(state.save_label(), "Save\u{2026}");
    assert_eq!(state.recovery_status(), "");

    // Finish waits until acknowledged.
    assert_eq!(state.finish_recovery(), FINISH_WAIT);
    assert_eq!(
        state.recovery_status(),
        "Turn on \u{201c}I have saved these codes\u{201d} to continue."
    );

    // Copy returns newline-terminated text and flips copyLabel until timer resets it.
    assert_eq!(state.copy_codes(), "aaaa-bbbb\ncccc-dddd\n");
    assert_eq!(state.copy_label(), RECOVERY_COPIED);

    // Save payload refuses empty or missing path; write failure sets recoveryStatus; success sets Saved.
    assert_eq!(state.recovery_file_payload(None), None);
    assert_eq!(state.recovery_file_payload(Some("")), None);
    assert_eq!(
        state.recovery_file_payload(Some("/tmp/codes.txt")),
        Some("aaaa-bbbb\ncccc-dddd\n".to_string())
    );
    state.mark_save_failed();
    assert_eq!(state.recovery_status(), RECOVERY_WRITE_FAILED);
    assert_eq!(state.save_label(), "Save\u{2026}");
    state.mark_save_succeeded();
    assert_eq!(state.recovery_status(), "");
    assert_eq!(state.save_label(), RECOVERY_SAVED);

    state.reset_recovery_labels();
    assert_eq!(state.copy_label(), "Copy");
    assert_eq!(state.save_label(), "Save\u{2026}");

    // Ack enables ready only while not busy, and unlocks finish.
    state.set_recovery_ack(true);
    assert!(!state.recovery_ready(true));
    assert!(state.recovery_ready(false));
    assert_eq!(state.finish_recovery(), FINISH_DONE);
}

#[test]
fn show_app_transitions_once_and_clears_why_open() {
    let mut state = AuthState::new(false, false, true);
    state.on_status(SIGN_IN_WRONG);
    assert!(state.explain_why());

    assert!(state.show_app());
    assert_eq!(state.phase(), "app");
    assert!(!state.why_open());
    // Calling show_app again is a no-op.
    assert!(!state.show_app());
}

#[test]
fn prompt_routing_handles_handler_questions_edited_weeks_and_idle_close() {
    assert_eq!(edited_prompt_choice("keep"), Some("keep"));
    assert_eq!(edited_prompt_choice("replace"), Some("replace"));
    assert_eq!(edited_prompt_choice("from_today"), Some("from_today"));
    assert_eq!(edited_prompt_choice("stay"), None);

    let mut state = AuthState::new(false, false, true);
    // Idle close/answer does nothing.
    assert_eq!(state.close_sheet(), PromptAction::None);
    assert_eq!(state.answer("keep"), PromptAction::None);

    // Handler question (recovery file save prompt).
    let prompt = json_map(json!({"id": "recovery-file", "title": "Save recovery codes"}));
    state.pose_question(prompt.clone(), true);
    assert_eq!(state.ask_value()["title"], "Save recovery codes");
    assert_eq!(
        state.answer("choose"),
        PromptAction::Question {
            choice: "choose".into(),
        }
    );
    assert_eq!(state.ask_value(), json!({}));

    state.pose_question(prompt, true);
    assert_eq!(state.close_sheet(), PromptAction::QuestionClosed);
    assert_eq!(state.ask_value(), json!({}));

    // Edited-weeks prompt: valid answers pass through; unknown answers become None; close cancels.
    let edited = json_map(json!({"id": "edited-weeks", "title": "Edited weeks"}));
    state.pose_edited(edited.clone(), true);
    assert_eq!(
        state.answer("replace"),
        PromptAction::Edited {
            choice: Some("replace".into()),
        }
    );
    assert_eq!(state.ask_value(), json!({}));

    state.pose_edited(edited.clone(), true);
    assert_eq!(
        state.answer("cancel"),
        PromptAction::Edited { choice: None }
    );

    state.pose_edited(edited, true);
    assert_eq!(state.close_sheet(), PromptAction::Edited { choice: None });

    // Empty ask dict with a callback still triggers Edited; empty ask with no callback is None.
    state.pose_edited(Map::new(), true);
    assert_eq!(state.close_sheet(), PromptAction::Edited { choice: None });
    state.pose_edited(Map::new(), false);
    assert_eq!(state.close_sheet(), PromptAction::None);
}

#[test]
fn exported_words_match_constants() {
    let words = words_json();
    assert_eq!(words["recovery_heading"], RECOVERY_HEADING);
    assert_eq!(words["recovery_note"], RECOVERY_NOTE);
    assert_eq!(words["recovery_ack"], RECOVERY_ACK);
    assert_eq!(words["recovery_continue"], RECOVERY_CONTINUE);
    assert_eq!(words["why_title"], WHY_TITLE);
    assert_eq!(words["auth_phases"], json!(AUTH_PHASES));
    assert_eq!(words["phases"], json!(PHASES));
}
