//! Stopping the session's workers at quit (`frame::stop_workers`): it waits for the work under way, and
//! work after it is skipped. Its own test program, since stopping the workers stops them for the process.

use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use flexweek_app::session::frame::{Frame, Host, WORKERS, stop_workers};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_testkit::{Counting, TestDb};

/// Holds every request's work at a gate, telling the test when each got there; counts every request whose
/// work ran.
struct GatedHost {
    entered: Mutex<Sender<()>>,
    gate: Mutex<Receiver<()>>,
    ran: AtomicUsize,
}

impl Host for GatedHost {
    fn steady_ms(&self) -> i64 {
        1_000
    }
    fn request_clock(&self) -> (i64, String) {
        (1_793_905_200, "2026-11-05T19:00".into())
    }
    fn restore_token(&self) -> String {
        "0000000000000001".into()
    }
    fn entropy(&self) -> Box<dyn Entropy + Send> {
        self.ran.fetch_add(1, Ordering::SeqCst);
        let _ = self.entered.lock().unwrap().send(());
        let _ = self.gate.lock().unwrap().recv();
        Box::new(Counting(1))
    }
    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

/// Every worker busy and one more request waiting in the queue when the app stops them: the stop waits for
/// the four, the waiting one never runs, and neither does one sent after the stop.
#[test]
fn stopping_waits_for_the_work_under_way_and_skips_what_has_not_started() {
    let db = TestDb::new("stop-workers");
    let (entered_tx, entered) = channel();
    let (release, gate) = channel();
    let host = Arc::new(GatedHost {
        entered: Mutex::new(entered_tx),
        gate: Mutex::new(gate),
        ran: AtomicUsize::new(0),
    });
    let (woken_tx, woken) = channel::<()>();
    let woken_tx = Mutex::new(woken_tx);
    let mut frame = Frame::new(
        db.path.clone(),
        host.clone(),
        Arc::new(move || {
            let _ = woken_tx.lock().unwrap().send(());
        }),
    );
    for _ in 0..WORKERS {
        frame.request("GET", "/api/auth/me", None).unwrap();
    }
    for _ in 0..WORKERS {
        entered
            .recv_timeout(Duration::from_secs(20))
            .expect("every worker to start its work");
    }
    // Queued behind the four.
    frame.request("GET", "/api/auth/me", None).unwrap();
    let stopped = Arc::new(AtomicBool::new(false));
    let stopping = {
        let stopped = Arc::clone(&stopped);
        std::thread::spawn(move || {
            stop_workers();
            stopped.store(true, Ordering::SeqCst);
        })
    };
    std::thread::sleep(Duration::from_millis(300));
    assert!(
        !stopped.load(Ordering::SeqCst),
        "stopping did not wait for the work under way"
    );
    // One more opening than the work under way needs, so a queued request that wrongly ran would finish too.
    for _ in 0..=WORKERS {
        release.send(()).unwrap();
    }
    stopping.join().unwrap();
    for _ in 0..WORKERS {
        woken
            .recv_timeout(Duration::from_secs(20))
            .expect("the work under way to answer");
    }
    assert_eq!(
        host.ran.load(Ordering::SeqCst),
        WORKERS,
        "the queued request ran"
    );
    // Work sent after the stop never runs either.
    frame.request("GET", "/api/auth/me", None).unwrap();
    assert!(woken.recv_timeout(Duration::from_millis(500)).is_err());
    assert_eq!(
        host.ran.load(Ordering::SeqCst),
        WORKERS,
        "work after the stop ran"
    );
}
