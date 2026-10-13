//! Scan-based, record-level merging for a local FlexWeek account.

use rusqlite::Connection;
use serde_json::Value;

mod apply;
mod clock;
pub mod net;
mod peers;
mod records;
mod scan;
mod schema;

pub use apply::apply_batch;
pub use clock::{next_hlc, observe};
pub use peers::{Peer, acknowledge_pull, acknowledge_push, list_peers, revoke_peer, upsert_peer};
pub use records::{Record, export_since};
pub use scan::scan;
pub use schema::{migrate, set_account, set_device};

#[derive(Debug)]
pub enum SyncError {
    Sqlite(rusqlite::Error),
    Json(serde_json::Error),
    Invalid(String),
}

impl std::fmt::Display for SyncError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Sqlite(error) => write!(f, "{error}"),
            Self::Json(error) => write!(f, "{error}"),
            Self::Invalid(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for SyncError {}
impl From<rusqlite::Error> for SyncError {
    fn from(value: rusqlite::Error) -> Self {
        Self::Sqlite(value)
    }
}
impl From<serde_json::Error> for SyncError {
    fn from(value: serde_json::Error) -> Self {
        Self::Json(value)
    }
}
pub type SyncResult<T> = Result<T, SyncError>;

/// `seq` is local to the sender and is a cursor, never part of the LWW stamp.
#[derive(Clone, Debug, PartialEq)]
pub struct Batch {
    pub account_uuid: String,
    pub from_device: String,
    pub records: Vec<Record>,
    pub next_since: i64,
    pub more: bool,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ApplyReport {
    pub applied: usize,
    pub skipped: usize,
    pub quarantined: usize,
    pub user_id: Option<i64>,
}

pub fn account_uuid(conn: &Connection, user_id: i64) -> SyncResult<String> {
    Ok(conn.query_row(
        "SELECT account_uuid FROM sync_account WHERE user_id = ?1",
        [user_id],
        |row| row.get(0),
    )?)
}

pub(crate) fn canonical(value: &Value) -> String {
    flexweek_engine::snapshot::canonical(value)
}

pub(crate) fn digest(value: &Value) -> String {
    use sha2::{Digest, Sha256};
    hex::encode(Sha256::digest(canonical(value).as_bytes()))
}
