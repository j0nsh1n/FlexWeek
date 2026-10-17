package com.flexweek.app.core

import com.flexweek.app.model.V2Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

// The real core's Running late output, saved by engine/ffi (phone_fixture_running_late_matches_the_output_
// and_the_android_copy): Monday 16:05, School fixed until 14:30, Soccer fixed at 17:30, the History essay
// at 16:00, thirty minutes late. Until 1.1 these screens were only ever tested against the fake core.
class RunningLateRealCoreTest {
    private fun fixture(): String {
        val stream = javaClass.getResourceAsStream("/phone/running-late-30.json")
        assertNotNull("the phone fixture is on the test classpath", stream)
        return stream!!.bufferedReader().use { it.readText() }
    }

    @Test fun realRunningLateMovesParse() {
        val preview = V2Json.parseRunningLate(RustPhoneJson.late(fixture(), 30))
        assertEquals(1, preview.moves.size)
        assertEquals("History essay", preview.moves[0].title)
        assertEquals("4 PM → 4:30 PM", preview.moves[0].detail)
    }

    @Test fun realRunningLateWhyIsTheCoresSentence() {
        val move = V2Json.parseRunningLate(RustPhoneJson.late(fixture(), 30)).moves.single()
        assertTrue("why is the core's words, not the phone's default: ${move.why}", move.why != "Running late")
        assertTrue("running late is not a missed day: ${move.why}", "missed a day" !in move.why)
    }

    @Test fun realRunningLateTitleIsNeverBlank() {
        val preview = V2Json.parseRunningLate(RustPhoneJson.late(fixture(), 30))
        assertTrue(preview.moves.isNotEmpty())
        preview.moves.forEach { assertTrue("a move has a title", it.title.isNotBlank()) }
    }
}
