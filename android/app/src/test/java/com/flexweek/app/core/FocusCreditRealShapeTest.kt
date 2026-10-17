package com.flexweek.app.core

import com.flexweek.app.model.FocusJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertFalse
import org.junit.Test

class FocusCreditRealShapeTest {
    private fun fixture(name: String): String {
        val stream = javaClass.classLoader?.getResourceAsStream("phone/$name")
        assertNotNull("real core fixture phone/$name exists", stream)
        return stream!!.bufferedReader().use { it.readText() }
    }

    @Test fun creditFixtureKeepsRealHomeworkShape() {
        val credit = FocusJson.parseCredit(fixture("focus-credit.json"))
        assertEquals(30, credit.getInt("focus_minutes"))
        assertEquals(1, credit.getInt("focus_sessions"))
        assertFalse(credit.getBoolean("completed"))
    }

    @Test fun runningAndPausedFixturesParseAsFocusStates() {
        assertEquals("History essay", FocusJson.parseState(fixture("focus-running.json"))?.title)
        val paused = FocusJson.parseState(fixture("focus-paused.json"))
        assertEquals(false, paused?.running)
        assertEquals(600_000L, paused?.remainingMs)
    }

    @Test fun replaceFixtureNamesBothHomeworkItems() {
        assertEquals("History essay" to "Bio reading", FocusJson.parseReplace(fixture("focus-replace.json")))
        assertEquals("needs_replace", JSONObject(fixture("focus-replace.json")).getString("kind"))
    }
}
