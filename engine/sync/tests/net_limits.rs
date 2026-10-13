mod common;

use std::net::SocketAddr;
use std::sync::mpsc;
use std::time::{Duration, Instant};

use common::*;
use flexweek_sync::net::protocol::{CLOSE_NOT_PAIRED, SYNC_ALPN};
use flexweek_sync::net::runtime::block_on;
use flexweek_sync::net::{NetError, SyncService};
use flexweek_sync::{Peer, list_peers, upsert_peer};
use iroh::endpoint::{Connection, ConnectionError, presets};
use iroh::protocol::{AcceptError, ProtocolHandler, Router};
use iroh::{Endpoint, RelayMode, SecretKey};

/// Accepts a sync connection and then says nothing, so only a deadline can end the sync.
#[derive(Debug, Clone)]
struct BlackHole;

impl ProtocolHandler for BlackHole {
    async fn accept(&self, connection: Connection) -> Result<(), AcceptError> {
        // Held open: dropping the streams would end the request with an empty reply instead.
        let streams = connection.accept_bi().await;
        tokio::time::sleep(Duration::from_secs(120)).await;
        drop(streams);
        Ok(())
    }
}

struct Hole {
    _router: Router,
    id: String,
    addr: SocketAddr,
}

fn black_hole() -> Hole {
    host_with(BlackHole)
}

fn host_with(handler: impl ProtocolHandler) -> Hole {
    block_on(async {
        let endpoint = Endpoint::builder(presets::Minimal)
            .relay_mode(RelayMode::Disabled)
            .clear_ip_transports()
            .bind_addr("127.0.0.1:0")
            .unwrap()
            .secret_key(SecretKey::generate())
            .bind()
            .await
            .unwrap();
        let addr = endpoint.bound_sockets()[0];
        let id = endpoint.id().to_string();
        let router = Router::builder(endpoint).accept(SYNC_ALPN, handler).spawn();
        Hole {
            _router: router,
            id,
            addr,
        }
    })
}

/// Pairs for real, then points the phone's record of the desktop at some other endpoint.
fn phone_pointing_at(endpoint_id: &str, addr: SocketAddr) -> (Device, Device, String) {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    let conn = phone.db();
    let user_id: i64 = conn
        .query_row("SELECT id FROM users", [], |row| row.get(0))
        .unwrap();
    let peer: Peer = list_peers(&conn, user_id).unwrap().remove(0);
    upsert_peer(
        &conn,
        user_id,
        &Peer {
            endpoint_id: endpoint_id.to_owned(),
            ..peer
        },
    )
    .unwrap();
    phone.service.set_peer_addrs(endpoint_id, &[addr]);
    (desktop, phone, desktop_id)
}

type Finished = (Instant, Result<(), NetError>);

/// Runs `sync_once` on its own thread so a test whose deadline is broken fails instead of hanging.
fn sync_in_thread(
    service: &std::sync::Arc<SyncService>,
    peer: &str,
    deadline_ms: u64,
) -> mpsc::Receiver<Finished> {
    let (tx, rx) = mpsc::channel();
    let (service, peer) = (service.clone(), peer.to_owned());
    std::thread::spawn(move || {
        let result = service.sync_once(&peer, deadline_ms).map(|_| ());
        let _ = tx.send((Instant::now(), result));
    });
    rx
}

#[test]
fn a_silent_peer_ends_at_the_deadline() {
    let hole = black_hole();
    let (_desktop, phone, desktop_id) = phone_pointing_at(&hole.id, hole.addr);
    let started = Instant::now();
    let rx = sync_in_thread(&phone.service, &desktop_id, 1_500);
    let (finished, result) = rx
        .recv_timeout(Duration::from_secs(20))
        .expect("sync_once never returned: the deadline is not enforced");
    let error = result.unwrap_err();
    assert_eq!(error.kind(), "timeout", "{error}");
    let elapsed = finished.duration_since(started);
    assert!(elapsed >= Duration::from_millis(1_400), "{elapsed:?}");
    assert!(elapsed < Duration::from_secs(6), "{elapsed:?}");
}

