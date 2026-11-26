//! Signing in, up and out through the session (P4 group 1, account.rs), against a real throwaway database.
//! Expected words and order are controller.py's `register`, `login`, `resume`, `logout` and `_fail`, and
//! client.py's `auth_error`.

use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use std::sync::mpsc::{Receiver, channel};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use flexweek_app::session::account::auth_words;
use flexweek_app::session::frame::{Host, REQUEST_LIMIT_MS};
use flexweek_app::session::{Session, words};
use flexweek_service::accounts::{Entropy, RECOVERY_CODE_COUNT};
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";

struct TestHost {
    steady: AtomicI64,
    draws: AtomicU64,
    /// While set, each request's work waits here for one opening.
    gate: Mutex<Option<Receiver<()>>>,
}

impl Host for TestHost {
    fn steady_ms(&self) -> i64 {
        self.steady.load(Ordering::SeqCst)
    }
    fn request_clock(&self) -> (i64, String) {
        (1_793_905_200, "2026-11-05T19:00".into())
    }
    fn restore_token(&self) -> String {
        format!("{:016x}", self.draws.fetch_add(1, Ordering::SeqCst))
    }
    fn entropy(&self) -> Box<dyn Entropy + Send> {
        if let Some(gate) = self.gate.lock().unwrap().as_ref() {
            let _ = gate.recv();
        }
        Box::new(Counting(self.draws.fetch_add(1000, Ordering::SeqCst)))
    }
    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

struct Rig {
    session: Session,
    host: Arc<TestHost>,
    woken: Receiver<()>,
    _db: TestDb,
}

fn rig(name: &str) -> Rig {
    let db = TestDb::new(name);
    let host = Arc::new(TestHost {
        steady: AtomicI64::new(1_000),
        draws: AtomicU64::new(1),
        gate: Mutex::new(None),
    });
    let (wake, woken) = channel();
    let wake = Mutex::new(wake);
    let session = Session::new(
        db.path.clone(),
        host.clone(),
        Arc::new(move || {
            let _ = wake.lock().unwrap().send(());
        }),
    );
    Rig {
        session,
        host,
        woken,
        _db: db,
    }
}

impl Rig {
    /// Holds every request's work until `answer` is sent, then moves the steady clock past the limit: the next
    /// event taken is the request failing as unanswered.
    fn hold_past_the_limit(&self) -> std::sync::mpsc::Sender<()> {
        let (open, gate) = channel();
        *self.host.gate.lock().unwrap() = Some(gate);
        open
    }

    fn timed_out(&mut self) -> Value {
        self.host
            .steady
            .fetch_add(REQUEST_LIMIT_MS, Ordering::SeqCst);
        serde_json::from_str(&self.session.take_event()).unwrap()
    }

    fn send(&mut self, command: Value) -> Value {
        serde_json::from_str(&self.session.send(&command.to_string())).unwrap()
    }

    fn view(&self, name: &str) -> Value {
        serde_json::from_str(&self.session.view(name)).unwrap()
    }

    /// Waits for one answer, then takes the next event.
    fn told(&mut self) -> Value {
        self.woken
            .recv_timeout(Duration::from_secs(20))
            .expect("a worker to answer");
        serde_json::from_str(&self.session.take_event()).unwrap()
    }

    fn sign_up(&mut self, name: &str) -> Value {
        self.send(
            json!({ "cmd": "register", "username": name, "password": PASSWORD, "keep": true }),
        );
        let told = self.told();
        assert_eq!(told["kind"], json!("registered"), "{told}");
        told
    }

