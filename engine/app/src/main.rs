//! The 2.0.0-shaped program for the upgrade test (2.0.0 plan, upgrade.md section 5): packaged as 2.0.0
//! will be, it opens no window yet. `--upgrade-check FILE` writes what it finds of a 1.x install to FILE;
//! `--smoke-test FILE` writes that it started.

use std::process::ExitCode;

use flexweek_platform::{clock, folders};

const USAGE: &str = "FlexWeek 2.0.0 preview: use --upgrade-check FILE or --smoke-test FILE";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (flag, file) = match args.as_slice() {
        [flag, file] => (flag.as_str(), file),
        _ => {
            eprintln!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    let body = match flag {
        "--upgrade-check" => flexweek_app::upgrade::report(
            &folders::default_data_dir(),
            &folders::config_dir(),
            clock::unix_seconds(),
        ),
        "--smoke-test" => serde_json::json!({ "ok": true }),
        _ => {
            eprintln!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    match std::fs::write(file, format!("{body}\n")) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("could not write {file}: {error}");
            ExitCode::FAILURE
        }
    }
}
