//! The desktop's requests answered with no server (flexweek_service::desk_requests): what the window
//! reads from each answer, its status, its words, and whether a session started or ended. The scripted
//! comparison with the FastAPI server (backend/tests/test_desk_requests_answer_as_the_server.py) showed
//! every route answers as the server did; these hold the parts the window depends on once it is gone.

use flexweek_service::desk_requests::{
    Answer, Clock, DATE_RULE, MONTH_RULE, NOT_ALLOWED, NOT_FOUND, REVISION_REQUIRED, Request,
    SERVER_ERROR, STORAGE_UNAVAILABLE, Session, TOO_LARGE, WEEK_START_RULE, answer,
};
use flexweek_service::plans;
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const PASSWORD: &str = "a-long-test-password";
const NOW: &str = "2026-11-05T19:00";
const SECONDS: i64 = 1_793_934_000;
/// Plans take no time here: the answer's timing is not what these tests read.
fn no_time() -> plans::Stopwatch {
    Box::new(|| 0.0)
}

const INVALID: &str = "Invalid input. Check field lengths, times and required values.";

struct Window<'a> {
    db: &'a TestDb,
    token: String,
    account: Option<String>,
    entropy: Counting,
}

impl<'a> Window<'a> {
    fn new(db: &'a TestDb) -> Self {
        Self {
            db,
            token: String::new(),
            account: None,
            entropy: Counting(0),
        }
    }

    fn send(&mut self, method: &str, path: &str, body: &str) -> Answer {
        let request = Request {
            method,
            path,
            body,
            token: &self.token,
            account: self.account.as_deref(),
        };
        let clock = Clock {
            seconds: SECONDS,
            now: NOW,
            restore_token: "0123456789abcdef",
            stopwatch: &no_time,
        };
        let answer = answer(&self.db.path, &request, &clock, &mut self.entropy);
        match &answer.session {
            Session::Started(token) => {
                self.token = token.clone();
                self.account = answer.body.as_ref().map(|body| body["id"].to_string());
            }
            Session::Ended => {
                self.token.clear();
                self.account = None;
            }
            Session::Kept => {}
        }
        answer
    }

    fn json(&mut self, method: &str, path: &str, body: Value) -> Answer {
        self.send(method, path, &body.to_string())
    }

    fn signed_up(db: &'a TestDb, name: &str) -> Self {
        Self::signed_up_drawing(db, name, 0)
    }

    /// Signed up with its own random draws, so a second account's session and salt differ.
    fn signed_up_drawing(db: &'a TestDb, name: &str, seed: u64) -> Self {
        let mut window = Self::new(db);
        window.entropy = Counting(seed);
        let made = window.json(
            "POST",
            "/api/auth/register",
            json!({ "username": name, "password": PASSWORD }),
        );
        assert_eq!(made.status, 201, "{made:?}");
        window
    }
}

fn detail(answer: &Answer) -> &str {
    answer.body.as_ref().unwrap()["detail"].as_str().unwrap()
}

fn refused(answer: &Answer, status: u16, words: &str) {
    assert_eq!(
        (answer.status, detail(answer), &answer.session),
        (status, words, &Session::Kept),
        "{answer:?}"
    );
}

#[test]
fn signing_up_starts_a_session_with_recovery_codes_and_the_lowercased_name() {
    let db = TestDb::new("desk-sign-up");
    let mut window = Window::new(&db);
    let made = window.json(
        "POST",
        "/api/auth/register",
        json!({ "username": "Ana_1", "password": PASSWORD, "keep": "yes" }),
    );
    assert_eq!(made.status, 201);
    let Session::Started(token) = &made.session else {
        panic!("{made:?}")
    };
    assert!(!token.is_empty());
    let body = made.body.unwrap();
    assert_eq!(body["username"], "ana_1");
    assert_eq!(body["recovery_codes"].as_array().unwrap().len(), 8);
    let me = window.send("GET", "/api/auth/me", "");
    assert_eq!(
        me.body.unwrap(),
        json!({ "id": body["id"], "username": "ana_1" })
    );
}

