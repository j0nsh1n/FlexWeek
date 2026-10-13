package com.flexweek.app.system

import android.content.Context
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager

object ReminderScheduler {
    const val UNIQUE_RESCHEDULE = "flexweek-reschedule-reminders"

    fun refreshAsync(context: Context) {
        val request = OneTimeWorkRequestBuilder<RescheduleWorker>().build()
        WorkManager.getInstance(context.applicationContext)
            .enqueueUniqueWork(UNIQUE_RESCHEDULE, ExistingWorkPolicy.REPLACE, request)
    }
}
