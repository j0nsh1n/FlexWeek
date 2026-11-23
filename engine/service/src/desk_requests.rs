//! The desktop's requests answered in this process, with no server between (2.0.0 plan, phase P2). The
//! window still asks by method and `/api/` path, so its callers keep their words and callbacks; this
//! module reads the path and the body, checks the session, calls the service, and answers with the status
//! and body the local server gave. The session token travels beside the request instead of in a cookie,
//! and an answer that starts or ends a session says so.
//!
//! Two differences from the server, on purpose: a path segment is decoded on its own, so an id holding
//! an escaped `/` is one id (the server decoded the whole path first and found no route), and the session
//! is checked before the body is read, so a malformed body from someone signed out hears "Please sign in"
//! (the window only sends JSON it wrote).

use std::path::Path;

use flexweek_engine::plan::parse_moment;
use flexweek_engine::snapshot::MAX_BODY;
use flexweek_engine::validate::yes_or_no;
use flexweek_store::StoreError;
use rusqlite::ffi;
use serde_json::{Map, Value, json};

use crate::accounts::{self, Account, Asker, Entropy, INVALID_INPUT, SignedIn};
use crate::{
    Refusal, ServiceError, ServiceResult, changes, comfort, homework_saves, plans, preferences,
    records, transfer, views, week_saves, weeks,
};

pub const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";
pub const DATE_RULE: &str = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31";
pub const MONTH_RULE: &str = "month must be YYYY-MM between 2000-01 and 2099-12";
pub const REVISION_REQUIRED: &str = "revision is required";
pub const STORAGE_UNAVAILABLE: &str =
    "Storage unavailable. Your changes were not saved; retry shortly.";
pub const TOO_LARGE: &str = "Request too large";
pub const NOT_FOUND: &str = "Not Found";
pub const NOT_ALLOWED: &str = "Method Not Allowed";
pub const SERVER_ERROR: &str = "Internal Server Error";
/// Who asks, for the sign-in limits: the desktop has always been the one local address.
pub const LOCAL_ADDRESS: &str = "127.0.0.1";

/// One request from the window.
pub struct Request<'a> {
    pub method: &'a str,
    /// `/api/...`, with its query.
    pub path: &'a str,
    /// The JSON body as sent; empty for none.
    pub body: &'a str,
    /// The session the window holds; empty for none.
    pub token: &'a str,
    /// The account the window believes is signed in, as the session check compares it.
    pub account: Option<&'a str>,
}

/// The app's clock for one request, and the name a restore point made by it would take.
pub struct Clock<'a> {
    pub seconds: i64,
    /// `YYYY-MM-DDTHH:MM`.
    pub now: &'a str,
    pub restore_token: &'a str,
    /// Starts timing a plan, for the time its answer reports.
    pub stopwatch: &'a (dyn Fn() -> plans::Stopwatch + Sync),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Session {
    Kept,
    Started(String),
    Ended,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Answer {
    pub status: u16,
    /// None for an answer with no body (204).
    pub body: Option<Value>,
    pub session: Session,
}

impl Answer {
    fn ok(body: Value) -> Self {
        Self {
            status: 200,
            body: Some(body),
            session: Session::Kept,
        }
    }

    fn refused(status: u16, words: &str) -> Self {
        Self {
            status,
            body: Some(json!({ "detail": words })),
            session: Session::Kept,
        }
    }
}

fn status_of(refusal: &Refusal) -> u16 {
    match refusal {
        Refusal::Invalid(_) => 422,
        Refusal::Unauthorized(_) => 401,
        Refusal::NotFound(_) => 404,
        Refusal::Conflict(_) => 409,
        Refusal::TooMany(_) => 429,
        Refusal::TooLarge(_) => 413,
    }
}

