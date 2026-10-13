package com.flexweek.app.system

/**
 * Pure scheduling plan: which alarm keys to drop and how to schedule the rest.
 */
object ReminderRescheduler {
    const val WINDOW_LENGTH_MS = 5 * 60_000L
    const val WINDOW_EARLY_MS = 60_000L

    data class ScheduleRequest(
        val key: String,
        val triggerAtMs: Long,
        val exact: Boolean,
        val title: String,
        val body: String,
    )

    data class Plan(
        val cancelKeys: Set<String>,
        val schedule: List<ScheduleRequest>,
    )

    fun plan(
        upcoming: List<ReminderItem>,
        currentlyScheduled: Set<String>,
        nowMs: Long,
        exactOptIn: Boolean,
        canScheduleExactAlarms: Boolean,
        sdkInt: Int,
    ): Plan {
        val upcomingKeys = upcoming.map { it.key }.toSet()
        val cancelKeys = currentlyScheduled - upcomingKeys
        val useExact = exactOptIn && (sdkInt < 31 || canScheduleExactAlarms)
        val schedule =
            upcoming.mapNotNull { item ->
                val at = item.fireAtEpochMs()
                if (at <= nowMs) {
                    null
                } else {
                    ScheduleRequest(
                        key = item.key,
                        triggerAtMs = at,
                        exact = useExact,
                        title = item.title,
                        body = item.body,
                    )
                }
            }
        return Plan(cancelKeys, schedule)
    }
}
