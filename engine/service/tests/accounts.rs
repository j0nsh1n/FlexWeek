//! The account rules, from what a student is promised: a new account gets eight one-time codes, a
//! wrong password or code never says which part was wrong, a new password ends every other session,
//! too many tries wait five minutes, and a deleted account frees its name.

use std::path::PathBuf;

use flexweek_service::accounts::{
    self, ACCOUNT_CHANGED, Account, Asker, Entropy, PASSWORD_SAME, PASSWORD_WRONG, PLEASE_SIGN_IN,
    RECOVER_WRONG, RECOVERY_CODE_COUNT, SESSION_ENDED, SIGN_IN_WRONG, TOO_MANY_TRIES,
    USERNAME_TAKEN,
};
use flexweek_service::{Refusal, ServiceError, with_db};

const NOW: i64 = 1_793_000_000;

/// Counts up, so every token, salt and code is new and a test can predict nothing else.
struct Counting(u64);

impl Entropy for Counting {
    fn session_token(&mut self) -> String {
        self.0 += 1;
        format!("token-{:040}", self.0)
    }
    fn salt(&mut self) -> String {
        self.0 += 1;
        format!("{:032x}", self.0)
    }
    fn code_bytes(&mut self) -> Vec<u8> {
        self.0 += 1;
        self.0.to_be_bytes().to_vec()
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

fn fresh(name: &str) -> Db {
    let dir = std::env::temp_dir().join(format!("flexweek-service-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("flexweek.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    Db { dir, path }
}

fn at(now: i64) -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now,
    }
}

fn refusal(result: Result<impl std::fmt::Debug, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn signing_up_gives_eight_codes_and_the_store_keeps_only_their_hashes() {
    let db = fresh("signup");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let codes = made.recovery_codes.clone().unwrap();
    assert_eq!(codes.len(), RECOVERY_CODE_COUNT);
    let distinct: std::collections::BTreeSet<_> = codes.iter().collect();
    assert_eq!(distinct.len(), RECOVERY_CODE_COUNT);
    let stored = with_db(&db.path, |conn| {
        Ok(flexweek_store::recovery_hashes(conn, made.account.id)?)
    })
    .unwrap();
    assert_eq!(stored.len(), RECOVERY_CODE_COUNT);
    assert!(
        codes.iter().all(|code| !stored.contains(code)),
        "a code is stored as itself"
    );
    let who = accounts::signed_in(&db.path, &made.token, NOW + 1, None).unwrap();
    assert_eq!(
        who,
        Account {
            id: made.account.id,
            username: "ana".to_string()
        }
    );
}

#[test]
fn a_taken_name_is_refused_and_nothing_is_made() {
    let db = fresh("taken");
    let mut entropy = Counting(0);
    accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let again = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "other password 2",
        false,
        "",
    );
    assert_eq!(
        refusal(again),
        Refusal::Conflict(USERNAME_TAKEN.to_string())
    );
}

#[test]
fn a_wrong_password_and_an_unknown_name_get_the_same_words() {
    let db = fresh("wrong");
    let mut entropy = Counting(0);
    accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let wrong = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "wrong horse 1",
        false,
        "",
    );
    let unknown = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "nobody",
        "correct horse 1",
        false,
        "",
    );
    assert_eq!(
        refusal(wrong),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
    assert_eq!(
        refusal(unknown),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
}

#[test]
fn signing_in_ends_the_session_this_window_had() {
    let db = fresh("previous");
    let mut entropy = Counting(0);
    let first = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let second = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        &first.token,
    )
    .unwrap();
    assert!(accounts::signed_in(&db.path, &second.token, NOW + 1, None).is_ok());
    let old = accounts::signed_in(&db.path, &first.token, NOW + 1, None);
    assert_eq!(
        refusal(old),
        Refusal::Unauthorized(PLEASE_SIGN_IN.to_string())
    );
}

#[test]
fn a_session_says_when_it_ended_and_when_it_belongs_to_another_account() {
    let db = fresh("ended");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let eight_days = NOW + 8 * 24 * 60 * 60;
    let ended = accounts::signed_in(&db.path, &made.token, eight_days, None);
    assert_eq!(
        refusal(ended),
        Refusal::Unauthorized(SESSION_ENDED.to_string())
    );
    let other = accounts::signed_in(&db.path, &made.token, NOW + 1, Some("999"));
    assert_eq!(
        refusal(other),
        Refusal::Unauthorized(ACCOUNT_CHANGED.to_string())
    );
    let own = made.account.id.to_string();
    assert!(accounts::signed_in(&db.path, &made.token, NOW + 1, Some(&own)).is_ok());
}

#[test]
fn a_recovery_code_sets_a_new_password_signs_in_and_is_used_up() {
    let db = fresh("recover");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let code = made.recovery_codes.unwrap()[3].clone();
    let back = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        &code,
        "brand new pass 2",
        false,
    )
    .unwrap();
    assert!(accounts::signed_in(&db.path, &back.token, NOW + 1, None).is_ok());
    assert_eq!(
        accounts::recovery_codes_left(&db.path, made.account.id).unwrap(),
        7
    );
    let old_session = accounts::signed_in(&db.path, &made.token, NOW + 1, None);
    assert!(old_session.is_err(), "recovering keeps an old session");
    assert!(
        accounts::login(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana",
            "brand new pass 2",
            false,
            ""
        )
        .is_ok()
    );
    let again = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        &code,
        "third pass word 3",
        false,
    );
    assert_eq!(
        refusal(again),
        Refusal::Unauthorized(RECOVER_WRONG.to_string())
    );
}

