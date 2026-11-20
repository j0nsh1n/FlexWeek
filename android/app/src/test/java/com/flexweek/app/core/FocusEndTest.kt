package com.flexweek.app.core

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusEndTest {
    @Test fun aRefusedCreditStillEndsTheTimerAndReportsTheRefusal() {
        var cleared = false
        var finished = false
        val answer = JSONObject(
            FocusEnd.run(
                credit = { throw IllegalStateException("homework was not found") },
                finish = { finished = true; "{}" },
                clearSavedTimer = { cleared = true },
                refusalText = { it.message ?: "" },
            ),
        )
        assertTrue("the engine's focus state is finished", finished)
        assertTrue("the saved timer is removed", cleared)
        assertFalse(answer.getBoolean("ok"))
        assertEquals("homework was not found", answer.getString("error"))
    }

    @Test fun anAcceptedCreditEndsTheTimerQuietly() {
        var cleared = false
        val answer = JSONObject(FocusEnd.run({}, { "{}" }, { cleared = true }, { "x" }))
        assertTrue(cleared)
        assertTrue(answer.getBoolean("ok"))
    }
}
