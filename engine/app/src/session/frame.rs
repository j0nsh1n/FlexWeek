//! The session's frame (2.0.0 plan, P4 group 1): who is signed in, the session token, and every request the
//! window sends, answered by the service on worker threads and taken back on the window's thread. It does
//! what `desktop/native/client.py`'s `NativeClient` does today, with no window toolkit:
//!
//! - a request is numbered and sent to one of the process's workers; its answer comes back as an event
//!   when the window takes the next one (after the worker's `wake`);
//! - events are taken one at a time, so what the window does with one answer (signing out, say) counts
//!   before the next answer is read, as it did when each answer landed on its own;
//! - signing in as someone else, or out, starts a new epoch: an answer sent in an earlier one is dropped;
//! - a request with no answer after [`REQUEST_LIMIT_MS`] fails as unanswered, and its late answer is dropped;
//!   [`Frame::next_deadline`] says when the window should look next;
//! - a 401 for a signed-in account, other than a wrong password, says the session ended, unless the window
//!   signed out or in again while it handled that answer.

use std::collections::BTreeMap;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Condvar, Mutex, OnceLock};

use flexweek_service::accounts::Entropy;
use flexweek_service::desk_requests::{self, Answer, Session};
use flexweek_service::plans::Stopwatch;
use serde_json::{Value, json};

use super::words::{NOT_AN_EXPIRY, UNREADABLE, error_words};

/// How long a request may wait for its answer before it fails as unanswered.
pub const REQUEST_LIMIT_MS: i64 = 30_000;
/// Requests answered at once, by one set of workers for the whole process. Each waits on the database or
/// hashes a password, so a Plan or a sign-in does not hold up the reads behind it.
pub const WORKERS: usize = 4;
/// A larger answer is not read (the window's limit since 1.0).
pub const MAX_ANSWER_BYTES: usize = 4 * 1024 * 1024;
const METHODS: [&str; 5] = ["GET", "POST", "PUT", "DELETE", "PATCH"];

/// What the session needs from the computer it runs on (group 1's part of the platform trait). Shared with
/// the workers, so it must be safe to use from any thread. Its calls cannot fail: a host that asks
/// something else (Python) answers with a fallback rather than panicking.
pub trait Host: Send + Sync {
    /// Milliseconds on a clock that only moves forward, for the request limit (not the app's clock, which a
    /// test may hold still).
    fn steady_ms(&self) -> i64;
    /// The app's clock as a request is sent: seconds since 1970 and `YYYY-MM-DDTHH:MM`.
    fn request_clock(&self) -> (i64, String);
    /// The name a restore point made by one request would take.
    fn restore_token(&self) -> String;
    /// Fresh randomness for one request (tokens, salts, recovery codes).
    fn entropy(&self) -> Box<dyn Entropy + Send>;
    /// Starts timing a plan, for the time its answer reports.
    fn stopwatch(&self) -> Stopwatch;
}

/// Who is signed in, as the window knows them.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Identity {
    pub id: i64,
    pub username: String,
}

