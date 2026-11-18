package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import java.time.LocalDate

class WeekViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var state by mutableStateOf(WeekRowsState("", "", emptyList()))
        private set

    /** The real date, for the "today" marker. */
    var today by mutableStateOf<LocalDate?>(null)
        private set

    /** Weeks away from the current one: 0 is this week, -1 the week before, 1 the next. */
    var weekOffset by mutableIntStateOf(0)
        private set

    // Only the newest answer is applied, so tapping an arrow twice quickly cannot end on the earlier week.
    private var request = 0

    init {
        refresh()
    }

    fun refresh() {
        val asked = ++request
        val offset = weekOffset
        viewModelScope.launch {
            // The current Monday is read with the rows, so a new week is picked up by the same refresh.
            val (loaded, date) = withContext(workerDispatcher) {
                val monday = LocalDate.parse(core.currentWeekStart()).plusWeeks(offset.toLong())
                V2Json.parseWeekRows(core.weekRows(monday.toString())) to LocalDate.parse(core.currentDate())
            }
            if (asked == request) {
                state = loaded
                today = date
            }
        }
    }

    fun previousWeek() = moveTo(weekOffset - 1)

    fun nextWeek() = moveTo(weekOffset + 1)

    fun thisWeek() = moveTo(0)

    private fun moveTo(offset: Int) {
        weekOffset = offset
        refresh()
    }
}
