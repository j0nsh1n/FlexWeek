package com.flexweek.app.ui.reminders

/** The Devices row in Settings, from the same sync answer as the top line. */
object DeviceWords {
    const val NOT_LINKED_TITLE = "No computer linked"
    const val NOT_LINKED_LINE = "Your week is saved here. Pair again from your computer."

    fun title(state: RemindersUiState): String = if (state.paired) state.deviceName else NOT_LINKED_TITLE

    fun line(state: RemindersUiState): String {
        if (!state.paired) return NOT_LINKED_LINE
        val since = if (state.pairedAt.isBlank()) "Paired" else "Paired ${state.pairedAt}"
        if (state.reachable) return "$since · reachable"
        val last = if (state.lastSync.isBlank()) "" else " · last synced ${state.lastSync}"
        return "$since · Your computer isn't reachable$last"
    }
}
