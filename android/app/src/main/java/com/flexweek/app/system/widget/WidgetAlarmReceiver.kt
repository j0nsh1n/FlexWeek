package com.flexweek.app.system.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** The widget's own refresh alarm; it is never booked in the reminder AlarmBook. */
class WidgetAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        WidgetRuntime.refreshAsync(context, pending = goAsync())
    }
}
