package com.flexweek.app.core

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId

class SyncWordsTest {
    @Test fun aComputerThatIsOffNeedsAnUpdateAndOtherFailuresReadDifferently() {
        val off = SyncWords.syncProblem("timeout", "the sync took too long and was stopped")
        val update = SyncWords.syncProblem("protocol", "unsupported protocol version")
        val other = SyncWords.syncProblem("database", "disk image is malformed")
        assertEquals(3, setOf(off, update, other).size)
        assertTrue(off, "isn't reachable" in off)
        assertTrue(update, "update" in update)
        assertFalse(other, "isn't reachable" in other)
    }

    @Test fun onlyAWrongCodeSaysTheCodeDidNotMatch() {
        assertTrue(SyncWords.pairProblem("wrong_code").startsWith("That code didn't match"))
        listOf("version_mismatch", "code_used", "device_mismatch", "key", "protocol", "database", "").forEach {
            assertFalse("$it: ${SyncWords.pairProblem(it)}", SyncWords.pairProblem(it).contains("didn't match"))
        }
        assertEquals(SyncWords.NEEDS_UPDATE, SyncWords.pairProblem("version_mismatch"))
        assertNotEquals(SyncWords.pairProblem("code_used"), SyncWords.pairProblem("code_expired"))
    }

    @Test fun aSuccessClearsTheKeptKindAndACancelKeepsIt() {
        assertNull(SyncWords.kindToRemember("""{"ok":true,"applied":0}""", "timeout"))
        assertEquals("timeout", SyncWords.kindToRemember("""{"ok":false,"kind":"cancelled"}""", "timeout"))
        assertEquals("protocol", SyncWords.kindToRemember("""{"ok":false,"kind":"protocol"}""", null))
    }

    @Test fun theStatusLineNamesAnUpdateInsteadOfAnOffComputer() {
        val raw = JSONObject().put("paired", true).put("state", "unreachable")
            .put("line", "Your computer isn't reachable. Showing the last saved week.").toString()
        val zone = ZoneId.of("UTC")
        assertEquals(SyncWords.NEEDS_UPDATE, JSONObject(RustPhoneJson.sync(raw, zone, "protocol")).getString("line"))
        assertTrue(JSONObject(RustPhoneJson.sync(raw, zone, "timeout")).getString("line").startsWith("Your computer isn't reachable"))
        assertEquals(SyncWords.OTHER, JSONObject(RustPhoneJson.sync(raw, zone, "database")).getString("line"))
    }
}
