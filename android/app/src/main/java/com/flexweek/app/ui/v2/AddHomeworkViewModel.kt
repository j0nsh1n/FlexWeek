package com.flexweek.app.ui.v2

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.HomeworkDraft
import com.flexweek.app.model.DueChips
import com.flexweek.app.model.V2Json
import org.json.JSONObject
import java.time.LocalDate

class AddHomeworkViewModel(
    private val core: FlexWeekCore,
    private val onSaved: (String) -> Unit,
) : ViewModel() {
    val recentTitles: List<String> = core.recentTitles()
    var draft by mutableStateOf(HomeworkDraft())
        private set

    init {
        draft = draft.copy(due = DueChips.forToday(LocalDate.now()).first().date.toString())
    }

    var stepProblem: String? by mutableStateOf(null)
        private set

    fun onTitleChange(value: String) {
        draft = draft.copy(title = value, tried = false)
        stepProblem = null
    }

    fun onRecentTitle(value: String) = onTitleChange(value)

    fun onDuePick(value: String) {
        draft = draft.copy(due = value)
    }

    fun onWhenMode(value: String) {
        draft = draft.copy(whenMode = value)
    }

    fun onEstimate(value: Int) {
        draft = draft.copy(estimateMin = value)
    }

    fun onSessions(value: String) {
        draft = draft.copy(sessions = value)
    }

    fun goToStep(step: Int) {
        draft = draft.copy(step = step.coerceIn(0, 2), tried = false)
        stepProblem = null
    }

    fun nextOrSave() {
        when (draft.step) {
            0 -> {
                draft = draft.copy(tried = true)
                if (draft.title.trim().isEmpty()) {
                    stepProblem = "Give the homework a title."
                    return
                }
                stepProblem = null
                draft = draft.copy(step = 1, tried = false)
            }
            1 -> {
                stepProblem = null
                draft = draft.copy(step = 2, tried = false)
            }
            else -> save()
        }
    }

    fun back() {
        if (draft.step > 0) {
            draft = draft.copy(step = draft.step - 1, tried = false)
            stepProblem = null
        }
    }

    private fun save() {
        val result = JSONObject(core.saveHomework(V2Json.homeworkDraftJson(draft), newOpId()))
        if (!result.optBoolean("ok", false)) {
            stepProblem = result.optString("error", "Could not save.")
            return
        }
        onSaved(result.optString("message", "Homework added."))
    }
}
