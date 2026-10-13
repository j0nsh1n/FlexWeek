package com.flexweek.app.core

import android.content.Context
import java.io.File

object FlexWeekCoreFactory {
    fun create(context: Context): FlexWeekCore {
        val jniDir = File(context.applicationInfo.nativeLibraryDir)
        val hasFfi = jniDir.listFiles()?.any { it.name == "libflexweek_ffi.so" } == true
        return if (hasFfi) {
            error("libflexweek_ffi.so is present but the UniFFI bridge is not wired in this slice yet")
        } else {
            FakeFlexWeekCore()
        }
    }
}
