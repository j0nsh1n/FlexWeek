mod common;

use common::*;
use flexweek_sync::net::protocol::PAIR_EXPIRY_MS;
use flexweek_sync::net::{NetError, PairRefusal, PairStatus};

const WRONG: &str = "00000000";

fn tries_left(desktop: &Device) -> u32 {
    match desktop.service.pair_status() {
        PairStatus::Waiting { tries_left, .. } => tries_left,
        other => panic!("expected a waiting offer, got {other:?}"),
    }
}

#[test]
fn a_wrong_proof_is_refused_and_counts_a_try() {
    let desktop = device("desktop", true);
    let offer = desktop.service.pair_start(1).unwrap();
    assert_ne!(offer.code, WRONG);
    assert_eq!(tries_left(&desktop), 3);
    let client = raw_endpoint();

    let first = RawPair::new(&client, &offer.qr, &offer.code)
        .proof_from(WRONG)
        .run();
    assert_eq!(first["ok"], false);
    assert_eq!(first["code"], "wrong_code");
    assert_eq!(tries_left(&desktop), 2);

    let second = RawPair::new(&client, &offer.qr, &offer.code)
        .proof_from(WRONG)
        .run();
    assert_eq!(second["code"], "wrong_code");
    assert_eq!(tries_left(&desktop), 1);

    // The third try is still allowed, and the right proof pairs.
    let third = RawPair::new(&client, &offer.qr, &offer.code).run();
    assert_eq!(third["ok"], true);
    assert_eq!(third["username"], "student");
    assert!(matches!(
        desktop.service.pair_status(),
        PairStatus::Paired(_)
    ));
}

#[test]
fn the_fourth_try_is_refused_even_with_the_right_proof() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    let client = raw_endpoint();
    for _ in 0..3 {
        let reply = RawPair::new(&client, &offer.qr, &offer.code)
            .proof_from(WRONG)
            .run();
        assert_eq!(reply["code"], "wrong_code");
    }
    assert_eq!(desktop.service.pair_status(), PairStatus::TooManyTries);
    let fourth = RawPair::new(&client, &offer.qr, &offer.code).run();
    assert_eq!(fourth["ok"], false);
    assert_eq!(fourth["code"], "too_many_tries");
    let error = phone.service.pair_from_qr(&offer.qr, 20_000).unwrap_err();
    assert!(
        matches!(error, NetError::PairRefused(PairRefusal::TooManyTries)),
        "{error}"
    );
    assert!(desktop.service.peers(1).unwrap().is_empty());
}

#[test]
fn a_code_expires_after_five_minutes() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let started = desktop.clock.now();
    let offer = desktop.service.pair_start(1).unwrap();
    assert_eq!(offer.expires_at_ms, started + PAIR_EXPIRY_MS);
    desktop.clock.advance(PAIR_EXPIRY_MS);
    assert_eq!(desktop.service.pair_status(), PairStatus::Expired);
    let error = phone.service.pair_from_qr(&offer.qr, 20_000).unwrap_err();
    assert!(
        matches!(error, NetError::PairRefused(PairRefusal::Expired)),
        "{error}"
    );
    assert!(desktop.service.peers(1).unwrap().is_empty());
}

#[test]
fn a_code_still_works_one_millisecond_before_it_expires() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    desktop.clock.advance(PAIR_EXPIRY_MS - 1);
    phone.service.pair_from_qr(&offer.qr, 20_000).unwrap();
    assert_eq!(desktop.service.peers(1).unwrap().len(), 1);
}

#[test]
fn a_code_works_once() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    phone.service.pair_from_qr(&offer.qr, 20_000).unwrap();

    let client = raw_endpoint();
    let reply = RawPair::new(&client, &offer.qr, &offer.code).run();
    assert_eq!(reply["ok"], false);
    assert_eq!(reply["code"], "used");

    let other = device("other phone", false);
    let error = other.service.pair_from_qr(&offer.qr, 20_000).unwrap_err();
    assert!(
        matches!(error, NetError::PairRefused(PairRefusal::Used)),
        "{error}"
    );
    let peers = desktop.service.peers(1).unwrap();
    assert_eq!(peers.len(), 1);
    assert_eq!(peers[0].device_id, phone.id());
}

