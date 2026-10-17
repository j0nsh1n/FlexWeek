package com.flexweek.app.ui.today

import com.flexweek.app.model.AgendaRow
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NowRowActionsTest {
    private val row = AgendaRow.Now("hw", "Homework", "now", "30 min", "today", true, null, null, true, true)

    @Test fun runningLateIsHiddenInReleaseBuild() {
        assertFalse(nowRowActions(row, lateEnabled = false).runningLate)
    }

    @Test fun runningLateShowsInDebugBuild() {
        assertTrue(nowRowActions(row, lateEnabled = true).runningLate)
    }

    @Test fun finishHomeworkStaysVisibleInReleaseBuild() {
        assertTrue(nowRowActions(row, lateEnabled = false).finishHomework)
    }

    @Test fun startFocusShowsOnAHomeworkRowInRelease() {
        assertTrue("a homework Now row offers Start focus", nowRowActions(row, lateEnabled = false).startFocus)
    }

    @Test fun startFocusIsNotOfferedOnAPlainBlock() {
        val plain = row.copy(showFinishFocus = false)
        assertFalse("a plain block does not offer Start focus", nowRowActions(plain, lateEnabled = false).startFocus)
    }
}
