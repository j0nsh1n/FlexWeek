//! The session's frame (P4 group 1): requests sent to the service on workers and their answers taken back,
//! as `desktop/native/client.py`'s `NativeClient` does them today. Expected words are the window's own
//! (client.py `_error`); the 30-second limit and the expiry rule are client.py's.

use std::sync::atomic::{AtomicBool, AtomicI64, AtomicU64, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use flexweek_app::session::frame::{Event, Frame, Host, Identity, Outcome, REQUEST_LIMIT_MS};
use flexweek_app::session::{Session, words};
use flexweek_service::accounts::{self, Entropy};
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";

/// The computer as a test sets it: a steady clock moved by hand, the app's clock at Thursday 5 November
/// 2026 19:00, counting randomness, optionally a gate every worker waits at before it answers, and
/// optionally a fault that makes the work panic.
struct TestHost {
    steady: AtomicI64,
    draws: AtomicU64,
    gate: Option<Mutex<Receiver<()>>>,
    broken: AtomicBool,
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
        if let Some(gate) = &self.gate {
            let _ = gate.lock().unwrap().recv();
        }
        if self.broken.load(Ordering::SeqCst) {
            panic!("the test host broke on purpose");
        }
        Box::new(Counting(self.draws.fetch_add(1000, Ordering::SeqCst)))
    }
    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

/// Dropped in this order: the gate opens first, so no worker still waits at it once the test is over.
struct Rig {
    release: Option<Sender<()>>,
    frame: Frame,
    host: Arc<TestHost>,
    woken: Receiver<()>,
    _db: TestDb,
}

fn host(gate: Option<Receiver<()>>) -> Arc<TestHost> {
    Arc::new(TestHost {
        steady: AtomicI64::new(1_000),
        draws: AtomicU64::new(1),
        gate: gate.map(Mutex::new),
        broken: AtomicBool::new(false),
    })
}

fn waker() -> (Arc<dyn Fn() + Send + Sync>, Receiver<()>) {
    let (wake, woken) = channel();
    let wake = Mutex::new(wake);
    (
        Arc::new(move || {
            let _ = wake.lock().unwrap().send(());
        }),
        woken,
    )
}

fn rig(name: &str, gated: bool) -> Rig {
    let db = TestDb::new(name);
    let (release, gate) = channel();
    let host = host(gated.then_some(gate));
    let (wake, woken) = waker();
    let frame = Frame::new(db.path.clone(), host.clone(), wake);
    Rig {
        release: gated.then_some(release),
        frame,
        host,
        woken,
        _db: db,
    }
}

impl Rig {
    fn open_gate(&self, times: usize) {
        for _ in 0..times {
            self.release.as_ref().unwrap().send(()).unwrap();
        }
    }

    /// Waits for `count` answers to be made, then takes every event there is, one at a time.
    fn answers(&mut self, count: usize) -> Vec<Event> {
        for _ in 0..count {
            self.woken
                .recv_timeout(Duration::from_secs(20))
                .expect("a worker to answer");
        }
        std::iter::from_fn(|| self.frame.take_event()).collect()
    }

    fn sign_up(&mut self, name: &str) -> Value {
        let number = self
            .frame
            .request(
                "POST",
                "/api/auth/register",
                Some(&json!({ "username": name, "password": PASSWORD })),
            )
            .unwrap();
        match self.answers(1).as_slice() {
            [
                Event::Answered {
                    number: answered,
                    outcome: Outcome::Ok { status: 201, body },
                },
            ] if *answered == number => body.clone(),
            other => panic!("{other:?}"),
        }
    }

    fn sign_in_as(&mut self, made: &Value) {
        self.frame
            .set_account(Identity {
                id: made["id"].as_i64().unwrap(),
                username: made["username"].as_str().unwrap().into(),
            })
            .unwrap();
    }
}

fn failed(event: &Event) -> (u16, &str) {
    match event {
        Event::Answered {
            outcome: Outcome::Failed { status, message },
            ..
        } => (*status, message.as_str()),
        other => panic!("not a failure: {other:?}"),
    }
}

#[test]
fn a_request_is_answered_by_the_service_and_a_new_session_is_held() {
    let mut rig = rig("frame-answered", false);
    assert_eq!(rig.frame.token(), None);
    let made = rig.sign_up("ana");
    assert_eq!(made["username"], json!("ana"));
    assert_eq!(
        made["recovery_codes"].as_array().map(Vec::len),
        Some(accounts::RECOVERY_CODE_COUNT)
    );
    let token = rig
        .frame
        .token()
        .expect("the session sign-up started")
        .to_string();
    // The next request carries it: the service knows who asks.
    rig.sign_in_as(&made);
    rig.frame.request("GET", "/api/auth/me", None).unwrap();
    match rig.answers(1).as_slice() {
        [
            Event::Answered {
                outcome: Outcome::Ok { status: 200, body },
                ..
            },
        ] => assert_eq!(body["username"], json!("ana")),
        other => panic!("{other:?}"),
    }
    assert_eq!(rig.frame.token(), Some(token.as_str()));
    assert_eq!(rig.frame.waiting(), 0);
}

#[test]
fn signing_out_ends_the_session_held_and_its_empty_answer_reads_as_done() {
    let mut rig = rig("frame-sign-out", false);
    let made = rig.sign_up("ana");
    rig.sign_in_as(&made);
    rig.frame.request("POST", "/api/auth/logout", None).unwrap();
    assert_eq!(
        rig.answers(1),
        vec![Event::Answered {
            number: 2,
            outcome: Outcome::Ok {
                status: 204,
                body: json!({})
            }
        }]
    );
    assert_eq!(rig.frame.token(), None);
}

#[test]
fn an_answer_to_a_request_sent_before_signing_out_is_dropped() {
    let mut rig = rig("frame-dropped", true);
    let number = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    rig.frame.reset();
    rig.open_gate(1);
    assert_eq!(rig.answers(1), vec![Event::Dropped { number }]);
    assert_eq!(rig.frame.waiting(), 0);
}

#[test]
fn a_session_started_by_an_answer_that_no_longer_counts_is_not_held() {
    let mut rig = rig("frame-dropped-token", true);
    rig.frame
        .request(
            "POST",
            "/api/auth/register",
            Some(&json!({ "username": "ana", "password": PASSWORD })),
        )
        .unwrap();
    rig.frame.adopt_session("kept-token-from-an-earlier-launch");
    rig.open_gate(1);
    rig.answers(1);
    assert_eq!(rig.frame.token(), Some("kept-token-from-an-earlier-launch"));
}

#[test]
fn what_the_window_does_with_one_answer_counts_before_the_next_is_read() {
    let mut rig = rig("frame-one-at-a-time", false);
    let first = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    let second = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    for _ in 0..2 {
        rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    }
    let taken = rig.frame.take_event().unwrap();
    assert!(matches!(taken, Event::Answered { number, .. } if number == first || number == second));
    // The window signs out on the first answer: the second, sent before, no longer counts.
    rig.frame.reset();
    assert!(matches!(
        rig.frame.take_event(),
        Some(Event::Dropped { .. })
    ));
    assert_eq!(rig.frame.take_event(), None);
}

#[test]
fn a_request_past_its_limit_fails_as_unanswered_and_its_late_answer_is_dropped() {
    let mut rig = rig("frame-limit", true);
    let number = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    assert_eq!(rig.frame.next_deadline(), Some(1_000 + REQUEST_LIMIT_MS));
    rig.host
        .steady
        .fetch_add(REQUEST_LIMIT_MS - 1, Ordering::SeqCst);
    assert_eq!(rig.frame.take_event(), None, "a millisecond early");
    rig.host.steady.fetch_add(1, Ordering::SeqCst);
    assert_eq!(
        rig.frame.take_event(),
        Some(Event::Answered {
            number,
            outcome: Outcome::Failed {
                status: 0,
                message:
                    "Could not reach FlexWeek. Your changes may not have been saved. Try again."
                        .into()
            }
        })
    );
    assert_eq!(rig.frame.next_deadline(), None);
    rig.open_gate(1);
    assert_eq!(rig.answers(1), vec![], "the late answer says nothing");
}

#[test]
fn a_late_answer_starting_a_session_after_the_limit_is_not_held() {
    let mut rig = rig("frame-limit-token", true);
    rig.frame
        .request(
            "POST",
            "/api/auth/register",
            Some(&json!({ "username": "ana", "password": PASSWORD })),
        )
        .unwrap();
    rig.host
        .steady
        .fetch_add(REQUEST_LIMIT_MS, Ordering::SeqCst);
    assert_eq!(failed(&rig.frame.take_event().unwrap()).0, 0);
    rig.open_gate(1);
    rig.answers(1);
    assert_eq!(rig.frame.token(), None);
}

#[test]
fn a_request_past_its_limit_after_signing_out_is_dropped_not_failed() {
    let mut rig = rig("frame-limit-stale", true);
    let number = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    rig.frame.reset();
    rig.host
        .steady
        .fetch_add(REQUEST_LIMIT_MS, Ordering::SeqCst);
    assert_eq!(rig.frame.take_event(), Some(Event::Dropped { number }));
}

#[test]
fn a_401_for_a_signed_in_account_says_the_session_ended_but_a_wrong_answer_does_not() {
    let mut rig = rig("frame-expired", false);
    let made = rig.sign_up("ana");
    let other = rig.sign_up("bea");
    rig.frame.reset();
    // Signed out, a 401 is only a refusal.
    rig.frame.request("GET", "/api/auth/me", None).unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 1, "{events:?}");
    assert_eq!(failed(&events[0]), (401, words::SIGN_IN_AGAIN));
    // Signed in, with no session the service knows: the session ended.
    rig.sign_in_as(&made);
    rig.frame.request("GET", "/api/auth/me", None).unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 2, "{events:?}");
    assert_eq!(failed(&events[0]).0, 401);
    assert_eq!(events[1], Event::Expired);
    // Signed in, a wrong password or recovery code is a wrong answer, not an ended session.
    let wrong = [
        (
            "/api/auth/login",
            json!({ "username": "ana", "password": "not-the-password!" }),
            words::SIGN_IN_WRONG,
        ),
        (
            "/api/auth/recover",
            json!({
                "username": "ana",
                "code": other["recovery_codes"][0],
                "password": "a-new-long-password"
            }),
            words::WRONG_RECOVERY_CODE,
        ),
    ];
    for (path, body, said) in wrong {
        rig.frame.request("POST", path, Some(&body)).unwrap();
        let events = rig.answers(1);
        assert_eq!(events.len(), 1, "{path}: {events:?}");
        assert_eq!(failed(&events[0]), (401, said), "{path}");
    }
    // "Incorrect password" needs a session: changing the password with the wrong current one.
    rig.frame
        .request(
            "POST",
            "/api/auth/login",
            Some(&json!({ "username": "ana", "password": PASSWORD })),
        )
        .unwrap();
    rig.answers(1);
    rig.frame
        .request(
            "POST",
            "/api/auth/password",
            Some(&json!({
                "current_password": "not-the-password!",
                "new_password": "a-new-long-password"
            })),
        )
        .unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 1, "{events:?}");
    assert_eq!(failed(&events[0]), (401, words::WRONG_PASSWORD));
}

