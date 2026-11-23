//! Recovery codes and changing the password (Settings > Account), and what each does to other sessions and
//! other accounts. With accounts.rs, the Rust twins of backend/tests/test_recovery_codes_and_password_change.py.
//! accounts.rs already holds the twins of its "recovering does not reveal the name", "nine wrong codes wait",
//! "new codes retire the old ones", "a new password keeps this session", "recovering ends other sessions" and
//! "randomness that fails saves nothing" tests (a short draw cannot happen: a code's draw is eight bytes by
//! type). The signed-out answers (401 "Please sign in") go with the server in P2.

use flexweek_engine::snapshot::hash_recovery_code;
use flexweek_service::accounts::{
    self, Asker, PASSWORD_SAME, PASSWORD_WRONG, RECOVER_WRONG, SIGN_IN_WRONG, SignedIn,
};
use flexweek_service::transfer::export_account;
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::{Counting, TestDb};
use serde_json::json;

const PASSWORD_A: &str = "alice-long-password";
const PASSWORD_B: &str = "bobby-long-password";
const REPLACEMENT: &str = "replacement-pw-1";
const NOW: &str = "2026-11-05T19:00";

fn at() -> Asker<'static> {
    Asker {
        address: "127.0.0.1",
        now: 1_795_000_000,
    }
}

fn register(db: &TestDb, entropy: &mut Counting, name: &str, password: &str) -> SignedIn {
    accounts::register(&db.path, at(), entropy, name, password, false, "").unwrap()
}

fn sign_in(
    db: &TestDb,
    entropy: &mut Counting,
    name: &str,
    password: &str,
) -> Result<SignedIn, ServiceError> {
    accounts::login(&db.path, at(), entropy, name, password, false, "")
}

fn recover(
    db: &TestDb,
    entropy: &mut Counting,
    name: &str,
    code: &str,
    password: &str,
) -> Result<SignedIn, ServiceError> {
    accounts::recover(&db.path, at(), entropy, name, code, password, false)
}

fn refusal<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn wrong_code() -> Refusal {
    Refusal::Unauthorized(RECOVER_WRONG.to_string())
}

fn wrong_password() -> Refusal {
    Refusal::Unauthorized(PASSWORD_WRONG.to_string())
}

fn open(db: &TestDb, who: &SignedIn) -> bool {
    accounts::signed_in(&db.path, &who.token, at().now + 1, None).is_ok()
}

fn left(db: &TestDb, who: &SignedIn) -> i64 {
    accounts::recovery_codes_left(&db.path, who.account.id).unwrap()
}

fn stored_hashes(db: &TestDb) -> Vec<String> {
    let conn = db.sql();
    let mut stmt = conn
        .prepare("SELECT code_hash FROM recovery_codes ORDER BY code_hash")
        .unwrap();
    stmt.query_map([], |row| row.get(0))
        .unwrap()
        .collect::<Result<_, _>>()
        .unwrap()
}

/// Four groups of four lowercase hex digits joined by dashes, as the sign-up screen shows them.
fn shown_as_a_code(code: &str) -> bool {
    let groups: Vec<&str> = code.split('-').collect();
    groups.len() == 4
        && groups.iter().all(|group| {
            group.len() == 4
                && group
                    .chars()
                    .all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))
        })
}

#[test]
fn the_codes_show_as_four_groups_of_four_and_all_eight_are_left() {
    let db = TestDb::new("recovery-shown");
    let alice = register(&db, &mut Counting(0), "alice", PASSWORD_A);
    let codes = alice.recovery_codes.clone().unwrap();
    assert!(codes.iter().all(|code| shown_as_a_code(code)), "{codes:?}");
    assert_eq!(left(&db, &alice), 8);
}

