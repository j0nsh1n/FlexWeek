package com.flexweek.app.system

import org.json.JSONObject

object FocusAlarmPlan {
    fun endAt(saved: String): Long? {
        if (saved == "null" || saved.isBlank()) return null
        val value = JSONObject(saved)
        return if (value.optBoolean("running", !value.isNull("endsAt")) && !value.isNull("endsAt")) value.optLong("endsAt") else null
    }

    fun rearmOnBoot(saved: String, schedule: (Long) -> Unit): Boolean {
        val endAt = endAt(saved) ?: return false
        schedule(endAt)
        return true
    }
}
