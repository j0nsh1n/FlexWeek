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
    fun addShowsOnTodayAndWeekButNotSettings() {
        assertTrue(MainTabs.addAvailable(MainTab.Today))
        assertTrue(MainTabs.addAvailable(MainTab.Week))
        assertFalse("Add covered Sync now on Settings", MainTabs.addAvailable(MainTab.Settings))
    }
}

class BackStepsTest {
    @Test fun anOpenSheetClosesFirstOnAnyTab() {
        MainTab.entries.forEach { assertEquals(BackStep.CloseSheet, BackSteps.next(sheetOpen = true, tab = it)) }
    }

    @Test fun thenWeekAndSettingsGoBackToToday() {
        assertEquals(BackStep.GoToToday, BackSteps.next(false, MainTab.Week))
        assertEquals(BackStep.GoToToday, BackSteps.next(false, MainTab.Settings))
    }

    @Test fun onlyTodayWithNoSheetLeavesTheApp() {
        assertEquals(BackStep.Leave, BackSteps.next(false, MainTab.Today))
    }
}
