package com.flexweek.app.core

/**
 * Kotlin-facing API matching the planned UniFFI surface (S3). JSON payloads use org.json on callers.
 */
interface FlexWeekCore {
    fun engineVersion(): String

    fun open(dbPath: String, deviceName: String)

    /** ISO date yyyy-MM-dd; [nowMinute] is minutes from midnight in local time. */
    fun today(date: String, nowMinute: Int): String

    fun setBlockDone(
        weekStart: String,
        blockId: String,
        dayIndex: Int,
        done: Boolean,
        opId: String,
    )

    fun setHomeworkDone(id: String, done: Boolean, opId: String)

    fun upcomingReminders(fromLocal: String, hours: Int): String

    fun settingsForPhone(): String

    fun syncStatus(): String

    fun syncOnce(deadlineMs: Long): String

    fun pairWithCode(code: String): String

    fun pairFromQr(text: String): String

    fun cancelSync()

    fun unlink()

    fun isPaired(): Boolean
}
