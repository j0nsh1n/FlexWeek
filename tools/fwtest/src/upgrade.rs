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

fn could_not(why: impl std::fmt::Display) -> String {
    format!("The update could not be put in place: {why}")
}

/// `_safe_extract`'s rule, checked on what was unpacked: no link may point outside the folder. (GNU tar
/// already refuses member names that climb out with `..` or start at `/`.)
fn links_stay_inside(folder: &Path) -> Result<(), String> {
    let root = folder.canonicalize().map_err(|error| error.to_string())?;
    let mut waiting = vec![root.clone()];
    while let Some(dir) = waiting.pop() {
        for entry in std::fs::read_dir(&dir).map_err(|error| error.to_string())? {
            let path = entry.map_err(|error| error.to_string())?.path();
            let kind = std::fs::symlink_metadata(&path).map_err(|error| error.to_string())?;
            if kind.file_type().is_symlink() {
                let target = std::fs::read_link(&path).map_err(|error| error.to_string())?;
                let mut resolved = path.parent().unwrap_or(&root).to_path_buf();
                for part in target.components() {
                    match part {
                        std::path::Component::RootDir => resolved = PathBuf::from("/"),
                        std::path::Component::ParentDir => {
                            resolved.pop();
                        }
                        std::path::Component::Normal(name) => resolved.push(name),
                        _ => {}
                    }
                }
                if !resolved.starts_with(&root) {
                    let name = path.strip_prefix(&root).unwrap_or(&path);
                    return Err(format!("{} links outside the folder", name.display()));
                }
            } else if kind.is_dir() {
                waiting.push(path);
            }
        }
    }
    Ok(())
}

/// The swap itself, once the new release is unpacked in `staging`: the first folder there in directory
/// order (as `iterdir` gives it, unsorted), or `staging` itself; the install moved aside, the new one moved
/// into its place, the old one put back if that fails.
pub fn put_in_place(root: &Path, staging: &Path) -> Result<(), String> {
    let parent = root.parent().ok_or("the install has no parent folder")?;
    let name = root
        .file_name()
        .ok_or("the install has no name")?
        .to_string_lossy();
    let previous = parent.join(format!("{name}.old"));
    let mut unpacked = staging.to_path_buf();
    for entry in std::fs::read_dir(staging).map_err(could_not)? {
        let path = entry.map_err(could_not)?.path();
        if path.is_dir() {
            unpacked = path;
            break;
        }
    }
    let _ = std::fs::remove_dir_all(&previous);
    let moved = std::fs::rename(root, &previous).and_then(|()| std::fs::rename(&unpacked, root));
    if let Err(error) = moved {
        let _ = std::fs::remove_dir_all(staging);
        if !root.exists() && previous.exists() {
            let _ = std::fs::rename(&previous, root);
        }
        return Err(could_not(error));
    }
    let _ = std::fs::remove_dir_all(staging);
    let _ = std::fs::remove_dir_all(&previous);
    Ok(())
}

/// `_swap_tree`: refuse an install that holds the data or whose folder cannot be written, unpack beside it
/// (refusing links that leave the folder), then swap. A failure before the swap leaves the install as it was
/// and no staging folder behind.
pub fn swap_tree(root: &Path, tarball: &Path) -> Result<(), String> {
    if root.join("flexweek.db").exists() {
        return Err(format!(
            "{} also holds FlexWeek's data, so the update was not applied.",
            root.display()
        ));
    }
    let parent = root.parent().ok_or("the install has no parent folder")?;
    // os.access(parent, W_OK): whether this process may write there, not only the mode bits.
    if nix::unistd::access(parent, nix::unistd::AccessFlags::W_OK).is_err() {
        return Err(format!(
            "{} can't be written, so the update was not applied.",
            parent.display()
        ));
    }
    let name = root
        .file_name()
        .ok_or("the install has no name")?
        .to_string_lossy();
    let staging = parent.join(format!("{name}.update"));
    let _ = std::fs::remove_dir_all(&staging);
    if let Err(why) = unpack(tarball, &staging).and_then(|()| links_stay_inside(&staging)) {
        let _ = std::fs::remove_dir_all(&staging);
        return Err(could_not(why));
    }
    put_in_place(root, &staging)
}

/// What the report holds about the account the kept sign-in opens.
const ACCOUNT: &[&str] = &[
    "username",
    "weeks",
    "homework",
    "routines",
    "restore_points",
    "standing_blocks",
    "phones",
    "alarms",
];

/// Every value of the report that is compared with the seed file, which must say each one.
pub const COMPARED: &[&str] = &[
    "data_dir",
    "username",
    "weeks",
    "homework",
    "routines",
    "restore_points",
    "standing_blocks",
    "phones",
    "alarms",
    "week_starts_on",
    "device_key",
    "look_preset",
    "look_keys",
    "login_command",
];

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
    for name in COMPARED {
        let Some(wanted) = expect.get(*name) else {
            found.push(format!("the seed file does not say what {name} should be"));
            continue;
        };
        let got = if ACCOUNT.contains(name) {
            &report["account"][*name]
        } else {
            &report[*name]
        };
        if got != wanted {
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
            println!(
                "PASS: the new program found each seeded value ({}) and the kept sign-in",
                COMPARED.join(", ")
            );
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
