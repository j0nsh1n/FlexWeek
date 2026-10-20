package com.flexweek.app.ui.v2

import org.junit.Assert.assertEquals
import org.junit.Test

class LateSliderTest {
    @Test
    fun zeroFractionPicksTheFiveMinuteStop() {
        assertEquals("fraction 0f picks the first slider stop: the 5-minute stop", 5, LateSlider.minutesAt(0f))
    }

    @Test
    fun halfFractionRoundsHalvesUpToTheThirtyFiveMinuteStop() {
        assertEquals("fraction 0.5f rounds halves-up to the 35-minute stop", 35, LateSlider.minutesAt(0.5f))
    }

    @Test
    fun fullFractionPicksTheSixtyMinuteStop() {
        assertEquals("fraction 1f picks the last slider stop: the 60-minute stop", 60, LateSlider.minutesAt(1f))
    }
}
