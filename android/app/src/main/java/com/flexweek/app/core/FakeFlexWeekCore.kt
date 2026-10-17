package com.flexweek.app.core

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID
import java.util.concurrent.atomic.AtomicReference

class FakeFlexWeekCore : FlexWeekCore {
    override fun currentDate(): String = "2025-10-08"
    override fun currentDayIndex(): Int = DemoSchedule.TODAY_INDEX
    override fun currentWeekStart(): String = DemoSchedule.WEEK_START
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

    override fun selectDay(index: Int) {
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
        val from = LocalDateTime.parse(fromLocal, DateTimeFormatter.ISO_LOCAL_DATE_TIME)
        val until = from.plusHours(hours.toLong())
        val arr = JSONArray()
        for (block in blocks) {
            if (!block.homework || isDone(block)) continue
            val fire = blockReminderFire(block)
            if (fire.isBefore(from) || !fire.isBefore(until)) continue
            val startLabel = DemoSchedule.formatTime(block.startMinute)
            arr.put(
                jsonObject {
                    put("key", reminderKey(block))
                    put("fire_at_local", fire.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME))
                    put("title", block.title)
                    put(
                        "body",
                        "$startLabel · ${DemoSchedule.formatLength(block.lengthMinutes)}",
                    )
                },
            )
        }
        return arr.toString()
    }

    /** Test hook: moving a block changes its reminder key so reschedule drops the old alarm. */
    fun moveBlock(
        blockId: String,
        newDayIndex: Int,
        newStartMinute: Int,
    ) {
        val idx = blocks.indexOfFirst { it.id == blockId }
        if (idx < 0) return
        val old = blocks[idx]
        blocks[idx] =
            old.copy(dayIndex = newDayIndex, startMinute = newStartMinute)
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

    private var planPreviewId: String? = null
    private var planPreviewPlacedIds: List<String> = emptyList()
    private var planPreviewChipIds: List<String> = emptyList()
    private var lastPlanNewIds: Set<String> = emptySet()
    private var runningLatePreviewId: String? = null

    override fun saveHomework(draftJson: String, opId: String): String {
        val draft = JSONObject(draftJson)
        val title = draft.optString("title", "").trim()
        if (title.isEmpty()) {
            return jsonString {
                put("ok", false)
                put("error", "Give the homework a title.")
            }
        }
        if (title.length > 80) {
            return jsonString {
                put("ok", false)
                put("error", "Title must be 80 characters or fewer.")
            }
        }
        val est = draft.optInt("estimate_min", 0)
        if (est <= 0 || est % 15 != 0) {
            return jsonString {
                put("ok", false)
                put("error", "Choose a length in 15-minute steps.")
            }
        }
        val dueLabel = draft.optString("due", "Fri 9 Oct")
        val dueIndex =
            when (dueLabel) {
                "Fri 9 Oct" -> 4
                "Sun 11 Oct" -> 6
                else -> 4
            }
        val id = "hw_${System.nanoTime()}"
        noTime.add(
            DemoSchedule.NoTimeChip(
                id = id,
                title = title,
                lengthMinutes = est,
                dueDayIndex = dueIndex,
            ),
        )
        return jsonString {
            put("ok", true)
            put("id", id)
            put("message", "$title added. No time yet.")
        }
    }

    override fun planWeek(weekStart: String): String {
        if (noTime.isEmpty()) {
            return jsonString {
                put("ok", false)
                put("error", "Nothing to plan.")
            }
        }
        val previewId = UUID.randomUUID().toString()
        planPreviewId = previewId
        val placedIds = mutableListOf<String>()
        val chipIds = mutableListOf<String>()
        val lines = JSONArray()
        var placedMinutes = 0
        for (chip in noTime.toList()) {
            val slot = DemoSchedule.fakePlace(chip)
            if (slot != null) {
                val blockId = "planned_${chip.id}"
                placedIds += blockId
                chipIds += chip.id
                placedMinutes += chip.lengthMinutes
                lines.put(
                    jsonObject {
                        put("title", chip.title)
                        put("detail", "")
                        put("right", "${DemoSchedule.dayLabels[slot.first]} ${DemoSchedule.formatTime(slot.second)}")
                    },
                )
            } else {
                lines.put(
                    jsonObject {
                        put("title", chip.title)
                        put("detail", "")
                        put(
                            "why",
                            "No ${DemoSchedule.formatLength(chip.lengthMinutes)} gap before " +
                                "${DemoSchedule.dayLabels[chip.dueDayIndex]} ${DemoSchedule.dayDates[chip.dueDayIndex]}. " +
                                "Move something, or allow splitting on your computer.",
                        )
                        put("right", "not placed")
                    },
                )
            }
        }
        lines.put(
            jsonObject {
                put("title", "History essay")
                put("detail", "already had a time")
                put("right", "Thu ${DemoSchedule.formatTime(19 * 60)}")
            },
        )
        planPreviewPlacedIds = placedIds
        planPreviewChipIds = chipIds
        val placedCount = placedIds.size
        val leftCount = noTime.size - placedCount
        return jsonString {
            put("ok", true)
            put("preview_id", previewId)
            put(
                "summary",
                "Placed $placedCount of ${noTime.size} · ${DemoSchedule.formatLength(placedMinutes)}" +
                    if (leftCount == 0) " · nothing left over" else "",
            )
            put("lines", lines)
            put("placed_ids", JSONArray(placedIds))
        }
    }

    override fun acceptPlan(previewId: String, opId: String): String {
        if (planPreviewId != previewId) {
            return jsonString {
                put("ok", false)
                put("error", "That plan preview expired. Plan again.")
            }
        }
        val chipsById = noTime.associateBy { it.id }
        for (chipId in planPreviewChipIds) {
            val chip = chipsById[chipId] ?: continue
            val slot = DemoSchedule.fakePlace(chip) ?: continue
            val blockId = "planned_$chipId"
            blocks.add(
                DemoSchedule.Block(
                    id = blockId,
                    title = chip.title,
                    category = "hw",
                    dayIndex = slot.first,
                    startMinute = slot.second,
                    lengthMinutes = chip.lengthMinutes,
                    homework = true,
                ),
            )
            noTime.removeAll { it.id == chipId }
        }
        val placedIds = planPreviewPlacedIds.toList()
        lastPlanNewIds = placedIds.toSet()
        planPreviewId = null
        planPreviewPlacedIds = emptyList()
        planPreviewChipIds = emptyList()
        return jsonString { put("ok", true); put("placed_ids", JSONArray(placedIds)) }
    }

    override fun runningLate(dayIndex: Int, minutes: Int, opId: String): String {
        val previewId = UUID.randomUUID().toString()
        runningLatePreviewId = previewId
        val moves = JSONArray()
        moves.put(
            jsonObject {
                put("title", "History essay")
                put("detail", "7–8 PM → 7:30–8:30 PM")
                put("why", "Soccer runs 30 min over, so the essay starts after it ends.")
            },
        )
        moves.put(
            jsonObject {
                put("title", "Soccer")
                put("detail", "stays")
                put("why", "Fixed time. It is not moved, only finished later.")
            },
        )
        return jsonString {
            put("ok", true)
            put("preview_id", previewId)
            put("minutes", minutes)
            put("moves", moves)
        }
    }

    override fun acceptRunningLate(previewId: String, opId: String): String {
        if (runningLatePreviewId != previewId) {
            return jsonString {
                put("ok", false)
                put("error", "That preview expired.")
            }
        }
        runningLatePreviewId = null
        return jsonString { put("ok", true) }
    }

    override fun weekShape(weekStart: String): String {
        val firstHour = 8f
        val lastHour = 22f
        val span = lastHour - firstHour
        val days = JSONArray()
        for (d in 0..6) {
            val dayBlocks = blocks.filter { it.dayIndex == d }.sortedBy { it.startMinute }
            val bars = JSONArray()
            for (b in dayBlocks) {
                val top = (b.startMinute / 60f - firstHour) / span
                val height = b.lengthMinutes / 60f / span
                bars.put(
                    jsonObject {
                        put("category", b.category)
                        put("top", top.coerceIn(0f, 1f))
                        put("height", height.coerceAtLeast(0.02f))
                        put("is_new", b.id in lastPlanNewIds)
                    },
                )
            }
            days.put(
                jsonObject {
                    put("index", d)
                    put("is_today", d == DemoSchedule.TODAY_INDEX)
                    put("bars", bars)
                },
            )
        }
        return jsonString {
            put("title", "5 – 11 Oct")
            put("days", days)
        }
    }

    override fun weekRows(weekStart: String): String {
        val heavyThresholdMinutes = 180
        val days = JSONArray()
        for (day in 0..6) {
            val homework = blocks.filter { it.dayIndex == day && it.homework }.sortedBy { it.startMinute }
            val names = blocks.filter { it.dayIndex == day && it.category != "school" }
                .sortedBy { it.startMinute }.map { it.title }.toMutableList()
            names.addAll(noTime.filter { it.dueDayIndex == day }.map { "${it.title} due" })
            if (names.isEmpty() && blocks.any { it.dayIndex == day && it.category == "school" }) names.add("School only")
            days.put(jsonObject {
                put("day", day)
                put("date", java.time.LocalDate.parse(weekStart).plusDays(day.toLong()).toString())
                put("names", JSONArray(names))
                put("minutes", homework.sumOf { it.lengthMinutes })
                put("heavy", homework.sumOf { it.lengthMinutes } > heavyThresholdMinutes)
                put("unplaced", JSONArray(noTime.filter { it.dueDayIndex == day }.map { it.title }))
                put("last_class_end", blocks.filter { it.dayIndex == day && it.category == "school" }
                    .maxOfOrNull { it.startMinute + it.lengthMinutes })
            })
        }
        return jsonString { put("week_start", weekStart); put("days", days) }
    }

    override fun setLeadMinutes(minutes: Int) {
        leadMinutes = minutes
    }

    override fun setExactReminders(on: Boolean) {
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

    private fun homeworkLeftToday(nowMinute: Int): Boolean =
        blocks.any { b ->
            b.dayIndex == DemoSchedule.TODAY_INDEX &&
                b.homework &&
                !isDone(b) &&
                b.startMinute + b.lengthMinutes > nowMinute
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
        val hwLeft = homeworkLeftToday(nowMinute)
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
            put("show_finish_focus", block.homework)
            put("show_running_late", hwLeft)
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

    private fun reminderKey(block: DemoSchedule.Block): String {
        val start = "%02d:%02d".format(block.startMinute / 60, block.startMinute % 60)
        return listOf(DemoSchedule.WEEK_START, block.id, block.dayIndex.toString(), start).joinToString("|")
    }

    private fun blockReminderFire(block: DemoSchedule.Block): LocalDateTime {
        val date = isoForDay(block.dayIndex)
        val fireMinute = (block.startMinute - leadMinutes).coerceAtLeast(0)
        val hour = fireMinute / 60
        val minute = fireMinute % 60
        return LocalDateTime.parse(
            "$date" + "T" + "%02d:%02d:00".format(hour, minute),
            DateTimeFormatter.ISO_LOCAL_DATE_TIME,
        )
    }
}

enum class SyncState {
    SYNCED,
    SYNCING,
    UNREACHABLE,
}

internal fun newOpId(): String = UUID.randomUUID().toString()
