//! `fwtest select`, `gate --touched`, `run --touched`, the rerun of a failed test and
//! `fwtest flaky`, on a fake checkout with a fake Python. The real FlexWeek suite is not run.

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const MAP: &str = r#"
[[area]]
name = "week"
tests = ["desktop/tests/week/"]
pictures = true

[[area]]
name = "day"
tests = ["desktop/tests/day/"]
pictures = true

[[rule]]
paths = ["desktop/native/hours/"]
areas = ["week"]

[[rule]]
paths = ["docs/"]
areas = []
"#;

/// The main pytest run (the one given --junitxml) copies $FWTEST_FAKE_REPORT to the report and
/// exits $FWTEST_FAKE_PYTEST_EXIT. A run without --junitxml is a rerun of one test alone and
/// exits $FWTEST_FAKE_RERUN_EXIT.
const PYTHON: &str = r#"#!/bin/sh
printf '%s\n' "$*" >> "$FWTEST_FAKE_LOG"
printf 'cwd=%s\n' "$(pwd)" >> "$FWTEST_FAKE_LOG"
if [ "$1" = "-c" ]; then
  printf '%s\n' "3 14"
  exit 0
fi
if [ "$2" = "pytest" ]; then
  xml=""
  for arg in "$@"; do
    case "$arg" in
      --junitxml=*) xml="${arg#--junitxml=}" ;;
    esac
  done
  if [ -n "$xml" ]; then
    cp "$FWTEST_FAKE_REPORT" "$xml"
    exit "${FWTEST_FAKE_PYTEST_EXIT:-0}"
  fi
  exit "${FWTEST_FAKE_RERUN_EXIT:-0}"
fi
exit 0
"#;

const PASSING: &str = r#"<testsuites><testsuite tests="2" skipped="0">
<testcase classname="desktop.tests.week.test_drag" name="test_a" file="desktop/tests/week/test_drag.py" time="0.1" />
<testcase classname="desktop.tests.week.test_drag" name="test_b" file="desktop/tests/week/test_drag.py" time="0.1" />
</testsuite></testsuites>"#;

const ONE_FAILED: &str = r#"<testsuites><testsuite tests="2" skipped="0" failures="1">
<testcase classname="desktop.tests.week.test_drag" name="test_a" file="desktop/tests/week/test_drag.py" time="0.1"><failure message="assert 1 == 2">E assert 1 == 2</failure></testcase>
<testcase classname="desktop.tests.week.test_drag" name="test_b" file="desktop/tests/week/test_drag.py" time="0.1" />
</testsuite></testsuites>"#;

fn scratch() -> PathBuf {
    let path = std::env::temp_dir().join(format!(
        "fwtest-touched-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(path.join("no-systemd")).unwrap();
    path
}

fn write(path: &Path, text: &str) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, text).unwrap();
}

fn git(dir: &Path, args: &[&str]) -> String {
    let output = Command::new("git")
        .args(args)
        .current_dir(dir)
        .env("GIT_AUTHOR_NAME", "fwtest")
        .env("GIT_AUTHOR_EMAIL", "fwtest@example.com")
        .env("GIT_COMMITTER_NAME", "fwtest")
        .env("GIT_COMMITTER_EMAIL", "fwtest@example.com")
        .output()
        .unwrap();
    assert!(output.status.success(), "git {args:?}");
    String::from_utf8_lossy(&output.stdout).trim().to_string()
}

struct Fake {
    home: PathBuf,
    repo: PathBuf,
    python: PathBuf,
}

