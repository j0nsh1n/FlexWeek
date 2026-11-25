package com.flexweek.app.ui.pair

import androidx.compose.ui.text.AnnotatedString
import org.junit.Assert.assertEquals
import org.junit.Test

class PairCodeGroupingTest {
    private fun shown(digits: String) = PairCodeGrouping.filter(AnnotatedString(digits))

    @Test
    fun theCodeShowsInTwoGroupsOfFour() {
        assertEquals("1234", shown("1234").text.text)
        assertEquals("1234 5", shown("12345").text.text)
        assertEquals("1234 5678", shown("12345678").text.text)
    }

    @Test
    fun theCursorAfterTheFifthDigitIsPastTheSpace() {
        val mapping = shown("12345").offsetMapping
        assertEquals(4, mapping.originalToTransformed(4))
        assertEquals(6, mapping.originalToTransformed(5))
        // A tap just after the space puts the cursor before the fifth digit, never inside the code's text.
        assertEquals(4, mapping.transformedToOriginal(5))
        assertEquals(5, mapping.transformedToOriginal(6))
    }

    @Test
    fun aShortCodeHasNoSpaceToMapAround() {
        val mapping = shown("123").offsetMapping
        for (offset in 0..3) {
            assertEquals(offset, mapping.originalToTransformed(offset))
            assertEquals(offset, mapping.transformedToOriginal(offset))
        }
    }
}
