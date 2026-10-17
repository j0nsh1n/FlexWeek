package com.flexweek.app.ui.today

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.SyncState
import com.flexweek.app.model.AgendaRow
import com.flexweek.app.core.FlexWeekCore
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TodayViewModelTest {
    private val core = FakeFlexWeekCore()

    @Test
    fun tickUpdatesMinutesLabelWithoutAddingRows() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        val before = vm.uiState.rows.size
        vm.tick(DemoSchedule.DEMO_NOW_MINUTE + 5)
        val nowAfter = vm.uiState.rows.filterIsInstance<AgendaRow.Now>().single()
        assertEquals("in 15 min", nowAfter.minsLabel)
        assertEquals(before, vm.uiState.rows.size)
    }

    @Test
    fun toggleHomeworkShowsUndoThenRestores() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        val essayBefore = vm.uiState.rows.filterIsInstance<AgendaRow.Item>().find { it.id == "essay" }
        assertFalse(essayBefore!!.done)
        vm.toggleHomework("essay")
        assertNotNull(vm.uiState.snackbar)
        val doneRow = vm.uiState.rows.filterIsInstance<AgendaRow.Item>().find { it.id == "essay" }
        assertTrue(doneRow!!.done)
        vm.undoLast()
        val undone = vm.uiState.rows.filterIsInstance<AgendaRow.Item>().find { it.id == "essay" }
        assertFalse(undone!!.done)
        assertEquals(null, vm.uiState.snackbar)
    }

    @Test
    fun daySwitchChangesTitle() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        vm.selectDay(1)
        assertEquals("Tuesday", vm.uiState.title)
        assertTrue(vm.uiState.showTodayJump)
    }

    @Test
    fun nowRowOffersRunningLateWhileHomeworkRemains() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        val beforeSoccer = vm.uiState.rows.filterIsInstance<AgendaRow.Now>().single()
        assertEquals(true, beforeSoccer.showRunningLate)
        assertEquals(false, beforeSoccer.showFinishFocus)
        vm.tick(17 * 60 + 30)
        val essayUpNext = vm.uiState.rows.filterIsInstance<AgendaRow.Now>().single()
        assertEquals("essay", essayUpNext.id)
        assertEquals(true, essayUpNext.showFinishFocus)
        assertEquals(true, essayUpNext.showRunningLate)
    }

    @Test
    fun startWithoutConfirmationDoesNotChangeTheTimer() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        vm.startFocus("essay")
        val first = vm.focusState
        assertEquals("essay", first?.assignmentId)
        vm.startFocus("bio")
        assertEquals(first, vm.focusState)
        assertEquals("History essay" to "Bio reading", vm.replacePrompt)
    }

    @Test
    fun syncStatesSurfaceInSyncLine() {
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = TodayViewModel(core)
        assertEquals("synced", vm.uiState.syncLine.state)
        vm.setSyncStateForDemo(SyncState.SYNCING)
        assertEquals("syncing", vm.uiState.syncLine.state)
        assertEquals("Syncing…", vm.uiState.syncLine.line)
        vm.setSyncStateForDemo(SyncState.UNREACHABLE)
        assertTrue(vm.uiState.syncLine.line.contains("Your computer isn't reachable"))
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun rustTodayReadsAndHomeworkWritesRunOffTheMainThread() {
        val mainDispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(mainDispatcher)
        try {
            val uiThread = Thread.currentThread()
            val calledOffMain = AtomicBoolean(true)
            val writeFinished = CountDownLatch(1)
            val delegate = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
            val core = object : FlexWeekCore by delegate {
                override fun selectedDate(): String {
                    calledOffMain.compareAndSet(true, Thread.currentThread() !== uiThread)
                    return delegate.selectedDate()
                }

                override fun today(date: String, nowMinute: Int): String {
                    calledOffMain.compareAndSet(true, Thread.currentThread() !== uiThread)
                    return delegate.today(date, nowMinute)
                }

                override fun setHomeworkDone(id: String, done: Boolean, opId: String) {
                    calledOffMain.compareAndSet(true, Thread.currentThread() !== uiThread)
                    delegate.setHomeworkDone(id, done, opId)
                    writeFinished.countDown()
                }
            }
            val vm = TodayViewModel(core)
            vm.toggleHomework("essay")

            assertTrue("homework write did not finish", writeFinished.await(5, TimeUnit.SECONDS))
            assertTrue("Rust calls must leave the UI thread", calledOffMain.get())
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun assertNotNull(value: Any?) {
        assertTrue(value != null)
    }
}
