package com.flexweek.app.system

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ReminderNotificationIdTest {
    @Test fun sameTitleDifferentReminderGetsDifferentId() {
        assertNotEquals(
            ReminderReceiver.reminderNotificationId("2026-10-05|essay-a|0|19:00"),
            ReminderReceiver.reminderNotificationId("2026-10-05|essay-b|1|19:00"),
        )
    }

    @Test fun samePostedAgainKeepsItsId() {
        assertEquals(ReminderReceiver.reminderNotificationId("week|essay|0|19:00"), ReminderReceiver.reminderNotificationId("week|essay|0|19:00"))
    }

    @Test fun renamedReminderWithSameKeyKeepsItsId() {
        assertEquals(
            ReminderReceiver.reminderNotificationId("week|essay|0|19:00"),
            ReminderReceiver.reminderNotificationId("week|essay|0|19:00"),
        )
    }

    @Test fun keysWithEqualStringHashCodeDoNotCollide() {
        assertNotEquals(ReminderReceiver.reminderNotificationId("Aa"), ReminderReceiver.reminderNotificationId("BB"))
    }
}
