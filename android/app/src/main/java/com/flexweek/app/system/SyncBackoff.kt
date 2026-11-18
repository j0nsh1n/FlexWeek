package com.flexweek.app.system

/** The pause between foreground syncs: short while the computer answers, longer each time it does not. */
object SyncBackoff {
    const val BASE_MS = 5_000L
    const val MAX_MS = 60_000L

    fun next(currentMs: Long, ok: Boolean): Long = if (ok) BASE_MS else (currentMs * 2).coerceAtMost(MAX_MS)
}