#[test]
fn a_hello_claiming_another_endpoint_is_refused() {
    let desktop = device("desktop", true);
    let offer = desktop.service.pair_start(1).unwrap();
    let client = raw_endpoint();
    let victim = raw_endpoint();
    let reply = RawPair::new(&client, &offer.qr, &offer.code)
        .claiming(&victim)
        .run();
    assert_eq!(reply["code"], "wrong_code");
    assert_eq!(tries_left(&desktop), 2);
    assert!(desktop.service.peers(1).unwrap().is_empty());
}

#[test]
fn a_typed_wrong_code_never_reaches_the_desktop() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    assert_ne!(offer.code, WRONG);
    let error = phone
        .service
        .pair_with_code(WRONG, &hints_of(&offer.qr), 3_000)
        .unwrap_err();
    assert!(
        matches!(error, NetError::Unreachable(_) | NetError::Timeout),
        "a different code derives a different endpoint: {error}"
    );
    assert_eq!(tries_left(&desktop), 3);
}

#[test]
fn a_new_code_replaces_the_old_one() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let old = desktop.service.pair_start(1).unwrap();
    let new = desktop.service.pair_start(1).unwrap();
    assert_ne!(old.code, new.code);
    let error = phone.service.pair_from_qr(&old.qr, 3_000).unwrap_err();
    assert!(
        matches!(error, NetError::Unreachable(_) | NetError::Timeout),
        "{error}"
    );
    phone.service.pair_from_qr(&new.qr, 20_000).unwrap();
}

#[test]
fn cancelling_closes_the_window() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    desktop.service.pair_cancel();
    assert_eq!(desktop.service.pair_status(), PairStatus::Idle);
    let error = phone.service.pair_from_qr(&offer.qr, 3_000).unwrap_err();
    assert!(
        matches!(error, NetError::Unreachable(_) | NetError::Timeout),
        "{error}"
    );
}

#[test]
fn a_badly_typed_code_is_rejected_before_any_network_call() {
    let phone = device("phone", false);
    for bad in ["1234567", "123456789", "1234 56a8", ""] {
        let error = phone.service.pair_with_code(bad, &[], 1_000).unwrap_err();
        assert_eq!(error.kind(), "bad_code", "{bad:?}");
    }
}

#[test]
fn a_device_id_that_is_not_the_endpoint_id_is_refused() {
    let desktop = device("desktop", true);
    let offer = desktop.service.pair_start(1).unwrap();
    let client = raw_endpoint();
    let reply = RawPair::new(&client, &offer.qr, &offer.code)
        .device_id("someone-elses-device")
        .run();
    assert_eq!(reply["code"], "wrong_code");
    assert!(desktop.service.peers(1).unwrap().is_empty());
}

#[test]
fn a_phone_that_never_confirms_leaves_nothing_behind() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    let client = raw_endpoint();
    let reply = RawPair::new(&client, &offer.qr, &offer.code)
        .without_confirming()
        .run();
    assert_eq!(
        reply["ok"], true,
        "the proof was right, the phone just left"
    );
    assert!(desktop.service.peers(1).unwrap().is_empty());
    assert_eq!(tries_left(&desktop), 3);
    // The code was not spent, so a real phone can still use it.
    phone.service.pair_from_qr(&offer.qr, 20_000).unwrap();
    assert_eq!(desktop.service.peers(1).unwrap().len(), 1);
}

#[test]
fn a_second_phone_waits_while_the_first_has_not_confirmed() {
    let desktop = device("desktop", true);
    let late = device("late phone", false);
    let offer = desktop.service.pair_start(1).unwrap();
    let client = raw_endpoint();
    let first = RawPair::new(&client, &offer.qr, &offer.code).open();
    assert_eq!(first.reply["ok"], true);

    let (service, qr) = (late.service.clone(), offer.qr.clone());
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let _ = tx.send(service.pair_from_qr(&qr, 30_000));
    });
    assert!(
        rx.recv_timeout(std::time::Duration::from_millis(2_500))
            .is_err(),
        "the second phone must wait for the first to confirm or leave"
    );
    first.confirm();
    let result = rx.recv_timeout(std::time::Duration::from_secs(20)).unwrap();
    let error = result.unwrap_err();
    assert!(
        matches!(error, NetError::PairRefused(PairRefusal::Used)),
        "{error}"
    );
    let peers = desktop.service.peers(1).unwrap();
    assert_eq!(peers.len(), 1);
    assert_eq!(peers[0].name, "Raw phone");
}
