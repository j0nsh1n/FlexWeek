use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use flexweek_sync::net::{NetError, NodeConfig, PairedHost, SyncService, Transport};
use serde_json::json;

use crate::Host;

pub(crate) trait SyncApi: Send + Sync {
    fn account_id(&self) -> Option<i64> {
        None
    }
    fn status(&self) -> String;
    fn sync_once(&self, deadline_ms: i64) -> String;
    fn pair_with_code(&self, code: &str) -> String;
    fn pair_from_qr(&self, text: &str) -> String;
    fn cancel_sync(&self) -> String;
    fn unlink(&self) -> String;
    fn join_from_pairing(&self, payload: &str) -> String;
}

pub(crate) struct NativeSync {
    db_path: PathBuf,
    device_name: String,
    host: Arc<dyn Host>,
    account: Mutex<Option<i64>>,
    service: Mutex<Option<Arc<SyncService>>>,
    transport: Transport,
}

fn error_json(error: NetError) -> String {
    json!({"ok": false, "kind": error.kind(), "error": error.to_string()}).to_string()
}

impl NativeSync {
    pub(crate) fn new(path: &Path, name: &str, host: Arc<dyn Host>, account: Option<i64>) -> Self {
        Self {
            db_path: path.to_owned(),
            device_name: name.into(),
            host,
            account: Mutex::new(account),
            service: Mutex::new(None),
            transport: Transport::Auto,
        }
    }

    fn service(&self) -> Result<Arc<SyncService>, NetError> {
        let mut slot = self.service.lock().expect("phone sync service");
        if let Some(service) = &*slot {
            return Ok(service.clone());
        }
        let mut config = NodeConfig::new(
            &self.db_path,
            &self.db_path.with_file_name("device.key"),
            &self.device_name,
            self.transport.clone(),
        );
        let host = self.host.clone();
        config.clock = Arc::new(move || host.now_unix_ms());
        let service = Arc::new(SyncService::start(config)?);
        *slot = Some(service.clone());
        Ok(service)
    }

    fn peers(&self) -> Result<Vec<flexweek_sync::Peer>, NetError> {
        let Some(user_id) = self.account_id() else {
            return Ok(Vec::new());
        };
        let db = flexweek_store::open_connection(&self.db_path)
            .map_err(|error| NetError::Protocol(error.to_string()))?;
        let exists: bool = db
            .query_row(
                "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE name='sync_peer')",
                [],
                |row| row.get(0),
            )
            .map_err(|error| NetError::Protocol(error.to_string()))?;
        if !exists {
            return Ok(Vec::new());
        }
        Ok(flexweek_sync::list_peers(&db, user_id)?
            .into_iter()
            .filter(|peer| !peer.revoked)
            .collect())
    }

    fn paired(&self, result: Result<PairedHost, NetError>) -> String {
        match result {
            Ok(paired) => {
                *self.account.lock().expect("phone account") = Some(paired.user_id);
                self.host.data_changed("account".into());
                json!({"ok": true, "peer_name": paired.host_name, "username": paired.username})
                    .to_string()
            }
            Err(error) => error_json(error),
        }
    }
}

impl SyncApi for NativeSync {
    fn account_id(&self) -> Option<i64> {
        *self.account.lock().expect("phone account")
    }

    fn status(&self) -> String {
        let peers = match self.peers() {
            Ok(peers) => peers,
            Err(error) => {
                return json!({"paired": false, "state": "unreachable", "line": error.to_string()})
                    .to_string();
            }
        };
        let peer = peers.first();
        let service = self.service.lock().expect("phone sync service").clone();
        let status = service.as_ref().map(|service| service.status());
        let last = status
            .as_ref()
            .and_then(|status| status.last_sync_ms)
            .or_else(|| peer.and_then(|peer| peer.last_seen.as_ref()?.parse().ok()));
        let (state, line) = if peer.is_none() {
            (
                "unreachable",
                "No computer is linked. Your saved week stays on this phone.".to_string(),
            )
        } else if status.as_ref().is_some_and(|status| status.syncing) {
            ("syncing", "Syncing…".into())
        } else if status
            .as_ref()
            .is_some_and(|status| status.last_error.is_some())
        {
            (
                "unreachable",
                "Your computer isn't reachable. Showing the last saved week.".into(),
            )
        } else if let Some(last) = last {
            let minutes = (self.host.now_unix_ms() - last).max(0) / 60_000;
            (
                "synced",
                if minutes == 0 {
                    "Synced just now".into()
                } else {
                    format!("Synced {minutes} min ago")
                },
            )
        } else {
            ("synced", "Not synced yet".into())
        };
        json!({
            "paired": peer.is_some(), "state": state, "line": line, "last_sync_ms": last,
            "has_account": self.account_id().is_some(),
            "peer_name": peer.map(|peer| peer.name.as_str()).unwrap_or("Your computer"),
            "paired_at": peer.map(|peer| peer.paired_at.as_str()).unwrap_or(""),
        })
        .to_string()
    }

