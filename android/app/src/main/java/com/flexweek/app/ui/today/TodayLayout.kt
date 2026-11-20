package com.flexweek.app.ui.today

import com.flexweek.app.model.AgendaRow

/** Today's agenda cut into the groups the screen shows, in the order the engine sent them. */
data class TodayGroups(
    val earlier: List<AgendaRow.Item>,
    val upNext: AgendaRow.Now?,
    val later: List<AgendaRow.Item>,
    val notes: List<AgendaRow>,
) {
    companion object {
        /** Items before the Up next row are Earlier; items after it (or any not-yet-past item) are Later today. */
        fun of(rows: List<AgendaRow>): TodayGroups {
            val earlier = mutableListOf<AgendaRow.Item>()
            val later = mutableListOf<AgendaRow.Item>()
            val notes = mutableListOf<AgendaRow>()
            var upNext: AgendaRow.Now? = null
            for (row in rows) {
                when (row) {
                    is AgendaRow.Now -> if (upNext == null) upNext = row
                    is AgendaRow.Item -> if (upNext == null && row.past) earlier += row else later += row
                    else -> notes += row
                }
            }
            return TodayGroups(earlier, upNext, later, notes)
        }
    }
}

/** "4:30 PM" is drawn as two short lines in the time column; a label with no space stays on one line. */
object TimeColumn {
    fun split(label: String): Pair<String, String?> {
        val i = label.indexOf(' ')
        return if (i < 0) label to null else label.substring(0, i) to label.substring(i + 1)
    }
}

/**
 * How the Up next card lays out its buttons. Two equal buttons side by side only when the longest label
 * fits in its half with room to spare at the phone's text size; otherwise they stack full width, so no
 * label is ever cut or wrapped mid-word.
 */
data class UpNextLayout(val startFocus: Boolean, val done: Boolean, val late: Boolean, val stacked: Boolean) {
    companion object {
        private const val LABEL_SP = 14f
        // Medium-weight sans averages about half an em per glyph; icon and padding are added on top.
        private const val GLYPH_EM = 0.5f
        private const val BUTTON_PADDING_DP = 12f * 2
        private const val ICON_DP = 18f + 8f
        private const val GAP_DP = 8f

        fun labelWidthDp(label: String, fontScale: Float): Float =
            label.length * GLYPH_EM * LABEL_SP * fontScale + BUTTON_PADDING_DP + ICON_DP

        /** `cardInnerWidthDp` is the width the buttons share: the screen minus the page and card padding. */
        fun of(actions: NowRowActions, cardInnerWidthDp: Float, fontScale: Float): UpNextLayout {
            val pair = actions.finishHomework && actions.runningLate
            val half = (cardInnerWidthDp - GAP_DP) / 2f
            val fits = labelWidthDp(RUNNING_LATE, fontScale) <= half && labelWidthDp(DONE, fontScale) <= half
            return UpNextLayout(actions.startFocus, actions.finishHomework, actions.runningLate, stacked = pair && !fits)
        }

        const val START_FOCUS = "Start focus"
        const val DONE = "Done"
        const val RUNNING_LATE = "Running late"
    }
}
