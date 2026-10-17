package com.flexweek.app.system.widget

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.system.AlarmScheduler
import com.flexweek.app.system.ReminderRescheduler
import com.flexweek.app.system.rescheduleRemindersNow
import org.junit.Assert.assertFalse
import org.junit.Test

// The reminder reschedule cancels every booked key it does not plan. The widget's refresh alarm must survive it,
// as the focus end alarm does.
class WidgetAlarmKeyTest {
    private class BookedScheduler(keys: Set<String>) : AlarmScheduler {
        private val booked = keys.toMutableSet()
        val cancelled = mutableListOf<String>()

        override fun scheduledKeys(): Set<String> = booked.toSet()

        override fun cancel(key: String) {
            cancelled += key
            booked -= key
        }

        override fun schedule(request: ReminderRescheduler.ScheduleRequest) {
            booked += request.key
        }
    }

    @Test fun theWidgetsAlarmKeySurvivesTheReminderReschedule() {
        val core = FakeFlexWeekCore()
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val scheduler = BookedScheduler(setOf(WidgetRefresh.ALARM_KEY))
        rescheduleRemindersNow(core, scheduler, "2025-10-08T15:00:00", 1_759_935_600_000L, true, 34)
        assertFalse(
            "the reminder reschedule cancelled the widget's alarm: ${scheduler.cancelled}",
            WidgetRefresh.ALARM_KEY in scheduler.cancelled,
        )
    }
}
