package com.flexweek.app.system

import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.ForegroundInfo
import com.flexweek.app.R
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.flexweek.app.FlexWeekApp
import com.flexweek.app.system.widget.WidgetRuntime
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    // Android 11 and older run expedited work as a foreground service and ask for this; without it the job fails.
    override suspend fun getForegroundInfo(): ForegroundInfo {
        val notification = NotificationCompat.Builder(applicationContext, FlexWeekApp.CHANNEL_SYNC)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(applicationContext.getString(R.string.channel_sync))
            .setOngoing(true)
            .build()
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(FOREGROUND_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(FOREGROUND_ID, notification)
        }
    }

    override suspend fun doWork(): Result {
        val app = applicationContext as FlexWeekApp
        val core = app.awaitCore() ?: return Result.retry()
        if (!core.isPaired() || !JSONObject(core.syncStatus()).optBoolean("paired", true)) {
            return Result.success()
        }
        return try {
            withContext(Dispatchers.IO) {
                val raw = core.syncOnce(SYNC_DEADLINE_MS)
                val ok = JSONObject(raw).optBoolean("ok", true)
                if (ok) {
                    ReminderScheduler.refreshAsync(applicationContext)
                    WidgetRuntime.refreshAsync(applicationContext)
                    Result.success()
                } else {
                    Result.retry()
                }
            }
        } catch (e: CancellationException) {
            core.cancelSync()
            throw e
        } catch (_: Throwable) {
            Result.retry()
        } finally {
            if (isStopped) {
                core.cancelSync()
            }
        }
    }

    companion object {
        // The desktop gives a whole sync 45 s; 10 s ended slow relay syncs as "unreachable".
        const val SYNC_DEADLINE_MS = 45_000L
        const val FOREGROUND_ID = 78125
    }
}
