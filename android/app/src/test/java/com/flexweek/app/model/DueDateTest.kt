package com.flexweek.app.model

import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DueDateTest {
    @Test fun dueDateAtEndOfThatDay() = assertEquals(
        "2026-10-23T23:59", DueDate.toDueText(LocalDate.parse("2026-10-23"), LocalDate.parse("2026-10-16")),
    )

    @Test fun aDayBeforeTodayIsRefusedWithoutThrowing() {
        // The sheet was opened yesterday and saved after midnight: its chip is now in the past.
        val result = runCatching { DueDate.toDueText(LocalDate.parse("2026-10-15"), LocalDate.parse("2026-10-16")) }
        assertTrue("refused with no exception, was $result", result.isSuccess && result.getOrNull() == null)
    }
}
