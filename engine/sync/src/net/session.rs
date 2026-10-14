//! The sync stream: the server side that answers a paired peer's request, and the client side
//! that pushes and pulls until neither side has more.

use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::Duration;

use iroh::endpoint::{Connection, ConnectionError};
use iroh::protocol::{AcceptError, ProtocolHandler};
use iroh::{EndpointAddr, EndpointId};
use rusqlite::{Connection as Db, OptionalExtension, params};
use serde_json::{Value, json};
use tokio::time::timeout;

use super::protocol::{
    BATCH_LIMIT, CLOSE_DONE, CLOSE_NOT_PAIRED, CONNECT_TIMEOUT_MS, MAX_MESSAGE_BYTES,
    PROTO_VERSION, SYNC_ALPN, decode, encode, refusal,
};
use super::service::Ctx;
use super::{NetError, NetResult, SyncSummary, blocking, open_db};
use crate::{
    Batch, Peer, SyncError, acknowledge_pull, acknowledge_push, apply_batch, export_since,
    list_peers, revoke_peer, scan,
};

const IDLE_MS: u64 = 60_000;
const EXCHANGE_MS: u64 = 45_000;

/// Scans every account in the database, so edits made by another process get a stamp.
pub(crate) fn scan_all(conn: &mut Db, now_ms: i64) -> NetResult<usize> {
    let users: Vec<i64> = conn
        .prepare("SELECT user_id FROM sync_account")
        .map_err(SyncError::from)?
        .query_map([], |row| row.get(0))
        .map_err(SyncError::from)?
        .collect::<Result<_, _>>()
        .map_err(SyncError::from)?;
    let mut changed = 0;
    for user_id in users {
        changed += scan(conn, user_id, now_ms)?;
    }
    Ok(changed)
}

/// Scan, then export. A desktop write between the two makes the export say "changed since last
/// scan", which is what one more scan fixes.
pub(crate) fn scan_and_export(
    conn: &mut Db,
    user_id: i64,
    now_ms: i64,
    since: i64,
    requester_device: &str,
    limit: usize,
) -> NetResult<Batch> {
    scan(conn, user_id, now_ms)?;
    match export_since(conn, user_id, since, requester_device, limit) {
        Err(SyncError::Invalid(message)) if message == "record changed since last scan" => {
            scan(conn, user_id, now_ms)?;
            Ok(export_since(conn, user_id, since, requester_device, limit)?)
        }
        other => Ok(other?),
    }
}

pub(crate) fn touch_peer(conn: &Db, user_id: i64, device_id: &str, now_ms: i64) -> NetResult<()> {
    conn.execute(
        "UPDATE sync_peer SET last_seen = ?3 WHERE user_id = ?1 AND peer_device_id = ?2",
        params![user_id, device_id, now_ms.to_string()],
    )
    .map_err(SyncError::from)?;
    Ok(())
}

/// The user and peer row for an endpoint that is paired (not revoked) for this account.
fn paired(conn: &Db, endpoint_id: &str, account_uuid: &str) -> NetResult<Option<(i64, Peer)>> {
    let user_id: Option<i64> = conn
        .query_row(
            "SELECT p.user_id FROM sync_peer p JOIN sync_account a ON a.user_id = p.user_id WHERE p.endpoint_id = ?1 AND a.account_uuid = ?2 AND p.revoked = 0",
            params![endpoint_id, account_uuid],
            |row| row.get(0),
        )
        .optional()
        .map_err(SyncError::from)?;
    let Some(user_id) = user_id else {
        return Ok(None);
    };
    Ok(list_peers(conn, user_id)?
        .into_iter()
        .find(|peer| peer.endpoint_id == endpoint_id && !peer.revoked)
        .map(|peer| (user_id, peer)))
}

fn endpoint_is_paired(conn: &Db, endpoint_id: &str) -> NetResult<bool> {
    Ok(conn
        .query_row(
            "SELECT 1 FROM sync_peer WHERE endpoint_id = ?1 AND revoked = 0",
            [endpoint_id],
            |_| Ok(()),
        )
        .optional()
        .map_err(SyncError::from)?
        .is_some())
}

