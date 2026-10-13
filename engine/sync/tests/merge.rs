use flexweek_sync::{
    Batch, Record, acknowledge_pull, acknowledge_push, apply_batch, export_since, list_peers,
    migrate, revoke_peer, scan, set_account, set_device, upsert_peer,
};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};
use std::sync::atomic::{AtomicUsize, Ordering};

const UUID: &str = "account-one";

static NEXT_DB: AtomicUsize = AtomicUsize::new(0);

/// A database with the schema `flexweek-store` really creates, so these tests cannot drift from it.
fn db(device: &str, account: bool) -> Connection {
    let path = std::path::Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!(
        "sync-{}-{}.db",
        std::process::id(),
        NEXT_DB.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = std::fs::remove_file(&path);
    flexweek_store::initialize(&path, "2026-10-12").unwrap();
    let conn = flexweek_store::open_connection(&path).unwrap();
    migrate(&conn).unwrap();
    set_device(&conn, device, device).unwrap();
    if account {
        conn.execute(
            "INSERT INTO users(id, username, password_hash) VALUES (1, 'student', 'hash')",
            [],
        )
        .unwrap();
        conn.execute("INSERT INTO preferences(user_id) VALUES (1)", [])
            .unwrap();
        set_account(&conn, 1, UUID).unwrap();
    }
    conn
}

fn assignment(id: &str, title: &str) -> Value {
    json!({"id": id, "title": title, "due": "2026-10-13", "estimate_min": 30})
}

fn block(title: &str) -> Value {
    json!({"id": "block", "title": title, "kind": "flexible", "duration_min": 30, "days": [0]})
}

fn put_assignment(conn: &Connection, id: &str, title: &str) {
    conn.execute("INSERT INTO assignments(user_id,id,body) VALUES (1,?1,?2) ON CONFLICT(user_id,id) DO UPDATE SET body=excluded.body", params![id, assignment(id, title).to_string()]).unwrap();
}

fn get_assignment(conn: &Connection, id: &str) -> Option<Value> {
    conn.query_row(
        "SELECT body FROM assignments WHERE user_id=1 AND id=?1",
        [id],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .unwrap()
    .map(|body| serde_json::from_str(&body).unwrap())
}

fn batch(from: &Connection, since: i64, requester: &str) -> Batch {
    export_since(from, 1, since, requester, 500).unwrap()
}

fn exchange(a: &mut Connection, b: &mut Connection, now: i64) {
    let to_a = batch(b, 0, "a");
    let to_b = batch(a, 0, "b");
    apply_batch(a, &to_a, now).unwrap();
    apply_batch(b, &to_b, now).unwrap();
}

type Stamped = (String, String, bool, String, i64, String);

fn state(conn: &Connection) -> Vec<Stamped> {
    let mut stmt = conn
        .prepare(
            "SELECT entity,key,deleted,hash,hlc,device_id FROM sync_record WHERE user_id=1 ORDER BY entity,key",
        )
        .unwrap();
    stmt.query_map([], |row| {
        Ok((
            row.get(0)?,
            row.get(1)?,
            row.get::<_, i64>(2)? != 0,
            row.get(3)?,
            row.get(4)?,
            row.get(5)?,
        ))
    })
    .unwrap()
    .map(Result::unwrap)
    .collect()
}

fn dump(conn: &Connection) -> Vec<String> {
    let tables: Vec<String> = conn
        .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sync_%' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        .unwrap()
        .query_map([], |row| row.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    let mut rows = Vec::new();
    for table in tables {
        let mut stmt = conn.prepare(&format!("SELECT * FROM {table}")).unwrap();
        let columns = stmt.column_count();
        let lines: Vec<String> = stmt
            .query_map([], |row| {
                Ok((0..columns)
                    .map(|index| format!("{:?}", row.get_ref(index).unwrap()))
                    .collect::<Vec<_>>()
                    .join("|"))
            })
            .unwrap()
            .map(Result::unwrap)
            .collect();
        rows.extend(lines.into_iter().map(|line| format!("{table}:{line}")));
    }
    rows
}

/// What a person would see: assignments as parsed JSON (key order and per-device revisions are
/// not content) plus the account-wide preference columns.
fn content(conn: &Connection) -> (Vec<(String, Value)>, Vec<i64>) {
    let assignments = conn
        .prepare("SELECT id, body FROM assignments ORDER BY id")
        .unwrap()
        .query_map([], |row| {
            let body: String = row.get(1)?;
            Ok((row.get(0)?, serde_json::from_str(&body).unwrap()))
        })
        .unwrap()
        .map(Result::unwrap)
        .collect();
    let prefs = conn
        .query_row(
            "SELECT reminders_enabled, reminder_lead_min, reminder_sound, reminder_dnd_override, timer_work_min, timer_break_min, timer_long_break_min, timer_long_break_every, auto_split_pomodoro FROM preferences",
            [],
            |row| (0..9).map(|index| row.get(index)).collect(),
        )
        .unwrap();
    (assignments, prefs)
}

#[test]
fn migration_is_additive_and_idempotent() {
    let path = std::path::Path::new(env!("CARGO_TARGET_TMPDIR")).join("sync-migration.db");
    let _ = std::fs::remove_file(&path);
    flexweek_store::initialize(&path, "2026-10-12").unwrap();
    let conn = flexweek_store::open_connection(&path).unwrap();
    conn.execute(
        "INSERT INTO users(id, username, password_hash) VALUES (1, 'student', 'hash')",
        [],
    )
    .unwrap();
    conn.execute("INSERT INTO preferences(user_id) VALUES (1)", [])
        .unwrap();
    put_assignment(&conn, "a1", "Read");
    conn.execute(
        "INSERT INTO weeks(user_id,week_start,blocks,revision) VALUES (1,'2026-10-12',?1,3)",
        [json!([block("Before")]).to_string()],
    )
    .unwrap();
    conn.execute("INSERT INTO recovery_codes VALUES (1,'code')", [])
        .unwrap();
    let before = dump(&conn);
    assert_eq!(before.len(), 5);
    assert!(
        conn.query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'sync_%'",
            [],
            |row| row.get::<_, i64>(0)
        )
        .unwrap()
            == 0
    );
    migrate(&conn).unwrap();
    assert_eq!(dump(&conn), before);
    migrate(&conn).unwrap();
    assert_eq!(dump(&conn), before);
    let names: Vec<String> = conn
        .prepare("SELECT name FROM sqlite_master WHERE name LIKE 'sync_%' AND type='table' ORDER BY name")
        .unwrap()
        .query_map([], |row| row.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    assert_eq!(
        names,
        [
            "sync_account",
            "sync_device",
            "sync_peer",
            "sync_quarantine",
            "sync_record"
        ]
    );
}

#[test]
fn scan_stamps_new_changed_deleted_once() {
    let mut conn = db("a", true);
    assert_eq!(scan(&mut conn, 1, 1_000).unwrap(), 12); // account and 11 account-wide preferences
    assert_eq!(scan(&mut conn, 1, 1_000).unwrap(), 0);
    put_assignment(&conn, "a1", "Read");
    assert_eq!(scan(&mut conn, 1, 1_001).unwrap(), 1);
    put_assignment(&conn, "a1", "Write");
    assert_eq!(scan(&mut conn, 1, 1_002).unwrap(), 1);
    conn.execute("DELETE FROM assignments WHERE user_id=1 AND id='a1'", [])
        .unwrap();
    assert_eq!(scan(&mut conn, 1, 1_003).unwrap(), 1);
    assert_eq!(scan(&mut conn, 1, 1_004).unwrap(), 0);
    let deleted: i64 = conn
        .query_row(
            "SELECT deleted FROM sync_record WHERE entity='assignment' AND key='a1'",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(deleted, 1);
}

#[test]
fn export_requires_a_scan_after_local_edits() {
    let mut conn = db("a", true);
    put_assignment(&conn, "a1", "Before");
    scan(&mut conn, 1, 1_000).unwrap();
    put_assignment(&conn, "a1", "After");
    assert!(export_since(&conn, 1, 0, "b", 500).is_err());
    scan(&mut conn, 1, 1_001).unwrap();
    let exported = batch(&conn, 0, "b");
    let current = exported
        .records
        .iter()
        .find(|record| record.key == "a1")
        .unwrap();
    assert_eq!(current.body, Some(assignment("a1", "After")));
}

#[test]
fn concurrent_edits_converge_per_record_in_either_order() {
    for reverse in [false, true] {
        let mut a = db("a", true);
        let mut b = db("b", true);
        for conn in [&a, &b] {
            put_assignment(conn, "same", "Before");
            put_assignment(conn, "delete_wins", "Before");
            put_assignment(conn, "edit_wins", "Before");
            conn.execute(
                "INSERT INTO weeks(user_id,week_start,blocks) VALUES (1,'2026-10-12',?1)",
                [json!([block("Before")]).to_string()],
            )
            .unwrap();
        }
        scan(&mut a, 1, 1_000).unwrap();
        let initial = batch(&a, 0, "b");
        apply_batch(&mut b, &initial, 1_000).unwrap();

        put_assignment(&a, "same", "From A");
        put_assignment(&b, "same", "From B");
        put_assignment(&b, "delete_wins", "Old edit");
        a.execute("DELETE FROM assignments WHERE id='edit_wins'", [])
            .unwrap();
        put_assignment(&b, "edit_wins", "New edit");
        a.execute(
            "UPDATE weeks SET blocks=?1",
            [json!([block("Moved A")]).to_string()],
        )
        .unwrap();
        b.execute(
            "UPDATE weeks SET blocks=?1",
            [json!([block("Moved B")]).to_string()],
        )
        .unwrap();
        a.execute(
            "INSERT INTO standing_blocks VALUES (1,'school','2026-10-12',0,?1)",
            [json!({"id":"school","title":"School"}).to_string()],
        )
        .unwrap();
        b.execute(
            "INSERT INTO routines VALUES (1,'daily','Daily','{}',0,'1','2')",
            [],
        )
        .unwrap();
        a.execute("UPDATE preferences SET reminder_lead_min=10", [])
            .unwrap();
        b.execute("UPDATE preferences SET timer_work_min=45", [])
            .unwrap();
        scan(&mut a, 1, 2_000).unwrap();
        scan(&mut b, 1, 2_001).unwrap();
        // A's tombstone is later than B's edit; B's edit_wins stamp is later than A's tombstone.
        a.execute("DELETE FROM assignments WHERE id='delete_wins'", [])
            .unwrap();
        scan(&mut a, 1, 3_000).unwrap();
        put_assignment(&b, "edit_wins", "New edit");
        b.execute(
            "UPDATE assignments SET body=?1 WHERE id='edit_wins'",
            [assignment("edit_wins", "Newest edit").to_string()],
        )
        .unwrap();
        scan(&mut b, 1, 4_000).unwrap();
        if reverse {
            exchange(&mut b, &mut a, 5_000);
        } else {
            exchange(&mut a, &mut b, 5_000);
        }
        exchange(&mut a, &mut b, 5_001);
        assert_eq!(state(&a), state(&b));
        assert_eq!(
            get_assignment(&a, "same"),
            Some(assignment("same", "From B"))
        );
        assert_eq!(get_assignment(&a, "delete_wins"), None);
        assert_eq!(
            get_assignment(&a, "edit_wins"),
            Some(assignment("edit_wins", "Newest edit"))
        );
        let blocks_text: String = a
            .query_row("SELECT blocks FROM weeks", [], |row| row.get(0))
            .unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&blocks_text).unwrap(),
            json!([block("Moved B")])
        );
        let standing: i64 = a
            .query_row("SELECT COUNT(*) FROM standing_blocks", [], |row| row.get(0))
            .unwrap();
        let routines: i64 = a
            .query_row("SELECT COUNT(*) FROM routines", [], |row| row.get(0))
            .unwrap();
        assert_eq!((standing, routines), (1, 1));
        let prefs: (i64, i64) = a
            .query_row(
                "SELECT reminder_lead_min,timer_work_min FROM preferences",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(prefs, (10, 45));
    }
}

#[test]
fn duplicate_and_echo_are_noops_and_remote_scan_does_not_restamp() {
    let mut a = db("a", true);
    let mut b = db("b", false);
    put_assignment(&a, "x", "One");
    scan(&mut a, 1, 1_000).unwrap();
    let first = batch(&a, 0, "b");
    let report = apply_batch(&mut b, &first, 1_000).unwrap();
    assert_eq!(report.applied, 13);
    let before = state(&b);
    assert_eq!(apply_batch(&mut b, &first, 1_001).unwrap().applied, 0);
    assert_eq!(state(&b), before);
    assert_eq!(scan(&mut b, 1, 1_002).unwrap(), 0);
    // B holds 13 records, all of them stamped by A (account + 11 preferences + 1 assignment),
    // numbered 1..=13 locally; sending them back to A must skip all and still advance the cursor.
    let back = batch(&b, 0, "a");
    assert_eq!(
        (back.records.len(), back.next_since, back.more),
        (0, 13, false)
    );
    let echo = batch(&b, 0, "x");
    assert_eq!(apply_batch(&mut a, &echo, 1_003).unwrap().applied, 0);
    let forged_echo = Batch {
        account_uuid: UUID.into(),
        from_device: "b".into(),
        records: vec![Record {
            entity: "assignment".into(),
            key: "x".into(),
            body: Some(assignment("x", "Echoed back")),
            hlc: 2_000 << 16,
            device_id: "a".into(),
            seq: 100,
        }],
        next_since: 100,
        more: false,
    };
    assert_eq!(apply_batch(&mut a, &forged_echo, 2_000).unwrap().applied, 0);
    assert_eq!(get_assignment(&a, "x"), Some(assignment("x", "One")));
}

#[test]
fn device_preferences_stay_local_and_wire_values_round_trip() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    a.execute("UPDATE preferences SET theme='slate', comfort_json='local-a-size', default_spotify_url='local-a'", []).unwrap();
    b.execute("UPDATE preferences SET theme='nocturne', comfort_json='local-b-size', default_spotify_url='local-b'", []).unwrap();
    scan(&mut a, 1, 1_000).unwrap();
    let sent = batch(&a, 0, "b");
    let decoded = Batch::from_value(&sent.to_value()).unwrap();
    assert_eq!(decoded, sent);
    apply_batch(&mut b, &decoded, 1_000).unwrap();
    let local: (String, String) = b
        .query_row(
            "SELECT theme,default_spotify_url FROM preferences",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(local, ("nocturne".into(), "local-b".into()));
    assert!(sent.records.iter().all(|record| record.key != "theme"
        && record.key != "comfort_json"
        && record.key != "default_spotify_url"));
}

#[test]
fn hlc_monotonicity_and_overflow_are_defined() {
    assert_eq!(flexweek_sync::next_hlc(0, 1_000).unwrap(), 1_000 << 16);
    assert_eq!(
        flexweek_sync::next_hlc(1_000 << 16, 900).unwrap(),
        (1_000 << 16) + 1
    );
    assert_eq!(
        flexweek_sync::observe(1_000 << 16, 2_000 << 16, 900).unwrap(),
        (2_000 << 16) + 1
    );
    assert_eq!(
        flexweek_sync::next_hlc((1_000 << 16) + 65_535, 1_000).unwrap(),
        1_001 << 16
    );
    assert!(flexweek_sync::next_hlc(0, i64::MAX).is_err());
}

#[test]
fn relay_reaches_a_third_database() {
    let mut a = db("a", true);
    let mut b = db("b", false);
    let mut c = db("c", false);
    put_assignment(&a, "x", "Relayed");
    scan(&mut a, 1, 1_000).unwrap();
    let first = batch(&a, 0, "b");
    apply_batch(&mut b, &first, 1_000).unwrap();
    let second = batch(&b, 0, "c");
    let report = apply_batch(&mut c, &second, 1_000).unwrap();
    assert_eq!(report.applied, 13);
    assert_eq!(get_assignment(&c, "x"), Some(assignment("x", "Relayed")));
    assert_eq!(state(&a), state(&c));
}

#[test]
fn used_recovery_code_stays_used_against_a_newer_copy() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    a.execute("INSERT INTO recovery_codes VALUES (1,'code')", [])
        .unwrap();
    scan(&mut a, 1, 1_000).unwrap();
    apply_batch(&mut b, &batch(&a, 0, "b"), 1_000).unwrap();
    a.execute("DELETE FROM recovery_codes WHERE code_hash='code'", [])
        .unwrap();
    scan(&mut a, 1, 2_000).unwrap();
    b.execute("DELETE FROM recovery_codes WHERE code_hash='code'", [])
        .unwrap();
    scan(&mut b, 1, 3_000).unwrap();
    b.execute("INSERT INTO recovery_codes VALUES (1,'code')", [])
        .unwrap();
    scan(&mut b, 1, 4_000).unwrap();
    exchange(&mut a, &mut b, 5_000);
    let left: i64 = a
        .query_row("SELECT COUNT(*) FROM recovery_codes", [], |row| row.get(0))
        .unwrap();
    let right: i64 = b
        .query_row("SELECT COUNT(*) FROM recovery_codes", [], |row| row.get(0))
        .unwrap();
    assert_eq!((left, right), (0, 0));
    assert_eq!(state(&a), state(&b));
}

#[test]
fn future_and_malformed_records_quarantine_without_stopping_batch() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let mut batch = batch(&a, 0, "b");
    batch.records.push(Record {
        entity: "assignment".into(),
        key: "future".into(),
        body: Some(assignment("future", "Future")),
        hlc: ((86_400_001_i64 + 1_000) << 16),
        device_id: "a".into(),
        seq: 100,
    });
    batch.records.push(Record {
        entity: "assignment".into(),
        key: "wrong".into(),
        body: Some(assignment("other", "Wrong")),
        hlc: 1_001 << 16,
        device_id: "a".into(),
        seq: 101,
    });
    batch.records.push(Record {
        entity: "assignment".into(),
        key: "good".into(),
        body: Some(assignment("good", "Good")),
        hlc: 1_002 << 16,
        device_id: "a".into(),
        seq: 102,
    });
    batch.records.push(Record {
        entity: "pref".into(),
        key: "reminder_lead_min".into(),
        body: Some(json!(999)),
        hlc: 1_003 << 16,
        device_id: "a".into(),
        seq: 103,
    });
    let report = apply_batch(&mut b, &batch, 1_000).unwrap();
    assert_eq!(report.quarantined, 3);
    assert_eq!(get_assignment(&b, "good"), Some(assignment("good", "Good")));
    assert_eq!(get_assignment(&b, "future"), None);
    let count: i64 = b
        .query_row("SELECT COUNT(*) FROM sync_quarantine", [], |row| row.get(0))
        .unwrap();
    assert_eq!(count, 3);
}

#[test]
fn empty_database_receives_readable_account() {
    let mut a = db("a", true);
    let mut phone = db("phone", false);
    put_assignment(&a, "x", "First sync");
    a.execute(
        "INSERT INTO weeks(user_id,week_start,blocks) VALUES (1,'2026-10-12',?1)",
        [json!([block("First")]).to_string()],
    )
    .unwrap();
    scan(&mut a, 1, 1_000).unwrap();
    phone
        .execute(
            "INSERT INTO users(id, username, password_hash) VALUES (5, 'other', 'x')",
            [],
        )
        .unwrap();
    let result = apply_batch(&mut phone, &batch(&a, 0, "phone"), 1_000).unwrap();
    assert_eq!(result.user_id, Some(6));
    assert_eq!(
        flexweek_store::find_user(&phone, "student").unwrap(),
        Some((6, "student".into(), "hash".into()))
    );
    let body = flexweek_store::assignment_body(&phone, 6, "x")
        .unwrap()
        .unwrap();
    assert_eq!(
        serde_json::from_str::<Value>(&body).unwrap(),
        assignment("x", "First sync")
    );
    let (blocks, revision) = flexweek_store::read_week(&phone, 6, "2026-10-12")
        .unwrap()
        .unwrap();
    assert_eq!(
        serde_json::from_str::<Value>(&blocks).unwrap(),
        json!([block("First")])
    );
    assert_eq!(revision, 1);
    let prefs: Value =
        serde_json::from_str(&flexweek_store::preference_row(&phone, 6).unwrap().unwrap()).unwrap();
    assert_eq!(prefs["reminder_lead_min"], 5);
    assert_eq!(prefs["theme"], "system");
}

#[test]
fn peer_cursors_only_advance_and_revocation_persists() {
    let conn = db("a", true);
    let peer = flexweek_sync::Peer {
        device_id: "b".into(),
        endpoint_id: "endpoint".into(),
        name: "Phone".into(),
        paired_at: "2026-10-12".into(),
        last_seen: None,
        revoked: false,
        pulled_seq: 0,
        pushed_seq: 0,
    };
    upsert_peer(&conn, 1, &peer).unwrap();
    acknowledge_pull(&conn, 1, "b", 8).unwrap();
    acknowledge_pull(&conn, 1, "b", 3).unwrap();
    acknowledge_push(&conn, 1, "b", 7).unwrap();
    revoke_peer(&conn, 1, "b").unwrap();
    acknowledge_push(&conn, 1, "b", 10).unwrap();
    let peers = list_peers(&conn, 1).unwrap();
    assert_eq!(
        (peers[0].pulled_seq, peers[0].pushed_seq, peers[0].revoked),
        (8, 7, true)
    );
}

#[test]
fn seeded_three_device_edits_converge_with_duplicates_and_random_delivery() {
    let mut seed = 0x5eed_u64;
    for case in 0..20 {
        let mut devices = [db("a", true), db("b", true), db("c", true)];
        for (index, conn) in devices.iter_mut().enumerate() {
            scan(conn, 1, 1_000).unwrap();
            for step in 0..12 {
                seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
                let key = format!("item{}", (seed >> 32) % 4);
                if (seed >> 40) & 3 == 0 {
                    conn.execute("DELETE FROM assignments WHERE id=?1", [&key])
                        .unwrap();
                } else {
                    put_assignment(conn, &key, &format!("case{case}-device{index}-step{step}"));
                }
                scan(conn, 1, 2_000 + step * 10 + index as i64).unwrap();
            }
        }
        for round in 0..8 {
            seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
            let from = ((seed >> 32) % 3) as usize;
            let to = (from + 1 + round % 2) % 3;
            let batch = batch(&devices[from], 0, "none");
            apply_batch(&mut devices[to], &batch, 10_000).unwrap();
            assert_eq!(
                apply_batch(&mut devices[to], &batch, 10_000)
                    .unwrap()
                    .applied,
                0
            );
        }
        let snapshots: Vec<_> = devices.iter().map(|conn| batch(conn, 0, "none")).collect();
        for (to, device) in devices.iter_mut().enumerate() {
            for (from, snapshot) in snapshots.iter().enumerate() {
                if from != to {
                    apply_batch(device, snapshot, 10_001).unwrap();
                }
            }
        }
        for pair in [(0, 1), (1, 2)] {
            assert_eq!(state(&devices[pair.0]), state(&devices[pair.1]));
            assert_eq!(content(&devices[pair.0]), content(&devices[pair.1]));
        }
    }
}

fn put_block_record(key: &str, body: Value, seq: i64) -> Record {
    Record {
        entity: "block".into(),
        key: key.into(),
        body: Some(body),
        hlc: 1_100 << 16,
        device_id: "a".into(),
        seq,
    }
}

#[test]
fn lengths_count_characters_not_bytes() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let mut sent = batch(&a, 0, "b");
    // 80 characters, 240 bytes: legal on the desktop. 81 characters: not.
    let ok = "字".repeat(80);
    let too_long = "字".repeat(81);
    for (key, title, seq) in [("ok", &ok, 100), ("long", &too_long, 101)] {
        sent.records.push(Record {
            entity: "assignment".into(),
            key: key.into(),
            body: Some(assignment(key, title)),
            hlc: 1_001 << 16,
            device_id: "a".into(),
            seq,
        });
    }
    let report = apply_batch(&mut b, &sent, 1_000).unwrap();
    assert_eq!(report.quarantined, 1);
    assert_eq!(get_assignment(&b, "ok"), Some(assignment("ok", &ok)));
    assert_eq!(get_assignment(&b, "long"), None);
}

