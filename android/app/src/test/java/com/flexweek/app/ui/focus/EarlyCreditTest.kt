package com.flexweek.app.ui.focus

import com.flexweek.app.model.FocusJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class EarlyCreditTest {
    private val start = 1_000_000_000L
    private fun running(workMin: Int = 25) =
        """{"assignmentId":"essay","title":"History essay","phase":"work","running":true,"endsAt":${start + workMin * 60_000L},"workMin":$workMin,"sessionId":"s1"}"""

    @Test fun sevenAndAHalfMinutesInCreditsSevenWholeMinutes() {
        val credit = FocusJson.earlyCredit(running(), start + 7 * 60_000L + 30_000L)!!
        assertEquals("essay", credit.assignmentId)
        assertEquals(7, credit.minutes)
    }

    @Test fun theDialogAndTheCreditAgree() {
        val now = start + 12 * 60_000L + 59_000L
        assertEquals(FocusJson.parseState(running())!!.elapsedMin(now), FocusJson.earlyCredit(running(), now)!!.minutes)
    }

    @Test fun lessThanAMinuteCreditsNothing() = assertNull(FocusJson.earlyCredit(running(), start + 59_000L))

    @Test fun aPausedTimerCreditsWhatWasWorkedBeforeThePause() {
        val paused = """{"assignmentId":"essay","phase":"work","running":false,"remainingMs":${18 * 60_000L},"workMin":25,"sessionId":"s1"}"""
        assertEquals(7, FocusJson.earlyCredit(paused, start)!!.minutes)
    }

    @Test fun aBreakCreditsNothing() {
        val onBreak = """{"assignmentId":"essay","phase":"break","running":true,"endsAt":${start + 300_000L},"workMin":25,"sessionId":"s2"}"""
        assertNull(FocusJson.earlyCredit(onBreak, start + 60_000L))
    }

    @Test fun noTimerCreditsNothing() = assertNull(FocusJson.earlyCredit("null", start))
}
