use crate::SyncResult;
use rusqlite::{Connection, params};

pub fn migrate(conn: &Connection) -> SyncResult<()> {
    for sql in [
        "CREATE TABLE IF NOT EXISTS sync_device (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), device_id TEXT NOT NULL, device_name TEXT NOT NULL, hlc_last INTEGER NOT NULL, seq_last INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS sync_account (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, account_uuid TEXT NOT NULL UNIQUE)",
        "CREATE TABLE IF NOT EXISTS sync_record (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, entity TEXT NOT NULL, key TEXT NOT NULL, hlc INTEGER NOT NULL, device_id TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, hash TEXT NOT NULL, seq INTEGER NOT NULL, PRIMARY KEY (user_id, entity, key))",
        "CREATE INDEX IF NOT EXISTS sync_record_seq ON sync_record(user_id, seq)",
        "CREATE TABLE IF NOT EXISTS sync_peer (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, peer_device_id TEXT NOT NULL, endpoint_id TEXT NOT NULL, name TEXT NOT NULL, paired_at TEXT NOT NULL, last_seen TEXT, revoked INTEGER NOT NULL DEFAULT 0, pulled_seq INTEGER NOT NULL DEFAULT 0, pushed_seq INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, peer_device_id))",
        "CREATE TABLE IF NOT EXISTS sync_quarantine (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, entity TEXT, key TEXT, reason TEXT, body TEXT, at TEXT)",
    ] {
        conn.execute(sql, [])?;
    }
    Ok(())
}

pub fn set_device(conn: &Connection, device_id: &str, device_name: &str) -> SyncResult<()> {
    conn.execute("INSERT INTO sync_device(singleton, device_id, device_name, hlc_last, seq_last) VALUES (1, ?1, ?2, 0, 0) ON CONFLICT(singleton) DO UPDATE SET device_name = excluded.device_name WHERE device_id = excluded.device_id", params![device_id, device_name])?;
    let current: String = conn.query_row(
        "SELECT device_id FROM sync_device WHERE singleton = 1",
        [],
        |row| row.get(0),
    )?;
    if current != device_id {
        return Err(crate::SyncError::Invalid(
            "database belongs to another device".into(),
        ));
    }
    Ok(())
}

pub fn set_account(conn: &Connection, user_id: i64, account_uuid: &str) -> SyncResult<()> {
    conn.execute("INSERT INTO sync_account(user_id, account_uuid) VALUES (?1, ?2) ON CONFLICT(user_id) DO NOTHING", params![user_id, account_uuid])?;
    let current: String = conn.query_row(
        "SELECT account_uuid FROM sync_account WHERE user_id = ?1",
        [user_id],
        |row| row.get(0),
    )?;
    if current != account_uuid {
        return Err(crate::SyncError::Invalid("account identity differs".into()));
    }
    Ok(())
}