#[test]
fn a_sign_in_form_with_a_wrong_field_is_refused_before_anything_is_asked() {
    let db = TestDb::new("desk-forms");
    let mut window = Window::new(&db);
    for body in [
        json!({ "username": "ab", "password": PASSWORD }),
        json!({ "username": "ana", "password": "short" }),
        json!({ "username": "ana", "password": PASSWORD, "extra": 1 }),
        json!({ "username": "ana", "password": PASSWORD, "keep": "maybe" }),
        json!({ "username": 7, "password": PASSWORD }),
        json!([1, 2]),
    ] {
        let answer = window.json("POST", "/api/auth/register", body.clone());
        refused(&answer, 422, INVALID);
    }
    refused(
        &window.send("POST", "/api/auth/login", "not json"),
        422,
        INVALID,
    );
    refused(&window.send("POST", "/api/auth/login", ""), 422, INVALID);
}

#[test]
fn signing_in_wrongly_says_so_and_too_many_tries_wait() {
    let db = TestDb::new("desk-wrong");
    Window::signed_up(&db, "ana");
    let mut window = Window::new(&db);
    let wrong = json!({ "username": "ana", "password": "wrong-password-1" });
    refused(
        &window.json("POST", "/api/auth/login", wrong.clone()),
        401,
        "Incorrect username or password",
    );
    let statuses: Vec<u16> = (0..12)
        .map(|_| window.json("POST", "/api/auth/login", wrong.clone()).status)
        .collect();
    assert_eq!(statuses.last(), Some(&429), "{statuses:?}");
}

#[test]
fn reads_need_a_session_and_the_account_the_window_expects() {
    let db = TestDb::new("desk-session");
    let mut window = Window::new(&db);
    refused(&window.send("GET", "/api/week", ""), 401, "Please sign in");
    let mut ana = Window::signed_up(&db, "ana");
    assert_eq!(ana.send("GET", "/api/week", "").status, 200);
    ana.account = Some("99".into());
    assert_eq!(ana.send("GET", "/api/week", "").status, 401);
}

#[test]
fn signing_out_ends_the_session_and_its_token_no_longer_works() {
    let db = TestDb::new("desk-sign-out");
    let mut ana = Window::signed_up(&db, "ana");
    let token = ana.token.clone();
    let out = ana.send("POST", "/api/auth/logout", "");
    assert_eq!(
        (out.status, &out.body, &out.session),
        (204, &None, &Session::Ended)
    );
    ana.token = token;
    assert_eq!(ana.send("GET", "/api/auth/me", "").status, 401);
}

#[test]
fn changing_the_password_starts_a_new_session() {
    let db = TestDb::new("desk-password");
    let mut ana = Window::signed_up(&db, "ana");
    let old = ana.token.clone();
    let changed = ana.json(
        "POST",
        "/api/auth/password",
        json!({ "current_password": PASSWORD, "new_password": "replacement-pw-1" }),
    );
    assert_eq!(changed.status, 200);
    assert!(matches!(&changed.session, Session::Started(new) if *new != old));
    assert_eq!(ana.send("GET", "/api/auth/me", "").status, 200);
}

#[test]
fn deleting_the_account_ends_the_session() {
    let db = TestDb::new("desk-delete");
    let mut ana = Window::signed_up(&db, "ana");
    refused(
        &ana.json(
            "DELETE",
            "/api/auth/account",
            json!({ "password": "wrong-password-1" }),
        ),
        401,
        "Incorrect password",
    );
    let gone = ana.json(
        "DELETE",
        "/api/auth/account",
        json!({ "password": PASSWORD }),
    );
    assert_eq!((gone.status, gone.session), (204, Session::Ended));
}

