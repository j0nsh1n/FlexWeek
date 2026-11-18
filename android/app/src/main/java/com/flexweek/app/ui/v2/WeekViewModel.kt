package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.model.V2Json
import com.flexweek.app.model.WeekRowsState

class WeekViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var state by mutableStateOf(WeekRowsState("", "", emptyList()))
        private set

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            // The week start is read with the rows, so a new Monday is picked up by the same refresh.
            state = withContext(workerDispatcher) { V2Json.parseWeekRows(core.weekRows(core.currentWeekStart())) }
        }
    }
}
