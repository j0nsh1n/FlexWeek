package com.flexweek.app.core

/** Times as the 1.1 phone screens say them: "7 PM", "3:30 PM", and "Thu 7 PM" when the day matters. */
object TimeLabel {
    private val DAYS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    fun short(hhmm: String): String {
        val (hour, minute) = hhmm.split(":").map(String::toInt)
        val half = if (hour < 12) "AM" else "PM"
        val clock = if (hour % 12 == 0) 12 else hour % 12
        return if (minute == 0) "$clock $half" else "$clock:${"%02d".format(minute)} $half"
    }

    fun lateDetail(fromDay: Int?, fromStart: String, toDay: Int?, toStart: String): String {
        if (fromDay == toDay) return "${short(fromStart)} → ${short(toStart)}"
        fun at(day: Int?, start: String) = if (day == null) short(start) else "${DAYS[day]} ${short(start)}"
        return "${at(fromDay, fromStart)} → ${at(toDay, toStart)}"
    }
}