#[test]
fn a_missing_or_unreadable_query_value_gets_its_rule() {
    let db = TestDb::new("desk-query");
    let mut ana = Window::signed_up(&db, "ana");
    refused(&ana.send("GET", "/api/day", ""), 422, DATE_RULE);
    refused(&ana.send("GET", "/api/month", ""), 422, MONTH_RULE);
    refused(
        &ana.send("GET", "/api/assignments", ""),
        422,
        WEEK_START_RULE,
    );
    refused(
        &ana.send("GET", "/api/month?month=2026-11&first_day=-1", ""),
        422,
        INVALID,
    );
    refused(
        &ana.send(
            "GET",
            "/api/assignments?week_start=2026-11-02&include_completed=maybe",
            "",
        ),
        422,
        INVALID,
    );
    let shown = ana.send(
        "GET",
        "/api/assignments?week_start=2026-11-02&include_completed=Yes",
        "",
    );
    assert_eq!(shown.status, 200);
    refused(
        &ana.send("DELETE", "/api/routines/r1", ""),
        422,
        REVISION_REQUIRED,
    );
    refused(
        &ana.send("DELETE", "/api/routines/r1?revision=abc", ""),
        422,
        INVALID,
    );
}

#[test]
fn the_week_without_a_start_is_this_weeks_monday() {
    let db = TestDb::new("desk-this-week");
    let mut ana = Window::signed_up(&db, "ana");
    let week = ana.send("GET", "/api/week", "").body.unwrap();
    assert_eq!(week["week_start"], "2026-11-02");
}

#[test]
fn ids_in_the_path_are_read_with_their_escapes() {
    let db = TestDb::new("desk-escapes");
    let mut ana = Window::signed_up(&db, "ana");
    let routine = json!({ "id": "r one/2", "name": "Morning", "blocks": [], "revision": 0 });
    let saved = ana.json("PUT", "/api/routines/r%20one%2F2", routine);
    assert_eq!(saved.status, 200, "{saved:?}");
    assert_eq!(saved.body.unwrap()["id"], "r one/2");
    // A revision past 64 bits matches no stored one: the routine changed, it is not a bad request.
    let stale = ana.send(
        "DELETE",
        "/api/routines/r%20one%2F2?revision=99999999999999999999999",
        "",
    );
    assert_eq!(stale.status, 409, "{stale:?}");
    let gone = ana.send("DELETE", "/api/routines/r%20one%2F2?revision=1", "");
    assert_eq!(gone.status, 200, "{gone:?}");
}

#[test]
fn a_body_that_is_not_an_object_is_refused_after_the_session_check() {
    let db = TestDb::new("desk-bodies");
    let mut window = Window::new(&db);
    refused(
        &window.send("PUT", "/api/week", "[]"),
        401,
        "Please sign in",
    );
    let mut ana = Window::signed_up(&db, "ana");
    for body in ["[]", "nope", "", "3"] {
        refused(&ana.send("PUT", "/api/preferences", body), 422, INVALID);
    }
}

#[test]
fn a_request_too_large_is_refused_whatever_it_asks() {
    let db = TestDb::new("desk-large");
    let mut window = Window::new(&db);
    let body = format!("{{\"pad\": \"{}\"}}", "x".repeat(300_000));
    refused(
        &window.send("POST", "/api/auth/register", &body),
        413,
        TOO_LARGE,
    );
}

#[test]
fn unknown_paths_and_methods_are_told_apart() {
    let db = TestDb::new("desk-paths");
    let mut window = Window::new(&db);
    refused(&window.send("GET", "/api/nothing-here", ""), 404, NOT_FOUND);
    refused(&window.send("GET", "/elsewhere", ""), 404, NOT_FOUND);
    refused(&window.send("PATCH", "/api/week", "{}"), 405, NOT_ALLOWED);
    refused(
        &window.send("GET", "/api/restore-points/p1/restore", ""),
        405,
        NOT_ALLOWED,
    );
    assert_eq!(
        window.send("get", "/api/health", "").body,
        Some(json!({ "ok": true }))
    );
}

