use std::collections::HashMap;
use std::fmt::Display;
use std::path::Path;
use std::sync::{Arc, Mutex};

use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime};
use flexweek_engine::time::monday_of;
use rusqlite::{Connection, OptionalExtension};
use serde_json::{Value, json};

#[cfg(test)]
use crate::sync_api::NotPairedSync;
use crate::sync_api::{NativeSync, SyncApi};

#[derive(Clone, Debug)]
pub(crate) struct Preview {
    pub week_start: String,
    pub blocks: Value,
    pub earlier: Vec<Value>,
    pub revision: i64,
    pub placed_ids: Vec<String>,
}

#[derive(Debug, thiserror::Error, uniffi::Error)]
pub enum FfiError {
    #[error("{details}")]
    Failure { details: String },
}

pub(crate) fn failure(error: impl Display) -> FfiError {
    FfiError::Failure {
        details: error.to_string(),
    }
}

pub(crate) fn engine_failure(error: flexweek_engine::EngineError) -> FfiError {
    failure(error.message)
}

#[uniffi::export(with_foreign)]
pub trait Host: Send + Sync {
    fn now_unix_ms(&self) -> i64;
    fn local_now(&self) -> String;
    fn random_bytes(&self, count: u32) -> Vec<u8>;
    fn data_changed(&self, scope: String);
}

/// Where a block was let go: the day it was dragged from and the day, start and end (minutes of the
/// day) it landed on.
#[derive(Clone, Debug, uniffi::Record)]
pub struct HandLanding {
    pub block_id: String,
    pub from_day: i64,
    pub to_day: i64,
    pub start_min: i64,
    pub end_min: i64,
}

#[derive(Clone, Debug, uniffi::Record)]
pub struct Reminder {
    pub id: String,
    pub title: String,
    pub local_time: String,
    pub kind: String,
    pub start_time: String,
    pub duration_min: Option<i64>,
}

#[derive(uniffi::Object)]
pub struct FlexWeek {
    pub(crate) db: Mutex<Connection>,
    pub(crate) user_id: Option<i64>,
    pub(crate) device_name: String,
    pub(crate) host: Arc<dyn Host>,
    pub(crate) sync: Box<dyn SyncApi>,
    pub(crate) previews: Mutex<HashMap<String, Preview>>,
}

#[uniffi::export]
impl FlexWeek {
    #[uniffi::constructor]
    pub fn open(
        db_path: String,
        device_name: String,
        host: Arc<dyn Host>,
    ) -> Result<Arc<Self>, FfiError> {
        let local = parse_local(&host.local_now())?;
        let monday = monday_of(&local.date_naive().format("%Y-%m-%d").to_string())
            .map_err(engine_failure)?;
        let path = Path::new(&db_path);
        flexweek_store::initialize(path, &monday).map_err(failure)?;
        let db = flexweek_store::open_connection(path).map_err(failure)?;
        let user_id = db
            .query_row("SELECT id FROM users ORDER BY id LIMIT 1", [], |row| {
                row.get(0)
            })
            .optional()
            .map_err(failure)?;
        let sync = NativeSync::new(path, &device_name, host.clone(), user_id);
        Ok(Arc::new(Self {
            db: Mutex::new(db),
            user_id,
            device_name,
            host,
            sync: Box::new(sync),
            previews: Mutex::new(HashMap::new()),
        }))
    }

    pub fn engine_version(&self) -> String {
        env!("CARGO_PKG_VERSION").to_string()
    }

    pub fn device_name(&self) -> String {
        self.device_name.clone()
    }

    pub fn today(&self, date: String, now_minute: i64) -> Result<String, FfiError> {
        crate::agenda::today(self, &date, now_minute)
    }

    pub fn focus_begin(
        &self,
        assignment_id: String,
        saved: String,
        replace: bool,
    ) -> Result<String, FfiError> {
        crate::focus::begin(self, &assignment_id, &saved, replace)
    }

    pub fn focus_pause(&self, state: String) -> Result<String, FfiError> {
        crate::focus::pause(self, &state)
    }

    pub fn focus_finish(&self, state: String) -> Result<String, FfiError> {
        crate::focus::finish(&state)
    }

    pub fn focus_restore(&self, saved: String) -> Result<String, FfiError> {
        crate::focus::restore(self, &saved)
    }

