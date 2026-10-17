package com.flexweek.app.system

import androidx.core.app.NotificationCompat
import org.json.JSONObject

enum class FocusAction { PAUSE, FINISH }

data class FocusNotificationPlan(val header: String, val title: String, val status: String, val whenMs: Long, val countdown: Boolean) {
    companion object {
        const val visibility: Int = NotificationCompat.VISIBILITY_PUBLIC
        fun from(saved: String): FocusNotificationPlan? {
            if (saved == "null" || saved.isBlank()) return null
            val value = JSONObject(saved)
            val running = value.optBoolean("running", !value.isNull("endsAt")) && !value.isNull("endsAt")
            return FocusNotificationPlan(
                "FlexWeek · focus",
                value.optString("title", "Focus session"),
                if (running) "" else "Paused",
                if (running) value.optLong("endsAt") else 0L,
                running,
            )
        }
        /** The end-of-session alert: what was added, never that the homework is finished. */
        fun endWords(saved: String): Pair<String, String> {
            val value = runCatching { JSONObject(saved) }.getOrNull()
            val title = value?.optString("title").orEmpty().ifBlank { "your homework" }
            val minutes = value?.optInt("workMin", 0) ?: 0
            return "Focus session over" to if (minutes > 0) "$minutes min added to $title." else "Time is up for $title."
        }

        fun action(value: String?): FocusAction? = when (value) {
            "pause", "resume" -> FocusAction.PAUSE
            "finish" -> FocusAction.FINISH
            else -> null
        }
    }
}