#[test]
fn storage_that_cannot_be_opened_keeps_the_students_changes() {
    let db = TestDb::new("desk-storage");
    let mut ana = Window::signed_up(&db, "ana");
    let request = Request {
        method: "GET",
        path: "/api/auth/me",
        body: "",
        token: &ana.token,
        account: None,
    };
    let clock = Clock {
        seconds: SECONDS,
        now: NOW,
        restore_token: "0123456789abcdef",
        stopwatch: &no_time,
    };
    let nowhere = db.path.with_file_name("missing-folder").join("flexweek.db");
    let answer = answer(&nowhere, &request, &clock, &mut ana.entropy);
    refused(&answer, 503, STORAGE_UNAVAILABLE);
}

#[test]
fn storage_info_says_this_device_and_the_transfer_limit() {
    let db = TestDb::new("desk-storage-info");
    let mut ana = Window::signed_up(&db, "ana");
    assert_eq!(
        ana.send("GET", "/api/storage-info", "").body.unwrap(),
        json!({ "mode": "local", "label": "On this device", "username": "ana",
                "transfer_limit_bytes": 262_144 })
    );
}

#[test]
fn a_percent_sign_without_two_hex_digits_stays_as_written() {
    let db = TestDb::new("desk-percent");
    let mut ana = Window::signed_up(&db, "ana");
    let routine = json!({ "id": "r%+1", "name": "Morning", "blocks": [], "revision": 0 });
    let saved = ana.json("PUT", "/api/routines/r%+1", routine);
    assert_eq!(saved.status, 200, "{saved:?}");
}

#[test]
fn bytes_that_are_not_text_are_read_as_a_replacement_character_not_refused() {
    let db = TestDb::new("desk-bytes");
    let mut window = Window::new(&db);
    assert_eq!(window.send("GET", "/api/health?x=%FF", "").status, 200);
    refused(
        &window.send("GET", "/api/week?week_start=%FF", ""),
        401,
        "Please sign in",
    );
    refused(&window.send("GET", "/api/nothing%FF", ""), 404, NOT_FOUND);
    let mut ana = Window::signed_up(&db, "ana");
    let routine = json!({ "id": "r\u{fffd}", "name": "Morning", "blocks": [], "revision": 0 });
    let saved = ana.json("PUT", "/api/routines/r%FF", routine);
    assert_eq!(saved.status, 200, "{saved:?}");
}

#[test]
fn an_empty_path_segment_names_no_route() {
    let db = TestDb::new("desk-empty-segment");
    let mut ana = Window::signed_up(&db, "ana");
    refused(
        &ana.send("GET", "/api/restore-points//preview", ""),
        404,
        NOT_FOUND,
    );
    refused(
        &ana.send("POST", "/api/assignments//spread", "{}"),
        404,
        NOT_FOUND,
    );
    refused(
        &ana.send("DELETE", "/api/routines/?revision=1", ""),
        404,
        NOT_FOUND,
    );
}

#[test]
fn the_first_day_is_checked_before_the_month_is_asked_for() {
    let db = TestDb::new("desk-first-day");
    let mut ana = Window::signed_up(&db, "ana");
    refused(&ana.send("GET", "/api/month?first_day=7", ""), 422, INVALID);
    refused(
        &ana.send("GET", "/api/month?first_day=6", ""),
        422,
        MONTH_RULE,
    );
}

#[test]
fn a_clock_that_is_not_a_date_is_a_server_error_not_a_panic() {
    let db = TestDb::new("desk-odd-clock");
    let mut ana = Window::signed_up(&db, "ana");
    let request = Request {
        method: "GET",
        path: "/api/week",
        body: "",
        token: &ana.token,
        account: None,
    };
    let clock = Clock {
        seconds: SECONDS,
        now: "2026-11-0\u{e9}T19:00",
        restore_token: "0123456789abcdef",
        stopwatch: &no_time,
    };
    let answer = answer(&db.path, &request, &clock, &mut ana.entropy);
    refused(&answer, 500, SERVER_ERROR);
}

