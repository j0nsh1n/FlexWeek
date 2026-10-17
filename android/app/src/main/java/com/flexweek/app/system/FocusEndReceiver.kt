package com.flexweek.app.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.flexweek.app.FlexWeekApp
import com.flexweek.app.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class FocusEndReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val app = context.applicationContext as FlexWeekApp
                val core = app.awaitCore() ?: return@launch
                core.focusComplete()
                FocusRuntime.update(context, core.focusState())
                if (NotificationManagerCompat.from(context).areNotificationsEnabled()) {
                    val notification = NotificationCompat.Builder(context, FlexWeekApp.CHANNEL_REMINDERS)
                        .setSmallIcon(R.drawable.ic_notification)
                        .setContentTitle("Session finished")
                        .setContentText("Homework finished")
                        .setAutoCancel(true)
                        .build()
                    NotificationManagerCompat.from(context).notify(FocusRuntime.NOTIFICATION_ID + 1, notification)
                }
            } finally {
                pending.finish()
            }
        }
    }
}
