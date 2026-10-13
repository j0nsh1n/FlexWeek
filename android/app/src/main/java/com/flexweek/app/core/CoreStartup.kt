package com.flexweek.app.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

suspend fun FlexWeekCore.openForPhone(dbPath: String): Boolean = withContext(Dispatchers.IO) {
    open(dbPath, "Phone")
    isPaired()
}
