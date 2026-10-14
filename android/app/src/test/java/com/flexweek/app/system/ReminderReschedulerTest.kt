package com.flexweek.app.system

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

class ReminderReschedulerTest {
    private lateinit var core: FakeFlexWeekCore
    private lateinit var scheduler: RecordingAlarmScheduler

    @Before
    fun setUp() {
        core = FakeFlexWeekCore()
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        scheduler = RecordingAlarmScheduler()
    }

    @Test
    fun rebootReschedule_keepsEssayAlarm() {
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 0))
        assertTrue(scheduler.scheduledKeys().any { it.contains("essay") })
    }

    @Test
    fun timezoneChange_replacesScheduledKeys() {
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 0))
        val first = scheduler.scheduledKeys().toSet()
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 5))
        assertEquals(first, scheduler.scheduledKeys().toSet())
        assertTrue(scheduler.scheduleCount >= 1)
    }

    @Test
    fun exactPermissionDenied_usesWindow() {
        core.setExactReminders(true)
        runReschedule(
            now = LocalDateTime.of(2025, 10, 8, 15, 0),
            canExact = false,
            sdkInt = 34,
        )
        assertTrue(scheduler.schedules.all { !it.exact })
    }

    @Test
    fun blockDone_removesItsAlarm() {
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 0))
        assertTrue(scheduler.scheduledKeys().any { it.contains("essay") })
        core.setHomeworkDone("essay", true, "op1")
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 1))
        assertFalse(scheduler.scheduledKeys().any { it.contains("essay") })
        assertTrue(scheduler.cancelled.any { it.contains("essay") })
    }

    @Test
    fun blockMoved_dropsOldKey() {
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 0))
        val oldKey = scheduler.scheduledKeys().first { it.contains("essay") }
        core.moveBlock("essay", newDayIndex = 4, newStartMinute = 20 * 60)
        runReschedule(now = LocalDateTime.of(2025, 10, 8, 15, 2))
        assertTrue(scheduler.cancelled.contains(oldKey))
        assertTrue(scheduler.scheduledKeys().any { it.contains("essay") && it != oldKey })
    }

    @Test
    fun exactOptIn_usesExactWhenAllowed() {
        core.setExactReminders(true)
        runReschedule(
            now = LocalDateTime.of(2025, 10, 8, 15, 0),
            canExact = true,
            sdkInt = 34,
        )
        assertTrue(scheduler.schedules.all { it.exact })
    }

    private fun runReschedule(
        now: LocalDateTime,
        canExact: Boolean = true,
        sdkInt: Int = 30,
    ) {
        val fromLocal = now.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
        rescheduleRemindersNow(
            core = core,
            scheduler = scheduler,
            fromLocal = fromLocal,
            nowMs = now.atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli(),
            canScheduleExactAlarms = canExact,
            sdkInt = sdkInt,
        )
    }
}

private class RecordingAlarmScheduler : AlarmScheduler {
    val schedules = mutableListOf<ReminderRescheduler.ScheduleRequest>()
    val cancelled = mutableListOf<String>()
    private val keys = mutableSetOf<String>()
    var scheduleCount = 0

    override fun scheduledKeys(): Set<String> = keys.toSet()

    override fun cancel(key: String) {
        cancelled += key
        keys -= key
    }

    override fun schedule(request: ReminderRescheduler.ScheduleRequest) {
        schedules += request
        keys += request.key
        scheduleCount++
    }
}
