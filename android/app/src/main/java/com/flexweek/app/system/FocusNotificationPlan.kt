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
        fun action(value: String?): FocusAction? = when (value) {
            "pause", "resume" -> FocusAction.PAUSE
            "finish" -> FocusAction.FINISH
            else -> null
        }
    }
}
