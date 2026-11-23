//! The account rules, from what a student is promised: a new account gets eight one-time codes, a
//! wrong password or code never says which part was wrong, a new password ends every other session,
//! too many tries wait five minutes, and a deleted account frees its name.

use std::path::PathBuf;

use flexweek_service::accounts::{
    self, ACCOUNT_CHANGED, Account, Asker, Entropy, INVALID_INPUT, PASSWORD_SAME, PASSWORD_WRONG,
    PLEASE_SIGN_IN, RECOVER_WRONG, RECOVERY_CODE_COUNT, SESSION_ENDED, SIGN_IN_WRONG,
    TOO_MANY_TRIES, USERNAME_TAKEN,
};
use flexweek_service::{Refusal, ServiceError, ServiceResult, with_db};
use flexweek_testkit::Counting;

const NOW: i64 = 1_793_000_000;

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
    let users: i64 = with_db(&db.path, |conn| {
        Ok(conn
            .query_row("SELECT count(*) FROM users", [], |row| row.get(0))
            .unwrap())
    })
    .unwrap();
    assert_eq!(users, 1, "a second account was made");
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
        "brand new word 2",
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
        "nope nope nope 1",
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
        "nope nope nope 1",
        "brand new word 2",
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
        "brand new word 2",
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
    let wrong = accounts::delete_account(&db.path, at(NOW), &made.account, "nope nope nope 1");
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

const PW: &str = "correct horse 1";

fn ana(db: &Db, entropy: &mut Counting) -> accounts::SignedIn {
    accounts::register(&db.path, at(NOW), entropy, "ana", PW, false, "").unwrap()
}

#[test]
fn a_name_is_the_same_in_any_case_and_bad_input_is_refused_before_anything_runs() {
    let db = fresh("input");
    let mut entropy = Counting(0);
    let made = accounts::register(&db.path, at(NOW), &mut entropy, "Ana_1", PW, false, "").unwrap();
    assert_eq!(made.account.username, "ana_1");
    let taken = accounts::register(&db.path, at(NOW), &mut entropy, "ANA_1", PW, false, "");
    assert_eq!(
        refusal(taken),
        Refusal::Conflict(USERNAME_TAKEN.to_string())
    );
    let signed = accounts::login(&db.path, at(NOW), &mut entropy, "aNa_1", PW, false, "").unwrap();
    assert_eq!(signed.account.username, "ana_1");
    let invalid = Refusal::Invalid(INVALID_INPUT.to_string());
    for (name, password) in [
        ("ab", PW),
        ("a-b-c", PW),
        (&"x".repeat(33) as &str, PW),
        ("ana_1", "short pass1"),
    ] {
        let refused = accounts::login(&db.path, at(NOW), &mut entropy, name, password, false, "");
        assert_eq!(refusal(refused), invalid, "{name:?} {password:?}");
    }
    for code in ["1234567", &"c".repeat(65) as &str] {
        let refused = accounts::recover(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana_1",
            code,
            "brand new pass 2",
            false,
        );
        assert_eq!(refusal(refused), invalid, "{code:?}");
    }
    let long = "p".repeat(129);
    let refused = accounts::register(&db.path, at(NOW), &mut entropy, "bob", &long, false, "");
    assert_eq!(refusal(refused), invalid);
    // Refused input never reached the throttle: the three real tries above and seven more make ten,
    // and only the eleventh waits.
    for _ in 0..7 {
        accounts::login(&db.path, at(NOW), &mut entropy, "ana_1", PW, false, "").unwrap();
    }
    let eleventh = accounts::login(&db.path, at(NOW), &mut entropy, "ana_1", PW, false, "");
    assert_eq!(
        refusal(eleventh),
        Refusal::TooMany(TOO_MANY_TRIES.to_string())
    );
}

#[test]
fn a_taken_name_keeps_its_first_password() {
    let db = fresh("taken-keeps");
    let mut entropy = Counting(0);
    ana(&db, &mut entropy);
    let _ = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "other password 2",
        false,
        "",
    );
    assert!(accounts::login(&db.path, at(NOW), &mut entropy, "ana", PW, false, "").is_ok());
    let other = accounts::login(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "other password 2",
        false,
        "",
    );
    assert_eq!(
        refusal(other),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
}

#[test]
fn signing_up_gives_the_account_its_preferences_and_ends_the_windows_old_session() {
    let db = fresh("signup-prefs");
    let mut entropy = Counting(0);
    let first = ana(&db, &mut entropy);
    let second = accounts::register(
        &db.path,
        at(NOW),
        &mut entropy,
        "bob",
        PW,
        false,
        &first.token,
    )
    .unwrap();
    let prefs = with_db(&db.path, |conn| {
        Ok(flexweek_store::preference_row(conn, second.account.id)?)
    })
    .unwrap();
    assert!(prefs.is_some(), "a new account has no preferences");
    let old = accounts::signed_in(&db.path, &first.token, NOW + 1, None);
    assert_eq!(
        refusal(old),
        Refusal::Unauthorized(PLEASE_SIGN_IN.to_string())
    );
}

