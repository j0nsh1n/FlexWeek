package com.flexweek.app.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.flexweek.app.system.widget.WidgetRuntime

/** Exact alarms were just allowed or taken away: plan every reminder again with the new answer. */
class ExactAlarmPermissionReceiver : BroadcastReceiver() {
    // AlarmManager.ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED needs API 31; the app runs from 26.
    private companion object { const val ACTION = "android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED" }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return
        ReminderScheduler.refreshAsync(context.applicationContext)
        WidgetRuntime.refreshAsync(context.applicationContext)
    }
}