    pub fn focus_advance(&self, state: String, completed: bool) -> Result<String, FfiError> {
        crate::focus::advance(self, &state, completed)
    }

    pub fn focus_persist(&self, state: String) -> Result<String, FfiError> {
        crate::focus::persist(&state)
    }

    pub fn credit_focus(
        &self,
        assignment_id: String,
        work_min: i64,
        op_id: String,
    ) -> Result<String, FfiError> {
        crate::focus::credit(self, &assignment_id, work_min, &op_id)
    }

    pub fn set_block_done(
        &self,
        week_start: String,
        block_id: String,
        day: i64,
        done: bool,
        op_id: String,
    ) -> Result<(), FfiError> {
        crate::agenda::set_block_done(self, &week_start, &block_id, day, done, &op_id)
    }

    pub fn set_homework_done(&self, id: String, done: bool, op_id: String) -> Result<(), FfiError> {
        crate::agenda::set_homework_done(self, &id, done, &op_id)
    }

    pub fn upcoming_reminders(
        &self,
        from_local: String,
        hours: u32,
    ) -> Result<Vec<Reminder>, FfiError> {
        crate::reminders::upcoming(self, &from_local, hours)
    }

    pub fn settings_for_phone(&self) -> Result<String, FfiError> {
        let Some(user_id) = self.account_id() else {
            return Ok(json!({
                "reminders_enabled": true,
                "reminder_lead_min": 5,
                "reminder_sound": true,
                "alarms": [],
            })
            .to_string());
        };
        let db = self.db.lock().map_err(failure)?;
        let raw = flexweek_store::preference_row(&db, user_id)
            .map_err(failure)?
            .unwrap_or_else(|| "{}".to_string());
        let prefs: Value = serde_json::from_str(&raw).map_err(failure)?;
        let alarms = prefs
            .get("alarms_json")
            .and_then(Value::as_str)
            .map(serde_json::from_str::<Value>)
            .transpose()
            .map_err(failure)?
            .unwrap_or_else(|| json!([]));
        let result = json!({
            "theme": prefs.get("theme").cloned().unwrap_or(json!("system")),
            "reminders_enabled": prefs.get("reminders_enabled").and_then(Value::as_i64).unwrap_or(1) != 0,
            "reminder_lead_min": prefs.get("reminder_lead_min").and_then(Value::as_i64).unwrap_or(5),
            "reminder_sound": prefs.get("reminder_sound").and_then(Value::as_i64).unwrap_or(1) != 0,
            "timer_work_min": prefs.get("timer_work_min").and_then(Value::as_i64).unwrap_or(30),
            "timer_break_min": prefs.get("timer_break_min").and_then(Value::as_i64).unwrap_or(15),
            "alarms": alarms,
        });
        Ok(result.to_string())
    }

    pub fn set_reminder_lead(&self, minutes: i64) -> Result<(), FfiError> {
        if !(0..=60).contains(&minutes) {
            return Err(failure("Choose a reminder lead between 0 and 60 minutes."));
        }
        let user_id = require_user(self)?;
        let db = db_lock(self)?;
        db.execute(
            "UPDATE preferences SET reminder_lead_min=?1 WHERE user_id=?2",
            rusqlite::params![minutes, user_id],
        )
        .map_err(failure)?;
        drop(db);
        self.host.data_changed("preferences".into());
        Ok(())
    }

    pub fn sync_status(&self) -> String {
        self.sync.status()
    }

    pub fn sync_once(&self, deadline_ms: i64) -> String {
        self.sync.sync_once(deadline_ms)
    }

    pub fn pair_with_code(&self, code: String) -> String {
        self.sync.pair_with_code(&code)
    }

    pub fn pair_from_qr(&self, text: String) -> String {
        self.sync.pair_from_qr(&text)
    }

    pub fn cancel_sync(&self) -> String {
        self.sync.cancel_sync()
    }

    pub fn unlink(&self) -> String {
        self.sync.unlink()
    }

    pub fn join_from_pairing(&self, payload: String) -> String {
        self.sync.join_from_pairing(&payload)
    }

    pub fn save_homework(&self, draft_json: String, op_id: String) -> Result<String, FfiError> {
        crate::homework::save_homework(self, &draft_json, &op_id)
    }

    pub fn recent_titles(&self) -> Result<Vec<String>, FfiError> {
        crate::homework::recent_titles(self)
    }

