//! Pairing: a signed-in desktop shows an 8-digit code; the phone proves it knows the code and
//! both sides record each other. The code is stretched into the pairing endpoint's secret key, so
//! the phone can find that endpoint from the digits alone and nobody can reach it without them.
//!
//! A phone that types a wrong code derives a different endpoint id and never reaches this
//! endpoint at all: the desktop sees nothing and the phone sees "could not be reached". Tries are
//! counted for connections that do reach it and fail the proof, which is what stops a client that
//! has the endpoint's key (a leaked code) from guessing further.

use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use iroh::endpoint::Connection;
use iroh::protocol::{AcceptError, ProtocolHandler, Router};
use iroh::{EndpointAddr, EndpointId};
use rusqlite::params;
use serde_json::{Value, json};
use tokio::time::timeout;

use super::identity::fill_random;
use super::protocol::{
    CLOSE_DONE, CONNECT_TIMEOUT_MS, MAX_MESSAGE_BYTES, PAIR_ALPN, PAIR_EXPIRY_MS, PAIR_MAX_TRIES,
    PROTO_VERSION, decode, derive_pair_keys, display_code, encode, hello_proof,
    hello_proof_matches, normalize_code, refusal,
};
use super::service::{Ctx, bind_endpoint, local_addrs};
use super::session::{scan_and_export, touch_peer};
use super::{NetError, NetResult, PairRefusal, blocking, open_db, qr};
use crate::{Batch, Peer, SyncError, account_uuid, apply_batch, scan, set_account, upsert_peer};

/// How long after the code expires the pairing endpoint keeps answering, so a late phone gets
/// "expired" instead of silence. Measured in real time, not by the injectable clock.
const GRACE: Duration = Duration::from_secs(30);

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PairOffer {
    /// Eight digits, no spaces.
    pub code: String,
    /// "1234 5678", for the screen.
    pub display_code: String,
    /// The QR text; the desktop draws it.
    pub qr: String,
    pub expires_at_ms: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PairedPeer {
    pub user_id: i64,
    pub device_id: String,
    pub device_name: String,
    pub endpoint_id: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PairStatus {
    Idle,
    Waiting { expires_at_ms: i64, tries_left: u32 },
    Paired(PairedPeer),
    Expired,
    TooManyTries,
    Cancelled,
}

/// What the phone learns when pairing succeeds.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PairedHost {
    pub user_id: i64,
    pub account_uuid: String,
    pub username: String,
    pub host_device_id: String,
    pub host_name: String,
    pub host_endpoint_id: String,
}

struct PairState {
    user_id: i64,
    proof_key: [u8; 32],
    expires_at_ms: i64,
    tries: u32,
    paired: Option<PairedPeer>,
    cancelled: bool,
}

pub(crate) struct PairHost {
    state: Arc<Mutex<PairState>>,
    router: Router,
    reaper: tokio::task::JoinHandle<()>,
}

impl PairHost {
    pub(crate) fn status(&self, now_ms: i64) -> PairStatus {
        let state = self.state.lock().expect("pair state");
        if let Some(peer) = &state.paired {
            PairStatus::Paired(peer.clone())
        } else if state.cancelled {
            PairStatus::Cancelled
        } else if state.tries >= PAIR_MAX_TRIES {
            PairStatus::TooManyTries
        } else if now_ms >= state.expires_at_ms {
            PairStatus::Expired
        } else {
            PairStatus::Waiting {
                expires_at_ms: state.expires_at_ms,
                tries_left: PAIR_MAX_TRIES - state.tries,
            }
        }
    }

    pub(crate) async fn shutdown(self, cancelled: bool) {
        if cancelled {
            self.state.lock().expect("pair state").cancelled = true;
        }
        self.reaper.abort();
        let _ = timeout(Duration::from_secs(2), self.router.shutdown()).await;
    }
}

fn random_code() -> String {
    let mut bytes = [0u8; 8];
    fill_random(&mut bytes);
    // 2^64 is not a multiple of 10^8; the bias is about 5e-12, far below anything a guess can use.
    format!("{:08}", u64::from_be_bytes(bytes) % 100_000_000)
}

fn random_uuid() -> String {
    let mut bytes = [0u8; 16];
    fill_random(&mut bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    let hex = hex::encode(bytes);
    format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    )
}

pub(crate) async fn start(ctx: &Arc<Ctx>, user_id: i64) -> NetResult<PairOffer> {
    let code = random_code();
    let for_keys = code.clone();
    let keys = blocking(move || derive_pair_keys(&for_keys)).await?;
    let (path, clock) = (ctx.cfg.db_path.clone(), ctx.cfg.clock.clone());
    blocking(move || {
        let mut conn = open_db(&path)?;
        if account_uuid(&conn, user_id).is_err() {
            set_account(&conn, user_id, &random_uuid())?;
        }
        scan(&mut conn, user_id, clock())?;
        Ok(())
    })
    .await?;
    let endpoint = bind_endpoint(&ctx.cfg.transport, keys.secret, None).await?;
    let expires_at_ms = (ctx.cfg.clock)() + PAIR_EXPIRY_MS;
    let state = Arc::new(Mutex::new(PairState {
        user_id,
        proof_key: keys.proof_key,
        expires_at_ms,
        tries: 0,
        paired: None,
        cancelled: false,
    }));
    let handler = PairHandler {
        ctx: ctx.clone(),
        state: state.clone(),
        gate: Arc::new(tokio::sync::Mutex::new(())),
    };
    let router = Router::builder(endpoint.clone())
        .accept(PAIR_ALPN, handler)
        .spawn();
    let hints = local_addrs(&endpoint, &ctx.cfg.transport, 4).await;
    let reaper_ctx = ctx.clone();
    let lifetime = Duration::from_millis(PAIR_EXPIRY_MS as u64) + GRACE;
    let reaper_state = state.clone();
    let reaper = tokio::spawn(async move {
        tokio::time::sleep(lifetime).await;
        let expired = {
            let mut slot = reaper_ctx.pairing.lock().expect("pairing slot");
            if slot
                .as_ref()
                .is_some_and(|host| Arc::ptr_eq(&host.state, &reaper_state))
            {
                slot.take()
            } else {
                None
            }
        };
        if let Some(host) = expired {
            let _ = timeout(Duration::from_secs(2), host.router.shutdown()).await;
        }
    });
    let previous = ctx.pairing.lock().expect("pairing slot").replace(PairHost {
        state,
        router,
        reaper,
    });
    if let Some(previous) = previous {
        previous.shutdown(true).await;
    }
    Ok(PairOffer {
        display_code: display_code(&code),
        qr: qr::build(&code, &hints),
        code,
        expires_at_ms,
    })
}

struct PairHandler {
    ctx: Arc<Ctx>,
    state: Arc<Mutex<PairState>>,
    /// One decision at a time, so two phones racing for the same code cannot both pass.
    gate: Arc<tokio::sync::Mutex<()>>,
}

impl std::fmt::Debug for PairHandler {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("PairHandler")
    }
}