/// Storage the app cannot reach right now (busy, locked, full, unreadable), as the server answered
/// Python's `sqlite3.OperationalError`: the student keeps their changes and tries again.
fn unavailable(error: &StoreError) -> bool {
    let code = match error {
        StoreError::Sqlite(rusqlite::Error::SqliteFailure(sqlite, _)) => sqlite.extended_code,
        StoreError::Sqlite(rusqlite::Error::SqlInputError { error, .. }) => error.extended_code,
        _ => return false,
    };
    matches!(
        code & 0xff,
        ffi::SQLITE_ERROR
            | ffi::SQLITE_PERM
            | ffi::SQLITE_ABORT
            | ffi::SQLITE_BUSY
            | ffi::SQLITE_LOCKED
            | ffi::SQLITE_READONLY
            | ffi::SQLITE_INTERRUPT
            | ffi::SQLITE_IOERR
            | ffi::SQLITE_FULL
            | ffi::SQLITE_CANTOPEN
            | ffi::SQLITE_PROTOCOL
            | ffi::SQLITE_EMPTY
            | ffi::SQLITE_SCHEMA
    )
}

fn failed(error: ServiceError) -> Answer {
    match error {
        ServiceError::Refused(refusal) => Answer::refused(status_of(&refusal), refusal.words()),
        ServiceError::Store(store) if unavailable(&store) => {
            Answer::refused(503, STORAGE_UNAVAILABLE)
        }
        ServiceError::Store(_) | ServiceError::Broken(_) => Answer::refused(500, SERVER_ERROR),
    }
}

fn invalid(words: &str) -> ServiceError {
    Refusal::Invalid(words.to_string()).into()
}

