//! The gate's port-ledger step on a real git repository: a Python test file deleted since the base
//! fails the step until a ledger row names its Rust twins.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use fwtest::ledger::{LEDGER_PATH, check};

fn scratch() -> PathBuf {
    let path = std::env::temp_dir().join(format!(
        "fwtest-ledger-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&path).unwrap();
    path
}

fn git(dir: &Path, args: &[&str]) {
    let status = Command::new("git")
        .args([
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
        ])
        .args(args)
        .current_dir(dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .unwrap();
    assert!(status.success(), "git {args:?}");
}

fn write(dir: &Path, path: &str, text: &str) {
    let full = dir.join(path);
    fs::create_dir_all(full.parent().unwrap()).unwrap();
    fs::write(full, text).unwrap();
}

const ROW: &str = r#"[[port]]
python = "desktop/tests/week/test_week_zoom.py"
rust = ["flexweek-app::week::zoom_keeps_the_top_time"]
red = "zoom's clamp removed by hand: zoom_keeps_the_top_time failed"
"#;

#[test]
fn a_deleted_python_test_needs_a_ledger_row() {
    let repo = scratch();
    git(&repo, &["init", "-q"]);
    write(
        &repo,
        "desktop/tests/week/test_week_zoom.py",
        "def test_x():\n    pass\n",
    );
    write(
        &repo,
        "desktop/tests/week/test_kept.py",
        "def test_y():\n    pass\n",
    );
    write(&repo, LEDGER_PATH, "port = []\n");
    git(&repo, &["add", "."]);
    git(&repo, &["commit", "-q", "-m", "base"]);
    git(&repo, &["tag", "base"]);

    assert!(check(&repo, "base").is_ok(), "nothing deleted yet");

    fs::remove_file(repo.join("desktop/tests/week/test_week_zoom.py")).unwrap();
    let refused = check(&repo, "base").unwrap_err();
    assert!(
        refused.contains("desktop/tests/week/test_week_zoom.py"),
        "{refused}"
    );
    assert!(!refused.contains("test_kept.py"), "{refused}");

    write(&repo, LEDGER_PATH, ROW);
    assert!(check(&repo, "base").is_ok());

    let _ = fs::remove_dir_all(&repo);
}
