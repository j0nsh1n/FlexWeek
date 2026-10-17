package com.flexweek.app.system.widget

import com.flexweek.app.core.RustPhoneJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

class WidgetRefreshTest {
    private val zone = ZoneId.of("America/Los_Angeles")
    private val synced = """{"paired":true,"state":"synced","line":"Synced just now","has_account":true}"""

    private fun at(hour: Int, minute: Int, second: Int = 0, day: Int = 12): Long =
        ZonedDateTime.of(2026, 10, day, hour, minute, second, 0, zone).toInstant().toEpochMilli()

    private fun phone(edit: (JSONObject) -> Unit = {}): String {
        val root = JSONObject(javaClass.getResourceAsStream("/phone/today-up-next.json")!!.bufferedReader().use { it.readText() })
        edit(root)
        return RustPhoneJson.today(root.toString(), "2026-10-12", synced)
    }

    @Test fun theNextBoundaryIsTheNextStartMinute() {
        val wake = WidgetRefresh.nextWake(at(14, 10), zone, listOf(14 * 60 + 30, 16 * 60), countdownShowing = false)
        assertEquals(at(14, 30), wake.atMs)
        assertEquals(WidgetRefresh.Kind.BOUNDARY, wake.kind)
    }

    @Test fun whileAnItemRunsTheNextBoundaryIsItsEnd() {
        val wake = WidgetRefresh.nextWake(at(14, 30), zone, listOf(14 * 60 + 30, 16 * 60), countdownShowing = false)
        assertEquals(at(16, 0), wake.atMs)
    }

    @Test fun withNothingLeftTheNextWakeIsLocalMidnight() {
        val wake = WidgetRefresh.nextWake(at(17, 0), zone, listOf(14 * 60 + 30, 16 * 60), countdownShowing = false)
        assertEquals(at(0, 0, day = 13), wake.atMs)
        assertEquals(WidgetRefresh.Kind.MIDNIGHT, wake.kind)
    }

    @Test fun midnightOnADaylightSavingDayIsLocalZeroNotTwentyFourHoursLater() {
        val now = ZonedDateTime.of(2026, 3, 8, 22, 0, 0, 0, zone)
        val wake = WidgetRefresh.nextWake(now.toInstant().toEpochMilli(), zone, emptyList(), countdownShowing = false)
        val midnight = ZonedDateTime.of(2026, 3, 9, 0, 0, 0, 0, zone).toInstant().toEpochMilli()
        val naive = ZonedDateTime.of(2026, 3, 8, 0, 0, 0, 0, zone).toInstant().plusSeconds(24 * 3600).toEpochMilli()
        assertNotEquals("the check needs a day that is not 24 hours long", midnight, naive)
        assertEquals(midnight, wake.atMs)
    }

    @Test fun aSyncThatMovesTheHeadlineMovesTheWake() {
        val before = WidgetWords.boundaryMinutes(phone())
        val after = WidgetWords.boundaryMinutes(phone { root ->
            root.getJSONArray("rows").getJSONObject(0).put("start", "15:00").put("start_min", 900)
        })
        assertTrue("the fixture has boundaries", before.isNotEmpty())
        assertEquals(at(14, 30), WidgetRefresh.nextWake(at(14, 10), zone, before, countdownShowing = false).atMs)
        assertEquals(at(15, 0), WidgetRefresh.nextWake(at(14, 10), zone, after, countdownShowing = false).atMs)
    }

    @Test fun neverWakesBeforeTheBoundary() {
        val wake = WidgetRefresh.nextWake(at(14, 29, 59), zone, listOf(14 * 60 + 30), countdownShowing = false)
        assertEquals(at(14, 30), wake.atMs)
        assertNotEquals("woke a minute early", at(14, 29), wake.atMs)
    }

    @Test fun aShowingCountdownWakesOnTheNextMinute() {
        val wake = WidgetRefresh.nextWake(at(14, 10, 20), zone, listOf(14 * 60 + 30), countdownShowing = true)
        assertEquals(at(14, 11), wake.atMs)
        assertEquals(WidgetRefresh.Kind.MINUTE, wake.kind)
    }

    @Test fun aBoundaryOnTheSameMinuteBeatsTheCountdownTick() {
        val wake = WidgetRefresh.nextWake(at(14, 10, 20), zone, listOf(14 * 60 + 11), countdownShowing = true)
        assertEquals(WidgetRefresh.Kind.BOUNDARY, wake.kind)
    }

    @Test fun theCountdownTicksOnlyWithinSixtyMinutes() {
        assertTrue("20 min is inside the window", WidgetWords.countdownShowing(phone()))
        assertFalse(
            "90 min is outside the window",
            WidgetWords.countdownShowing(phone { it.getJSONObject("now").put("minutes_left", 90) }),
        )
        assertEquals(60, WidgetWords.COUNTDOWN_WINDOW_MIN)
    }
}
