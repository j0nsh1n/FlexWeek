package com.flexweek.app.core

import org.junit.Assert.assertEquals
import org.junit.Test

class TimeLabelTest {
    @Test fun onTheHourHasNoMinutes() = assertEquals("7 PM", TimeLabel.short("19:00"))

    @Test fun halfHourKeepsMinutes() = assertEquals("3:30 PM", TimeLabel.short("15:30"))

    @Test fun midnightAndNoonAreTwelve() {
        assertEquals("12 AM", TimeLabel.short("00:00"))
        assertEquals("12 PM", TimeLabel.short("12:00"))
    }

    @Test fun aMoveOnTheSameDaySaysOnlyTheTimes() =
        assertEquals("4 PM → 4:30 PM", TimeLabel.lateDetail(0, "16:00", 0, "16:30"))

    @Test fun aMoveToAnotherDayNamesBothDays() =
        assertEquals("Thu 7 PM → Fri 3:30 PM", TimeLabel.lateDetail(3, "19:00", 4, "15:30"))
}
