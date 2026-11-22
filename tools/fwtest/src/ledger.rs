//! The port ledger: while the desktop moves to Rust (2.0.0), a Python test file may be deleted only
//! with a row in `tools/fwtest/port-ledger.toml` naming the Rust tests that replace it and how they
//! were seen to fail. The gate compares the base's Python test files with the working tree and
//! refuses any that went without a row.

use std::collections::BTreeSet;
use std::path::Path;
use std::process::Command;

use serde::Deserialize;

pub const LEDGER_PATH: &str = "tools/fwtest/port-ledger.toml";

#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ledger {
    #[serde(default)]
    pub port: Vec<Row>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Row {
    /// The deleted Python test file, from the repository root.
    pub python: String,
    /// The Rust tests that replace it, as `package::path::test_name` or a test file path.
    pub rust: Vec<String>,
    /// How each was seen to fail: the rule broken by hand or the mutation case that turned it red.
    pub red: String,
}

impl Ledger {
    pub fn parse(text: &str) -> Result<Self, String> {
        let ledger: Ledger =
            toml::from_str(text).map_err(|error| format!("{LEDGER_PATH}: {error}"))?;
        for row in &ledger.port {
            if row.rust.iter().all(|name| name.trim().is_empty()) {
                return Err(format!("{LEDGER_PATH}: {} names no Rust test", row.python));
            }
            if row.red.trim().is_empty() {
                return Err(format!(
                    "{LEDGER_PATH}: {} does not say how its Rust tests failed",
                    row.python
                ));
            }
        }
        Ok(ledger)
    }

    fn named(&self) -> BTreeSet<&str> {
        self.port.iter().map(|row| row.python.as_str()).collect()
    }
}

/// A Python test file: `test_*.py` under `desktop/tests/` or `backend/tests/`.
pub fn is_python_test(path: &str) -> bool {
    let in_tests = path.starts_with("desktop/tests/") || path.starts_with("backend/tests/");
    let name = path.rsplit('/').next().unwrap_or(path);
    in_tests && name.starts_with("test_") && name.ends_with(".py")
}

/// The base's Python test files that are gone and that no ledger row names, sorted.
pub fn unrecorded<'a>(
    base_files: impl IntoIterator<Item = &'a str>,
    exists: impl Fn(&str) -> bool,
    ledger: &Ledger,
) -> Vec<String> {
    let named = ledger.named();
    let mut missing: Vec<String> = base_files
        .into_iter()
        .filter(|path| is_python_test(path) && !exists(path) && !named.contains(path))
        .map(str::to_string)
        .collect();
    missing.sort();
    missing.dedup();
    missing
}

/// The gate step. A checkout without a ledger file has nothing to check.
pub fn check(checkout: &Path, base: &str) -> Result<(), String> {
    println!("\nPort ledger");
    let ledger_file = checkout.join(LEDGER_PATH);
    if !ledger_file.is_file() {
        println!("no {LEDGER_PATH} here; nothing to check");
        return Ok(());
    }
    let text =
        std::fs::read_to_string(&ledger_file).map_err(|error| format!("{LEDGER_PATH}: {error}"))?;
    let ledger = Ledger::parse(&text)?;
    let output = Command::new("git")
        .args(["ls-tree", "-r", "--name-only", base])
        .current_dir(checkout)
        .output()
        .map_err(|error| format!("git ls-tree {base}: {error}"))?;
    if !output.status.success() {
        return Err(format!("git ls-tree {base} failed"));
    }
    let listing = String::from_utf8_lossy(&output.stdout);
    let missing = unrecorded(
        listing.lines(),
        |path| checkout.join(path).is_file(),
        &ledger,
    );
    if missing.is_empty() {
        return Ok(());
    }
    Err(format!(
        "These Python test files were deleted without a row in {LEDGER_PATH} naming their Rust twins:\n{}",
        missing.join("\n")
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    const ROW: &str = r#"
[[port]]
python = "desktop/tests/week/test_week_zoom.py"
rust = ["flexweek-app::week::zoom_keeps_the_top_time"]
red = "zoom's clamp removed by hand: zoom_keeps_the_top_time failed"
"#;

    #[test]
    fn only_test_files_under_the_two_test_folders_count() {
        assert!(is_python_test("desktop/tests/week/test_week_zoom.py"));
        assert!(is_python_test("backend/tests/test_saving_a_week.py"));
        assert!(!is_python_test("desktop/tests/week/support_week.py"));
        assert!(!is_python_test("desktop/native/test_helpers.py"));
        assert!(!is_python_test("desktop/tests/week/test_notes.md"));
    }

    #[test]
    fn a_deleted_test_without_a_row_is_reported() {
        let ledger = Ledger::default();
        let base = [
            "desktop/tests/week/test_week_zoom.py",
            "desktop/tests/week/test_kept.py",
        ];
        let gone = |path: &str| path.ends_with("test_week_zoom.py");
        let missing = unrecorded(base, |path| !gone(path), &ledger);
        assert_eq!(
            missing,
            vec!["desktop/tests/week/test_week_zoom.py".to_string()]
        );
    }

    #[test]
    fn a_deleted_test_with_a_row_passes() {
        let ledger = Ledger::parse(ROW).unwrap();
        let base = ["desktop/tests/week/test_week_zoom.py"];
        assert!(unrecorded(base, |_| false, &ledger).is_empty());
    }

    #[test]
    fn a_test_still_present_needs_no_row() {
        let base = ["backend/tests/test_saving_a_week.py"];
        assert!(unrecorded(base, |_| true, &Ledger::default()).is_empty());
    }

    #[test]
    fn a_row_must_name_a_rust_test_and_say_how_it_failed() {
        let no_rust = "[[port]]\npython = \"a/test_x.py\"\nrust = []\nred = \"broke it\"\n";
        assert!(
            Ledger::parse(no_rust)
                .unwrap_err()
                .contains("names no Rust test")
        );
        let no_red = "[[port]]\npython = \"a/test_x.py\"\nrust = [\"t\"]\nred = \" \"\n";
        assert!(
            Ledger::parse(no_red)
                .unwrap_err()
                .contains("how its Rust tests failed")
        );
    }

    #[test]
    fn an_empty_ledger_parses() {
        let text = "# header only\nport = []\n";
        assert!(Ledger::parse(text).unwrap().port.is_empty());
    }
}
