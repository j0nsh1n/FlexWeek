package com.flexweek.app.model

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

data class HomeworkDraft(
    val title: String = "",
    val due: String = "",
    // 0 until the student picks a length; Save stays off until then.
    val estimateMin: Int = 0,
    // "Other" is chosen: the length comes from the minutes field instead of a chip.
    val otherLength: Boolean = false,
    val sessions: String = "one",
) {
    /** Save needs a title, a due day and a length. */
    val canSave: Boolean get() = title.trim().isNotEmpty() && due.isNotBlank() && estimateMin > 0
}

data class PlanRecordLine(
    val title: String,
    val detail: String,
    val right: String,
    val why: String? = null,
)

data class PlanRecordState(
    val previewId: String,
    val summary: String,
    val lines: List<PlanRecordLine>,
)

data class RunningLateMove(
    val title: String,
    val detail: String,
    val why: String,
    val durationMin: Int,
)

data class RunningLateCurrent(val title: String, val end: String)

data class RunningLatePreview(
    val previewId: String,
    val minutes: Int,
    val moves: List<RunningLateMove>,
    val current: RunningLateCurrent,
    val stays: List<String>,
    val warning: String?,
)

data class WeekBar(
    val category: String,
    val topFraction: Float,
    val heightFraction: Float,
    val isNew: Boolean,
)

data class WeekDayShape(
    val dayIndex: Int,
    val isToday: Boolean,
    val bars: List<WeekBar>,
)

data class WeekUiState(
    val title: String,
    val days: List<WeekDayShape>,
)

/** One line of a day in the Week list. `start` is minutes after midnight, or null for a "due" line with no time. */
data class WeekSession(val start: Int?, val minutes: Int, val title: String, val category: String, val done: Boolean)

data class WeekDayWords(
    val dayIndex: Int,
    val date: Int,
    val names: List<String>,
    val sessions: List<WeekSession>,
    val fullDate: LocalDate,
    val minutes: Int,
    val heavy: Boolean,
    val unplaced: List<String>,
    val lastClassEnd: Int?,
)

data class WeekRowsState(
    val title: String,
    val homeworkTotal: String,
    val days: List<WeekDayWords>,
    val weekStart: LocalDate? = null,
)

object WeekRows {
    private const val HEAVY_THRESHOLD_MINUTES = 180
    fun isHeavy(minutes: Int): Boolean = minutes > HEAVY_THRESHOLD_MINUTES
}

/** A Week row's right-hand words, as picture 5 B writes them. */
object WeekRowWords {
    private const val MINUTES_PER_HOUR = 60
    private const val HOURS_PER_DAY = 24
    private const val HOURS_PER_HALF_DAY = 12

    fun right(minutes: Int, heavy: Boolean, lastClassEnd: Int?): String = when {
        minutes > 0 -> duration(minutes) + if (heavy) " · heavy" else ""
        lastClassEnd != null -> "free after ${clock(lastClassEnd)}"
        else -> "free"
    }

    /** "3 h of homework planned · 1 h done": time still planned, then finished time apart from it. */
    fun summary(planned: Int, done: Int): String = when {
        planned == 0 && done == 0 -> "No homework planned"
        done == 0 -> "${duration(planned)} of homework planned"
        planned == 0 -> "All homework done · ${duration(done)}"
        else -> "${duration(planned)} of homework planned · ${duration(done)} done"
    }

    /** What a day's heading says on its right: the homework time, or when school lets out on a day with none. */
    fun dayTotal(minutes: Int, heavy: Boolean, lastClassEnd: Int?): String = when {
        minutes > 0 -> duration(minutes) + if (heavy) " · heavy" else ""
        lastClassEnd != null -> "free after ${clock(lastClassEnd)}"
        else -> ""
    }

    fun duration(minutes: Int): String {
        val hours = minutes / MINUTES_PER_HOUR
        val rest = minutes % MINUTES_PER_HOUR
        return when {
            hours == 0 -> "$rest min"
            rest == 0 -> "$hours h"
            else -> "$hours h $rest"
        }
    }

    /** 12-hour without AM/PM, minutes only when not zero: "2:30", "3". */
    private fun clock(minutes: Int): String {
        val hour24 = minutes / MINUTES_PER_HOUR % HOURS_PER_DAY
        val minute = minutes % MINUTES_PER_HOUR
        val hour12 = if (hour24 % HOURS_PER_HALF_DAY == 0) HOURS_PER_HALF_DAY else hour24 % HOURS_PER_HALF_DAY
        return if (minute == 0) hour12.toString() else "$hour12:${minute.toString().padStart(2, '0')}"
    }
}

