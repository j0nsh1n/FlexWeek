package com.flexweek.app.system.widget

import org.junit.Assert.assertEquals
import org.junit.Test

class WidgetSizeTest {
    private val row = { n: Int -> WidgetRow("r$n", "4 PM", "Row $n", "45 min", "school", false, false) }
    private val full = WidgetContent("Up next · in 20 min", "Algebra set 4", "2:30–4 PM · 1 h 30 min", listOf(row(1), row(2)), null)

    @Test fun theDefaultFourByTwoShowsTheTwoRows() {
        assertEquals(2, WidgetSize.rowsToShow(full, WidgetSize.ROWS_MIN_WIDTH_DP, WidgetSize.ROWS_MIN_HEIGHT_DP).size)
    }

    @Test fun smallerThanFourByTwoDropsTheRows() {
        assertEquals("two by two", 0, WidgetSize.rowsToShow(full, 110, 110).size)
        assertEquals("four by one", 0, WidgetSize.rowsToShow(full, 250, 40).size)
    }

    @Test fun largerThanFourByTwoStillShowsOnlyTwoRows() {
        val three = full.copy(rows = listOf(row(1), row(2), row(3)))
        assertEquals(2, WidgetSize.rowsToShow(three, 320, 250).size)
    }

    @Test fun anUnreachableLineTakesTheSecondRow() {
        val noted = full.copy(note = "Your computer isn't reachable. Showing the last saved week.")
        assertEquals(1, WidgetSize.rowsToShow(noted, 250, 110).size)
    }
}
