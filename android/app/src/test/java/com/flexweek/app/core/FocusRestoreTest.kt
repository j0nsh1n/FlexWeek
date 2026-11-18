package com.flexweek.app.core

import com.flexweek.app.bindings.FfiException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FocusRestoreTest {
    @Test fun aTimerForAHomeworkThatIsGoneIsDroppedAndOpeningCarriesOn() {
        val kept = FocusRestore.keep("""{"assignmentId":"gone"}""") { throw FfiException.Failure("homework was not found") }
        assertNull(kept)
    }

    @Test fun anUnreadableAnswerDropsTheTimerToo() = assertNull(FocusRestore.keep("{}") { "not json" })

    @Test fun aTimerThatRestoresIsKept() {
        val kept = FocusRestore.keep("{}") { """{"state":{},"persist":{"assignmentId":"essay","phase":"work"}}""" }
        assertEquals("essay", org.json.JSONObject(kept!!).getString("assignmentId"))
    }

    @Test fun anEndedTimerHasNothingToKeep() = assertNull(FocusRestore.keep("{}") { """{"state":null,"persist":null}""" })
}
