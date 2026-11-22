//! How long a sign-in lasts (spec.md): seven days, or thirty with "Keep me signed in", each renewed by use;
//! an ended session says so. The Rust twins of backend/tests/test_session_lifetime.py (its cookie check
//! is the route's and stays in Python, in test_session_cookie_and_request_checks.py).

use std::path::PathBuf;

use flexweek_service::accounts::{self, Asker, Entropy, SESSION_ENDED, SignedIn};
use flexweek_service::{Refusal, ServiceError, ServiceResult, with_db};
use flexweek_store::{SESSION_SECONDS, SESSION_SECONDS_KEEP};

const NOW: i64 = 1_793_000_000;
const DAY: i64 = 24 * 60 * 60;
const PASSWORD: &str = "a-long-test-password";

struct Counting(u64);

impl Entropy for Counting {
    fn session_token(&mut self) -> ServiceResult<String> {
        self.0 += 1;
        Ok(format!("token-{:040}", self.0))
    }
    fn salt(&mut self) -> ServiceResult<String> {
        self.0 += 1;
        Ok(format!("{:032x}", self.0))
    }
    fn code_bytes(&mut self) -> ServiceResult<[u8; 8]> {
        self.0 += 1;
        Ok(self.0.to_be_bytes())
    }
}

struct Db {
    dir: PathBuf,
    path: PathBuf,
}

impl Drop for Db {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

fn at(now: i64) -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now,
    }
}

/// A student who signed up and then signed in, ticking "Keep me signed in" or not, at NOW.
fn signed_in(name: &str, keep: bool) -> (Db, SignedIn) {
    let dir = std::env::temp_dir().join(format!("flexweek-lifetime-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("sessions.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    let mut entropy = Counting(0);
    accounts::register(&path, at(NOW), &mut entropy, "student", PASSWORD, false, "").unwrap();
    let session =
        accounts::login(&path, at(NOW), &mut entropy, "student", PASSWORD, keep, "").unwrap();
    (Db { dir, path }, session)
}

fn stored(db: &Db, token: &str) -> (i64, Option<i64>) {
    rusqlite::Connection::open(&db.path)
        .unwrap()
        .query_row(
            "SELECT expires, lifetime FROM sessions WHERE token_hash = ?1",
            [flexweek_store::digest(token)],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap()
}

fn open_at(db: &Db, token: &str, now: i64) -> bool {
    accounts::signed_in(&db.path, token, now, None).is_ok()
}

fn ended_at(db: &Db, token: &str, now: i64) {
    match accounts::signed_in(&db.path, token, now, None) {
        Err(ServiceError::Refused(Refusal::Unauthorized(words))) => {
            assert_eq!(words, SESSION_ENDED);
        }
        other => panic!("the session did not end: {other:?}"),
    }
}

#[test]
fn a_ticked_session_is_stored_for_thirty_days_and_an_unticked_one_for_seven() {
    let (db, kept) = signed_in("stored-kept", true);
    assert_eq!(SESSION_SECONDS_KEEP, 30 * DAY);
    assert_eq!(
        stored(&db, &kept.token),
        (NOW + SESSION_SECONDS_KEEP, Some(SESSION_SECONDS_KEEP))
    );
    let (db, plain) = signed_in("stored-plain", false);
    assert_eq!(SESSION_SECONDS, 7 * DAY);
    assert_eq!(stored(&db, &plain.token).0, NOW + SESSION_SECONDS);
}

#[test]
fn a_ticked_session_is_open_on_day_29_and_ended_on_day_31() {
    let (db, kept) = signed_in("ticked-29", true);
    assert!(open_at(&db, &kept.token, NOW + 29 * DAY));
    let (db, kept) = signed_in("ticked-31", true);
    ended_at(&db, &kept.token, NOW + 31 * DAY);
}

#[test]
fn an_unticked_session_left_alone_has_ended_on_day_8() {
    let (db, plain) = signed_in("unticked-8", false);
    ended_at(&db, &plain.token, NOW + 8 * DAY);
}

#[test]
fn an_unticked_session_used_on_day_6_is_still_open_on_day_12() {
    let (db, plain) = signed_in("unticked-12", false);
    assert!(open_at(&db, &plain.token, NOW + 6 * DAY));
    assert!(open_at(&db, &plain.token, NOW + 12 * DAY));
}

#[test]
fn a_session_row_with_no_length_is_renewed_for_seven_days() {
    let (db, plain) = signed_in("no-length", false);
    with_db(&db.path, |conn| {
        conn.execute(
            "UPDATE sessions SET lifetime = NULL, expires = ?1 WHERE token_hash = ?2",
            rusqlite::params![NOW + SESSION_SECONDS, flexweek_store::digest(&plain.token)],
        )
        .unwrap();
        Ok(())
    })
    .unwrap();
    // Each use renews it for seven days: used on days 6 and 12, it has ended by day 20.
    assert!(open_at(&db, &plain.token, NOW + 6 * DAY));
    assert!(open_at(&db, &plain.token, NOW + 12 * DAY));
    ended_at(&db, &plain.token, NOW + 20 * DAY);
}

#[test]
fn a_session_row_with_no_length_left_alone_has_ended_on_day_8() {
    let (db, plain) = signed_in("no-length-alone", false);
    with_db(&db.path, |conn| {
        conn.execute(
            "UPDATE sessions SET lifetime = NULL, expires = ?1 WHERE token_hash = ?2",
            rusqlite::params![NOW + SESSION_SECONDS, flexweek_store::digest(&plain.token)],
        )
        .unwrap();
        Ok(())
    })
    .unwrap();
    ended_at(&db, &plain.token, NOW + 8 * DAY);
}
