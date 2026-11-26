//! When the week saves itself (P4 group 2, autosave.rs): window.py's `_autosave_tick` rules, then the same
//! through the session's JSON commands on the host's steady clock.

use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};

use flexweek_app::session::Session;
use flexweek_app::session::autosave::{AFTER_MS, Autosave, RETRY_MS, Week};
use flexweek_app::session::frame::Host;
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const CHANGED: Week = Week {
    signed_in: true,
    conflict: false,
    dirty: true,
    pending: false,
};

/// The window's waits: a change saves 1.5 s after the last one; a failed save is tried again after 6 s.
#[test]
fn the_waits_are_the_windows() {
    assert_eq!((AFTER_MS, RETRY_MS), (1_500, 6_000));
}

#[test]
fn a_change_saves_once_the_student_has_stopped_changing_things() {
    let mut autosave = Autosave {
        changed_ms: 10_000,
        last_try_ms: 0,
    };
    assert!(!autosave.due(CHANGED, false, 10_000 + AFTER_MS - 1));
    assert!(autosave.due(CHANGED, false, 10_000 + AFTER_MS));
    assert_eq!(
        autosave.last_try_ms,
        10_000 + AFTER_MS,
        "the try was not counted"
    );
    let clean = Week {
        dirty: false,
        ..CHANGED
    };
    assert!(
        !autosave.due(clean, false, 99_000),
        "saved with nothing changed"
    );
}

#[test]
fn nothing_saves_signed_out_while_a_request_is_in_flight_or_after_a_conflict() {
    let mut autosave = Autosave::default();
    let late = 1_000_000;
    assert!(!autosave.due(
        Week {
            signed_in: false,
            ..CHANGED
        },
        false,
        late
    ));
    assert!(!autosave.due(CHANGED, true, late));
    assert!(!autosave.due(
        Week {
            conflict: true,
            ..CHANGED
        },
        false,
        late
    ));
    let failed = Week {
        pending: true,
        ..CHANGED
    };
    assert!(!autosave.due(
        Week {
            conflict: true,
            ..failed
        },
        false,
        late
    ));
    assert!(!autosave.due(failed, true, late));
    assert_eq!(autosave.last_try_ms, 0);
}

/// A failed save is tried again every 6 seconds from its last try, whatever has changed since, and only then.
#[test]
fn a_failed_save_is_tried_again_after_the_retry_wait() {
    let mut autosave = Autosave {
        changed_ms: 0,
        last_try_ms: 50_000,
    };
    let failed = Week {
        pending: true,
        ..CHANGED
    };
    assert!(!autosave.due(failed, false, 50_000 + RETRY_MS - 1));
    assert!(autosave.due(failed, false, 50_000 + RETRY_MS));
    assert!(
        !autosave.due(failed, false, 50_000 + RETRY_MS + 1),
        "tried twice in a row"
    );
    // Not dirty any more, still waiting to be tried: the retry is what counts.
    let quiet = Week {
        dirty: false,
        ..failed
    };
    assert!(autosave.due(quiet, false, 50_000 + 2 * RETRY_MS));
}

struct Steady(AtomicI64);

