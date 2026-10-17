package com.flexweek.app.system.widget

// The theme's colours (FlexWeekTheme.categoryColor) as plain ints, because RemoteViews cannot use Compose.
// WidgetPaletteTest checks each value is still in the theme file.
object WidgetPalette {
    private const val ACCENT_LIGHT = 0xFF3D6FC4.toInt()
    private const val ACCENT_DARK = 0xFF7FA8FF.toInt()
    private const val OK_LIGHT = 0xFF2F7D4A.toInt()
    private const val OK_DARK = 0xFF7ED39A.toInt()
    private const val ERROR_LIGHT = 0xFFB42318.toInt()
    private const val ERROR_DARK = 0xFFFF8A7A.toInt()
    private const val OUTLINE_LIGHT = 0xFFC3CCD9.toInt()
    private const val OUTLINE_DARK = 0xFF3A3F46.toInt()

    // The real core names homework's category "homework"; the demo core says "hw". Both are red.
    fun categoryArgb(category: String, dark: Boolean): Int = when (category) {
        "school" -> if (dark) ACCENT_DARK else ACCENT_LIGHT
        "sports" -> if (dark) OK_DARK else OK_LIGHT
        "hw", "homework" -> if (dark) ERROR_DARK else ERROR_LIGHT
        else -> if (dark) OUTLINE_DARK else OUTLINE_LIGHT
    }
}