impl Fake {
    fn new(report: &str) -> Self {
        let home = scratch();
        let repo = home.join("repo");
        write(&repo.join("tools/fwtest/areas.toml"), MAP);
        write(&repo.join("desktop/tests/week/test_drag.py"), "");
        write(&repo.join("docs/notes.md"), "notes\n");
        git(&repo, &["init"]);
        git(&repo, &["add", "."]);
        git(&repo, &["commit", "-m", "init"]);
        write(&home.join("report.xml"), report);
        let python = home.join("python");
        fs::write(&python, PYTHON).unwrap();
        let mut perms = fs::metadata(&python).unwrap().permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&python, perms).unwrap();
        Self { home, repo, python }
    }

    fn changed(&self, paths: &[&str]) -> PathBuf {
        let file = self.home.join("changed.txt");
        fs::write(&file, paths.join("\n")).unwrap();
        file
    }

    fn fwtest(&self) -> Command {
        let sha = git(&self.repo, &["rev-parse", "HEAD"]);
        let mut command = Command::new(env!("CARGO_BIN_EXE_fwtest"));
        command
            .current_dir(&self.repo)
            .env("HOME", &self.home)
            .env("XDG_RUNTIME_DIR", self.home.join("no-systemd"))
            .env("DBUS_SESSION_BUS_ADDRESS", "")
            .env("FWTEST_QUEUE_POLL_SECS", "1")
            .env("FWTEST_QUEUE_WAIT_SECS", "8")
            .env("FWTEST_FAKE_LOG", self.home.join("calls.log"))
            .env("FWTEST_FAKE_REPORT", self.home.join("report.xml"))
            .env("FWTEST_FLAKY_LOG", self.home.join("flaky.jsonl"))
            .env_remove("GITHUB_ACTIONS")
            .env_remove("GITHUB_STEP_SUMMARY")
            .env("VERIFY_BASE_SHA", sha)
            .env("FWTEST_PYTHON", &self.python);
        command
    }

    fn calls(&self) -> String {
        fs::read_to_string(self.home.join("calls.log")).unwrap_or_default()
    }

    fn pytest_calls(&self) -> Vec<String> {
        self.calls()
            .lines()
            .filter(|line| line.starts_with("-m pytest"))
            .map(String::from)
            .collect()
    }
}

impl Drop for Fake {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.home);
    }
}

fn text(output: &Output) -> (String, String) {
    (
        String::from_utf8_lossy(&output.stdout).into_owned(),
        String::from_utf8_lossy(&output.stderr).into_owned(),
    )
}

#[test]
fn select_prints_the_areas_tests_and_pictures_the_changed_paths_pick() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["desktop/native/hours/zoom.py"]);
    let output = fake
        .fwtest()
        .args(["select", "--paths-from"])
        .arg(&changed)
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(output.status.success(), "{stderr}");
    assert!(stdout.contains("areas: week\n"), "{stdout}");
    assert!(
        stdout.contains("pytest: 1 path(s)\n  desktop/tests/week\n"),
        "{stdout}"
    );
    assert!(stdout.contains("cargo: none"), "{stdout}");
    assert!(stdout.contains("pictures: week"), "{stdout}");
}

#[test]
fn select_compares_with_a_base_and_counts_uncommitted_and_untracked_files() {
    let fake = Fake::new(PASSING);
    let base = git(&fake.repo, &["rev-parse", "HEAD"]);
    write(&fake.repo.join("desktop/native/hours/zoom.py"), "x = 1\n");
    git(&fake.repo, &["add", "."]);
    git(&fake.repo, &["commit", "-m", "zoom"]);
    write(&fake.repo.join("docs/notes.md"), "changed\n");
    write(&fake.repo.join("brand/new.txt"), "untracked\n");
    let output = fake
        .fwtest()
        .args(["select", "--base", &base])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(output.status.success(), "{stderr}");
    assert!(stdout.contains("changed: 3 path(s)"), "{stdout}");
    assert!(stdout.contains("unknown: brand/new.txt"), "{stdout}");
    assert!(stdout.contains("areas: every area"), "{stdout}");
}

#[test]
fn gate_touched_runs_pytest_on_the_selected_paths_and_says_so() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["desktop/native/hours/zoom.py"]);
    let output = fake
        .fwtest()
        .args(["gate", "--touched", "--workers", "2", "--paths-from"])
        .arg(&changed)
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(
        output.status.success(),
        "stdout:\n{stdout}\nstderr:\n{stderr}"
    );
    let pytest = fake.pytest_calls();
    assert_eq!(pytest.len(), 1, "{pytest:?}");
    assert!(pytest[0].ends_with(" desktop/tests/week"), "{}", pytest[0]);
    assert!(!pytest[0].contains("desktop/tests/day"), "{}", pytest[0]);
    assert!(
        stdout.contains("VERIFIED: Touched areas only (week); CI runs everything."),
        "{stdout}"
    );
    assert!(!stdout.contains("Backend and desktop"), "{stdout}");
}