impl ProtocolHandler for PairHandler {
    async fn accept(&self, connection: Connection) -> Result<(), AcceptError> {
        let opened = timeout(Duration::from_secs(10), connection.accept_bi()).await;
        let Ok(Ok((mut send, mut recv))) = opened else {
            return Ok(());
        };
        let hello = timeout(Duration::from_secs(10), recv.read_to_end(MAX_MESSAGE_BYTES)).await;
        let Ok(Ok(hello)) = hello else {
            return Ok(());
        };
        let reply = self.decide(connection.remote_id(), &hello).await;
        if send.write_all(&encode(&reply)).await.is_ok() {
            let _ = send.finish();
        }
        // The phone closes once it has read the reply; waiting keeps the reply from being cut off.
        let _ = timeout(Duration::from_secs(5), connection.closed()).await;
        Ok(())
    }
}

struct Hello {
    device_id: String,
    device_name: String,
    endpoint_id: EndpointId,
    nonce: Vec<u8>,
    proof: Vec<u8>,
    addrs: Vec<SocketAddr>,
}

fn parse_hello(bytes: &[u8]) -> Option<Hello> {
    let value = decode(bytes).ok()?;
    if value.get("proto").and_then(Value::as_i64) != Some(PROTO_VERSION) {
        return None;
    }
    let text = |key: &str, max: usize| {
        value
            .get(key)
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty() && s.chars().count() <= max)
            .map(str::to_owned)
    };
    Some(Hello {
        device_id: text("device_id", 128)?,
        device_name: text("device_name", 80)?,
        endpoint_id: text("endpoint_id", 128)?.parse().ok()?,
        nonce: hex::decode(text("nonce", 64)?).ok()?,
        proof: hex::decode(text("proof", 128)?).ok()?,
        addrs: value
            .get("addrs")
            .and_then(Value::as_array)
            .map(|list| {
                list.iter()
                    .filter_map(|item| item.as_str()?.parse().ok())
                    .take(8)
                    .collect()
            })
            .unwrap_or_default(),
    })
}