#[test]
fn first_batch_leads_with_the_account_even_when_its_seq_is_late() {
    let mut a = db("a", true);
    let mut phone = db("phone", false);
    for index in 0..5 {
        put_assignment(&a, &format!("a{index}"), "Work");
    }
    // Scan order is by key: account 1, a0..a4 2..6, the 11 preferences 7..17.
    scan(&mut a, 1, 1_000).unwrap();
    a.execute("UPDATE users SET password_hash='changed'", [])
        .unwrap();
    scan(&mut a, 1, 2_000).unwrap(); // the account record is now seq 18
    let first = export_since(&a, 1, 0, "phone", 3).unwrap();
    let names: Vec<_> = first
        .records
        .iter()
        .map(|record| (record.entity.as_str(), record.key.as_str(), record.seq))
        .collect();
    assert_eq!(
        names,
        [
            ("account", "-", 18),
            ("assignment", "a0", 2),
            ("assignment", "a1", 3)
        ]
    );
    assert_eq!((first.next_since, first.more), (3, true));
    apply_batch(&mut phone, &first, 3_000).unwrap();
    let mut since = first.next_since;
    loop {
        let next = export_since(&a, 1, since, "phone", 500).unwrap();
        apply_batch(&mut phone, &next, 3_000).unwrap();
        since = next.next_since;
        if !next.more {
            break;
        }
    }
    assert_eq!(since, 18);
    assert_eq!(
        flexweek_store::find_user(&phone, "student")
            .unwrap()
            .unwrap()
            .2,
        "changed"
    );
    assert_eq!(state(&a), state(&phone));
}

