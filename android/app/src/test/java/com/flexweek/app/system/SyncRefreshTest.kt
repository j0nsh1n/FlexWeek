package com.flexweek.app.system

import org.junit.Assert.assertEquals
import org.junit.Test

class SyncRefreshTest {
    @Test fun aSyncRefreshesTodaySettingsTheWeekAndTheWidget() {
        val calls = mutableListOf<String>()
        SyncRefresh({ calls += "today:$it" }, { calls += "settings" }, { calls += "week" }, { calls += "widget" }).afterSync(615)
        assertEquals(listOf("today:615", "settings", "week", "widget"), calls)
    }
}
