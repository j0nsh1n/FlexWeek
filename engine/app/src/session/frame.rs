//! The session's frame (2.0.0 plan, P4 group 1): who is signed in, the session token, and every request the
//! window sends, answered by the service on worker threads and taken back on the window's thread. It does
//! what `desktop/native/client.py`'s `NativeClient` does today, with no window toolkit:
//!
//! - a request is numbered, sent to a worker, and its answer comes back as an event when the window takes
//!   its events (after the worker's `wake`);
//! - signing in as someone else, or out, starts a new epoch: an answer sent in an earlier one is dropped;
//! - a request with no answer after [`REQUEST_LIMIT_MS`] fails as unanswered, and its late answer is dropped;
//! - a 401 for a signed-in account, other than a wrong password, says the session ended.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use flexweek_service::accounts::Entropy;
use flexweek_service::desk_requests::{self, Answer, Session};
use flexweek_service::plans::Stopwatch;
use serde_json::{Value, json};

use super::words::{NOT_AN_EXPIRY, UNREADABLE, error_words};

/// How long a request may wait for its answer before it fails as unanswered.
pub const REQUEST_LIMIT_MS: i64 = 30_000;
/// Requests answered at once. Each waits on the database or hashes a password, so a Plan or a sign-in does
/// not hold up the reads behind it.
pub const WORKERS: usize = 4;
/// A larger answer is not read (the window's limit since 1.0).
pub const MAX_ANSWER_BYTES: usize = 4 * 1024 * 1024;
const METHODS: [&str; 5] = ["GET", "POST", "PUT", "DELETE", "PATCH"];

/// What the session needs from the computer it runs on (group 1's part of the platform trait). Shared with
/// the workers, so it must be safe to use from any thread.
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

/// What the window learns when it takes its events.
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
}

/// An answer made by a worker.
struct Landed {
    number: u64,
    answer: Answer,
}

type Job = Box<dyn FnOnce() + Send>;

pub struct Frame {
    database: PathBuf,
    host: Arc<dyn Host>,
    wake: Arc<dyn Fn() + Send + Sync>,
    account: Option<Identity>,
    token: String,
    epoch: u64,
    number: u64,
    waiting: BTreeMap<u64, Waiting>,
    jobs: Option<Sender<Job>>,
    workers: Vec<JoinHandle<()>>,
    landed_tx: Sender<Landed>,
    landed: Receiver<Landed>,
}

impl Frame {
    /// The frame for the account database at `database`. `wake` is called on a worker thread whenever an
    /// answer is ready, so the window can take its events on its own thread.
    pub fn new(database: PathBuf, host: Arc<dyn Host>, wake: Arc<dyn Fn() + Send + Sync>) -> Self {
        let (jobs, queue) = channel::<Job>();
        let queue = Arc::new(Mutex::new(queue));
        let workers = (0..WORKERS)
            .map(|_| {
                let queue = Arc::clone(&queue);
                std::thread::spawn(move || {
                    loop {
                        let job = match queue.lock() {
                            Ok(queue) => queue.recv(),
                            Err(_) => return,
                        };
                        match job {
                            Ok(job) => job(),
                            Err(_) => return,
                        }
                    }
                })
            })
            .collect();
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
            jobs: Some(jobs),
            workers,
            landed_tx,
            landed,
        }
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

    /// Requests sent and not yet answered or timed out.
    pub fn waiting(&self) -> usize {
        self.waiting.len()
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
            Some(Value::Object(_)) => body.map(Value::to_string).unwrap_or_default(),
            Some(_) => return Err("API request bodies must be JSON objects.".into()),
        };
        self.number += 1;
        let number = self.number;
        self.waiting.insert(
            number,
            Waiting {
                epoch: self.epoch,
                deadline: self.host.steady_ms() + REQUEST_LIMIT_MS,
                signed_in: self.account.is_some(),
            },
        );
        let (seconds, now) = self.host.request_clock();
        let restore = self.host.restore_token();
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
        let job: Job = Box::new(move || {
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
            let answer = desk_requests::answer(&database, &request, &clock, entropy.as_mut());
            // The frame may be gone; then no one is left to tell.
            if landed.send(Landed { number, answer }).is_ok() {
                wake();
            }
        });
        if let Some(jobs) = &self.jobs {
            let _ = jobs.send(job);
        }
        Ok(number)
    }

    /// The events since the last call, in the order they happened: answers that came in, requests past
    /// their limit, and an ended session.
    pub fn take_events(&mut self) -> Vec<Event> {
        let mut events = Vec::new();
        let now = self.host.steady_ms();
        let late: Vec<u64> = self
            .waiting
            .iter()
            .filter(|(_, waiting)| waiting.deadline <= now)
            .map(|(number, _)| *number)
            .collect();
        let mut finished: Vec<(u64, Waiting, Option<Answer>)> = Vec::new();
        while let Ok(Landed { number, answer }) = self.landed.try_recv() {
            // An answer that came after its request's limit was already given up on.
            if let Some(waiting) = self.waiting.remove(&number) {
                finished.push((number, waiting, Some(answer)));
            }
        }
        for number in late {
            if let Some(waiting) = self.waiting.remove(&number) {
                finished.push((number, waiting, None));
            }
        }
        finished.sort_by_key(|(number, _, _)| *number);
        for (number, waiting, answer) in finished {
            self.finish(number, &waiting, answer, &mut events);
        }
        events
    }

    fn finish(
        &mut self,
        number: u64,
        waiting: &Waiting,
        answer: Option<Answer>,
        events: &mut Vec<Event>,
    ) {
        if waiting.epoch != self.epoch {
            events.push(Event::Dropped { number });
            return;
        }
        let reached = answer.is_some();
        let answer = answer.unwrap_or(Answer {
            status: 0,
            body: None,
            session: Session::Kept,
        });
        match &answer.session {
            Session::Started(token) => self.token = token.clone(),
            Session::Ended => self.token.clear(),
            Session::Kept => {}
        }
        // Read as the window read the text: an empty body is `{}`, an over-large one is not read at all.
        let body = match &answer.body {
            None => Some(json!({})),
            Some(body) if body.to_string().len() > MAX_ANSWER_BYTES => None,
            Some(body) => Some(body.clone()),
        };
        let status = answer.status;
        if !(200..300).contains(&status) || !reached {
            let detail = body.as_ref().and_then(|body| body.get("detail"));
            let message = error_words(status, detail).to_string();
            let expired = status == 401
                && waiting.signed_in
                && !detail
                    .and_then(Value::as_str)
                    .is_some_and(|said| NOT_AN_EXPIRY.contains(&said));
            events.push(Event::Answered {
                number,
                outcome: Outcome::Failed { status, message },
            });
            if expired {
                events.push(Event::Expired);
            }
            return;
        }
        let outcome = match body {
            Some(body @ Value::Object(_)) if answer.body.is_some() || status == 204 => {
                Outcome::Ok { status, body }
            }
            _ => Outcome::Failed {
                status,
                message: UNREADABLE.into(),
            },
        };
        events.push(Event::Answered { number, outcome });
    }
}

impl Drop for Frame {
    /// Requests already handed out are still answered; their answers go nowhere.
    fn drop(&mut self) {
        self.jobs = None;
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
    }
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
