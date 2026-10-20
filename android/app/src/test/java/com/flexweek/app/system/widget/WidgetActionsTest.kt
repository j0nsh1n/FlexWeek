package com.flexweek.app.system.widget

import android.content.Intent
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WidgetActionsTest {
    private class RecordingCore(val calls: MutableList<String> = mutableListOf()) : FlexWeekCore by FakeFlexWeekCore() {
        override fun currentDate() = "2026-10-12"
        override fun selectedDate() = "2026-10-15"
        override fun today(date: String, nowMinute: Int): String {
            calls += "today:$date:$nowMinute"
            return "{}"
        }
        override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
            calls += "done:$id:$done:$opId"
        }
    }

    @Test fun theWidgetReadsThePhonesTodayNotTheSelectedDay() {
        val core = RecordingCore()
        WidgetRead.today(core, 14 * 60 + 10)
        assertEquals(listOf("today:2026-10-12:850"), core.calls)
    }

    @Test fun theTickReadsTodayFirstSoTheRowIsKnownThenMarksItFinished() {
        val core = RecordingCore()
        WidgetTick.markFinished(core, "spanish-session", 14 * 60 + 10, "op-1")
        assertEquals(listOf("today:2026-10-12:850", "done:spanish-session:true:op-1"), core.calls)
    }

    @Test fun aTapOpensTodayInAFreshActivityWithNoScreenshotExtras() {
        val open = WidgetTap.openToday()
        val flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        assertEquals("a tap must start a fresh Today", flags, open.flags)
        assertTrue("extras would steer the app to another screen: ${open.extras}", open.extras.isEmpty())
    }
}
