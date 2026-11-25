package com.flexweek.app.ui.pair

import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation

/**
 * Shows the pairing code as "1234 5678" while the field holds only the digits, so the cursor never sits on
 * either side of a space it did not type.
 */
object PairCodeGrouping : VisualTransformation {
    private const val GROUP = 4

    override fun filter(text: AnnotatedString): TransformedText {
        val digits = text.text
        val shown = if (digits.length <= GROUP) digits else digits.substring(0, GROUP) + " " + digits.substring(GROUP)
        return TransformedText(AnnotatedString(shown), Mapping(digits.length))
    }

    /** Where each place in the digits is in the shown text, and back. */
    class Mapping(private val length: Int) : OffsetMapping {
        override fun originalToTransformed(offset: Int): Int =
            if (offset <= GROUP || length <= GROUP) offset else offset + 1

        override fun transformedToOriginal(offset: Int): Int =
            if (offset <= GROUP || length <= GROUP) offset else (offset - 1).coerceAtMost(length)
    }
}
