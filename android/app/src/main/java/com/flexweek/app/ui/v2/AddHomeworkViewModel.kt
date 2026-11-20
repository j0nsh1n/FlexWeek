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
import com.flexweek.app.core.newOpId
import com.flexweek.app.model.HomeworkDraft
import com.flexweek.app.model.AddHomeworkWords
import com.flexweek.app.model.DueChips
import com.flexweek.app.model.V2Json
import org.json.JSONObject
import java.time.LocalDate

class AddHomeworkViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
    var onSaved: (String) -> Unit,
) : ViewModel() {
    // A nice-to-have row: if the core cannot list them, the sheet opens without it.
    var recentTitles: List<String> by mutableStateOf(emptyList())
        private set
    var draft by mutableStateOf(HomeworkDraft())
        private set
    private var saving = false

    var problem: String? by mutableStateOf(null)
        private set

    init {
        reset()
        viewModelScope.launch {
            recentTitles = withContext(workerDispatcher) { runCatching { core.recentTitles() }.getOrDefault(emptyList()) }
        }
    }

    /** A fresh form, with the due day taken again from today, for the next time Add opens. */
    fun reset() {
        draft = HomeworkDraft(due = DueChips.forToday(LocalDate.now()).first().date.toString())
        problem = null
        saving = false
    }

    fun onTitleChange(value: String) {
        draft = draft.copy(title = value)
        problem = null
    }

    fun onRecentTitle(value: String) = onTitleChange(value)

    fun onDuePick(value: String) {
        draft = draft.copy(due = value)
    }

    fun onEstimate(value: Int) {
        draft = draft.copy(estimateMin = value, otherLength = false)
    }

    /** "Other": the length now comes from the minutes field, empty until the student types one. */
    fun onOtherLength() {
        draft = draft.copy(otherLength = true, estimateMin = 0)
    }

    fun onOtherMinutes(text: String) {
        val minutes = text.filter { it.isDigit() }.take(3).toIntOrNull() ?: 0
        draft = draft.copy(otherLength = true, estimateMin = minutes)
    }

    fun onSessions(value: String) {
        draft = draft.copy(sessions = value)
    }

    fun save() {
        if (!draft.canSave) {
            problem = when {
                draft.title.trim().isEmpty() -> AddHomeworkWords.NEEDS_TITLE
                draft.estimateMin > 0 && !draft.validLength -> AddHomeworkWords.NEEDS_STEPS
                else -> null
            }
            return
        }
        send()
    }

    private fun send() {
        if (saving) return
        saving = true
        val json = V2Json.homeworkDraftJson(draft)
        viewModelScope.launch {
            val result = JSONObject(withContext(workerDispatcher) { core.saveHomework(json, newOpId()) })
            saving = false
            if (!result.optBoolean("ok", false)) {
                problem = result.optString("error", "Could not save.")
                return@launch
            }
            onSaved(result.optString("message", "Homework added."))
        }
    }
}