pub(crate) struct SyncHandler(pub Arc<Ctx>);

impl std::fmt::Debug for SyncHandler {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("SyncHandler")
    }
}

impl ProtocolHandler for SyncHandler {
    async fn accept(&self, connection: Connection) -> Result<(), AcceptError> {
        let ctx = &self.0;
        let remote = connection.remote_id().to_string();
        let path = ctx.cfg.db_path.clone();
        let remote_for_db = remote.clone();
        let known = blocking(move || endpoint_is_paired(&open_db(&path)?, &remote_for_db))
            .await
            .unwrap_or(false);
        if !known || ctx.stopping.load(Ordering::Relaxed) {
            connection.close(CLOSE_NOT_PAIRED.into(), b"not paired");
            return Ok(());
        }
        loop {
            let opened = timeout(Duration::from_millis(IDLE_MS), connection.accept_bi()).await;
            let Ok(Ok((mut send, mut recv))) = opened else {
                break;
            };
            let request = timeout(
                Duration::from_millis(EXCHANGE_MS),
                recv.read_to_end(MAX_MESSAGE_BYTES),
            )
            .await;
            let Ok(Ok(request)) = request else {
                break;
            };
            let response = respond(ctx, &remote, request).await;
            let sent = timeout(
                Duration::from_millis(EXCHANGE_MS),
                send.write_all(&encode(&response)),
            )
            .await;
            if !sent.is_ok_and(|result| result.is_ok()) || send.finish().is_err() {
                break;
            }
        }
        connection.close(CLOSE_DONE.into(), b"done");
        Ok(())
    }
}

async fn respond(ctx: &Arc<Ctx>, remote: &str, request: Vec<u8>) -> Value {
    let request = match decode(&request) {
        Ok(value) => value,
        Err(error) => return refusal("bad_request", &error.to_string()),
    };
    let ctx = ctx.clone();
    let remote = remote.to_owned();
    match blocking(move || serve(&ctx, &remote, &request)).await {
        Ok(response) => response,
        Err(NetError::NotPaired) => refusal("not_paired", "this device is not paired"),
        Err(error) => refusal("failed", &error.to_string()),
    }
}

fn text<'a>(request: &'a Value, key: &str) -> NetResult<&'a str> {
    request
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| NetError::Protocol(format!("request is missing {key}")))
}

fn serve(ctx: &Ctx, remote: &str, request: &Value) -> NetResult<Value> {
    if request.get("proto").and_then(Value::as_i64) != Some(PROTO_VERSION) {
        return Err(NetError::Protocol("unsupported protocol version".into()));
    }
    let account_uuid = text(request, "account_uuid")?;
    let device_id = text(request, "device_id")?;
    let mut conn = open_db(&ctx.cfg.db_path)?;
    let (user_id, peer) = paired(&conn, remote, account_uuid)?.ok_or(NetError::NotPaired)?;
    if peer.device_id != device_id {
        return Err(NetError::NotPaired);
    }
    let now = (ctx.cfg.clock)();
    match text(request, "op")? {
        "bye" => {
            revoke_peer(&conn, user_id, &peer.device_id)?;
            Ok(json!({"ok": true}))
        }
        "sync" => {
            let since = request
                .get("since")
                .and_then(Value::as_i64)
                .ok_or_else(|| NetError::Protocol("request is missing since".into()))?;
            let push = Batch::from_value(request.get("push").unwrap_or(&Value::Null))?;
            if push.account_uuid != account_uuid || push.from_device != peer.device_id {
                return Err(NetError::Protocol("batch does not match the peer".into()));
            }
            let report = apply_batch(&mut conn, &push, now)?;
            acknowledge_pull(&conn, user_id, &peer.device_id, push.next_since)?;
            acknowledge_push(&conn, user_id, &peer.device_id, since)?;
            touch_peer(&conn, user_id, &peer.device_id, now)?;
            let batch =
                scan_and_export(&mut conn, user_id, now, since, &peer.device_id, BATCH_LIMIT)?;
            if report.applied > 0 {
                ctx.generation.fetch_add(1, Ordering::Relaxed);
            }
            Ok(json!({
                "ok": true,
                "ack_through": push.next_since,
                "batch": batch.to_value(),
                "applied": report.applied,
                "quarantined": report.quarantined,
            }))
        }
        other => Err(NetError::Protocol(format!("unknown request {other}"))),
    }
}

