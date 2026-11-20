package com.flexweek.app.ui.reminders

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FeedbackFormTest {
    private val link = "https://docs.google.com/forms/d/e/FORM/viewform?usp=pp_url&entry.111=1.4.0&entry.222=test&entry.333=keep"

    @Test fun theSampleAnswersBecomeThisVersionAndPhone() {
        assertEquals(
            "https://docs.google.com/forms/d/e/FORM/viewform?usp=pp_url&entry.111=1.4.1&entry.222=Pixel%208%2C%20Android%2015&entry.333=keep",
            FeedbackForm.url("1.4.1", "Pixel 8, Android 15", link),
        )
    }

    @Test fun noLinkMeansNoRow() {
        assertFalse(FeedbackForm.available(""))
        assertTrue(FeedbackForm.available(link))
    }

    @Test fun theDeviceIsModelAndAndroidVersionWithoutRepeatingTheMaker() {
        assertEquals("Google Pixel 8, Android 15", FeedbackForm.device("Google", "Pixel 8", "15"))
        assertEquals("samsung SM-S911B, Android 14", FeedbackForm.device("samsung", "SM-S911B", "14"))
        assertEquals("Google Pixel 8, Android 15", FeedbackForm.device("Google", "Google Pixel 8", "15"))
    }
}
