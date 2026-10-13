//! Phone side of a hand test: `sync_dial <flexweek.db> <key file> <QR text or code> [lan]`.
//! Pairs, then runs one sync and prints what moved.

use flexweek_sync::net::{NodeConfig, SyncService, Transport};
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 {
        eprintln!("usage: sync_dial <flexweek.db> <key file> <QR text or code> [lan]");
        std::process::exit(2);
    }
    let transport = if args.get(4).is_some_and(|v| v == "lan") {
        Transport::LanOnly { bind: None }
    } else {
        Transport::Auto
    };
    let cfg = NodeConfig::new(
        Path::new(&args[1]),
        Path::new(&args[2]),
        "sync_dial",
        transport,
    );
    let service = SyncService::start(cfg).expect("start");
    let host = if args[3].starts_with("flexweek://") {
        service.pair_from_qr(&args[3], 45_000)
    } else {
        service.pair_with_code(&args[3], &[], 45_000)
    }
    .expect("pair");
    println!("PAIRED with {} ({})", host.host_name, host.host_device_id);
    let summary = service
        .sync_once(&host.host_device_id, 45_000)
        .expect("sync");
    println!("SYNCED {summary:?}");
    service.stop();
}
