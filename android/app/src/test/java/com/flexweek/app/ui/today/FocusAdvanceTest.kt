package com.flexweek.app.ui.today

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.model.FocusUiState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusAdvanceTest {
    private class RecordingCore(delegate: FlexWeekCore) : FlexWeekCore by delegate {
        val completedValues = mutableListOf<Boolean>()
        var advanceAnswer = "{}"

        override fun focusAdvance(completed: Boolean): String {
            completedValues += completed
            return advanceAnswer
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun skipFocusPassesCompletedFalseToTheCore() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        try {
            val core = RecordingCore(FakeFlexWeekCore())
            val vm = TodayViewModel(core, workerDispatcher = UnconfinedTestDispatcher())

            vm.skipFocus()

            assertEquals(listOf(false), core.completedValues)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun skipFocusUpdatesFocusStateToTheReturnedBreakState() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        try {
            val delegate = FakeFlexWeekCore()
            delegate.focusBegin("essay")
            val core = RecordingCore(delegate)
            core.advanceAnswer = BREAK_ANSWER
            val vm = TodayViewModel(core, workerDispatcher = UnconfinedTestDispatcher())
            assertEquals("work", vm.focusState?.phase)

            vm.skipFocus()

            assertEquals(
                FocusUiState(
                    assignmentId = "essay",
                    title = "History essay",
                    phase = "break",
                    running = true,
                    endsAt = 1_755_000_000_000,
                    remainingMs = 0,
                    workMin = 30,
                ),
                vm.focusState,
            )
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun completeFocusPassesCompletedTrueToTheCore() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        try {
            val core = RecordingCore(FakeFlexWeekCore())
            val vm = TodayViewModel(core, workerDispatcher = UnconfinedTestDispatcher())

            vm.completeFocus()

            assertEquals(listOf(true), core.completedValues)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun completeFocusClearsFocusStateWhenTheCoreReturnsNoState() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        try {
            val delegate = FakeFlexWeekCore()
            delegate.focusBegin("essay")
            val core = RecordingCore(delegate)
            core.advanceAnswer = NO_STATE_ANSWER
            val vm = TodayViewModel(core, workerDispatcher = UnconfinedTestDispatcher())
            assertTrue(vm.focusState != null)

            vm.completeFocus()

            assertNull(vm.focusState)
        } finally {
            Dispatchers.resetMain()
        }
    }

    private companion object {
        private val BREAK_ANSWER = """
            {"state":{"assignmentId":"essay","title":"History essay","phase":"break",
            "running":true,"endsAt":1755000000000,"remainingMs":0,"workMin":30},
            "persist":{"assignmentId":"essay","phase":"break"}}
        """.trimIndent()

        private const val NO_STATE_ANSWER = """{"state":null,"persist":null}"""
    }
}