    fn sign_out(&mut self) {
        let id = self.view("frame")["account"]["id"].as_i64();
        let answer = self.send(json!({ "cmd": "logout", "account_id": id }));
        if answer["finished"].is_null() {
            assert_eq!(self.told()["kind"], json!("signed_out"));
        }
    }
}

#[test]
fn signing_up_signs_in_and_hands_out_the_recovery_codes() {
    let mut rig = rig("account-register");
    let started = rig
        .send(json!({ "cmd": "register", "username": "ana", "password": PASSWORD, "keep": true }));
    assert_eq!(
        started,
        json!({ "ok": true, "ticket": 1, "said": "Creating account…" })
    );
    assert_eq!(rig.view("status")["busy"], json!(true));
    assert_eq!(rig.view("status")["message"], json!("Creating account…"));
    let told = rig.told();
    assert_eq!(told["kind"], json!("registered"));
    assert_eq!(told["account"]["username"], json!("ana"));
    assert_eq!(told["codes"].as_array().unwrap().len(), RECOVERY_CODE_COUNT);
    assert_eq!(rig.view("frame")["account"], told["account"]);
    assert!(rig.view("frame")["token"].is_string(), "no session held");
    assert_eq!(
        rig.view("status"),
        json!({ "ticket": 1, "busy": false, "planning": false, "message": "Save these recovery codes before continuing." })
    );
}

#[test]
fn signing_in_signs_in_and_a_wrong_password_says_so_on_the_sign_in_card() {
    let mut rig = rig("account-login");
    let made = rig.sign_up("ana")["account"].clone();
    rig.sign_out();
    rig.send(
        json!({ "cmd": "login", "username": "ana", "password": "not-the-password", "keep": true }),
    );
    assert_eq!(rig.view("status")["message"], json!("Signing in…"));
    assert_eq!(
        rig.told(),
        json!({ "kind": "auth_failed", "idle": true, "forget": false, "message": words::SIGN_IN_WRONG })
    );
    assert_eq!(rig.view("status")["busy"], json!(false));
    assert_eq!(rig.view("status")["message"], json!(words::SIGN_IN_WRONG));
    assert_eq!(rig.view("frame")["account"], Value::Null);
    rig.send(json!({ "cmd": "login", "username": "ana", "password": PASSWORD, "keep": true }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "signed_in", "how": "login", "account": made })
    );
    assert_eq!(rig.view("frame")["account"], made);
    assert_eq!(rig.view("status")["busy"], json!(false));
}

/// The window moved on (a newer request) before the sign-in's answer came: it changes nothing at all.
#[test]
fn a_sign_in_the_window_moved_on_from_changes_nothing() {
    let mut rig = rig("account-stale");
    rig.sign_up("ana");
    rig.sign_out();
    for wrong in [false, true] {
        let password = if wrong { "not-the-password" } else { PASSWORD };
        rig.send(json!({ "cmd": "login", "username": "ana", "password": password, "keep": true }));
        rig.send(json!({ "cmd": "begin" }));
        rig.send(json!({ "cmd": "say", "text": "Loading…" }));
        rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
        assert_eq!(rig.session.take_event(), "null");
        assert_eq!(rig.view("frame")["account"], Value::Null, "wrong: {wrong}");
        // Not even the session a right password started: an account-less request would act as it.
        assert_eq!(rig.view("frame")["token"], Value::Null, "wrong: {wrong}");
        assert_eq!(rig.view("status")["busy"], json!(true));
        assert_eq!(rig.view("status")["message"], json!("Loading…"));
    }
}

#[test]
fn a_kept_session_that_works_signs_in_and_one_that_does_not_is_forgotten() {
    let mut rig = rig("account-resume");
    let made = rig.sign_up("ana")["account"].clone();
    let token = rig.view("frame")["token"].clone();
    rig.send(json!({ "cmd": "reset" }));
    rig.send(json!({ "cmd": "resume", "token": token }));
    assert_eq!(rig.view("status")["message"], json!("Signing in…"));
    assert_eq!(
        rig.view("frame")["token"],
        token,
        "the kept session was not taken up"
    );
    assert_eq!(
        rig.told(),
        json!({ "kind": "signed_in", "how": "resume", "account": made })
    );
    rig.send(json!({ "cmd": "reset" }));
    rig.send(json!({ "cmd": "resume", "token": "no-such-session" }));
    let told = rig.told();
    assert_eq!(told["kind"], json!("auth_failed"));
    assert_eq!(told["forget"], json!(true), "{told}");
    assert_eq!(told["idle"], json!(true));
    assert_eq!(
        rig.view("frame")["token"],
        Value::Null,
        "the dead session was kept"
    );
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("status")["message"], told["message"]);
    let refused = rig.send(json!({ "cmd": "resume", "token": "" }));
    assert_eq!(refused["ok"], json!(false));
}

