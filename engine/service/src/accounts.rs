//! Accounts: sign up, sign in and out, the signed-in check, recovery codes, a new password and
//! deleting the account. These are `backend/app.py`'s auth routes without HTTP: the caller passes the
//! time, the address the request came from and the randomness, and turns a refusal into its answer.

use std::collections::BTreeSet;
use std::path::Path;

use flexweek_engine::snapshot::{accept_recovery_draw, hash_recovery_code, recovery_code_matches};
use flexweek_store::{self as store, Connection, StoreError};

use crate::{Refusal, ServiceResult, with_db};

pub const RECOVERY_CODE_COUNT: usize = 8;
pub const TOO_MANY_TRIES: &str = "Too many tries. Wait 5 minutes, then try again.";
pub const SIGN_IN_WRONG: &str = "Incorrect username or password";
pub const RECOVER_WRONG: &str = "Incorrect username or recovery code";
pub const PASSWORD_WRONG: &str = "Incorrect password";
pub const PASSWORD_SAME: &str = "New password must be different";
pub const USERNAME_TAKEN: &str = "Username unavailable";
pub const SESSION_ENDED: &str = "Your session ended. Sign in again.";
pub const PLEASE_SIGN_IN: &str = "Please sign in";
pub const ACCOUNT_CHANGED: &str = "Account changed. Please sign in again.";

/// The randomness an account change needs. The caller supplies it, so tests can fix it.
pub trait Entropy {
    /// A new session token: 32 random bytes as URL-safe base64 without padding.
    fn session_token(&mut self) -> String;
    /// A password salt: 16 random bytes as 32 lowercase hex digits.
    fn salt(&mut self) -> String;
    /// Eight random bytes for one recovery code.
    fn code_bytes(&mut self) -> Vec<u8>;
}

/// Where a request came from and when, for the throttle and the session.
#[derive(Clone, Copy, Debug)]
pub struct Asker<'a> {
    pub address: &'a str,
    pub now: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Account {
    pub id: i64,
    pub username: String,
}

/// A new session. `recovery_codes` is set only for a new account.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedIn {
    pub account: Account,
    pub token: String,
    pub keep: bool,
    pub recovery_codes: Option<Vec<String>>,
}

fn throttled(path: &Path, asker: Asker<'_>, username: &str) -> ServiceResult<()> {
    if store::throttle(path, asker.address, username, asker.now)? {
        Ok(())
    } else {
        Err(Refusal::TooMany(TOO_MANY_TRIES.to_string()).into())
    }
}

fn open_session(
    conn: &Connection,
    entropy: &mut dyn Entropy,
    user_id: i64,
    now: i64,
    keep: bool,
) -> ServiceResult<String> {
    let token = entropy.session_token();
    store::open_session(conn, &token, user_id, now, keep)?;
    Ok(token)
}

pub fn generate_recovery_codes(entropy: &mut dyn Entropy) -> Vec<String> {
    let mut seen = BTreeSet::new();
    let mut codes = Vec::with_capacity(RECOVERY_CODE_COUNT);
    while codes.len() < RECOVERY_CODE_COUNT {
        if let Some(code) = accept_recovery_draw(&entropy.code_bytes(), &mut seen) {
            codes.push(code);
        }
    }
    codes
}

fn store_recovery_codes(conn: &Connection, user_id: i64, codes: &[String]) -> ServiceResult<()> {
    let hashes: Vec<String> = codes.iter().map(|code| hash_recovery_code(code)).collect();
    store::replace_recovery_codes(conn, user_id, &hashes)?;
    Ok(())
}

fn is_unique_violation(error: &StoreError) -> bool {
    matches!(
        error,
        StoreError::Sqlite(rusqlite::Error::SqliteFailure(failure, _))
            if failure.code == rusqlite::ErrorCode::ConstraintViolation
    )
}

