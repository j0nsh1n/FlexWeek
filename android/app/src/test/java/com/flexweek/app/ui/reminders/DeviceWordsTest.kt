package com.flexweek.app.ui.reminders

import com.flexweek.app.core.RustPhoneJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId

class DeviceWordsTest {
    private val zone = ZoneId.of("UTC")
    private val prefs = """{"reminder_lead_min":10}"""
    private fun sync(vararg fields: Pair<String, Any?>) =
        JSONObject().also { json -> fields.forEach { (key, value) -> json.put(key, value) } }.toString()

    private fun state(settings: String): RemindersUiState = JSONObject(settings).let {
        RemindersUiState(deviceName = it.getString("device_name"), pairedAt = it.getString("paired_at"),
            reachable = it.getBoolean("reachable"), paired = it.getBoolean("paired"), lastSync = it.getString("last_sync"))
    }

    @Test fun aPairedComputerThatIsOffNeverReadsAsNotLinked() {
        val raw = sync("paired" to true, "state" to "unreachable", "peer_name" to "Joo's laptop",
            "paired_at" to "1760000000000", "last_sync_ms" to 1_760_100_000_000L)
        val shown = state(RustPhoneJson.phoneSettings(prefs, RustPhoneJson.sync(raw, zone), false, zone))
        assertEquals("Joo's laptop", DeviceWords.title(shown))
        val line = DeviceWords.line(shown)
        assertTrue(line, "isn't reachable" in line && "last synced" in line)
        assertFalse(line, "Wi" in line)
    }

    @Test fun aReachableComputerSaysReachableNotSameWifi() {
        val raw = sync("paired" to true, "state" to "synced", "peer_name" to "Joo's laptop", "paired_at" to "1760000000000")
        val line = DeviceWords.line(state(RustPhoneJson.phoneSettings(prefs, raw, false, zone)))
        assertTrue(line, line.endsWith("· reachable"))
        assertFalse(line, "Wi" in line)
    }

    @Test fun noPairedComputerSaysSoOnTheRowToo() {
        val shown = state(RustPhoneJson.phoneSettings(prefs, RustPhoneJson.sync("not paired"), false, zone))
        assertEquals(DeviceWords.NOT_LINKED_TITLE, DeviceWords.title(shown))
        assertFalse(DeviceWords.line(shown).contains("Paired"))
    }
}
