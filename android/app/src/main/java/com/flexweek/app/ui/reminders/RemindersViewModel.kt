package com.flexweek.app.ui.reminders

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.flexweek.app.core.FlexWeekCore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class RemindersUiState(
    val leadMinutes: Int = 10,
    val exactReminders: Boolean = false,
    val showPermissionBanner: Boolean = true,
    val deviceName: String = "Joo's laptop",
    val pairedAt: String = "8 Oct",
    val reachable: Boolean = true,
    val syncing: Boolean = false,
    val problem: String? = null,
)

private data class ReminderSettings(
    val leadMinutes: Int,
    val exactReminders: Boolean,
    val deviceName: String,
    val pairedAt: String,
    val reachable: Boolean,
)

class RemindersViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var state by mutableStateOf(RemindersUiState())
        private set

    init {
        reload()
    }

    fun reload() {
        if (core !is com.flexweek.app.core.FakeFlexWeekCore) {
            viewModelScope.launch {
                val refreshed = withContext(workerDispatcher) { readSettings() }
                state = state.copy(
                    leadMinutes = refreshed.leadMinutes,
                    exactReminders = refreshed.exactReminders,
                    deviceName = refreshed.deviceName,
                    pairedAt = refreshed.pairedAt,
                    reachable = refreshed.reachable,
                )
            }
            return
        }
        applySettings(readSettings())
    }

    private fun readSettings(): ReminderSettings {
        val settings = JSONObject(core.settingsForPhone())
        return ReminderSettings(
            leadMinutes = settings.getInt("lead_minutes"),
            exactReminders = settings.getBoolean("exact_reminders"),
            deviceName = settings.getString("device_name"),
            pairedAt = settings.getString("paired_at"),
            reachable = settings.getBoolean("reachable"),
        )
    }

    private fun applySettings(refreshed: ReminderSettings) {
        state = state.copy(
            leadMinutes = refreshed.leadMinutes,
            exactReminders = refreshed.exactReminders,
            deviceName = refreshed.deviceName,
            pairedAt = refreshed.pairedAt,
            reachable = refreshed.reachable,
        )
    }

    fun setLeadMinutes(minutes: Int) {
        if (core !is com.flexweek.app.core.FakeFlexWeekCore) {
            viewModelScope.launch {
                val refreshed = withContext(workerDispatcher) {
                    core.setLeadMinutes(minutes)
                    readSettings()
                }
                applySettings(refreshed)
            }
            return
        }
        core.setLeadMinutes(minutes)
        reload()
    }

    fun toggleExact(onRequestExactSetting: () -> Unit = {}) {
        val next = !state.exactReminders
        if (next) {
            onRequestExactSetting()
        }
        if (core !is com.flexweek.app.core.FakeFlexWeekCore) {
            viewModelScope.launch {
                val refreshed = withContext(workerDispatcher) {
                    core.setExactReminders(next)
                    readSettings()
                }
                applySettings(refreshed)
            }
            return
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
        if (state.syncing) return
        state = state.copy(syncing = true, problem = null)
        viewModelScope.launch {
            withContext(workerDispatcher) { core.syncOnce(45_000) }
            state = state.copy(syncing = false)
            reload()
        }
    }

    fun unpair(onUnpaired: () -> Unit) {
        if (state.syncing) return
        state = state.copy(syncing = true, problem = null)
        viewModelScope.launch {
            try {
                withContext(workerDispatcher) { core.unlink() }
                onUnpaired()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                state = state.copy(problem = error.message ?: "Could not unlink. Try again.")
            } finally {
                state = state.copy(syncing = false)
            }
        }
    }
}
