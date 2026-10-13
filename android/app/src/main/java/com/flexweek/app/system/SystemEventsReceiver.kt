package com.flexweek.app.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Reschedule alarms after reboot, clock or time zone changes, or an app update. */
class SystemEventsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_TIME_CHANGED,
            "android.intent.action.TIME_SET",
            Intent.ACTION_TIMEZONE_CHANGED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            -> ReminderScheduler.refreshAsync(context.applicationContext)
        }
    }
}
