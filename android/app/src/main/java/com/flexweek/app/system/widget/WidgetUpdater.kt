package com.flexweek.app.system.widget

import java.time.ZoneId

/** What the updater needs from Android: where it remembers the last text, how it draws, how it sets a wake. */
interface WidgetHost {
    /** The text last drawn; [show] records it. */
    var lastShown: String?

    fun show(content: WidgetContent)

    fun schedule(wake: WidgetRefresh.Wake)
}

/** Draws the widget only when its text changes, and always sets the next wake. */
class WidgetUpdater(
    private val read: () -> String?,
    private val host: WidgetHost,
    private val nowMs: () -> Long,
    private val zone: () -> ZoneId,
) {
    fun refresh(force: Boolean = false) {
        val now = nowMs()
        val raw = try {
            read()
        } catch (_: Exception) {
            return failed(now)
        }
        val content: WidgetContent
        val boundaries: List<Int>
        val countdown: Boolean
        if (raw == null) {
            content = WidgetWords.placeholder()
            boundaries = emptyList()
            countdown = false
        } else {
            try {
                content = WidgetWords.from(raw)
                boundaries = WidgetWords.boundaryMinutes(raw)
                countdown = WidgetWords.countdownShowing(raw)
            } catch (_: Exception) {
                return failed(now)
            }
        }
        if (force || content.toString() != host.lastShown) host.show(content)
        host.schedule(WidgetRefresh.nextWake(now, zone(), boundaries, countdown))
    }

    // A failed read never blanks a widget that had good text; one that has shown nothing yet gets the placeholder.
    private fun failed(now: Long) {
        if (host.lastShown == null) host.show(WidgetWords.placeholder())
        host.schedule(WidgetRefresh.Wake(now + WidgetRefresh.RETRY_AFTER_MS, WidgetRefresh.Kind.MINUTE))
    }
}
