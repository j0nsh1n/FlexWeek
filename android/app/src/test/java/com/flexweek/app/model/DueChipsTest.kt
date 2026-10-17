package com.flexweek.app.model

import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DueChipsTest {
    @Test fun chipsAreOnOrAfterToday() {
        val today = LocalDate.parse("2026-10-16")
        assertTrue(DueChips.forToday(today).all { !it.date.isBefore(today) })
    }

    @Test fun chipLabelMatchesItsDate() {
        val chips = DueChips.forToday(LocalDate.parse("2026-10-16"))
        assertEquals("Fri 23 Oct", chips[1].label)
        assertEquals(5, chips[1].date.dayOfWeek.value)
    }

    @Test fun chipsRollIntoTheNextYear() {
        val chips = DueChips.forToday(LocalDate.parse("2026-12-30"))
        assertEquals("Fri 1 Jan", chips[1].label)
        assertEquals(LocalDate.parse("2027-01-01"), chips[1].date)
    }

    @Test fun noTwoChipsShareADate() {
        // On a Thursday tomorrow is the next Friday; on a Sunday it is the next Monday.
        for (day in listOf("2026-10-15", "2026-10-18")) {
            val dates = DueChips.forToday(LocalDate.parse(day)).filter { it.label != "Pick a day" }.map { it.date }
            assertEquals("chips on $day: $dates", dates.distinct(), dates)
        }
    }

    @Test fun aChosenDayIsSaidTheWayItsChipSaysIt() {
        val today = LocalDate.parse("2026-10-16")
        assertEquals("Tomorrow", DueChips.label(LocalDate.parse("2026-10-17"), today))
        assertEquals("Fri 23 Oct", DueChips.label(LocalDate.parse("2026-10-23"), today))
    }
}
