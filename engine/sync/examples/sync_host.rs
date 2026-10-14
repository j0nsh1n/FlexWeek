//! Desktop side of a hand test: `sync_host <flexweek.db> <key file> [user id] [lan]`.
//! Prints the pairing code and QR text, then serves syncs until a line is read from stdin.

use flexweek_sync::net::{NodeConfig, SyncService, Transport};
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: sync_host <flexweek.db> <key file> [user id] [lan]");
        std::process::exit(2);
    }
    let user_id: i64 = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(1);
    let transport = if args.get(4).is_some_and(|v| v == "lan") {
        Transport::LanOnly { bind: None }
    } else {
        Transport::Auto
    };
    let mut cfg = NodeConfig::new(
        Path::new(&args[1]),
        Path::new(&args[2]),
        "sync_host",
        transport,
    );
    cfg.scan_interval = Some(std::time::Duration::from_secs(1));
    let service = SyncService::start(cfg).expect("start");
    let offer = service.pair_start(user_id).expect("pair_start");
    println!("DEVICE {}", service.device_id());
    println!("ADDRS {:?}", service.local_addrs());
    println!("CODE {}", offer.display_code);
    println!("QR {}", offer.qr);
    let mut line = String::new();
    let _ = std::io::stdin().read_line(&mut line);
    service.stop();
}