#[test]
fn signing_out_ends_the_session_and_with_none_finishes_at_once() {
    let mut rig = rig("account-logout");
    let made = rig.sign_up("ana")["account"].clone();
    let answer = rig.send(json!({ "cmd": "logout", "account_id": made["id"] }));
    assert_eq!(answer["finished"], Value::Null);
    assert_eq!(rig.view("status")["message"], json!("Signing out…"));
    assert_eq!(
        rig.told(),
        json!({ "kind": "signed_out", "account_id": made["id"] })
    );
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("frame")["token"], Value::Null);
    assert_eq!(
        (
            rig.view("status")["busy"].clone(),
            rig.view("status")["message"].clone()
        ),
        (json!(false), json!("Signed out."))
    );
    // Nobody signed in: nothing to ask the service, finished in the answer itself.
    let answer = rig.send(json!({ "cmd": "logout", "account_id": null }));
    assert_eq!(
        answer["finished"],
        json!({ "kind": "signed_out", "account_id": null })
    );
    assert_eq!(rig.view("frame")["waiting"], json!(0));
}

/// No answer within the limit: the sign-in card says FlexWeek stopped responding, and the late answer
/// changes nothing.
#[test]
fn a_sign_in_past_its_limit_says_flexweek_stopped_responding() {
    let mut rig = rig("account-limit");
    rig.sign_up("ana");
    rig.sign_out();
    let (open, gate) = channel();
    *rig.host.gate.lock().unwrap() = Some(gate);
    rig.send(json!({ "cmd": "login", "username": "ana", "password": PASSWORD, "keep": true }));
    rig.host
        .steady
        .fetch_add(REQUEST_LIMIT_MS, Ordering::SeqCst);
    let told: Value = serde_json::from_str(&rig.session.take_event()).unwrap();
    assert_eq!(
        told,
        json!({
            "kind": "auth_failed", "idle": true, "forget": false,
            "message": "FlexWeek stopped responding. Close FlexWeek, open it again, then sign in."
        })
    );
    open.send(()).unwrap();
    rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    assert_eq!(rig.session.take_event(), "null");
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("frame")["token"], Value::Null);
}

#[test]
fn the_sign_in_card_words_say_what_to_do_not_that_changes_were_lost() {
    for (creating, then) in [(false, "sign in"), (true, "create your account")] {
        assert_eq!(
            auth_words(0, "ignored", creating),
            format!("FlexWeek stopped responding. Close FlexWeek, open it again, then {then}.")
        );
        assert_eq!(
            auth_words(503, "ignored", creating),
            format!("FlexWeek can't open its saved data right now. Wait a minute, then {then}.")
        );
        assert_eq!(
            auth_words(401, words::SIGN_IN_WRONG, creating),
            words::SIGN_IN_WRONG
        );
    }
}

