//! `fwtest gate` runs the same checks as `scripts/verify.py`, in the same order.
//!
//! The success line is the one `verify.py` prints, including the backend-only
//! wording. Each step is one contained command. The per-step limit is 2400
//! seconds unless `FWTEST_STEP_TIMEOUT_SECS` is set (tests use a few seconds).
//!
//! `--touched` runs the same steps on what the changed paths select (select.rs): pytest on the
//! selected paths, then `cargo test` on the selected packages. A failed test is rerun alone
//! once (flaky.rs).

use std::path::Path;
use std::process::Command;

use crate::contain::{self, half_cpus};
use crate::select::{self, Change, Plan, Pytest};

/// What the gate covers.
pub enum Scope {
    Full,
    BackendOnly,
    Touched(Box<Plan>),
}

impl Scope {
    fn needs_desktop(&self) -> bool {
        match self {
            Self::Full => true,
            Self::BackendOnly => false,
            Self::Touched(plan) => match &plan.pytest {
                Pytest::Nothing => false,
                Pytest::Everything(_) => true,
                Pytest::Paths(paths) => paths.iter().any(|path| !path.starts_with("backend/")),
            },
        }
    }

    fn runs_pytest(&self) -> bool {
        !matches!(self, Self::Touched(plan) if plan.pytest == Pytest::Nothing)
    }
}

const VERIFIED_TAIL: &str = "Packaged binaries and other platforms need separate checks.";

pub fn verified_line(backend_only: bool) -> String {
    let scope = if backend_only {
        "Backend only; desktop NOT VERIFIED"
    } else {
        "Backend and desktop"
    };
    format!("\nVERIFIED: {scope}. {VERIFIED_TAIL}")
}

/// The success line of `gate --touched`. It never claims the whole suite: CI runs that.
pub fn touched_line(plan: &Plan) -> String {
    let areas = if plan.selection.everything {
        "every area".to_string()
    } else if plan.selection.areas.is_empty() {
        "no test area".to_string()
    } else {
        plan.selection.areas.join(", ")
    };
    format!("\nVERIFIED: Touched areas only ({areas}); CI runs everything. {VERIFIED_TAIL}")
}

pub fn default_workers() -> u32 {
    (half_cpus().len() as u32).max(2)
}

pub fn step_timeout_secs() -> u64 {
    std::env::var("FWTEST_STEP_TIMEOUT_SECS")
        .ok()
        .and_then(|value| value.parse().ok())
        .filter(|value| *value > 0)
        .unwrap_or(2400)
}

