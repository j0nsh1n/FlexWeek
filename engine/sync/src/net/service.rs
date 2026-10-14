//! The long-lived object both apps hold: the permanent endpoint, its listener, the optional scan
//! loop, and the blocking calls Kotlin and Python make.

use std::collections::HashMap;
use std::net::{IpAddr, SocketAddr};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use iroh::address_lookup::MemoryLookup;
use iroh::endpoint::presets;
use iroh::protocol::Router;
use iroh::{Endpoint, EndpointAddr, EndpointId, RelayMode, SecretKey};
use tokio::sync::watch;
use tokio::time::timeout;

use super::identity::{ensure_device, load_or_create_key};
use super::pair::{self, PairHost, PairOffer, PairStatus, PairedHost};
use super::protocol::{SYNC_ALPN, SYNC_DEADLINE_MS};
use super::runtime::block_on;
use super::session::{self, SyncHandler, scan_all};
use super::{NetError, NetResult, NodeConfig, Transport, blocking, open_db, qr};
use crate::{Peer, SyncError, list_peers, revoke_peer};

pub(crate) struct Ctx {
    pub cfg: NodeConfig,
    pub device_id: String,
    pub endpoint: Endpoint,
    pub lookup: MemoryLookup,
    pub generation: AtomicU64,
    pub cancel: watch::Sender<u64>,
    pub status: Mutex<StatusInner>,
    pub hints: Mutex<HashMap<String, Vec<String>>>,
    pub pairing: Mutex<Option<PairHost>>,
    pub stopping: AtomicBool,
}

#[derive(Default)]
pub(crate) struct StatusInner {
    running: usize,
    last_sync_ms: Option<i64>,
    last_error: Option<String>,
    scan_error: Option<String>,
}

impl Ctx {
    /// Remembers where a peer's permanent endpoint can be reached on the local network, in memory
    /// for iroh and in a small file so a restart in LAN-only mode still finds it.
    pub(crate) fn add_hints(&self, endpoint_id: &str, addrs: &[SocketAddr]) {
        let Ok(id) = endpoint_id.parse::<EndpointId>() else {
            return;
        };
        if addrs.is_empty() {
            return;
        }
        let mut address = EndpointAddr::new(id);
        for addr in addrs {
            address = address.with_ip_addr(*addr);
        }
        self.lookup.add_endpoint_info(address);
        let mut hints = self.hints.lock().expect("hints");
        hints.insert(
            endpoint_id.to_owned(),
            addrs.iter().map(SocketAddr::to_string).collect(),
        );
        let json = serde_json::to_vec(&*hints).unwrap_or_default();
        let path = self.cfg.hints_path();
        let temp = path.with_extension("tmp");
        if std::fs::write(&temp, json).is_ok() {
            let _ = std::fs::rename(&temp, &path);
        }
    }

    fn check_running(&self) -> NetResult<()> {
        if self.stopping.load(Ordering::Relaxed) {
            Err(NetError::Stopped)
        } else {
            Ok(())
        }
    }
}

pub(crate) async fn bind_endpoint(
    transport: &Transport,
    secret: SecretKey,
    lookup: Option<&MemoryLookup>,
) -> NetResult<Endpoint> {
    let builder = match transport {
        Transport::Auto => Endpoint::builder(presets::N0),
        Transport::LanOnly { bind } => {
            let builder = Endpoint::builder(presets::Minimal).relay_mode(RelayMode::Disabled);
            match bind {
                Some(addr) => builder
                    .clear_ip_transports()
                    .bind_addr(*addr)
                    .map_err(|e| NetError::Protocol(format!("bad bind address: {e}")))?,
                None => builder,
            }
        }
    };
    let builder = builder.secret_key(secret);
    let builder = match lookup {
        Some(lookup) => builder.address_lookup(lookup.clone()),
        None => builder,
    };
    builder
        .bind()
        .await
        .map_err(|e| NetError::Protocol(format!("could not open the network endpoint: {e}")))
}

