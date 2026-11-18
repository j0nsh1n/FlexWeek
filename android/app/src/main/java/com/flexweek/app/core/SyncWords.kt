package com.flexweek.app.core

import org.json.JSONException
import org.json.JSONObject

/** What a failed sync or pairing says, by the engine's stable error kind (NetError::kind). */
object SyncWords {
    const val OFF = "Your computer isn't reachable. Check that FlexWeek is open on it."
    const val NEEDS_UPDATE = "FlexWeek needs an update on this phone or your computer. Update both, then try again."
    const val OTHER = "Sync ran into a problem. Try again in a moment."

    private const val VERSION_TEXT = "unsupported protocol version"
    private val OFF_KINDS = setOf("timeout", "unreachable", "stopped")
    private val UPDATE_KINDS = setOf("version_mismatch")

    fun isOff(kind: String) = kind in OFF_KINDS
    fun needsUpdate(kind: String) = kind in UPDATE_KINDS

    /**
     * The computer's own handler errors (a busy database, a sync that is not making progress) also arrive as
     * "protocol"; only the version answer means something is out of date.
     */
    fun effectiveKind(kind: String, error: String): String =
        if (kind == "protocol" && VERSION_TEXT in error) "version_mismatch" else kind

    fun syncProblem(kind: String, error: String): String = when {
        isOff(kind) -> OFF
        needsUpdate(effectiveKind(kind, error)) -> NEEDS_UPDATE
        error.isBlank() -> OTHER
        else -> "$OTHER ($error)"
    }

    fun pairProblem(kind: String): String = when (kind) {
        "wrong_code" -> "That code didn't match. Check the digits on your computer."
        "bad_code" -> "That code isn't valid. It has 8 digits."
        "timeout", "unreachable", "stopped" -> "Check the code and that FlexWeek is open on both devices."
        "already_linked" -> "This phone is already linked to another FlexWeek account."
        "code_expired" -> "That code has expired. Start a new one on your computer."
        "code_used" -> "That code was already used. Start a new one on your computer."
        "too_many_tries" -> "Too many wrong tries. Start a new code on your computer."
        "version_mismatch" -> NEEDS_UPDATE
        "device_mismatch", "key" ->
            "This phone could not set up its sync key. Restart FlexWeek and try again."
        else -> "Pairing did not finish. Start a new code on your computer and try again."
    }

    /** The error kind to keep after a sync answer: none after a success, the old one after a cancel. */
    fun kindToRemember(answer: String, previous: String?): String? {
        val root = try { JSONObject(answer) } catch (_: JSONException) { return previous }
        if (root.optBoolean("ok", true)) return null
        return when (val kind = root.optString("kind")) {
            "", "cancelled", "not_paired" -> previous
            else -> effectiveKind(kind, root.optString("error"))
        }
    }
}