    pub fn plan_week(&self, week_start: String, elapsed_ms: f64) -> Result<String, FfiError> {
        crate::plan_week::plan_week(self, &week_start, elapsed_ms)
    }

    pub fn accept_plan(&self, preview_id: String) -> Result<String, FfiError> {
        crate::plan_week::accept_plan(self, &preview_id)
    }

    pub fn running_late(
        &self,
        day: i64,
        minutes: i64,
        elapsed_ms: f64,
    ) -> Result<String, FfiError> {
        crate::running_late::running_late(self, day, minutes, elapsed_ms)
    }

    pub fn week_shape(&self, week_start: String) -> Result<String, FfiError> {
        crate::week_shape::week_shape(self, &week_start)
    }

    pub fn week_rows(&self, week_start: String) -> Result<String, FfiError> {
        crate::week_rows::week_rows(self, &week_start)
    }

    /// Move a block the student let go at `landing`. Returns JSON: `moved` with the block as saved,
    /// or not moved with the `problem` in words.
    pub fn hand_move(
        &self,
        week_start: String,
        landing: HandLanding,
        op_id: String,
    ) -> Result<String, FfiError> {
        crate::hand_move::hand_move(self, &week_start, &landing, &op_id)
    }

    /// The week's timed blocks, seven days Monday to Sunday, for the three-days-at-a-time Week.
    pub fn week_blocks(&self, week_start: String) -> Result<String, FfiError> {
        crate::hand_move::week_blocks(self, &week_start)
    }
}

impl FlexWeek {
    pub(crate) fn account_id(&self) -> Option<i64> {
        self.sync.account_id().or(self.user_id)
    }
}

pub(crate) fn require_user(week: &FlexWeek) -> Result<i64, FfiError> {
    week.account_id()
        .ok_or_else(|| failure("not paired: no account is stored on this phone"))
}

pub(crate) fn db_lock(week: &FlexWeek) -> Result<std::sync::MutexGuard<'_, Connection>, FfiError> {
    week.db.lock().map_err(failure)
}

