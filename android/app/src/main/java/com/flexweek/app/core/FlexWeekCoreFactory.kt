package com.flexweek.app.core

import android.content.Context

object FlexWeekCoreFactory {
    fun create(context: Context, onDataChanged: (String) -> Unit): FlexWeekCore {
        System.loadLibrary("flexweek_ffi")
        return RealFlexWeekCore(context, onDataChanged)
    }
}
