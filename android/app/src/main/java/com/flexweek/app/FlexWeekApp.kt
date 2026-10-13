package com.flexweek.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.FlexWeekCoreFactory
import com.flexweek.app.core.openForPhone
import com.flexweek.app.system.ReminderScheduler
import com.flexweek.app.system.SyncScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first

data class StartupState(val core: FlexWeekCore? = null, val paired: Boolean = false, val problem: String? = null)

class FlexWeekApp : Application() {
    lateinit var core: FlexWeekCore
        private set
    private val _startup = MutableStateFlow(StartupState())
    val startup = _startup.asStateFlow()
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        applicationScope.launch {
            try {
                val opened = FlexWeekCoreFactory.create(this@FlexWeekApp) { scope ->
                    if (scope == "sync" || scope == "phone_settings") {
                        ReminderScheduler.refreshAsync(this@FlexWeekApp)
                    } else {
                        afterLocalEdit()
                    }
                }
                val paired = opened.openForPhone(filesDir.resolve("flexweek.db").absolutePath)
                withContext(Dispatchers.Main) {
                    core = opened
                    _startup.value = StartupState(core = opened, paired = paired)
                    SyncScheduler.installPeriodic(this@FlexWeekApp)
                    SyncScheduler.requestExpeditedSync(this@FlexWeekApp)
                    ReminderScheduler.refreshAsync(this@FlexWeekApp)
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) {
                    _startup.value = StartupState(problem = error.message ?: "Could not open FlexWeek.")
                }
            }
        }
    }

    fun afterLocalEdit() {
        ReminderScheduler.refreshAsync(this)
        SyncScheduler.requestExpeditedSync(this)
    }

    suspend fun awaitCore(): FlexWeekCore? {
        val ready = startup.first { it.core != null || it.problem != null }
        return ready.core
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_REMINDERS,
                getString(R.string.channel_reminders),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_SYNC,
                getString(R.string.channel_sync),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    companion object {
        const val CHANNEL_REMINDERS = "reminders"
        const val CHANNEL_SYNC = "sync"
    }
}
