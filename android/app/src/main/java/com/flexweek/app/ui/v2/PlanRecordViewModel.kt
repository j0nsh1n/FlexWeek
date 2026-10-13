package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.PlanRecordState
import com.flexweek.app.model.V2Json
import org.json.JSONObject

class PlanRecordViewModel(
    private val core: FlexWeekCore,
    private val onAccepted: () -> Unit,
    private val onDismiss: () -> Unit,
) : ViewModel() {
    var record by mutableStateOf<PlanRecordState?>(null)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    init {
        loadPlan()
    }

    fun loadPlan() {
        error = null
        val raw = core.planWeek(DemoSchedule.WEEK_START)
        val root = JSONObject(raw)
        if (!root.optBoolean("ok", false)) {
            error = root.optString("error", "Could not plan.")
            return
        }
        record = V2Json.parsePlanRecord(raw)
    }

    fun undo() {
        record = null
        onDismiss()
    }

    fun accept() {
        val preview = record ?: return
        val raw = core.acceptPlan(preview.previewId, newOpId())
        if (!JSONObject(raw).optBoolean("ok", false)) {
            error = JSONObject(raw).optString("error", "Could not accept.")
            return
        }
        record = null
        onAccepted()
    }
}
