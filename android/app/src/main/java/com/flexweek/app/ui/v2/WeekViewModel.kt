package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.model.V2Json
import com.flexweek.app.model.WeekRowsState

class WeekViewModel(
    private val core: FlexWeekCore,
) : ViewModel() {
    var state by mutableStateOf(WeekRowsState("", "", emptyList()))
        private set

    init {
        refresh()
    }

    fun refresh() {
        state = V2Json.parseWeekRows(core.weekRows(core.currentWeekStart()))
    }
}
