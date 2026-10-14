package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.RunningLatePreview
import com.flexweek.app.model.V2Json
import org.json.JSONObject

class RunningLateViewModel(
    private val core: FlexWeekCore,
    private val onAccepted: () -> Unit,
    private val onDismiss: () -> Unit,
) : ViewModel() {
    var minutes by mutableIntStateOf(30)
        private set

    var preview by mutableStateOf<RunningLatePreview?>(null)
        private set

    init {
        loadPreview()
    }

    fun pickMinutes(value: Int) {
        minutes = value
        loadPreview()
    }

    private fun loadPreview() {
        val raw = core.runningLate(core.currentDayIndex(), minutes, newOpId())
        val root = JSONObject(raw)
        if (root.optBoolean("ok", false)) {
            preview = V2Json.parseRunningLate(raw)
        }
    }

    fun cancel() {
        preview = null
        onDismiss()
    }

    fun accept() {
        val id = preview?.previewId ?: return
        val raw = core.acceptRunningLate(id, newOpId())
        if (JSONObject(raw).optBoolean("ok", false)) {
            preview = null
            onAccepted()
        }
    }
}
