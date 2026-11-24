//! Saving before leaving (P4 group 2, leaving.rs): window.py's `_save_before_leaving` poll, then the same
//! through the session's JSON commands.

use std::sync::Arc;

use flexweek_app::session::Session;
use flexweek_app::session::frame::Host;
use flexweek_app::session::leaving::{Leaving, Step};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const POLL: i64 = 100;
const LIMIT: i64 = 5_000;

fn leaving() -> Leaving {
    let mut leaving = Leaving::default();
    leaving.start(LIMIT, "close FlexWeek again");
    leaving
}

#[test]
fn it_saves_the_week_on_screen_then_each_parked_week_then_leaves() {
    let mut leaving = leaving();
    assert_eq!(leaving.poll(POLL, true, true, true), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, true, true), Step::Save);
    assert_eq!(leaving.poll(POLL, true, false, true), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, false, true), Step::Load);
    // The parked week, now on screen, is saved in its turn.
    assert_eq!(leaving.poll(POLL, false, true, false), Step::Save);
    assert_eq!(leaving.poll(POLL, false, false, false), Step::Leave);
}

#[test]
fn a_save_that_leaves_the_week_unsaved_gives_up() {
    let mut leaving = leaving();
    assert_eq!(leaving.poll(POLL, false, true, false), Step::Save);
    assert_eq!(leaving.poll(POLL, true, true, false), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, true, false), Step::GiveUp);
    assert_eq!(
        leaving.gave_up_words(),
        "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then close FlexWeek again."
    );
}

#[test]
fn the_wait_runs_out_after_its_limit_counted_in_polls() {
    let mut leaving = leaving();
    for _ in 0..LIMIT / POLL {
        assert_eq!(leaving.poll(POLL, true, true, false), Step::Wait);
    }
    assert_eq!(leaving.poll(POLL, true, true, false), Step::GiveUp);
    // Starting again starts the count again.
    leaving.start(LIMIT, "sign out again");
    assert_eq!(leaving.poll(POLL, false, false, false), Step::Leave);
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

#[test]
fn the_session_decides_each_poll_in_json_text_with_its_own_busy_state() {
    let db = TestDb::new("leaving-json");
    let mut session = Session::new(db.path.clone(), Arc::new(Still), Arc::new(|| {}));
    send(
        &mut session,
        json!({ "cmd": "leaving_start", "limit_ms": 300, "again": "sign out again" }),
    );
    let poll = json!({ "cmd": "leaving_poll", "poll_ms": 100, "held": true, "parked": false });
    send(&mut session, json!({ "cmd": "begin" }));
    assert_eq!(
        send(&mut session, poll.clone()),
        json!({ "ok": true, "step": "wait" })
    );
    send(&mut session, json!({ "cmd": "set_busy", "busy": false }));
    assert_eq!(
        send(&mut session, poll.clone()),
        json!({ "ok": true, "step": "save" })
    );
    assert_eq!(
        send(&mut session, poll.clone()),
        json!({
            "ok": true, "step": "give_up",
            "words": "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then sign out again."
        })
    );
    for (command, error) in [
        (
            json!({ "cmd": "leaving_start", "again": "x" }),
            "limit_ms is a whole number",
        ),
        (
            json!({ "cmd": "leaving_poll", "poll_ms": 100, "held": true }),
            "parked is true or false",
        ),
    ] {
        assert_eq!(
            send(&mut session, command.clone()),
            json!({ "ok": false, "error": error }),
            "{command}"
        );
    }
}
