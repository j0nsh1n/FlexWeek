package com.flexweek.app.core

import com.flexweek.app.model.AgendaRow
import com.flexweek.app.model.TodayJson
import com.flexweek.app.model.V2Json
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class RustPhoneJsonTest {
    private fun agenda(): String {
        val days = JSONArray()
        for (day in 0..6) days.put(JSONObject().put("day", day)
            .put("date", "2026-10-${(5 + day).toString().padStart(2, '0')}")
            .put("scheduled_count", if (day == 3) 1 else 0).put("due_count", if (day == 4) 1 else 0))
        return JSONObject().put("date", "2026-10-08").put("week_start", "2026-10-05")
            .put("day", 3).put("days", days).put("nothing_left", false)
            .put("rows", JSONArray("""[{"id":"essay-session","assignment_id":"essay","title":"History essay","category":"homework","start":"19:00","end":"20:00","duration_min":60,"homework":true,"done":false,"past":false}]"""))
            .put("now", JSONObject("""{"kind":"up_next","block_id":"essay-session","title":"History essay","minutes_left":20,"then_title":null,"then_start":null}"""))
            .put("no_time_yet", JSONArray("""[{"id":"poster-session","title":"Science poster","minutes":60,"due":"2026-10-09T16:00"}]"""))
            .toString()
    }
    private val sync = """{"state":"synced","line":"Synced just now","paired":true}"""

    @Test fun nativeAgendaKeepsTheSessionIdAndShowsUpNext() {
        val state = TodayJson.parse(RustPhoneJson.today(agenda(), "2026-10-08", sync))
        assertEquals("Today", state.title)
        assertEquals(7, state.days.size)
        assertEquals(8, state.days[3].date)
        assertTrue(state.days[3].isToday)
        assertTrue(state.days[4].hasDot)
        val now = state.rows.single() as AgendaRow.Now
        assertEquals("essay-session", now.id)
        assertEquals("Up next", now.kick)
        assertEquals("in 20 min", now.minsLabel)
        assertEquals("7:00 PM–8:00 PM · 60 min", now.whenLine)
        assertEquals("Fri 9 Oct", state.noTime.single().dueLabel)
    }

    @Test fun anotherDateHasOrdinaryRowsAndAJumpBackToToday() {
        val state = TodayJson.parse(RustPhoneJson.today(agenda(), "2026-10-09", sync))
        assertEquals("Thursday", state.title)
        assertEquals("Thursday 8 October", state.daySubtitle)
        assertTrue(state.showTodayJump)
        assertTrue(state.days[4].isToday)
        val item = state.rows.single() as AgendaRow.Item
        assertEquals("essay-session", item.id)
        assertEquals("7:00 PM", item.timeLabel)
        assertFalse(item.done)
    }

    @Test fun nativeWeekSegmentsBecomeDayBars() {
        val shape = V2Json.parseWeekShape(RustPhoneJson.week(
            """{"week_start":"2026-10-05","days":[{"day":0,"segments":[{"start_min":480,"end_min":540,"category":"school"}]}]}""",
            "2026-10-05",
        ))
        val day = shape.days.single()
        assertTrue(day.isToday)
        assertEquals(0, day.dayIndex)
        assertEquals("school", day.bars.single().category)
        assertEquals(1f / 3f, day.bars.single().topFraction, 0.00001f)
        assertEquals(1f / 24f, day.bars.single().heightFraction, 0.00001f)
    }
}