#[test]
fn a_session_end_is_not_said_when_the_window_signed_out_on_that_answer() {
    let mut rig = rig("frame-expired-handled", false);
    let made = rig.sign_up("ana");
    rig.frame.reset();
    rig.sign_in_as(&made);
    rig.frame.request("POST", "/api/auth/logout", None).unwrap();
    rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    assert_eq!(failed(&rig.frame.take_event().unwrap()).0, 401);
    // Signing out on a failed sign-out, as the window does: the ended session is already handled.
    rig.frame.reset();
    assert_eq!(rig.frame.take_event(), None);
}

#[test]
fn a_failure_inside_a_worker_is_a_server_error_and_the_workers_carry_on() {
    let mut rig = rig("frame-panic", false);
    rig.host.broken.store(true, Ordering::SeqCst);
    let broken = flexweek_app::session::frame::WORKERS + 1;
    for _ in 0..broken {
        rig.frame.request("GET", "/api/auth/me", None).unwrap();
    }
    let events = rig.answers(broken);
    assert_eq!(events.len(), broken, "{events:?}");
    for event in &events {
        assert_eq!(
            failed(event),
            (500, "FlexWeek could not complete this request. Try again.")
        );
    }
    rig.host.broken.store(false, Ordering::SeqCst);
    rig.sign_up("ana");
}

