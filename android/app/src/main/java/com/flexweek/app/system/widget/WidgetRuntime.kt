package com.flexweek.app.system.widget

import android.app.AlarmManager
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import com.flexweek.app.FlexWeekApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.time.LocalTime
import java.time.ZoneId

/** Refreshes the Up next widget; every trigger calls [refreshAsync], and the updater redraws only on a change. */
object WidgetRuntime {
    private const val PREFS = "flexweek_widget"
    private const val KEY_LAST = "last"
    private const val REQUEST_CODE_WAKE = 91_001

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val one = Mutex()

    fun refreshAsync(context: Context, force: Boolean = false, pending: BroadcastReceiver.PendingResult? = null) {
        val app = context.applicationContext
        scope.launch {
            try {
                one.withLock { refresh(app, force) }
            } finally {
                pending?.finish()
            }
        }
    }

    fun cancelWake(context: Context) {
        val pending = wakeIntent(context)
        context.getSystemService(AlarmManager::class.java).cancel(pending)
        pending.cancel()
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY_LAST).apply()
    }

    private suspend fun refresh(app: Context, force: Boolean) {
        val manager = AppWidgetManager.getInstance(app)
        val ids = manager.getAppWidgetIds(ComponentName(app, UpNextWidgetProvider::class.java))
        if (ids.isEmpty()) {
            cancelWake(app)
            return
        }
        val core = (app as FlexWeekApp).awaitCore()
        val host = AndroidWidgetHost(app, manager, ids) {
            core != null && try {
                JSONObject(core.settingsForPhone()).optBoolean("exact_reminders", false)
            } catch (_: Exception) {
                false
            }
        }
        WidgetUpdater(
            read = { core?.let { WidgetRead.today(it, LocalTime.now().let { now -> now.hour * 60 + now.minute }) } },
            host = host,
            nowMs = System::currentTimeMillis,
            zone = ZoneId::systemDefault,
        ).refresh(force)
    }

    internal fun wakeIntent(context: Context): PendingIntent = PendingIntent.getBroadcast(
        context,
        REQUEST_CODE_WAKE,
        Intent(context, WidgetAlarmReceiver::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private class AndroidWidgetHost(
        private val context: Context,
        private val manager: AppWidgetManager,
        private val ids: IntArray,
        private val exactOptIn: () -> Boolean,
    ) : WidgetHost {
        private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        override var lastShown: String?
            get() = prefs.getString(KEY_LAST, null)
            set(value) = prefs.edit().putString(KEY_LAST, value).apply()

        override fun show(content: WidgetContent) {
            for (id in ids) {
                manager.updateAppWidget(id, WidgetViews.build(context, content, manager.getAppWidgetOptions(id)))
            }
            lastShown = content.toString()
        }

        // Always set, never skipped as unchanged: a reboot clears alarms, and the update that follows must re-arm.
        override fun schedule(wake: WidgetRefresh.Wake) {
            val alarm = context.getSystemService(AlarmManager::class.java)
            val pending = wakeIntent(context)
            val exactAllowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarm.canScheduleExactAlarms()
            when {
                // Exact only for a start, an end or midnight, and only when the user has opted in to exact reminders.
                wake.kind != WidgetRefresh.Kind.MINUTE && exactOptIn() && exactAllowed ->
                    alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, wake.atMs, pending)
                // A countdown minute does not wake the phone: it redraws when the phone is next awake.
                wake.kind == WidgetRefresh.Kind.MINUTE -> alarm.setAndAllowWhileIdle(AlarmManager.RTC, wake.atMs, pending)
                else -> alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, wake.atMs, pending)
            }
        }
    }
}
