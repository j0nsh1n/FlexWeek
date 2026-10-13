package com.flexweek.app.ui.pair

import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class PairUiState(
    val mode: PairInputMode = PairInputMode.Qr,
    val code: String = "",
    val tried: Boolean = false,
    val problem: String? = null,
    val joining: Boolean = false,
    val canScan: Boolean = false,
)

enum class PairInputMode {
    Qr,
    Code,
}

class PairViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val onPaired: () -> Unit,
) : ViewModel() {
    val uiState = mutableStateOf(PairUiState(
        mode = if (core is FakeFlexWeekCore) PairInputMode.Qr else PairInputMode.Code,
        canScan = core is FakeFlexWeekCore,
    ))

    fun showCodeEntry() {
        uiState.value = uiState.value.copy(mode = PairInputMode.Code, problem = null)
    }

    fun showQr() {
        uiState.value = uiState.value.copy(mode = PairInputMode.Qr, problem = null, tried = false)
    }

    fun onCodeChange(raw: String) {
        val digits = raw.filter { it.isDigit() }.take(8)
        val grouped =
            when {
                digits.length <= 4 -> digits
                else -> digits.substring(0, 4) + " " + digits.substring(4)
            }
        uiState.value = uiState.value.copy(code = grouped, problem = null)
    }

    fun submitPair() {
        if (uiState.value.joining) return
        val digits = uiState.value.code.filter { it.isDigit() }
        uiState.value = uiState.value.copy(tried = true)
        if (digits.length != 8) {
            uiState.value =
                uiState.value.copy(
                    problem = "The code has 8 digits. Check your computer's screen.",
                )
            return
        }
        uiState.value = uiState.value.copy(joining = true, problem = null)
        viewModelScope.launch {
            val result = withContext(workerDispatcher) { JSONObject(core.pairWithCode(digits)) }
            if (result.optBoolean("ok")) {
                onPaired()
            } else {
                val problem = when (result.optString("kind")) {
                    "timeout", "unreachable" -> "Check the code and that FlexWeek is open on both devices."
                    "already_linked" -> "This phone is already linked to another FlexWeek account."
                    "code_expired" -> "That code has expired. Start a new one on your computer."
                    "too_many_tries" -> "Too many wrong tries. Start a new code on your computer."
                    else -> "That code didn't match. Codes last 5 minutes; ask your computer for a new one."
                }
                uiState.value = uiState.value.copy(joining = false, problem = problem)
            }
        }
    }

    /** Typed path for tests without a camera. */
    fun pairFromTypedCode(digits: String) {
        uiState.value = uiState.value.copy(code = digits, mode = PairInputMode.Code)
        submitPair()
    }
}