#[test]
fn a_frame_that_goes_away_wakes_no_one() {
    let db = TestDb::new("frame-gone");
    let (release, gate) = channel();
    let host = host(Some(gate));
    let (wake, woken) = waker();
    let mut frame = Frame::new(db.path.clone(), host, wake);
    frame.request("GET", "/api/auth/me", None).unwrap();
    drop(frame);
    release.send(()).unwrap();
    assert!(woken.recv_timeout(Duration::from_secs(2)).is_err());
}

/// Work the frame handed out but no worker had started is skipped once the frame goes: with every worker
/// held at a gate, the gone frame's request waits behind them, and its host is never asked for anything.
#[test]
fn work_not_started_when_the_frame_goes_is_skipped() {
    let db = TestDb::new("frame-skipped");
    let workers = flexweek_app::session::frame::WORKERS;
    let mut holding = rig("frame-skipped-holding", true);
    for _ in 0..workers {
        holding.frame.request("GET", "/api/auth/me", None).unwrap();
    }
    let gone_host = host(None);
    let (wake, _woken) = waker();
    let mut gone = Frame::new(db.path.clone(), gone_host.clone(), wake);
    gone.request("GET", "/api/auth/me", None).unwrap();
    let asked = gone_host.draws.load(Ordering::SeqCst);
    drop(gone);
    holding.open_gate(workers);
    holding.answers(workers);
    // One more request after it, so the gone frame's work has been taken from the queue by now.
    holding.frame.request("GET", "/api/auth/me", None).unwrap();
    holding.open_gate(1);
    holding.answers(1);
    assert_eq!(
        gone_host.draws.load(Ordering::SeqCst),
        asked,
        "the gone frame's work ran"
    );
}