/// What the window learns when it takes the next event.
#[derive(Clone, Debug, PartialEq)]
pub enum Event {
    /// A request's answer: `Ok` with the body read as JSON (an empty body reads as `{}`), or the words to show.
    Answered { number: u64, outcome: Outcome },
    /// A request whose answer no longer counts (sent before a sign-in or sign-out); nothing is said.
    Dropped { number: u64 },
    /// The service said the session ended.
    Expired,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Outcome {
    Ok { status: u16, body: Value },
    Failed { status: u16, message: String },
}

impl Event {
    pub fn to_json(&self) -> Value {
        match self {
            Event::Answered {
                number,
                outcome: Outcome::Ok { status, body },
            } => {
                json!({ "kind": "answer", "number": number, "ok": true, "status": status, "body": body })
            }
            Event::Answered {
                number,
                outcome: Outcome::Failed { status, message },
            } => json!({
                "kind": "answer", "number": number, "ok": false, "status": status, "message": message
            }),
            Event::Dropped { number } => json!({ "kind": "dropped", "number": number }),
            Event::Expired => json!({ "kind": "expired" }),
        }
    }
}

/// A request waiting for its answer.
struct Waiting {
    epoch: u64,
    deadline: i64,
    /// Who was signed in when it was sent: a 401 then means the session ended.
    signed_in: bool,
    /// A session its answer starts is held for whoever sent it to accept (a sign-in the window may have moved
    /// on from), not taken up at once.
    hold_start: bool,
}

/// An answer made by a worker.
struct Landed {
    number: u64,
    answer: Answer,
}

type Job = Box<dyn FnOnce() + Send>;

/// The process's workers, started with the first frame and kept for the life of the program, as the
/// window's pool was. A frame that goes away never waits for them; only [`stop_workers`] does, at quit.
struct Pool {
    jobs: Mutex<Sender<Job>>,
    /// How many workers are running a job, and whether the app has stopped them (jobs taken after that
    /// are skipped). One lock for both, so no job starts after [`stop_workers`] has counted.
    running: Mutex<(usize, bool)>,
    finished: Condvar,
}

fn workers() -> &'static Pool {
    static POOL: OnceLock<Arc<Pool>> = OnceLock::new();
    POOL.get_or_init(|| {
        let (jobs, queue) = channel::<Job>();
        let pool = Arc::new(Pool {
            jobs: Mutex::new(jobs),
            running: Mutex::new((0, false)),
            finished: Condvar::new(),
        });
        let queue = Arc::new(Mutex::new(queue));
        for _ in 0..WORKERS {
            let queue = Arc::clone(&queue);
            let pool = Arc::clone(&pool);
            std::thread::spawn(move || {
                loop {
                    let job = match queue.lock() {
                        Ok(queue) => queue.recv(),
                        Err(_) => return,
                    };
                    let Ok(job) = job else { return };
                    {
                        let Ok(mut running) = pool.running.lock() else {
                            return;
                        };
                        if running.1 {
                            continue;
                        }
                        running.0 += 1;
                    }
                    // The work catches its own failures; this also catches one in the window's `wake`,
                    // so no worker is ever lost.
                    let _ = catch_unwind(AssertUnwindSafe(job));
                    if let Ok(mut running) = pool.running.lock() {
                        running.0 -= 1;
                    }
                    pool.finished.notify_all();
                }
            });
        }
        pool
    })
}

/// At quit: work not yet started is skipped from now on, and this waits for the work under way to finish,
/// so no answer writes after the app has let go of its files. A caller holding a lock a worker's work or
/// `wake` needs (Python's) lets go of it while this waits.
pub fn stop_workers() {
    let pool = workers();
    let Ok(mut running) = pool.running.lock() else {
        return;
    };
    running.1 = true;
    while running.0 > 0 {
        running = match pool.finished.wait(running) {
            Ok(running) => running,
            Err(_) => return,
        };
    }
}

pub struct Frame {
    database: PathBuf,
    host: Arc<dyn Host>,
    wake: Arc<dyn Fn() + Send + Sync>,
    account: Option<Identity>,
    token: String,
    epoch: u64,
    number: u64,
    waiting: BTreeMap<u64, Waiting>,
    /// Set when the frame goes: work not yet started is skipped. (Work under way finishes, and its answer
    /// goes nowhere: the frame's end of the channel is gone, so no one is woken.)
    closed: Arc<AtomicBool>,
    landed_tx: Sender<Landed>,
    landed: Receiver<Landed>,
    /// Answer each request on the window's own thread, as it is sent, instead of on a worker: for the
    /// desktop tests' light app, whose answers come on the next turn of the window's loop (`wake` is still
    /// called, from inside [`Frame::request`]).
    inline: bool,
    /// Sessions started by answers sent with [`Frame::hold_new_session`], by request number, until taken.
    held: BTreeMap<u64, String>,
    /// A 401 just handed to the window that means the session ended, with the epoch it was sent in: told
    /// next, unless the window has signed out or in since.
    expiry: Option<u64>,
}

impl Frame {
    /// The frame for the account database at `database`. `wake` is called on a worker thread whenever an
    /// answer is ready, so the window can take its events on its own thread.
    pub fn new(database: PathBuf, host: Arc<dyn Host>, wake: Arc<dyn Fn() + Send + Sync>) -> Self {
        let (landed_tx, landed) = channel();
        Self {
            database,
            host,
            wake,
            account: None,
            token: String::new(),
            epoch: 0,
            number: 0,
            waiting: BTreeMap::new(),
            closed: Arc::new(AtomicBool::new(false)),
            landed_tx,
            landed,
            inline: false,
            held: BTreeMap::new(),
            expiry: None,
        }
    }

