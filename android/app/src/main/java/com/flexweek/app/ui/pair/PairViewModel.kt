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
import java.util.concurrent.atomic.AtomicBoolean

data class PairUiState(
    val mode: PairInputMode = PairInputMode.Qr,
    val code: String = "",
    val tried: Boolean = false,
    val problem: String? = null,
    val joining: Boolean = false,
    val paired: Boolean = false,
    val canScan: Boolean = false,
)

enum class PairInputMode {
    Qr,
    Code,
}

class PairViewModel(
    private val core: FlexWeekCore,
    private val workerDispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val onPaired: () -> Unit = {},
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
        if (uiState.value.joining || uiState.value.paired) return
        val digits = uiState.value.code.filter { it.isDigit() }
        uiState.value = uiState.value.copy(tried = true)
        if (digits.length != 8) {
            uiState.value =
                uiState.value.copy(
                    problem = "The code has 8 digits. Check your computer's screen.",
                )
            return
        }
        if (!pairingInFlight.compareAndSet(false, true)) {
            uiState.value =
                uiState.value.copy(problem = "Pairing is already running. Wait for it to finish.")
            return
        }
        uiState.value = uiState.value.copy(joining = true, problem = null)
        viewModelScope.launch {
            try {
                val result = withContext(workerDispatcher) { JSONObject(core.pairWithCode(digits)) }
                if (result.optBoolean("ok")) {
                    // Drop the code once pairing has succeeded. It is not stored anywhere else.
                    uiState.value = uiState.value.copy(joining = false, paired = true, code = "")
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
            } finally {
                pairingInFlight.set(false)
            }
        }
    }

    /** Typed path for tests without a camera. */
    fun pairFromTypedCode(digits: String) {
        uiState.value = uiState.value.copy(code = digits, mode = PairInputMode.Code)
        submitPair()
    }

    companion object {
        // One pairing for the whole process. A recreated screen must not start a second one.
        private val pairingInFlight = AtomicBoolean(false)

        internal fun resetPairingGateForTest() {
            pairingInFlight.set(false)
        }
    }
}
