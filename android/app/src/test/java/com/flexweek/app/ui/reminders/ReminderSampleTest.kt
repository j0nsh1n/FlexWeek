package com.flexweek.app.ui.reminders

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class ReminderSampleTest {
    @Test fun theSampleIsTheRealNotificationsShape() {
        // The real reminder is the block's title with "7:00 PM · 1 h" as its text: no "starts in", no "then free until".
        assertEquals("7:00 PM · 1 h", ReminderSample.body())
        assertFalse(ReminderSample.TITLE.contains("starts in"))
    }

    @Test fun theSoundRowIsGoneBecauseNothingSetsIt() {
        val screen = File("src/main/java/com/flexweek/app/ui/reminders/RemindersScreen.kt").readText()
        assertFalse("a Sound row with no control", screen.contains("title = \"Sound\""))
        assertTrue(screen.contains("ReminderSample.body()"))
    }
}
