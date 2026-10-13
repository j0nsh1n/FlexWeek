package com.flexweek.app.core

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Locale

internal object RustPhoneJson {
    private val timeFormat = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)
    private val dayFormat = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)

    fun time(value: String): String = LocalTime.parse(value).format(timeFormat)

    fun today(raw: String, today: String, sync: String): String {
        val root = JSONObject(raw)
        val selected = LocalDate.parse(root.getString("date"))
        val current = LocalDate.parse(today)
        val now = root.optJSONObject("now")
        val days = root.getJSONArray("days")
        for (i in 0 until days.length()) {
            val chip = days.getJSONObject(i)
            val date = LocalDate.parse(chip.getString("date"))
            chip.put("index", chip.getInt("day"))
            chip.put("label", date.format(DateTimeFormatter.ofPattern("EEE", Locale.ENGLISH)))
            chip.put("date", date.dayOfMonth)
            chip.put("is_today", date == current)
            chip.put("selected", date == selected)
            chip.put("has_dot", chip.getInt("due_count") > 0)
        }
        val rows = root.getJSONArray("rows")
        val homeworkLeft = (0 until rows.length()).any {
            val row = rows.getJSONObject(it)
            row.getBoolean("homework") && !row.getBoolean("done") && !row.getBoolean("past")
        }
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val range = "${time(row.getString("start"))}–${time(row.getString("end"))}"
            val detail = "$range · ${row.getInt("duration_min")} min"
            val isNow = selected == current && row.getString("id") == now?.getString("block_id")
            row.put("type", if (isNow) "now" else "item")
            row.put("time_label", time(row.getString("start")))
            row.put("detail", detail + if (row.getBoolean("done")) " · finished" else "")
            if (isNow && now != null) {
                val running = now.getString("kind") == "now"
                row.put("kick", if (running) "Now" else "Up next")
                row.put("mins_label", if (running) "${now.getInt("minutes_left")} min left" else "in ${now.getInt("minutes_left")} min")
                row.put("when_line", detail)
                row.put("show_finish_focus", row.getBoolean("homework"))
                row.put("show_running_late", homeworkLeft)
                if (!now.isNull("then_title")) {
                    row.put("then_title", now.getString("then_title"))
                    row.put("then_time", time(now.getString("then_start")))
                }
            }
        }
        if (rows.length() == 0) rows.put(JSONObject().put("type", "empty"))
        else if (selected == current && root.getBoolean("nothing_left")) {
            rows.put(JSONObject().put("type", "nothing_left"))
        }
        val noTime = root.getJSONArray("no_time_yet")
        for (i in 0 until noTime.length()) {
            val item = noTime.getJSONObject(i)
            item.put("length_label", "${item.getInt("minutes")} min")
            item.put("due_label", if (item.isNull("due")) "" else LocalDate.parse(item.getString("due").take(10))
                .format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH)))
        }
        root.put("selected_day", selected.dayOfWeek.value - 1)
        root.put("today_index", current.dayOfWeek.value - 1)
        root.put("day_title", if (selected == current) "Today" else selected.dayOfWeek.getDisplayName(java.time.format.TextStyle.FULL, Locale.ENGLISH))
        root.put("day_subtitle", selected.format(dayFormat))
        root.put("no_time", noTime)
        root.put("sync", JSONObject(sync))
        return root.toString()
    }

    fun sync(raw: String): String = if (raw.startsWith("{")) raw else JSONObject()
        .put("paired", false).put("state", "unreachable").put("line", "No computer is linked yet.").toString()

    fun week(raw: String, today: String): String {
        val root = JSONObject(raw)
        val start = LocalDate.parse(root.getString("week_start"))
        val days = root.getJSONArray("days")
        for (i in 0 until days.length()) {
            val day = days.getJSONObject(i)
            val bars = JSONArray()
            val segments = day.getJSONArray("segments")
            for (j in 0 until segments.length()) {
                val segment = segments.getJSONObject(j)
                bars.put(JSONObject().put("category", segment.getString("category"))
                    .put("top", segment.getInt("start_min") / 1440.0)
                    .put("height", (segment.getInt("end_min") - segment.getInt("start_min")) / 1440.0))
            }
            day.put("index", day.getInt("day"))
            day.put("is_today", start.plusDays(i.toLong()).toString() == today)
            day.put("bars", bars)
        }
        root.put("title", "${start.format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))}–${start.plusDays(6).format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))}")
        return root.toString()
    }

    fun plan(raw: String): String {
        val root = JSONObject(raw)
        val placed = root.getJSONArray("placed")
        val waiting = root.getJSONArray("not_placed")
        val lines = JSONArray()
        for (i in 0 until placed.length()) {
            val block = placed.getJSONObject(i)
            lines.put(JSONObject().put("title", block.getString("title"))
                .put("detail", "${block.optString("start")} · ${block.optInt("duration_min")} min")
                .put("right", "Placed"))
        }
        for (i in 0 until waiting.length()) {
            val block = waiting.getJSONObject(i)
            lines.put(JSONObject().put("title", block.getString("title"))
                .put("right", "No time yet").put("why", block.optString("reason", "No free time.")))
        }
        return root.put("ok", true).put("preview_id", root.getString("applied_preview"))
            .put("summary", "Placed ${placed.length()} of ${placed.length() + waiting.length()}")
            .put("lines", lines).toString()
    }

    fun late(raw: String, minutes: Int): String {
        val root = JSONObject(raw)
        val moves = root.getJSONArray("moves")
        for (i in 0 until moves.length()) {
            val move = moves.getJSONObject(i)
            move.put("detail", move.optString("detail", "Time moved"))
            move.put("why", move.optString("why", "Running late"))
        }
        return root.put("ok", true).put("preview_id", root.getString("applied_preview"))
            .put("minutes", minutes).toString()
    }
}
