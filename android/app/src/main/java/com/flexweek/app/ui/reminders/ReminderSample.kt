package com.flexweek.app.ui.reminders

import com.flexweek.app.core.RustPhoneJson

/** The sample in Settings is built the way a real reminder is: the block's title, and its start and length. */
object ReminderSample {
    const val TITLE = "History essay"

    fun body(): String = RustPhoneJson.reminderBody("19:00", 60)
}
