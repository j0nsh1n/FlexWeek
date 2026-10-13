package com.flexweek.app.ui.pair

import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import com.flexweek.app.core.FlexWeekCore
import org.json.JSONObject

data class PairUiState(
    val mode: PairInputMode = PairInputMode.Qr,
    val code: String = "",
    val tried: Boolean = false,
    val problem: String? = null,
    val joining: Boolean = false,
)

enum class PairInputMode {
    Qr,
    Code,
}

class PairViewModel(
    private val core: FlexWeekCore,
    private val onPaired: () -> Unit,
) : ViewModel() {
    val uiState = mutableStateOf(PairUiState())

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
        val digits = uiState.value.code.filter { it.isDigit() }
        uiState.value = uiState.value.copy(tried = true)
        if (digits.length != 8) {
            uiState.value =
                uiState.value.copy(
                    problem = "The code has 8 digits. Check your computer's screen.",
                )
            return
        }
        val result = JSONObject(core.pairWithCode(digits))
        if (!result.optBoolean("ok")) {
            uiState.value =
                uiState.value.copy(
                    problem =
                        "That code didn't match. Codes last 5 minutes; ask your computer for a new one.",
                )
            return
        }
        uiState.value = uiState.value.copy(joining = true, problem = null)
        onPaired()
    }

    /** Typed path for tests without a camera. */
    fun pairFromTypedCode(digits: String) {
        uiState.value = uiState.value.copy(code = digits, mode = PairInputMode.Code)
        submitPair()
    }
}