impl PairHandler {
    async fn decide(&self, remote: EndpointId, bytes: &[u8]) -> Value {
        let _decision = self.gate.lock().await;
        let now = (self.ctx.cfg.clock)();
        let (user_id, proof_key) = {
            let state = self.state.lock().expect("pair state");
            if state.paired.is_some() {
                return refusal("used", "this code was already used");
            }
            if state.tries >= PAIR_MAX_TRIES {
                return refusal("too_many_tries", "too many wrong tries");
            }
            if state.cancelled || now >= state.expires_at_ms {
                return refusal("expired", "this code has expired");
            }
            (state.user_id, state.proof_key)
        };
        let hello = parse_hello(bytes).filter(|hello| {
            hello.endpoint_id == remote
                && hello_proof_matches(
                    &proof_key,
                    &hello.nonce,
                    hello.endpoint_id.as_bytes(),
                    &hello.device_id,
                    &hello.device_name,
                    &hello.proof,
                )
        });
        let Some(hello) = hello else {
            let mut state = self.state.lock().expect("pair state");
            state.tries += 1;
            return refusal("wrong_code", "that code is not right");
        };
        let (path, clock) = (self.ctx.cfg.db_path.clone(), self.ctx.cfg.clock.clone());
        let (device_id, device_name) =
            (self.ctx.device_id.clone(), self.ctx.cfg.device_name.clone());
        let stored = (
            hello.device_id.clone(),
            hello.device_name.clone(),
            hello.endpoint_id.to_string(),
        );
        let outcome = blocking(move || {
            let mut conn = open_db(&path)?;
            let now = clock();
            let uuid = account_uuid(&conn, user_id)?;
            let first = scan_and_export(&mut conn, user_id, now, 0, &stored.0, 1)?;
            let username: String = conn
                .query_row(
                    "SELECT username FROM users WHERE id = ?1",
                    [user_id],
                    |row| row.get(0),
                )
                .map_err(SyncError::from)?;
            record_peer(&conn, user_id, &stored.0, &stored.2, &stored.1, now)?;
            Ok((uuid, username, first))
        })
        .await;
        let (uuid, username, first) = match outcome {
            Ok(done) => done,
            Err(error) => return refusal("failed", &error.to_string()),
        };
        self.ctx
            .add_hints(&hello.endpoint_id.to_string(), &hello.addrs);
        self.state.lock().expect("pair state").paired = Some(PairedPeer {
            user_id,
            device_id: hello.device_id,
            device_name: hello.device_name,
            endpoint_id: hello.endpoint_id.to_string(),
        });
        let addrs = local_addrs(&self.ctx.endpoint, &self.ctx.cfg.transport, 6).await;
        json!({
            "ok": true,
            "account_uuid": uuid,
            "username": username,
            "device_id": device_id,
            "device_name": device_name,
            "endpoint_id": self.ctx.endpoint.id().to_string(),
            "addrs": addrs.iter().map(SocketAddr::to_string).collect::<Vec<_>>(),
            "first": first.to_value(),
        })
    }
}

/// Both sides start the cursors at 0 on a new pairing. Records are idempotent, so resending is
/// harmless, and it covers a peer that came back with an empty database.
fn record_peer(
    conn: &rusqlite::Connection,
    user_id: i64,
    device_id: &str,
    endpoint_id: &str,
    name: &str,
    now_ms: i64,
) -> NetResult<()> {
    upsert_peer(
        conn,
        user_id,
        &Peer {
            device_id: device_id.to_owned(),
            endpoint_id: endpoint_id.to_owned(),
            name: name.to_owned(),
            paired_at: now_ms.to_string(),
            last_seen: Some(now_ms.to_string()),
            revoked: false,
            pulled_seq: 0,
            pushed_seq: 0,
        },
    )?;
    conn.execute(
        "UPDATE sync_peer SET pulled_seq = 0, pushed_seq = 0 WHERE user_id = ?1 AND peer_device_id = ?2",
        params![user_id, device_id],
    )
    .map_err(SyncError::from)?;
    touch_peer(conn, user_id, device_id, now_ms)
}

