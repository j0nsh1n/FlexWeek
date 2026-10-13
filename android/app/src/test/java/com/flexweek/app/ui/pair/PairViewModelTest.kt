package com.flexweek.app.ui.pair

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PairViewModelTest {
    @Test
    fun shortCodeShowsLengthProblem() {
        val core = FakeFlexWeekCore()
        val vm = PairViewModel(core) {}
        vm.showCodeEntry()
        vm.onCodeChange("1234567")
        vm.submitPair()
        assertEquals("The code has 8 digits. Check your computer's screen.", vm.uiState.value.problem)
    }

    @Test
    fun wrongCodeShowsMismatchProblem() {
        val core = FakeFlexWeekCore()
        val vm = PairViewModel(core) {}
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
        val vm = PairViewModel(core) { paired = true }
        vm.pairFromTypedCode(DemoSchedule.VALID_PAIR_CODE)
        assertNull(vm.uiState.value.problem)
        assertEquals(true, paired)
        assertEquals(true, core.isPaired())
    }
}
