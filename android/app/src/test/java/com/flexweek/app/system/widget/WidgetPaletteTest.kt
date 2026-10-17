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
            "school" to (0xFF3D6FC4.toInt() to 0xFF7FA8FF.toInt()),
            "sports" to (0xFF2F7D4A.toInt() to 0xFF7ED39A.toInt()),
            "hw" to (0xFFB42318.toInt() to 0xFFFF8A7A.toInt()),
        )
        assertTrue("there are colours to check", expected.isNotEmpty())
        for ((category, pair) in expected) {
            assertEquals("$category in light", pair.first, WidgetPalette.categoryArgb(category, dark = false))
            assertEquals("$category in dark", pair.second, WidgetPalette.categoryArgb(category, dark = true))
            assertTrue("$category light colour is in the theme", inTheme(pair.first))
            assertTrue("$category dark colour is in the theme", inTheme(pair.second))
        }
    }

    @Test fun theRealCoresHomeworkCategoryGetsTheHomeworkColour() {
        assertEquals(WidgetPalette.categoryArgb("hw", dark = false), WidgetPalette.categoryArgb("homework", dark = false))
    }

    @Test fun anyOtherCategoryGetsTheThemesOutlineColour() {
        assertEquals(0xFFC3CCD9.toInt(), WidgetPalette.categoryArgb("study", dark = false))
        assertEquals(0xFF3A3F46.toInt(), WidgetPalette.categoryArgb("study", dark = true))
        assertTrue(inTheme(0xFFC3CCD9.toInt()))
        assertTrue(inTheme(0xFF3A3F46.toInt()))
    }
}
