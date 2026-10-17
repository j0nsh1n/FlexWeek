package com.flexweek.app.system.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import android.view.View
import android.widget.RemoteViews
import com.flexweek.app.MainActivity
import com.flexweek.app.R
import com.flexweek.app.system.ReminderReceiver
import java.util.Locale

/** Draws [WidgetContent] into the widget's layout: picture 9 A. */
internal object WidgetViews {
    private const val REQUEST_CODE_OPEN = 91_002

    private class RowIds(val row: Int, val time: Int, val bar: Int, val title: Int, val length: Int, val tick: Int)

    private val rowIds = listOf(
        RowIds(R.id.widget_row1, R.id.widget_row1_time, R.id.widget_row1_bar, R.id.widget_row1_title, R.id.widget_row1_length, R.id.widget_row1_tick),
        RowIds(R.id.widget_row2, R.id.widget_row2_time, R.id.widget_row2_bar, R.id.widget_row2_title, R.id.widget_row2_length, R.id.widget_row2_tick),
    )

    fun build(context: Context, content: WidgetContent, options: Bundle): RemoteViews {
        val configuration = context.resources.configuration
        val dark = configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES
        // The launcher reports width as MIN in portrait and MAX in landscape, and height the other way round.
        val portrait = configuration.orientation != Configuration.ORIENTATION_LANDSCAPE
        val widthDp = options.getInt(if (portrait) AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH else AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0)
            .takeIf { it > 0 } ?: WidgetSize.ROWS_MIN_WIDTH_DP
        val heightDp = options.getInt(if (portrait) AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT else AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0)
            .takeIf { it > 0 } ?: WidgetSize.ROWS_MIN_HEIGHT_DP
        val views = RemoteViews(context.packageName, R.layout.widget_up_next)
        views.setTextViewText(R.id.widget_kicker, content.kicker?.uppercase(Locale.ENGLISH).orEmpty())
        views.setTextViewText(R.id.widget_headline, content.headline)
        views.setViewVisibility(R.id.widget_headline_time, if (content.headlineTime == null) View.GONE else View.VISIBLE)
        views.setTextViewText(R.id.widget_headline_time, content.headlineTime.orEmpty())
        views.setViewVisibility(R.id.widget_note, if (content.note == null) View.GONE else View.VISIBLE)
        views.setTextViewText(R.id.widget_note, content.note.orEmpty())
        val shown = WidgetSize.rowsToShow(content, widthDp, heightDp)
        rowIds.forEachIndexed { at, ids ->
            val row = shown.getOrNull(at)
            views.setViewVisibility(ids.row, if (row == null) View.GONE else View.VISIBLE)
            if (row != null) bindRow(context, views, ids, row, dark)
        }
        views.setOnClickPendingIntent(R.id.widget_root, openToday(context))
        return views
    }

    private fun bindRow(context: Context, views: RemoteViews, ids: RowIds, row: WidgetRow, dark: Boolean) {
        views.setTextViewText(ids.time, row.time)
        views.setTextViewText(ids.title, row.title)
        views.setTextViewText(ids.length, row.length)
        views.setInt(ids.bar, "setBackgroundColor", WidgetPalette.categoryArgb(row.category, dark))
        views.setViewVisibility(ids.tick, if (row.homework) View.VISIBLE else View.GONE)
        if (!row.homework) return
        if (row.done) {
            views.setImageViewResource(ids.tick, R.drawable.widget_tick_done)
            views.setContentDescription(ids.tick, "${row.title} finished")
            return
        }
        views.setImageViewResource(ids.tick, R.drawable.widget_tick_open)
        views.setContentDescription(ids.tick, WidgetWords.tickLabel(row.title))
        val tick = Intent(context, WidgetTickReceiver::class.java).putExtra(WidgetTickReceiver.EXTRA_ID, row.id)
        views.setOnClickPendingIntent(
            ids.tick,
            PendingIntent.getBroadcast(
                context,
                ReminderReceiver.reminderNotificationId("widget-tick-${row.id}"),
                tick,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            ),
        )
    }

    private fun openToday(context: Context): PendingIntent {
        val request = WidgetTap.openToday()
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = request.flags
            request.extras.forEach { (key, value) -> putExtra(key, value) }
        }
        return PendingIntent.getActivity(context, REQUEST_CODE_OPEN, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }
}
