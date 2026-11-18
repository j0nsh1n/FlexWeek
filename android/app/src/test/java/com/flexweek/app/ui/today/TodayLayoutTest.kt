package com.flexweek.app.ui.today

import com.flexweek.app.model.AgendaRow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TodayLayoutTest {
    private val both = NowRowActions(finishHomework = true, startFocus = true, runningLate = true)

    // The phone Jonathan tests on is 360 dp wide; the page pads 16 dp a side and the card 16 dp a side,
    // so the buttons share 360 - 64 = 296 dp.
    private val inner360 = 296f

    @Test fun twoButtonsSideBySideAtNormalTextOn360dp() {
        assertFalse(UpNextLayout.of(both, inner360, 1.0f).stacked)
    }

    @Test fun theButtonsStackAtFontScale13On360dpSoNoLabelIsCut() {
        val layout = UpNextLayout.of(both, inner360, 1.3f)
        assertTrue(layout.stacked)
        // Stacked, each label has the whole 296 dp.
        assertTrue(UpNextLayout.labelWidthDp(UpNextLayout.RUNNING_LATE, 1.3f) <= inner360)
    }

    @Test fun anyWidthAndScaleEitherFitsHalfOrStacks() {
        for (width in listOf(300f, 320f, 360f, 411f, 600f)) for (scale in listOf(0.85f, 1f, 1.15f, 1.3f, 1.5f, 2f)) {
            val layout = UpNextLayout.of(both, width, scale)
            val half = (width - 8f) / 2f
            val sideBySideFits = UpNextLayout.labelWidthDp(UpNextLayout.RUNNING_LATE, scale) <= half
            assertEquals("width $width scale $scale", !sideBySideFits, layout.stacked)
        }
    }

    @Test fun aLoneRunningLateButtonNeverStacks() {
        val layout = UpNextLayout.of(NowRowActions(false, false, true), 200f, 2f)
        assertFalse(layout.stacked)
        assertTrue(layout.late)
        assertFalse(layout.done)
    }

    @Test fun timeColumnSplitsTheClockFromAmPm() {
        assertEquals("4:30" to "PM", TimeColumn.split("4:30 PM"))
        assertEquals("16:30" to null, TimeColumn.split("16:30"))
    }

    private fun item(id: String, past: Boolean) =
        AgendaRow.Item(id, id, "school", "8:00 AM", "", homework = false, done = past, past = past)

    private fun now() = AgendaRow.Now("n", "n", "UP NEXT", "in 5 min", "", true, null, null, true, true)

    @Test fun rowsBeforeUpNextAreEarlierAndRowsAfterAreLater() {
        val groups = TodayGroups.of(listOf(item("a", true), now(), item("b", false), AgendaRow.NothingLeft))
        assertEquals(listOf("a"), groups.earlier.map { it.id })
        assertEquals(listOf("b"), groups.later.map { it.id })
        assertEquals("n", groups.upNext?.id)
        assertEquals(listOf<AgendaRow>(AgendaRow.NothingLeft), groups.notes)
    }

    @Test fun withNoUpNextAPastItemIsStillEarlier() {
        val groups = TodayGroups.of(listOf(item("a", true), item("b", false)))
        assertNull(groups.upNext)
        assertEquals(listOf("a"), groups.earlier.map { it.id })
        assertEquals(listOf("b"), groups.later.map { it.id })
    }
}
