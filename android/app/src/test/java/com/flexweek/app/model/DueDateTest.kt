package com.flexweek.app.model

import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Test

class DueDateTest {
    @Test fun dueDateAtEndOfThatDay() = assertEquals(
        "2026-10-23T23:59", DueDate.toDueText(LocalDate.parse("2026-10-23"), LocalDate.parse("2026-10-16")),
    )
}