#[test]
fn gate_touched_with_only_prose_changed_runs_no_pytest() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["docs/notes.md"]);
    let output = fake
        .fwtest()
        .args(["gate", "--touched", "--workers", "2", "--paths-from"])
        .arg(&changed)
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(
        output.status.success(),
        "stdout:\n{stdout}\nstderr:\n{stderr}"
    );
    assert!(fake.pytest_calls().is_empty(), "{}", fake.calls());
    assert!(stdout.contains("Python lint"), "{stdout}");
    assert!(stdout.contains("Committed range whitespace"), "{stdout}");
    assert!(
        stdout.contains("Touched areas only (no test area)"),
        "{stdout}"
    );
}

#[test]
fn a_test_that_fails_in_the_run_and_passes_alone_is_logged_as_flaky_and_does_not_fail_the_gate() {
    let fake = Fake::new(ONE_FAILED);
    let output = fake
        .fwtest()
        .env("FWTEST_FAKE_PYTEST_EXIT", "1")
        .env("FWTEST_FAKE_RERUN_EXIT", "0")
        .args(["gate", "--backend-only", "--workers", "2"])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(
        output.status.success(),
        "stdout:\n{stdout}\nstderr:\n{stderr}"
    );
    let pytest = fake.pytest_calls();
    assert_eq!(pytest.len(), 2, "{pytest:?}");
    assert_eq!(
        pytest[1],
        "-m pytest -q -p no:cacheprovider desktop/tests/week/test_drag.py::test_a"
    );
    assert!(
        stdout.contains("FLAKY: desktop/tests/week/test_drag.py::test_a"),
        "{stdout}"
    );
    let log = fs::read_to_string(fake.home.join("flaky.jsonl")).unwrap();
    assert_eq!(log.lines().count(), 1, "{log}");
    let entry: serde_json::Value = serde_json::from_str(log.trim()).unwrap();
    assert_eq!(entry["test"], "desktop/tests/week/test_drag.py::test_a");
    assert_eq!(entry["place"], "local");
    assert_eq!(entry["commit"], git(&fake.repo, &["rev-parse", "HEAD"]));
    assert_eq!(entry["beside"]["tests_in_run"], 2);
    assert!(entry["how"].as_str().unwrap().starts_with("assert 1 == 2"));
    assert!(stdout.contains("VERIFIED:"), "{stdout}");
}

#[test]
fn a_test_that_fails_again_alone_fails_the_gate_and_is_not_logged() {
    let fake = Fake::new(ONE_FAILED);
    let output = fake
        .fwtest()
        .env("FWTEST_FAKE_PYTEST_EXIT", "1")
        .env("FWTEST_FAKE_RERUN_EXIT", "1")
        .args(["gate", "--backend-only", "--workers", "2"])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert_eq!(output.status.code(), Some(1), "{stderr}");
    assert!(
        stderr.contains("FAILED again alone: desktop/tests/week/test_drag.py::test_a"),
        "{stderr}"
    );
    assert!(
        stderr.contains("FAILED: Python behavior (exit 1)"),
        "{stderr}"
    );
    assert!(!stdout.contains("VERIFIED:"), "{stdout}");
    assert!(!fake.home.join("flaky.jsonl").exists());
}

#[test]
fn a_pytest_failure_that_names_no_failed_test_is_not_rerun() {
    let fake = Fake::new(PASSING);
    let output = fake
        .fwtest()
        .env("FWTEST_FAKE_PYTEST_EXIT", "1")
        .args(["gate", "--backend-only", "--workers", "2"])
        .output()
        .unwrap();
    let (_, stderr) = text(&output);
    assert_eq!(output.status.code(), Some(1), "{stderr}");
    assert_eq!(fake.pytest_calls().len(), 1, "{}", fake.calls());
    assert!(stderr.contains("names no failed test"), "{stderr}");
}

#[test]
fn run_touched_adds_the_selected_paths_and_runs_at_the_checkout() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["desktop/native/hours/zoom.py"]);
    let nested = fake.repo.join("docs");
    let output = fake
        .fwtest()
        .current_dir(&nested)
        .args(["run", "--touched", "--paths-from"])
        .arg(&changed)
        .arg("--")
        .arg(&fake.python)
        .args(["-m", "pytest", "-q"])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(
        output.status.success(),
        "stdout:\n{stdout}\nstderr:\n{stderr}"
    );
    let pytest = fake.pytest_calls();
    assert_eq!(pytest.len(), 1, "{pytest:?}");
    assert!(
        pytest[0].starts_with("-m pytest -q desktop/tests/week --junitxml="),
        "{}",
        pytest[0]
    );
    let log = fake.calls();
    assert!(
        log.contains(&format!("cwd={}", fake.repo.display())),
        "{log}"
    );
}

