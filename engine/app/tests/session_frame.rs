//! The session's frame (P4 group 1): requests sent to the service on workers and their answers taken back,
//! as `desktop/native/client.py`'s `NativeClient` does them today. Expected words are the window's own
//! (client.py `_error`); the 30-second limit and the expiry rule are client.py's.

use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
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
/// 2026 19:00, counting randomness, and optionally a gate every worker waits at before it answers.
struct TestHost {
    steady: AtomicI64,
    draws: AtomicU64,
    gate: Option<Mutex<Receiver<()>>>,
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
        Box::new(Counting(self.draws.fetch_add(1000, Ordering::SeqCst)))
    }
    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

/// Dropped in this order: the gate opens first, so no worker still waits at it when the frame joins them.
struct Rig {
    release: Option<Sender<()>>,
    frame: Frame,
    host: Arc<TestHost>,
    woken: Receiver<()>,
    _db: TestDb,
}

fn rig(name: &str, gated: bool) -> Rig {
    let db = TestDb::new(name);
    let (release, gate) = channel();
    let host = Arc::new(TestHost {
        steady: AtomicI64::new(1_000),
        draws: AtomicU64::new(1),
        gate: gated.then(|| Mutex::new(gate)),
    });
    let (wake, woken) = channel();
    let wake = Mutex::new(wake);
    let frame = Frame::new(
        db.path.clone(),
        host.clone(),
        Arc::new(move || {
            let _ = wake.lock().unwrap().send(());
        }),
    );
    Rig {
        release: gated.then_some(release),
        frame,
        host,
        woken,
        _db: db,
    }
}

impl Rig {
    /// Waits for `count` answers to be made, then takes the events.
    fn answers(&mut self, count: usize) -> Vec<Event> {
        for _ in 0..count {
            self.woken
                .recv_timeout(Duration::from_secs(20))
                .expect("a worker to answer");
        }
        self.frame.take_events()
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
    let body = rig.sign_up("ana");
    assert_eq!(body["username"], json!("ana"));
    assert_eq!(
        body["recovery_codes"].as_array().map(Vec::len),
        Some(accounts::RECOVERY_CODE_COUNT)
    );
    let token = rig
        .frame
        .token()
        .expect("the session sign-up started")
        .to_string();
    // The next request carries it: the service knows who asks.
    let id = body["id"].as_i64().unwrap();
    rig.frame
        .set_account(Identity {
            id,
            username: "ana".into(),
        })
        .unwrap();
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
fn an_answer_to_a_request_sent_before_signing_out_is_dropped() {
    let mut rig = rig("frame-dropped", true);
    let number = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    rig.frame.reset();
    rig.release.as_ref().unwrap().send(()).unwrap();
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
    rig.release.as_ref().unwrap().send(()).unwrap();
    rig.answers(1);
    assert_eq!(rig.frame.token(), Some("kept-token-from-an-earlier-launch"));
}

#[test]
fn a_request_past_its_limit_fails_as_unanswered_and_its_late_answer_is_dropped() {
    let mut rig = rig("frame-limit", true);
    let number = rig.frame.request("GET", "/api/auth/me", None).unwrap();
    rig.host
        .steady
        .fetch_add(REQUEST_LIMIT_MS - 1, Ordering::SeqCst);
    assert_eq!(rig.frame.take_events(), vec![], "a millisecond early");
    rig.host.steady.fetch_add(1, Ordering::SeqCst);
    assert_eq!(
        rig.frame.take_events(),
        vec![Event::Answered {
            number,
            outcome: Outcome::Failed {
                status: 0,
                message:
                    "Could not reach FlexWeek. Your changes may not have been saved. Try again."
                        .into()
            }
        }]
    );
    rig.release.as_ref().unwrap().send(()).unwrap();
    assert_eq!(rig.answers(1), vec![], "the late answer says nothing");
}

#[test]
fn a_401_for_a_signed_in_account_says_the_session_ended_but_a_wrong_password_does_not() {
    let mut rig = rig("frame-expired", false);
    let made = rig.sign_up("ana");
    rig.frame.reset();
    // Signed out, a 401 is only a refusal.
    rig.frame.request("GET", "/api/auth/me", None).unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 1, "{events:?}");
    assert_eq!(failed(&events[0]), (401, words::SIGN_IN_AGAIN));
    // Signed in, with no session the service knows: the session ended.
    rig.frame
        .set_account(Identity {
            id: made["id"].as_i64().unwrap(),
            username: "ana".into(),
        })
        .unwrap();
    rig.frame.request("GET", "/api/auth/me", None).unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 2, "{events:?}");
    assert_eq!(failed(&events[0]).0, 401);
    assert_eq!(events[1], Event::Expired);
    // Signed in, a wrong password is a wrong answer, not an ended session.
    rig.frame
        .request(
            "POST",
            "/api/auth/login",
            Some(&json!({ "username": "ana", "password": "not-the-password!" })),
        )
        .unwrap();
    let events = rig.answers(1);
    assert_eq!(events.len(), 1, "{events:?}");
    assert_eq!(failed(&events[0]), (401, words::SIGN_IN_WRONG));
}

