package com.flexweek.app.system

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.flexweek.app.core.FlexWeekCore
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject

internal suspend fun syncWhileForeground(
    core: FlexWeekCore,
    lifecycle: Lifecycle,
    workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
    onRefresh: () -> Unit,
) {
    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        var pauseMs = SyncBackoff.BASE_MS
        while (isActive) {
            val answer = withContext(workerDispatcher) { core.syncOnce(10_000) }
            onRefresh()
            pauseMs = SyncBackoff.next(pauseMs, runCatching { JSONObject(answer).optBoolean("ok", true) }.getOrDefault(true))
            delay(pauseMs)
        }
    }
}
