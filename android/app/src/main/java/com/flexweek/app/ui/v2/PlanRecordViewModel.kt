package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
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
import com.flexweek.app.model.PlanRecordState
import com.flexweek.app.model.V2Json
import org.json.JSONObject

class PlanRecordViewModel(
    private val core: FlexWeekCore,
    private val onAccepted: (List<String>) -> Unit,
    private val onDismiss: () -> Unit,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var record by mutableStateOf<PlanRecordState?>(null)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    init {
        loadPlan()
    }

    // The planner can take its whole time budget and may wait on a sync's database lock: never on the main thread.
    fun loadPlan() {
        error = null
        viewModelScope.launch {
            val raw = withContext(workerDispatcher) { core.planWeek(core.currentWeekStart()) }
            val root = JSONObject(raw)
            if (!root.optBoolean("ok", false)) {
                error = root.optString("error", "Couldn't plan your homework. Try again.")
                return@launch
            }
            record = V2Json.parsePlanRecord(raw)
        }
    }

    fun undo() {
        record = null
        onDismiss()
    }

    fun accept() {
        val preview = record ?: return
        viewModelScope.launch {
            val raw = withContext(workerDispatcher) { core.acceptPlan(preview.previewId, newOpId()) }
            if (!JSONObject(raw).optBoolean("ok", false)) {
                // The sheet shows the reason in place of the plan, which is stale once the core refused it.
                error = JSONObject(raw).optString("error").ifBlank { "Couldn't accept this plan. Try planning again." }
                record = null
                return@launch
            }
            record = null
            val placedIds = JSONObject(raw).optJSONArray("placed_ids")
            onAccepted(if (placedIds == null) emptyList() else List(placedIds.length()) { placedIds.getString(it) })
        }
    }
}
