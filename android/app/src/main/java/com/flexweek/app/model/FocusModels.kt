package com.flexweek.app.model

import org.json.JSONObject

data class FocusUiState(
    val assignmentId: String,
    val title: String,
    val phase: String,
    val running: Boolean,
    val endsAt: Long,
    val remainingMs: Long,
    val workMin: Int,
) {
    fun remaining(nowMs: Long): Long = if (running) (endsAt - nowMs).coerceAtLeast(0) else remainingMs.coerceAtLeast(0)

    /** Whole minutes of the work session already spent, running or paused; a break has none. */
    fun elapsedMin(nowMs: Long): Int =
        if (phase != "work") 0 else ((workMin * 60_000L - remaining(nowMs)) / 60_000L).toInt().coerceAtLeast(0)
}

/** What ending a session early credits, the same whole minutes the End question promises. */
data class EarlyCredit(val assignmentId: String, val minutes: Int, val operation: String)

object FocusJson {
    fun countdown(milliseconds: Long): String {
        val seconds = (milliseconds.coerceAtLeast(0) + 999) / 1000
        return "%02d:%02d".format(seconds / 60, seconds % 60)
    }

    fun parseState(json: String): FocusUiState? {
        if (json == "null" || json.isBlank()) return null
        val value = JSONObject(json)
        if (value.isNull("assignmentId") || value.isNull("phase")) return null
        val endsAt = if (value.isNull("endsAt")) 0L else value.getLong("endsAt")
        val running = !value.isNull("endsAt") && value.optBoolean("running", true)
        return FocusUiState(
            assignmentId = value.getString("assignmentId"),
            title = value.optString("title", "Focus session"),
            phase = value.getString("phase"),
            running = running,
            endsAt = endsAt,
            remainingMs = value.optLong("remainingMs", 0L),
            workMin = value.optInt("workMin", 30),
        )
    }

    fun replaceText(current: String, incoming: String): String =
        "Stop the timer for $current and start $incoming instead?"

    fun finishText(minutes: Int, title: String): String =
        "You've done $minutes min of $title."

    fun parseReplace(json: String): Pair<String, String> {
        val value = JSONObject(json)
        require(value.getString("kind") == "needs_replace")
        return value.getString("current") to value.getString("incoming")
    }

    fun earlyCredit(saved: String, nowMs: Long): EarlyCredit? {
        val state = parseState(saved) ?: return null
        val minutes = state.elapsedMin(nowMs)
        if (minutes <= 0) return null
        val session = JSONObject(saved).optString("sessionId", "${state.assignmentId}-${state.endsAt}")
        return EarlyCredit(state.assignmentId, minutes, "focus-early-$session-$minutes")
    }

    fun parseCredit(json: String): JSONObject = JSONObject(json).getJSONObject("assignment")
}

object FocusSheetText {
    const val replaceTitle = "Replace timer"
    const val finishTitle = "End this session?"
    const val keepCurrent = "Keep current timer"
    const val replace = "Replace timer"
    const val keepGoing = "Keep going"
    const val endSession = "End session"
}
