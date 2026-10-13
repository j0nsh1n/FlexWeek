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

    @Test fun unpairOffersPairingWhileTheSavedAccountRemains() {
        val dispatcher = UnconfinedTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            var unlinks = 0
            val core = object : FlexWeekCore by FakeFlexWeekCore() {
                override fun isPaired(): Boolean = true
                override fun unlink() { unlinks += 1 }
            }
            val vm = RemindersViewModel(core, dispatcher)
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
            val vm = RemindersViewModel(core, dispatcher)
            var pairingOffered = false
            vm.unpair { pairingOffered = true }
            assertFalse(pairingOffered)
            assertEquals("Could not unlink. Try again.", vm.state.problem)
            assertFalse(vm.state.syncing)
        } finally {
            Dispatchers.resetMain()
        }
    }
}