#[test]
fn cancel_sync_returns_at_once() {
    let hole = black_hole();
    let (_desktop, phone, desktop_id) = phone_pointing_at(&hole.id, hole.addr);
    let rx = sync_in_thread(&phone.service, &desktop_id, 60_000);
    std::thread::sleep(Duration::from_millis(800));
    assert!(
        rx.try_recv().is_err(),
        "the sync should still be waiting on the silent peer"
    );
    let cancelled_at = Instant::now();
    phone.service.cancel_sync();
    let (finished, result) = rx
        .recv_timeout(Duration::from_secs(5))
        .expect("cancel_sync did not end the sync");
    assert_eq!(result.unwrap_err().kind(), "cancelled");
    assert!(
        finished.duration_since(cancelled_at) < Duration::from_millis(500),
        "{:?}",
        finished.duration_since(cancelled_at)
    );
}

#[test]
fn cancelling_when_nothing_runs_does_not_cancel_the_next_sync() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    phone.service.cancel_sync();
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
}

#[test]
fn connecting_gives_up_after_ten_seconds() {
    // Nothing listens on the discard port, so the dial can only time out.
    let nowhere: SocketAddr = "127.0.0.1:9".parse().unwrap();
    let (_desktop, phone, desktop_id) =
        phone_pointing_at(&SecretKey::generate().public().to_string(), nowhere);
    let started = Instant::now();
    let rx = sync_in_thread(&phone.service, &desktop_id, 45_000);
    let (finished, result) = rx
        .recv_timeout(Duration::from_secs(30))
        .expect("the connect step has no limit of its own");
    let error = result.unwrap_err();
    assert_eq!(error.kind(), "unreachable", "{error}");
    let elapsed = finished.duration_since(started);
    assert!(elapsed >= Duration::from_secs(9), "{elapsed:?}");
    assert!(elapsed < Duration::from_secs(14), "{elapsed:?}");
}

#[test]
fn an_unpaired_endpoint_cannot_open_the_sync_stream() {
    let desktop = device("desktop", true);
    let client = raw_endpoint();
    let address = iroh::EndpointAddr::new(desktop.id().parse().unwrap())
        .with_ip_addr(desktop.service.local_addrs()[0]);
    let reason = block_on(async {
        let connection = client.connect(address, SYNC_ALPN).await.unwrap();
        let attempt = async {
            if let Ok((mut send, mut recv)) = connection.open_bi().await {
                let _ = send.write_all(b"{}").await;
                let _ = send.finish();
                let _ = recv.read_to_end(1 << 16).await;
            }
            connection.closed().await
        };
        tokio::time::timeout(Duration::from_secs(10), attempt).await
    })
    .expect("the desktop kept the connection open for an unpaired endpoint");
    assert!(
        matches!(reason, ConnectionError::ApplicationClosed(ref close)
            if close.error_code.into_inner() == u64::from(CLOSE_NOT_PAIRED)),
        "{reason}"
    );
}

#[test]
fn a_removed_phone_is_refused() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    desktop.service.unlink(1, &phone.id(), false).unwrap();
    put_assignment(&desktop.db(), "a1", "After removal", "");
    let error = phone.service.sync_once(&desktop_id, 20_000).unwrap_err();
    assert_eq!(error.kind(), "not_paired", "{error}");
    assert!(
        get_assignment(&phone.db(), "a1").is_none(),
        "a removed phone must receive nothing new"
    );
}

#[test]
fn removing_a_phone_tells_it() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    assert!(desktop.service.unlink(1, &phone.id(), true).unwrap());
    let on_phone = list_peers(&phone.db(), 1).unwrap();
    assert!(
        on_phone[0].revoked,
        "the phone should have marked the desktop as removed"
    );
    let error = phone.service.sync_once(&desktop_id, 5_000).unwrap_err();
    assert_eq!(error.kind(), "not_paired");
}

