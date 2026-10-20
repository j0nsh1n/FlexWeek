package com.flexweek.app.system.widget

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

// Each trigger from decision 2 is a call in a class the JVM cannot run (a worker, an application, a receiver).
// The call is what the refresh depends on, so the source is checked for it.
class WidgetWiringTest {
    private fun source(path: String) = File("src/main/java/com/flexweek/app/$path").readText()

    private fun assertRefreshes(path: String, why: String) =
        assertTrue("$path does not refresh the widget $why", "WidgetRuntime.refreshAsync(" in source(path))

    @Test fun aSyncRefreshesTheWidget() = assertRefreshes("system/SyncWorker.kt", "after a background sync")

    @Test fun theForegroundSyncLoopRefreshesTheWidget() = assertRefreshes("MainActivity.kt", "after a foreground sync")

    @Test fun everyLocalEditRefreshesTheWidget() = assertRefreshes("FlexWeekApp.kt", "after a local edit")

    @Test fun aFocusChangeRefreshesTheWidget() = assertRefreshes("system/FocusRuntime.kt", "after a focus change")

    @Test fun aClockOrZoneChangeRefreshesTheWidget() = assertRefreshes("system/SystemEventsReceiver.kt", "after a clock or zone change")
}
