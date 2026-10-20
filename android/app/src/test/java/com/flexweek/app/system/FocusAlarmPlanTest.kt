package com.flexweek.app.system

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FocusAlarmPlanTest {
    @Test fun runningTimerArmsAnAlarmAtTheEnd() {
        assertEquals(1_800_000L, FocusAlarmPlan.endAt("""{"running":true,"endsAt":1800000}"""))
    }

    @Test fun pausedOrNoTimerArmsNothing() {
        assertNull(FocusAlarmPlan.endAt("""{"running":false,"endsAt":null,"remainingMs":600000}"""))
        assertNull(FocusAlarmPlan.endAt("null"))
    }

    @Test fun bootReArmsARunningTimer() {
        val scheduled = mutableListOf<Long>()
        assertEquals(true, FocusAlarmPlan.rearmOnBoot("""{"running":true,"endsAt":1800000}""", scheduled::add))
        assertEquals(listOf(1_800_000L), scheduled)
    }
}
