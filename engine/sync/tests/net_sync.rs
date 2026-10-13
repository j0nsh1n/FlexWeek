mod common;

use common::*;
use flexweek_sync::net::{NetError, PairStatus};

#[test]
fn pair_by_qr_then_sync_both_ways() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    put_assignment(&desktop.db(), "a1", "Read chapter 3", "");

    let offer = desktop.service.pair_start(1).unwrap();
    assert_eq!(offer.code.len(), 8);
    assert!(offer.code.bytes().all(|b| b.is_ascii_digit()));
    assert_eq!(
        offer.display_code,
        format!("{} {}", &offer.code[..4], &offer.code[4..])
    );
    let host = phone.service.pair_from_qr(&offer.qr, 20_000).unwrap();
    assert_eq!(host.username, "student");
    assert_eq!(host.host_device_id, desktop.id());
    assert!(matches!(
        desktop.service.pair_status(),
        PairStatus::Paired(ref peer) if peer.device_id == phone.id() && peer.device_name == "phone"
    ));

    // First sync: the whole account arrives.
    let first = phone.service.sync_once(&desktop.id(), 20_000).unwrap();
    assert!(first.received >= 2, "account and assignment, got {first:?}");
    let got = get_assignment(&phone.db(), "a1").unwrap();
    assert_eq!(got["title"], "Read chapter 3");
    assert_eq!(got["estimate_min"], 30);

    // Phone edits and adds; the desktop receives it when the phone dials.
    put_assignment(&phone.db(), "a1", "Read chapter 3 and 4", "");
    put_assignment(&phone.db(), "a2", "Lab report", "");
    phone.service.sync_once(&desktop.id(), 20_000).unwrap();
    let on_desktop = desktop.db();
    assert_eq!(
        get_assignment(&on_desktop, "a1").unwrap()["title"],
        "Read chapter 3 and 4"
    );
    assert_eq!(
        get_assignment(&on_desktop, "a2").unwrap()["title"],
        "Lab report"
    );

    // The desktop edits; the phone receives it on its next sync.
    desktop.clock.advance(5_000);
    put_assignment(&desktop.db(), "a2", "Lab report, draft 2", "");
    phone.service.sync_once(&desktop.id(), 20_000).unwrap();
    assert_eq!(
        get_assignment(&phone.db(), "a2").unwrap()["title"],
        "Lab report, draft 2"
    );

    // And the desktop can dial the phone: its address came with the pairing.
    phone.clock.advance(5_000);
    put_assignment(&phone.db(), "a3", "Quiz prep", "");
    let summary = desktop.service.sync_once(&phone.id(), 20_000).unwrap();
    assert_eq!(summary.applied, 1);
    assert_eq!(
        get_assignment(&desktop.db(), "a3").unwrap()["title"],
        "Quiz prep"
    );
}

#[test]
fn a_sync_with_nothing_new_changes_nothing() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    put_assignment(&desktop.db(), "a1", "Read", "");
    let desktop_id = pair(&desktop, &phone);
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    let before = desktop.service.generation();
    let again = phone.service.sync_once(&desktop_id, 20_000).unwrap();
    assert_eq!(again.applied, 0);
    assert_eq!(again.sent, 0);
    assert_eq!(again.exchanges, 1);
    assert_eq!(desktop.service.generation(), before);
}

#[test]
fn generation_rises_when_a_batch_changes_data() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    let phone_before = phone.service.generation();
    let desktop_before = desktop.service.generation();
    put_assignment(&desktop.db(), "a1", "Read", "");
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    assert_eq!(phone.service.generation(), phone_before + 1);
    assert_eq!(desktop.service.generation(), desktop_before);
    put_assignment(&phone.db(), "a2", "Lab", "");
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    assert_eq!(desktop.service.generation(), desktop_before + 1);
}

#[test]
fn a_hundred_kilobyte_batch_round_trips_under_a_deadline() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let notes = "n".repeat(400);
    {
        let conn = desktop.db();
        for index in 0..220 {
            put_assignment(
                &conn,
                &format!("a{index}"),
                &format!("Task {index}"),
                &notes,
            );
        }
    }
    let desktop_id = pair(&desktop, &phone);
    let summary = phone.service.sync_once(&desktop_id, 30_000).unwrap();
    assert_eq!(
        summary.exchanges, 1,
        "220 records of ~470 bytes fit one batch"
    );
    let on_phone = phone.db();
    for index in 0..220 {
        let got = get_assignment(&on_phone, &format!("a{index}")).unwrap();
        assert_eq!(got["title"], format!("Task {index}"));
        assert_eq!(got["notes"].as_str().unwrap().len(), 400);
    }
}

