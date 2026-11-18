package com.flexweek.app.ui.reminders

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.content.Context
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.SyncWords
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
    val paired: Boolean = true,
    val lastSync: String = "",
    val syncing: Boolean = false,
    val problem: String? = null,
)

private data class ReminderSettings(
    val leadMinutes: Int,
    val exactReminders: Boolean,
    val deviceName: String,
    val pairedAt: String,
    val reachable: Boolean,
    val paired: Boolean,
    val lastSync: String,
)

interface ReminderPrefs {
    /** When the student last chose "Not now" (epoch ms), 0 for never. */
    var permissionBannerDismissedAt: Long
    var notificationAsked: Boolean
}

class SharedPreferenceReminderPrefs(context: Context) : ReminderPrefs {
    private val prefs = context.getSharedPreferences("flexweek_reminders", Context.MODE_PRIVATE)

    override var permissionBannerDismissedAt: Long
        get() = prefs.getLong("permission_banner_dismissed_at", 0L)
        set(value) { prefs.edit().putLong("permission_banner_dismissed_at", value).apply() }
    override var notificationAsked: Boolean
        get() = prefs.getBoolean("notification_asked", false)
        set(value) { prefs.edit().putBoolean("notification_asked", value).apply() }
}

class InMemoryReminderPrefs : ReminderPrefs {
    override var permissionBannerDismissedAt: Long = 0L
    override var notificationAsked: Boolean = false
}

class RemindersViewModel(
    private val core: FlexWeekCore,
    private val prefs: ReminderPrefs = InMemoryReminderPrefs(),
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val permissions: SystemPermissions = UnknownPermissions,
    private val clock: () -> Long = System::currentTimeMillis,
) : ViewModel() {
    constructor(core: FlexWeekCore, workerDispatcher: CoroutineDispatcher) :
        this(core, InMemoryReminderPrefs(), workerDispatcher)

    var state by mutableStateOf(RemindersUiState(showPermissionBanner = bannerShown()))
        private set

    init {
        reload()
    }

    private fun bannerShown() =
        PermissionBanner.show(permissions.notificationsAllowed(), prefs.permissionBannerDismissedAt, clock())

    /** Asks Android again (on return from a system screen): the banner and the exact switch follow the answer. */
    fun refreshPermissions() {
        state = state.copy(showPermissionBanner = bannerShown())
        reload()
    }

    val notificationAsked: Boolean
        get() = prefs.notificationAsked

    fun markNotificationAsked() { prefs.notificationAsked = true }

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
                    paired = refreshed.paired,
                    lastSync = refreshed.lastSync,
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
            exactReminders = settings.getBoolean("exact_reminders") && permissions.canScheduleExact(),
            deviceName = settings.getString("device_name"),
            pairedAt = settings.getString("paired_at"),
            reachable = settings.getBoolean("reachable"),
            paired = settings.optBoolean("paired", true),
            lastSync = settings.optString("last_sync", ""),
        )
    }

    private fun applySettings(refreshed: ReminderSettings) {
        state = state.copy(
            leadMinutes = refreshed.leadMinutes,
            exactReminders = refreshed.exactReminders,
            deviceName = refreshed.deviceName,
            pairedAt = refreshed.pairedAt,
            reachable = refreshed.reachable,
            paired = refreshed.paired,
            lastSync = refreshed.lastSync,
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
        if (next && !permissions.canScheduleExact()) {
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
        state = state.copy(showPermissionBanner = !permissions.notificationsAllowed())
    }

    fun allowNotifications() {
        state = state.copy(showPermissionBanner = false)
    }

    fun dismissPermissionBanner() {
        prefs.permissionBannerDismissedAt = clock()
        state = state.copy(showPermissionBanner = false)
    }

    fun onNotificationPermissionResult(granted: Boolean) {
        if (granted) allowNotifications()
    }

    fun syncNow() {
        if (state.syncing) return
        state = state.copy(syncing = true, problem = null)
        viewModelScope.launch {
            val answer = JSONObject(withContext(workerDispatcher) { core.syncOnce(45_000) })
            val failure = if (answer.optBoolean("ok", true)) null
            else SyncWords.syncProblem(answer.optString("kind"), answer.optString("error"))
            state = state.copy(syncing = false, problem = failure)
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
