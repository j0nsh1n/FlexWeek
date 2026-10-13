//! Needs the internet: both devices use n0's public relays and name lookup, with no address hints.
//! Run by hand: `cargo test -p flexweek-sync --lib net_relay -- --ignored`.

use crate::common::*;

use std::sync::Arc;

use flexweek_sync::net::{SyncService, Transport};

fn online_device(name: &str, account: bool) -> Device {
    let dir = scratch(name);
    let db = make_db(&dir, account);
    let clock = TestClock::new();
    let mut cfg = config(&dir, name, &clock);
    cfg.transport = Transport::Auto;
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

#[test]
#[ignore = "needs the internet (n0 relays and discovery)"]
fn pair_by_typed_code_and_sync_through_the_relay() {
    let desktop = online_device("desktop", true);
    let phone = online_device("phone", false);
    put_assignment(&desktop.db(), "a1", "Read chapter 3", "");
    let offer = desktop.service.pair_start(1).unwrap();
    // Typed, no address hints: the phone finds the desktop from the digits alone.
    let host = phone
        .service
        .pair_with_code(&offer.display_code, &[], 45_000)
        .unwrap();
    assert_eq!(host.host_device_id, desktop.id());
    phone.service.sync_once(&desktop.id(), 45_000).unwrap();
    assert_eq!(
        get_assignment(&phone.db(), "a1").unwrap()["title"],
        "Read chapter 3"
    );

    put_assignment(&phone.db(), "a2", "Lab report", "");
    phone.service.sync_once(&desktop.id(), 45_000).unwrap();
    assert_eq!(
        get_assignment(&desktop.db(), "a2").unwrap()["title"],
        "Lab report"
    );
}
