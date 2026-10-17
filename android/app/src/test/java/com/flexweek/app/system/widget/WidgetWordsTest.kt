package com.flexweek.app.system.widget

import com.flexweek.app.core.RustPhoneJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

// The words are typed from picture 9 A (Monday, 2:10 PM): the fixture is real engine output, never the fake core's.
class WidgetWordsTest {
    private val synced = """{"paired":true,"state":"synced","line":"Synced just now","has_account":true}"""
    private val unreachable = """{"paired":true,"state":"unreachable","line":"Your computer isn't reachable. Showing the last saved week.","has_account":true}"""

    private fun fixture(): JSONObject =
        JSONObject(javaClass.getResourceAsStream("/phone/today-up-next.json")!!.bufferedReader().use { it.readText() })

    private fun phone(sync: String = synced, edit: (JSONObject) -> Unit = {}): String {
        val root = fixture()
        edit(root)
        return RustPhoneJson.today(root.toString(), "2026-10-12", sync)
    }

    private fun content(sync: String = synced, edit: (JSONObject) -> Unit = {}) = WidgetWords.from(phone(sync, edit))

    @Test fun kickerSaysUpNextAndTheCountdown() {
        assertEquals("Up next · in 20 min", content().kicker)
    }

    @Test fun headlineIsTheNextItemWithItsRangeAndLength() {
        val shown = content()
        assertEquals("Algebra set 4", shown.headline)
        assertEquals("2:30–4 PM · 1 h 30 min", shown.headlineTime)
    }

    @Test fun firstRowAfterTheHeadlineIsSpanishQuizPrep() {
        val rows = content().rows
        assertEquals("two rows follow the headline", 2, rows.size)
        assertEquals(listOf("4 PM", "Spanish quiz prep", "45 min"), listOf(rows[0].time, rows[0].title, rows[0].length))
        assertTrue("homework gets the tick", rows[0].homework)
        assertFalse(rows[0].done)
    }

    @Test fun secondRowIsSoccerPractice() {
        val rows = content().rows
        assertEquals("two rows follow the headline", 2, rows.size)
        assertEquals(listOf("5 PM", "Soccer practice", "2 h"), listOf(rows[1].time, rows[1].title, rows[1].length))
        assertFalse("fixed items get no tick", rows[1].homework)
    }

    @Test fun runningUsesTodaysWords() {
        val shown = content { root -> root.getJSONObject("now").put("kind", "now").put("minutes_left", 20) }
        assertEquals("Now · 20 min left", shown.kicker)
    }

    @Test fun aDoneRowKeepsItsTickFilledAndTheHeadlineNeverSaysFinished() {
        val shown = content { root ->
            root.getJSONArray("rows").getJSONObject(0).put("done", true)
            root.getJSONArray("rows").getJSONObject(1).put("done", true)
        }
        assertEquals("a finished row stays listed until it is past", 2, shown.rows.size)
        assertTrue(shown.rows[0].done)
        assertNotNull("the headline has a time line", shown.headlineTime)
        assertFalse("no finished suffix in the headline: ${shown.headlineTime}", shown.headlineTime.orEmpty().contains("finished"))
    }

    @Test fun aDayWithNoRowsSaysNothingLeftToday() {
        val shown = content { root ->
            root.put("rows", org.json.JSONArray())
            root.put("now", JSONObject.NULL)
            root.put("empty", true)
        }
        assertEquals("Nothing left today", shown.headline)
        assertTrue(shown.rows.isEmpty())
        assertNull(shown.kicker)
    }

    @Test fun aDayThatIsOverSaysNothingLeftToday() {
        val shown = content { root ->
            val rows = root.getJSONArray("rows")
            for (i in 0 until rows.length()) rows.getJSONObject(i).put("past", true)
            root.put("now", JSONObject.NULL)
            root.put("nothing_left", true)
        }
        assertEquals("Nothing left today", shown.headline)
        assertTrue(shown.rows.isEmpty())
    }

    @Test fun anUnpairedPhoneShowsTodaysSyncWords() {
        val shown = content(sync = RustPhoneJson.sync("")) { root ->
            root.put("rows", org.json.JSONArray())
            root.put("now", JSONObject.NULL)
            root.put("empty", true)
        }
        assertEquals("No computer linked. Your week is saved here.", shown.headline)
        assertTrue(shown.rows.isEmpty())
    }

    @Test fun anUnreachableComputerKeepsTheAgendaAndAddsTheLine() {
        val shown = content(sync = unreachable)
        assertEquals("Up next · in 20 min", shown.kicker)
        assertEquals("Your computer isn't reachable. Showing the last saved week.", shown.note)
        assertNull("a reachable computer adds no line", content().note)
    }

    @Test fun timesUseTheShortFormWithNoZeroMinutes() {
        val shown = content()
        assertNotNull("the headline has a time line", shown.headlineTime)
        val times = listOf(shown.headlineTime.orEmpty()) + shown.rows.map { it.time }
        assertTrue("there are times to check", times.size == 3)
        times.forEach { assertFalse("no :00 in $it", it.contains(":00")) }
    }

    @Test fun aRangeDropsTheFirstHalfOnlyWhenBothAreInTheSameHalf() {
        assertEquals("2:30–4 PM", WidgetWords.range("14:30", "16:00"))
        assertEquals("11 AM–1 PM", WidgetWords.range("11:00", "13:00"))
        assertEquals("9–9:30 AM", WidgetWords.range("09:00", "09:30"))
    }

    @Test fun moreThanTwoLaterRowsAreCappedAtTwo() {
        val shown = content { root ->
            val rows = root.getJSONArray("rows")
            val last = rows.getJSONObject(2)
            rows.put(JSONObject(last.toString()).put("id", "extra-1").put("start", "19:00").put("end", "19:30").put("start_min", 1140).put("end_min", 1170).put("duration_min", 30))
        }
        assertEquals(2, shown.rows.size)
        assertEquals(listOf("Spanish quiz prep", "Soccer practice"), shown.rows.map { it.title })
    }

    @Test fun pastRowsAreNotListedAfterTheHeadline() {
        val shown = content { root -> root.getJSONArray("rows").getJSONObject(1).put("past", true) }
        assertEquals(listOf("Soccer practice"), shown.rows.map { it.title })
    }

    @Test fun theTickSaysWhatItMarks() {
        assertEquals("Mark Spanish quiz prep finished", WidgetWords.tickLabel("Spanish quiz prep"))
    }

    @Test fun placeholderIsTheOpenTheAppLine() {
        assertEquals("Open FlexWeek to see your week.", WidgetWords.placeholder().headline)
    }
}
