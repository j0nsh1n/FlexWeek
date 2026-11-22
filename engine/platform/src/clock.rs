//! The real clock. Every other desktop crate takes the time as an argument (the clock rule), so this is
//! where a program reads it.

use std::time::{SystemTime, UNIX_EPOCH};

/// Seconds since 1970 now; 0 if the system clock is set before then.
pub fn unix_seconds() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |since| {
            i64::try_from(since.as_secs()).unwrap_or(i64::MAX)
        })
}
