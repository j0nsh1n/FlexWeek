//! Test support for the desktop crates: seeded accounts and weeks, a clock the test moves by hand, a fake
//! platform, and the driver that steps the app the way a student would (2.0.0 plan, phase P3). Used only by
//! tests. So far: a throwaway database with accounts in it, and randomness a test can predict.

use std::path::PathBuf;

use flexweek_service::accounts::Entropy;
use flexweek_service::{ServiceResult, with_db};
use serde_json::{Map, Value};

/// Counts up, so every token, salt and recovery code is new and a test can predict them.
pub struct Counting(pub u64);

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

/// A database file in its own folder under the system's temporary folder, removed when dropped. The
/// folder's name holds the test's name and the process id, so tests running at once never share one.
pub struct TestDb {
    dir: PathBuf,
    pub path: PathBuf,
}

impl Drop for TestDb {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

impl TestDb {
    /// The folder and the file's path, with nothing made yet (for a test that builds an old database).
    pub fn empty(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("flexweek-test-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("test folder");
        let path = dir.join("flexweek.db");
        Self { dir, path }
    }

    /// A database made as the app makes it on first start.
    pub fn new(name: &str) -> Self {
        let db = Self::empty(name);
        flexweek_store::initialize(&db.path, "2026-11-16").expect("initialize");
        db
    }

    /// An account as sign-up leaves it (its preferences row at today's version), without a password
    /// check or a session; its id.
    pub fn account(&self, name: &str) -> i64 {
        with_db(&self.path, |conn| {
            let user = flexweek_store::insert_user(conn, name, "hash")?;
            flexweek_store::insert_preferences(conn, user, flexweek_store::PREFS_VERSION)?;
            Ok(user)
        })
        .expect("account")
    }

    /// A plain connection, for reading or planting rows the way another program would.
    pub fn sql(&self) -> rusqlite::Connection {
        rusqlite::Connection::open(&self.path).expect("open")
    }
}

/// `base` with the fields of `changes` put over it, keeping `base`'s order.
pub fn merged(base: Value, changes: Value) -> Value {
    let mut out: Map<String, Value> = base.as_object().cloned().unwrap_or_default();
    if let Value::Object(fields) = changes {
        out.extend(fields);
    }
    Value::Object(out)
}