    /// A session the answer to request `number` starts is held, not taken up: see [`Frame::take_new_session`].
    pub fn hold_new_session(&mut self, number: u64) {
        if let Some(waiting) = self.waiting.get_mut(&number) {
            waiting.hold_start = true;
        }
    }

    /// The session held from request `number`'s answer, if it started one; taken up only by
    /// [`Frame::use_session`], so one let go of here is never used.
    pub fn take_new_session(&mut self, number: u64) -> Option<String> {
        self.held.remove(&number)
    }

    /// Takes up a session a held answer started, for the account about to be signed in.
    pub fn use_session(&mut self, token: String) {
        self.token = token;
    }

    /// See the `inline` field: every request from now on is answered as it is sent.
    pub fn answer_inline(&mut self) {
        self.inline = true;
    }

    pub fn account(&self) -> Option<&Identity> {
        self.account.as_ref()
    }

    pub fn epoch(&self) -> u64 {
        self.epoch
    }

    /// The session token held, if any.
    pub fn token(&self) -> Option<&str> {
        (!self.token.is_empty()).then_some(self.token.as_str())
    }

    /// Now on the host's steady clock.
    pub fn steady_ms(&self) -> i64 {
        self.host.steady_ms()
    }

    /// Requests sent and not yet answered or timed out.
    pub fn waiting(&self) -> usize {
        self.waiting.len()
    }

    /// When, on the steady clock, the next request reaches its limit: the window looks again then, since a
    /// request that never comes back wakes no one.
    pub fn next_deadline(&self) -> Option<i64> {
        self.waiting.values().map(|waiting| waiting.deadline).min()
    }

    /// Signed in as `identity`: answers to requests sent before no longer count.
    pub fn set_account(&mut self, identity: Identity) -> Result<(), String> {
        if identity.id <= 0 || identity.username.is_empty() {
            return Err("An account needs a valid id and username.".into());
        }
        self.account = Some(identity);
        self.epoch += 1;
        Ok(())
    }

    /// Signed out: no account and no session.
    pub fn reset(&mut self) {
        self.account = None;
        self.token.clear();
        self.epoch += 1;
    }

    /// A session kept from an earlier launch; the next request says whether it still works.
    pub fn adopt_session(&mut self, token: &str) {
        self.account = None;
        self.epoch += 1;
        self.token = token.to_string();
    }

    /// Sends one request; its answer comes back as an event under the number returned. `body` is a JSON
    /// object or None. A request the window should never make is refused here, with nothing sent.
    pub fn request(
        &mut self,
        method: &str,
        path: &str,
        body: Option<&Value>,
    ) -> Result<u64, String> {
        check_path(path)?;
        let method = method.to_uppercase();
        if !METHODS.contains(&method.as_str()) {
            return Err("Unsupported API request method.".into());
        }
        let encoded = match body {
            None => String::new(),
            Some(object @ Value::Object(_)) => object.to_string(),
            Some(_) => return Err("API request bodies must be JSON objects.".into()),
        };
        let (seconds, now) = self.host.request_clock();
        let restore = self.host.restore_token();
        self.number += 1;
        let number = self.number;
        self.waiting.insert(
            number,
            Waiting {
                epoch: self.epoch,
                deadline: self.host.steady_ms() + REQUEST_LIMIT_MS,
                signed_in: self.account.is_some(),
                hold_start: false,
            },
        );
        let token = self.token.clone();
        let account = self
            .account
            .as_ref()
            .map(|identity| identity.id.to_string());
        let database = self.database.clone();
        let path = path.to_string();
        let host = Arc::clone(&self.host);
        let wake = Arc::clone(&self.wake);
        let landed = self.landed_tx.clone();
        let closed = Arc::clone(&self.closed);
        let job: Job = Box::new(move || {
            if closed.load(Ordering::SeqCst) {
                return;
            }
            // A failure inside the service is a server error to the window, as it was, and the worker lives on.
            let answer = catch_unwind(AssertUnwindSafe(|| {
                let request = desk_requests::Request {
                    method: &method,
                    path: &path,
                    body: &encoded,
                    token: &token,
                    account: account.as_deref(),
                };
                let start = || host.stopwatch();
                let clock = desk_requests::Clock {
                    seconds,
                    now: &now,
                    restore_token: &restore,
                    stopwatch: &start,
                };
                let mut entropy = host.entropy();
                desk_requests::answer(&database, &request, &clock, entropy.as_mut())
            }))
            .unwrap_or(Answer {
                status: 500,
                body: None,
                session: Session::Kept,
            });
            // The frame may be gone; then no one is left to tell.
            if landed.send(Landed { number, answer }).is_ok() {
                wake();
            }
        });
        if self.inline {
            job();
        // If no worker could take it, it fails at its limit like any unanswered request.
        } else if let Ok(jobs) = workers().jobs.lock() {
            let _ = jobs.send(job);
        }
        Ok(number)
    }

