package com.flexweek.app.system

/**
 * Everything on screen that shows synced data, refreshed after each foreground sync. The Week tab was
 * left out once, so it kept the old week until the app restarted and never rolled over on a Monday.
 */
internal class SyncRefresh(
    private val today: (nowMinute: Int) -> Unit,
    private val settings: () -> Unit,
    private val week: () -> Unit,
    private val widget: () -> Unit,
) {
    fun afterSync(nowMinute: Int) {
        today(nowMinute)
        settings()
        week()
        widget()
    }
}
