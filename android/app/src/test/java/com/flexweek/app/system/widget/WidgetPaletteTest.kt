package com.flexweek.app.system.widget

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

// The widget is drawn outside Compose, so it cannot call categoryColor. The theme's private colours are the
// source: each hex below must still be in the theme file, so a changed palette fails here.
class WidgetPaletteTest {
    private val theme = File("src/main/java/com/flexweek/app/ui/theme/FlexWeekTheme.kt").readText()

    private fun inTheme(argb: Int) = "Color(0x${"%08X".format(argb)})" in theme

    @Test fun schoolSportsAndHomeworkUseTheThemesColours() {
        val expected = mapOf(
            "school" to (0xFF4A6FB5.toInt() to 0xFF9DB8F0.toInt()),
            "sports" to (0xFF2F7D55.toInt() to 0xFF7FCF9F.toInt()),
            "hw" to (0xFF9A6A12.toInt() to 0xFFE3B65A.toInt()),
        )
        assertTrue("there are colours to check", expected.isNotEmpty())
        for ((category, pair) in expected) {
            assertEquals("$category in light", pair.first, WidgetPalette.categoryArgb(category, dark = false))
            assertEquals("$category in dark", pair.second, WidgetPalette.categoryArgb(category, dark = true))
            assertTrue("$category light colour is in the theme", inTheme(pair.first))
            assertTrue("$category dark colour is in the theme", inTheme(pair.second))
        }
    }

    @Test fun everyCategoryNameTheAppColoursGreenIsGreenOnTheWidgetToo() {
        for (name in listOf("sports", "sport", "activity", "activities")) {
            assertEquals(name, 0xFF2F7D55.toInt(), WidgetPalette.categoryArgb(name, dark = false))
        }
    }

    @Test fun theRealCoresHomeworkCategoryGetsTheHomeworkColour() {
        assertEquals(WidgetPalette.categoryArgb("hw", dark = false), WidgetPalette.categoryArgb("homework", dark = false))
    }

    @Test fun anyOtherCategoryGetsTheThemesOutlineColour() {
        assertEquals(0xFF74777F.toInt(), WidgetPalette.categoryArgb("study", dark = false))
        assertEquals(0xFF8E9099.toInt(), WidgetPalette.categoryArgb("study", dark = true))
        assertTrue(inTheme(0xFF74777F.toInt()))
        assertTrue(inTheme(0xFF8E9099.toInt()))
    }
}
