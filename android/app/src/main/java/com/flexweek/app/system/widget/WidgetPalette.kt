package com.flexweek.app.system.widget

import com.flexweek.app.ui.theme.CategoryKind
import com.flexweek.app.ui.theme.categoryKind

// The theme's colours (FlexWeekTheme.categoryColor) as plain ints, because RemoteViews cannot use Compose.
// WidgetPaletteTest checks each value is still in the theme file.
object WidgetPalette {
    private const val ACCENT_LIGHT = 0xFF4A6FB5.toInt()
    private const val ACCENT_DARK = 0xFF9DB8F0.toInt()
    private const val OK_LIGHT = 0xFF2F7D55.toInt()
    private const val OK_DARK = 0xFF7FCF9F.toInt()
    private const val HOMEWORK_LIGHT = 0xFF9A6A12.toInt()
    private const val HOMEWORK_DARK = 0xFFE3B65A.toInt()
    private const val OUTLINE_LIGHT = 0xFF74777F.toInt()
    private const val OUTLINE_DARK = 0xFF8E9099.toInt()

    // The real core names homework's category "homework"; the demo core says "hw". Both are amber.
    fun categoryArgb(category: String, dark: Boolean): Int = when (categoryKind(category)) {
        CategoryKind.School -> if (dark) ACCENT_DARK else ACCENT_LIGHT
        CategoryKind.Sports -> if (dark) OK_DARK else OK_LIGHT
        CategoryKind.Homework -> if (dark) HOMEWORK_DARK else HOMEWORK_LIGHT
        null -> if (dark) OUTLINE_DARK else OUTLINE_LIGHT
    }
}