#[test]
fn an_unscanned_local_edit_is_not_overwritten_by_an_older_remote_edit() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    put_assignment(&a, "x", "Shared");
    scan(&mut a, 1, 1_000).unwrap();
    apply_batch(&mut b, &batch(&a, 0, "b"), 1_000).unwrap();
    put_assignment(&a, "x", "From A");
    scan(&mut a, 1, 2_000).unwrap();
    // B edits at about 3 000 ms and has not scanned yet when A's older edit arrives.
    put_assignment(&b, "x", "From B");
    apply_batch(&mut b, &batch(&a, 0, "b"), 3_000).unwrap();
    assert_eq!(get_assignment(&b, "x"), Some(assignment("x", "From B")));
    let origin: (String, i64) = b
        .query_row(
            "SELECT device_id, hlc FROM sync_record WHERE entity='assignment' AND key='x'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(origin, ("b".into(), 3_000 << 16));
}

#[test]
fn bad_block_and_standing_keys_are_quarantined() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let mut sent = batch(&a, 0, "b");
    let id =
        json!({"id": "blk", "title": "T", "kind": "flexible", "duration_min": 30, "days": [0]});
    sent.records
        .push(put_block_record("garbage/blk", id.clone(), 100));
    // 2026-10-13 is a Tuesday.
    sent.records
        .push(put_block_record("2026-10-13/blk", id.clone(), 101));
    sent.records.push(Record {
        entity: "standing".into(),
        key: "school/2026-10-13".into(),
        body: Some(json!({"position": 0, "body": null})),
        hlc: 1_100 << 16,
        device_id: "a".into(),
        seq: 102,
    });
    let report = apply_batch(&mut b, &sent, 1_000).unwrap();
    assert_eq!(report.quarantined, 3);
    let rows: i64 = b
        .query_row(
            "SELECT (SELECT COUNT(*) FROM weeks) + (SELECT COUNT(*) FROM standing_blocks)",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(rows, 0);
}

