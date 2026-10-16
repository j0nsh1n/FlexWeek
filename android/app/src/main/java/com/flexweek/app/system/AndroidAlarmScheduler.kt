package com.flexweek.app.system

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build

class AndroidAlarmScheduler(
    private val context: Context,
    private val alarmManager: AlarmManager,
    private val book: AlarmBook,
) : AlarmScheduler {
    override fun scheduledKeys(): Set<String> = book.keys()

    override fun cancel(key: String) {
        val pi = pendingIntent(key, "", "")
        alarmManager.cancel(pi)
        pi.cancel()
        cancelLegacy(key)
        book.remove(key)
    }

    override fun schedule(request: ReminderRescheduler.ScheduleRequest) {
        val pi =
            pendingIntent(
                request.key,
                request.title,
                request.body,
            )
        if (request.exact) {
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                request.triggerAtMs,
                pi,
            )
        } else {
            val windowStart = (request.triggerAtMs - ReminderRescheduler.WINDOW_EARLY_MS).coerceAtLeast(0L)
            alarmManager.setWindow(
                AlarmManager.RTC_WAKEUP,
                windowStart,
                ReminderRescheduler.WINDOW_LENGTH_MS,
                pi,
            )
        }
        cancelLegacy(request.key)
        book.remember(request.key)
    }

    // 1.0.0 set its alarms with key.hashCode() as the request code. After an update those alarms are still
    // pending and a new request code no longer reaches them, so they would fire beside the new ones. Each key
    // that is scheduled or cancelled also cancels its old alarm, if one is left.
    private fun cancelLegacy(key: String) {
        val intent = Intent(context, ReminderReceiver::class.java)
        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_NO_CREATE
        val legacy = PendingIntent.getBroadcast(context, key.hashCode(), intent, flags) ?: return
        alarmManager.cancel(legacy)
        legacy.cancel()
    }

    private fun pendingIntent(
        key: String,
        title: String,
        body: String,
    ): PendingIntent {
        val intent =
            Intent(context, ReminderReceiver::class.java).apply {
                putExtra(ReminderReceiver.EXTRA_KEY, key)
                putExtra(ReminderReceiver.EXTRA_TITLE, title)
                putExtra(ReminderReceiver.EXTRA_BODY, body)
            }
        val flags =
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        return PendingIntent.getBroadcast(context, ReminderReceiver.reminderNotificationId(key), intent, flags)
    }
}

class AlarmBook(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun keys(): Set<String> = prefs.getStringSet(KEY_KEYS, emptySet())?.toSet() ?: emptySet()

    fun remember(key: String) {
        val next = keys().toMutableSet()
        next += key
        prefs.edit().putStringSet(KEY_KEYS, next).apply()
    }

    fun remove(key: String) {
        val next = keys().toMutableSet()
        next -= key
        prefs.edit().putStringSet(KEY_KEYS, next).apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_KEYS).apply()
    }

    companion object {
        private const val PREFS = "flexweek_alarm_book"
        private const val KEY_KEYS = "keys"
    }
}

/** Applies a [ReminderRescheduler.Plan] to any [AlarmScheduler] (real or test fake). */
fun applyReminderPlan(
    scheduler: AlarmScheduler,
    plan: ReminderRescheduler.Plan,
) {
    plan.cancelKeys.forEach { scheduler.cancel(it) }
    for (req in plan.schedule) {
        scheduler.cancel(req.key)
        scheduler.schedule(req)
    }
}

fun rescheduleRemindersNow(
    core: com.flexweek.app.core.FlexWeekCore,
    scheduler: AlarmScheduler,
    fromLocal: String,
    nowMs: Long,
    canScheduleExactAlarms: Boolean,
    sdkInt: Int = Build.VERSION.SDK_INT,
) {
    if (!core.isPaired()) {
        scheduler.cancelAllNotIn(emptySet())
        return
    }
    val settings = org.json.JSONObject(core.settingsForPhone())
    val upcoming = ReminderJson.parseArray(core.upcomingReminders(fromLocal, 48))
    val plan =
        ReminderRescheduler.plan(
            upcoming = upcoming,
            currentlyScheduled = scheduler.scheduledKeys(),
            nowMs = nowMs,
            exactOptIn = settings.optBoolean("exact_reminders", false),
            canScheduleExactAlarms = canScheduleExactAlarms,
            sdkInt = sdkInt,
        )
    applyReminderPlan(scheduler, plan)
}
