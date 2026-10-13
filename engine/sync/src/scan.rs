use std::collections::HashMap;

use rusqlite::{Connection, params};

use crate::{SyncResult, clock::next_hlc, digest, records::live};

pub fn scan(conn: &mut Connection, user_id: i64, now_ms: i64) -> SyncResult<usize> {
    let tx = conn.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let count = scan_in(&tx, user_id, now_ms)?;
    tx.commit()?;
    Ok(count)
}

/// Runs inside the caller's write transaction, so a remote record can never overwrite a local
/// edit that has not been stamped yet.
pub(crate) fn scan_in(tx: &Connection, user_id: i64, now_ms: i64) -> SyncResult<usize> {
    let current = live(tx, user_id)?;
    let mut stmt =
        tx.prepare("SELECT entity, key, deleted, hash FROM sync_record WHERE user_id = ?1")?;
    let old = stmt
        .query_map([user_id], |row| {
            Ok((
                (row.get::<_, String>(0)?, row.get::<_, String>(1)?),
                row.get::<_, i64>(2)? != 0,
                row.get::<_, String>(3)?,
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;
    drop(stmt);
    let known: HashMap<&(String, String), (bool, &str)> = old
        .iter()
        .map(|(name, deleted, hash)| (name, (*deleted, hash.as_str())))
        .collect();
    let device: (String, i64, i64) = tx.query_row(
        "SELECT device_id, hlc_last, seq_last FROM sync_device WHERE singleton = 1",
        [],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    )?;
    let (device_id, mut hlc, mut seq) = device;
    let mut count = 0;
    for ((entity, key), body) in &current {
        let hash = digest(body);
        if known
            .get(&(entity.clone(), key.clone()))
            .is_some_and(|(deleted, prior)| !deleted && *prior == hash)
        {
            continue;
        }
        hlc = next_hlc(hlc, now_ms)?;
        seq += 1;
        tx.execute("INSERT INTO sync_record(user_id, entity, key, hlc, device_id, deleted, hash, seq) VALUES (?1, ?2, ?3, ?4, ?5, 0, ?6, ?7) ON CONFLICT(user_id, entity, key) DO UPDATE SET hlc=excluded.hlc, device_id=excluded.device_id, deleted=0, hash=excluded.hash, seq=excluded.seq", params![user_id, entity, key, hlc, device_id, hash, seq])?;
        count += 1;
    }
    for ((entity, key), deleted, _) in &old {
        if *deleted || current.contains_key(&(entity.clone(), key.clone())) {
            continue;
        }
        hlc = next_hlc(hlc, now_ms)?;
        seq += 1;
        tx.execute("UPDATE sync_record SET hlc=?4, device_id=?5, deleted=1, hash='', seq=?6 WHERE user_id=?1 AND entity=?2 AND key=?3", params![user_id, entity, key, hlc, device_id, seq])?;
        count += 1;
    }
    tx.execute(
        "UPDATE sync_device SET hlc_last=?1, seq_last=?2 WHERE singleton=1",
        params![hlc, seq],
    )?;
    Ok(count)
}
