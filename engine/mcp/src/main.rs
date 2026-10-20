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
    now_unix: i64,
    today: String,
    started_as: Arc<Mutex<Option<i64>>>,
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
    let clock = match host::clock(launch.now_flag.as_deref()) {
        Ok(clock) => clock,
        Err(reason) => {
            host::log_line(&format!("{version} refused: {reason}"));
            std::process::exit(1);
        }
    };
    let signed_in = session::resolve(&launch.session_file, &launch.database, clock.unix);
    match &signed_in {
        Ok(_) => host::log_line(&format!("{version} session ok")),
        Err(reason) => host::log_line(&format!("{version} refused: {reason}")),
    }
    let app = App {
        data_dir: launch.data_dir,
        database: launch.database,
        session_file: launch.session_file,
        now_unix: clock.unix,
        today: clock.today,
        started_as: Arc::new(Mutex::new(signed_in.ok().map(|account| account.user_id))),
    };
    let served = app.serve(rmcp::transport::stdio()).await;
    let Ok(running) = served else {
        std::process::exit(1);
    };
    if running.waiting().await.is_err() {
        std::process::exit(1);
    }
}
