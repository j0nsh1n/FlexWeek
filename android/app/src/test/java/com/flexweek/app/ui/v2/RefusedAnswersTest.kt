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
import org.junit.Assert.assertTrue
import kotlinx.coroutines.asCoroutineDispatcher
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RefusedAnswersTest {
    @get:org.junit.Rule val main = com.flexweek.app.testing.MainThreadRule()

    @Test fun aRefusedAcceptShowsTheReasonInPlaceOfAPlanWithADeadButton() {
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun acceptPlan(previewId: String, opId: String) = """{"ok":false,"error":"The week changed on another device. Plan again."}"""
        }
        var accepted = false
        val vm = PlanRecordViewModel(core, onAccepted = { accepted = true }, onDismiss = {}, workerDispatcher = main.dispatcher)
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
        val vm = PlanRecordViewModel(core, onAccepted = {}, onDismiss = {}, workerDispatcher = main.dispatcher)
        assertNull(vm.record)
        assertEquals("This week is over, so nothing was planned.", vm.error)
    }

    @Test fun aRefusedMoveItShowsTheReason() {
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun acceptRunningLate(previewId: String, opId: String) = """{"ok":false,"error":"The week changed on another device."}"""
        }
        var accepted = false
        val vm = RunningLateViewModel(core, onAccepted = { accepted = true }, onDismiss = {}, workerDispatcher = main.dispatcher)
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

class ThreadingTest {
    @get:org.junit.Rule val main = com.flexweek.app.testing.MainThreadRule()

    private fun offMain(calls: MutableList<Boolean>, uiThread: Thread) { calls += Thread.currentThread() !== uiThread }

    // A worker dispatcher on its own thread stands for Dispatchers.IO: every engine call must run on it.
    @Test fun planRunningLateAddAndWeekCallTheEngineOffTheMainThread() {
        val executor = java.util.concurrent.Executors.newSingleThreadExecutor()
        try {
            val worker = executor.asCoroutineDispatcher()
            val uiThread = Thread.currentThread()
            val calls = java.util.Collections.synchronizedList(mutableListOf<Boolean>())
            val delegate = FakeFlexWeekCore()
            val core = object : FlexWeekCore by delegate {
                override fun planWeek(weekStart: String): String { offMain(calls, uiThread); return delegate.planWeek(weekStart) }
                override fun runningLate(dayIndex: Int, minutes: Int, opId: String): String { offMain(calls, uiThread); return delegate.runningLate(dayIndex, minutes, opId) }
                override fun saveHomework(draftJson: String, opId: String): String { offMain(calls, uiThread); return delegate.saveHomework(draftJson, opId) }
                override fun weekRows(weekStart: String): String { offMain(calls, uiThread); return delegate.weekRows(weekStart) }
            }
            PlanRecordViewModel(core, {}, {}, workerDispatcher = worker)
            val late = RunningLateViewModel(core, {}, {}, workerDispatcher = worker)
            late.pickMinutes(15)
            val week = WeekViewModel(core, worker)
            val add = AddHomeworkViewModel(core, worker) {}
            add.onTitleChange("Lab report")
            add.onEstimate(60)
            add.save()
            executor.shutdown()
            assertTrue("engine calls did not finish", executor.awaitTermination(5, java.util.concurrent.TimeUnit.SECONDS))
            assertEquals("plan, two late steps, week, save", 5, calls.size)
            assertTrue("every engine call leaves the main thread: $calls", calls.all { it })
        } finally {
            executor.shutdownNow()
        }
    }
}

class RefusedTicksTest {
    @get:org.junit.Rule val main = com.flexweek.app.testing.MainThreadRule()

    private fun core(refuse: Boolean = true) = object : FlexWeekCore by FakeFlexWeekCore() {
        override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
            if (refuse) throw IllegalStateException("block was not found")
        }
    }

    // A wrapped fake is not `is FakeFlexWeekCore`, so the view model reads the real clock; pin it to the demo's
    // afternoon, or after about 18:45 the unticked homework is the Now card instead of a row.
    private fun today(core: FlexWeekCore) =
        TodayViewModel(core, workerDispatcher = main.dispatcher).also { it.tick(com.flexweek.app.core.DemoSchedule.DEMO_NOW_MINUTE) }

    @Test fun aTickTheEngineRefusesShowsItsMessageInsteadOfCrashing() {
        val vm = today(core())
        vm.toggleHomework("gone")
        assertEquals("block was not found", vm.uiState.snackbar?.message)
    }

    @Test fun anUndoTheEngineRefusesShowsItsMessage() {
        var refuseNow = false
        val delegate = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
                if (refuseNow) throw IllegalStateException("day is not one of the block's days")
            }
        }
        val vm = today(delegate)
        val row = vm.uiState.rows.filterIsInstance<com.flexweek.app.model.AgendaRow.Item>().first { it.homework && !it.done }
        vm.toggleHomework(row.id)
        refuseNow = true
        vm.undoLast()
        assertEquals("day is not one of the block's days", vm.uiState.snackbar?.message)
    }

    @Test fun aRefusedEarlyCreditStillEndsTheTimerAndSaysWhy() {
        val finished = core(refuse = false).let { delegate ->
            object : FlexWeekCore by delegate {
                override fun focusFinish() = """{"ok":false,"error":"homework was not found"}"""
            }
        }
        val vm = today(finished)
        vm.endFocus()
        assertNull(vm.focusState)
        assertEquals("homework was not found", vm.uiState.snackbar?.message)
    }

    @Test fun aTickedSessionSaysSessionMarkedDone() {
        val vm = today(core(refuse = false))
        val row = vm.uiState.rows.filterIsInstance<com.flexweek.app.model.AgendaRow.Item>().first { it.homework && !it.done }
        vm.toggleHomework(row.id)
        assertEquals("Session marked done", vm.uiState.snackbar?.message)
    }
}