    fn sync_once(&self, deadline_ms: i64) -> String {
        let result = (|| {
            if self.peers()?.is_empty() {
                return Err(NetError::NotPaired);
            }
            let service = self.service()?;
            let rows =
                service.sync_all(u64::try_from(deadline_ms).map_err(|_| NetError::Timeout)?)?;
            let mut applied = 0;
            for (device, result) in rows {
                match result {
                    Ok(summary) => applied += summary.applied,
                    Err(error) => {
                        if matches!(error, NetError::NotPaired) {
                            service.unlink(
                                self.account_id().ok_or(NetError::NotPaired)?,
                                &device,
                                false,
                            )?;
                        }
                        return Err(error);
                    }
                }
            }
            if applied > 0 {
                self.host.data_changed("sync".into());
            }
            Ok(json!({"ok": true, "applied": applied}).to_string())
        })();
        result.unwrap_or_else(error_json)
    }

    fn pair_with_code(&self, code: &str) -> String {
        self.paired(
            self.service()
                .and_then(|service| service.pair_with_code(code, &[], 45_000)),
        )
    }
    fn pair_from_qr(&self, text: &str) -> String {
        self.paired(
            self.service()
                .and_then(|service| service.pair_from_qr(text, 45_000)),
        )
    }
    fn cancel_sync(&self) -> String {
        if let Some(service) = self.service.lock().expect("phone sync service").as_ref() {
            service.cancel_sync();
        }
        json!({"ok": true}).to_string()
    }
    fn unlink(&self) -> String {
        let result = (|| {
            let peers = self.peers()?;
            if peers.is_empty() {
                return Ok(json!({"ok": true}).to_string());
            }
            let service = self.service()?;
            let user = self.account_id().ok_or(NetError::NotPaired)?;
            for peer in peers {
                service.unlink(user, &peer.device_id, true)?;
            }
            self.host.data_changed("sync".into());
            Ok(json!({"ok": true}).to_string())
        })();
        result.unwrap_or_else(error_json)
    }
    fn join_from_pairing(&self, payload: &str) -> String {
        self.pair_from_qr(payload)
    }
}