#[test]
fn an_account_needs_an_id_and_a_name_and_signing_in_starts_a_new_epoch() {
    let mut rig = rig("frame-account", false);
    for (id, username) in [(0, "ana"), (-3, "ana"), (4, "")] {
        assert_eq!(
            rig.frame.set_account(Identity {
                id,
                username: username.into()
            }),
            Err("An account needs a valid id and username.".into())
        );
    }
    assert_eq!((rig.frame.epoch(), rig.frame.account()), (0, None));
    rig.frame
        .set_account(Identity {
            id: 4,
            username: "ana".into(),
        })
        .unwrap();
    assert_eq!(rig.frame.epoch(), 1);
    rig.frame.adopt_session("kept");
    assert_eq!(
        (rig.frame.epoch(), rig.frame.account(), rig.frame.token()),
        (2, None, Some("kept"))
    );
    rig.frame.reset();
    assert_eq!((rig.frame.epoch(), rig.frame.token()), (3, None));
}

#[test]
fn answers_come_back_under_their_own_numbers() {
    let mut rig = rig("frame-numbers", false);
    let numbers: Vec<u64> = (0..6)
        .map(|_| rig.frame.request("GET", "/api/auth/me", None).unwrap())
        .collect();
    assert_eq!(numbers, vec![1, 2, 3, 4, 5, 6]);
    let mut answered: Vec<u64> = rig
        .answers(6)
        .into_iter()
        .map(|event| match event {
            Event::Answered { number, .. } => number,
            other => panic!("{other:?}"),
        })
        .collect();
    answered.sort_unstable();
    assert_eq!(answered, numbers);
}

#[test]
fn a_request_the_window_should_never_make_is_refused_and_nothing_is_sent() {
    let mut rig = rig("frame-refused", false);
    for path in [
        "/apix",
        "api/auth/me",
        "http://example.org/api/auth/me",
        "/api/../auth",
        "/api/%2e%2e/auth",
        "/api/.",
        "/api/%2e",
        "/api//auth",
        "/api/a\\b",
        "/api/a%5Cb",
        "/api/a#b",
        "/api/a b",
        "/api/a\u{7f}",
        "/api/a\n",
        "/api/a\t",
        "/api/a\0",
        "/api/%2F/me",
    ] {
        assert_eq!(
            rig.frame.request("GET", path, None),
            Err("Only relative /api/ requests are allowed.".into()),
            "{path:?}"
        );
    }
    assert_eq!(
        rig.frame.request("TRACE", "/api/auth/me", None),
        Err("Unsupported API request method.".into())
    );
    assert_eq!(
        rig.frame
            .request("POST", "/api/auth/login", Some(&json!([1]))),
        Err("API request bodies must be JSON objects.".into())
    );
    assert_eq!(rig.frame.waiting(), 0);
    // The same rules let an ordinary path through, as Python's unquote reads it: a query is not a path,
    // and a `%` without two hex digits is only a `%`.
    for path in [
        "/api/auth/me",
        "/api/week?start=2026-11-02",
        "/api/assignments/a%20b",
        "/api/a?b=..",
        "/api/a?b=c\\d",
        "/api/%",
        "/api/%2",
        "/api/%ZZ",
        "/api/%%2e%2e",
        "/api/%FF",
    ] {
        assert!(rig.frame.request("get", path, None).is_ok(), "{path}");
    }
}

