package com.flexweek.app.model

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AddHomeworkWordsTest {
    @Test fun neitherLinePromisesATimeThatSaveDoesNotGive() {
        assertFalse("Save does not place the homework", AddHomeworkWords.TIME_NOTE.contains("picks the time"))
        assertTrue(AddHomeworkWords.TIME_NOTE.contains("Plan"))
    }
}
