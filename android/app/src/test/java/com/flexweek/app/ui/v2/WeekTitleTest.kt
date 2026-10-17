package com.flexweek.app.ui.v2

import com.flexweek.app.model.WeekTitle
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Test

class WeekTitleTest {
    @Test
    fun sameMonthKeepsOneMonthName() {
        assertEquals("19 – 25 Oct", WeekTitle.format(LocalDate.parse("2026-10-19")))
    }

    @Test
    fun crossingIntoNextYearShowsTheYear() {
        assertEquals("28 Dec – 3 Jan 2027", WeekTitle.format(LocalDate.parse("2026-12-28")))
    }

    @Test
    fun crossingMonthsShowsBothMonthNames() {
        assertEquals("28 Sep – 4 Oct", WeekTitle.format(LocalDate.parse("2026-09-28")))
    }
}