#[test]
fn signing_out_from_a_window_of_another_account_leaves_this_session_alone() {
    let db = fresh("logout");
    let mut entropy = Counting(0);
    let made = ana(&db, &mut entropy);
    let refused = accounts::logout(&db.path, &made.token, NOW + 1, Some("999"));
    assert_eq!(
        refusal(refused),
        Refusal::Unauthorized(ACCOUNT_CHANGED.to_string())
    );
    assert!(accounts::signed_in(&db.path, &made.token, NOW + 1, None).is_ok());
    let own = made.account.id.to_string();
    accounts::logout(&db.path, &made.token, NOW + 1, Some(&own)).unwrap();
    assert!(accounts::signed_in(&db.path, &made.token, NOW + 1, None).is_err());
    let again = ana_login(&db, &mut entropy);
    accounts::logout(&db.path, &again, NOW + 1, None).unwrap();
    assert!(accounts::signed_in(&db.path, &again, NOW + 1, None).is_err());
}

fn ana_login(db: &Db, entropy: &mut Counting) -> String {
    accounts::login(&db.path, at(NOW), entropy, "ana", PW, false, "")
        .unwrap()
        .token
}

#[test]
fn the_padding_code_never_opens_an_account_with_fewer_than_eight_codes() {
    let db = fresh("padding");
    let mut entropy = Counting(0);
    let made = ana(&db, &mut entropy);
    let code = made.recovery_codes.unwrap()[0].clone();
    accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        &code,
        "brand new pass 2",
        false,
    )
    .unwrap();
    let padding = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "missing-recovery-code",
        "third pass word 3",
        false,
    );
    assert_eq!(
        refusal(padding),
        Refusal::Unauthorized(RECOVER_WRONG.to_string())
    );
}

#[test]
fn a_wrong_current_password_is_wrong_even_when_it_equals_the_new_one() {
    let db = fresh("same-wrong");
    let mut entropy = Counting(0);
    let made = ana(&db, &mut entropy);
    let refused = accounts::change_password(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "brand new word 2",
        "brand new word 2",
    );
    assert_eq!(
        refusal(refused),
        Refusal::Unauthorized(PASSWORD_WRONG.to_string())
    );
}

#[test]
fn renewed_codes_work_and_a_refused_renewal_keeps_the_old_ones() {
    let db = fresh("renew-works");
    let mut entropy = Counting(0);
    let made = ana(&db, &mut entropy);
    let old = made.recovery_codes.clone().unwrap();
    let _ = accounts::renew_recovery_codes(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "nope nope nope 1",
    );
    assert_eq!(
        accounts::recovery_codes_left(&db.path, made.account.id).unwrap(),
        8
    );
    accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        &old[1],
        "brand new pass 2",
        false,
    )
    .unwrap();
    let new = accounts::renew_recovery_codes(
        &db.path,
        at(NOW),
        &mut entropy,
        &made.account,
        "brand new pass 2",
    )
    .unwrap();
    assert!(
        accounts::recover(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana",
            &new[5],
            "third pass word 3",
            false
        )
        .is_ok()
    );
}

#[test]
fn a_kept_session_lasts_thirty_days_and_an_unkept_one_seven() {
    let db = fresh("keep");
    let mut entropy = Counting(0);
    ana(&db, &mut entropy);
    let kept = accounts::login(&db.path, at(NOW), &mut entropy, "ana", PW, true, "").unwrap();
    let plain = accounts::login(&db.path, at(NOW), &mut entropy, "ana", PW, false, "").unwrap();
    let day = 24 * 60 * 60;
    assert!(accounts::signed_in(&db.path, &kept.token, NOW + 29 * day, None).is_ok());
    assert!(accounts::signed_in(&db.path, &plain.token, NOW + 8 * day, None).is_err());
}

#[test]
fn wrong_recovery_codes_also_wait_five_minutes() {
    let db = fresh("throttle-recover");
    let mut entropy = Counting(0);
    ana(&db, &mut entropy);
    for _ in 0..9 {
        let wrong = accounts::recover(
            &db.path,
            at(NOW),
            &mut entropy,
            "ana",
            "0000-0000-0000-0000",
            "brand new pass 2",
            false,
        );
        assert_eq!(
            refusal(wrong),
            Refusal::Unauthorized(RECOVER_WRONG.to_string())
        );
    }
    let blocked = accounts::recover(
        &db.path,
        at(NOW),
        &mut entropy,
        "ana",
        "0000-0000-0000-0000",
        "brand new pass 2",
        false,
    );
    assert_eq!(
        refusal(blocked),
        Refusal::TooMany(TOO_MANY_TRIES.to_string())
    );
}

