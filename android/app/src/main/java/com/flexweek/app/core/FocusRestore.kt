package com.flexweek.app.core

import org.json.JSONObject

internal object FocusRestore {
    /**
     * The saved timer to keep after opening, or null to drop it. A timer whose homework is gone makes the core
     * refuse to restore it; keeping it would fail the same way at every launch and the app would never open.
     */
    fun keep(saved: String, restore: (String) -> String): String? {
        val answer = try {
            JSONObject(restore(saved))
        } catch (_: com.flexweek.app.bindings.FfiException) {
            return null
        } catch (_: org.json.JSONException) {
            return null
        }
        val persisted = answer.opt("persist")
        return if (persisted == null || persisted == JSONObject.NULL) null else persisted.toString()
    }
}