/// A new password: signed in again with a new session (a new epoch), the old one no longer works; a wrong current
/// password says the service's words and changes nothing.
#[test]
fn changing_the_password_starts_a_new_session_and_a_wrong_one_changes_nothing() {
    let mut rig = rig("account-password");
    let made = rig.sign_up("ana")["account"].clone();
    let (old_token, old_epoch) = (
        rig.view("frame")["token"].clone(),
        rig.view("frame")["epoch"].clone(),
    );
    rig.send(json!({ "cmd": "change_password", "current_password": "not-the-password", "new_password": "another-long-password" }));
    assert_eq!(rig.view("status")["message"], json!("Changing password…"));
    let told = rig.told();
    assert_eq!(told["kind"], json!("auth_failed"));
    assert_eq!(told["message"], json!(words::WRONG_PASSWORD));
    assert_eq!(rig.view("frame")["token"], old_token);
    rig.send(json!({ "cmd": "change_password", "current_password": PASSWORD, "new_password": "another-long-password" }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "password_replaced", "account": made })
    );
    let frame = rig.view("frame");
    assert!(frame["token"].is_string());
    assert_ne!(frame["token"], old_token, "the old session was kept");
    assert!(frame["epoch"].as_u64() > old_epoch.as_u64(), "no new epoch");
    assert_eq!(
        (
            rig.view("status")["busy"].clone(),
            rig.view("status")["message"].clone()
        ),
        (json!(false), json!("Password replaced."))
    );
}

#[test]
fn replacing_the_recovery_codes_hands_out_new_ones() {
    let mut rig = rig("account-codes");
    let first = rig.sign_up("ana")["codes"].clone();
    rig.send(json!({ "cmd": "replace_recovery_codes", "password": PASSWORD }));
    assert_eq!(
        rig.view("status")["message"],
        json!("Replacing recovery codes…")
    );
    let told = rig.told();
    assert_eq!(told["kind"], json!("codes_replaced"));
    assert_eq!(told["codes"].as_array().unwrap().len(), RECOVERY_CODE_COUNT);
    assert_ne!(told["codes"], first);
    assert_eq!(told["remaining"], json!(RECOVERY_CODE_COUNT));
    assert_eq!(
        rig.view("status")["message"],
        json!("Save these replacement recovery codes.")
    );
    rig.send(json!({ "cmd": "replace_recovery_codes", "password": "not-the-password" }));
    assert_eq!(rig.told()["message"], json!(words::WRONG_PASSWORD));
}

#[test]
fn deleting_the_account_signs_out_and_a_wrong_password_keeps_it() {
    let mut rig = rig("account-delete");
    let made = rig.sign_up("ana")["account"].clone();
    let owner = made["id"].to_string();
    rig.send(json!({ "cmd": "delete_account", "password": "not-the-password", "owner": owner }));
    assert_eq!(rig.told()["message"], json!(words::WRONG_PASSWORD));
    assert_eq!(rig.view("frame")["account"], made);
    rig.send(json!({ "cmd": "delete_account", "password": PASSWORD, "owner": owner }));
    assert_eq!(rig.view("status")["message"], json!("Deleting account…"));
    assert_eq!(
        rig.told(),
        json!({ "kind": "account_deleted", "owner": owner })
    );
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("frame")["token"], Value::Null);
    assert_eq!(
        (
            rig.view("status")["busy"].clone(),
            rig.view("status")["message"].clone()
        ),
        (json!(false), json!("Account deleted."))
    );
    // The account is gone: signing in with it fails.
    rig.send(json!({ "cmd": "login", "username": "ana", "password": PASSWORD, "keep": true }));
    assert_eq!(rig.told()["message"], json!(words::SIGN_IN_WRONG));
}

/// The words when no answer comes, as the old client gave them: the sign-in card's for signing in and up, the
/// general ones for recovering and taking up a kept session.
const NO_ANSWER: &str = "FlexWeek didn't answer. Your changes may not have been saved. Try again.";

