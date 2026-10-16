package com.flexweek.app.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.flexweek.app.FlexWeekApp
import com.flexweek.app.MainActivity
import com.flexweek.app.R
import java.nio.ByteBuffer
import java.security.MessageDigest

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            return
        }
        val title = intent.getStringExtra(EXTRA_TITLE) ?: return
        val body = intent.getStringExtra(EXTRA_BODY) ?: ""
        val open =
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
        val content =
            android.app.PendingIntent.getActivity(
                context,
                reminderNotificationId(intent.getStringExtra(EXTRA_KEY) ?: title),
                open,
                android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT,
            )
        val notification =
            NotificationCompat.Builder(context, FlexWeekApp.CHANNEL_REMINDERS)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(body)
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setAutoCancel(true)
                .setContentIntent(content)
                .build()
        NotificationManagerCompat.from(context).notify(reminderNotificationId(intent.getStringExtra(EXTRA_KEY) ?: title), notification)
    }

    companion object {
        const val EXTRA_KEY = "key"
        const val EXTRA_TITLE = "title"
        const val EXTRA_BODY = "body"

        fun reminderNotificationId(key: String): Int {
            val digest = MessageDigest.getInstance("SHA-256").digest(key.toByteArray(Charsets.UTF_8))
            return ByteBuffer.wrap(digest, 0, Int.SIZE_BYTES).int
        }
    }
}
