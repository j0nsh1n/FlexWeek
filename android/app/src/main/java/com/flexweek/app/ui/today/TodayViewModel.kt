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
import com.flexweek.app.model.FocusJson
import com.flexweek.app.model.FocusUiState
import org.json.JSONObject
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val MARKED_DONE = "Session marked done"

class TodayViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    var uiState by mutableStateOf(emptyToday())
        private set

    var focusState by mutableStateOf(FocusJson.parseState(core.focusState()))
        private set
    var replacePrompt by mutableStateOf<Pair<String, String>?>(null)
        private set
    var finishPrompt by mutableStateOf(false)
        private set
    private var replaceAssignmentId: String? = null

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
                    try {
                        val current = TodayJson.parse(core.today(core.selectedDate(), nowMinute))
                        val row = current.rows.filterIsInstance<com.flexweek.app.model.AgendaRow.Item>().find { it.id == id }
                        val newDone = row?.done != true
                        core.setHomeworkDone(id, newDone, newOpId())
                        newDone to readToday()
                    } catch (error: Exception) {
                        if (error is kotlinx.coroutines.CancellationException) throw error
                        // The session may have moved or gone on the computer after this screen was drawn.
                        refusalText(error)
                    }
                }
                if (result is String) {
                    pendingUndo = null
                    refresh(snackbar = SnackbarState(result, null))
                    return@launch
                }
                @Suppress("UNCHECKED_CAST")
                val (newDone, parsed) = result as Pair<Boolean, TodayUiState>
                pendingUndo = if (newDone) id to true else null
                uiState = parsed.copy(
                    snackbar = if (newDone) SnackbarState(MARKED_DONE, id) else null,
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
                    SnackbarState(MARKED_DONE, id)
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
                    try {
                        core.setHomeworkDone(pending.first, !pending.second, newOpId())
                        readToday()
                    } catch (error: Exception) {
                        if (error is kotlinx.coroutines.CancellationException) throw error
                        refusalText(error)
                    }
                }
                pendingUndo = null
                if (parsed is String) refresh(snackbar = SnackbarState(parsed, null))
                else uiState = (parsed as TodayUiState).copy(snackbar = null)
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

    fun startFocus(assignmentId: String) {
        if (core is FakeFlexWeekCore) applyStart(core.focusBegin(assignmentId), core.focusState(), assignmentId)
        else viewModelScope.launch {
            val answer = withContext(workerDispatcher) { core.focusBegin(assignmentId) to core.focusState() }
            applyStart(answer.first, answer.second, assignmentId)
        }
    }

    private fun applyStart(raw: String, saved: String, assignmentId: String) {
        val answer = JSONObject(raw)
        if (!answer.optBoolean("ok", true)) {
            showMessage(answer.optString("error").ifBlank { "Could not start focus." })
        } else if (answer.optString("kind") == "needs_replace") {
            replaceAssignmentId = assignmentId
            replacePrompt = answer.getString("current") to answer.getString("incoming")
        } else focusState = FocusJson.parseState(saved)
    }

    fun keepCurrentFocus() {
        replacePrompt = null
        replaceAssignmentId = null
    }

    fun replaceFocus() {
        val incoming = replaceAssignmentId ?: return
        replacePrompt = null
        replaceAssignmentId = null
        if (core is FakeFlexWeekCore) {
            core.focusBegin(incoming, replace = true)
            focusState = FocusJson.parseState(core.focusState())
        } else viewModelScope.launch {
            val saved = withContext(workerDispatcher) {
                core.focusBegin(incoming, replace = true)
                core.focusState()
            }
            focusState = FocusJson.parseState(saved)
        }
    }

    fun pauseFocus() {
        if (core is FakeFlexWeekCore) {
            core.focusPause()
            focusState = FocusJson.parseState(core.focusState())
        } else viewModelScope.launch {
            focusState = FocusJson.parseState(withContext(workerDispatcher) {
                core.focusPause()
                core.focusState()
            })
        }
    }

fun skipFocus() = advanceFocus(completed = false)

    fun completeFocus() = advanceFocus(completed = true)

    private fun advanceFocus(completed: Boolean) {
        if (core is FakeFlexWeekCore) applyAdvance(core.focusAdvance(completed))
        else viewModelScope.launch {
            applyAdvance(withContext(workerDispatcher) { core.focusAdvance(completed) })
        }
    }

    private fun applyAdvance(raw: String) {
        val answer = JSONObject(raw)
        focusState = if (answer.isNull("state")) null
        else FocusJson.parseState(answer.getJSONObject("state").toString())
    }

    fun askFinishFocus() { finishPrompt = focusState != null }

    fun keepGoing() { finishPrompt = false }

    fun endFocus() {
        if (core is FakeFlexWeekCore) {
            core.focusFinish()
            focusState = null
            finishPrompt = false
        } else viewModelScope.launch {
            val answer = withContext(workerDispatcher) { core.focusFinish() }
            focusState = null
            finishPrompt = false
            // The timer is over either way; a refused early credit only says why the minutes were not added.
            runCatching { JSONObject(answer) }.getOrNull()?.takeIf { !it.optBoolean("ok", true) }?.let {
                refresh(snackbar = SnackbarState(it.optString("error", "The minutes could not be added."), null))
            }
        }
    }

    private fun refusalText(error: Exception): String =
        (error as? com.flexweek.app.bindings.FfiException)?.let(com.flexweek.app.core.RustPhoneJson::ffiText)
            ?: error.message ?: "That could not be saved. Nothing was changed."

    private fun refresh(snackbar: SnackbarState? = uiState.snackbar) {
        if (core !is FakeFlexWeekCore) {
            viewModelScope.launch {
                // The timer is read with the day: the notification's Pause and Finish change it while the card is open.
                val (parsed, saved) = withContext(workerDispatcher) { readToday() to core.focusState() }
                uiState = parsed.copy(snackbar = snackbar)
                focusState = FocusJson.parseState(saved)
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