#[test]
fn recovering_with_a_code_signs_in_and_a_wrong_code_says_so() {
    let mut rig = rig("account-recover");
    let made = rig.sign_up("ana");
    let code = made["codes"][0].clone();
    rig.sign_out();
    rig.send(json!({ "cmd": "recover", "username": "ana", "code": "WRONG-CODE", "password": "a-new-long-password", "keep": true }));
    assert_eq!(rig.view("status")["message"], json!("Recovering account…"));
    assert_eq!(
        rig.told(),
        json!({ "kind": "auth_failed", "idle": true, "forget": false, "message": words::WRONG_RECOVERY_CODE })
    );
    rig.send(json!({ "cmd": "recover", "username": "ana", "code": code, "password": "a-new-long-password", "keep": true }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "signed_in", "how": "recover", "account": made["account"] })
    );
    assert!(
        rig.view("frame")["token"].is_string(),
        "no session after recovering"
    );
    rig.sign_out();
    let open = rig.hold_past_the_limit();
    rig.send(json!({ "cmd": "recover", "username": "ana", "code": made["codes"][1], "password": "a-third-long-password", "keep": true }));
    assert_eq!(rig.timed_out()["message"], json!(NO_ANSWER));
    open.send(()).unwrap();
}

#[test]
fn a_failed_sign_up_says_why_on_the_sign_up_card() {
    let mut rig = rig("account-register-fails");
    rig.sign_up("ana");
    rig.sign_out();
    rig.send(json!({ "cmd": "register", "username": "ana", "password": PASSWORD, "keep": true }));
    assert_eq!(rig.told()["message"], json!(words::USERNAME_TAKEN));
    assert_eq!(rig.view("frame")["account"], Value::Null);
    let open = rig.hold_past_the_limit();
    rig.send(json!({ "cmd": "register", "username": "bea", "password": PASSWORD, "keep": true }));
    assert_eq!(
        rig.timed_out()["message"],
        json!(
            "FlexWeek stopped responding. Close FlexWeek, open it again, then create your account."
        )
    );
    open.send(()).unwrap();
}

/// Signed out here even when the service could not end the session (it had already ended elsewhere): no
/// account, no session, and no "your session ended" after it.
#[test]
fn a_sign_out_the_service_refuses_still_signs_out() {
    let mut rig = rig("account-logout-refused");
    let made = rig.sign_up("ana")["account"].clone();
    let token = rig.view("frame")["token"].clone();
    // Another window on the same account signs that session out first.
    let mut other = rig_on(&rig);
    other.send(json!({ "cmd": "adopt_session", "token": token }));
    other.send(json!({ "cmd": "set_account", "id": made["id"], "username": "ana" }));
    other.send(json!({ "cmd": "logout", "account_id": made["id"] }));
    assert_eq!(other.told()["kind"], json!("signed_out"));
    rig.send(json!({ "cmd": "logout", "account_id": made["id"] }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "signed_out", "account_id": made["id"] })
    );
    assert_eq!(
        rig.session.take_event(),
        "null",
        "an ended session was told after signing out"
    );
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("frame")["token"], Value::Null);
}

/// A second session on the same database and host, for another window.
fn rig_on(first: &Rig) -> Rig {
    let (wake, woken) = channel();
    let wake = Mutex::new(wake);
    let db = TestDb::new("account-other-window");
    let session = Session::new(
        first._db.path.clone(),
        first.host.clone(),
        Arc::new(move || {
            let _ = wake.lock().unwrap().send(());
        }),
    );
    Rig {
        session,
        host: first.host.clone(),
        woken,
        _db: db,
    }
}

#[test]
fn a_kept_session_that_cannot_be_checked_is_signed_out_of_but_kept() {
    let mut rig = rig("account-resume-unanswered");
    rig.sign_up("ana");
    let token = rig.view("frame")["token"].clone();
    rig.send(json!({ "cmd": "reset" }));
    rig.send(json!({ "cmd": "resume", "token": "no-such-session" }));
    // An unknown session: the service says to sign in, which the window words as signing in again.
    assert_eq!(rig.told()["message"], json!(words::SIGN_IN_AGAIN));
    let open = rig.hold_past_the_limit();
    rig.send(json!({ "cmd": "resume", "token": token }));
    assert_eq!(
        rig.timed_out(),
        json!({ "kind": "auth_failed", "idle": true, "forget": false, "message": NO_ANSWER })
    );
    assert_eq!(rig.view("frame")["token"], Value::Null);
    open.send(()).unwrap();
}