#[test]
fn a_big_account_arrives_in_several_batches() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let notes = "n".repeat(900);
    {
        let conn = desktop.db();
        for index in 0..600 {
            put_assignment(
                &conn,
                &format!("a{index}"),
                &format!("Task {index}"),
                &notes,
            );
        }
    }
    let desktop_id = pair(&desktop, &phone);
    let summary = phone.service.sync_once(&desktop_id, 40_000).unwrap();
    assert!(
        summary.exchanges >= 3,
        "600 x ~1 KB is over two 256 KiB batches: {summary:?}"
    );
    let count = |conn: &rusqlite::Connection, sql: &str| -> i64 {
        conn.query_row(sql, [], |row| row.get(0)).unwrap()
    };
    let (on_phone, on_desktop) = (phone.db(), desktop.db());
    assert_eq!(
        count(
            &on_phone,
            "SELECT count(*) FROM assignments WHERE user_id = 1"
        ),
        600
    );
    // Every stamped record on the desktop (assignments, the account, the preference columns)
    // exists on the phone with the same stamp.
    let stamps = "SELECT count(*) FROM sync_record WHERE user_id = 1 AND deleted = 0";
    assert_eq!(count(&on_phone, stamps), count(&on_desktop, stamps));
    assert!(summary.received as i64 >= count(&on_desktop, stamps));
    for index in [0, 299, 599] {
        assert_eq!(
            get_assignment(&on_phone, &format!("a{index}")).unwrap()["title"],
            format!("Task {index}")
        );
    }
}

#[test]
fn a_phone_with_another_account_refuses_to_pair() {
    let first = device("first", true);
    let second = device("second", true);
    let phone = device("phone", false);
    pair(&first, &phone);
    let offer = second.service.pair_start(1).unwrap();
    let error = phone.service.pair_from_qr(&offer.qr, 20_000).unwrap_err();
    assert!(matches!(error, NetError::AlreadyLinked), "{error}");
    assert_eq!(error.kind(), "already_linked");
    assert!(
        second.service.peers(1).unwrap().is_empty(),
        "a phone that could not finish must not stay admitted"
    );
    assert_eq!(phone.service.peers(1).unwrap().len(), 1);
}

#[test]
fn the_desktop_scan_loop_stamps_edits_made_by_another_connection() {
    let dir = scratch("scanner");
    let db = make_db(&dir, true);
    let clock = TestClock::new();
    let mut cfg = config(&dir, "desktop", &clock);
    cfg.scan_interval = Some(std::time::Duration::from_millis(100));
    let service = flexweek_sync::net::SyncService::start(cfg).unwrap();
    service.pair_start(1).unwrap();
    let conn = flexweek_store::open_connection(&db).unwrap();
    put_assignment(&conn, "a1", "Read", "");
    let stamped = |id: &str| -> i64 {
        conn.query_row(
            "SELECT count(*) FROM sync_record WHERE user_id = 1 AND entity = 'assignment' AND key = ?1",
            [id],
            |row| row.get(0),
        )
        .unwrap()
    };
    let started = std::time::Instant::now();
    while stamped("a1") == 0 && started.elapsed() < std::time::Duration::from_secs(5) {
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
    assert_eq!(
        stamped("a1"),
        1,
        "the loop should stamp a new assignment on its own"
    );
}

#[test]
fn a_big_push_from_the_phone_arrives_in_several_batches() {
    let desktop = device("desktop", true);
    let phone = device("phone", false);
    let desktop_id = pair(&desktop, &phone);
    phone.service.sync_once(&desktop_id, 20_000).unwrap();
    let notes = "n".repeat(900);
    {
        let conn = phone.db();
        for index in 0..600 {
            put_assignment(
                &conn,
                &format!("p{index}"),
                &format!("Phone task {index}"),
                &notes,
            );
        }
    }
    let summary = phone.service.sync_once(&desktop_id, 40_000).unwrap();
    assert!(summary.exchanges >= 3, "{summary:?}");
    assert_eq!(summary.sent, 600);
    let on_desktop = desktop.db();
    let count: i64 = on_desktop
        .query_row(
            "SELECT count(*) FROM assignments WHERE user_id = 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(count, 600);
    for index in [0, 300, 599] {
        assert_eq!(
            get_assignment(&on_desktop, &format!("p{index}")).unwrap()["title"],
            format!("Phone task {index}")
        );
    }
}

#[test]
fn sync_all_visits_every_paired_device() {
    let desktop = device("desktop", true);
    let (first, second) = (device("first", false), device("second", false));
    pair(&desktop, &first);
    pair(&desktop, &second);
    put_assignment(&first.db(), "never-synced", "Before", "");
    let mut results = desktop.service.sync_all(20_000).unwrap();
    results.sort_by(|a, b| a.0.cmp(&b.0));
    let mut expected = [first.id(), second.id()];
    expected.sort();
    assert_eq!(
        results.iter().map(|r| r.0.clone()).collect::<Vec<_>>(),
        expected
    );
    assert!(
        results.iter().all(|(_, result)| result.is_ok()),
        "{results:?}"
    );
}
