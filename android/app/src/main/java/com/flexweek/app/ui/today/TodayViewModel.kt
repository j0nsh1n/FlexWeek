package com.flexweek.app.ui.today

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.SyncState
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.SnackbarState
import com.flexweek.app.model.TodayJson
import com.flexweek.app.model.TodayUiState
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class TodayViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var uiState by mutableStateOf(emptyToday())
        private set

    private var nowMinute =
        if (core is FakeFlexWeekCore) DemoSchedule.DEMO_NOW_MINUTE
        else java.time.LocalTime.now().let { it.hour * 60 + it.minute }
    private var pendingUndo: Pair<String, Boolean>? = null

    init {
        refresh()
    }

    fun tick(nowMinute: Int) {
        this.nowMinute = nowMinute
        refresh()
    }

    fun selectDay(index: Int) {
        if (core is FakeFlexWeekCore) {
            core.selectDay(index)
            refresh()
        } else {
            viewModelScope.launch {
                val parsed = withContext(workerDispatcher) {
                    core.selectDay(index)
                    readToday()
                }
                uiState = parsed.copy(snackbar = uiState.snackbar)
            }
        }
    }

    fun jumpToToday() {
        if (core is FakeFlexWeekCore) selectDay(core.currentDayIndex())
        else viewModelScope.launch { selectDay(withContext(workerDispatcher) { core.currentDayIndex() }) }
    }

    fun toggleHomework(id: String) {
        if (core !is FakeFlexWeekCore) {
            viewModelScope.launch {
                val result = withContext(workerDispatcher) {
                    val current = TodayJson.parse(core.today(core.selectedDate(), nowMinute))
                    val row = current.rows.filterIsInstance<com.flexweek.app.model.AgendaRow.Item>().find { it.id == id }
                    val newDone = row?.done != true
                    core.setHomeworkDone(id, newDone, newOpId())
                    newDone to readToday()
                }
                val (newDone, parsed) = result
                pendingUndo = if (newDone) id to true else null
                uiState = parsed.copy(
                    snackbar = if (newDone) SnackbarState("Marked finished", id) else null,
                )
            }
            return
        }
        val json = core.today(todayIso(), nowMinute)
        val current = TodayJson.parse(json)
        val row = current.rows.filterIsInstance<com.flexweek.app.model.AgendaRow.Item>().find { it.id == id }
        val wasDone = row?.done == true
        val newDone = !wasDone
        core.setHomeworkDone(id, newDone, newOpId())
        pendingUndo = if (newDone) id to true else null
        refresh(
            snackbar =
                if (newDone) {
                    SnackbarState("Marked finished", id)
                } else {
                    null
                },
        )
    }

    fun undoLast() {
        val pending = pendingUndo ?: return
        if (core !is FakeFlexWeekCore) {
            viewModelScope.launch {
                val parsed = withContext(workerDispatcher) {
                    core.setHomeworkDone(pending.first, !pending.second, newOpId())
                    readToday()
                }
                pendingUndo = null
                uiState = parsed.copy(snackbar = null)
            }
            return
        }
        core.setHomeworkDone(pending.first, !pending.second, newOpId())
        pendingUndo = null
        refresh(snackbar = null)
    }

    fun dismissSnackbar() {
        pendingUndo = null
        refresh(snackbar = null)
    }

    fun setSyncStateForDemo(state: SyncState) {
        (core as? FakeFlexWeekCore)?.setSyncState(state)
        refresh()
    }

    fun refreshAgenda(snackbar: SnackbarState? = uiState.snackbar) {
        refresh(snackbar)
    }

    fun showMessage(message: String) {
        refresh(snackbar = SnackbarState(message, null))
    }

    private fun refresh(snackbar: SnackbarState? = uiState.snackbar) {
        if (core !is FakeFlexWeekCore) {
            viewModelScope.launch {
                val parsed = withContext(workerDispatcher) { readToday() }
                uiState = parsed.copy(snackbar = snackbar)
            }
            return
        }
        val parsed = TodayJson.parse(core.today(todayIso(), nowMinute))
        uiState = parsed.copy(snackbar = snackbar)
    }

    private fun readToday(): TodayUiState = TodayJson.parse(core.today(core.selectedDate(), nowMinute))

    private fun todayIso(): String = core.selectedDate()

    private fun emptyToday(): TodayUiState =
        TodayUiState(
            title = "Today",
            daySubtitle = null,
            showTodayJump = false,
            days = emptyList(),
            rows = emptyList(),
            noTime = emptyList(),
            noTimeCount = 0,
            syncLine = com.flexweek.app.model.SyncLine("synced", ""),
        )
}