#[test]
fn every_private_request_needs_a_session_and_a_made_up_one_is_refused() {
    let db = TestDb::new("desk-private");
    let mut window = Window::new(&db);
    let week = json!({ "week_start": "2026-11-02", "blocks": [], "revision": 0 });
    let private: [(&str, &str, Value); 25] = [
        ("GET", "/api/auth/me", json!(null)),
        ("GET", "/api/auth/recovery-status", json!(null)),
        (
            "POST",
            "/api/auth/recovery-codes",
            json!({ "password": PASSWORD }),
        ),
        (
            "POST",
            "/api/auth/password",
            json!({ "current_password": PASSWORD, "new_password": PASSWORD }),
        ),
        (
            "DELETE",
            "/api/auth/account",
            json!({ "password": PASSWORD }),
        ),
        ("GET", "/api/week", json!(null)),
        ("PUT", "/api/week", week),
        ("GET", "/api/weeks", json!(null)),
        ("GET", "/api/day?date=2026-11-05", json!(null)),
        ("GET", "/api/month?month=2026-11", json!(null)),
        ("GET", "/api/assignments?week_start=2026-11-02", json!(null)),
        ("PUT", "/api/assignments/hw", json!({})),
        ("POST", "/api/assignments/hw/spread", json!({})),
        ("DELETE", "/api/assignments/hw?revision=1", json!(null)),
        ("POST", "/api/repeat-edits", json!({ "repeats": [] })),
        (
            "POST",
            "/api/changes",
            json!({ "weeks": [], "assignments": [] }),
        ),
        ("GET", "/api/preferences", json!(null)),
        ("PUT", "/api/preferences", json!({})),
        ("GET", "/api/routines", json!(null)),
        ("DELETE", "/api/routines/r1?revision=1", json!(null)),
        ("GET", "/api/storage-info", json!(null)),
        (
            "POST",
            "/api/account-export",
            json!({ "password": PASSWORD }),
        ),
        ("GET", "/api/restore-points", json!(null)),
        (
            "POST",
            "/api/restore-points",
            json!({ "label": "Before", "operation_id": "op-1" }),
        ),
        ("POST", "/api/solve", json!({ "blocks": [] })),
    ];
    for token in ["", "made-up-token"] {
        window.token = token.to_string();
        for (method, path, body) in &private {
            let text = if body.is_null() {
                String::new()
            } else {
                body.to_string()
            };
            let answer = window.send(method, path, &text);
            assert_eq!(
                answer.status, 401,
                "{method} {path} with {token:?}: {answer:?}"
            );
        }
    }
}

#[test]
fn signing_out_with_no_session_is_accepted() {
    let db = TestDb::new("desk-sign-out-none");
    let mut window = Window::new(&db);
    let out = window.send("POST", "/api/auth/logout", "");
    assert_eq!((out.status, out.session), (204, Session::Ended));
}

#[test]
fn a_window_that_names_an_older_account_can_not_read_write_or_sign_out_the_new_one() {
    let db = TestDb::new("desk-older-account");
    let first = Window::signed_up(&db, "first");
    let mut second = Window::signed_up_drawing(&db, "second", 1_000);
    second.account = first.account.clone();
    assert_eq!(second.send("GET", "/api/week", "").status, 401);
    let week = json!({ "week_start": "2026-11-02", "blocks": [], "revision": 0 });
    assert_eq!(second.json("PUT", "/api/week", week).status, 401);
    assert_eq!(second.send("POST", "/api/auth/logout", "").status, 401);
    second.account = None;
    assert_eq!(
        second.send("GET", "/api/auth/me", "").body.unwrap()["username"],
        "second"
    );
}
