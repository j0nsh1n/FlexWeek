package com.flexweek.app.system.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.flexweek.app.FlexWeekApp
import com.flexweek.app.core.newOpId
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.time.LocalTime

/** The tick on a homework row: marks it finished. Everything else on the widget opens Today. */
class WidgetTickReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getStringExtra(EXTRA_ID) ?: return
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val core = (context.applicationContext as FlexWeekApp).awaitCore()
                if (core != null) {
                    val now = LocalTime.now()
                    WidgetTick.markFinished(core, id, now.hour * 60 + now.minute, newOpId())
                }
            } catch (error: Exception) {
                // The widget redraws below, so a tick that did not take shows as an empty circle.
                Log.w("FlexWeekWidget", "could not mark $id finished", error)
            } finally {
                WidgetRuntime.refreshAsync(context, pending = pending)
            }
        }
    }

    companion object {
        const val EXTRA_ID = "id"
    }
}
