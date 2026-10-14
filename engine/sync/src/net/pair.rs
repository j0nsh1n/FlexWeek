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
    PAIR_VERSION, check_pair_version, decode, derive_pair_keys, display_code, encode, hello_proof,
    hello_proof_matches, normalize_code, refusal,
};
use super::service::{Ctx, bind_endpoint, local_addrs};
use super::session::{scan_and_export, touch_peer};
use super::{NetError, NetResult, PairRefusal, blocking, open_db, qr};
use crate::{
    Batch, Peer, SyncError, account_uuid, apply_batch, revoke_peer, scan, set_account, upsert_peer,
};

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
            PairStatus::Idle
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
    let host = PairHost {
        state,
        router,
        reaper,
    };
    // `stop` sets the flag before it empties the slot, so either this sees it or `stop` sees the
    // new window; one of the two always shuts it down.
    let previous = {
        let mut slot = ctx.pairing.lock().expect("pairing slot");
        if ctx.stopping.load(std::sync::atomic::Ordering::SeqCst) {
            drop(slot);
            host.shutdown(true).await;
            return Err(NetError::Stopped);
        }
        slot.replace(host)
    };
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
        let (reply, pending) = self.decide(connection.remote_id(), &hello).await;
        if write_reply(&mut send, &reply).await
            && let Some(pending) = pending
        {
            // The phone confirms on a second stream once it has stored this device. Only then is
            // the peer recorded and the code spent, so a phone that cannot finish (another
            // account, a deadline, a dropped connection) leaves nothing behind on this side.
            let confirmed = timeout(Duration::from_secs(15), async {
                let (send, mut recv) = connection.accept_bi().await.ok()?;
                let bytes = recv.read_to_end(1024).await.ok()?;
                let asked = decode(&bytes).ok()?;
                (asked.get("op").and_then(Value::as_str) == Some("confirm")).then_some(send)
            })
            .await;
            if let Ok(Some(mut answer)) = confirmed {
                let result = self.commit(pending).await;
                let body = match result {
                    Ok(()) => json!({"ok": true}),
                    Err(error) => refusal("failed", &error.to_string()),
                };
                write_reply(&mut answer, &body).await;
            }
        }
        // The phone closes once it has read the reply; waiting keeps the reply from being cut off.
        let _ = timeout(Duration::from_secs(5), connection.closed()).await;
        Ok(())
    }
}

