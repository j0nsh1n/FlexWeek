//! The account and save rules the local FastAPI server holds today (`backend/app.py`'s helpers, request
//! checks and route bodies), as plain Rust calls with no HTTP: sign up and in, weeks, homework and plans,
//! preferences, routines, restore points, export and import. It calls `flexweek-store` and
//! `flexweek-engine`; the time and randomness come in as arguments (2.0.0 plan, phase P1).

use std::path::Path;

use flexweek_store::{Connection, StoreError};

pub mod accounts;
pub mod blocks;
pub mod changes;
pub mod comfort;
pub mod homework_saves;
pub mod plans;
pub mod preferences;
pub mod records;
pub mod views;
pub mod week_saves;
pub mod weeks;

/// A refusal the student is told about, with the words they see. The caller turns its kind into an
/// answer: `Invalid` 422, `Unauthorized` 401, `NotFound` 404, `Conflict` 409, `TooMany` 429 (retry
/// after 300 s).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Refusal {
    Invalid(String),
    Unauthorized(String),
    NotFound(String),
    Conflict(String),
    TooMany(String),
}

impl Refusal {
    pub fn words(&self) -> &str {
        match self {
            Self::Invalid(words)
            | Self::Unauthorized(words)
            | Self::NotFound(words)
            | Self::Conflict(words)
            | Self::TooMany(words) => words,
        }
    }
}

#[derive(Debug)]
pub enum ServiceError {
    Refused(Refusal),
    /// The store failed; the caller answers as it does for any storage error.
    Store(StoreError),
    /// Stored data the rules no longer accept (Python answers these with a server error).
    Broken(String),
}

pub type ServiceResult<T> = Result<T, ServiceError>;

impl From<Refusal> for ServiceError {
    fn from(refusal: Refusal) -> Self {
        Self::Refused(refusal)
    }
}

impl From<StoreError> for ServiceError {
    fn from(error: StoreError) -> Self {
        Self::Store(error)
    }
}

impl From<flexweek_engine::EngineError> for ServiceError {
    fn from(error: flexweek_engine::EngineError) -> Self {
        Self::Store(StoreError::Engine(error))
    }
}

/// One connection for one piece of work, as `backend/storage.py`'s `connect` gives the routes: what
/// `work` wrote is committed when it succeeds and rolled back when it fails.
pub fn with_db<T>(
    path: &Path,
    work: impl FnOnce(&Connection) -> ServiceResult<T>,
) -> ServiceResult<T> {
    let conn = flexweek_store::open_connection(path)?;
    let outcome = work(&conn);
    if conn.is_autocommit() {
        return outcome;
    }
    match outcome {
        Ok(value) => {
            conn.execute("COMMIT", []).map_err(StoreError::Sqlite)?;
            Ok(value)
        }
        Err(error) => {
            let _ = conn.execute("ROLLBACK", []);
            Err(error)
        }
    }
}