object WeekTitle {
    private const val DAYS_IN_WEEK_SPAN = 6L

    fun format(weekStart: LocalDate): String {
        val end = weekStart.plusDays(DAYS_IN_WEEK_SPAN)
        val day = DateTimeFormatter.ofPattern("d", Locale.ENGLISH)
        val month = DateTimeFormatter.ofPattern("MMM", Locale.ENGLISH)
        return when {
            weekStart.year != end.year -> "${weekStart.format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))} – ${end.format(DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH))}"
            weekStart.month == end.month -> "${weekStart.format(day)} – ${end.format(day)} ${end.format(month)}"
            else -> "${weekStart.format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))} – ${end.format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))}"
        }
    }
}

object V2Json {
    fun parseWeekRows(json: String): WeekRowsState {
        val root = JSONObject(json)
        val daysArr = root.getJSONArray("days")
        val days = buildList {
            for (i in 0 until daysArr.length()) {
                val row = daysArr.getJSONObject(i)
                add(WeekDayWords(
                    dayIndex = row.getInt("day"),
                    date = LocalDate.parse(row.getString("date")).dayOfMonth,
                    fullDate = LocalDate.parse(row.getString("date")),
                    sessions = (row.optJSONArray("sessions") ?: JSONArray()).let { list ->
                        (0 until list.length()).map { j ->
                            val item = list.getJSONObject(j)
                            WeekSession(
                                start = if (item.isNull("start")) null else item.getInt("start"),
                                minutes = item.getInt("minutes"),
                                title = item.getString("title"),
                                category = item.getString("category"),
                                done = item.optBoolean("done", false),
                            )
                        }
                    },
                    names = row.getJSONArray("names").let { list -> (0 until list.length()).map(list::getString) },
                    minutes = row.getInt("minutes"),
                    // The engine's own answer: it counts only time still planned, and a second rule here drifted from it.
                    heavy = if (row.has("heavy")) row.getBoolean("heavy") else WeekRows.isHeavy(row.getInt("minutes")),
                    unplaced = row.getJSONArray("unplaced").let { list -> (0 until list.length()).map(list::getString) },
                    lastClassEnd = if (row.isNull("last_class_end")) null else row.getInt("last_class_end"),
                ))
            }
        }
        val planned = days.sumOf { it.minutes }
        val done = days.sumOf { day -> day.sessions.filter { it.done && it.start != null }.sumOf { it.minutes } }
        val start = LocalDate.parse(root.getString("week_start"))
        return WeekRowsState(WeekTitle.format(start), WeekRowWords.summary(planned, done), days, start)
    }

    fun parsePlanRecord(json: String): PlanRecordState {
        val root = JSONObject(json)
        val linesArr = root.getJSONArray("lines")
        val lines = buildList {
            for (i in 0 until linesArr.length()) {
                val line = linesArr.getJSONObject(i)
                add(
                    PlanRecordLine(
                        title = line.getString("title"),
                        detail = line.optString("detail", ""),
                        right = line.getString("right"),
                        why = line.optString("why", null),
                    ),
                )
            }
        }
        return PlanRecordState(
            previewId = root.getString("preview_id"),
            summary = root.getString("summary"),
            lines = lines,
        )
    }

    fun parseRunningLate(json: String): RunningLatePreview {
        val root = JSONObject(json)
        val movesArr = root.getJSONArray("moves")
        val moves = buildList {
            for (i in 0 until movesArr.length()) {
                val m = movesArr.getJSONObject(i)
                add(
                    RunningLateMove(
                        title = m.getString("title"),
                        detail = m.getString("detail"),
                        why = m.getString("why"),
                        durationMin = m.getInt("duration_min"),
                    ),
                )
            }
        }
        return RunningLatePreview(
            previewId = root.getString("preview_id"),
            minutes = root.getInt("minutes"),
            moves = moves,
            current = root.getJSONObject("current").let { RunningLateCurrent(it.getString("title"), it.getString("end")) },
            stays = root.getJSONArray("stays").let { values -> buildList { for (i in 0 until values.length()) add(values.getJSONObject(i).getString("title")) } },
            warning = if (root.isNull("warning")) null else root.optString("warning").takeIf { it.isNotBlank() },
        )
    }

