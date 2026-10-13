package com.flexweek.app.core

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.atomic.AtomicReference

class FakeFlexWeekCore : FlexWeekCore {
    private var paired = false
    private var selectedDay = DemoSchedule.TODAY_INDEX
    private val doneIds = mutableSetOf<String>()
    private val blocks = DemoSchedule.defaultBlocks().toMutableList()
    private val noTime = DemoSchedule.defaultNoTime.toMutableList()
    private var leadMinutes = 10
    private var exactReminders = false
    private val syncState = AtomicReference(SyncState.SYNCED)
    private var lastSyncLabel = "Synced 2 min ago"
    private var lastSyncAt = "3:12 PM"

    init {
        blocks.filter { it.initiallyDone }.forEach { doneIds += it.id }
    }

    override fun engineVersion(): String = "flexweek-demo-fake/1.0.0"

    override fun open(dbPath: String, deviceName: String) {
        // Demo data is in-memory only.
    }

    override fun today(date: String, nowMinute: Int): String {
        val day = selectedDay
        val items = blocks.filter { it.dayIndex == day }.sortedBy { it.startMinute }
        val rows = JSONArray()
        if (items.isEmpty()) {
            rows.put(jsonObject { put("type", "empty") })
        } else if (day == DemoSchedule.TODAY_INDEX && date == isoForDay(day)) {
            val queue = items.filter { !isDone(it) && it.startMinute + it.lengthMinutes > nowMinute }
            val current = queue.firstOrNull { it.startMinute <= nowMinute }
            val highlight = current ?: queue.firstOrNull()
            val highlightId = highlight?.id
            for (block in items) {
                if (block.id == highlightId && highlight != null) {
                    rows.put(buildNowRow(highlight, current != null, nowMinute, queue.getOrNull(1)))
                } else {
                    rows.put(buildItemRow(block, past = block.startMinute + block.lengthMinutes <= nowMinute))
                }
            }
            if (highlight == null) {
                rows.put(
                    jsonObject {
                        put("type", "nothing_left")
                        put("free_until", DemoSchedule.formatTime(22 * 60))
                    },
                )
            }
        } else {
            for (block in items) {
                rows.put(buildItemRow(block, past = false))
            }
        }
        val days = JSONArray()
        DemoSchedule.dayLabels.forEachIndexed { i, label ->
            days.put(
                jsonObject {
                    put("index", i)
                    put("label", label)
                    put("date", DemoSchedule.dayDates[i])
                    put("is_today", i == DemoSchedule.TODAY_INDEX)
                    put("selected", i == day)
                    put("has_dot", noTime.any { it.dueDayIndex == i })
                },
            )
        }
        val noTimeArr = JSONArray()
        noTime.forEach { chip ->
            noTimeArr.put(
                jsonObject {
                    put("id", chip.id)
                    put("title", chip.title)
                    put("length_label", DemoSchedule.formatLength(chip.lengthMinutes))
                    put(
                        "due_label",
                        "${DemoSchedule.dayLabels[chip.dueDayIndex]} ${DemoSchedule.dayDates[chip.dueDayIndex]}",
                    )
                },
            )
        }
        return jsonString {
            put("week_start", DemoSchedule.WEEK_START)
            put("selected_day", day)
            put("today_index", DemoSchedule.TODAY_INDEX)
            put("now_minute", nowMinute)
            put("date", date)
            put("day_title", if (day == DemoSchedule.TODAY_INDEX) "Today" else DemoSchedule.dayFull[day])
            put("day_subtitle", "${DemoSchedule.dayFull[day]} ${DemoSchedule.dayDates[day]} October")
            put("days", days)
            put("rows", rows)
            put("no_time", noTimeArr)
            put("sync", JSONObject(syncStatus()))
        }
    }

    fun selectDay(index: Int) {
        selectedDay = index.coerceIn(0, 6)
    }

    override fun setBlockDone(
        weekStart: String,
        blockId: String,
        dayIndex: Int,
        done: Boolean,
        opId: String,
    ) {
        if (done) doneIds += blockId else doneIds -= blockId
    }