#[test]
fn answers_come_back_under_their_own_numbers_in_order() {
    let mut rig = rig("frame-numbers", false);
    let numbers: Vec<u64> = (0..6)
        .map(|_| rig.frame.request("GET", "/api/auth/me", None).unwrap())
        .collect();
    assert_eq!(numbers, vec![1, 2, 3, 4, 5, 6]);
    let mut answered = Vec::new();
    for _ in 0..6 {
        rig.woken.recv_timeout(Duration::from_secs(20)).unwrap();
    }
    for event in rig.frame.take_events() {
        if let Event::Answered { number, .. } = event {
            answered.push(number);
        }
    }
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
        "/api//auth",
        "/api/a\\b",
        "/api/a%5Cb",
        "/api/a#b",
        "/api/a b",
        "/api/a\u{7f}",
        "/api/%2F/me",
    ] {
        assert_eq!(
            rig.frame.request("GET", path, None),
            Err("Only relative /api/ requests are allowed.".into()),
            "{path}"
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
    // The same rules let an ordinary path through, query and escaped name included.
    for path in [
        "/api/auth/me",
        "/api/week?start=2026-11-02",
        "/api/assignments/a%20b",
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
    let host = Arc::new(TestHost {
        steady: AtomicI64::new(0),
        draws: AtomicU64::new(1),
        gate: None,
    });
    let (wake, woken) = channel();
    let wake = Mutex::new(wake);
    let mut session = Session::new(
        db.path.clone(),
        host,
        Arc::new(move || {
            let _ = wake.lock().unwrap().send(());
        }),
    );
    let sent: Value = serde_json::from_str(&session.send(
        r#"{"cmd":"request","method":"POST","path":"/api/auth/register","body":{"username":"ana","password":"a-long-test-password"}}"#,
    ))
    .unwrap();
    assert_eq!(sent, json!({ "number": 1, "ok": true }));
    let refused: Value =
        serde_json::from_str(&session.send(r#"{"cmd":"request","method":"GET","path":"/x"}"#))
            .unwrap();
    assert_eq!(
        refused,
        json!({ "ok": false, "error": "Only relative /api/ requests are allowed." })
    );
    let unknown: Value = serde_json::from_str(&session.send(r#"{"cmd":"fly"}"#)).unwrap();
    assert_eq!(unknown["ok"], json!(false));
    woken.recv_timeout(Duration::from_secs(20)).unwrap();
    let events: Value = serde_json::from_str(&session.take_events()).unwrap();
    assert_eq!(events[0]["kind"], json!("answer"));
    assert_eq!(events[0]["number"], json!(1));
    assert_eq!(events[0]["ok"], json!(true));
    assert_eq!(events[0]["status"], json!(201));
    let id = events[0]["body"]["id"].as_i64().unwrap();
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
}
