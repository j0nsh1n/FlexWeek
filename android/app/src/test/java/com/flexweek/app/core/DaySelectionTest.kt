package com.flexweek.app.core

import com.flexweek.app.model.TodayJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class DaySelectionTest {
    private var today = LocalDate.parse("2026-11-17")
    private val selection = DaySelection { today }

    @Test fun aTappedDayHoldsForTheRestOfTheRealDay() {
        selection.select(LocalDate.parse("2026-11-19"))
        assertEquals(LocalDate.parse("2026-11-19"), selection.date())
    }

    @Test fun whenANewDayStartsTodayFollowsTheRealDate() {
        selection.select(LocalDate.parse("2026-11-16"))
        today = LocalDate.parse("2026-11-18")
        assertEquals(LocalDate.parse("2026-11-18"), selection.date())
    }

    @Test fun lastWeeksSameWeekdayIsNotToday() {
        val agenda = """{"date":"2026-11-11","week_start":"2026-11-09","day":2,"days":[],"nothing_left":false,"rows":[],"no_time_yet":[]}"""
        val shown = RustPhoneJson.today(agenda, "2026-11-18", """{"state":"synced","line":"Synced just now","paired":true}""")
        assertTrue(JSONObject(shown).has("selected_is_today"))
        val state = TodayJson.parse(shown)
        assertTrue("the jump back to today shows", state.showTodayJump)
        assertFalse(JSONObject(shown).getBoolean("selected_is_today"))
    }
}
