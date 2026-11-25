//! The session's status (P4 group 1): the rules of controller.py's `_begin`, `_alive`, `_idle`, `planning`,
//! `_say` and the ended-session path (`_on_expired`), and the same through the session's JSON commands.

use std::sync::Arc;

use flexweek_app::session::frame::Host;
use flexweek_app::session::{Session, Status};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

#[test]
fn only_the_latest_request_makes_the_session_idle() {
    let mut status = Status::default();
    assert!(!status.busy());
    let first = status.begin(false);
    let second = status.begin(false);
    assert!(status.busy());
    assert!(!status.alive(first));
    // The window moved on from the first request: its answer changes nothing.
    assert!(!status.idle(first));
    assert!(status.busy());
    assert!(status.idle(second));
    assert!(!status.busy());
}

#[test]
fn planning_lasts_while_the_plan_is_the_latest_request_and_unanswered() {
    let mut status = Status::default();
    let plan = status.begin(true);
    assert!(status.planning());
    assert!(status.idle(plan));
    assert!(!status.planning(), "planning after its answer came");
    status.begin(true);
    status.begin(false);
    assert!(!status.planning(), "a later request is not a plan");
    status.begin(true);
    status.set_busy(false);
    assert!(!status.planning(), "planning while not busy");
}

#[test]
fn an_ended_session_stops_every_request_from_counting() {
    let mut status = Status::default();
    let ticket = status.begin(false);
    status.cancel();
    assert!(!status.busy());
    assert!(!status.idle(ticket));
    assert!(!status.alive(ticket));
}

struct Still;

impl Host for Still {
    fn steady_ms(&self) -> i64 {
        0
    }
    fn request_clock(&self) -> (i64, String) {
        (1_793_905_200, "2026-11-05T19:00".into())
    }
    fn restore_token(&self) -> String {
        "0000000000000001".into()
    }
    fn entropy(&self) -> Box<dyn Entropy + Send> {
        Box::new(Counting(1))
    }
    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

fn send(session: &mut Session, command: Value) -> Value {
    serde_json::from_str(&session.send(&command.to_string())).unwrap()
}

fn status(session: &Session) -> Value {
    serde_json::from_str(&session.view("status")).unwrap()
}

#[test]
fn the_status_answers_in_json_text() {
    let db = TestDb::new("status-json");
    let mut session = Session::new(db.path.clone(), Arc::new(Still), Arc::new(|| {}));
    assert_eq!(
        status(&session),
        json!({ "ticket": 0, "busy": false, "planning": false, "message": "" })
    );
    assert_eq!(
        send(&mut session, json!({ "cmd": "begin", "planning": true })),
        json!({ "ok": true, "ticket": 1 })
    );
    assert_eq!(status(&session)["planning"], json!(true));
    assert_eq!(
        send(&mut session, json!({ "cmd": "begin" })),
        json!({ "ok": true, "ticket": 2 })
    );
    assert_eq!(
        send(&mut session, json!({ "cmd": "idle", "ticket": 1 })),
        json!({ "ok": true, "idle": false })
    );
    assert_eq!(
        send(&mut session, json!({ "cmd": "idle", "ticket": 2 })),
        json!({ "ok": true, "idle": true })
    );
    send(&mut session, json!({ "cmd": "say", "text": "Signing in…" }));
    send(&mut session, json!({ "cmd": "set_busy", "busy": true }));
    assert_eq!(
        status(&session),
        json!({ "ticket": 2, "busy": true, "planning": false, "message": "Signing in…" })
    );
    send(&mut session, json!({ "cmd": "cancel" }));
    assert_eq!(
        (
            status(&session)["ticket"].clone(),
            status(&session)["busy"].clone()
        ),
        (json!(3), json!(false))
    );
    for (command, error) in [
        (
            json!({ "cmd": "idle", "ticket": "2" }),
            "ticket is a whole number",
        ),
        (
            json!({ "cmd": "set_busy", "busy": 1 }),
            "busy is true or false",
        ),
        (json!({ "cmd": "say" }), "text is text"),
    ] {
        assert_eq!(
            send(&mut session, command.clone()),
            json!({ "ok": false, "error": error }),
            "{command}"
        );
    }
}
