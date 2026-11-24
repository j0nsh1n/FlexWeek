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
    assert_eq!(started, json!({ "ok": true, "ticket": 1 }));
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
