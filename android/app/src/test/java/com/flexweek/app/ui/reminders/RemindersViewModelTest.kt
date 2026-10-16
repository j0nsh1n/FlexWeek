package com.flexweek.app.ui.reminders

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.resetMain
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

@OptIn(ExperimentalCoroutinesApi::class)
class RemindersViewModelTest {
    @Test
    fun leadTimeAndExactTogglePersistInSettings() {
        val core = FakeFlexWeekCore()
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = RemindersViewModel(core)
        vm.setLeadMinutes(15)
        vm.toggleExact()
        assertEquals(15, vm.state.leadMinutes)
        assertEquals(true, vm.state.exactReminders)
        vm.reload()
        assertEquals(15, vm.state.leadMinutes)
    }

    @Test
    fun allowNotificationsHidesBanner() {
        val core = FakeFlexWeekCore()
        core.pairWithCode(DemoSchedule.VALID_PAIR_CODE)
        val vm = RemindersViewModel(core)
        assertTrue(vm.state.showPermissionBanner)
        vm.allowNotifications()
        assertFalse(vm.state.showPermissionBanner)
    }

    @Test fun notNowHidesBannerForNow() {
        val core = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
        val vm = RemindersViewModel(core, FakeReminderPrefs())
        assertTrue(vm.state.showPermissionBanner)
        vm.dismissPermissionBanner()
        assertFalse(vm.state.showPermissionBanner)
    }

    @Test fun notNowIsRememberedOnTheNextLaunch() {
        val core = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
        val prefs = FakeReminderPrefs()
        RemindersViewModel(core, prefs).dismissPermissionBanner()
        assertFalse(RemindersViewModel(core, prefs).state.showPermissionBanner)
    }

    @Test fun deniedNotificationPermissionKeepsBanner() {
        val core = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
        val vm = RemindersViewModel(core, FakeReminderPrefs())
        vm.onNotificationPermissionResult(false)
        assertTrue(vm.state.showPermissionBanner)
    }

    @Test fun grantedNotificationPermissionHidesBanner() {
        val core = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
        val vm = RemindersViewModel(core, FakeReminderPrefs())
        vm.onNotificationPermissionResult(true)
        assertFalse(vm.state.showPermissionBanner)
    }

    @Test fun unpairOffersPairingWhileTheSavedAccountRemains() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            var unlinks = 0
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun isPaired(): Boolean = true
                override fun unlink() { unlinks += 1 }
            }
            val vm = RemindersViewModel(core, workerDispatcher = dispatcher)
            var pairingOffered = false
            vm.unpair { pairingOffered = true }
            assertEquals(1, unlinks)
            assertTrue(pairingOffered)
            assertTrue(core.isPaired())
            assertFalse(vm.state.syncing)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test fun failedUnpairKeepsTheSavedWeekAndShowsTheProblem() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun unlink() { error("Could not unlink. Try again.") }
            }
            val vm = RemindersViewModel(core, workerDispatcher = dispatcher)
            var pairingOffered = false
            vm.unpair { pairingOffered = true }
            assertFalse(pairingOffered)
            assertEquals("Could not unlink. Try again.", vm.state.problem)
            assertFalse(vm.state.syncing)
        } finally {
            Dispatchers.resetMain()
        }
    }
    @Test fun rustReminderReadsAndWritesRunOffTheMainThread() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            val uiThread = Thread.currentThread()
            val calledOffMain = AtomicBoolean(true)
            val settingsRead = CountDownLatch(2)
            val leadWritten = CountDownLatch(1)
            val delegate = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }
            val core = object : FlexWeekCore by delegate {
                override fun settingsForPhone(): String {
                    calledOffMain.compareAndSet(true, Thread.currentThread() !== uiThread)
                    settingsRead.countDown()
                    return delegate.settingsForPhone()
                }

                override fun setLeadMinutes(minutes: Int) {
                    calledOffMain.compareAndSet(true, Thread.currentThread() !== uiThread)
                    delegate.setLeadMinutes(minutes)
                    leadWritten.countDown()
                }
            }
            val vm = RemindersViewModel(core)
            vm.setLeadMinutes(15)

            assertTrue("settings reads did not finish", settingsRead.await(5, TimeUnit.SECONDS))
            assertTrue("lead time write did not finish", leadWritten.await(5, TimeUnit.SECONDS))
            assertTrue("Rust calls must leave the UI thread", calledOffMain.get())
        } finally {
            Dispatchers.resetMain()
        }
    }
}

private class FakeReminderPrefs : ReminderPrefs {
    override var permissionBannerDismissed: Boolean = false
}
