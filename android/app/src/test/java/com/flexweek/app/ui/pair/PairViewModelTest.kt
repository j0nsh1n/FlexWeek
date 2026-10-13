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
    @After fun tearDown() { Dispatchers.resetMain() }
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
            "That code didn't match. Codes last 5 minutes; ask your computer for a new one.",
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
    }
}
