package com.flexweek.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ScreenshotTweaksTest {
    @Test fun darkThemeFollowsSystemWhenNoExtraIsSent() {
        assertNull(ScreenshotTweaks.parse(emptyMap()).darkTheme)
    }

    @Test fun darkThemeExtraTrueForcesDarkForScreenshots() {
        assertEquals(true, ScreenshotTweaks.parse(mapOf("darkTheme" to true)).darkTheme)
    }

    @Test fun darkThemeExtraFalseForcesLightForScreenshots() {
        assertEquals(false, ScreenshotTweaks.parse(mapOf("darkTheme" to false)).darkTheme)
    }
}