#[test]
fn a_code_typed_in_capitals_without_dashes_works_for_the_name_in_capitals() {
    let db = TestDb::new("recovery-typed");
    // Counting from here draws codes with letters in them, so typing them in capitals means something.
    let mut entropy = Counting(0xabcd_ef00_0000_0000);
    let alice = register(&db, &mut entropy, "alice", PASSWORD_A);
    let code = alice.recovery_codes.clone().unwrap()[0].clone();
    assert!(code.chars().any(|c| c.is_ascii_lowercase()), "{code}");
    let typed = code.replace('-', "").to_uppercase();
    let back = recover(&db, &mut entropy, "ALICE", &typed, REPLACEMENT).unwrap();
    assert_eq!(back.account.username, "alice");
    assert!(open(&db, &back));
    assert_eq!(left(&db, &alice), 7);
    assert_eq!(
        refusal(sign_in(&db, &mut entropy, "alice", PASSWORD_A)),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
    assert_eq!(
        refusal(recover(&db, &mut entropy, "alice", &code, PASSWORD_A)),
        wrong_code()
    );
}

#[test]
fn a_wrong_password_refuses_every_password_gated_action_and_changes_nothing() {
    let db = TestDb::new("recovery-gated");
    let mut entropy = Counting(0);
    let alice = register(&db, &mut entropy, "alice", PASSWORD_A);
    let before = stored_hashes(&db);
    assert_eq!(
        refusal(accounts::renew_recovery_codes(
            &db.path,
            at(),
            &mut entropy,
            &alice.account,
            REPLACEMENT
        )),
        wrong_password()
    );
    assert_eq!(stored_hashes(&db), before);
    // A wrong current password is wrong even when the new one equals it, so "must be different" never
    // confirms a guess.
    assert_eq!(
        refusal(accounts::change_password(
            &db.path,
            at(),
            &mut entropy,
            &alice.account,
            REPLACEMENT,
            REPLACEMENT
        )),
        wrong_password()
    );
    assert!(open(&db, &alice));
    assert_eq!(
        refusal(accounts::delete_account(
            &db.path,
            at(),
            &alice.account,
            REPLACEMENT
        )),
        wrong_password()
    );
    let users: i64 = db
        .sql()
        .query_row("SELECT COUNT(*) FROM users", [], |row| row.get(0))
        .unwrap();
    assert_eq!(users, 1);
    assert_eq!(left(&db, &alice), 8);
    assert_eq!(
        refusal(export_account(
            &db.path,
            at(),
            &alice.account,
            &json!({ "password": REPLACEMENT }),
            NOW
        )),
        wrong_password()
    );
    // The old password still works, so none of the refusals changed it.
    assert!(sign_in(&db, &mut entropy, "alice", PASSWORD_A).is_ok());
}

#[test]
fn the_recovery_count_belongs_to_each_account() {
    let db = TestDb::new("recovery-count");
    let mut entropy = Counting(0);
    let alice = register(&db, &mut entropy, "alice", PASSWORD_A);
    let bob = register(&db, &mut entropy, "bob", PASSWORD_B);
    assert_eq!((left(&db, &alice), left(&db, &bob)), (8, 8));
    let code = alice.recovery_codes.clone().unwrap()[0].clone();
    recover(&db, &mut entropy, "alice", &code, REPLACEMENT).unwrap();
    assert!(!open(&db, &alice));
    assert_eq!((left(&db, &alice), left(&db, &bob)), (7, 8));
}

#[test]
fn recovering_spends_one_code_and_signs_out_only_that_account() {
    let db = TestDb::new("recovery-one-account");
    let mut entropy = Counting(0);
    let alice = register(&db, &mut entropy, "alice", PASSWORD_A);
    let codes = alice.recovery_codes.clone().unwrap();
    let bob = register(&db, &mut entropy, "bob", PASSWORD_B);
    let alice_phone = sign_in(&db, &mut entropy, "alice", PASSWORD_A).unwrap();
    // Bob holds a row with the same code hash as Alice's first code.
    db.sql()
        .execute(
            "INSERT INTO recovery_codes(user_id, code_hash) VALUES (?1, ?2)",
            rusqlite::params![bob.account.id, hash_recovery_code(&codes[0])],
        )
        .unwrap();
    let bobs_code = bob.recovery_codes.clone().unwrap()[0].clone();
    for (name, code) in [
        ("alice", "WRONG-CODE-0000"),
        ("nobody", codes[0].as_str()),
        ("alice", bobs_code.as_str()),
    ] {
        assert_eq!(
            refusal(recover(&db, &mut entropy, name, code, REPLACEMENT)),
            wrong_code(),
            "{name} {code}"
        );
    }
    let back = recover(&db, &mut entropy, "alice", &codes[0], REPLACEMENT).unwrap();
    assert_eq!(back.account, alice.account);
    assert_eq!(
        accounts::signed_in(&db.path, &back.token, at().now + 1, None).unwrap(),
        alice.account
    );
    // Alice's other sessions are gone; Bob's is not.
    assert!(!open(&db, &alice));
    assert!(!open(&db, &alice_phone));
    assert!(open(&db, &bob));
    // The code is spent for Alice, and Bob's own row with that hash is still his.
    assert_eq!((left(&db, &alice), left(&db, &bob)), (7, 9));
    assert_eq!(
        refusal(recover(&db, &mut entropy, "alice", &codes[0], REPLACEMENT)),
        wrong_code()
    );
    // Alice's password changed and Bob's did not.
    assert_eq!(
        refusal(sign_in(&db, &mut entropy, "alice", PASSWORD_A)),
        Refusal::Unauthorized(SIGN_IN_WRONG.to_string())
    );
    assert!(sign_in(&db, &mut entropy, "alice", REPLACEMENT).is_ok());
    assert!(sign_in(&db, &mut entropy, "bob", PASSWORD_B).is_ok());
    assert!(sign_in(&db, &mut entropy, "bob", REPLACEMENT).is_err());
}

#[test]
fn a_password_check_reads_the_signed_in_accounts_own_password() {
    let db = TestDb::new("recovery-own-password");
    let mut entropy = Counting(0);
    let alice = register(&db, &mut entropy, "alice", PASSWORD_A);
    let bob = register(&db, &mut entropy, "bob", PASSWORD_B);
    let first = bob.recovery_codes.clone().unwrap();
    let bob_phone = sign_in(&db, &mut entropy, "bob", PASSWORD_B).unwrap();
    // Alice's password does not open Bob's account.
    assert_eq!(
        refusal(accounts::renew_recovery_codes(
            &db.path,
            at(),
            &mut entropy,
            &bob.account,
            PASSWORD_A
        )),
        wrong_password()
    );
    let fresh =
        accounts::renew_recovery_codes(&db.path, at(), &mut entropy, &bob.account, PASSWORD_B)
            .unwrap();
    assert_eq!(fresh.len(), 8);
    assert!(fresh.iter().all(|code| !first.contains(code)));
    assert_eq!((left(&db, &bob), left(&db, &alice)), (8, 8));
    // The old codes no longer work; Alice's were not touched.
    assert_eq!(
        refusal(recover(&db, &mut entropy, "bob", &first[0], REPLACEMENT)),
        wrong_code()
    );
    let change = |entropy: &mut Counting, current: &str, new: &str| {
        accounts::change_password(&db.path, at(), entropy, &bob.account, current, new)
    };
    assert_eq!(
        refusal(change(&mut entropy, PASSWORD_A, REPLACEMENT)),
        wrong_password()
    );
    assert_eq!(
        refusal(change(&mut entropy, PASSWORD_B, PASSWORD_B)),
        Refusal::Invalid(PASSWORD_SAME.to_string())
    );
    let token = change(&mut entropy, PASSWORD_B, REPLACEMENT).unwrap();
    assert_eq!(
        accounts::signed_in(&db.path, &token, at().now + 1, None).unwrap(),
        bob.account
    );
    assert!(!open(&db, &bob_phone));
    assert!(open(&db, &alice));
    assert!(sign_in(&db, &mut entropy, "bob", PASSWORD_B).is_err());
    assert!(sign_in(&db, &mut entropy, "bob", REPLACEMENT).is_ok());
    assert!(sign_in(&db, &mut entropy, "alice", PASSWORD_A).is_ok());
}
