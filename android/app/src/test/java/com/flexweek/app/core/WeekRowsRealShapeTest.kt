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

class WeekRowsHeavyTest {
    @Test
    fun theHeavyTagIsTheEnginesAnswerNotARecount() {
        // Only 3 h 15 min is still planned here, which the engine calls heavy; 90 min is not, whatever the Kotlin rule says.
        val raw = """{"week_start":"2026-10-19","days":[
            {"day":0,"date":"2026-10-19","names":[],"minutes":195,"heavy":true,"unplaced":[],"last_class_end":null},
            {"day":1,"date":"2026-10-20","names":[],"minutes":200,"heavy":false,"unplaced":[],"last_class_end":null}]}"""
        val days = V2Json.parseWeekRows(raw).days
        assertEquals(true, days[0].heavy)
        assertEquals("the engine did not call this day heavy", false, days[1].heavy)
    }
}
