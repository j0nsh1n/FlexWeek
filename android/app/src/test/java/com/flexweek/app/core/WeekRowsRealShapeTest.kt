package com.flexweek.app.core

import com.flexweek.app.model.V2Json
import org.junit.Assert.assertEquals
import org.junit.Test

class WeekRowsRealShapeTest {
    @Test
    fun mondayNamesAndMinutesMatchTheRealCoreFixture() {
        val raw = javaClass.getResourceAsStream("/phone/week-rows.json")!!.bufferedReader().use { it.readText() }
        val monday = V2Json.parseWeekRows(raw).days.first { it.dayIndex == 0 }

        assertEquals(listOf("History essay", "Bio reading"), monday.names)
        assertEquals(90, monday.minutes)
    }
}
