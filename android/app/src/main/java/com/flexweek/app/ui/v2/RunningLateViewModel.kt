package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.RunningLatePreview
import com.flexweek.app.model.V2Json
import org.json.JSONObject

class RunningLateViewModel(
    private val core: FlexWeekCore,
    private val onAccepted: () -> Unit,
    private val onDismiss: () -> Unit,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    // Each slider step asks the planner; an answer that comes back after a newer step was asked is dropped.
    private var latestRequest = 0
    var minutes by mutableIntStateOf(30)
        private set

    var preview by mutableStateOf<RunningLatePreview?>(null)
        private set

    /** The core's own words when it cannot preview, shown in the sheet instead of nothing. */
    var error by mutableStateOf<String?>(null)
        private set

    init {
        loadPreview()
    }

    fun pickMinutes(value: Int) {
        minutes = value
        loadPreview()
    }

    private fun loadPreview() {
        val request = ++latestRequest
        val asked = minutes
        viewModelScope.launch {
            val raw = withContext(workerDispatcher) { core.runningLate(core.currentDayIndex(), asked, newOpId()) }
            if (request != latestRequest) return@launch
            val root = JSONObject(raw)
            if (root.optBoolean("ok", false)) {
                preview = V2Json.parseRunningLate(raw)
                error = null
            } else {
                preview = null
                error = root.optString("error").ifBlank { "Running late could not look at your day." }
            }
        }
    }

    fun cancel() {
        preview = null
        error = null
        onDismiss()
    }

    fun accept() {
        val id = preview?.previewId ?: return
        viewModelScope.launch {
            val answer = JSONObject(withContext(workerDispatcher) { core.acceptRunningLate(id, newOpId()) })
            // Either way the preview is spent: accepted, or stale because the week changed under it.
            preview = null
            if (answer.optBoolean("ok", false)) onAccepted()
            else error = answer.optString("error").ifBlank { "Running late could not move that. Try again." }
        }
    }
}
