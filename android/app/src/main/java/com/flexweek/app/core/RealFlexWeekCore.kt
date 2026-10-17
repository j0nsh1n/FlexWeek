package com.flexweek.app.core

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.flexweek.app.bindings.FfiException
import com.flexweek.app.bindings.FlexWeek
import com.flexweek.app.bindings.Host
import org.json.JSONArray
import org.json.JSONObject
import java.security.SecureRandom
import java.time.LocalDate
import java.time.LocalDateTime
import com.flexweek.app.model.DueDate
import java.util.concurrent.ConcurrentHashMap

private const val UNREADABLE = "FlexWeek could not read its own answer. Nothing was changed."

class RealFlexWeekCore(context: Context, private val onDataChanged: (String) -> Unit) : FlexWeekCore {
    private val main = Handler(Looper.getMainLooper())
    private val localSettings = context.getSharedPreferences("phone-settings", Context.MODE_PRIVATE)
    private lateinit var native: FlexWeek
    private var selected: String? = null
    private data class Completion(val assignment: String?, val week: String, val day: Int)
    private val completions = ConcurrentHashMap<String, Completion>()
    private val host = object : Host {
        private val random = SecureRandom()
        override fun nowUnixMs(): Long = System.currentTimeMillis()
        override fun localNow(): String = LocalDateTime.now().withNano(0).toString()
        override fun randomBytes(count: UInt): ByteArray = ByteArray(count.toInt()).also(random::nextBytes)
        override fun dataChanged(scope: String) { main.post { onDataChanged(scope) } }
    }

    override fun open(dbPath: String, deviceName: String) {
        native = FlexWeek.open(dbPath, deviceName, host)
    }

    override fun engineVersion(): String = native.engineVersion()
    override fun selectedDate(): String = selected ?: currentDate()
    override fun selectDay(index: Int) {
        require(index in 0..6)
        selected = LocalDate.parse(currentWeekStart()).plusDays(index.toLong()).toString()
    }

    override fun today(date: String, nowMinute: Int): String {
        val raw = native.today(date, nowMinute.toLong())
        val root = JSONObject(raw)
        val rows = root.getJSONArray("rows")
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            completions[row.getString("id")] = Completion(
                if (row.isNull("assignment_id")) null else row.getString("assignment_id"),
                root.getString("week_start"), root.getInt("day"),
            )
        }
        return RustPhoneJson.today(raw, currentDate(), syncStatus())
    }

    override fun setBlockDone(weekStart: String, blockId: String, dayIndex: Int, done: Boolean, opId: String) =
        native.setBlockDone(weekStart, blockId, dayIndex.toLong(), done, opId)

    override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
        val target = completions[id] ?: error("Homework row is no longer available. Open the day again.")
        if (target.assignment != null) native.setHomeworkDone(target.assignment, done, opId)
        else native.setBlockDone(target.week, id, target.day.toLong(), done, opId)
    }

    override fun upcomingReminders(fromLocal: String, hours: Int): String = JSONArray().also { items ->
        native.upcomingReminders(fromLocal.take(19), hours.toUInt()).forEach { reminder ->
            items.put(JSONObject().put("key", reminder.id).put("fire_at_local", reminder.localTime)
                .put("title", reminder.title).put("body", RustPhoneJson.reminderBody(reminder.startTime, reminder.durationMin)))
        }
    }.toString()

    override fun settingsForPhone(): String {
        val settings = JSONObject(native.settingsForPhone())
        val sync = JSONObject(syncStatus())
        return settings.put("lead_minutes", settings.getInt("reminder_lead_min"))
            .put("exact_reminders", localSettings.getBoolean("exact-reminders", false))
            .put("device_name", sync.optString("peer_name", "Your computer"))
            .put("paired_at", RustPhoneJson.pairedDate(sync.optString("paired_at", "")))
            .put("reachable", sync.optString("state") != "unreachable").toString()
    }

    override fun setLeadMinutes(minutes: Int) = native.setReminderLead(minutes.toLong())
    override fun setExactReminders(on: Boolean) {
        localSettings.edit().putBoolean("exact-reminders", on).apply()
        onDataChanged("phone_settings")
    }
    override fun syncStatus(): String = RustPhoneJson.sync(native.syncStatus())
    override fun syncOnce(deadlineMs: Long): String = native.syncOnce(deadlineMs)
    override fun pairWithCode(code: String): String = native.pairWithCode(code)
    override fun pairFromQr(text: String): String = native.pairFromQr(text)
    override fun cancelSync() { native.cancelSync() }
    override fun unlink() {
        val result = JSONObject(native.unlink())
        check(result.optBoolean("ok")) { result.optString("error", "Could not unlink. Try again.") }
    }
    override fun isPaired(): Boolean = JSONObject(syncStatus()).optBoolean("has_account")

    private fun result(call: () -> String): String = try {
        JSONObject(call()).put("ok", true).toString()
    } catch (error: FfiException) {
        JSONObject().put("ok", false).put("error", error.message).toString()
    } catch (error: org.json.JSONException) {
        // An answer the phone cannot read once crashed the app as soon as Running late opened.
        JSONObject().put("ok", false).put("error", UNREADABLE).toString()
    }

    override fun saveHomework(draftJson: String, opId: String): String {
        val draft = JSONObject(draftJson)
        val due = DueDate.toDueText(LocalDate.parse(draft.getString("due").take(10)), LocalDate.now())
            ?: return JSONObject().put("ok", false).put("error", DueDate.PAST_DAY).toString()
        return saved(draft.put("due", due), opId)
    }

    private fun saved(draft: JSONObject, opId: String): String = result {
        draft.put("from_date", currentDate()).put("spread", if (draft.optString("sessions") == "one") "one" else "spread")
        native.saveHomework(draft.toString(), opId)
    }
    override fun recentTitles(): List<String> = native.recentTitles()
    override fun planWeek(weekStart: String): String = result { RustPhoneJson.plan(native.planWeek(weekStart, 0.0)) }
    override fun acceptPlan(previewId: String, opId: String): String = result { native.acceptPlan(previewId) }
    override fun runningLate(dayIndex: Int, minutes: Int, opId: String): String = result {
        RustPhoneJson.late(native.runningLate(dayIndex.toLong(), minutes.toLong(), 0.0), minutes)
    }
    override fun acceptRunningLate(previewId: String, opId: String): String = acceptPlan(previewId, opId)
    override fun weekShape(weekStart: String): String = RustPhoneJson.week(native.weekShape(weekStart), currentDate())
    override fun weekRows(weekStart: String): String = native.weekRows(weekStart)
}
