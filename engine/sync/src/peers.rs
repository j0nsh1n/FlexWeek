use crate::SyncResult;
use rusqlite::{Connection, params};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Peer {
    pub device_id: String,
    pub endpoint_id: String,
    pub name: String,
    pub paired_at: String,
    pub last_seen: Option<String>,
    pub revoked: bool,
    pub pulled_seq: i64,
    pub pushed_seq: i64,
}

pub fn upsert_peer(conn: &Connection, user_id: i64, peer: &Peer) -> SyncResult<()> {
    conn.execute("INSERT INTO sync_peer(user_id, peer_device_id, endpoint_id, name, paired_at, last_seen, revoked, pulled_seq, pushed_seq) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9) ON CONFLICT(user_id, peer_device_id) DO UPDATE SET endpoint_id=excluded.endpoint_id, name=excluded.name, last_seen=excluded.last_seen, revoked=excluded.revoked", params![user_id, peer.device_id, peer.endpoint_id, peer.name, peer.paired_at, peer.last_seen, i64::from(peer.revoked), peer.pulled_seq, peer.pushed_seq])?;
    Ok(())
}

pub fn list_peers(conn: &Connection, user_id: i64) -> SyncResult<Vec<Peer>> {
    let mut stmt = conn.prepare("SELECT peer_device_id, endpoint_id, name, paired_at, last_seen, revoked, pulled_seq, pushed_seq FROM sync_peer WHERE user_id = ?1 ORDER BY peer_device_id")?;
    Ok(stmt
        .query_map([user_id], |row| {
            Ok(Peer {
                device_id: row.get(0)?,
                endpoint_id: row.get(1)?,
                name: row.get(2)?,
                paired_at: row.get(3)?,
                last_seen: row.get(4)?,
                revoked: row.get::<_, i64>(5)? != 0,
                pulled_seq: row.get(6)?,
                pushed_seq: row.get(7)?,
            })
        })?
        .collect::<Result<_, _>>()?)
}

pub fn revoke_peer(conn: &Connection, user_id: i64, device_id: &str) -> SyncResult<()> {
    conn.execute(
        "UPDATE sync_peer SET revoked = 1 WHERE user_id = ?1 AND peer_device_id = ?2",
        params![user_id, device_id],
    )?;
    Ok(())
}

pub fn acknowledge_pull(
    conn: &Connection,
    user_id: i64,
    device_id: &str,
    seq: i64,
) -> SyncResult<()> {
    conn.execute("UPDATE sync_peer SET pulled_seq = max(pulled_seq, ?3) WHERE user_id = ?1 AND peer_device_id = ?2 AND revoked = 0", params![user_id, device_id, seq])?;
    Ok(())
}

pub fn acknowledge_push(
    conn: &Connection,
    user_id: i64,
    device_id: &str,
    seq: i64,
) -> SyncResult<()> {
    conn.execute("UPDATE sync_peer SET pushed_seq = max(pushed_seq, ?3) WHERE user_id = ?1 AND peer_device_id = ?2 AND revoked = 0", params![user_id, device_id, seq])?;
    Ok(())
}