/// A new account with its preferences, eight recovery codes and a session.
pub fn register(
    path: &Path,
    asker: Asker<'_>,
    entropy: &mut dyn Entropy,
    username: &str,
    password: &str,
    keep: bool,
    previous_token: &str,
) -> ServiceResult<SignedIn> {
    throttled(path, asker, username)?;
    let encoded = store::password_hash(password, &entropy.salt())?;
    let codes = generate_recovery_codes(entropy);
    let created = with_db(path, |conn| {
        let user_id = match store::insert_user(conn, username, &encoded) {
            Ok(id) => id,
            Err(error) if is_unique_violation(&error) => {
                return Err(Refusal::Conflict(USERNAME_TAKEN.to_string()).into());
            }
            Err(error) => return Err(error.into()),
        };
        store::insert_preferences(conn, user_id, store::PREFS_VERSION)?;
        store_recovery_codes(conn, user_id, &codes)?;
        let token = open_session(conn, entropy, user_id, asker.now, keep)?;
        Ok((user_id, token))
    })?;
    end_previous_session(path, previous_token)?;
    Ok(SignedIn {
        account: Account {
            id: created.0,
            username: username.to_string(),
        },
        token: created.1,
        keep,
        recovery_codes: Some(codes),
    })
}

/// Sign in. An unknown name still runs the password check, so the answer takes as long either way.
pub fn login(
    path: &Path,
    asker: Asker<'_>,
    entropy: &mut dyn Entropy,
    username: &str,
    password: &str,
    keep: bool,
    previous_token: &str,
) -> ServiceResult<SignedIn> {
    throttled(path, asker, username)?;
    let found = with_db(path, |conn| Ok(store::find_user(conn, username)?))?;
    let encoded = match &found {
        Some((_, _, hash)) => hash.clone(),
        None => store::password_hash("missing-account-password", &"00".repeat(16))?,
    };
    let matched = store::password_matches_index(password, &encoded)?;
    let Some((user_id, _, _)) = found.filter(|_| matched) else {
        return Err(Refusal::Unauthorized(SIGN_IN_WRONG.to_string()).into());
    };
    let token = with_db(path, |conn| {
        // The hash was checked outside the lock; a recovery or new password may have replaced it and
        // signed every session out meanwhile, so the session opens only if it is still the account's.
        store::begin_immediate(conn)?;
        if store::password_hash_of(conn, user_id)?.as_deref() != Some(encoded.as_str()) {
            return Err(Refusal::Unauthorized(SIGN_IN_WRONG.to_string()).into());
        }
        open_session(conn, entropy, user_id, asker.now, keep)
    })?;
    end_previous_session(path, previous_token)?;
    Ok(SignedIn {
        account: Account {
            id: user_id,
            username: username.to_string(),
        },
        token,
        keep,
        recovery_codes: None,
    })
}

fn end_previous_session(path: &Path, previous_token: &str) -> ServiceResult<()> {
    with_db(path, |conn| {
        Ok(store::delete_session(conn, &store::digest(previous_token))?)
    })
}

/// The account a session token belongs to. `expected_id` is the account the caller last saw signed
/// in, when it said; a different one is refused so a window never writes into another account.
pub fn signed_in(
    path: &Path,
    token: &str,
    now: i64,
    expected_id: Option<&str>,
) -> ServiceResult<Account> {
    let token_hash = store::digest(token);
    let (found, ended) = with_db(path, |conn| {
        let found = store::session_user(conn, &token_hash, now)?;
        let ended = found.is_none() && store::session_expired(conn, &token_hash, now)?;
        Ok((found, ended))
    })?;
    let Some((id, username)) = found else {
        let words = if ended { SESSION_ENDED } else { PLEASE_SIGN_IN };
        return Err(Refusal::Unauthorized(words.to_string()).into());
    };
    if expected_id.is_some_and(|expected| expected != id.to_string()) {
        return Err(Refusal::Unauthorized(ACCOUNT_CHANGED.to_string()).into());
    }
    Ok(Account { id, username })
}

pub fn logout(path: &Path, token: &str) -> ServiceResult<()> {
    end_previous_session(path, token)
}