#[test]
fn recovering_does_not_say_whether_the_name_exists() {
    let db = fresh("recover-unknown");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let code = made.recovery_codes.unwrap()[0].clone();
    let unknown = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "nobody",
        &code,
        "brand new pass 2",
        false,
    );
    let wrong = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "0000-0000-0000-0000",
        "brand new 2",
        false,
    );
    assert_eq!(
        refusal(unknown),
        Refusal::Unauthorized(RECOVER_WRONG.to_string())
    );
    assert_eq!(
        refusal(wrong),
        Refusal::Unauthorized(RECOVER_WRONG.to_string())
    );
}

#[test]
fn new_codes_retire_the_old_ones_and_need_the_password() {
    let db = fresh("renew");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let old = made.recovery_codes.clone().unwrap();
    let wrong = accounts::renew_recovery_codes(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "nope nope 1",
    );
    assert_eq!(
        refusal(wrong),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string())
    );
    let new = accounts::renew_recovery_codes(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "correct horse 1",
    )
    .unwrap();
    assert_eq!(new.len(), RECOVERY_CODE_COUNT);
    let stale = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        &old[0],
        "brand new pass 2",
        false,
    );
    assert_eq!(
        refusal(stale),
        Refusal::Unauthorized(RECOVER_WRONG.to_string())
    );
}

#[test]
fn a_new_password_ends_every_other_session_and_keeps_this_one_signed_in() {
    let db = fresh("change");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let other = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let same = accounts::change_password(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "correct horse 1",
        "correct horse 1",
    );
    assert_eq!(refusal(same), Refusal::Invalid(PASSWORD_SAME.to_string()));
    let wrong = accounts::change_password(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "nope nope 1",
        "brand new 2",
    );
    assert_eq!(
        refusal(wrong),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string())
    );
    assert!(
        accounts::signed_in(&db.path, &other.token, NOW + 1, None).is_ok(),
        "a refused change ended a session"
    );
    let token = accounts::change_password(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "correct horse 1",
        "brand new 2",
    )
    .unwrap();
    assert!(accounts::signed_in(&db.path, &token, NOW + 1, None).is_ok());
    assert!(accounts::signed_in(&db.path, &other.token, NOW + 1, None).is_err());
    let old = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    );
    assert_eq!(
        refusal(old),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
}

#[test]
fn deleting_needs_the_password_and_frees_the_name() {
    let db = fresh("delete");
    let mut entropy = Counting(0);
    let made = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    let wrong = accounts::delete_account(&db.path, at(NOW), &made.account, "nope nope 1");
    assert_eq!(
        refusal(wrong),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string())
    );
    assert!(accounts::signed_in(&db.path, &made.token, NOW + 1, None).is_ok());
    accounts::delete_account(&db.path, at(NOW), &made.account, "correct horse 1").unwrap();
    assert!(accounts::signed_in(&db.path, &made.token, NOW + 1, None).is_err());
    assert!(
        accounts::register(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana",
            "another pass 3",
            false,
            ""
        )
        .is_ok()
    );
}

#[test]
fn the_eleventh_try_on_one_name_waits_five_minutes() {
    let db = fresh("throttle");
    let mut entropy = Counting(0);
    accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    )
    .unwrap();
    for _ in 0..9 {
        let wrong = accounts::login(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana",
            "wrong horse 1",
            false,
            "",
        );
        assert_eq!(
            refusal(wrong),
            Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
        );
    }
    let blocked = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    );
    assert_eq!(
        refusal(blocked),
        Refusal::TooMany(TOO_MANY_TRIES.to_string())
    );
    let later = accounts::login(
        &db.path,
        at(NOW + 301),
        &mut entropy,
        "ana",
        "correct horse 1",
        false,
        "",
    );
    assert!(later.is_ok(), "the wait did not end after five minutes");
}
