package com.flexweek.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.FlexWeekCoreFactory

class FlexWeekApp : Application() {
    lateinit var core: FlexWeekCore
        private set

    override fun onCreate() {
        super.onCreate()
        core = FlexWeekCoreFactory.create(this)
        core.open(filesDir.resolve("flexweek.db").absolutePath, "Phone")
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_REMINDERS,
                getString(R.string.channel_reminders),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_SYNC,
                getString(R.string.channel_sync),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    companion object {
        const val CHANNEL_REMINDERS = "reminders"
        const val CHANNEL_SYNC = "sync"
    }
}
