package com.flexweek.app.ui.focus

import com.flexweek.app.model.FocusJson
import com.flexweek.app.model.FocusSheetText
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusSheetTest {
    @Test fun replaceSheetWordsMatchTheDesktop() {
        assertEquals("Stop the timer for History essay and start Bio reading instead?", FocusJson.replaceText("History essay", "Bio reading"))
        assertEquals("Replace timer", FocusSheetText.replaceTitle)
    }

    @Test fun keepIsTheDefaultAnswer() {
        assertEquals("Keep current timer", FocusSheetText.keepCurrent)
    }

    @Test fun finishSheetSaysMinutesAndKeepGoingIsTheDefault() {
        assertEquals("You have done 7 min of History essay.", FocusJson.finishText(7, "History essay"))
        assertEquals("End this session?", FocusSheetText.finishTitle)
        assertEquals("Keep going", FocusSheetText.keepGoing)
    }
}