#[test]
fn a_failed_piece_of_work_leaves_nothing_it_wrote() {
    let db = fresh("rollback");
    let failed: Result<(), ServiceError> = with_db(&db.path, |conn| {
        flexweek_store::begin_immediate(conn)?;
        flexweek_store::insert_user(conn, "ghost", "hash")?;
        Err(Refusal::Conflict("stop".to_string()).into())
    });
    assert!(failed.is_err());
    let found = with_db(&db.path, |conn| {
        Ok(flexweek_store::find_user(conn, "ghost")?)
    })
    .unwrap();
    assert!(found.is_none(), "a refused piece of work kept its insert");
}

#[test]
fn the_password_gated_actions_wait_five_minutes_after_ten_tries() {
    for action in ["renew", "change", "delete"] {
        let db = fresh(&format!("throttle-{action}"));
        let mut entropy = Counting(0);
        let made = ana(&db, &mut entropy);
        let mut last = None;
        for _ in 0..10 {
            let tried = match action {
                "renew" => accounts::renew_recovery_codes(
                    &db.path,
                    at(NOW),
                    &mut entropy,
                    &made.account,
                    "nope nope nope 1",
                )
                .map(|_| ()),
                "change" => accounts::change_password(
                    &db.path,
                    at(NOW),
                    &mut entropy,
                    &made.account,
                    "nope nope nope 1",
                    "brand new word 2",
                )
                .map(|_| ()),
                _ => accounts::delete_account(&db.path, at(NOW), &made.account, "nope nope nope 1"),
            };
            last = Some(refusal(tried));
        }
        // Sign-up was the first try; the tenth here is the eleventh on this name.
        assert_eq!(
            last,
            Some(Refusal::TooMany(TOO_MANY_TRIES.to_string())),
            "{action}"
        );
    }
}

#[test]
fn a_sign_up_that_fails_part_way_leaves_no_account() {
    // The database refuses the recovery codes: nothing of the account may stay, and the student is told
    // the name is unavailable, as the route always said for a refused write during sign-up.
    let db = fresh("part-way");
    let mut entropy = Counting(0);
    with_db(&db.path, |conn| {
        conn.execute_batch(
            "CREATE TRIGGER refuse_codes BEFORE INSERT ON recovery_codes
             BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END",
        )
        .map_err(flexweek_store::StoreError::Sqlite)?;
        Ok(())
    })
    .unwrap();
    let failed = accounts::register(&db.path, at(NOW), &mut entropy, "ana", PW, false, "");
    assert_eq!(
        refusal(failed),
        Refusal::Conflict(USERNAME_TAKEN.to_string())
    );
    let left = with_db(&db.path, |conn| {
        let count = |table: &str| -> rusqlite::Result<i64> {
            conn.query_row(&format!("SELECT count(*) FROM {table}"), [], |row| {
                row.get(0)
            })
        };
        Ok((count("users"), count("preferences"), count("sessions")))
    })
    .unwrap();
    assert_eq!(
        (left.0.unwrap(), left.1.unwrap(), left.2.unwrap()),
        (0, 0, 0),
        "a half-made account was left behind"
    );
}

/// A source of randomness that breaks at one of its three draws.
struct Breaks(&'static str, Counting);

impl Entropy for Breaks {
    fn session_token(&mut self) -> ServiceResult<String> {
        if self.0 == "token" {
            return Err(ServiceError::Broken("no token".into()));
        }
        self.1.session_token()
    }
    fn salt(&mut self) -> ServiceResult<String> {
        if self.0 == "salt" {
            return Err(ServiceError::Broken("no salt".into()));
        }
        self.1.salt()
    }
    fn code_bytes(&mut self) -> ServiceResult<[u8; 8]> {
        if self.0 == "code" {
            return Err(ServiceError::Broken("no code".into()));
        }
        self.1.code_bytes()
    }
}

#[test]
fn a_sign_up_whose_randomness_fails_makes_no_account() {
    for part in ["token", "salt", "code"] {
        let db = fresh(&format!("breaks-{part}"));
        let made = accounts::register(
            &db.path,
            at(NOW),
            &mut Breaks(part, Counting(0)),
            "ana",
            "correct horse 1",
            false,
            "",
        );
        assert!(
            matches!(made, Err(ServiceError::Broken(_))),
            "{part}: {made:?}"
        );
        let accounts: i64 = with_db(&db.path, |conn| {
            Ok(conn
                .query_row("SELECT count(*) FROM users", [], |row| row.get(0))
                .unwrap())
        })
        .unwrap();
        assert_eq!(accounts, 0, "{part}: an account was saved");
        for table in ["preferences", "recovery_codes", "sessions"] {
            let rows: i64 = with_db(&db.path, |conn| {
                Ok(conn
                    .query_row(&format!("SELECT count(*) FROM {table}"), [], |row| {
                        row.get(0)
                    })
                    .unwrap())
            })
            .unwrap();
            assert_eq!(rows, 0, "{part}: {table} kept a row");
        }
    }
}
