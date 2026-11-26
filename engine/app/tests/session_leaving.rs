//! Saving before leaving (P4 group 2, leaving.rs): window.py's `_save_before_leaving` poll, then the same
//! through the session's JSON commands.

use std::sync::Arc;

use flexweek_app::session::Session;
use flexweek_app::session::frame::Host;
use flexweek_app::session::leaving::{Leaving, Step, Unsaved};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const POLL: i64 = 100;
const LIMIT: i64 = 5_000;
const OPEN: Option<Unsaved<'_>> = Some(Unsaved::Open);

fn leaving() -> Leaving {
    let mut leaving = Leaving::default();
    leaving.start(LIMIT, "close FlexWeek again");
    leaving
}

#[test]
fn it_saves_the_week_on_screen_then_each_parked_week_then_leaves() {
    let mut leaving = leaving();
    let parked = Some(Unsaved::Parked("2026-11-09"));
    assert_eq!(leaving.poll(POLL, true, OPEN), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, OPEN), Step::Save);
    assert_eq!(leaving.poll(POLL, true, parked), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, parked), Step::Load("2026-11-09"));
    assert_eq!(leaving.poll(POLL, false, OPEN), Step::Save);
    assert_eq!(leaving.poll(POLL, false, None), Step::Leave);
}

#[test]
fn a_save_that_leaves_the_week_unsaved_gives_up() {
    let mut leaving = leaving();
    assert_eq!(leaving.poll(POLL, false, OPEN), Step::Save);
    assert_eq!(leaving.poll(POLL, true, OPEN), Step::Wait);
    assert_eq!(leaving.poll(POLL, false, OPEN), Step::GiveUp);
    assert_eq!(
        leaving.gave_up_words(),
        "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then close FlexWeek again."
    );
}

#[test]
fn the_wait_runs_out_after_its_limit_counted_in_polls() {
    let mut leaving = leaving();
    for _ in 0..LIMIT / POLL {
        assert_eq!(leaving.poll(POLL, true, OPEN), Step::Wait);
    }
    assert_eq!(leaving.poll(POLL, true, OPEN), Step::GiveUp);
    // Starting again starts the count again.
    leaving.start(LIMIT, "sign out again");
    assert_eq!(leaving.poll(POLL, false, None), Step::Leave);
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
fn the_session_decides_each_poll_from_its_open_draft_and_busy_state() {
    let db = TestDb::new("leaving-json");
    let mut session = Session::new(db.path.clone(), Arc::new(Still), Arc::new(|| {}));
    let start =
        json!({ "cmd": "drafts_leaving_start", "limit_ms": 300, "again": "sign out again" });
    let poll = json!({ "cmd": "drafts_leaving_poll", "poll_ms": 100 });
    send(&mut session, json!({ "cmd": "begin" }));
    assert_eq!(send(&mut session, start.clone())["waiting"], false);

    let edit = json!({ "cmd": "drafts_set", "fields": { "dirty": true } });
    assert_eq!(send(&mut session, edit)["ok"], true);
    assert_eq!(send(&mut session, start.clone())["waiting"], true);
    assert_eq!(send(&mut session, poll.clone())["step"], "wait");
    send(&mut session, json!({ "cmd": "set_busy", "busy": false }));
    assert_eq!(send(&mut session, poll.clone())["step"], "save");
    let gave_up = send(&mut session, poll.clone());
    assert_eq!(gave_up["step"], "give_up");
    assert_eq!(
        gave_up["words"],
        "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then sign out again."
    );

    assert_eq!(send(&mut session, start)["waiting"], true);
    assert_eq!(send(&mut session, poll.clone())["step"], "save");
    send(
        &mut session,
        json!({ "cmd": "drafts_set", "fields": { "dirty": false } }),
    );
    assert_eq!(send(&mut session, poll)["step"], "leave");
}

#[test]
fn the_session_times_out_on_the_first_poll_past_the_limit() {
    let db = TestDb::new("leaving-timeout");
    let mut session = Session::new(db.path.clone(), Arc::new(Still), Arc::new(|| {}));
    let edit =
        json!({ "cmd": "drafts_set", "fields": { "pending_save": { "operation_id": "failed" } } });
    assert_eq!(send(&mut session, edit)["ok"], true);
    let start =
        json!({ "cmd": "drafts_leaving_start", "limit_ms": 300, "again": "close FlexWeek again" });
    assert_eq!(send(&mut session, start)["waiting"], true);
    send(&mut session, json!({ "cmd": "begin" }));
    let poll = json!({ "cmd": "drafts_leaving_poll", "poll_ms": 100 });
    for _ in 0..3 {
        assert_eq!(send(&mut session, poll.clone())["step"], "wait");
    }
    let gave_up = send(&mut session, poll);
    assert_eq!(gave_up["step"], "give_up");
    assert_eq!(
        gave_up["words"],
        "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then close FlexWeek again."
    );
    for (command, error) in [
        (
            json!({ "cmd": "drafts_leaving_start", "again": "x" }),
            "limit_ms is a whole number",
        ),
        (
            json!({ "cmd": "drafts_leaving_poll" }),
            "poll_ms is a whole number",
        ),
    ] {
        assert_eq!(
            send(&mut session, command.clone()),
            json!({ "ok": false, "error": error }),
            "{command}"
        );
    }
}
