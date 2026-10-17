package com.flexweek.app.ui.nav

enum class MainTab(val label: String, val icon: String) {
    Today("Today", "▤"),
    Week("Week", "▦"),
    Settings("Settings", "⚙"),
}

/** The bottom bar's tabs, in order, and where Add shows: MainActivity draws both from here. */
object MainTabs {
    val releaseTabs = listOf(MainTab.Today, MainTab.Week, MainTab.Settings)

    /** Add is an action over every tab, not a tab of its own (pick 1 A). */
    fun addAvailable(tab: MainTab): Boolean = tab in releaseTabs
}
