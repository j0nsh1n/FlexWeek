package com.flexweek.app.system.widget

object WidgetSize {
    // A 4 x 2 cell grid is 70 dp per cell less 30 dp: 250 x 110. Kept equal to minWidth and minHeight in
    // up_next_widget_info.xml (a test checks), so the widget's smallest default size shows its rows.
    const val ROWS_MIN_WIDTH_DP = 250
    const val ROWS_MIN_HEIGHT_DP = 110

    /** Smaller than 4 x 2 shows the kicker, headline and time only; larger shows the same two rows. */
    fun rowsToShow(content: WidgetContent, widthDp: Int, heightDp: Int): List<WidgetRow> {
        if (widthDp < ROWS_MIN_WIDTH_DP || heightDp < ROWS_MIN_HEIGHT_DP) return emptyList()
        // The unreachable line takes the second row's place.
        return content.rows.take(if (content.note != null) 1 else WidgetWords.MAX_ROWS)
    }
}
