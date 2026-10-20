package com.flexweek.app.system.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.os.Bundle

class UpNextWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        WidgetRuntime.refreshAsync(context, force = true, pending = goAsync())
    }

    // A resize changes how many rows fit, not the text, so it has to redraw.
    override fun onAppWidgetOptionsChanged(context: Context, appWidgetManager: AppWidgetManager, appWidgetId: Int, newOptions: Bundle) {
        WidgetRuntime.refreshAsync(context, force = true, pending = goAsync())
    }

    override fun onDisabled(context: Context) {
        WidgetRuntime.cancelWake(context)
    }
}