async fn exchange(connection: &Connection, request: &Value) -> NetResult<Value> {
    let (mut send, mut recv) = connection
        .open_bi()
        .await
        .map_err(|e| NetError::Unreachable(e.to_string()))?;
    send.write_all(&encode(request))
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

/// The peer closes a connection it does not accept with `CLOSE_NOT_PAIRED`; the failed read only
/// says "connection lost", so the close reason is what tells the two apart.
async fn closed_as_not_paired(connection: &Connection) -> bool {
    let reason = match connection.close_reason() {
        Some(reason) => Some(reason),
        None => timeout(Duration::from_millis(300), connection.closed())
            .await
            .ok(),
    };
    matches!(reason, Some(ConnectionError::ApplicationClosed(close)) if close.error_code.into_inner() == u64::from(CLOSE_NOT_PAIRED))
}

pub(crate) async fn bye(ctx: &Arc<Ctx>, user_id: i64, peer: &Peer) -> NetResult<()> {
    let path = ctx.cfg.db_path.clone();
    let uuid = blocking(move || Ok(crate::account_uuid(&open_db(&path)?, user_id)?)).await?;
    let id: EndpointId = peer
        .endpoint_id
        .parse()
        .map_err(|_| NetError::Protocol("the peer's endpoint id is not readable".into()))?;
    let connection = ctx
        .endpoint
        .connect(EndpointAddr::new(id), SYNC_ALPN)
        .await
        .map_err(|e| NetError::Unreachable(e.to_string()))?;
    let request = json!({"proto": PROTO_VERSION, "op": "bye", "account_uuid": uuid, "device_id": ctx.device_id});
    let result = exchange(&connection, &request).await;
    connection.close(CLOSE_DONE.into(), b"done");
    result.map(|_| ())
}

fn find_peer(conn: &Db, device_id: &str) -> NetResult<(i64, Peer)> {
    let users: Vec<i64> = conn
        .prepare("SELECT user_id FROM sync_account")
        .map_err(SyncError::from)?
        .query_map([], |row| row.get(0))
        .map_err(SyncError::from)?
        .collect::<Result<_, _>>()
        .map_err(SyncError::from)?;
    for user_id in users {
        if let Some(peer) = list_peers(conn, user_id)?
            .into_iter()
            .find(|peer| peer.device_id == device_id && !peer.revoked)
        {
            return Ok((user_id, peer));
        }
    }
    Err(NetError::NotPaired)
}

pub(crate) async fn sync_with(ctx: &Arc<Ctx>, device_id: &str) -> NetResult<SyncSummary> {
    let path = ctx.cfg.db_path.clone();
    let wanted = device_id.to_owned();
    let (user_id, peer) = blocking(move || find_peer(&open_db(&path)?, &wanted)).await?;
    let id: EndpointId = peer
        .endpoint_id
        .parse()
        .map_err(|_| NetError::Protocol("the peer's endpoint id is not readable".into()))?;
    let connect = ctx.endpoint.connect(EndpointAddr::new(id), SYNC_ALPN);
    let connection = timeout(Duration::from_millis(CONNECT_TIMEOUT_MS), connect)
        .await
        .map_err(|_| NetError::Unreachable("no answer within 10 seconds".into()))?
        .map_err(|e| NetError::Unreachable(e.to_string()))?;
    let result = rounds(ctx, &connection, user_id, &peer).await;
    let result = match result {
        Err(NetError::Unreachable(_)) if closed_as_not_paired(&connection).await => {
            Err(NetError::NotPaired)
        }
        other => other,
    };
    connection.close(CLOSE_DONE.into(), b"done");
    result
}

async fn rounds(
    ctx: &Arc<Ctx>,
    connection: &Connection,
    user_id: i64,
    peer: &Peer,
) -> NetResult<SyncSummary> {
    let mut summary = SyncSummary::default();
    loop {
        let (path, peer_id, clock) = (
            ctx.cfg.db_path.clone(),
            peer.device_id.clone(),
            ctx.cfg.clock.clone(),
        );
        let (request, push) = blocking(move || {
            let mut conn = open_db(&path)?;
            let cursors = list_peers(&conn, user_id)?
                .into_iter()
                .find(|p| p.device_id == peer_id && !p.revoked)
                .ok_or(NetError::NotPaired)?;
            let now = clock();
            let push = scan_and_export(
                &mut conn,
                user_id,
                now,
                cursors.pushed_seq,
                &peer_id,
                BATCH_LIMIT,
            )?;
            let device_id: String = conn
                .query_row(
                    "SELECT device_id FROM sync_device WHERE singleton = 1",
                    [],
                    |row| row.get(0),
                )
                .map_err(SyncError::from)?;
            let request = json!({
                "proto": PROTO_VERSION,
                "op": "sync",
                "account_uuid": push.account_uuid,
                "device_id": device_id,
                "since": cursors.pulled_seq,
                "push": push.to_value(),
            });
            Ok((request, (push, cursors)))
        })
        .await?;
        let (push, cursors) = push;
        let response = exchange(connection, &request).await?;
        if response.get("ok").and_then(Value::as_bool) != Some(true) {
            let code = response
                .get("code")
                .and_then(Value::as_str)
                .unwrap_or("failed");
            let message = response
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("the other device refused");
            return Err(if code == "not_paired" {
                NetError::NotPaired
            } else {
                NetError::Protocol(message.to_owned())
            });
        }
        let batch = Batch::from_value(response.get("batch").unwrap_or(&Value::Null))?;
        let ack_through = response
            .get("ack_through")
            .and_then(Value::as_i64)
            .ok_or_else(|| NetError::Protocol("response is missing ack_through".into()))?;
        if batch.account_uuid != push.account_uuid {
            return Err(NetError::Protocol("response is for another account".into()));
        }
        // A cursor is only ever raised, so one absurd value would stop this peer's records for
        // good. The acknowledgement must be exactly what was sent, and a pull cannot go backwards.
        if ack_through != push.next_since || batch.next_since < cursors.pulled_seq {
            return Err(NetError::Protocol(
                "the other device sent positions that do not add up".into(),
            ));
        }
        let (path, peer_id, clock) = (
            ctx.cfg.db_path.clone(),
            peer.device_id.clone(),
            ctx.cfg.clock.clone(),
        );
        let incoming = batch.clone();
        let report = blocking(move || {
            let mut conn = open_db(&path)?;
            let now = clock();
            let report = apply_batch(&mut conn, &incoming, now)?;
            acknowledge_pull(&conn, user_id, &peer_id, incoming.next_since)?;
            acknowledge_push(&conn, user_id, &peer_id, ack_through)?;
            touch_peer(&conn, user_id, &peer_id, now)?;
            Ok(report)
        })
        .await?;
        if report.applied > 0 {
            ctx.generation.fetch_add(1, Ordering::Relaxed);
        }
        summary.sent += push.records.len();
        summary.received += batch.records.len();
        summary.applied += report.applied;
        summary.quarantined += report.quarantined;
        summary.clock_skewed += report.clock_skewed;
        summary.exchanges += 1;
        if !push.more && !batch.more {
            return Ok(summary);
        }
        if push.next_since <= cursors.pushed_seq && batch.next_since <= cursors.pulled_seq {
            return Err(NetError::Protocol("sync is not making progress".into()));
        }
    }
}
