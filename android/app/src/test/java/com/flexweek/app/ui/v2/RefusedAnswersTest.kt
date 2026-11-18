package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.ui.reminders.RemindersViewModel
import com.flexweek.app.ui.today.TodayViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RefusedAnswersTest {
    @Test fun aRefusedAcceptShowsTheReasonInPlaceOfAPlanWithADeadButton() {
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun acceptPlan(previewId: String, opId: String) = """{"ok":false,"error":"The week changed on another device. Plan again."}"""
        }
        var accepted = false
        val vm = PlanRecordViewModel(core, onAccepted = { accepted = true }, onDismiss = {})
        assertNotNull(vm.record)
        vm.accept()
        assertEquals(false, accepted)
        assertNull(vm.record)
        assertEquals("The week changed on another device. Plan again.", vm.error)
    }

    @Test fun aPlanThatCannotPlaceShowsItsMessage() {
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun planWeek(weekStart: String) = """{"ok":false,"error":"This week is over, so nothing was planned."}"""
        }
        val vm = PlanRecordViewModel(core, onAccepted = {}, onDismiss = {})
        assertNull(vm.record)
        assertEquals("This week is over, so nothing was planned.", vm.error)
    }

    @Test fun aRefusedMoveItShowsTheReason() {
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun acceptRunningLate(previewId: String, opId: String) = """{"ok":false,"error":"The week changed on another device."}"""
        }
        var accepted = false
        val vm = RunningLateViewModel(core, onAccepted = { accepted = true }, onDismiss = {})
        vm.accept()
        assertEquals(false, accepted)
        assertEquals("The week changed on another device.", vm.error)
    }

    @Test fun aRefusedStartFocusShowsTheReason() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun focusBegin(assignmentId: String, replace: Boolean) = """{"ok":false,"error":"homework was not found"}"""
            }
            val vm = TodayViewModel(core, workerDispatcher = dispatcher)
            vm.startFocus("gone")
            assertEquals("homework was not found", vm.uiState.snackbar?.message)
            assertNull(vm.focusState)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test fun aFailedSyncNowShowsTheEnginesMessage() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun syncOnce(deadlineMs: Long) = """{"ok":false,"kind":"timeout","error":"the sync took too long and was stopped"}"""
            }
            val vm = RemindersViewModel(core, workerDispatcher = dispatcher)
            vm.syncNow()
            assertEquals(com.flexweek.app.core.SyncWords.OFF, vm.state.problem)
        } finally {
            Dispatchers.resetMain()
        }
    }
}