pub fn run(
    backend_only: bool,
    workers: Option<u32>,
    python: Option<&Path>,
    touched: Option<&Change>,
) -> u8 {
    let workers = workers.unwrap_or_else(default_workers);
    if workers == 0 {
        eprintln!("--workers must be at least 1");
        return 2;
    }
    let checkout = match crate::state::git_toplevel() {
        Ok(path) => path,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let scope = match touched {
        Some(change) => match select::plan(&checkout, change) {
            Ok(plan) => {
                // The gate does not run mutation cases; listing them says which to run by hand.
                let cases = select::mutation_cases(&checkout, &plan.selection).unwrap_or_default();
                print!("{}", select::describe(&plan, &cases));
                Scope::Touched(Box::new(plan))
            }
            Err(message) => {
                eprintln!("{message}");
                return 2;
            }
        },
        None if backend_only => Scope::BackendOnly,
        None => Scope::Full,
    };
    let python = match crate::state::resolve_python(python, &checkout) {
        Ok(path) => path,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let session = match contain::session() {
        Ok(session) => session,
        Err(code) => return code,
    };
    if !python_is_314(&python) {
        eprintln!("Verification needs the project's Python 3.14 interpreter.");
        return 1;
    }
    if scope.needs_desktop() && !pyside_present(&python) {
        eprintln!(
            "Full verification needs requirements-desktop.txt. --backend-only omits desktop explicitly."
        );
        return 1;
    }
    let base = match diff_base(&checkout) {
        Ok(base) => base,
        Err(message) => {
            eprintln!("FAILED: {message}");
            return 1;
        }
    };
    let report_dir = std::env::temp_dir().join(format!(
        "fwtest-gate-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    ));
    if let Err(error) = std::fs::create_dir_all(&report_dir) {
        eprintln!("FAILED: could not create the pytest report directory: {error}");
        return 1;
    }
    let junit = report_dir.join("pytest.xml");
    let timeout = step_timeout_secs();
    let mut patterns_checked = false;
    for (name, command) in steps(&python, workers, &scope, &junit, &base) {
        let past_lint = name != "Python lint" && name != "Backend types";
        if past_lint && !patterns_checked {
            patterns_checked = true;
            if let Err(message) = mutation_patterns(&checkout) {
                eprintln!("FAILED: Mutation patterns:\n{message}");
                let _ = std::fs::remove_dir_all(&report_dir);
                return 1;
            }
        }
        println!("\n{name}");
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let code = match session.run_in(&command, Some(timeout), &checkout) {
            Ok(1) if name == "Python behavior" => {
                crate::flaky::settle(&session, &checkout, &command, &junit, Some(timeout))
            }
            Ok(code) => code,
            Err(error) => {
                eprintln!("FAILED: {name}: {error}");
                let _ = std::fs::remove_dir_all(&report_dir);
                return 1;
            }
        };
        if code == 124 {
            eprintln!("FAILED: {name}: timed out");
            let _ = std::fs::remove_dir_all(&report_dir);
            return 1;
        }
        if code != 0 {
            eprintln!("FAILED: {name} (exit {code})");
            let _ = std::fs::remove_dir_all(&report_dir);
            return 1;
        }
    }
    match junit_totals(&junit) {
        _ if !scope.runs_pytest() => {}
        Ok((count, skipped)) if count > 0 && skipped == 0 => {}
        Ok((count, skipped)) => {
            eprintln!("FAILED: Python suite ran {count} tests with {skipped} skipped.");
            let _ = std::fs::remove_dir_all(&report_dir);
            return 1;
        }
        Err(error) => {
            eprintln!("FAILED: Python suite ran 0 tests with 0 skipped.");
            eprintln!("FAILED: could not read the pytest report: {error}");
            let _ = std::fs::remove_dir_all(&report_dir);
            return 1;
        }
    }
    let _ = std::fs::remove_dir_all(&report_dir);
    match &scope {
        Scope::Touched(plan) => println!("{}", touched_line(plan)),
        _ => println!("{}", verified_line(backend_only)),
    }
    0
}

/// Every mutation case's old text still occurs once in its source file, and its test still exists.
/// Edits near a case break the first, and a rename breaks the second; finding either out in the long
/// test step, or in a later mutation run, wastes the wait. A checkout with no `scripts/mutations`
/// has nothing to check.
fn mutation_patterns(checkout: &Path) -> Result<(), String> {
    println!("\nMutation patterns");
    if !checkout.join("scripts/mutations").is_dir() {
        println!("no scripts/mutations here; nothing to check");
        return Ok(());
    }
    let mut misses = crate::mutate::pattern_misses(checkout)?;
    misses.extend(crate::mutate::test_misses(checkout)?);
    if misses.is_empty() {
        return Ok(());
    }
    Err(misses.join("\n"))
}

pub fn steps(
    python: &Path,
    workers: u32,
    scope: &Scope,
    junit: &Path,
    base: &str,
) -> Vec<(String, Vec<String>)> {
    let python = python.to_string_lossy().into_owned();
    let mut pytest = vec![
        python.clone(),
        "-m".to_string(),
        "pytest".to_string(),
        "-q".to_string(),
        "-n".to_string(),
        workers.to_string(),
    ];
    pytest.extend(crate::flaky::report_args(junit));
    let mut tests = Vec::new();
    match scope {
        Scope::Full => tests.push(("Python behavior".to_string(), pytest)),
        Scope::BackendOnly => {
            pytest.push("backend/tests".to_string());
            tests.push(("Python behavior".to_string(), pytest));
        }
        Scope::Touched(plan) => {
            match &plan.pytest {
                Pytest::Nothing => {}
                Pytest::Everything(_) => tests.push(("Python behavior".to_string(), pytest)),
                Pytest::Paths(paths) => {
                    pytest.extend(paths.iter().cloned());
                    tests.push(("Python behavior".to_string(), pytest));
                }
            }
            for (dir, packages) in &plan.selection.cargo {
                let mut cargo = vec![
                    "cargo".to_string(),
                    "test".to_string(),
                    "--manifest-path".to_string(),
                    format!("{dir}/Cargo.toml"),
                ];
                for package in packages {
                    cargo.push("-p".to_string());
                    cargo.push(package.clone());
                }
                tests.push((format!("Rust tests ({dir})"), cargo));
            }
        }
    }
    let mut steps = vec![
        (
            "Python lint".to_string(),
            vec![
                python.clone(),
                "-m".to_string(),
                "ruff".to_string(),
                "check".to_string(),
                ".".to_string(),
            ],
        ),
        (
            "Backend types".to_string(),
            vec![
                python.clone(),
                "-m".to_string(),
                "mypy".to_string(),
                "backend".to_string(),
            ],
        ),
    ];
    steps.extend(tests);
    steps.extend([
        (
            "Working diff whitespace".to_string(),
            vec!["git".to_string(), "diff".to_string(), "--check".to_string()],
        ),
        (
            "Staged diff whitespace".to_string(),
            vec![
                "git".to_string(),
                "diff".to_string(),
                "--cached".to_string(),
                "--check".to_string(),
            ],
        ),
        (
            "Committed range whitespace".to_string(),
            vec![
                "git".to_string(),
                "diff".to_string(),
                "--check".to_string(),
                format!("{base}...HEAD"),
            ],
        ),
    ]);
    steps
}

fn python_is_314(python: &Path) -> bool {
    let output = Command::new(python)
        .args([
            "-c",
            "import sys; print(sys.version_info[0], sys.version_info[1])",
        ])
        .output();
    let Ok(output) = output else {
        return false;
    };
    let text = String::from_utf8_lossy(&output.stdout);
    output.status.success() && text.split_whitespace().eq(["3", "14"])
}

fn pyside_present(python: &Path) -> bool {
    Command::new(python)
        .args([
            "-c",
            "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PySide6') else 1)",
        ])
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn diff_base(checkout: &Path) -> Result<String, String> {
    let from_env = std::env::var("VERIFY_BASE_SHA").ok();
    for candidate in [
        from_env,
        Some("main".to_string()),
        Some("origin/main".to_string()),
        Some("HEAD^".to_string()),
    ]
    .into_iter()
    .flatten()
    {
        if candidate.is_empty() || candidate.chars().all(|c| c == '0') {
            continue;
        }
        let ok = Command::new("git")
            .args(["rev-parse", "--verify", &candidate])
            .current_dir(checkout)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false);
        if ok {
            return Ok(candidate);
        }
    }
    Err("Could not find a base revision for committed diff checks.".to_string())
}

fn junit_totals(path: &Path) -> std::io::Result<(u64, u64)> {
    let text = std::fs::read_to_string(path)?;
    let mut tests = 0u64;
    let mut skipped = 0u64;
    let mut rest = text.as_str();
    while let Some(start) = rest.find("<testsuite ") {
        rest = &rest[start + 1..];
        let end = rest.find('>').unwrap_or(rest.len());
        let tag = &rest[..end];
        tests += attr(tag, "tests");
        skipped += attr(tag, "skipped");
    }
    Ok((tests, skipped))
}

fn attr(tag: &str, name: &str) -> u64 {
    let key = format!("{name}=\"");
    let Some(start) = tag.find(&key) else {
        return 0;
    };
    let value = &tag[start + key.len()..];
    let end = value.find('"').unwrap_or(value.len());
    value[..end].parse().unwrap_or(0)
}
