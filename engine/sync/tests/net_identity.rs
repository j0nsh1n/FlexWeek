use crate::common::*;
use flexweek_sync::net::SyncService;
use flexweek_sync::net::identity::load_or_create_key;
use flexweek_sync::net::protocol::{
    derive_pair_keys, display_code, hello_proof, hello_proof_matches, normalize_code,
};
use flexweek_sync::net::qr;

#[cfg(unix)]
#[test]
fn the_key_file_is_private_and_beside_the_database() {
    use std::os::unix::fs::PermissionsExt;
    let device = device("desktop", true);
    let mode = std::fs::metadata(&device.key).unwrap().permissions().mode() & 0o777;
    assert_eq!(mode, 0o600);
    assert_eq!(std::fs::metadata(&device.key).unwrap().len(), 32);
    assert_eq!(
        device.key.parent().unwrap().parent().unwrap(),
        device.db.parent().unwrap()
    );
    let database = std::fs::read(&device.db).unwrap();
    let key = std::fs::read(&device.key).unwrap();
    assert!(
        !database.windows(32).any(|window| window == key.as_slice()),
        "the secret key must never be written into the database"
    );
}

#[cfg(unix)]
#[test]
fn a_key_file_others_can_read_is_made_private() {
    use std::os::unix::fs::PermissionsExt;
    let dir = scratch("loose");
    let path = dir.join("device.key");
    load_or_create_key(&path).unwrap();
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o644)).unwrap();
    load_or_create_key(&path).unwrap();
    assert_eq!(
        std::fs::metadata(&path).unwrap().permissions().mode() & 0o777,
        0o600
    );
}

#[test]
fn the_endpoint_id_survives_a_restart() {
    let first = device("desktop", true);
    let id = first.id();
    first.service.stop();
    let cfg = config(&first.dir, "desktop", &first.clock);
    let second = SyncService::start(cfg).unwrap();
    assert_eq!(second.device_id(), id);
}

#[test]
fn a_damaged_key_file_is_an_error_not_a_new_identity() {
    let dir = scratch("damaged");
    make_db(&dir, true);
    let clock = TestClock::new();
    let cfg = config(&dir, "desktop", &clock);
    std::fs::create_dir_all(cfg.key_path.parent().unwrap()).unwrap();
    std::fs::write(&cfg.key_path, b"too short").unwrap();
    let error = SyncService::start(cfg.clone()).err().unwrap();
    assert_eq!(error.kind(), "key");
    assert_eq!(std::fs::read(&cfg.key_path).unwrap(), b"too short");
}

#[test]
fn a_copied_database_will_not_sync_as_the_original_device() {
    let original = device("desktop", true);
    original.service.stop();
    let copy_dir = scratch("copy");
    std::fs::copy(&original.db, copy_dir.join("flexweek.db")).unwrap();
    let clock = TestClock::new();
    let cfg = config(&copy_dir, "desktop copy", &clock);
    let error = SyncService::start(cfg).err().unwrap();
    assert_eq!(error.kind(), "device_mismatch", "{error}");
}

#[test]
fn a_code_always_derives_the_same_endpoint_and_another_code_a_different_one() {
    let a = derive_pair_keys("12345678").unwrap();
    let again = derive_pair_keys("1234 5678").unwrap();
    let b = derive_pair_keys("12345679").unwrap();
    assert_eq!(a.secret.public(), again.secret.public());
    assert_eq!(a.proof_key, again.proof_key);
    assert_ne!(a.secret.public(), b.secret.public());
    assert_ne!(a.proof_key, b.proof_key);
    assert_ne!(
        a.secret.to_bytes(),
        a.proof_key,
        "the proof key must not be the endpoint's secret"
    );
}

