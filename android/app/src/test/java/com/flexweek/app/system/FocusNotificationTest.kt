package com.flexweek.app.system

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusNotificationTest {
    private fun plan(saved: String) = requireNotNull(FocusNotificationPlan.from(saved))

    @Test fun runningNotificationCountsToTheEnd() {
        val plan = plan("""{"title":"History essay","running":true,"endsAt":1800000,"remainingMs":900000}""")
        assertEquals("running notification uses endsAt", 1_800_000L, plan.whenMs)
        assertTrue("running notification shows system countdown", plan.countdown)
    }

    @Test fun pausedNotificationSaysPausedAndHasNoCountdown() {
        val plan = plan("""{"title":"History essay","running":false,"endsAt":null,"remainingMs":600000}""")
        assertEquals("paused notification says Paused", "Paused", plan.status)
        assertFalse("paused notification has no countdown", plan.countdown)
    }

    @Test fun notificationKeepsTheHomeworkTitle() {
        val plan = plan("""{"title":"History essay","running":true,"endsAt":1800000}""")
        assertEquals("lock-screen header matches picture 8 C", "FlexWeek · focus", plan.header)
        assertEquals("notification body is the homework title", "History essay", plan.title)
    }

    @Test fun notificationIsPublicOnTheLockScreen() {
        assertEquals("notification is visible on the lock screen", androidx.core.app.NotificationCompat.VISIBILITY_PUBLIC, FocusNotificationPlan.visibility)
    }

    @Test fun focusActionFromIntent() {
        assertEquals("pause action toggles the timer", FocusAction.PAUSE, FocusNotificationPlan.action("pause"))
        assertEquals("resume action toggles the timer", FocusAction.PAUSE, FocusNotificationPlan.action("resume"))
        assertEquals("finish action ends the timer", FocusAction.FINISH, FocusNotificationPlan.action("finish"))
        assertEquals("unknown actions are ignored", null, FocusNotificationPlan.action("other"))
    }
}