/// Inside the caller's transaction, so a password changed by another session between the check and
/// the write cannot still allow the write.
fn require_password(conn: &Connection, user_id: i64, password: &str) -> ServiceResult<()> {
    let stored = store::password_hash_of(conn, user_id)?;
    match stored {
        Some(stored) if store::password_matches_index(password, &stored)? => Ok(()),
        _ => Err(Refusal::Unauthorized(PASSWORD_WRONG.to_string()).into()),
    }
}

/// A new password from a recovery code, which is used up. Every code is compared, also when the
/// name is unknown, so the answer does not say which part was wrong.
pub fn recover(
    path: &Path,
    asker: Asker<'_>,
    entropy: &mut dyn Entropy,
    username: &str,
    code: &str,
    new_password: &str,
    keep: bool,
) -> ServiceResult<SignedIn> {
    throttled(path, asker, username)?;
    let dummy = hash_recovery_code("missing-recovery-code");
    let new_hash = store::password_hash(new_password, &entropy.salt())?;
    let (account, token) = with_db(path, |conn| {
        store::begin_immediate(conn)?;
        let found = store::find_user(conn, username)?;
        let hashes = match &found {
            Some((id, _, _)) => store::recovery_hashes(conn, *id)?,
            None => Vec::new(),
        };
        let mut padded = hashes.clone();
        while padded.len() < RECOVERY_CODE_COUNT {
            padded.push(dummy.clone());
        }
        let mut matched = None;
        for stored in &padded {
            if recovery_code_matches(code, stored)? {
                matched = Some(stored.clone());
            }
        }
        let (Some((user_id, name, _)), Some(matched)) = (found, matched) else {
            return Err(Refusal::Unauthorized(RECOVER_WRONG.to_string()).into());
        };
        if !hashes.contains(&matched) {
            return Err(Refusal::Unauthorized(RECOVER_WRONG.to_string()).into());
        }
        store::use_recovery_code(conn, user_id, &matched)?;
        store::rotate_password(conn, user_id, &new_hash)?;
        let token = open_session(conn, entropy, user_id, asker.now, keep)?;
        Ok((
            Account {
                id: user_id,
                username: name,
            },
            token,
        ))
    })?;
    Ok(SignedIn {
        account,
        token,
        keep,
        recovery_codes: None,
    })
}

pub fn recovery_codes_left(path: &Path, user_id: i64) -> ServiceResult<i64> {
    with_db(path, |conn| Ok(store::count_recovery_codes(conn, user_id)?))
}

/// Eight new recovery codes in place of the old ones, after the password.
pub fn renew_recovery_codes(
    path: &Path,
    asker: Asker<'_>,
    entropy: &mut dyn Entropy,
    account: &Account,
    password: &str,
) -> ServiceResult<Vec<String>> {
    throttled(path, asker, &account.username)?;
    let codes = generate_recovery_codes(entropy);
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        require_password(conn, account.id, password)?;
        store_recovery_codes(conn, account.id, &codes)
    })?;
    Ok(codes)
}

/// A new password. Every other session ends (the store's rotate does it); this one gets a new token.
pub fn change_password(
    path: &Path,
    asker: Asker<'_>,
    entropy: &mut dyn Entropy,
    account: &Account,
    current: &str,
    new: &str,
) -> ServiceResult<String> {
    throttled(path, asker, &account.username)?;
    let new_hash = store::password_hash(new, &entropy.salt())?;
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        require_password(conn, account.id, current)?;
        if new == current {
            return Err(Refusal::Invalid(PASSWORD_SAME.to_string()).into());
        }
        store::rotate_password(conn, account.id, &new_hash)?;
        open_session(conn, entropy, account.id, asker.now, false)
    })
}

/// Deletes the account and everything in it, after the password.
pub fn delete_account(
    path: &Path,
    asker: Asker<'_>,
    account: &Account,
    password: &str,
) -> ServiceResult<()> {
    throttled(path, asker, &account.username)?;
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        require_password(conn, account.id, password)?;
        Ok(store::delete_account(conn, account.id)?)
    })
}
