//! The tarball swap as 1.x's updater does it, and the comparison of the new program's report.

use std::path::{Path, PathBuf};
use std::process::Command;

use fwtest::upgrade::{problems, swap_tree};
use serde_json::json;

struct Scratch(PathBuf);

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn scratch(name: &str) -> Scratch {
    let dir = std::env::temp_dir().join(format!("fwtest-upgrade-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    Scratch(dir)
}

fn write(path: &Path, text: &str) {
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    std::fs::write(path, text).unwrap();
}

/// A tarball whose one top folder holds `files`.
fn tarball(at: &Path, top: &str, files: &[(&str, &str)]) -> PathBuf {
    let stage = at.join(format!("stage-{top}"));
    for (name, text) in files {
        write(&stage.join(top).join(name), text);
    }
    let out = at.join(format!("{top}.tar.gz"));
    let status = Command::new("tar")
        .arg("-C")
        .arg(&stage)
        .arg("-czf")
        .arg(&out)
        .arg(top)
        .status()
        .unwrap();
    assert!(status.success());
    out
}

fn installed(at: &Path) -> PathBuf {
    let root = at.join("opt/FlexWeek");
    write(&root.join("FlexWeek"), "old launcher");
    write(&root.join("app/FlexWeek"), "old program");
    write(&root.join("app/old-library.so"), "old");
    root
}

#[test]
fn the_new_top_folder_takes_the_install_place_and_nothing_is_left_beside_it() {
    let dir = scratch("swap");
    let root = installed(&dir.0);
    let new = tarball(
        &dir.0,
        "Packaged",
        &[
            ("FlexWeek", "new launcher"),
            ("app/FlexWeek", "new program"),
            ("app/flexweek-mcp", "helper"),
        ],
    );
    swap_tree(&root, &new).unwrap();
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "new program"
    );
    assert!(
        !root.join("app/old-library.so").exists(),
        "an old file survived the swap"
    );
    for left in ["FlexWeek.update", "FlexWeek.old"] {
        assert!(!dir.0.join("opt").join(left).exists(), "{left} was left");
    }
}

#[test]
fn an_install_that_holds_the_data_is_not_replaced() {
    let dir = scratch("data");
    let root = installed(&dir.0);
    write(&root.join("flexweek.db"), "data");
    let new = tarball(&dir.0, "Packaged", &[("app/FlexWeek", "new program")]);
    let refused = swap_tree(&root, &new).unwrap_err();
    assert!(refused.contains("also holds FlexWeek's data"), "{refused}");
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "old program"
    );
}

#[test]
fn the_comparison_names_each_thing_the_new_program_lost() {
    let dir = scratch("compare");
    let root = installed(&dir.0);
    let report = json!({
        "kept_session": false,
        "data_dir": "/home/s/.local/share/FlexWeek",
        "account": { "username": "ana", "weeks": 1, "homework": 2, "alarms": 0 },
        "week_starts_on": "monday",
    });
    let expect = json!({
        "data_dir": "/home/s/.local/share/FlexWeek",
        "username": "ana",
        "weeks": 1,
        "homework": 2,
        "alarms": 2,
        "week_starts_on": "sunday",
    });
    let found = problems(&root, &report, &expect);
    assert_eq!(
        found,
        vec![
            "the updated install has no app/flexweek-mcp".to_string(),
            "the kept sign-in was not found".to_string(),
            "alarms: seeded 2, the new program found 0".to_string(),
            "week_starts_on: seeded \"sunday\", the new program found \"monday\"".to_string(),
        ]
    );
    write(&root.join("app/flexweek-mcp"), "helper");
    let whole = json!({
        "kept_session": true,
        "data_dir": "/home/s/.local/share/FlexWeek",
        "account": { "username": "ana", "weeks": 1, "homework": 2, "alarms": 2 },
        "week_starts_on": "sunday",
    });
    assert!(problems(&root, &whole, &expect).is_empty());
}