#[test]
fn run_touched_with_nothing_selected_runs_nothing() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["docs/notes.md"]);
    let output = fake
        .fwtest()
        .args(["run", "--touched", "--paths-from"])
        .arg(&changed)
        .arg("--")
        .arg(&fake.python)
        .args(["-m", "pytest", "-q"])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(output.status.success(), "{stderr}");
    assert!(stdout.contains("nothing to run"), "{stdout}");
    assert!(fake.pytest_calls().is_empty(), "{}", fake.calls());
}

#[test]
fn run_touched_refuses_a_command_that_is_not_pytest() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["docs/notes.md"]);
    let output = fake
        .fwtest()
        .args(["run", "--touched", "--paths-from"])
        .arg(&changed)
        .args(["--", "true"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
}

#[test]
fn a_flaky_test_in_fwtest_run_is_rerun_and_logged_too() {
    let fake = Fake::new(ONE_FAILED);
    let output = fake
        .fwtest()
        .env("FWTEST_FAKE_PYTEST_EXIT", "1")
        .env("FWTEST_FAKE_RERUN_EXIT", "0")
        .arg("run")
        .arg("--")
        .arg(&fake.python)
        .args(["-m", "pytest", "-q", "-n", "4", "desktop/tests/week"])
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(
        output.status.success(),
        "stdout:\n{stdout}\nstderr:\n{stderr}"
    );
    let log = fs::read_to_string(fake.home.join("flaky.jsonl")).unwrap();
    let entry: serde_json::Value = serde_json::from_str(log.trim()).unwrap();
    assert_eq!(entry["test"], "desktop/tests/week/test_drag.py::test_a");
    assert!(
        entry["beside"]["command"]
            .as_str()
            .unwrap()
            .contains("-n 4 desktop/tests/week"),
        "{entry}"
    );
}

#[test]
fn base_and_paths_from_need_touched_and_backend_only_does_not_mix_with_it() {
    let fake = Fake::new(PASSING);
    let changed = fake.changed(&["docs/notes.md"]);
    let without = fake
        .fwtest()
        .args(["gate", "--paths-from"])
        .arg(&changed)
        .output()
        .unwrap();
    assert_eq!(without.status.code(), Some(2));
    let both = fake
        .fwtest()
        .args(["gate", "--backend-only", "--touched"])
        .output()
        .unwrap();
    assert_eq!(both.status.code(), Some(2));
    assert!(fake.calls().is_empty(), "{}", fake.calls());
}

#[test]
fn flaky_summarises_the_log_most_frequent_first() {
    let fake = Fake::new(PASSING);
    let line = |test: &str, date: &str| {
        format!(
            r#"{{"test":"{test}","date":"{date}","commit":"0123456789abcdef","place":"ci desktop","how":"boom\nmore","beside":{{"command":"pytest","tests_in_run":3,"other_failures":[]}}}}"#
        )
    };
    let log = [
        line("a::rare", "2026-11-06T09:00:00Z"),
        line("b::often", "2026-11-05T09:00:00Z"),
        line("b::often", "2026-11-07T09:00:00Z"),
    ]
    .join("\n");
    let path = fake.home.join("given.jsonl");
    fs::write(&path, log).unwrap();
    let output = fake
        .fwtest()
        .args(["flaky", "--log"])
        .arg(&path)
        .output()
        .unwrap();
    let (stdout, stderr) = text(&output);
    assert!(output.status.success(), "{stderr}");
    let often = stdout.find("b::often").expect(&stdout);
    let rare = stdout.find("a::rare").expect(&stdout);
    assert!(often < rare, "{stdout}");
    assert!(stdout.contains("   2  b::often"), "{stdout}");
    assert!(
        stdout.contains("last 2026-11-07T09:00:00Z at 0123456789 (ci desktop): boom"),
        "{stdout}"
    );
}

#[test]
fn flaky_with_no_log_says_nothing_is_logged() {
    let fake = Fake::new(PASSING);
    let output = fake.fwtest().arg("flaky").output().unwrap();
    let (stdout, stderr) = text(&output);
    assert!(output.status.success(), "{stderr}");
    assert!(stdout.contains("no flaky tests logged"), "{stdout}");
}
