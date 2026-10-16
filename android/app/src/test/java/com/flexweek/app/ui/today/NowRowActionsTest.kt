package com.flexweek.app.ui.today

import com.flexweek.app.model.AgendaRow
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NowRowActionsTest {
    private val row = AgendaRow.Now("hw", "Homework", "now", "30 min", "today", true, null, null, true, true)

    @Test fun runningLateIsHiddenInReleaseBuild() {
        assertFalse(nowRowActions(row, focusEnabled = false, lateEnabled = false).runningLate)
    }

    @Test fun runningLateShowsInDebugBuild() {
        assertTrue(nowRowActions(row, focusEnabled = true, lateEnabled = true).runningLate)
    }

    @Test fun finishHomeworkStaysVisibleInReleaseBuild() {
        assertTrue(nowRowActions(row, focusEnabled = false, lateEnabled = false).finishHomework)
    }

    @Test fun startFocusIsHiddenInReleaseUntilFocusShips() {
        assertFalse(nowRowActions(row, focusEnabled = false, lateEnabled = false).startFocus)
    }

    @Test fun startFocusShowsWhenFocusIsEnabled() {
        assertTrue(nowRowActions(row, focusEnabled = true, lateEnabled = true).startFocus)
    }
}