#[test]
fn bodies_with_extra_keys_are_quarantined_so_they_cannot_restamp() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let mut sent = batch(&a, 0, "b");
    sent.records.push(Record {
        entity: "routine".into(),
        key: "r".into(),
        body: Some(
            json!({"name": "R", "body": {}, "created_at": "1", "updated_at": "2", "extra": 1}),
        ),
        hlc: 1_100 << 16,
        device_id: "a".into(),
        seq: 100,
    });
    assert_eq!(apply_batch(&mut b, &sent, 1_000).unwrap().quarantined, 1);
    assert_eq!(scan(&mut b, 1, 1_001).unwrap(), 0);
}

#[test]
fn a_block_delete_for_a_week_never_saved_creates_no_week() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let mut sent = batch(&a, 0, "b");
    sent.records.push(Record {
        entity: "block".into(),
        key: "2026-10-12/blk".into(),
        body: None,
        hlc: 1_100 << 16,
        device_id: "a".into(),
        seq: 100,
    });
    apply_batch(&mut b, &sent, 1_000).unwrap();
    let weeks: i64 = b
        .query_row("SELECT COUNT(*) FROM weeks", [], |row| row.get(0))
        .unwrap();
    assert_eq!(weeks, 0);
}

#[test]
fn the_clock_guard_is_exactly_24_hours() {
    let mut a = db("a", true);
    let mut b = db("b", true);
    scan(&mut a, 1, 1_000).unwrap();
    let now = 1_000_i64;
    let mut sent = batch(&a, 0, "b");
    for (key, ms, seq) in [
        ("edge", now + 86_400_000, 100),
        ("past", now + 86_400_001, 101),
    ] {
        sent.records.push(Record {
            entity: "assignment".into(),
            key: key.into(),
            body: Some(assignment(key, "T")),
            hlc: ms << 16,
            device_id: "a".into(),
            seq,
        });
    }
    let report = apply_batch(&mut b, &sent, now).unwrap();
    assert_eq!(report.quarantined, 1);
    assert_eq!(get_assignment(&b, "edge"), Some(assignment("edge", "T")));
    assert_eq!(get_assignment(&b, "past"), None);
}
