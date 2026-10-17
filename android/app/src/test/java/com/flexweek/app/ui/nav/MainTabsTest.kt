package com.flexweek.app.ui.nav

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MainTabsTest {
    @Test
    fun releaseTabsAreTodayWeekSettings() {
        assertEquals(listOf(MainTab.Today, MainTab.Week, MainTab.Settings), MainTabs.releaseTabs)
    }

    @Test
    fun addIsAnActionNotATab() {
        assertFalse(MainTabs.releaseTabs.any { it.name == "Add" })
    }

    @Test
    fun addIsAvailableOnEveryTab() {
        MainTabs.releaseTabs.forEach { tab -> assertTrue("Add missing on $tab", MainTabs.addAvailable(tab)) }
    }
}