    fun parseWeekShape(json: String): WeekUiState {
        val root = JSONObject(json)
        val daysArr = root.getJSONArray("days")
        val days = buildList {
            for (i in 0 until daysArr.length()) {
                val d = daysArr.getJSONObject(i)
                val barsArr = d.getJSONArray("bars")
                val bars = buildList {
                    for (j in 0 until barsArr.length()) {
                        val b = barsArr.getJSONObject(j)
                        add(
                            WeekBar(
                                category = b.getString("category"),
                                topFraction = b.getDouble("top").toFloat(),
                                heightFraction = b.getDouble("height").toFloat(),
                                isNew = b.optBoolean("is_new", false),
                            ),
                        )
                    }
                }
                add(
                    WeekDayShape(
                        dayIndex = d.getInt("index"),
                        isToday = d.getBoolean("is_today"),
                        bars = bars,
                    ),
                )
            }
        }
        return WeekUiState(title = root.getString("title"), days = days)
    }

    fun homeworkDraftJson(draft: HomeworkDraft): String =
        JSONObject()
            .put("title", draft.title)
            .put("due", draft.due)
            .put("estimate_min", draft.estimateMin)
            .put("sessions", draft.sessions)
            .toString()
}

/** What the form says about the time: Save leaves the homework in "No time yet" until Plan gives it one. */
object AddHomeworkWords {
    const val TIME_NOTE = "Save puts it in No time yet. Plan gives it a time."
    const val NEEDS_TITLE = "Give the homework a title."
    val LENGTHS: List<Pair<String, Int>> =
        listOf("15 min" to 15, "30 min" to 30, "45 min" to 45, "1 h" to 60, "1 h 30" to 90, "2 h" to 120)
    const val OTHER = "Other"
}

data class DueChip(val label: String, val date: LocalDate)

object DueChips {
    fun label(date: LocalDate, today: LocalDate): String =
        if (date == today.plusDays(1)) "Tomorrow" else date.format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH))

    fun forToday(today: LocalDate): List<DueChip> {
        val tomorrow = today.plusDays(1)
        val friday = today.with(java.time.temporal.TemporalAdjusters.next(java.time.DayOfWeek.FRIDAY))
        val monday = today.with(java.time.temporal.TemporalAdjusters.next(java.time.DayOfWeek.MONDAY))
        // On a Thursday tomorrow is the next Friday, on a Sunday the next Monday: one chip per day.
        return listOf(tomorrow, friday, monday).distinct().map { DueChip(label(it, today), it) }
    }
}

object DueDate {
    const val PAST_DAY = "That day has passed. Choose today or a later day."

    /** The day's end, or null for a day already gone (a sheet left open past midnight). */
    fun toDueText(choice: LocalDate, today: LocalDate): String? =
        if (choice.isBefore(today)) null else "${choice}T23:59"
}

/** The Week list: each day with something in it is a heading and its sessions; free days run into one line. */
sealed class WeekEntry {
    data class Day(val label: String, val total: String, val dayIndex: Int, val sessions: List<WeekSession>) : WeekEntry()
    data class Free(val label: String) : WeekEntry()
}

object WeekList {
    private val LABELS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    private fun short(day: WeekDayWords) = "${LABELS[day.dayIndex]} ${day.date}"

    fun build(days: List<WeekDayWords>, today: LocalDate): List<WeekEntry> {
        val entries = mutableListOf<WeekEntry>()
        var free = mutableListOf<WeekDayWords>()
        fun flush() {
            if (free.isEmpty()) return
            val label = when (free.size) {
                1 -> short(free[0])
                2 -> "${short(free[0])} · ${short(free[1])}"
                else -> "${short(free.first())} – ${short(free.last())}"
            }
            entries += WeekEntry.Free(label)
            free = mutableListOf()
        }
        for (day in days) {
            if (day.sessions.isEmpty()) {
                free += day
                continue
            }
            flush()
            val label = short(day) + if (day.fullDate == today) " · today" else ""
            entries += WeekEntry.Day(label, WeekRowWords.dayTotal(day.minutes, day.heavy, day.lastClassEnd), day.dayIndex, day.sessions)
        }
        flush()
        return entries
    }
}