pub(crate) fn parse_local(text: &str) -> Result<DateTime<FixedOffset>, FfiError> {
    DateTime::parse_from_rfc3339(text)
        .map_err(failure)
        .or_else(|_| {
            let naive = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S")
                .or_else(|_| NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M"))
                .map_err(failure)?;
            let offset = FixedOffset::east_opt(0).expect("zero offset is valid");
            Ok(DateTime::from_naive_utc_and_offset(naive, offset))
        })
}

pub(crate) fn parse_date(text: &str) -> Result<NaiveDate, FfiError> {
    NaiveDate::parse_from_str(text, "%Y-%m-%d").map_err(failure)
}

pub(crate) fn hex_preview(host: &dyn Host) -> String {
    format!("p-{}", crate::account::hex_id(&host.random_bytes(8)))
}

/// `YYYY-MM-DDTHH:MM`, the stamp `calendar.local_stamp` stores on finished homework.
pub(crate) fn local_stamp(host: &dyn Host) -> Result<String, FfiError> {
    Ok(parse_local(&host.local_now())?
        .format("%Y-%m-%dT%H:%M")
        .to_string())
}

#[cfg(test)]
pub(crate) mod tests_support {
    use super::*;
    use std::sync::atomic::{AtomicI64, Ordering};

    pub struct TestHost {
        pub local: String,
        pub now: AtomicI64,
        pub events: Mutex<Vec<String>>,
    }

    impl Host for TestHost {
        fn now_unix_ms(&self) -> i64 {
            self.now.load(Ordering::SeqCst)
        }

        fn local_now(&self) -> String {
            self.local.clone()
        }

        fn random_bytes(&self, count: u32) -> Vec<u8> {
            vec![0; count as usize]
        }

        fn data_changed(&self, scope: String) {
            self.events.lock().unwrap().push(scope);
        }
    }

    pub fn open_test(name: &str) -> (Arc<FlexWeek>, std::path::PathBuf) {
        open_at(name, "2026-10-12T15:40:00-07:00")
    }

    pub fn open_at(name: &str, local: &str) -> (Arc<FlexWeek>, std::path::PathBuf) {
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../target/ffi-tests");
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join(format!("{name}-{}.sqlite", std::process::id()));
        let _ = std::fs::remove_file(&path);
        flexweek_store::initialize(&path, "2026-10-12").unwrap();
        let db = flexweek_store::open_connection(&path).unwrap();
        let user_id = flexweek_store::insert_user(&db, "ada", "test").unwrap();
        flexweek_store::insert_preferences(&db, user_id, 2).unwrap();
        db.execute_batch("COMMIT").unwrap();
        let host = Arc::new(TestHost {
            local: local.into(),
            now: AtomicI64::new(1_792_000_000_000),
            events: Mutex::new(Vec::new()),
        });
        let week = FlexWeek {
            db: Mutex::new(flexweek_store::open_connection(&path).unwrap()),
            user_id: Some(user_id),
            device_name: "test-phone".into(),
            host,
            sync: Box::new(NotPairedSync),
            previews: Mutex::new(HashMap::new()),
        };
        (Arc::new(week), path)
    }

    pub fn save_week(week: &FlexWeek, start: &str, blocks: &Value) {
        let db = week.db.lock().unwrap();
        flexweek_store::save_week(&db, week.user_id.unwrap(), start, &blocks.to_string(), 0)
            .unwrap();
        let _ = db.execute_batch("COMMIT");
    }

    #[test]
    fn open_and_phone_settings_and_sync_stubs_have_safe_defaults() {
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../target/ffi-tests");
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join(format!("open-{}.sqlite", std::process::id()));
        let _ = std::fs::remove_file(&path);
        let host = Arc::new(TestHost {
            local: "2026-10-12T15:40:00-07:00".into(),
            now: AtomicI64::new(1_792_000_000_000),
            events: Mutex::new(Vec::new()),
        });
        let week = FlexWeek::open(
            path.to_string_lossy().to_string(),
            "Ada's phone".into(),
            host,
        )
        .unwrap();
        assert_eq!(week.device_name(), "Ada's phone");
        assert_eq!(week.engine_version(), env!("CARGO_PKG_VERSION"));
        let settings: Value = serde_json::from_str(&week.settings_for_phone().unwrap()).unwrap();
        assert_eq!(settings["reminders_enabled"], true);
        let agenda: Value =
            serde_json::from_str(&week.today("2026-10-12".into(), 15 * 60).unwrap()).unwrap();
        assert_eq!(agenda["days"].as_array().unwrap().len(), 7);
        let status: Value = serde_json::from_str(&week.sync_status()).unwrap();
        assert_eq!(status["paired"], false);
        assert_eq!(status["state"], "unreachable");
        assert_eq!(
            serde_json::from_str::<Value>(&week.sync_once(1000)).unwrap()["kind"],
            "not_paired"
        );
        assert_eq!(
            serde_json::from_str::<Value>(&week.cancel_sync()).unwrap()["ok"],
            true
        );
        assert_eq!(
            serde_json::from_str::<Value>(&week.unlink()).unwrap()["ok"],
            true
        );
        assert!(
            !path.with_file_name("device.key").exists(),
            "reading an unpaired core opens no endpoint"
        );
    }

    #[test]
    fn settings_for_phone_reads_store_preferences_and_alarm_rows() {
        let (week, _path) = open_test("phone-settings");
        let db = week.db.lock().unwrap();
        db.execute(
            "UPDATE preferences SET reminders_enabled=0, reminder_lead_min=15,
                alarms_json=?1 WHERE user_id=?2",
            [
                r#"[{"id":"wake","name":"Wake up","time":"07:00","days":[0],"enabled":true}]"#,
                &week.user_id.unwrap().to_string(),
            ],
        )
        .unwrap();
        let _ = db.execute_batch("COMMIT");
        drop(db);
        let settings: Value = serde_json::from_str(&week.settings_for_phone().unwrap()).unwrap();
        assert_eq!(settings["reminders_enabled"], false);
        assert_eq!(settings["reminder_lead_min"], 15);
        assert_eq!(settings["alarms"][0]["name"], "Wake up");
    }

    #[test]
    fn phone_reminder_lead_is_saved_and_rejects_out_of_range_values() {
        let (week, _path) = open_test("reminder-lead");
        week.set_reminder_lead(15).unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&week.settings_for_phone().unwrap()).unwrap()["reminder_lead_min"],
            15
        );
        assert_eq!(
            week.set_reminder_lead(61).unwrap_err().to_string(),
            "Choose a reminder lead between 0 and 60 minutes."
        );
    }
}
