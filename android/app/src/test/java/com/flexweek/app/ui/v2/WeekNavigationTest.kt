package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.model.V2Json
import com.flexweek.app.model.WeekEntry
import com.flexweek.app.model.WeekList
import com.flexweek.app.model.WeekRowWords
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class WeekNavigationTest {
    @get:Rule val main = com.flexweek.app.testing.MainThreadRule()

    private val asked = mutableListOf<String>()
    private val core: FlexWeekCore = object : FlexWeekCore by FakeFlexWeekCore() {
        override fun currentWeekStart() = "2026-11-16"
        override fun currentDate() = "2026-11-17"
        override fun weekRows(weekStart: String): String {
            asked += weekStart
            return """{"week_start":"$weekStart","days":[]}"""
        }
    }

    @Test fun theArrowsLoadTheWeekBeforeAndAfterTheCurrentOne() {
        val vm = WeekViewModel(core, main.dispatcher)
        assertEquals("2026-11-16", asked.last())
        vm.nextWeek()
        assertEquals("2026-11-23", asked.last())
        assertEquals("23 – 29 Nov", vm.state.title)
        vm.previousWeek()
        vm.previousWeek()
        assertEquals("2026-11-09", asked.last())
        assertEquals("9 – 15 Nov", vm.state.title)
        assertEquals(-1, vm.weekOffset)
        vm.thisWeek()
        assertEquals("2026-11-16", asked.last())
        assertEquals(0, vm.weekOffset)
    }

    @Test fun aRefreshAfterASyncStaysOnTheWeekBeingLooked() {
        val vm = WeekViewModel(core, main.dispatcher)
        vm.nextWeek()
        vm.refresh()
        assertEquals("2026-11-23", asked.last())
    }

    private val realWeek by lazy {
        V2Json.parseWeekRows(javaClass.getResourceAsStream("/phone/week-rows.json")!!.bufferedReader().readText())
    }

    @Test fun theRealWeekListsEachSessionWithStartAndLength() {
        val monday = realWeek.days[0].sessions
        assertEquals(listOf("History essay", "Bio reading"), monday.map { it.title })
        assertEquals(listOf(900, 960), monday.map { it.start })
        assertEquals(listOf(60, 30), monday.map { it.minutes })
        assertEquals("a due line has no time", null, realWeek.days[6].sessions.single().start)
    }

    @Test fun freeDaysRunIntoOneLineAndDaysWithSessionsKeepTheirHeading() {
        val entries = WeekList.build(realWeek.days, today = LocalDate.parse("2026-10-19"))
        val labels = entries.map { if (it is WeekEntry.Day) it.label else (it as WeekEntry.Free).label }
        assertEquals(listOf("Mon 19 · today", "Tue 20", "Wed 21", "Thu 22 · Fri 23", "Sat 24", "Sun 25"), labels)
        assertTrue(entries[3] is WeekEntry.Free)
    }

    @Test fun threeFreeDaysInARowAreOneRange() {
        val days = realWeek.days.mapIndexed { i, d -> if (i in 1..3) d.copy(sessions = emptyList()) else d }
        val labels = WeekList.build(days, LocalDate.parse("2026-10-19")).filterIsInstance<WeekEntry.Free>().map { it.label }
        assertEquals(listOf("Tue 20 – Fri 23"), labels)
    }

    @Test fun thePlannedAndDoneLineKeepsFinishedTimeApart() {
        assertEquals("3 h of homework planned · 1 h done", WeekRowWords.summary(180, 60))
        assertEquals("1 h 30 of homework planned", WeekRowWords.summary(90, 0))
        assertEquals("No homework planned", WeekRowWords.summary(0, 0))
        assertFalse(WeekRowWords.summary(60, 60).contains("2 h"))
    }
}