/// The phone's side: derive the pairing endpoint from the code, prove knowledge of it, and keep
/// what the desktop sends back.
pub(crate) async fn pair_dial(
    ctx: &Arc<Ctx>,
    code: &str,
    hints: &[SocketAddr],
) -> NetResult<PairedHost> {
    let code = normalize_code(code)?;
    let keys = blocking(move || derive_pair_keys(&code)).await?;
    let mut address = EndpointAddr::new(keys.secret.public());
    for hint in hints {
        address = address.with_ip_addr(*hint);
    }
    let connect = ctx.endpoint.connect(address, PAIR_ALPN);
    let connection = timeout(Duration::from_millis(CONNECT_TIMEOUT_MS), connect)
        .await
        .map_err(|_| {
            NetError::Unreachable(
                "no answer; check the code and that both devices are online".into(),
            )
        })?
        .map_err(|e| NetError::Unreachable(e.to_string()))?;
    let mut nonce = [0u8; 16];
    fill_random(&mut nonce);
    let proof = hello_proof(
        &keys.proof_key,
        &nonce,
        ctx.endpoint.id().as_bytes(),
        &ctx.device_id,
        &ctx.cfg.device_name,
    );
    let addrs = local_addrs(&ctx.endpoint, &ctx.cfg.transport, 6).await;
    let hello = json!({
        "proto": PROTO_VERSION,
        "device_id": ctx.device_id,
        "device_name": ctx.cfg.device_name,
        "endpoint_id": ctx.endpoint.id().to_string(),
        "nonce": hex::encode(nonce),
        "proof": hex::encode(proof),
        "addrs": addrs.iter().map(SocketAddr::to_string).collect::<Vec<_>>(),
    });
    let reply = async {
        let (mut send, mut recv) = connection
            .open_bi()
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        send.write_all(&encode(&hello))
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        send.finish()
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        let bytes = recv
            .read_to_end(MAX_MESSAGE_BYTES)
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        decode(&bytes)
    }
    .await;
    connection.close(CLOSE_DONE.into(), b"done");
    let reply = reply?;
    if reply.get("ok").and_then(Value::as_bool) != Some(true) {
        let message = reply
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("pairing was refused");
        return Err(match reply.get("code").and_then(Value::as_str) {
            Some("wrong_code") => NetError::PairRefused(PairRefusal::WrongCode),
            Some("expired") => NetError::PairRefused(PairRefusal::Expired),
            Some("used") => NetError::PairRefused(PairRefusal::Used),
            Some("too_many_tries") => NetError::PairRefused(PairRefusal::TooManyTries),
            _ => NetError::Protocol(message.to_owned()),
        });
    }
    let text = |key: &str| {
        reply
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .ok_or_else(|| NetError::Protocol(format!("pairing reply is missing {key}")))
    };
    let host = (
        text("account_uuid")?,
        text("username")?,
        text("device_id")?,
        text("device_name")?,
        text("endpoint_id")?,
    );
    let first = Batch::from_value(reply.get("first").unwrap_or(&Value::Null))?;
    let host_addrs: Vec<SocketAddr> = reply
        .get("addrs")
        .and_then(Value::as_array)
        .map(|list| {
            list.iter()
                .filter_map(|a| a.as_str()?.parse().ok())
                .take(8)
                .collect()
        })
        .unwrap_or_default();
    let (path, clock) = (ctx.cfg.db_path.clone(), ctx.cfg.clock.clone());
    let finished = host.clone();
    let user_id = blocking(move || {
        let mut conn = open_db(&path)?;
        let other: Option<String> = conn
            .query_row(
                "SELECT account_uuid FROM sync_account WHERE account_uuid != ?1 LIMIT 1",
                [&finished.0],
                |row| row.get(0),
            )
            .map(Some)
            .or_else(|e| {
                if e == rusqlite::Error::QueryReturnedNoRows {
                    Ok(None)
                } else {
                    Err(e)
                }
            })
            .map_err(SyncError::from)?;
        if other.is_some() {
            return Err(NetError::AlreadyLinked);
        }
        if first.account_uuid != finished.0 {
            return Err(NetError::Protocol(
                "pairing reply is for another account".into(),
            ));
        }
        let now = clock();
        let report = apply_batch(&mut conn, &first, now)?;
        let user_id = report
            .user_id
            .ok_or_else(|| NetError::Protocol("pairing reply has no account".into()))?;
        record_peer(&conn, user_id, &finished.2, &finished.4, &finished.3, now)?;
        Ok(user_id)
    })
    .await?;
    ctx.add_hints(&host.4, &host_addrs);
    Ok(PairedHost {
        user_id,
        account_uuid: host.0,
        username: host.1,
        host_device_id: host.2,
        host_name: host.3,
        host_endpoint_id: host.4,
    })
}
