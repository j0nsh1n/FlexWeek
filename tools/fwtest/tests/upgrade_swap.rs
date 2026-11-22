//! The tarball swap as 1.x's updater does it, and the comparison of the new program's report.

use std::path::{Path, PathBuf};
use std::process::Command;

use fwtest::upgrade::{problems, put_in_place, swap_tree};
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

fn seeded() -> serde_json::Value {
    json!({
        "data_dir": "/home/s/.local/share/FlexWeek", "username": "ana", "weeks": 1, "homework": 2,
        "routines": 2, "restore_points": 1, "standing_blocks": 3, "phones": 1, "alarms": 2,
        "week_starts_on": "sunday", "device_key": true, "look_preset": "plum",
        "look_keys": ["material", "zoom"],
        "login_command": "/opt/FlexWeek/FlexWeek",
    })
}

/// The report a new program gives when it found everything `seeded` says.
fn found_all() -> serde_json::Value {
    let seed = seeded();
    json!({
        "kept_session": true,
        "data_dir": seed["data_dir"], "week_starts_on": seed["week_starts_on"],
        "device_key": seed["device_key"], "look_preset": seed["look_preset"],
        "look_keys": seed["look_keys"],
        "login_command": seed["login_command"],
        "account": {
            "username": "ana", "weeks": 1, "homework": 2, "routines": 2, "restore_points": 1,
            "standing_blocks": 3, "phones": 1, "alarms": 2,
        },
    })
}

#[test]
fn the_comparison_names_each_thing_the_new_program_lost() {
    let dir = scratch("compare");
    let root = installed(&dir.0);
    write(&root.join("app/flexweek-mcp"), "helper");
    assert!(problems(&root, &found_all(), &seeded()).is_empty());
    for (place, name, lost) in [
        ("account", "routines", json!(0)),
        ("account", "restore_points", json!(0)),
        ("account", "standing_blocks", json!(0)),
        ("account", "phones", json!(0)),
        ("account", "alarms", json!(0)),
        ("account", "weeks", json!(0)),
        ("account", "homework", json!(0)),
        ("account", "username", json!(null)),
        ("top", "device_key", json!(false)),
        ("top", "look_preset", json!(null)),
        ("top", "look_keys", json!(["material"])),
        ("top", "login_command", json!(null)),
        ("top", "week_starts_on", json!("monday")),
        ("top", "data_dir", json!("/elsewhere")),
    ] {
        let mut report = found_all();
        let field = if place == "account" {
            &mut report["account"][name]
        } else {
            &mut report[name]
        };
        *field = lost.clone();
        let found = problems(&root, &report, &seeded());
        assert_eq!(
            found,
            vec![format!(
                "{name}: seeded {}, the new program found {lost}",
                seeded()[name]
            )],
            "losing {name}"
        );
    }
}

#[test]
fn a_seed_file_that_leaves_a_value_out_fails_and_so_does_a_missing_helper_or_sign_in() {
    let dir = scratch("seed-gaps");
    let root = installed(&dir.0);
    let mut short = seeded();
    short.as_object_mut().unwrap().remove("phones");
    let mut report = found_all();
    report["kept_session"] = json!(false);
    assert_eq!(
        problems(&root, &report, &short),
        vec![
            "the updated install has no app/flexweek-mcp".to_string(),
            "the kept sign-in was not found".to_string(),
            "the seed file does not say what phones should be".to_string(),
        ]
    );
}

#[test]
fn the_first_folder_in_directory_order_is_installed_not_the_first_by_name() {
    let dir = scratch("order");
    let root = installed(&dir.0);
    let staging = dir.0.join("opt/FlexWeek.update");
    for name in ["B", "A", "C"] {
        write(&staging.join(name).join("app/FlexWeek"), name);
    }
    let first = std::fs::read_dir(&staging)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .find(|path| path.is_dir())
        .unwrap();
    let wanted = first.file_name().unwrap().to_string_lossy().into_owned();
    put_in_place(&root, &staging).unwrap();
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        wanted
    );
}

#[test]
fn a_release_with_a_link_out_of_its_folder_is_refused_and_the_install_kept() {
    let dir = scratch("link");
    let root = installed(&dir.0);
    let stage = dir.0.join("stage-link/Packaged/app");
    std::fs::create_dir_all(&stage).unwrap();
    std::os::unix::fs::symlink("../../../../../../etc/passwd", stage.join("FlexWeek")).unwrap();
    let out = dir.0.join("link.tar.gz");
    assert!(
        Command::new("tar")
            .arg("-C")
            .arg(dir.0.join("stage-link"))
            .arg("-czf")
            .arg(&out)
            .arg("Packaged")
            .status()
            .unwrap()
            .success()
    );
    let refused = swap_tree(&root, &out).unwrap_err();
    assert!(refused.contains("links outside the folder"), "{refused}");
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "old program"
    );
    assert!(
        !dir.0.join("opt/FlexWeek.update").exists(),
        "staging was left"
    );
}