/// A peer that stops reading must not pin this task, so the write has its own limit.
async fn write_reply(send: &mut iroh::endpoint::SendStream, reply: &Value) -> bool {
    let sent = timeout(Duration::from_secs(10), send.write_all(&encode(reply))).await;
    let wrote = sent.is_ok_and(|result| result.is_ok());
    if wrote {
        let _ = send.finish();
    }
    wrote
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
    check_pair_version(&value).ok()?;
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

/// A phone that passed the proof and was sent the account, waiting for its confirmation. Holding
/// the gate keeps a second phone out until this one confirms or gives up.
struct Pending {
    _gate: tokio::sync::OwnedMutexGuard<()>,
    hello: Hello,
    user_id: i64,
}

impl PairHandler {
    async fn decide(&self, remote: EndpointId, bytes: &[u8]) -> (Value, Option<Pending>) {
        let gate = self.gate.clone().lock_owned().await;
        if let Ok(value) = decode(bytes)
            && let Err(error) = check_pair_version(&value)
        {
            return (refusal(error.kind(), &error.to_string()), None);
        }
        let now = (self.ctx.cfg.clock)();
        let (user_id, proof_key) = {
            let state = self.state.lock().expect("pair state");
            if state.paired.is_some() {
                return (refusal("used", "this code was already used"), None);
            }
            if state.tries >= PAIR_MAX_TRIES {
                return (refusal("too_many_tries", "too many wrong tries"), None);
            }
            if state.cancelled || now >= state.expires_at_ms {
                return (refusal("expired", "this code has expired"), None);
            }
            (state.user_id, state.proof_key)
        };
        // The device id is the endpoint id, so a phone cannot take over another device's row.
        let hello = parse_hello(bytes).filter(|hello| {
            hello.endpoint_id == remote
                && hello.device_id == hello.endpoint_id.to_string()
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
            self.state.lock().expect("pair state").tries += 1;
            return (refusal("wrong_code", "that code is not right"), None);
        };
        let (path, clock) = (self.ctx.cfg.db_path.clone(), self.ctx.cfg.clock.clone());
        let (device_id, device_name) =
            (self.ctx.device_id.clone(), self.ctx.cfg.device_name.clone());
        let requester = hello.device_id.clone();
        let outcome = blocking(move || {
            let mut conn = open_db(&path)?;
            let now = clock();
            let uuid = account_uuid(&conn, user_id)?;
            let first = scan_and_export(&mut conn, user_id, now, 0, &requester, 1)?;
            let username: String = conn
                .query_row(
                    "SELECT username FROM users WHERE id = ?1",
                    [user_id],
                    |row| row.get(0),
                )
                .map_err(SyncError::from)?;
            Ok((uuid, username, first))
        })
        .await;
        let (uuid, username, first) = match outcome {
            Ok(done) => done,
            Err(error) => return (refusal("failed", &error.to_string()), None),
        };
        let addrs = local_addrs(&self.ctx.endpoint, &self.ctx.cfg.transport, 6).await;
        let reply = json!({
            "ok": true,
            "proto": PAIR_VERSION,
            "account_uuid": uuid,
            "username": username,
            "device_id": device_id,
            "device_name": device_name,
            "endpoint_id": self.ctx.endpoint.id().to_string(),
            "addrs": addrs.iter().map(SocketAddr::to_string).collect::<Vec<_>>(),
            "first": first.to_value(),
        });
        (
            reply,
            Some(Pending {
                _gate: gate,
                hello,
                user_id,
            }),
        )
    }

    /// Records the phone and spends the code. `paired` is set inside the blocking task, right
    /// after the commit, so cancelling the window cannot land between the two.
    async fn commit(&self, pending: Pending) -> NetResult<()> {
        let Pending { hello, user_id, .. } = &pending;
        let (path, clock, state) = (
            self.ctx.cfg.db_path.clone(),
            self.ctx.cfg.clock.clone(),
            self.state.clone(),
        );
        let peer = PairedPeer {
            user_id: *user_id,
            device_id: hello.device_id.clone(),
            device_name: hello.device_name.clone(),
            endpoint_id: hello.endpoint_id.to_string(),
        };
        let (ctx, addrs) = (self.ctx.clone(), hello.addrs.clone());
        blocking(move || {
            let mut conn = open_db(&path)?;
            record_peer(
                &mut conn,
                peer.user_id,
                &peer.device_id,
                &peer.endpoint_id,
                &peer.device_name,
                clock(),
            )?;
            ctx.add_hints(&peer.endpoint_id, &addrs);
            state.lock().expect("pair state").paired = Some(peer);
            Ok(())
        })
        .await
    }
}

/// Both sides start the cursors at 0 on a new pairing. Records are idempotent, so resending is
/// harmless, and it covers a peer that came back with an empty database. One transaction, so a
/// failure in the middle cannot leave a half-written peer that is admitted.
fn record_peer(
    conn: &mut rusqlite::Connection,
    user_id: i64,
    device_id: &str,
    endpoint_id: &str,
    name: &str,
    now_ms: i64,
) -> NetResult<()> {
    let tx = conn.transaction().map_err(SyncError::from)?;
    upsert_peer(
        &tx,
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
    tx.execute(
        "UPDATE sync_peer SET pulled_seq = 0, pushed_seq = 0 WHERE user_id = ?1 AND peer_device_id = ?2",
        params![user_id, device_id],
    )
    .map_err(SyncError::from)?;
    touch_peer(&tx, user_id, device_id, now_ms)?;
    tx.commit().map_err(SyncError::from)?;
    Ok(())
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
        "proto": PAIR_VERSION,
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
    let reply = match reply {
        Ok(reply) => reply,
        Err(error) => {
            connection.close(CLOSE_DONE.into(), b"done");
            return Err(error);
        }
    };
    if reply.get("ok").and_then(Value::as_bool) != Some(true) {
        connection.close(CLOSE_DONE.into(), b"done");
        let message = reply
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("pairing was refused");
        return Err(match reply.get("code").and_then(Value::as_str) {
            Some("wrong_code") => NetError::PairRefused(PairRefusal::WrongCode),
            Some("expired") => NetError::PairRefused(PairRefusal::Expired),
            Some("used") => NetError::PairRefused(PairRefusal::Used),
            Some("too_many_tries") => NetError::PairRefused(PairRefusal::TooManyTries),
            Some("version_mismatch") => NetError::PairVersionMismatch,
            _ => NetError::Protocol(message.to_owned()),
        });
    }
    if let Err(error) = check_pair_version(&reply) {
        connection.close(CLOSE_DONE.into(), b"done");
        return Err(error);
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
    if host.2 != host.4 {
        connection.close(CLOSE_DONE.into(), b"done");
        return Err(NetError::Protocol(
            "pairing reply has a device id that is not its endpoint id".into(),
        ));
    }
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
    let stored = blocking(move || {
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
        record_peer(
            &mut conn,
            user_id,
            &finished.2,
            &finished.4,
            &finished.3,
            now,
        )?;
        Ok(user_id)
    })
    .await;
    let user_id = match stored {
        Ok(user_id) => user_id,
        Err(error) => {
            connection.close(CLOSE_DONE.into(), b"done");
            return Err(error);
        }
    };
    // The desktop records this phone only once it hears this; if it cannot, undo our side too.
    let confirmed = confirm(&connection).await;
    connection.close(CLOSE_DONE.into(), b"done");
    if let Err(error) = confirmed {
        let (path, device) = (ctx.cfg.db_path.clone(), host.2.clone());
        let _ = blocking(move || Ok(revoke_peer(&open_db(&path)?, user_id, &device)?)).await;
        return Err(error);
    }
    let (hints_ctx, hints_id) = (ctx.clone(), host.4.clone());
    blocking(move || {
        hints_ctx.add_hints(&hints_id, &host_addrs);
        Ok(())
    })
    .await?;
    Ok(PairedHost {
        user_id,
        account_uuid: host.0,
        username: host.1,
        host_device_id: host.2,
        host_name: host.3,
        host_endpoint_id: host.4,
    })
}

async fn confirm(connection: &Connection) -> NetResult<()> {
    let answer = timeout(Duration::from_secs(10), async {
        let (mut send, mut recv) = connection
            .open_bi()
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        send.write_all(&encode(&json!({"op": "confirm"})))
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        send.finish()
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        let bytes = recv
            .read_to_end(MAX_MESSAGE_BYTES)
            .await
            .map_err(|e| NetError::Unreachable(e.to_string()))?;
        decode(&bytes)
    })
    .await
    .map_err(|_| NetError::Unreachable("the desktop did not confirm the pairing".into()))??;
    if answer.get("ok").and_then(Value::as_bool) == Some(true) {
        Ok(())
    } else {
        Err(NetError::Protocol(
            "the desktop could not finish pairing".into(),
        ))
    }
}
