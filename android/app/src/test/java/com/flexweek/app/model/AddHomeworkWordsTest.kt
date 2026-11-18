package com.flexweek.app.model

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AddHomeworkWordsTest {
    @Test fun neitherLinePromisesATimeThatSaveDoesNotGive() {
        listOf(AddHomeworkWords.TIME_NOTE, AddHomeworkWords.dueCrumb("Fri 20 Nov")).forEach {
            assertFalse("Save does not place the homework: $it", it.contains("picks the time"))
        }
        assertTrue(AddHomeworkWords.TIME_NOTE.contains("Plan"))
    }
}