/// Direct addresses other devices on this network can try. Waits briefly for the endpoint to learn
/// its interfaces, never for a relay.
pub(crate) async fn local_addrs(
    endpoint: &Endpoint,
    transport: &Transport,
    max: usize,
) -> Vec<SocketAddr> {
    let loopback_ok =
        matches!(transport, Transport::LanOnly { bind: Some(a) } if a.ip().is_loopback());
    let usable = |addr: &SocketAddr| match addr.ip() {
        IpAddr::V4(ip) => {
            !ip.is_unspecified() && !ip.is_link_local() && (loopback_ok || !ip.is_loopback())
        }
        IpAddr::V6(ip) => {
            !ip.is_unspecified()
                && (ip.segments()[0] & 0xffc0) != 0xfe80
                && (loopback_ok || !ip.is_loopback())
        }
    };
    let mut found = Vec::new();
    for _ in 0..20 {
        found = endpoint
            .addr()
            .ip_addrs()
            .copied()
            .filter(|addr| usable(addr))
            .collect();
        if !found.is_empty() {
            break;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    found.sort_by_key(|addr| (addr.is_ipv6(), *addr));
    found.dedup();
    found.truncate(max);
    found
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SyncSummary {
    /// Records this device sent.
    pub sent: usize,
    /// Records the peer sent.
    pub received: usize,
    /// Of those, how many changed this device's data.
    pub applied: usize,
    /// Records this device set aside as unusable ("1 item could not be applied").
    pub quarantined: usize,
    /// Records this device set aside because the sender's clock is more than 24 hours ahead.
    pub clock_skewed: usize,
    pub exchanges: usize,
}

#[derive(Clone, Debug)]
pub struct SyncStatus {
    pub device_id: String,
    pub listening: bool,
    pub syncing: bool,
    pub last_sync_ms: Option<i64>,
    pub last_error: Option<String>,
    /// Rises whenever a batch changed this device's data, so the desktop knows to reload.
    pub generation: u64,
    pub pairing: PairStatus,
}

pub struct SyncService {
    ctx: Arc<Ctx>,
    router: Mutex<Option<Router>>,
    scanner: Mutex<Option<tokio::task::JoinHandle<()>>>,
}

struct Running<'a>(&'a Ctx);

impl<'a> Running<'a> {
    fn begin(ctx: &'a Ctx) -> Self {
        ctx.status.lock().expect("status").running += 1;
        Self(ctx)
    }

    fn finish<T>(self, result: &NetResult<T>) {
        let mut status = self.0.status.lock().expect("status");
        match result {
            Ok(_) => {
                status.last_sync_ms = Some((self.0.cfg.clock)());
                status.last_error = None;
            }
            Err(error) => status.last_error = Some(error.to_string()),
        }
    }
}

impl Drop for Running<'_> {
    fn drop(&mut self) {
        let mut status = self.0.status.lock().expect("status");
        status.running = status.running.saturating_sub(1);
    }
}

/// Ends `work` at the deadline or when `cancel_sync` is called after this point.
async fn limited<T>(
    ctx: &Ctx,
    cancel_base: u64,
    deadline_ms: u64,
    work: impl std::future::Future<Output = NetResult<T>>,
) -> NetResult<T> {
    let mut cancelled = ctx.cancel.subscribe();
    let cancel = async {
        let _ = cancelled.wait_for(|count| *count != cancel_base).await;
    };
    tokio::select! {
        result = timeout(Duration::from_millis(deadline_ms), work) => {
            result.unwrap_or(Err(NetError::Timeout))
        }
        () = cancel => Err(NetError::Cancelled),
    }
}

impl SyncService {
    /// Opens the key, the endpoint and the listener. Blocking.
    pub fn start(cfg: NodeConfig) -> NetResult<Self> {
        block_on(Self::start_async(cfg))
    }

    async fn start_async(cfg: NodeConfig) -> NetResult<Self> {
        let key_path = cfg.key_path.clone();
        let secret = blocking(move || load_or_create_key(&key_path)).await?;
        let lookup = MemoryLookup::new();
        let endpoint = bind_endpoint(&cfg.transport, secret, Some(&lookup)).await?;
        let device_id = endpoint.id().to_string();
        let (path, name, id) = (
            cfg.db_path.clone(),
            cfg.device_name.clone(),
            device_id.clone(),
        );
        if let Err(error) = blocking(move || ensure_device(&open_db(&path)?, &id, &name)).await {
            let _ = timeout(Duration::from_secs(2), endpoint.close()).await;
            return Err(error);
        }
        let hints: HashMap<String, Vec<String>> = std::fs::read(cfg.hints_path())
            .ok()
            .and_then(|bytes| serde_json::from_slice(&bytes).ok())
            .unwrap_or_default();
        for (id, addrs) in &hints {
            if let Ok(id) = id.parse::<EndpointId>() {
                let mut address = EndpointAddr::new(id);
                for addr in addrs.iter().filter_map(|a| a.parse::<SocketAddr>().ok()) {
                    address = address.with_ip_addr(addr);
                }
                lookup.add_endpoint_info(address);
            }
        }
        let interval = cfg.scan_interval;
        let ctx = Arc::new(Ctx {
            cfg,
            device_id,
            endpoint: endpoint.clone(),
            lookup,
            generation: AtomicU64::new(0),
            cancel: watch::channel(0).0,
            status: Mutex::new(StatusInner::default()),
            hints: Mutex::new(hints),
            pairing: Mutex::new(None),
            stopping: AtomicBool::new(false),
        });
        let router = Router::builder(endpoint)
            .accept(SYNC_ALPN, SyncHandler(ctx.clone()))
            .spawn();
        let scanner = interval.map(|interval| tokio::spawn(scan_loop(ctx.clone(), interval)));
        Ok(Self {
            ctx,
            router: Mutex::new(Some(router)),
            scanner: Mutex::new(scanner),
        })
    }

    pub fn device_id(&self) -> &str {
        &self.ctx.device_id
    }

    /// Stops listening, ends any running sync and closes the endpoint. Safe to call twice.
    pub fn stop(&self) {
        if self.ctx.stopping.swap(true, Ordering::Relaxed) {
            return;
        }
        self.ctx.cancel.send_modify(|count| *count += 1);
        if let Some(scanner) = self.scanner.lock().expect("scanner").take() {
            scanner.abort();
        }
        let pairing = self.ctx.pairing.lock().expect("pairing slot").take();
        let router = self.router.lock().expect("router").take();
        let endpoint = self.ctx.endpoint.clone();
        block_on(async move {
            if let Some(pairing) = pairing {
                pairing.shutdown(true).await;
            }
            if let Some(router) = router {
                let _ = timeout(Duration::from_secs(3), router.shutdown()).await;
            }
            let _ = timeout(Duration::from_secs(2), endpoint.close()).await;
        });
    }

    /// Pulls and pushes with one paired device until neither has more. Blocking. Ends with
    /// `NetError::Timeout` at `deadline_ms` (callers pass `SYNC_DEADLINE_MS`) and with
    /// `NetError::Cancelled` when `cancel_sync` is called.
    pub fn sync_once(&self, peer_device_id: &str, deadline_ms: u64) -> NetResult<SyncSummary> {
        self.ctx.check_running()?;
        let base = *self.ctx.cancel.borrow();
        let running = Running::begin(&self.ctx);
        let ctx = self.ctx.clone();
        let result = block_on(async {
            limited(
                &ctx,
                base,
                deadline_ms,
                session::sync_with(&ctx, peer_device_id),
            )
            .await
        });
        running.finish(&result);
        result
    }

    /// `sync_once` with every paired, not removed device, one after the other. `cancel_sync`
    /// ends the one running and skips the rest.
    pub fn sync_all(&self, deadline_ms: u64) -> NetResult<Vec<(String, NetResult<SyncSummary>)>> {
        let base = *self.ctx.cancel.borrow();
        let mut results = Vec::new();
        for peer in self.all_peers()? {
            let cancelled = *self.ctx.cancel.borrow() != base;
            let result = if cancelled {
                Err(NetError::Cancelled)
            } else {
                self.sync_once(&peer.device_id, deadline_ms)
            };
            results.push((peer.device_id, result));
        }
        Ok(results)
    }

    /// Ends a running `sync_once` at once. Does nothing when none is running.
    pub fn cancel_sync(&self) {
        self.ctx.cancel.send_modify(|count| *count += 1);
    }

    pub fn status(&self) -> SyncStatus {
        let (running, last_sync_ms, last_error) = {
            let status = self.ctx.status.lock().expect("status");
            (
                status.running,
                status.last_sync_ms,
                status.last_error.clone(),
            )
        };
        let now = (self.ctx.cfg.clock)();
        let pairing = self
            .ctx
            .pairing
            .lock()
            .expect("pairing slot")
            .as_ref()
            .map_or(PairStatus::Idle, |host| host.status(now));
        SyncStatus {
            device_id: self.ctx.device_id.clone(),
            listening: !self.ctx.stopping.load(Ordering::Relaxed),
            syncing: running > 0,
            last_sync_ms,
            last_error,
            generation: self.generation(),
            pairing,
        }
    }

    /// Addresses on this machine other devices can try (shown as the typed "Desktop address").
    pub fn local_addrs(&self) -> Vec<SocketAddr> {
        block_on(local_addrs(&self.ctx.endpoint, &self.ctx.cfg.transport, 6))
    }

    pub fn generation(&self) -> u64 {
        self.ctx.generation.load(Ordering::Relaxed)
    }

    pub fn peers(&self, user_id: i64) -> NetResult<Vec<Peer>> {
        Ok(list_peers(&open_db(&self.ctx.cfg.db_path)?, user_id)?)
    }

    fn all_peers(&self) -> NetResult<Vec<Peer>> {
        let conn = open_db(&self.ctx.cfg.db_path)?;
        let users: Vec<i64> = conn
            .prepare("SELECT user_id FROM sync_account")
            .map_err(SyncError::from)?
            .query_map([], |row| row.get(0))
            .map_err(SyncError::from)?
            .collect::<Result<_, _>>()
            .map_err(SyncError::from)?;
        let mut peers = Vec::new();
        for user_id in users {
            peers.extend(
                list_peers(&conn, user_id)?
                    .into_iter()
                    .filter(|p| !p.revoked),
            );
        }
        Ok(peers)
    }

    /// Where to find a paired device on the local network (the typed "Desktop address").
    pub fn set_peer_addrs(&self, endpoint_id: &str, addrs: &[SocketAddr]) {
        self.ctx.add_hints(endpoint_id, addrs);
    }

    /// Starts a pairing window for this account: a new code, a QR text, 5 minutes, 3 tries, one
    /// use. Replaces any earlier window.
    pub fn pair_start(&self, user_id: i64) -> NetResult<PairOffer> {
        self.ctx.check_running()?;
        let ctx = self.ctx.clone();
        block_on(async move { pair::start(&ctx, user_id).await })
    }

    pub fn pair_status(&self) -> PairStatus {
        self.status().pairing
    }

    pub fn pair_cancel(&self) {
        let host = self.ctx.pairing.lock().expect("pairing slot").take();
        if let Some(host) = host {
            block_on(host.shutdown(true));
        }
    }

    /// The phone's side, typed. `hints` are LAN addresses to try first; may be empty.
    pub fn pair_with_code(
        &self,
        code: &str,
        hints: &[SocketAddr],
        deadline_ms: u64,
    ) -> NetResult<PairedHost> {
        self.ctx.check_running()?;
        let base = *self.ctx.cancel.borrow();
        let ctx = self.ctx.clone();
        block_on(async {
            limited(&ctx, base, deadline_ms, pair::pair_dial(&ctx, code, hints)).await
        })
    }

    /// The phone's side, from the scanned text.
    pub fn pair_from_qr(&self, text: &str, deadline_ms: u64) -> NetResult<PairedHost> {
        let payload = qr::parse(text)?;
        self.pair_with_code(&payload.code, &payload.hints, deadline_ms)
    }

    /// Removes a device. It keeps what it has and gets nothing new. When `notify` is set, tries
    /// for a few seconds to tell it; the answer says whether it was told.
    pub fn unlink(&self, user_id: i64, device_id: &str, notify: bool) -> NetResult<bool> {
        let (path, wanted) = (self.ctx.cfg.db_path.clone(), device_id.to_owned());
        let peer = block_on(blocking(move || {
            let conn = open_db(&path)?;
            let peer = list_peers(&conn, user_id)?
                .into_iter()
                .find(|peer| peer.device_id == wanted)
                .ok_or(NetError::NotPaired)?;
            revoke_peer(&conn, user_id, &wanted)?;
            Ok(peer)
        }))?;
        if !notify || peer.revoked {
            return Ok(false);
        }
        let ctx = self.ctx.clone();
        let base = *ctx.cancel.borrow();
        let told = block_on(async {
            limited(&ctx, base, 3_000, session::bye(&ctx, user_id, &peer)).await
        });
        Ok(told.is_ok())
    }
}

impl Drop for SyncService {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Every `interval`, scan when another connection has committed since the last look. SQLite's
/// `data_version` only changes for commits made by other connections, which is what a private
/// connection that never writes sees of the desktop's own edits.
async fn scan_loop(ctx: Arc<Ctx>, interval: Duration) {
    let mut conn: Option<rusqlite::Connection> = None;
    let mut seen: Option<i64> = None;
    loop {
        tokio::time::sleep(interval).await;
        if ctx.stopping.load(Ordering::Relaxed) {
            return;
        }
        let (path, clock, held, last) = (
            ctx.cfg.db_path.clone(),
            ctx.cfg.clock.clone(),
            conn.take(),
            seen,
        );
        let step = blocking(move || {
            let mut db = match held {
                Some(db) => db,
                None => open_db(&path)?,
            };
            let version: i64 = db
                .query_row("PRAGMA data_version", [], |row| row.get(0))
                .map_err(SyncError::from)?;
            if last != Some(version) {
                scan_all(&mut db, clock())?;
            }
            Ok((db, version))
        })
        .await;
        match step {
            Ok((db, version)) => {
                conn = Some(db);
                seen = Some(version);
                ctx.status.lock().expect("status").scan_error = None;
            }
            Err(error) => {
                ctx.status.lock().expect("status").scan_error = Some(error.to_string());
            }
        }
    }
}

/// The default whole-sync limit, for callers that have no reason to choose another.
pub const DEFAULT_SYNC_DEADLINE_MS: u64 = SYNC_DEADLINE_MS;