impl Host for Steady {
    fn steady_ms(&self) -> i64 {
        self.0.load(Ordering::SeqCst)
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

fn edit(session: &mut Session, fields: Value) {
    let answer = send(session, json!({ "cmd": "drafts_set", "fields": fields }));
    assert_eq!(answer["ok"], true, "{answer}");
}

#[test]
fn the_session_uses_its_draft_and_steady_clock_for_debounce_and_retry() {
    let db = TestDb::new("autosave-json");
    let clock = Arc::new(Steady(AtomicI64::new(20_000)));
    let mut session = Session::new(db.path.clone(), clock.clone(), Arc::new(|| {}));
    let tick = json!({ "cmd": "drafts_autosave", "signed_in": true });
    assert_eq!(send(&mut session, tick.clone())["save"], false);
    edit(&mut session, json!({ "dirty": true }));
    send(&mut session, json!({ "cmd": "autosave_changed" }));
    clock.0.store(20_000 + AFTER_MS - 1, Ordering::SeqCst);
    assert_eq!(send(&mut session, tick.clone())["save"], false);
    clock.0.store(20_000 + AFTER_MS, Ordering::SeqCst);
    assert_eq!(send(&mut session, tick.clone())["save"], true);
    // Busy (a request in flight): no save.
    send(
        &mut session,
        json!({ "cmd": "autosave_times", "changed_ms": 0 }),
    );
    send(&mut session, json!({ "cmd": "begin" }));
    assert_eq!(send(&mut session, tick.clone())["save"], false);
    send(&mut session, json!({ "cmd": "set_busy", "busy": false }));
    // A failure starts the retry wait from when it failed (later than the timer's last try).
    let failed_at = 30_000;
    clock.0.store(failed_at, Ordering::SeqCst);
    send(&mut session, json!({ "cmd": "autosave_failed" }));
    let view: Value = serde_json::from_str(&session.view("autosave")).unwrap();
    assert_eq!(
        view,
        json!({ "changed_ms": 0, "last_try_ms": failed_at, "after_ms": AFTER_MS, "retry_ms": RETRY_MS })
    );
    edit(
        &mut session,
        json!({ "dirty": false, "pending_save": { "operation_id": "failed" } }),
    );
    clock.0.store(failed_at + RETRY_MS - 1, Ordering::SeqCst);
    assert_eq!(send(&mut session, tick.clone())["save"], false);
    clock.0.store(failed_at + RETRY_MS, Ordering::SeqCst);
    assert_eq!(send(&mut session, tick)["save"], true);
    // A refused pair of times changes neither.
    send(
        &mut session,
        json!({ "cmd": "autosave_times", "changed_ms": 123, "last_try_ms": "bad" }),
    );
    let view: Value = serde_json::from_str(&session.view("autosave")).unwrap();
    assert_eq!(view["changed_ms"], json!(0));
    for (command, error) in [
        (
            json!({ "cmd": "drafts_autosave" }),
            "signed_in is true or false",
        ),
        (
            json!({ "cmd": "autosave_times", "changed_ms": "1" }),
            "changed_ms is a whole number",
        ),
        (
            json!({ "cmd": "begin", "planning": 1 }),
            "planning is true or false",
        ),
    ] {
        assert_eq!(
            send(&mut session, command.clone()),
            json!({ "ok": false, "error": error }),
            "{command}"
        );
    }
}

/// Host whose steady clock counts how often it is read.
struct Counted(AtomicI64);

impl Host for Counted {
    fn steady_ms(&self) -> i64 {
        self.0.fetch_add(1, Ordering::SeqCst)
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

/// Signed out, busy or after a 409, the tick does not even look at the clock, as the window did not.
#[test]
fn a_tick_that_cannot_save_does_not_read_the_clock() {
    let db = TestDb::new("autosave-clock");
    let clock = Arc::new(Counted(AtomicI64::new(0)));
    let mut session = Session::new(db.path.clone(), clock.clone(), Arc::new(|| {}));
    let tick = json!({ "cmd": "drafts_autosave", "signed_in": true });
    edit(&mut session, json!({ "dirty": true }));
    assert_eq!(
        send(
            &mut session,
            json!({ "cmd": "drafts_autosave", "signed_in": false })
        )["save"],
        false
    );

    edit(
        &mut session,
        json!({ "conflict": true, "pending_save": { "operation_id": "conflicted" } }),
    );
    assert_eq!(send(&mut session, tick.clone())["save"], false);

    edit(&mut session, json!({ "conflict": false }));
    send(&mut session, json!({ "cmd": "begin" }));
    assert_eq!(send(&mut session, tick)["save"], false);
    assert_eq!(clock.0.load(Ordering::SeqCst), 0, "the clock was read");
}
