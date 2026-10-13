package com.flexweek.app.ui.reminders

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.FlexWeekCore
import org.json.JSONObject

data class RemindersUiState(
    val leadMinutes: Int = 10,
    val exactReminders: Boolean = false,
    val showPermissionBanner: Boolean = true,
    val deviceName: String = "Joo's laptop",
    val pairedAt: String = "8 Oct",
    val reachable: Boolean = true,
    val syncing: Boolean = false,
)

class RemindersViewModel(
    private val core: FlexWeekCore,
) : ViewModel() {
    var state by mutableStateOf(RemindersUiState())
        private set

    init {
        reload()
    }

    fun reload() {
        val settings = JSONObject(core.settingsForPhone())
        state =
            state.copy(
                leadMinutes = settings.getInt("lead_minutes"),
                exactReminders = settings.getBoolean("exact_reminders"),
                deviceName = settings.getString("device_name"),
                pairedAt = settings.getString("paired_at"),
                reachable = settings.getBoolean("reachable"),
            )
    }

    fun setLeadMinutes(minutes: Int) {
        core.setLeadMinutes(minutes)
        reload()
    }

    fun toggleExact(onRequestExactSetting: () -> Unit = {}) {
        val next = !state.exactReminders
        if (next) {
            onRequestExactSetting()
        }
        core.setExactReminders(next)
        reload()
    }

    fun showPostPairBanner() {
        state = state.copy(showPermissionBanner = true)
    }

    fun allowNotifications() {
        state = state.copy(showPermissionBanner = false)
    }

    fun syncNow() {
        state = state.copy(syncing = true)
        core.syncOnce(45_000)
        state = state.copy(syncing = false)
        reload()
    }
}