/// `%XX` decoded (two hex digits, or the `%` stays as written), `+` a space only in a query, and bytes
/// that are not UTF-8 read as U+FFFD: as Python's `unquote` and `unquote_plus` read them.
fn decoded(raw: &str, query: bool) -> String {
    let bytes = raw.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut at = 0;
    while at < bytes.len() {
        match bytes[at] {
            b'%' => {
                let pair = bytes
                    .get(at + 1..at + 3)
                    .filter(|hex| hex.iter().all(u8::is_ascii_hexdigit))
                    .and_then(|hex| std::str::from_utf8(hex).ok())
                    .and_then(|hex| u8::from_str_radix(hex, 16).ok());
                match pair {
                    Some(byte) => {
                        out.push(byte);
                        at += 3;
                    }
                    None => {
                        out.push(b'%');
                        at += 1;
                    }
                }
            }
            b'+' if query => {
                out.push(b' ');
                at += 1;
            }
            byte => {
                out.push(byte);
                at += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

struct Query(Vec<(String, String)>);

impl Query {
    fn parse(raw: &str) -> Self {
        let pairs = raw
            .split('&')
            .filter(|part| !part.is_empty())
            .map(|part| {
                let (name, value) = part.split_once('=').unwrap_or((part, ""));
                (decoded(name, true), decoded(value, true))
            })
            .collect();
        Self(pairs)
    }

    /// The last value given for `name`, as the server read a repeated name.
    fn get(&self, name: &str) -> Option<&str> {
        self.0
            .iter()
            .rev()
            .find(|(key, _)| key == name)
            .map(|(_, value)| value.as_str())
    }

    /// A flag as the server read one (pydantic's lax reading: true, 1, yes, on and their opposites).
    fn flag(&self, name: &str) -> ServiceResult<bool> {
        match self.get(name) {
            None => Ok(false),
            Some(text) => {
                yes_or_no(&Value::String(text.to_string())).ok_or_else(|| invalid(INVALID_INPUT))
            }
        }
    }

    /// A whole number given as text. One too large for 64 bits is kept as None, which matches no stored
    /// revision, as the store read Python's larger numbers.
    fn whole(&self, name: &str) -> ServiceResult<Option<Option<i64>>> {
        let Some(text) = self.get(name) else {
            return Ok(None);
        };
        let text = text.trim();
        let digits = text.strip_prefix(['+', '-']).unwrap_or(text);
        if digits.is_empty() || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
            return Err(invalid(INVALID_INPUT));
        }
        Ok(Some(text.trim_start_matches('+').parse::<i64>().ok()))
    }
}

/// The request body: a JSON object, as each route's body had to be.
fn object(body: &str) -> ServiceResult<Value> {
    match serde_json::from_str::<Value>(body) {
        Ok(value @ Value::Object(_)) => Ok(value),
        _ => Err(invalid(INVALID_INPUT)),
    }
}

/// The fields a sign-in form may hold, each a string (or `keep` a flag); any other field is refused.
struct Form(Map<String, Value>);

impl Form {
    fn read(body: &str, fields: &[&str]) -> ServiceResult<Self> {
        let Value::Object(map) = object(body)? else {
            unreachable!("object() answers objects only")
        };
        if map.keys().any(|key| !fields.contains(&key.as_str())) {
            return Err(invalid(INVALID_INPUT));
        }
        Ok(Self(map))
    }

    fn text(&self, name: &str) -> ServiceResult<&str> {
        self.0
            .get(name)
            .and_then(Value::as_str)
            .ok_or_else(|| invalid(INVALID_INPUT))
    }

    fn keep(&self) -> ServiceResult<bool> {
        match self.0.get("keep") {
            None => Ok(false),
            Some(keep) => yes_or_no(keep).ok_or_else(|| invalid(INVALID_INPUT)),
        }
    }
}

fn signed_in_answer(signed: SignedIn, status: u16) -> Answer {
    let mut body = json!({ "id": signed.account.id, "username": signed.account.username });
    if let Some(codes) = signed.recovery_codes {
        body["recovery_codes"] = json!(codes);
    }
    Answer {
        status,
        body: Some(body),
        session: Session::Started(signed.token),
    }
}

fn ended() -> Answer {
    Answer {
        status: 204,
        body: None,
        session: Session::Ended,
    }
}

/// Answers one request. Every refusal and storage failure is an answer, never an error.
pub fn answer(
    store: &Path,
    request: &Request<'_>,
    clock: &Clock<'_>,
    entropy: &mut dyn Entropy,
) -> Answer {
    if request.body.len() > MAX_BODY {
        return Answer::refused(413, TOO_LARGE);
    }
    routed(store, request, clock, entropy).unwrap_or_else(failed)
}

fn routed(
    store: &Path,
    request: &Request<'_>,
    clock: &Clock<'_>,
    entropy: &mut dyn Entropy,
) -> ServiceResult<Answer> {
    let (path, query) = request.path.split_once('?').unwrap_or((request.path, ""));
    let Some(rest) = path.strip_prefix("/api/") else {
        return Ok(Answer::refused(404, NOT_FOUND));
    };
    // Each segment is decoded on its own, so an id holding an escaped `/` stays one id. An empty segment
    // names no route, as a path parameter is never empty.
    let parts: Vec<String> = rest.split('/').map(|part| decoded(part, false)).collect();
    if parts.iter().any(String::is_empty) {
        return Ok(Answer::refused(404, NOT_FOUND));
    }
    let parts: Vec<&str> = parts.iter().map(String::as_str).collect();
    let query = Query::parse(query);
    let asker = Asker {
        address: LOCAL_ADDRESS,
        now: clock.seconds,
    };
    let method = request.method.to_ascii_uppercase();
    let user = || -> ServiceResult<Account> {
        accounts::signed_in(store, request.token, clock.seconds, request.account)
    };
    let body = || object(request.body);
    let moment = || {
        parse_moment(clock.now)
            .map_err(|error| ServiceError::Broken(format!("the app's clock: {}", error.message)))
    };

    let answer = match (method.as_str(), parts.as_slice()) {
        ("POST", ["auth", "register" | "login"]) => {
            let form = Form::read(request.body, &["username", "password", "keep"])?;
            let username = accounts::checked_username(form.text("username")?)?;
            let password = accounts::checked_password(form.text("password")?)?;
            let keep = form.keep()?;
            let registering = parts[1] == "register";
            let signing = if registering {
                accounts::register
            } else {
                accounts::login
            };
            let signed = signing(
                store,
                asker,
                entropy,
                &username,
                password,
                keep,
                request.token,
            )?;
            signed_in_answer(signed, if registering { 201 } else { 200 })
        }
        ("GET", ["auth", "me"]) => {
            let account = user()?;
            Answer::ok(json!({ "id": account.id, "username": account.username }))
        }
        ("POST", ["auth", "logout"]) => {
            accounts::logout(store, request.token, clock.seconds, request.account)?;
            ended()
        }
        ("POST", ["auth", "recover"]) => {
            let form = Form::read(request.body, &["username", "code", "password", "keep"])?;
            let username = accounts::checked_username(form.text("username")?)?;
            let code = accounts::checked_code(form.text("code")?)?;
            let password = accounts::checked_password(form.text("password")?)?;
            let keep = form.keep()?;
            let signed = accounts::recover(store, asker, entropy, &username, code, password, keep)?;
            signed_in_answer(signed, 200)
        }
        ("GET", ["auth", "recovery-status"]) => {
            let account = user()?;
            Answer::ok(json!({ "remaining": accounts::recovery_codes_left(store, account.id)? }))
        }
        ("POST", ["auth", "recovery-codes"]) => {
            let account = user()?;
            let form = Form::read(request.body, &["password"])?;
            let password = accounts::checked_password(form.text("password")?)?;
            let codes = accounts::renew_recovery_codes(store, asker, entropy, &account, password)?;
            Answer::ok(json!({ "recovery_codes": codes, "remaining": codes.len() }))
        }
        ("POST", ["auth", "password"]) => {
            let account = user()?;
            let form = Form::read(request.body, &["current_password", "new_password"])?;
            let current = accounts::checked_password(form.text("current_password")?)?;
            let new = accounts::checked_password(form.text("new_password")?)?;
            let token = accounts::change_password(store, asker, entropy, &account, current, new)?;
            Answer {
                status: 200,
                body: Some(json!({ "id": account.id, "username": account.username })),
                session: Session::Started(token),
            }
        }
        ("DELETE", ["auth", "account"]) => {
            let account = user()?;
            let form = Form::read(request.body, &["password"])?;
            let password = accounts::checked_password(form.text("password")?)?;
            accounts::delete_account(store, asker, &account, password)?;
            ended()
        }
        ("GET", ["week"]) => {
            let account = user()?;
            let start = match query.get("week_start") {
                Some(start) => start.to_string(),
                None => flexweek_engine::time::monday_of(clock.now.get(..10).unwrap_or(clock.now))
                    .map_err(|error| ServiceError::Broken(error.message))?,
            };
            Answer::ok(weeks::read_week(store, account.id, &start)?)
        }
        ("PUT", ["week"]) => {
            let account = user()?;
            Answer::ok(week_saves::save_week(store, account.id, &body()?)?)
        }
        ("GET", ["weeks"]) => Answer::ok(weeks::list_weeks(store, user()?.id)?),
        ("GET", ["day"]) => {
            let account = user()?;
            let date = query.get("date").ok_or_else(|| invalid(DATE_RULE))?;
            Answer::ok(views::day(store, account.id, date, moment()?)?)
        }
        ("GET", ["month"]) => {
            let account = user()?;
            let first_day = match query.whole("first_day")? {
                None => 0,
                // Checked before the month, as the server checked its query values first.
                Some(Some(day @ 0..=6)) => day as u32,
                Some(_) => return Err(invalid(INVALID_INPUT)),
            };
            let month = query.get("month").ok_or_else(|| invalid(MONTH_RULE))?;
            Answer::ok(views::month(
                store,
                account.id,
                month,
                first_day,
                moment()?,
            )?)
        }
        ("GET", ["assignments"]) => {
            let account = user()?;
            let completed = query.flag("include_completed")?;
            let start = query
                .get("week_start")
                .ok_or_else(|| invalid(WEEK_START_RULE))?;
            Answer::ok(views::homework(
                store,
                account.id,
                start,
                completed,
                moment()?,
            )?)
        }
        ("PUT", ["assignments", id]) => {
            let account = user()?;
            Answer::ok(homework_saves::save_homework(
                store,
                account.id,
                id,
                &body()?,
            )?)
        }
        ("POST", ["assignments", id, "spread"]) => {
            let account = user()?;
            Answer::ok(homework_saves::spread_preview(
                store,
                account.id,
                id,
                &body()?,
            )?)
        }
        ("DELETE", ["assignments", id]) => {
            let account = user()?;
            let revision = query
                .whole("revision")?
                .ok_or_else(|| invalid(REVISION_REQUIRED))?;
            Answer::ok(records::delete_homework(store, account.id, id, revision)?)
        }
        ("POST", ["repeat-edits"]) => {
            let account = user()?;
            Answer::ok(week_saves::preview_repeat_edits(
                store,
                account.id,
                &body()?,
            )?)
        }
        ("POST", ["changes"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(changes::apply_changes(
                store,
                account.id,
                &given,
                clock.restore_token,
                clock.now,
            )?)
        }
        ("GET", ["preferences"]) => Answer::ok(preferences::read_preferences(store, user()?.id)?),
        ("PUT", ["preferences"]) => {
            let account = user()?;
            Answer::ok(preferences::write_preferences(store, account.id, &body()?)?)
        }
        ("GET", ["routines"]) => Answer::ok(views::routines(store, user()?.id)?),
        ("PUT", ["routines", id]) => {
            let account = user()?;
            Answer::ok(records::save_routine(
                store,
                account.id,
                id,
                &body()?,
                clock.now,
            )?)
        }
        ("DELETE", ["routines", id]) => {
            let account = user()?;
            let revision = query
                .whole("revision")?
                .ok_or_else(|| invalid(REVISION_REQUIRED))?;
            let operation = query.get("operation_id");
            Answer::ok(records::delete_routine(
                store, account.id, id, revision, operation,
            )?)
        }
        ("GET", ["storage-info"]) => {
            let account = user()?;
            Answer::ok(json!({
                "mode": "local",
                "label": "On this device",
                "username": account.username,
                "transfer_limit_bytes": MAX_BODY,
            }))
        }
        ("POST", ["account-export"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(transfer::export_account(
                store, asker, &account, &given, clock.now,
            )?)
        }
        ("POST", ["account-import", "preview"]) => {
            let account = user()?;
            Answer::ok(transfer::import_preview(store, account.id, &body()?)?)
        }
        ("POST", ["account-import"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(transfer::import_account(
                store,
                account.id,
                &given,
                clock.restore_token,
                clock.now,
            )?)
        }
        ("GET", ["timer-presets"]) => {
            user()?;
            Answer::ok(json!({ "presets": flexweek_engine::plan::timer_presets() }))
        }
        ("GET", ["reminder-limits"]) => {
            user()?;
            Answer::ok(json!(flexweek_engine::plan::reminder_limits()))
        }
        ("POST", ["timer-split-preview"]) => {
            user()?;
            Answer::ok(comfort::split_preview(&body()?)?)
        }
        ("GET", ["restore-points"]) => Answer::ok(views::restore_points(store, user()?.id)?),
        ("POST", ["restore-points"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(records::create_restore_point(
                store,
                account.id,
                &given,
                clock.restore_token,
                clock.now,
            )?)
        }
        ("GET", ["restore-points", id, "preview"]) => {
            let account = user()?;
            Answer::ok(records::restore_preview(store, account.id, id)?)
        }
        ("POST", ["restore-points", id, "restore"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(records::restore(
                store,
                account.id,
                id,
                &given,
                clock.restore_token,
                clock.now,
            )?)
        }
        ("POST", ["solve"]) => {
            let account = user()?;
            let given = body()?;
            Answer::ok(plans::plan(store, account.id, &given, clock.stopwatch)?)
        }
        ("GET", ["health"]) => Answer::ok(json!({ "ok": true })),
        (_, route) if known(route) => Answer::refused(405, NOT_ALLOWED),
        _ => Answer::refused(404, NOT_FOUND),
    };
    Ok(answer)
}

/// A path some method answers, so another method on it is "not allowed" rather than "not found".
fn known(route: &[&str]) -> bool {
    matches!(
        route,
        [
            "auth",
            "register" | "login" | "me" | "logout" | "recover" | "recovery-status"
        ] | ["auth", "recovery-codes" | "password" | "account"]
            | ["week" | "weeks" | "day" | "month" | "assignments" | "repeat-edits" | "changes"]
            | ["preferences" | "routines" | "storage-info" | "account-export" | "account-import"]
            | ["timer-presets" | "reminder-limits" | "timer-split-preview" | "restore-points"]
            | ["solve" | "health"]
            | ["assignments" | "routines", _]
            | ["assignments", _, "spread"]
            | ["account-import", "preview"]
            | ["restore-points", _, "preview" | "restore"]
    )
}