    override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
        if (done) doneIds += id else doneIds -= id
    }

    override fun upcomingReminders(fromLocal: String, hours: Int): String {
        val arr = JSONArray()
        arr.put(
            jsonObject {
                put("title", "History essay")
                put("starts_at", "7:00 PM")
                put("lead_minutes", leadMinutes)
            },
        )
        return arr.toString()
    }

    override fun settingsForPhone(): String =
        jsonString {
            put("lead_minutes", leadMinutes)
            put("exact_reminders", exactReminders)
            put("device_name", "Joo's laptop")
            put("paired_at", "8 Oct")
            put("reachable", syncState.get() != SyncState.UNREACHABLE)
        }

    override fun syncStatus(): String {
        return when (syncState.get()) {
            SyncState.SYNCED ->
                jsonString {
                    put("state", "synced")
                    put("line", lastSyncLabel)
                }
            SyncState.SYNCING ->
                jsonString {
                    put("state", "syncing")
                    put("line", "Syncing…")
                }
            SyncState.UNREACHABLE ->
                jsonString {
                    put("state", "unreachable")
                    put(
                        "line",
                        "Your computer isn't reachable. Showing what synced at $lastSyncAt.",
                    )
                }
        }
    }

    override fun syncOnce(deadlineMs: Long): String {
        syncState.set(SyncState.SYNCING)
        syncState.set(SyncState.SYNCED)
        lastSyncLabel = "Synced just now"
        return jsonString { put("ok", true) }
    }

    override fun pairWithCode(code: String): String {
        val digits = code.filter { it.isDigit() }
        if (digits.length != 8) {
            return jsonString {
                put("ok", false)
                put("error", "length")
            }
        }
        if (digits != DemoSchedule.VALID_PAIR_CODE) {
            return jsonString {
                put("ok", false)
                put("error", "mismatch")
            }
        }
        paired = true
        return jsonString { put("ok", true) }
    }

    override fun pairFromQr(text: String): String {
        val match = Regex("c=(\\d{8})").find(text)
        return if (match != null) {
            pairWithCode(match.groupValues[1])
        } else {
            jsonString {
                put("ok", false)
                put("error", "qr")
            }
        }
    }

    override fun cancelSync() {
        syncState.set(SyncState.SYNCED)
    }

    override fun unlink() {
        paired = false
    }

    override fun isPaired(): Boolean = paired

    fun setLeadMinutes(minutes: Int) {
        leadMinutes = minutes
    }

    fun setExactReminders(on: Boolean) {
        exactReminders = on
    }

    fun setSyncState(state: SyncState) {
        syncState.set(state)
    }

    private fun isDone(block: DemoSchedule.Block): Boolean = block.id in doneIds

    private fun buildItemRow(block: DemoSchedule.Block, past: Boolean): JSONObject {
        val done = isDone(block)
        return jsonObject {
            put("type", "item")
            put("id", block.id)
            put("title", block.title)
            put("category", block.category)
            put("time_label", DemoSchedule.formatTime(block.startMinute))
            put(
                "detail",
                "${DemoSchedule.formatRange(block.startMinute, block.lengthMinutes)} · " +
                    DemoSchedule.formatLength(block.lengthMinutes) +
                    if (done) " · finished" else "",
            )
            put("homework", block.homework)
            put("done", done)
            put("past", past)
        }
    }

    private fun buildNowRow(
        block: DemoSchedule.Block,
        isNow: Boolean,
        nowMinute: Int,
        next: DemoSchedule.Block?,
    ): JSONObject {
        val end = block.startMinute + block.lengthMinutes
        val minsLabel =
            if (isNow) {
                "${end - nowMinute} min left"
            } else {
                "in ${block.startMinute - nowMinute} min"
            }
        return jsonObject {
            put("type", "now")
            put("id", block.id)
            put("title", block.title)
            put("kick", if (isNow) "Now" else "Up next")
            put("mins_label", minsLabel)
            put(
                "when_line",
                "${DemoSchedule.formatRange(block.startMinute, block.lengthMinutes)} · " +
                    DemoSchedule.formatLength(block.lengthMinutes),
            )
            put("homework", block.homework)
            if (next != null) {
                put("then_title", next.title)
                put("then_time", DemoSchedule.formatTime(next.startMinute))
            }
        }
    }

    private fun isoForDay(dayIndex: Int): String {
        val day = DemoSchedule.dayDates[dayIndex]
        return "2025-10-${day.toString().padStart(2, '0')}"
    }
}

enum class SyncState {
    SYNCED,
    SYNCING,
    UNREACHABLE,
}

internal fun newOpId(): String = UUID.randomUUID().toString()