#[test]
fn the_code_stretch_matches_an_independent_scrypt() {
    // Independent Python hashlib.scrypt vector for the test-only N=16, r=8, p=1 cost.
    let keys = derive_pair_keys("12345678").unwrap();
    let output = [keys.secret.to_bytes(), keys.proof_key].concat();
    assert_eq!(
        hex(&output),
        "6ee5ffefd2fd6a9c1af74724db5a2e71745da1dc4bac4a59f4a0d1eab1a1745568c19f2f80762c37253c55960b5b5d004d834da6cbeb4fc0a260e7e76267f109"
    );
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[test]
fn the_proof_binds_every_field() {
    let keys = derive_pair_keys("12345678").unwrap();
    let nonce = [1u8; 16];
    let id = [2u8; 32];
    let proof = hello_proof(&keys.proof_key, &nonce, &id, "device", "Phone");
    assert!(hello_proof_matches(
        &keys.proof_key,
        &nonce,
        &id,
        "device",
        "Phone",
        &proof
    ));
    assert!(!hello_proof_matches(
        &keys.proof_key,
        &[9u8; 16],
        &id,
        "device",
        "Phone",
        &proof
    ));
    assert!(!hello_proof_matches(
        &keys.proof_key,
        &nonce,
        &[3u8; 32],
        "device",
        "Phone",
        &proof
    ));
    assert!(!hello_proof_matches(
        &keys.proof_key,
        &nonce,
        &id,
        "other",
        "Phone",
        &proof
    ));
    assert!(!hello_proof_matches(
        &keys.proof_key,
        &nonce,
        &id,
        "device",
        "Tablet",
        &proof
    ));
    let other = derive_pair_keys("87654321").unwrap();
    assert!(!hello_proof_matches(
        &other.proof_key,
        &nonce,
        &id,
        "device",
        "Phone",
        &proof
    ));
    // "ab"+"c" and "a"+"bc" must not collide.
    let joined = hello_proof(&keys.proof_key, &nonce, &id, "ab", "c");
    assert!(!hello_proof_matches(
        &keys.proof_key,
        &nonce,
        &id,
        "a",
        "bc",
        &joined
    ));
}

#[test]
fn codes_are_normalised_and_displayed_in_two_groups() {
    for text in ["12345678", "1234 5678", "1234-5678", " 1234  5678 "] {
        assert_eq!(normalize_code(text).unwrap(), "12345678", "{text:?}");
    }
    for text in ["", "1234567", "123456789", "1234 567a", "１２３４５６７８"] {
        assert_eq!(
            normalize_code(text).unwrap_err().kind(),
            "bad_code",
            "{text:?}"
        );
    }
    assert_eq!(display_code("12345678"), "1234 5678");
}

#[test]
fn the_qr_text_round_trips() {
    let hints: Vec<std::net::SocketAddr> = vec![
        "192.168.1.5:5555".parse().unwrap(),
        "[fd00::1]:6000".parse().unwrap(),
    ];
    let text = qr::build("12345678", &hints);
    assert_eq!(
        text,
        "flexweek://pair/2?c=12345678&a=192.168.1.5:5555,[fd00::1]:6000"
    );
    let parsed = qr::parse(&text).unwrap();
    assert_eq!(parsed.code, "12345678");
    assert_eq!(parsed.hints, hints);
    let bare = qr::build("12345678", &[]);
    assert_eq!(bare, "flexweek://pair/2?c=12345678");
    assert!(qr::parse(&bare).unwrap().hints.is_empty());
}

#[test]
fn unreadable_qr_text_is_refused() {
    for text in [
        "https://example.test/?c=12345678",
        "flexweek://pair/2?a=1.2.3.4:5",
        "flexweek://pair/2?c=1234",
        "flexweek://pair/2?c=12345678&a=not-an-address",
    ] {
        assert!(qr::parse(text).is_err(), "{text:?}");
    }
}

#[test]
fn old_and_future_qr_versions_are_refused_before_pairing() {
    let phone = device("phone", false);
    for text in [
        "flexweek://pair?c=12345678",
        "flexweek://pair/1?c=12345678",
        "flexweek://pair/3?c=12345678",
    ] {
        let error = phone.service.pair_from_qr(text, 20_000).unwrap_err();
        assert_eq!(error.kind(), "version_mismatch");
        assert_eq!(
            error.to_string(),
            "these devices use different pairing versions; update FlexWeek on both devices"
        );
        assert!(phone.service.peers(1).unwrap().is_empty());
    }
}

#[test]
fn an_offer_carries_the_hints_the_phone_needs() {
    let desktop = device("desktop", true);
    let offer = desktop.service.pair_start(1).unwrap();
    let payload = qr::parse(&offer.qr).unwrap();
    assert_eq!(payload.code, offer.code);
    assert_eq!(payload.hints.len(), 1);
    assert_eq!(payload.hints[0].ip().to_string(), "127.0.0.1");
    assert_ne!(
        payload.hints[0],
        desktop.service.local_addrs()[0],
        "a separate endpoint, a separate port"
    );
}
