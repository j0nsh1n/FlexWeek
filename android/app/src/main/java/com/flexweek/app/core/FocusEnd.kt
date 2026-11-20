package com.flexweek.app.core

import org.json.JSONObject

/** Ending a timer always ends it; a refused early credit (its homework may be gone) only adds a message. */
object FocusEnd {
    fun run(credit: () -> Unit, finish: () -> String, clearSavedTimer: () -> Unit, refusalText: (Exception) -> String): String {
        val refusal = try {
            credit()
            null
        } catch (error: Exception) {
            refusalText(error)
        }
        val answer = JSONObject(finish())
        clearSavedTimer()
        if (!answer.has("ok")) answer.put("ok", true)
        if (refusal != null) answer.put("ok", false).put("error", refusal)
        return answer.toString()
    }
}
