package com.flexweek.app.system

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.flexweek.app.FlexWeekApp
import com.flexweek.app.R
import com.flexweek.app.system.widget.WidgetRuntime

object FocusRuntime {
    const val NOTIFICATION_ID = 78124
    const val END_ALARM_KEY = "focus-end"
    const val ACTION = "com.flexweek.app.FOCUS_ACTION"
    const val EXTRA_ACTION = "focus_action"

    fun update(context: Context, saved: String) {
        val app = context.applicationContext
        // Finishing a timer can finish its homework, which the widget shows.
        WidgetRuntime.refreshAsync(app)
        val manager = NotificationManagerCompat.from(app)
        val plan = FocusNotificationPlan.from(saved)
        if (plan == null) {
            manager.cancel(NOTIFICATION_ID)
            cancelAlarm(app)
            return
        }
        if (manager.areNotificationsEnabled()) {
            val action = if (plan.countdown) "pause" else "resume"
            val notification = NotificationCompat.Builder(app, FlexWeekApp.CHANNEL_REMINDERS)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(plan.header)
                .setContentText(if (plan.status == "Paused") "${plan.title} · Paused" else plan.title)
                .setVisibility(FocusNotificationPlan.visibility)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setWhen(plan.whenMs)
                .setUsesChronometer(plan.countdown)
                .setChronometerCountDown(plan.countdown)
                .addAction(0, if (plan.countdown) "Pause" else "Resume", actionIntent(app, action))
                .addAction(0, "Finish", actionIntent(app, "finish"))
                .build()
            manager.notify(NOTIFICATION_ID, notification)
        }
        val armed = FocusAlarmPlan.rearmOnBoot(saved) { scheduleAlarm(app, it) }
        if (!armed) cancelAlarm(app)
    }

    private fun actionIntent(context: Context, action: String) = PendingIntent.getBroadcast(
        context, action.hashCode(), Intent(context, FocusActionReceiver::class.java).apply {
            this.action = ACTION
            putExtra(EXTRA_ACTION, action)
        }, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun cancelAlarm(context: Context) {
        AndroidAlarmScheduler(context, context.getSystemService(AlarmManager::class.java), AlarmBook(context)).cancel(END_ALARM_KEY)
    }

    private fun scheduleAlarm(context: Context, at: Long) {
        val alarm = context.getSystemService(AlarmManager::class.java)
        val exact = android.os.Build.VERSION.SDK_INT < 31 || alarm.canScheduleExactAlarms()
        val scheduler = AndroidAlarmScheduler(context, alarm, AlarmBook(context))
        applyReminderPlan(scheduler, ReminderRescheduler.Plan(
            cancelKeys = emptySet(),
            schedule = listOf(ReminderRescheduler.ScheduleRequest(END_ALARM_KEY, at, exact, "Focus session over", "")),
        ))
    }
}
