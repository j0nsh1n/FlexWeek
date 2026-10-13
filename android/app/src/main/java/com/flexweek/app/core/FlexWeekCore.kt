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

    /** v2 (S8): draft JSON with title, due, when, estimate_min, sessions. Returns ok or error text. */
    fun saveHomework(draftJson: String, opId: String): String

    /** v2: returns preview JSON (preview_id, placed, not_placed, …). */
    fun planWeek(weekStart: String): String

    fun acceptPlan(previewId: String, opId: String): String

    /** v2: preview moves for Running late on [dayIndex] by [minutes]. */
    fun runningLate(dayIndex: Int, minutes: Int, opId: String): String

    fun acceptRunningLate(previewId: String, opId: String): String

    /** v2: colour bars per day, no words. */
    fun weekShape(weekStart: String): String
}
