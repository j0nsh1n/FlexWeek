//! `fwtest run` for pytest commands: `--touched` appends the selected test paths, and a failed
//! test is rerun alone (flaky.rs). Any other command runs as `contain::execute` runs it.

use std::path::{Path, PathBuf};

use crate::flaky;
use crate::select::{self, Change, Pytest};

pub fn run(command: &[String], timeout: Option<u64>, touched: Option<&Change>) -> u8 {
    if command.is_empty() {
        eprintln!("fwtest run needs a command");
        return 2;
    }
    let is_pytest = flaky::pytest_prefix(command).is_some();
    if touched.is_some() && !is_pytest {
        eprintln!(
            "--touched adds test paths to a pytest command (python -m pytest ...); this is not one"
        );
        return 2;
    }
    if !is_pytest {
        return crate::contain::execute(command, timeout);
    }
    let checkout = crate::state::git_toplevel();
    let mut argv = command.to_vec();
    let cwd = match touched {
        Some(change) => {
            let checkout = match &checkout {
                Ok(path) => path.clone(),
                Err(message) => {
                    eprintln!("{message}");
                    return 2;
                }
            };
            let plan = match select::plan(&checkout, change) {
                Ok(plan) => plan,
                Err(message) => {
                    eprintln!("{message}");
                    return 2;
                }
            };
            for path in &plan.selection.unknown {
                println!("unknown path {path}: every area");
            }
            match plan.pytest {
                Pytest::Nothing => {
                    println!("The changed paths select no pytest tests; nothing to run.");
                    return 0;
                }
                Pytest::Everything(reason) => println!("Running the whole suite: {reason}."),
                Pytest::Paths(paths) => {
                    println!("Running the tests of: {}", plan.selection.areas.join(", "));
                    argv.extend(paths);
                }
            }
            // The selected paths are relative to the checkout.
            Some(checkout)
        }
        None => None,
    };
    let Ok(checkout) = checkout else {
        // Outside a git checkout there is no root to rerun node ids from; run it as before.
        return crate::contain::execute(command, timeout);
    };
    let (junit, own_report) = match given_report(&argv) {
        Some(path) if path.is_relative() && cwd.is_some() => {
            (cwd.as_deref().unwrap_or(&checkout).join(path), None)
        }
        Some(path) => (path, None),
        None => {
            let folder = report_folder();
            if let Err(error) = std::fs::create_dir_all(&folder) {
                eprintln!("could not create the pytest report folder: {error}");
                return 1;
            }
            let junit = folder.join("pytest.xml");
            argv.extend(flaky::report_args(&junit));
            (junit, Some(folder))
        }
    };
    if own_report.is_none() {
        argv.extend(["-o".to_string(), "junit_family=xunit1".to_string()]);
    }
    let code = run_and_settle(&argv, timeout, cwd.as_deref(), &checkout, &junit);
    if let Some(folder) = own_report {
        let _ = std::fs::remove_dir_all(folder);
    }
    code
}

fn run_and_settle(
    argv: &[String],
    timeout: Option<u64>,
    cwd: Option<&Path>,
    checkout: &Path,
    junit: &Path,
) -> u8 {
    let session = match crate::contain::session() {
        Ok(session) => session,
        Err(code) => return code,
    };
    let ran = match cwd {
        Some(cwd) => session.run_in(argv, timeout, cwd),
        None => session.run(argv, timeout),
    };
    match ran {
        Ok(1) => flaky::settle(&session, checkout, argv, junit, timeout),
        Ok(code) => code,
        Err(error) => {
            eprintln!("run failed: {error}");
            1
        }
    }
}

/// The report path a command already passes with `--junitxml=PATH` or `--junitxml PATH`.
fn given_report(argv: &[String]) -> Option<PathBuf> {
    argv.iter().enumerate().find_map(|(at, arg)| {
        if let Some(path) = arg.strip_prefix("--junitxml=") {
            return Some(PathBuf::from(path));
        }
        (arg == "--junitxml")
            .then(|| argv.get(at + 1).map(PathBuf::from))
            .flatten()
    })
}

fn report_folder() -> PathBuf {
    std::env::temp_dir().join(format!(
        "fwtest-run-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    ))
}