#[test]
fn a_broken_tarball_leaves_the_install_and_no_staging_folder() {
    let dir = scratch("broken");
    let root = installed(&dir.0);
    let bad = dir.0.join("broken.tar.gz");
    std::fs::write(&bad, b"not a tarball").unwrap();
    let refused = swap_tree(&root, &bad).unwrap_err();
    assert!(
        refused.starts_with("The update could not be put in place:"),
        "{refused}"
    );
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "old program"
    );
    assert!(
        !dir.0.join("opt/FlexWeek.update").exists(),
        "staging was left"
    );
}

/// The new folder cannot be moved into place (its folder is read-only), so the install moved aside is
/// moved back, as `_swap_tree` does.
#[test]
fn when_the_new_folder_cannot_be_moved_in_the_old_install_is_put_back() {
    use std::os::unix::fs::PermissionsExt;
    let dir = scratch("rollback");
    let root = installed(&dir.0);
    let staging = dir.0.join("opt/FlexWeek.update");
    write(&staging.join("Packaged/app/FlexWeek"), "new program");
    std::fs::set_permissions(&staging, std::fs::Permissions::from_mode(0o555)).unwrap();
    let refused = put_in_place(&root, &staging);
    std::fs::set_permissions(&staging, std::fs::Permissions::from_mode(0o755)).ok();
    assert!(refused.is_err(), "the move should have failed");
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "old program"
    );
    assert!(!dir.0.join("opt/FlexWeek.old").exists());
}

#[test]
fn an_install_whose_folder_cannot_be_written_is_left_alone_with_the_updaters_words() {
    use std::os::unix::fs::PermissionsExt;
    let dir = scratch("unwritable");
    let root = installed(&dir.0);
    let new = tarball(&dir.0, "Packaged", &[("app/FlexWeek", "new program")]);
    let opt = dir.0.join("opt");
    std::fs::set_permissions(&opt, std::fs::Permissions::from_mode(0o555)).unwrap();
    let refused = swap_tree(&root, &new);
    std::fs::set_permissions(&opt, std::fs::Permissions::from_mode(0o755)).unwrap();
    assert_eq!(
        refused.unwrap_err(),
        format!(
            "{} can't be written, so the update was not applied.",
            opt.display()
        )
    );
    assert_eq!(
        std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
        "old program"
    );
}

/// A gzipped tarball whose members are written with the raw names and link targets given, so a test can
/// make the archives a release must never contain.
fn crafted(at: &Path, entries: &[(&str, tar::EntryType, &str)]) -> PathBuf {
    let out = at.join("crafted.tar.gz");
    let file = std::fs::File::create(&out).unwrap();
    let mut builder = tar::Builder::new(flate2::write::GzEncoder::new(
        file,
        flate2::Compression::default(),
    ));
    for (name, kind, link) in entries {
        let mut header = tar::Header::new_old();
        header.as_old_mut().name[..name.len()].copy_from_slice(name.as_bytes());
        header.as_old_mut().linkname[..link.len()].copy_from_slice(link.as_bytes());
        header.set_entry_type(*kind);
        header.set_mode(0o755);
        let body: &[u8] = if kind.is_file() { b"new program" } else { b"" };
        header.set_size(body.len() as u64);
        header.set_cksum();
        builder.append(&header, body).unwrap();
    }
    builder.into_inner().unwrap().finish().unwrap();
    out
}

#[test]
fn an_absolute_member_or_a_hard_link_out_of_the_folder_is_refused_before_anything_is_written() {
    use tar::EntryType;
    for (case, entries) in [
        (
            "absolute",
            vec![("/tmp/fwtest-absolute-member", EntryType::Regular, "")],
        ),
        (
            "hard link",
            vec![
                ("Packaged/app/FlexWeek", EntryType::Regular, ""),
                (
                    "Packaged/app/escape",
                    EntryType::Link,
                    "../../../../etc/passwd",
                ),
            ],
        ),
        (
            "climbs out",
            vec![("Packaged/../../outside", EntryType::Regular, "")],
        ),
    ] {
        let dir = scratch(&format!("crafted-{}", case.replace(' ', "-")));
        let root = installed(&dir.0);
        let archive = crafted(&dir.0, &entries);
        let refused = swap_tree(&root, &archive).unwrap_err();
        assert!(refused.contains("outside the folder"), "{case}: {refused}");
        assert_eq!(
            std::fs::read_to_string(root.join("app/FlexWeek")).unwrap(),
            "old program",
            "{case}"
        );
        assert!(
            !dir.0.join("opt/FlexWeek.update").exists(),
            "{case}: staging was left"
        );
        assert!(
            !Path::new("/tmp/fwtest-absolute-member").exists(),
            "{case}: an absolute member was written"
        );
    }
}
