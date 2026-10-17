package com.flexweek.app.system.widget

import java.time.ZoneId
import java.time.temporal.ChronoUnit

object WidgetRefresh {
    // Not an AlarmBook key: the reminder reschedule cancels any booked key it does not plan.
    const val ALARM_KEY = "widget-refresh"

    // A read that failed is tried again after this long.
    const val RETRY_AFTER_MS = 60_000L

    private const val MINUTES_PER_DAY = 24 * 60

    /** A boundary or midnight can use an exact alarm; a countdown tick never does. */
    enum class Kind { MINUTE, BOUNDARY, MIDNIGHT }

    data class Wake(val atMs: Long, val kind: Kind)

    /** The earliest moment the text can change: a start or end minute, the next countdown minute, or local midnight. */
    fun nextWake(nowMs: Long, zone: ZoneId, boundaryMinutes: List<Int>, countdownShowing: Boolean): Wake {
        val now = java.time.Instant.ofEpochMilli(nowMs).atZone(zone)
        val today = now.toLocalDate()
        val candidates = mutableListOf(Wake(today.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli(), Kind.MIDNIGHT))
        for (minute in boundaryMinutes.filter { it in 0 until MINUTES_PER_DAY }) {
            val at = today.atTime(minute / 60, minute % 60).atZone(zone).toInstant().toEpochMilli()
            if (at > nowMs) candidates += Wake(at, Kind.BOUNDARY)
        }
        if (countdownShowing) {
            candidates += Wake(now.truncatedTo(ChronoUnit.MINUTES).plusMinutes(1).toInstant().toEpochMilli(), Kind.MINUTE)
        }
        // A boundary and a countdown tick on the same minute are one wake, and the exact kind wins.
        return candidates.minWith(compareBy<Wake>({ it.atMs }, { if (it.kind == Kind.MINUTE) 1 else 0 }))
    }
}
