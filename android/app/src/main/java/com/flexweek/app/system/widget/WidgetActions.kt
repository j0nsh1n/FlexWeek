package com.flexweek.app.system.widget

import android.content.Intent
import com.flexweek.app.core.FlexWeekCore

object WidgetRead {
    /** The phone's own today, never the day Today has selected. */
    fun today(core: FlexWeekCore, nowMinute: Int): String = core.today(core.currentDate(), nowMinute)
}

object WidgetTick {
    /** Today's call: the real core only knows a row's id after it has read the day. */
    fun markFinished(core: FlexWeekCore, id: String, nowMinute: Int, opId: String) {
        WidgetRead.today(core, nowMinute)
        core.setHomeworkDone(id, true, opId)
    }
}

object WidgetTap {
    data class OpenRequest(val flags: Int, val extras: Map<String, String>)

    // A fresh activity starts on Today; extras would steer it elsewhere (they are screenshot switches).
    fun openToday(): OpenRequest = OpenRequest(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP, emptyMap())
}
