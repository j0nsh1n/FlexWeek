package com.flexweek.app.system

interface AlarmScheduler {
    fun scheduledKeys(): Set<String>

    fun cancel(key: String)

    fun schedule(request: ReminderRescheduler.ScheduleRequest)

    fun cancelAllNotIn(keepKeys: Set<String>) {
        val drop = scheduledKeys() - keepKeys
        drop.forEach { cancel(it) }
    }
}
