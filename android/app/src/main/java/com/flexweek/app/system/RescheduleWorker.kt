package com.flexweek.app.system

import android.app.AlarmManager
import android.content.Context
import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.flexweek.app.FlexWeekApp
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

class RescheduleWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val app = applicationContext as FlexWeekApp
        val core = app.awaitCore() ?: return Result.retry()
        val am = applicationContext.getSystemService(AlarmManager::class.java)
        val book = AlarmBook(applicationContext)
        val scheduler = AndroidAlarmScheduler(applicationContext, am, book)
        val fromLocal = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
        rescheduleRemindersNow(
            core = core,
            scheduler = scheduler,
            fromLocal = fromLocal,
            nowMs = System.currentTimeMillis(),
            canScheduleExactAlarms =
                if (Build.VERSION.SDK_INT >= 31) {
                    am.canScheduleExactAlarms()
                } else {
                    true
                },
        )
        return Result.success()
    }
}
