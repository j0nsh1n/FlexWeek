//! The upgrade check reads what a 1.x install left behind and changes none of it.

use std::path::{Path, PathBuf};

use flexweek_app::upgrade::report;
use flexweek_platform::folders::default_session_file;
use serde_json::json;

const NOW: i64 = 1_795_000_000;
const TOKEN: &str = "kept-session-token-0123456789abcdef";

struct Folder(PathBuf);

impl Drop for Folder {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn seeded(name: &str) -> Folder {
    let root = std::env::temp_dir().join(format!("flexweek-upgrade-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    let data = root.join("FlexWeek");
    let database = data.join("flexweek.db");
    flexweek_store::initialize(&database, "2026-11-16").unwrap();
    let conn = rusqlite::Connection::open(&database).unwrap();
    let user = flexweek_store::insert_user(&conn, "ana", "hash").unwrap();
    flexweek_store::open_session(&conn, TOKEN, user, NOW - 60, true).unwrap();
    let block =
        r#"[{"id":"b","title":"B","kind":"locked","duration_min":60,"days":[3],"start":"10:00"}]"#;
    for monday in ["2026-11-09", "2026-11-16"] {
        flexweek_store::save_week(&conn, user, monday, block, 0).unwrap();
    }
    flexweek_store::insert_preferences(&conn, user, 2).unwrap();
    conn.execute(
        "UPDATE preferences SET alarms_json = ?1 WHERE user_id = ?2",
        rusqlite::params![
            r#"[{"id":"a1","name":"Wake","time":"07:00","days":[0]}]"#,
            user
        ],
    )
    .unwrap();
    // The store's writes open a transaction the caller commits.
    if !conn.is_autocommit() {
        conn.execute_batch("COMMIT").unwrap();
    }
    drop(conn);
    let kept = default_session_file(&data, &database, false);
    std::fs::create_dir_all(kept.parent().unwrap()).unwrap();
    std::fs::write(&kept, json!({ "token": TOKEN }).to_string()).unwrap();
    std::fs::write(
        data.join("flexweek-look.json"),
        json!({ "material": { "preset": "plum" }, "zoom": {}, "layout": "old" }).to_string(),
    )
    .unwrap();
    std::fs::write(
        data.join("week-start.json"),
        r#"{"week_starts_on":"sunday"}"#,
    )
    .unwrap();
    std::fs::create_dir_all(data.join("sync")).unwrap();
    std::fs::write(data.join("sync/device.key"), b"key").unwrap();
    std::fs::create_dir_all(root.join("config/autostart")).unwrap();
    std::fs::write(
        root.join("config/autostart/flexweek.desktop"),
        "[Desktop Entry]\nType=Application\nExec=/opt/FlexWeek/app/FlexWeek\n",
    )
    .unwrap();
    Folder(root)
}

fn bytes(path: &Path) -> Vec<u8> {
    std::fs::read(path).unwrap()
}

#[test]
fn the_report_names_what_the_install_left() {
    let folder = seeded("names");
    let data = folder.0.join("FlexWeek");
    let found = report(&data, &folder.0.join("config"), NOW);
    assert_eq!(found["database"], true);
    assert_eq!(found["kept_session"], true);
    let account = &found["account"];
    assert_eq!(account["username"], "ana", "{found}");
    assert_eq!(account["weeks"], 2);
    assert_eq!(account["homework"], 0);
    assert_eq!(account["alarms"], 1);
    assert_eq!(found["look_preset"], "plum");
    assert_eq!(found["look_keys"], json!(["material", "zoom", "layout"]));
    assert_eq!(found["week_starts_on"], "sunday");
    assert_eq!(found["device_key"], true);
    assert_eq!(found["login_command"], "/opt/FlexWeek/app/FlexWeek");
}

#[test]
fn an_ended_session_finds_no_account() {
    let folder = seeded("ended");
    let data = folder.0.join("FlexWeek");
    let later = NOW + 31 * 24 * 3600;
    let found = report(&data, &folder.0.join("config"), later);
    assert_eq!(found["kept_session"], true);
    assert!(found["account"].is_null(), "{found}");
}

#[test]
fn checking_changes_nothing_in_the_data_folder() {
    let folder = seeded("unchanged");
    let data = folder.0.join("FlexWeek");
    let database = data.join("flexweek.db");
    let before = bytes(&database);
    let found = report(&data, &folder.0.join("config"), NOW);
    assert_eq!(found["account"]["username"], "ana");
    assert_eq!(bytes(&database), before, "the check wrote to the database");
    let names: Vec<_> = std::fs::read_dir(&data)
        .unwrap()
        .map(|entry| entry.unwrap().file_name())
        .collect();
    assert!(
        !names
            .iter()
            .any(|name| name.to_string_lossy().ends_with("-wal")),
        "the check left a write-ahead log: {names:?}"
    );
}
