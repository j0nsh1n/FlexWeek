//! `flexweek-mcp`: a stdio MCP server for the account kept signed in on this computer.
//!
//! stdout is protocol only. The start line goes to stderr.

mod host;
mod session;
mod tools;

use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use rmcp::ServiceExt;

#[derive(Clone)]
struct App {
    data_dir: PathBuf,
    database: PathBuf,
    session_file: PathBuf,
    clock: host::ClockSource,
    started_as: Arc<Mutex<Option<i64>>>,
    /// `--read-only`: only the read tools are listed or served.
    read_only: bool,
    /// Explicit `--week-starts-on` override when passed; otherwise each call reads `week-start.json`.
    week_starts_on_override: Option<u32>,
}

impl App {
    /// The time for this call. A student's helper runs for days, so nothing about the time is kept.
    fn now(&self) -> Result<host::Clock, String> {
        self.clock.now()
    }

    /// The first day of the week right now (`--week-starts-on`, else `week-start.json`).
    pub(crate) fn first_weekday(&self) -> u32 {
        host::first_weekday(&self.data_dir, self.week_starts_on_override)
    }
}

#[cfg(windows)]
fn main() {
    host::log_line(&format!(
        "{} refused: {}",
        env!("CARGO_PKG_VERSION"),
        host::WINDOWS_REFUSAL
    ));
    std::process::exit(1);
}

#[cfg(unix)]
#[tokio::main]
async fn main() {
    let version = env!("CARGO_PKG_VERSION");
    let launch = match host::parse(std::env::args().skip(1)) {
        Ok(launch) => launch,
        Err(reason) => {
            host::log_line(&format!("{version} refused: {reason}"));
            std::process::exit(1);
        }
    };
    let clock = match host::source(launch.now_flag.as_deref()) {
        Ok(clock) => clock,
        Err(reason) => {
            host::log_line(&format!("{version} refused: {reason}"));
            std::process::exit(1);
        }
    };
    let started = match clock.now() {
        Ok(now) => now,
        Err(reason) => {
            host::log_line(&format!("{version} refused: {reason}"));
            std::process::exit(1);
        }
    };
    // Checked without renewing: starting the helper is not the student using FlexWeek.
    let signed_in = session::peek(&launch.session_file, &launch.database, started.unix);
    match &signed_in {
        Ok(_) => host::log_line(&format!("{version} session ok")),
        Err(reason) => host::log_line(&format!("{version} refused: {reason}")),
    }
    let app = App {
        data_dir: launch.data_dir,
        database: launch.database,
        session_file: launch.session_file,
        clock,
        started_as: Arc::new(Mutex::new(signed_in.ok().map(|account| account.user_id))),
        read_only: launch.read_only,
        week_starts_on_override: launch.week_starts_on_override,
    };
    let served = app.serve(rmcp::transport::stdio()).await;
    let Ok(running) = served else {
        std::process::exit(1);
    };
    if running.waiting().await.is_err() {
        std::process::exit(1);
    }
}