    /// The next thing that happened, or None: an answer that came in (in the order they came), a request
    /// past its limit, or an ended session. Taken one at a time, so whatever the window does with one
    /// (signing out, say) counts before the next is read.
    pub fn take_event(&mut self) -> Option<Event> {
        if self.take_expiry() {
            return Some(Event::Expired);
        }
        while let Ok(Landed { number, answer }) = self.landed.try_recv() {
            // An answer that came after its request's limit was already given up on.
            if let Some(waiting) = self.waiting.remove(&number) {
                return Some(self.finish(number, &waiting, Some(answer)));
            }
        }
        let now = self.host.steady_ms();
        let late = self
            .waiting
            .iter()
            .filter(|(_, waiting)| waiting.deadline <= now)
            .min_by_key(|(number, waiting)| (waiting.deadline, **number))
            .map(|(number, _)| *number)?;
        let waiting = self.waiting.remove(&late)?;
        Some(self.finish(late, &waiting, None))
    }

    /// Whether the answer just taken said the session ended, and the window has not signed out or in since:
    /// for a window that takes one answer per turn of its loop and hears of the end with that answer. Told
    /// once, here or as the next event.
    pub fn take_expiry(&mut self) -> bool {
        self.expiry.take().is_some_and(|epoch| epoch == self.epoch)
    }

    fn finish(&mut self, number: u64, waiting: &Waiting, answer: Option<Answer>) -> Event {
        if waiting.epoch != self.epoch {
            return Event::Dropped { number };
        }
        let reached = answer.is_some();
        let answer = answer.unwrap_or(Answer {
            status: 0,
            body: None,
            session: Session::Kept,
        });
        match &answer.session {
            Session::Started(token) if waiting.hold_start => {
                self.held.insert(number, token.clone());
            }
            Session::Started(token) => self.token = token.clone(),
            Session::Ended => self.token.clear(),
            Session::Kept => {}
        }
        let (outcome, expired) = read(answer.status, answer.body, reached, waiting.signed_in);
        if expired {
            self.expiry = Some(waiting.epoch);
        }
        Event::Answered { number, outcome }
    }
}

impl Drop for Frame {
    /// Work handed out and not yet started is skipped; an answer still being made goes nowhere and wakes no
    /// one. Nothing here waits for a worker.
    fn drop(&mut self) {
        self.closed.store(true, Ordering::SeqCst);
    }
}

/// What the window makes of an answer, as client.py read the text it was given: `status` (0 when none came),
/// the body (None for an empty one, which reads as `{}`; one over [`MAX_ANSWER_BYTES`] is not read), whether
/// one came, and whether someone was signed in when it was sent. Also says whether it means the session ended.
pub fn read(status: u16, body: Option<Value>, reached: bool, signed_in: bool) -> (Outcome, bool) {
    let empty = body.is_none();
    let body = match body {
        None => Some(json!({})),
        Some(body) if serialized_len(&body) > MAX_ANSWER_BYTES => None,
        Some(body) => Some(body),
    };
    if !(200..300).contains(&status) || !reached {
        let detail = body.as_ref().and_then(|body| body.get("detail"));
        let message = error_words(status, detail).to_string();
        let expired = status == 401
            && signed_in
            && !detail
                .and_then(Value::as_str)
                .is_some_and(|said| NOT_AN_EXPIRY.contains(&said));
        return (Outcome::Failed { status, message }, expired);
    }
    let outcome = match body {
        Some(body @ Value::Object(_)) if !empty || status == 204 => Outcome::Ok { status, body },
        _ => Outcome::Failed {
            status,
            message: UNREADABLE.into(),
        },
    };
    (outcome, false)
}