#[test]
fn an_unknown_peer_name_is_not_paired() {
    let phone = device("phone", false);
    let error = phone.service.sync_once("nobody", 5_000).unwrap_err();
    assert_eq!(error.kind(), "not_paired");
}

#[test]
fn stopping_ends_a_running_sync_and_later_calls_fail() {
    let hole = black_hole();
    let (_desktop, phone, desktop_id) = phone_pointing_at(&hole.id, hole.addr);
    let rx = sync_in_thread(&phone.service, &desktop_id, 60_000);
    std::thread::sleep(Duration::from_millis(800));
    phone.service.stop();
    let (_, result) = rx
        .recv_timeout(Duration::from_secs(5))
        .expect("stop did not end the sync");
    assert_eq!(result.unwrap_err().kind(), "cancelled");
    assert_eq!(
        phone
            .service
            .sync_once(&desktop_id, 5_000)
            .unwrap_err()
            .kind(),
        "stopped"
    );
    assert!(!phone.service.status().listening);
}

#[test]
fn starting_on_the_default_network_does_not_wait_for_it() {
    let dir = scratch("auto");
    make_db(&dir, true);
    let clock = TestClock::new();
    let mut cfg = config(&dir, "desktop", &clock);
    cfg.transport = flexweek_sync::net::Transport::Auto;
    let started = Instant::now();
    let service = SyncService::start(cfg).unwrap();
    assert!(
        started.elapsed() < Duration::from_secs(5),
        "{:?}",
        started.elapsed()
    );
    service.stop();
}

#[test]
fn no_source_waits_for_the_relay_to_come_online() {
    let folder = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src/net");
    let mut checked = 0;
    for entry in std::fs::read_dir(folder).unwrap() {
        let path = entry.unwrap().path();
        let source = std::fs::read_to_string(&path).unwrap();
        for (number, line) in source.lines().enumerate() {
            let code = line.split("//").next().unwrap_or("");
            assert!(
                !code.replace(' ', "").contains(".online()"),
                "{}:{} awaits online()",
                path.display(),
                number + 1
            );
        }
        checked += 1;
    }
    assert!(checked >= 8, "the scan should cover every file in net/");
}

/// Answers every sync with an acknowledgement that does not match what was sent.
#[derive(Debug, Clone)]
struct LyingPeer {
    account_uuid: String,
}

impl ProtocolHandler for LyingPeer {
    async fn accept(&self, connection: Connection) -> Result<(), AcceptError> {
        let (mut send, mut recv) = connection.accept_bi().await?;
        let _ = recv.read_to_end(1 << 22).await;
        let reply = serde_json::json!({
            "ok": true,
            "ack_through": 999_999,
            "batch": {"account_uuid": self.account_uuid, "from_device": "x", "records": [], "next_since": 0, "more": false},
        });
        send.write_all(reply.to_string().as_bytes())
            .await
            .map_err(AcceptError::from_err)?;
        send.finish()?;
        let _ = tokio::time::timeout(Duration::from_secs(5), connection.closed()).await;
        Ok(())
    }
}

#[test]
fn a_peer_that_acknowledges_the_wrong_position_is_refused_and_no_cursor_moves() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    let uuid: String = phone
        .db()
        .query_row("SELECT account_uuid FROM sync_account", [], |row| {
            row.get(0)
        })
        .unwrap();
    let hole = host_with(LyingPeer { account_uuid: uuid });
    let conn = phone.db();
    let peer: Peer = list_peers(&conn, 1).unwrap().remove(0);
    upsert_peer(
        &conn,
        1,
        &Peer {
            endpoint_id: hole.id.clone(),
            ..peer
        },
    )
    .unwrap();
    phone.service.set_peer_addrs(&hole.id, &[hole.addr]);
    let error = phone.service.sync_once(&desktop_id, 10_000).unwrap_err();
    assert_eq!(error.kind(), "protocol", "{error}");
    let after = list_peers(&conn, 1).unwrap().remove(0);
    assert_eq!((after.pushed_seq, after.pulled_seq), (0, 0));
}
