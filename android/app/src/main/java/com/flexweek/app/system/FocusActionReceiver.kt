package com.flexweek.app.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.flexweek.app.FlexWeekApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class FocusActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = FocusNotificationPlan.action(intent.getStringExtra(FocusRuntime.EXTRA_ACTION)) ?: return
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val app = context.applicationContext as FlexWeekApp
                val core = app.awaitCore() ?: return@launch
                if (action == FocusAction.FINISH) core.focusFinish() else core.focusPause()
                FocusRuntime.update(context, core.focusState())
            } finally {
                pending.finish()
            }
        }
    }
}
