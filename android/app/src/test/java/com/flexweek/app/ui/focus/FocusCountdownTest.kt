package com.flexweek.app.ui.focus

import com.flexweek.app.model.FocusJson
import com.flexweek.app.model.FocusUiState
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusCountdownTest {
    @Test fun countdownShowsMinutesAndSeconds() {
        assertEquals("24:12", FocusJson.countdown(1_452_000))
    }

    @Test fun countdownNeverGoesBelowZero() {
        assertEquals("00:00", FocusJson.countdown(-1))
    }

    @Test fun pausedCardShowsTheSavedTime() {
        val paused = FocusUiState("history", "History essay", "work", false, 0, 600_000, 30)
        assertEquals(600_000, paused.remaining(99_000_000))
        assertEquals("10:00", FocusJson.countdown(paused.remaining(99_000_000)))
    }
}