#[test]
fn keep_signed_in_must_be_said_and_either_choice_signs_in() {
    let mut rig = rig("account-keep");
    rig.sign_up("ana");
    rig.sign_out();
    for keep in [json!(null), json!(1), json!("false")] {
        let refused = rig
            .send(json!({ "cmd": "login", "username": "ana", "password": PASSWORD, "keep": keep }));
        assert_eq!(
            refused,
            json!({ "ok": false, "error": "keep is true or false" }),
            "{keep}"
        );
    }
    assert_eq!(
        rig.view("status")["busy"],
        json!(false),
        "a refused sign-in started"
    );
    rig.send(json!({ "cmd": "login", "username": "ana", "password": PASSWORD, "keep": false }));
    assert_eq!(rig.told()["kind"], json!("signed_in"));
    assert!(rig.view("frame")["token"].is_string());
}

const NEW_PASSWORD: &str = "another-long-password";

/// A wrong password on each of the account's own changes: the service's words, nothing forgotten, not busy,
/// the session kept, and no "your session ended" after it.
#[test]
fn a_wrong_password_on_the_accounts_own_changes_changes_nothing() {
    let mut rig = rig("account-own-wrong");
    rig.sign_up("ana");
    let token = rig.view("frame")["token"].clone();
    for command in [
        json!({ "cmd": "change_password", "current_password": "not-the-password", "new_password": NEW_PASSWORD }),
        json!({ "cmd": "replace_recovery_codes", "password": "not-the-password" }),
        json!({ "cmd": "delete_account", "password": "not-the-password", "owner": "1" }),
    ] {
        rig.send(command.clone());
        assert_eq!(
            rig.told(),
            json!({ "kind": "auth_failed", "idle": true, "forget": false, "message": words::WRONG_PASSWORD }),
            "{command}"
        );
        assert!(!rig.session.take_expiry(), "{command}");
        assert_eq!(rig.view("status")["busy"], json!(false), "{command}");
        assert_eq!(rig.view("frame")["token"], token, "{command}");
    }
}

#[test]
fn the_accounts_own_changes_with_no_answer_say_so_in_the_general_words() {
    let mut rig = rig("account-own-unanswered");
    rig.sign_up("ana");
    for command in [
        json!({ "cmd": "change_password", "current_password": PASSWORD, "new_password": NEW_PASSWORD }),
        json!({ "cmd": "replace_recovery_codes", "password": PASSWORD }),
        json!({ "cmd": "delete_account", "password": PASSWORD, "owner": "1" }),
    ] {
        let open = rig.hold_past_the_limit();
        rig.send(command.clone());
        assert_eq!(rig.timed_out()["message"], json!(NO_ANSWER), "{command}");
        // Open first: the held work waits at the gate while holding it.
        open.send(()).unwrap();
        // The late answer changes nothing it may not (each is checked in its own test); let it land.
        rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
        *rig.host.gate.lock().unwrap() = None;
        let _ = rig.session.take_event();
        if rig.view("frame")["account"].is_null() {
            break;
        }
    }
}

