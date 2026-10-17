package com.flexweek.app.model

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

data class HomeworkDraft(
    val title: String = "",
    val due: String = "",
    val whenMode: String = "pick",
    val estimateMin: Int = 60,
    val sessions: String = "one",
    val step: Int = 0,
    val tried: Boolean = false,
)

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
)

data class RunningLatePreview(
    val previewId: String,
    val minutes: Int,
    val moves: List<RunningLateMove>,
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

data class WeekDayWords(
    val dayIndex: Int,
    val date: Int,
    val names: List<String>,
    val minutes: Int,
    val heavy: Boolean,
    val unplaced: List<String>,
    val lastClassEnd: Int?,
)

data class WeekRowsState(val title: String, val homeworkTotal: String, val days: List<WeekDayWords>)

object WeekRows {
    private const val HEAVY_THRESHOLD_MINUTES = 180
    fun isHeavy(minutes: Int): Boolean = minutes > HEAVY_THRESHOLD_MINUTES
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
                    names = row.getJSONArray("names").let { list -> (0 until list.length()).map(list::getString) },
                    minutes = row.getInt("minutes"),
                    heavy = WeekRows.isHeavy(row.getInt("minutes")),
                    unplaced = row.getJSONArray("unplaced").let { list -> (0 until list.length()).map(list::getString) },
                    lastClassEnd = if (row.isNull("last_class_end")) null else row.getInt("last_class_end"),
                ))
            }
        }
        val total = days.sumOf { it.minutes }
        val hours = total / 60
        val rest = total % 60
        val length = when {
            hours == 0 -> "$rest min"
            rest == 0 -> "$hours h"
            else -> "$hours h $rest min"
        }
        return WeekRowsState(
            WeekTitle.format(LocalDate.parse(root.getString("week_start"))),
            "$length of homework",
            days,
        )
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
                    ),
                )
            }
        }
        return RunningLatePreview(
            previewId = root.getString("preview_id"),
            minutes = root.getInt("minutes"),
            moves = moves,
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

data class DueChip(val label: String, val date: LocalDate)

object DueChips {
    fun label(date: LocalDate, today: LocalDate): String =
        if (date == today.plusDays(1)) "Tomorrow" else date.format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH))

    fun forToday(today: LocalDate): List<DueChip> {
        val tomorrow = today.plusDays(1)
        val friday = today.with(java.time.temporal.TemporalAdjusters.next(java.time.DayOfWeek.FRIDAY))
        val monday = today.with(java.time.temporal.TemporalAdjusters.next(java.time.DayOfWeek.MONDAY))
        // On a Thursday tomorrow is the next Friday, on a Sunday the next Monday: one chip per day.
        return listOf(tomorrow, friday, monday).distinct().map { DueChip(label(it, today), it) } +
            DueChip("Pick a day", monday)
    }
}

object DueDate {
    const val PAST_DAY = "That day has passed. Choose today or a later day."

    /** The day's end, or null for a day already gone (a sheet left open past midnight). */
    fun toDueText(choice: LocalDate, today: LocalDate): String? =
        if (choice.isBefore(today)) null else "${choice}T23:59"
}
