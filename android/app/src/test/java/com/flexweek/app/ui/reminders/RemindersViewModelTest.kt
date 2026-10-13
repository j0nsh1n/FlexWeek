package com.flexweek.app.ui.reminders

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

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
}