/// The password changed while the window had started something else: the service has already ended the old
/// session, so the new one is taken up and the account signed in again anyway (a new epoch), the window is
/// told so it keeps the new session, and nothing is left busy. The old session no longer works.
#[test]
fn a_password_change_counts_even_if_the_window_moved_on() {
    let mut rig = rig("account-password-moved-on");
    let made = rig.sign_up("ana")["account"].clone();
    let (old_token, old_epoch) = (
        rig.view("frame")["token"].clone(),
        rig.view("frame")["epoch"].clone(),
    );
    rig.send(json!({ "cmd": "change_password", "current_password": PASSWORD, "new_password": NEW_PASSWORD }));
    rig.send(json!({ "cmd": "begin" }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "password_replaced", "account": made })
    );
    let frame = rig.view("frame");
    assert!(frame["token"].is_string());
    assert_ne!(frame["token"], old_token);
    assert!(frame["epoch"].as_u64() > old_epoch.as_u64());
    assert_eq!(rig.view("status")["busy"], json!(false));
    // A wrong password while the window moved on: nothing at all.
    let token = frame["token"].clone();
    rig.send(json!({ "cmd": "change_password", "current_password": "not-the-password", "new_password": PASSWORD }));
    rig.send(json!({ "cmd": "begin" }));
    rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    assert_eq!(rig.session.take_event(), "null");
    assert_eq!(rig.view("frame")["token"], token);
    // The old session no longer works: taking it up is refused, and forgotten.
    rig.send(json!({ "cmd": "reset" }));
    rig.send(json!({ "cmd": "resume", "token": old_token }));
    let told = rig.told();
    assert_eq!(
        (told["kind"].clone(), told["forget"].clone()),
        (json!("auth_failed"), json!(true))
    );
}

/// The account deleted while the window had started something else: it is gone anyway, so the window is told
/// and signs out; a refused deletion the window moved on from changes nothing; the deleted account's session
/// no longer works.
#[test]
fn a_deleted_account_is_signed_out_of_even_if_the_window_moved_on() {
    let mut rig = rig("account-delete-moved-on");
    let made = rig.sign_up("ana")["account"].clone();
    let owner = made["id"].to_string();
    let token = rig.view("frame")["token"].clone();
    rig.send(json!({ "cmd": "delete_account", "password": "not-the-password", "owner": owner }));
    rig.send(json!({ "cmd": "begin" }));
    rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    assert_eq!(rig.session.take_event(), "null");
    assert_eq!(rig.view("frame")["account"], made);
    rig.send(json!({ "cmd": "delete_account", "password": PASSWORD, "owner": owner }));
    rig.send(json!({ "cmd": "begin" }));
    assert_eq!(
        rig.told(),
        json!({ "kind": "account_deleted", "owner": owner })
    );
    assert_eq!(rig.view("frame")["account"], Value::Null);
    assert_eq!(rig.view("frame")["token"], Value::Null);
    assert_eq!(rig.view("status")["busy"], json!(false));
    rig.send(json!({ "cmd": "resume", "token": token }));
    assert_eq!(rig.told()["forget"], json!(true));
}

/// New recovery codes the window moved on from are not shown (as before); answers to any of the account's own
/// changes sent before a sign-out are dropped.
#[test]
fn recovery_codes_the_window_moved_on_from_and_answers_from_before_a_sign_out_change_nothing() {
    let mut rig = rig("account-own-dropped");
    rig.sign_up("ana");
    rig.send(json!({ "cmd": "replace_recovery_codes", "password": PASSWORD }));
    rig.send(json!({ "cmd": "begin" }));
    rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    assert_eq!(rig.session.take_event(), "null");
    rig.send(json!({ "cmd": "set_busy", "busy": false }));
    // The service still made each change: the window only stopped listening. After the second, the new
    // password is the one that signs in.
    for (command, password) in [
        (
            json!({ "cmd": "replace_recovery_codes", "password": PASSWORD }),
            PASSWORD,
        ),
        (
            json!({ "cmd": "change_password", "current_password": PASSWORD, "new_password": NEW_PASSWORD }),
            NEW_PASSWORD,
        ),
    ] {
        rig.send(command.clone());
        let epoch = rig.view("frame")["epoch"].clone();
        rig.send(json!({ "cmd": "reset" }));
        rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
        assert_eq!(rig.session.take_event(), "null", "{command}");
        assert_eq!(rig.view("frame")["token"], Value::Null, "{command}");
        assert!(rig.view("frame")["epoch"].as_u64() > epoch.as_u64());
        assert_eq!(rig.view("frame")["account"], Value::Null, "{command}");
        rig.send(json!({ "cmd": "login", "username": "ana", "password": password, "keep": true }));
        assert_eq!(rig.told()["kind"], json!("signed_in"), "{command}");
    }
}