/// The length of a value written as JSON text, without keeping the text.
fn serialized_len(value: &Value) -> usize {
    struct Count(usize);
    impl std::io::Write for Count {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.0 += bytes.len();
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut count = Count(0);
    let _ = serde_json::to_writer(&mut count, value);
    count.0
}

/// Only a relative `/api/` path may be asked for, with nothing that could step outside it (the window's
/// rule since 1.0, `client.py` `_api_path`).
pub fn check_path(path: &str) -> Result<(), String> {
    let refused = || Err("Only relative /api/ requests are allowed.".to_string());
    if !path.starts_with("/api/") || path.contains('#') {
        return refused();
    }
    if path.chars().any(|c| (c as u32) < 33 || c as u32 == 127) {
        return refused();
    }
    let bare = path.split('?').next().unwrap_or_default();
    let decoded = percent_decoded(bare);
    if decoded.contains('\\')
        || decoded.contains("//")
        || decoded.split('/').any(|part| part == "." || part == "..")
        || !decoded.starts_with("/api/")
    {
        return refused();
    }
    Ok(())
}

/// `%XX` turned back into bytes and read as UTF-8 (an unreadable byte becomes U+FFFD); a `%` without two
/// hex digits stays as it is, as Python's `unquote` does.
fn percent_decoded(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut at = 0;
    while at < bytes.len() {
        if bytes[at] == b'%' && at + 2 < bytes.len() {
            let (high, low) = (hex_value(bytes[at + 1]), hex_value(bytes[at + 2]));
            if let (Some(high), Some(low)) = (high, low) {
                out.push(high * 16 + low);
                at += 3;
                continue;
            }
        }
        out.push(bytes[at]);
        at += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn hex_value(byte: u8) -> Option<u8> {
    (byte as char)
        .to_digit(16)
        .and_then(|digit| u8::try_from(digit).ok())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ok(status: u16, body: Value) -> (Outcome, bool) {
        (Outcome::Ok { status, body }, false)
    }

    fn unreadable(status: u16) -> (Outcome, bool) {
        (
            Outcome::Failed {
                status,
                message: UNREADABLE.into(),
            },
            false,
        )
    }

    /// client.py read the text it was given: empty is `{}`, which only a 204 may be; a body must be an
    /// object; one over 4 MiB is not read, so an error then has no detail.
    #[test]
    fn an_answer_is_read_as_the_window_read_its_text() {
        assert_eq!(read(204, None, true, true), ok(204, json!({})));
        assert_eq!(read(200, None, true, true), unreadable(200));
        assert_eq!(read(200, Some(json!([1, 2])), true, true), unreadable(200));
        assert_eq!(read(200, Some(json!("text")), true, true), unreadable(200));
        assert_eq!(
            read(201, Some(json!({ "id": 3 })), true, true),
            ok(201, json!({ "id": 3 }))
        );
        let large = json!({ "detail": "Incorrect password", "pad": "x".repeat(MAX_ANSWER_BYTES) });
        assert_eq!(read(200, Some(large.clone()), true, true), unreadable(200));
        // Unread, the 401's detail is gone: generic words, and it counts as an ended session.
        assert_eq!(
            read(401, Some(large), true, true),
            (
                Outcome::Failed {
                    status: 401,
                    message: super::super::words::SIGN_IN_AGAIN.into()
                },
                true
            )
        );
        // `{"pad":""}` is 10 bytes: the limit itself is read, a byte more is not.
        let at_limit = json!({ "pad": "x".repeat(MAX_ANSWER_BYTES - 10) });
        assert_eq!(serialized_len(&at_limit), MAX_ANSWER_BYTES);
        assert!(matches!(
            read(200, Some(at_limit), true, true).0,
            Outcome::Ok { .. }
        ));
        let over = json!({ "pad": "x".repeat(MAX_ANSWER_BYTES - 9) });
        assert_eq!(read(200, Some(over), true, true), unreadable(200));
    }

    #[test]
    fn no_answer_at_all_fails_with_the_could_not_reach_words_even_on_a_200() {
        assert_eq!(
            read(200, Some(json!({})), false, true),
            (
                Outcome::Failed {
                    status: 200,
                    message: error_words(200, None).into()
                },
                false
            )
        );
        assert_eq!(
            read(0, None, false, true).0,
            Outcome::Failed {
                status: 0,
                message: error_words(0, None).into()
            }
        );
    }
}
