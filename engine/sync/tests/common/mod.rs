#![allow(dead_code)]

use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicI64, AtomicUsize, Ordering};

use flexweek_sync::net::{NodeConfig, SyncService, Transport};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};

static NEXT: AtomicUsize = AtomicUsize::new(0);

pub fn loopback() -> Transport {
    Transport::LanOnly {
        bind: Some("127.0.0.1:0".parse().unwrap()),
    }
}

pub fn scratch(label: &str) -> PathBuf {
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!(
        "net-{}-{}-{label}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// A clock the test can move; it starts at the real time so stamps pass the 24 hour guard.
#[derive(Clone)]
pub struct TestClock(pub Arc<AtomicI64>);

impl TestClock {
    pub fn new() -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;
        Self(Arc::new(AtomicI64::new(now)))
    }

    pub fn now(&self) -> i64 {
        self.0.load(Ordering::SeqCst)
    }

    pub fn advance(&self, ms: i64) {
        self.0.fetch_add(ms, Ordering::SeqCst);
    }
}

pub struct Device {
    pub dir: PathBuf,
    pub db: PathBuf,
    pub key: PathBuf,
    pub clock: TestClock,
    pub service: Arc<SyncService>,
}

impl Device {
    pub fn db(&self) -> Connection {
        flexweek_store::open_connection(&self.db).unwrap()
    }

    pub fn id(&self) -> String {
        self.service.device_id().to_owned()
    }
}

/// A database with the schema `flexweek-store` really creates and, when asked, the one account.
pub fn make_db(dir: &Path, account: bool) -> PathBuf {
    let path = dir.join("flexweek.db");
    flexweek_store::initialize(&path, "2026-10-12").unwrap();
    if account {
        let conn = flexweek_store::open_connection(&path).unwrap();
        conn.execute(
            "INSERT INTO users(id, username, password_hash) VALUES (1, 'student', 'hash')",
            [],
        )
        .unwrap();
        conn.execute("INSERT INTO preferences(user_id) VALUES (1)", [])
            .unwrap();
    }
    path
}

pub fn config(dir: &Path, name: &str, clock: &TestClock) -> NodeConfig {
    let mut cfg = NodeConfig::new(
        &dir.join("flexweek.db"),
        &dir.join("sync").join("device.key"),
        name,
        loopback(),
    );
    let clock = clock.clone();
    cfg.clock = Arc::new(move || clock.now());
    cfg
}

pub fn device(name: &str, account: bool) -> Device {
    let dir = scratch(name);
    let db = make_db(&dir, account);
    let clock = TestClock::new();
    let cfg = config(&dir, name, &clock);
    let key = cfg.key_path.clone();
    let service = Arc::new(SyncService::start(cfg).unwrap());
    Device {
        dir,
        db,
        key,
        clock,
        service,
    }
}

pub fn assignment(id: &str, title: &str, notes: &str) -> Value {
    json!({"id": id, "title": title, "due": "2026-10-13", "estimate_min": 30, "notes": notes})
}

pub fn put_assignment(conn: &Connection, id: &str, title: &str, notes: &str) {
    conn.execute("INSERT INTO assignments(user_id,id,body) VALUES (1,?1,?2) ON CONFLICT(user_id,id) DO UPDATE SET body=excluded.body", params![id, assignment(id, title, notes).to_string()]).unwrap();
}

pub fn get_assignment(conn: &Connection, id: &str) -> Option<Value> {
    conn.query_row(
        "SELECT body FROM assignments WHERE user_id=1 AND id=?1",
        [id],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .unwrap()
    .map(|body| serde_json::from_str(&body).unwrap())
}

pub fn hints_of(qr: &str) -> Vec<SocketAddr> {
    flexweek_sync::net::qr::parse(qr).unwrap().hints
}

/// Pairs `phone` with `desktop` through the QR text and returns the desktop's device id.
pub fn pair(desktop: &Device, phone: &Device) -> String {
    let offer = desktop.service.pair_start(1).unwrap();
    let host = phone.service.pair_from_qr(&offer.qr, 20_000).unwrap();
    assert_eq!(host.host_device_id, desktop.id());
    host.host_device_id
}

pub fn raw_endpoint() -> iroh::Endpoint {
    use iroh::endpoint::presets;
    flexweek_sync::net::runtime::block_on(async {
        iroh::Endpoint::builder(presets::Minimal)
            .relay_mode(iroh::RelayMode::Disabled)
            .clear_ip_transports()
            .bind_addr("127.0.0.1:0")
            .unwrap()
            .secret_key(iroh::SecretKey::generate())
            .bind()
            .await
            .unwrap()
    })
}

/// Speaks the pairing wire format directly, so a test can send a proof made from another code,
/// claim another endpoint's id, or walk away without confirming, which the real client never does.
pub struct RawPair<'a> {
    client: &'a iroh::Endpoint,
    qr: &'a str,
    key_code: &'a str,
    proof_code: &'a str,
    claim: Option<&'a iroh::Endpoint>,
    device_id: Option<&'a str>,
    confirm: bool,
}

impl<'a> RawPair<'a> {
    pub fn new(client: &'a iroh::Endpoint, qr: &'a str, code: &'a str) -> Self {
        Self {
            client,
            qr,
            key_code: code,
            proof_code: code,
            claim: None,
            device_id: None,
            confirm: true,
        }
    }

    pub fn proof_from(mut self, code: &'a str) -> Self {
        self.proof_code = code;
        self
    }

    pub fn claiming(mut self, other: &'a iroh::Endpoint) -> Self {
        self.claim = Some(other);
        self
    }

    pub fn device_id(mut self, id: &'a str) -> Self {
        self.device_id = Some(id);
        self
    }

    pub fn without_confirming(mut self) -> Self {
        self.confirm = false;
        self
    }

    pub fn run(self) -> Value {
        let confirm = self.confirm;
        let session = self.open();
        let reply = session.reply.clone();
        if confirm && reply["ok"] == true {
            session.confirm();
        } else {
            session.leave();
        }
        reply
    }

    /// Sends the hello and returns with the reply read, the connection still open.
    pub fn open(self) -> RawSession {
        use flexweek_sync::net::protocol::{PAIR_ALPN, derive_pair_keys, hello_proof};
        flexweek_sync::net::runtime::block_on(async {
            let payload = flexweek_sync::net::qr::parse(self.qr).unwrap();
            let host_keys = derive_pair_keys(self.key_code).unwrap();
            let proof_keys = derive_pair_keys(self.proof_code).unwrap();
            let mut address = iroh::EndpointAddr::new(host_keys.secret.public());
            for hint in &payload.hints {
                address = address.with_ip_addr(*hint);
            }
            let connection = self.client.connect(address, PAIR_ALPN).await.unwrap();
            let claimed = self.claim.unwrap_or(self.client).id();
            let device_id = self
                .device_id
                .map_or_else(|| claimed.to_string(), str::to_owned);
            let nonce = [7u8; 16];
            let proof = hello_proof(
                &proof_keys.proof_key,
                &nonce,
                claimed.as_bytes(),
                &device_id,
                "Raw phone",
            );
            let hello = json!({
                "proto": 1, "device_id": device_id, "device_name": "Raw phone",
                "endpoint_id": claimed.to_string(), "nonce": hex_of(&nonce), "proof": hex_of(&proof),
            });
            let (mut send, mut recv) = connection.open_bi().await.unwrap();
            send.write_all(hello.to_string().as_bytes()).await.unwrap();
            send.finish().unwrap();
            let reply: Value =
                serde_json::from_slice(&recv.read_to_end(1 << 20).await.unwrap()).unwrap();
            RawSession { connection, reply }
        })
    }
}

pub struct RawSession {
    pub connection: iroh::endpoint::Connection,
    pub reply: Value,
}

impl RawSession {
    pub fn confirm(self) {
        flexweek_sync::net::runtime::block_on(async {
            let (mut send, mut recv) = self.connection.open_bi().await.unwrap();
            send.write_all(br#"{"op":"confirm"}"#).await.unwrap();
            send.finish().unwrap();
            let answer: Value =
                serde_json::from_slice(&recv.read_to_end(1 << 16).await.unwrap()).unwrap();
            assert_eq!(answer["ok"], true);
            self.connection.close(0u32.into(), b"done");
        });
    }

    pub fn leave(self) {
        self.connection.close(0u32.into(), b"done");
    }
}

fn hex_of(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
