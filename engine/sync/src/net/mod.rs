//! Device-to-device transport: one permanent iroh endpoint per device, pairing by an 8-digit
//! code, and a pull-and-push exchange with a paired peer. The merge rules live in the crate root;
//! this module only moves batches and decides who may exchange them.

use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use rusqlite::Connection;

pub mod identity;
pub mod pair;
pub mod protocol;
pub mod qr;
pub mod runtime;
pub mod service;
pub mod session;

pub use pair::{PairOffer, PairStatus, PairedHost, PairedPeer};
pub use service::{SyncService, SyncStatus, SyncSummary};

use crate::SyncError;

#[derive(Debug)]
pub enum PairRefusal {
    WrongCode,
    Expired,
    Used,
    TooManyTries,
}

#[derive(Debug)]
pub enum NetError {
    /// The whole call ran out of time.
    Timeout,
    /// `cancel_sync` ended it.
    Cancelled,
    /// The other device could not be reached within the connect limit.
    Unreachable(String),
    /// The other device does not (or no longer does) list this one as paired.
    NotPaired,
    PairRefused(PairRefusal),
    /// The code or QR text is not eight digits.
    BadCode,
    /// This device already holds a different FlexWeek account.
    AlreadyLinked,
    /// The database was made by a device with another key.
    DeviceMismatch,
    Key(String),
    Protocol(String),
    Db(SyncError),
    Stopped,
}

impl NetError {
    /// A stable name for callers that map errors to their own words (UniFFI, PyO3).
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Timeout => "timeout",
            Self::Cancelled => "cancelled",
            Self::Unreachable(_) => "unreachable",
            Self::NotPaired => "not_paired",
            Self::PairRefused(PairRefusal::WrongCode) => "wrong_code",
            Self::PairRefused(PairRefusal::Expired) => "code_expired",
            Self::PairRefused(PairRefusal::Used) => "code_used",
            Self::PairRefused(PairRefusal::TooManyTries) => "too_many_tries",
            Self::BadCode => "bad_code",
            Self::AlreadyLinked => "already_linked",
            Self::DeviceMismatch => "device_mismatch",
            Self::Key(_) => "key",
            Self::Protocol(_) => "protocol",
            Self::Db(_) => "database",
            Self::Stopped => "stopped",
        }
    }
}

impl std::fmt::Display for NetError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Timeout => write!(f, "the sync took too long and was stopped"),
            Self::Cancelled => write!(f, "the sync was cancelled"),
            Self::Unreachable(why) => write!(f, "the other device could not be reached: {why}"),
            Self::NotPaired => write!(f, "this device is not paired with the other one"),
            Self::PairRefused(PairRefusal::WrongCode) => write!(f, "that code is not right"),
            Self::PairRefused(PairRefusal::Expired) => write!(f, "that code has expired"),
            Self::PairRefused(PairRefusal::Used) => write!(f, "that code was already used"),
            Self::PairRefused(PairRefusal::TooManyTries) => {
                write!(f, "too many wrong tries, start a new code")
            }
            Self::BadCode => write!(f, "a pairing code is eight digits"),
            Self::AlreadyLinked => {
                write!(
                    f,
                    "this device is already linked to another FlexWeek account"
                )
            }
            Self::DeviceMismatch => write!(f, "this database belongs to another device"),
            Self::Key(why) => write!(f, "{why}"),
            Self::Protocol(why) => write!(f, "{why}"),
            Self::Db(error) => write!(f, "{error}"),
            Self::Stopped => write!(f, "sync is stopped"),
        }
    }
}

impl std::error::Error for NetError {}

impl From<SyncError> for NetError {
    fn from(value: SyncError) -> Self {
        Self::Db(value)
    }
}

pub type NetResult<T> = Result<T, NetError>;

/// Milliseconds since the Unix epoch. The merge core never reads a clock; this is the one place
/// the transport does, and tests replace it.
pub type Clock = Arc<dyn Fn() -> i64 + Send + Sync>;

pub fn system_clock() -> Clock {
    Arc::new(|| {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| i64::try_from(d.as_millis()).unwrap_or(i64::MAX))
    })
}

#[derive(Clone, Debug)]
pub enum Transport {
    /// Direct addresses first, n0's public relays as the fallback.
    Auto,
    /// No relay and no internet lookups; peers are found from address hints (the QR code or a
    /// typed address). `bind` pins the sockets, tests use a loopback address.
    LanOnly { bind: Option<SocketAddr> },
}

#[derive(Clone)]
pub struct NodeConfig {
    pub db_path: PathBuf,
    /// Beside the database, never inside it, so a copied database does not clone a device.
    pub key_path: PathBuf,
    pub device_name: String,
    pub transport: Transport,
    pub clock: Clock,
    /// The desktop scans for edits made by other processes on this interval; the phone scans
    /// after its own writes and leaves this unset.
    pub scan_interval: Option<Duration>,
}

impl NodeConfig {
    pub fn new(db_path: &Path, key_path: &Path, device_name: &str, transport: Transport) -> Self {
        Self {
            db_path: db_path.to_owned(),
            key_path: key_path.to_owned(),
            device_name: device_name.to_owned(),
            transport,
            clock: system_clock(),
            scan_interval: None,
        }
    }

    pub(crate) fn hints_path(&self) -> PathBuf {
        self.key_path.with_file_name("peer-hints.json")
    }
}

/// Same settings as `flexweek-store`'s `open_connection`; the store is a dev-only dependency here.
pub(crate) fn open_db(path: &Path) -> NetResult<Connection> {
    let db = Connection::open(path).map_err(SyncError::from)?;
    db.busy_timeout(Duration::from_secs(10))
        .map_err(SyncError::from)?;
    db.execute("PRAGMA foreign_keys = ON", [])
        .map_err(SyncError::from)?;
    Ok(db)
}

/// Runs blocking SQLite work off the async threads.
pub(crate) async fn blocking<T, F>(work: F) -> NetResult<T>
where
    T: Send + 'static,
    F: FnOnce() -> NetResult<T> + Send + 'static,
{
    tokio::task::spawn_blocking(work)
        .await
        .map_err(|e| NetError::Protocol(format!("database task failed: {e}")))?
}