#[test]
fn the_words_for_each_failure_are_the_windows() {
    let cases: [(u16, Value, &str); 12] = [
        (
            0,
            Value::Null,
            "Could not reach FlexWeek. Your changes may not have been saved. Try again.",
        ),
        (
            401,
            json!("Incorrect password"),
            "Wrong password. Try again.",
        ),
        (
            401,
            json!("Incorrect username or password"),
            "Wrong username or password. Try again, or choose Forgot password.",
        ),
        (
            409,
            json!("Username unavailable"),
            "That username is taken. Try another.",
        ),
        (
            401,
            json!("Incorrect username or recovery code"),
            "Wrong username or recovery code. Each code works once; try another one.",
        ),
        (
            401,
            json!("Your session ended. Sign in again."),
            "Your session ended. Sign in again.",
        ),
        (
            401,
            json!("Please sign in"),
            "Please sign in again, or check your username and password.",
        ),
        (
            422,
            json!([{ "loc": ["body", "new_password"], "msg": "short" }]),
            "At least 12 characters.",
        ),
        (
            422,
            json!([{ "loc": ["body", "Username"] }]),
            "Use 3 to 32 letters, numbers or underscores, with no spaces.",
        ),
        (
            422,
            json!([{ "loc": ["body", "title"] }]),
            "Check the required fields, dates, times and lengths, then try again.",
        ),
        (
            503,
            Value::Null,
            "Storage is unavailable. Keep your changes and try again shortly.",
        ),
        (
            418,
            Value::Null,
            "FlexWeek could not complete this request. Try again.",
        ),
    ];
    for (status, detail, said) in cases {
        let detail = (!detail.is_null()).then_some(&detail);
        assert_eq!(
            words::error_words(status, detail),
            said,
            "{status} {detail:?}"
        );
    }
}

#[test]
fn the_session_answers_in_json_text() {
    let db = TestDb::new("frame-json");
    let (wake, woken) = waker();
    let mut session = Session::new(db.path.clone(), host(None), wake);
    let sent: Value = serde_json::from_str(&session.send(
        r#"{"cmd":"request","method":"POST","path":"/api/auth/register","body":{"username":"ana","password":"a-long-test-password"}}"#,
    ))
    .unwrap();
    assert_eq!(sent, json!({ "number": 1, "ok": true }));
    let frame: Value = serde_json::from_str(&session.view("frame")).unwrap();
    assert_eq!(frame["waiting"], json!(1));
    assert_eq!(frame["next_deadline"], json!(1_000 + REQUEST_LIMIT_MS));
    for (command, error) in [
        (
            r#"{"cmd":"request","method":"GET","path":"/x"}"#,
            "Only relative /api/ requests are allowed.",
        ),
        (r#"{"cmd":"fly"}"#, "no command called Some(\"fly\")"),
        (r#"{"cmd":"set_account","id":"4"}"#, "id is a whole number"),
    ] {
        let refused: Value = serde_json::from_str(&session.send(command)).unwrap();
        assert_eq!(refused, json!({ "ok": false, "error": error }), "{command}");
    }
    let unreadable: Value = serde_json::from_str(&session.send("{not json")).unwrap();
    assert_eq!(unreadable["ok"], json!(false));
    woken.recv_timeout(Duration::from_secs(20)).unwrap();
    let event: Value = serde_json::from_str(&session.take_event()).unwrap();
    assert_eq!(event["kind"], json!("answer"));
    assert_eq!(event["number"], json!(1));
    assert_eq!(event["ok"], json!(true));
    assert_eq!(event["status"], json!(201));
    assert_eq!(session.take_event(), "null");
    let id = event["body"]["id"].as_i64().unwrap();
    let set: Value = serde_json::from_str(
        &session.send(&json!({ "cmd": "set_account", "id": id, "username": "ana" }).to_string()),
    )
    .unwrap();
    assert_eq!(set, json!({ "ok": true }));
    let frame: Value = serde_json::from_str(&session.view("frame")).unwrap();
    assert_eq!(frame["account"], json!({ "id": id, "username": "ana" }));
    assert_eq!(frame["epoch"], json!(1));
    assert!(frame["token"].is_string());
    assert_eq!(frame["waiting"], json!(0));
    assert_eq!(frame["next_deadline"], Value::Null);
    assert_eq!(
        serde_json::from_str::<Value>(&session.send(r#"{"cmd":"adopt_session","token":"kept"}"#))
            .unwrap(),
        json!({ "ok": true })
    );
    let frame: Value = serde_json::from_str(&session.view("frame")).unwrap();
    assert_eq!(
        (&frame["account"], &frame["token"], &frame["epoch"]),
        (&Value::Null, &json!("kept"), &json!(2))
    );
    session.send(r#"{"cmd":"reset"}"#);
    let frame: Value = serde_json::from_str(&session.view("frame")).unwrap();
    assert_eq!(
        (&frame["token"], &frame["epoch"]),
        (&Value::Null, &json!(3))
    );
    let unknown: Value = serde_json::from_str(&session.view("moon")).unwrap();
    assert_eq!(unknown, json!({ "error": "no view called \"moon\"" }));
}
