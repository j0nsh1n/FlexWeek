//! The port ledger: while the desktop moves to Rust (2.0.0), a Python test file may be deleted only
//! with a row in `tools/fwtest/port-ledger.toml` naming the Rust tests that replace it and how they
//! were seen to fail, or, for a test of something the app no longer has, the approved decision that
//! removed it (`gone`). The gate compares the base's Python test files with the working tree and
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
    #[serde(default)]
    pub rust: Vec<String>,
    /// How each was seen to fail: the rule broken by hand or the mutation case that turned it red.
    #[serde(default)]
    pub red: String,
    /// Instead of `rust` and `red`: the approved decision that removed what the file tested (the
    /// server, the hosted-server setting), so nothing is left to port.
    #[serde(default)]
    pub gone: String,
}

impl Ledger {
    pub fn parse(text: &str) -> Result<Self, String> {
        let ledger: Ledger =
            toml::from_str(text).map_err(|error| format!("{LEDGER_PATH}: {error}"))?;
        let mut seen = BTreeSet::new();
        for row in &ledger.port {
            if row.python.trim().is_empty() {
                return Err(format!("{LEDGER_PATH}: a row names no Python test file"));
            }
            if !seen.insert(row.python.as_str()) {
                return Err(format!("{LEDGER_PATH}: {} has two rows", row.python));
            }
            if !row.gone.trim().is_empty() {
                if !row.rust.is_empty() || !row.red.trim().is_empty() {
                    return Err(format!(
                        "{LEDGER_PATH}: {} is both gone and ported; a row is one or the other",
                        row.python
                    ));
                }
                continue;
            }
            if row.rust.is_empty() || row.rust.iter().any(|name| name.trim().is_empty()) {
                return Err(format!(
                    "{LEDGER_PATH}: {} names no Rust test, or a blank one",
                    row.python
                ));
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

/// The folders pytest collects (pytest.ini `testpaths`), with pytest's default file names.
const TEST_FOLDERS: [&str; 4] = [
    "backend/tests/",
    "desktop/tests/",
    "scripts/rig/",
    "scripts/pictures/",
];

/// A Python test file: `test_*.py` or `*_test.py` in a folder pytest collects.
pub fn is_python_test(path: &str) -> bool {
    let in_tests = TEST_FOLDERS.iter().any(|folder| path.starts_with(folder));
    let name = path.rsplit('/').next().unwrap_or(path);
    let named = name.ends_with(".py") && (name.starts_with("test_") || name.ends_with("_test.py"));
    in_tests && named
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

fn git_z(checkout: &Path, args: &[&str]) -> Result<Vec<String>, String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(checkout)
        .output()
        .map_err(|error| format!("git {}: {error}", args.join(" ")))?;
    if !output.status.success() {
        return Err(format!("git {} failed", args.join(" ")));
    }
    Ok(output
        .stdout
        .split(|byte| *byte == 0)
        .filter(|part| !part.is_empty())
        .map(|part| String::from_utf8_lossy(part).into_owned())
        .collect())
}

/// The gate step. The comparison is with where this branch left the base, so a test added on the
/// base later is not counted as deleted here. A checkout whose base had no ledger has nothing to check;
/// deleting the ledger itself fails.
pub fn check(checkout: &Path, base: &str) -> Result<(), String> {
    println!("\nPort ledger");
    let fork = git_z(checkout, &["merge-base", base, "HEAD"])
        .ok()
        .and_then(|lines| lines.first().map(|line| line.trim().to_string()))
        .unwrap_or_else(|| base.to_string());
    let base_files = git_z(checkout, &["ls-tree", "-r", "-z", "--name-only", &fork])?;
    let tracked: BTreeSet<String> = git_z(checkout, &["ls-files", "-z"])?.into_iter().collect();
    let ledger_file = checkout.join(LEDGER_PATH);
    if !tracked.contains(LEDGER_PATH) || !ledger_file.is_file() {
        if base_files.iter().any(|path| path == LEDGER_PATH) {
            return Err(format!(
                "{LEDGER_PATH} was deleted; it must stay while Python tests remain"
            ));
        }
        println!("no {LEDGER_PATH} here; nothing to check");
        return Ok(());
    }
    let text =
        std::fs::read_to_string(&ledger_file).map_err(|error| format!("{LEDGER_PATH}: {error}"))?;
    let ledger = Ledger::parse(&text)?;
    let missing = unrecorded(
        base_files.iter().map(String::as_str),
        |path| tracked.contains(path) && checkout.join(path).is_file(),
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
    fn only_test_files_in_the_folders_pytest_collects_count() {
        assert!(is_python_test("desktop/tests/week/test_week_zoom.py"));
        assert!(is_python_test("backend/tests/test_saving_a_week.py"));
        assert!(!is_python_test("desktop/tests/week/support_week.py"));
        assert!(!is_python_test("desktop/native/test_helpers.py"));
        assert!(!is_python_test("desktop/tests/week/test_notes.md"));
        assert!(is_python_test("scripts/rig/test_drive.py"));
        assert!(is_python_test("scripts/pictures/test_render.py"));
        assert!(is_python_test("backend/tests/saving_test.py"));
        assert!(!is_python_test("scripts/mutations/test_cases.py"));
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
        let blank_entry =
            "[[port]]\npython = \"a/test_x.py\"\nrust = [\"t\", \" \"]\nred = \"broke it\"\n";
        assert!(Ledger::parse(blank_entry).is_err());
        let twice = "[[port]]\npython = \"a/test_x.py\"\nrust = [\"t\"]\nred = \"r\"\n\n[[port]]\npython = \"a/test_x.py\"\nrust = [\"u\"]\nred = \"r\"\n";
        assert!(Ledger::parse(twice).unwrap_err().contains("two rows"));
        let no_python = "[[port]]\npython = \" \"\nrust = [\"t\"]\nred = \"r\"\n";
        assert!(Ledger::parse(no_python).is_err());
        let no_red = "[[port]]\npython = \"a/test_x.py\"\nrust = [\"t\"]\nred = \" \"\n";
        assert!(
            Ledger::parse(no_red)
                .unwrap_err()
                .contains("how its Rust tests failed")
        );
    }

    #[test]
    fn a_test_of_something_removed_names_the_decision_instead() {
        let gone = "[[port]]\npython = \"a/test_x.py\"\ngone = \"D4: the hosted server was removed\"\n";
        let ledger = Ledger::parse(gone).unwrap();
        assert!(unrecorded(["a/test_x.py"], |_| false, &ledger).is_empty());
        let blank = "[[port]]\npython = \"a/test_x.py\"\ngone = \" \"\n";
        assert!(Ledger::parse(blank).unwrap_err().contains("names no Rust test"));
        let both = "[[port]]\npython = \"a/test_x.py\"\ngone = \"D4\"\nrust = [\"t\"]\nred = \"r\"\n";
        assert!(Ledger::parse(both).unwrap_err().contains("one or the other"));
        let gone_with_red = "[[port]]\npython = \"a/test_x.py\"\ngone = \"D4\"\nred = \"r\"\n";
        assert!(Ledger::parse(gone_with_red).is_err());
    }

    #[test]
    fn an_empty_ledger_parses() {
        let text = "# header only\nport = []\n";
        assert!(Ledger::parse(text).unwrap().port.is_empty());
    }
}
