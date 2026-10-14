package com.flexweek.app.system

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.flexweek.app.FlexWeekApp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
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
        const val SYNC_DEADLINE_MS = 10_000L
    }
}
