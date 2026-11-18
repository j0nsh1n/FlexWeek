package com.flexweek.app.ui.reminders

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FeedbackFormTest {
    @Test fun theTemplateHasBothPlaceholdersSoTheFormArrivesFilled() {
        assertTrue(FEEDBACK_FORM_URL.contains("{version}"))
        assertTrue(FEEDBACK_FORM_URL.contains("{device}"))
    }

    @Test fun versionAndDeviceAreFilledAndEncoded() {
        val url = FeedbackForm.url("1.4.0", "Pixel 8, Android 15", "https://forms.example/f?entry.1={version}&entry.2={device}")
        assertEquals("https://forms.example/f?entry.1=1.4.0&entry.2=Pixel%208%2C%20Android%2015", url)
    }

    @Test fun aRealTemplateLeavesNoPlaceholderBehind() {
        val url = FeedbackForm.url("1.4.0", "Pixel 8, Android 15")
        assertFalse(url.contains("{"))
        assertTrue(url.contains("1.4.0"))
    }

    @Test fun theDeviceIsModelAndAndroidVersionWithoutRepeatingTheMaker() {
        assertEquals("Google Pixel 8, Android 15", FeedbackForm.device("Google", "Pixel 8", "15"))
        assertEquals("samsung SM-S911B, Android 14", FeedbackForm.device("samsung", "SM-S911B", "14"))
        assertEquals("Google Pixel 8, Android 15", FeedbackForm.device("Google", "Google Pixel 8", "15"))
    }
}
