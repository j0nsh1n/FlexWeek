package com.flexweek.app.core

/**
 * Demo week from design-1.0.0/android.html (Mon 5 – Sun 11 Oct, today = Thu index 3 at 3:40 PM).
 */
internal object DemoSchedule {
    const val TODAY_INDEX = 3
    const val DEMO_NOW_MINUTE = 15 * 60 + 40
    const val WEEK_START = "2025-10-06"
    const val VALID_PAIR_CODE = "48127390"

    val dayLabels = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    val dayDates = listOf(5, 6, 7, 8, 9, 10, 11)
    val dayFull = listOf(
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    )

    data class Block(
        val id: String,
        val title: String,
        val category: String,
        val dayIndex: Int,
        val startMinute: Int,
        val lengthMinutes: Int,
        val homework: Boolean = false,
        val initiallyDone: Boolean = false,
    )

    data class NoTimeChip(
        val id: String,
        val title: String,
        val lengthMinutes: Int,
        val dueDayIndex: Int,
    )

    fun defaultBlocks(): List<Block> = listOf(
        *(0..4).map { d ->
            Block(
                id = "school$d",
                title = "School",
                category = "school",
                dayIndex = d,
                startMinute = 8 * 60,
                lengthMinutes = (6.5 * 60).toInt(),
            )
        }.toTypedArray(),
        Block("soccer1", "Soccer", "sports", 1, 16 * 60, 90),
        Block("soccer3", "Soccer", "sports", 3, 16 * 60, 90),
        Block("bio", "Bio reading", "hw", 2, 17 * 60, 60, homework = true, initiallyDone = true),
        Block("essay", "History essay", "hw", 3, 19 * 60, 60, homework = true),
    )

    val defaultNoTime = listOf(
        NoTimeChip("poster", "Science poster", 60, 4),
        NoTimeChip("math", "Math worksheet", 60, 6),
    )

    fun formatTime(minute: Int): String {
        val h = minute / 60
        val m = minute % 60
        val ap = if (h >= 12) "PM" else "AM"
        val h12 = ((h + 11) % 12) + 1
        return if (m == 0) "$h12\u00a0$ap" else "$h12:${m.toString().padStart(2, '0')}\u00a0$ap"
    }

    fun formatRange(startMinute: Int, lengthMinutes: Int): String {
        val end = startMinute + lengthMinutes
        val startLabel = formatTime(startMinute).substringBefore('\u00a0')
        return "$startLabel–${formatTime(end)}"
    }

    fun formatLength(minutes: Int): String {
        if (minutes >= 60) {
            val h = minutes / 60
            val rem = minutes % 60
            return if (rem == 0) "$h h" else "$h h $rem min"
        }
        return "$minutes min"
    }
}
