package com.flexweek.app.core

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalTime
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

internal object RustPhoneJson {
    private val timeFormat = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)
    private val dayFormat = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)

    // The engine's "24:00" (a block that ends at midnight) is not an ISO time, so read hour and minute by hand.
    fun time(value: String): String {
        val (hour, minute) = value.split(":").map(String::toInt)
        return LocalTime.of(hour % 24, minute).format(timeFormat)
    }

    fun length(minutes: Long): String {
        if (minutes < 60) return "$minutes min"
        val hours = minutes / 60
        val rest = minutes % 60
        return if (rest == 0L) "$hours h" else "$hours h $rest min"
    }

    fun reminderBody(start: String, duration: Long?): String =
        time(start) + if (duration == null) "" else " · ${length(duration)}"

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
            row.put("past", selected == current && row.getBoolean("past"))
            val range = "${time(row.getString("start"))}–${time(row.getString("end"))}"
            val detail = "$range · ${length(row.getLong("duration_min"))}"
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
            item.put("length_label", length(item.getLong("minutes")))
            item.put("due_label", if (item.isNull("due")) "" else LocalDate.parse(item.getString("due").take(10))
                .format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH)))
        }
        // Dates, not weekday numbers: last Wednesday is not today even when today is a Wednesday.
        root.put("selected_is_today", selected == current)
        root.put("selected_day", selected.dayOfWeek.value - 1)
        root.put("today_index", current.dayOfWeek.value - 1)
        root.put("day_title", if (selected == current) "Today" else selected.dayOfWeek.getDisplayName(java.time.format.TextStyle.FULL, Locale.ENGLISH))
        root.put("day_subtitle", selected.format(dayFormat))
        root.put("no_time", noTime)
        root.put("sync", JSONObject(sync))
        return root.toString()
    }

    fun sync(raw: String, zone: ZoneId = ZoneId.systemDefault(), errorKind: String? = null): String {
        if (!raw.startsWith("{")) return JSONObject().put("paired", false)
            .put("state", "unreachable").put("line", "No computer linked. Your week is saved here.").toString()
        val root = JSONObject(raw)
        if (root.optString("state") == "unreachable" && root.optBoolean("paired") && !root.isNull("last_sync_ms")) {
            val at = Instant.ofEpochMilli(root.getLong("last_sync_ms")).atZone(zone).format(timeFormat)
            root.put("line", "Your computer isn't reachable. Showing what synced at $at.")
        }
        // A failure that is not "the computer is off" says what it is, so the student does not wait for a computer
        // that is already on.
        if (root.optString("state") == "unreachable" && root.optBoolean("paired") && errorKind != null && !SyncWords.isOff(errorKind)) {
            root.put("line", if (SyncWords.needsUpdate(errorKind)) SyncWords.NEEDS_UPDATE else SyncWords.OTHER)
        }
        return root.toString()
    }

    /**
     * Settings' view of the computer, built from the same sync answer as the top line so the two cannot
     * disagree: "paired" is the answer's own flag, not a guess from the name or the date.
     */
    fun phoneSettings(settingsRaw: String, syncRaw: String, exactReminders: Boolean, zone: ZoneId = ZoneId.systemDefault()): String {
        val settings = JSONObject(settingsRaw)
        val sync = JSONObject(syncRaw)
        val lastSync = if (sync.isNull("last_sync_ms") || !sync.has("last_sync_ms")) ""
        else Instant.ofEpochMilli(sync.getLong("last_sync_ms")).atZone(zone).format(timeFormat)
        return settings.put("lead_minutes", settings.getInt("reminder_lead_min"))
            .put("exact_reminders", exactReminders)
            .put("device_name", sync.optString("peer_name", "Your computer"))
            .put("paired_at", pairedDate(sync.optString("paired_at", ""), zone))
            .put("paired", sync.optBoolean("paired"))
            .put("last_sync", lastSync)
            .put("reachable", sync.optString("state") != "unreachable").toString()
    }

    fun pairedDate(raw: String, zone: ZoneId = ZoneId.systemDefault()): String {
        val milliseconds = raw.toLongOrNull() ?: return ""
        return Instant.ofEpochMilli(milliseconds).atZone(zone)
            .format(DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH))
    }

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

    const val NOTHING_TO_PLAN = "Nothing is waiting for a time right now."

    /** The engine's own sentence from a refused call; its exception text is "details=...". */
    fun ffiText(error: com.flexweek.app.bindings.FfiException): String =
        (error as? com.flexweek.app.bindings.FfiException.Failure)?.details ?: error.message ?: UNREADABLE_ERROR

    private const val UNREADABLE_ERROR = "FlexWeek could not finish that. Nothing was changed."

    fun plan(raw: String): String {
        val root = JSONObject(raw)
        // With nothing to place (or a week that is over) the engine saves no preview and says why in "message".
        if (root.optString("applied_preview").isBlank()) {
            return JSONObject().put("ok", false)
                .put("error", root.optString("message").ifBlank { NOTHING_TO_PLAN }).toString()
        }
        val placed = root.getJSONArray("placed")
        val waiting = root.getJSONArray("not_placed")
        val lines = JSONArray()
        for (i in 0 until placed.length()) {
            val block = placed.getJSONObject(i)
            val day = block.getJSONArray("days").getInt(0)
            lines.put(JSONObject().put("title", block.getString("title"))
                // The time is on the right already; saying it again here (as "16:00") showed it twice.
                .put("detail", length(block.optLong("duration_min")))
                .put("right", TimeLabel.dayAndTime(day, block.getString("start"))))
        }
        for (i in 0 until waiting.length()) {
            val block = waiting.getJSONObject(i)
            lines.put(JSONObject().put("title", block.getString("title"))
                .put("right", "No time yet").put("why", block.optString("why").ifBlank { null }))
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
            // "from 4 PM to 4:30 PM": the engine's detail only said where it moved from.
            if (move.optString("from_start").isNotBlank() && move.optString("to_start").isNotBlank()) {
                move.put("detail", TimeLabel.lateDetail(
                    if (move.isNull("from_day")) null else move.getInt("from_day"), move.getString("from_start"),
                    if (move.isNull("to_day")) null else move.getInt("to_day"), move.getString("to_start"),
                ))
            }
        }
        return root.put("ok", true).put("preview_id", root.getString("applied_preview"))
            .put("minutes", minutes).toString()
    }
}