#[cfg(test)]
pub(crate) struct NotPairedSync;
#[cfg(test)]
impl SyncApi for NotPairedSync {
    fn status(&self) -> String {
        "not paired".into()
    }
    fn sync_once(&self, _deadline_ms: i64) -> String {
        "not paired".into()
    }
    fn pair_with_code(&self, _code: &str) -> String {
        "not paired".into()
    }
    fn pair_from_qr(&self, _text: &str) -> String {
        "not paired".into()
    }
    fn cancel_sync(&self) -> String {
        "not paired".into()
    }
    fn unlink(&self) -> String {
        "not paired".into()
    }
    fn join_from_pairing(&self, _payload: &str) -> String {
        "not paired".into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::FlexWeek;
    use crate::core::tests_support::TestHost;
    use serde_json::Value;
    use std::collections::HashMap;
    use std::sync::atomic::AtomicI64;

    #[test]
    fn a_phone_pairs_reads_new_homework_ticks_it_and_keeps_data_after_removal() {
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!(
            "../target/ffi-network-tests/{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let desktop_path = dir.join("desktop.db");
        let phone_path = dir.join("phone.db");
        let _ = std::fs::remove_file(&desktop_path);
        let _ = std::fs::remove_file(&phone_path);
        flexweek_store::initialize(&desktop_path, "2026-10-12").unwrap();
        flexweek_store::initialize(&phone_path, "2026-10-12").unwrap();
        let desktop_db = flexweek_store::open_connection(&desktop_path).unwrap();
        let user = flexweek_store::insert_user(&desktop_db, "ada", "test").unwrap();
        flexweek_store::insert_preferences(&desktop_db, user, 2).unwrap();
        desktop_db.execute_batch("COMMIT").unwrap();
        let host = Arc::new(TestHost {
            local: "2026-10-13T15:40:00".into(),
            now: AtomicI64::new(1_792_000_000_000),
            events: Mutex::new(Vec::new()),
        });
        let transport = Transport::LanOnly {
            bind: Some("127.0.0.1:0".parse().unwrap()),
        };
        let mut cfg = NodeConfig::new(
            &desktop_path,
            &dir.join("desktop.key"),
            "Desk",
            transport.clone(),
        );
        let clock = host.clone();
        cfg.clock = Arc::new(move || clock.now_unix_ms());
        let desktop = SyncService::start(cfg).unwrap();
        let mut native = NativeSync::new(&phone_path, "Phone", host.clone(), None);
        native.transport = transport;
        let phone_service = native.service().unwrap();
        let phone = FlexWeek {
            db: Mutex::new(flexweek_store::open_connection(&phone_path).unwrap()),
            user_id: None,
            device_name: "Phone".into(),
            host: host.clone(),
            sync: Box::new(native),
            previews: Mutex::new(HashMap::new()),
        };
        let offer = desktop.pair_start(user).unwrap();
        let pair: Value = serde_json::from_str(&phone.pair_from_qr(offer.qr)).unwrap();
        assert_eq!(pair["ok"], true, "{pair}");
        assert_eq!(phone.account_id(), Some(user));
        assert_eq!(
            serde_json::from_str::<Value>(&phone.sync_status()).unwrap()["paired"],
            true
        );
        flexweek_store::insert_assignment(&desktop_db, user, "essay",
            r#"{"id":"essay","title":"History essay","due":"2026-10-14T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#).unwrap();
        flexweek_store::save_week(&desktop_db, user, "2026-10-12",
            r#"[{"id":"essay-session","assignment_id":"essay","title":"History essay","kind":"flexible","days":[1],"start":"19:00","duration_min":60},{"id":"school","title":"School tomorrow","kind":"locked","days":[2],"start":"18:00","duration_min":30}]"#, 0).unwrap();
        desktop_db.execute_batch("COMMIT").unwrap();
        let synced: Value = serde_json::from_str(&phone.sync_once(15_000)).unwrap();
        assert_eq!(synced["ok"], true, "{synced}");
        let day: Value =
            serde_json::from_str(&phone.today("2026-10-13".into(), 15 * 60 + 40).unwrap()).unwrap();
        assert_eq!(day["rows"][0]["title"], "History essay");
        assert_eq!(day["rows"][0]["assignment_id"], "essay");
        phone
            .set_homework_done("essay".into(), true, "phone-tick".into())
            .unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&phone.sync_once(15_000)).unwrap()["ok"],
            true
        );
        let body: String = desktop_db
            .query_row("SELECT body FROM assignments WHERE id='essay'", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&body).unwrap()["completed"],
            true
        );
        desktop
            .unlink(user, phone_service.device_id(), true)
            .unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&phone.sync_status()).unwrap()["paired"],
            false
        );
        let kept: Value =
            serde_json::from_str(&phone.today("2026-10-13".into(), 21 * 60).unwrap()).unwrap();
        assert_eq!(kept["rows"][0]["title"], "History essay");
        assert_eq!(kept["rows"][0]["done"], true);
        assert_eq!(
            serde_json::from_str::<Value>(&phone.sync_once(1000)).unwrap()["kind"],
            "not_paired"
        );
        let reminders = phone
            .upcoming_reminders("2026-10-13T21:00".into(), 48)
            .unwrap();
        assert_eq!(reminders.len(), 1);
        assert_eq!(reminders[0].title, "School tomorrow");
        assert_eq!(reminders[0].local_time, "2026-10-14T17:55");
        assert_eq!(reminders[0].start_time, "18:00");
        assert_eq!(reminders[0].duration_min, Some(30));
        assert_eq!(
            *host.events.lock().unwrap(),
            vec!["account", "sync", "homework"]
        );
        phone_service.stop();
        desktop.stop();
    }
}
