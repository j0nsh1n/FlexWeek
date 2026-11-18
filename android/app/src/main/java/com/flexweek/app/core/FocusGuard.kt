package com.flexweek.app.core

import com.flexweek.app.model.FocusJson
import org.json.JSONObject

/** A paused timer has not run to its end, so nothing may finish it and credit a full session. */
object FocusGuard {
    fun isPaused(saved: String): Boolean = FocusJson.parseState(saved)?.running == false

    /** The answer to give instead of finishing a paused timer, or null when finishing may go ahead. */
    fun holdIfPaused(saved: String, completed: Boolean): String? =
        if (completed && isPaused(saved)) JSONObject().put("state", JSONObject(saved)).toString() else null
}
