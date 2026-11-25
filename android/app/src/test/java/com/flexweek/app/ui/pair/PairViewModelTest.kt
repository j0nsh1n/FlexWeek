package com.flexweek.app.ui.pair

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.Before
import org.junit.After
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.ExperimentalCoroutinesApi

@OptIn(ExperimentalCoroutinesApi::class)
class PairViewModelTest {
    private val dispatcher = UnconfinedTestDispatcher()
    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() {
        Dispatchers.resetMain()
        PairViewModel.resetPairingGateForTest()
    }
    @Test
    fun typedDigitsStayInTheOrderTheyWereTyped() {
        // Jonathan, 2026-11-24: typing a code after the fourth digit put digits out of order. The field holds
        // only the digits; the space is drawn, so nothing typed lands on the wrong side of it.
        val vm = PairViewModel(FakeFlexWeekCore(), dispatcher) {}
        vm.showCodeEntry()
        for (digit in "12345678") vm.onCodeChange(vm.uiState.value.code + digit)
        assertEquals("12345678", vm.uiState.value.code)
        vm.onCodeChange("1234 5678 9")
        assertEquals("12345678", vm.uiState.value.code)
    }

    @Test
    fun shortCodeShowsLengthProblem() {
        val core = FakeFlexWeekCore()
        val vm = PairViewModel(core, dispatcher) {}
        vm.showCodeEntry()
        vm.onCodeChange("1234567")
        vm.submitPair()
        assertEquals("The code has 8 digits. Check your computer's screen.", vm.uiState.value.problem)
    }

    @Test
    fun wrongCodeShowsMismatchProblem() {
        val core = FakeFlexWeekCore()
        val vm = PairViewModel(core, dispatcher) {}
        vm.pairFromTypedCode("00000000")
        assertEquals(
            "That code didn't match. Check the digits on your computer.",
            vm.uiState.value.problem,
        )
    }

    @Test
    fun validCodePairs() {
        val core = FakeFlexWeekCore()
        var paired = false
        val vm = PairViewModel(core, dispatcher) { paired = true }
        vm.pairFromTypedCode(DemoSchedule.VALID_PAIR_CODE)
        assertNull(vm.uiState.value.problem)
        assertEquals(true, paired)
        assertEquals(true, core.isPaired())
        assertEquals("", vm.uiState.value.code)
    }

    @Test
    fun pairingWaitsForBackgroundWorkAndIgnoresAnotherSubmit() = runTest {
        val fake = FakeFlexWeekCore()
        var calls = 0
        val core = object : FlexWeekCore by fake {
            override fun pairWithCode(code: String): String {
                calls += 1
                return fake.pairWithCode(code)
            }
        }
        var paired = false
        val vm = PairViewModel(core, StandardTestDispatcher(testScheduler)) { paired = true }
        vm.pairFromTypedCode("48127390")
        vm.submitPair()
        assertEquals(true, vm.uiState.value.joining)
        assertEquals(false, paired)
        assertEquals(0, calls)
        advanceUntilIdle()
        assertEquals(1, calls)
        assertEquals(true, paired)
        assertEquals("", vm.uiState.value.code)
    }

    @Test
    fun aSecondScreenCannotStartPairingWhileTheFirstIsStillRunning() = runTest {
        val fake = FakeFlexWeekCore()
        var calls = 0
        val core = object : FlexWeekCore by fake {
            override fun pairWithCode(code: String): String {
                calls += 1
                return fake.pairWithCode(code)
            }
        }
        val first = PairViewModel(core, StandardTestDispatcher(testScheduler)) {}
        val second = PairViewModel(core, StandardTestDispatcher(testScheduler)) {}
        first.pairFromTypedCode("48127390")
        second.pairFromTypedCode("48127390")
        assertEquals(0, calls)
        assertEquals("Pairing is already running. Wait for it to finish.", second.uiState.value.problem)
        advanceUntilIdle()
        assertEquals(1, calls)
        assertEquals(true, first.uiState.value.paired)
        assertEquals("", first.uiState.value.code)
        assertEquals(false, second.uiState.value.paired)
    }
}
