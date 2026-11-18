package com.flexweek.app.ui.nav

import androidx.annotation.DrawableRes
import com.flexweek.app.R

enum class MainTab(val label: String, @DrawableRes val icon: Int, @DrawableRes val selectedIcon: Int) {
    Today("Today", R.drawable.ic_today, R.drawable.ic_today_filled),
    Week("Week", R.drawable.ic_calendar_view_week, R.drawable.ic_calendar_view_week_filled),
    Settings("Settings", R.drawable.ic_settings, R.drawable.ic_settings_filled),
}

/** The bottom bar's tabs, in order, and where Add shows: MainActivity draws both from here. */
object MainTabs {
    val releaseTabs = listOf(MainTab.Today, MainTab.Week, MainTab.Settings)

    /** Add is an action over every tab, not a tab of its own (pick 1 A). */
    fun addAvailable(tab: MainTab): Boolean = tab in releaseTabs
}

/** What Back does: close an open sheet first, then go back to Today, and only then leave the app. */
enum class BackStep { CloseSheet, GoToToday, Leave }

object BackSteps {
    fun next(sheetOpen: Boolean, tab: MainTab): BackStep = when {
        sheetOpen -> BackStep.CloseSheet
        tab != MainTab.Today -> BackStep.GoToToday
        else -> BackStep.Leave
    }
}
