use crate::{SyncError, SyncResult};

pub const MAX_FUTURE_MS: i64 = 24 * 60 * 60 * 1000;

pub fn next_hlc(last: i64, now_ms: i64) -> SyncResult<i64> {
    let wall = now_ms
        .checked_mul(1 << 16)
        .ok_or_else(|| SyncError::Invalid("clock overflow".into()))?;
    if wall > last {
        Ok(wall)
    } else {
        last.checked_add(1)
            .ok_or_else(|| SyncError::Invalid("clock overflow".into()))
    }
}

pub fn observe(last: i64, remote: i64, now_ms: i64) -> SyncResult<i64> {
    Ok(next_hlc(last, now_ms)?.max(
        remote
            .checked_add(1)
            .ok_or_else(|| SyncError::Invalid("clock overflow".into()))?,
    ))
}
