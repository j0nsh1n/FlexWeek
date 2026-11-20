package com.flexweek.app.ui.reminders

import android.app.AlarmManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationManagerCompat

/** What Android says now about notifications and exact alarms; asked each time, never remembered here. */
interface SystemPermissions {
    fun notificationsAllowed(): Boolean
    fun canScheduleExact(): Boolean
}

/** For places with no Android to ask (tests, previews): notifications off, exact alarms on. */
object UnknownPermissions : SystemPermissions {
    override fun notificationsAllowed() = false
    override fun canScheduleExact() = true
}

class AndroidPermissions(context: Context) : SystemPermissions {
    private val app = context.applicationContext
    override fun notificationsAllowed() = NotificationManagerCompat.from(app).areNotificationsEnabled()
    override fun canScheduleExact(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S || app.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
}

object PermissionBanner {
    const val REOFFER_AFTER_MS = 3L * 24 * 60 * 60 * 1000

    /** Shown while Android has notifications off; "Not now" hides it for a few days, not for good. */
    fun show(allowed: Boolean, dismissedAtMs: Long, nowMs: Long): Boolean =
        !allowed && (dismissedAtMs == 0L || nowMs - dismissedAtMs >= REOFFER_AFTER_MS)
}

/** What the Allow button does: ask once, then send the student to Android's own switch. */
object NotificationAsk {
    enum class Step { Ask, OpenSystemSettings }

    fun next(askedBefore: Boolean, canAskAgain: Boolean): Step =
        if (!askedBefore || canAskAgain) Step.Ask else Step.OpenSystemSettings
}
