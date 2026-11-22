//! The Linux tarball row of the upgrade test (2.0.0 plan, upgrade.md section 6): a 1.x install is
//! updated to a new tarball the way 1.x's updater does it (`desktop/native/updater.py`, `_swap_tree`),
//! and the new program is asked what it finds of the data the old one left.

use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value;

use crate::ExitCode;

pub struct Upgrade {
    pub old: PathBuf,
    pub new: PathBuf,
    pub home: PathBuf,
    pub expect: PathBuf,
    pub work: PathBuf,
}

fn run(command: &mut Command) -> Result<(), String> {
    let shown = format!("{command:?}");
    let status = command
        .status()
        .map_err(|error| format!("{shown}: {error}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("{shown} ended with {status}"))
    }
}

/// The tarball's `.sha256` beside it, checked as the updater checks a download.
fn checked(tarball: &Path) -> Result<(), String> {
    let folder = tarball.parent().unwrap_or(Path::new("."));
    let name = tarball
        .file_name()
        .ok_or_else(|| format!("{} is not a file", tarball.display()))?;
    let mut sums = name.to_os_string();
    sums.push(".sha256");
    run(Command::new("sha256sum")
        .arg("--check")
        .arg("--status")
        .arg(&sums)
        .current_dir(folder))
    .map_err(|why| format!("{}: checksum does not match ({why})", tarball.display()))
}

fn unpack(tarball: &Path, into: &Path) -> Result<(), String> {
    std::fs::create_dir_all(into).map_err(|error| format!("{}: {error}", into.display()))?;
    run(Command::new("tar")
        .arg("-xzf")
        .arg(tarball)
        .arg("--no-same-owner")
        .arg("-C")
        .arg(into))
}

/// The install's top folder as the updater finds it from the running program (`bundle_root`).
fn bundle_root(program: &Path) -> PathBuf {
    let parent = program.parent().unwrap_or(Path::new("."));
    if parent.file_name().is_some_and(|name| name == "app")
        && let Some(top) = parent.parent()
        && top.join("FlexWeek").is_file()
    {
        return top.to_path_buf();
    }
    parent.to_path_buf()
}

/// `_swap_tree`, step by step: refuse an install that holds the data, unpack beside it, take the first
/// folder in the archive, move the install aside, move the new one into its place, then tidy up.
pub fn swap_tree(root: &Path, tarball: &Path) -> Result<(), String> {
    if root.join("flexweek.db").exists() {
        return Err(format!(
            "{} also holds FlexWeek's data, so the update was not applied.",
            root.display()
        ));
    }
    let parent = root.parent().ok_or("the install has no parent folder")?;
    let name = root
        .file_name()
        .ok_or("the install has no name")?
        .to_string_lossy();
    let staging = parent.join(format!("{name}.update"));
    let previous = parent.join(format!("{name}.old"));
    let _ = std::fs::remove_dir_all(&staging);
    unpack(tarball, &staging)?;
    let mut folders: Vec<PathBuf> = std::fs::read_dir(&staging)
        .map_err(|error| error.to_string())?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.is_dir())
        .collect();
    folders.sort();
    let unpacked = folders
        .into_iter()
        .next()
        .unwrap_or_else(|| staging.clone());
    let _ = std::fs::remove_dir_all(&previous);
    let moved = std::fs::rename(root, &previous).and_then(|()| std::fs::rename(&unpacked, root));
    if let Err(error) = moved {
        let _ = std::fs::remove_dir_all(&staging);
        if !root.exists() && previous.exists() {
            let _ = std::fs::rename(&previous, root);
        }
        return Err(format!("The update could not be put in place: {error}"));
    }
    let _ = std::fs::remove_dir_all(&staging);
    let _ = std::fs::remove_dir_all(&previous);
    Ok(())
}

/// What the new program's report must say about the seeded data, and the install's shape after the
/// swap. Each problem is one line.
pub fn problems(root: &Path, report: &Value, expect: &Value) -> Vec<String> {
    let mut found = Vec::new();
    for file in ["FlexWeek", "app/FlexWeek", "app/flexweek-mcp"] {
        if !root.join(file).is_file() {
            found.push(format!("the updated install has no {file}"));
        }
    }
    let parent = root.parent().unwrap_or(Path::new("."));
    for left in ["FlexWeek.update", "FlexWeek.old"] {
        if parent.join(left).exists() {
            found.push(format!("{left} was left beside the install"));
        }
    }
    if report["kept_session"] != Value::Bool(true) {
        found.push("the kept sign-in was not found".into());
    }
    let pairs = [
        ("data_dir", &report["data_dir"]),
        ("username", &report["account"]["username"]),
        ("weeks", &report["account"]["weeks"]),
        ("homework", &report["account"]["homework"]),
        ("alarms", &report["account"]["alarms"]),
        ("week_starts_on", &report["week_starts_on"]),
    ];
    for (name, got) in pairs {
        if let Some(wanted) = expect.get(name)
            && got != wanted
        {
            found.push(format!(
                "{name}: seeded {wanted}, the new program found {got}"
            ));
        }
    }
    found
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text =
        std::fs::read_to_string(path).map_err(|error| format!("{}: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{}: {error}", path.display()))
}

fn attempt(task: &Upgrade) -> Result<Vec<String>, String> {
    checked(&task.old)?;
    checked(&task.new)?;
    let install = task.work.join("install");
    let _ = std::fs::remove_dir_all(&install);
    unpack(&task.old, &install)?;
    let root = bundle_root(&install.join("FlexWeek/app/FlexWeek"));
    if root != install.join("FlexWeek") {
        return Err(format!(
            "the old release is not laid out as FlexWeek/app/FlexWeek: {}",
            root.display()
        ));
    }
    swap_tree(&root, &task.new)?;
    let report_file = task.work.join("upgrade-report.json");
    let _ = std::fs::remove_file(&report_file);
    run(Command::new(root.join("FlexWeek"))
        .arg("--upgrade-check")
        .arg(&report_file)
        .env("HOME", &task.home)
        .env_remove("XDG_DATA_HOME")
        .env_remove("XDG_CONFIG_HOME"))?;
    let report = read_json(&report_file)?;
    println!("report: {}", report_file.display());
    Ok(problems(&root, &report, &read_json(&task.expect)?))
}

pub fn upgrade(task: &Upgrade) -> ExitCode {
    match attempt(task) {
        Ok(found) if found.is_empty() => {
            println!("PASS: the update kept everything that was seeded");
            ExitCode::OK
        }
        Ok(found) => {
            for line in found {
                println!("FAIL: {line}");
            }
            ExitCode::CHECK_FAILED
        }
        Err(why) => {
            println!("FAIL: {why}");
            ExitCode::CHECK_FAILED
        }
    }
}
