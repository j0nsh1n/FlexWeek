package com.flexweek.app.ui.reminders

import com.flexweek.app.core.DemoSchedule
import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PermissionStateTest {
    @get:org.junit.Rule val main = com.flexweek.app.testing.MainThreadRule()

    private class Permissions(var notifications: Boolean, var exact: Boolean) : SystemPermissions {
        override fun notificationsAllowed() = notifications
        override fun canScheduleExact() = exact
    }

    private class Prefs : ReminderPrefs {
        override var permissionBannerDismissedAt = 0L
        override var notificationAsked = false
    }

    private fun core() = FakeFlexWeekCore().also { it.pairWithCode(DemoSchedule.VALID_PAIR_CODE) }

    @Test fun theBannerGoesWhenAndroidHasNotificationsOnAndComesBackWhenItDoesNot() {
        val system = Permissions(notifications = false, exact = true)
        val vm = RemindersViewModel(core(), Prefs(), permissions = system)
        assertTrue(vm.state.showPermissionBanner)
        system.notifications = true
        vm.refreshPermissions()
        assertFalse(vm.state.showPermissionBanner)
        system.notifications = false
        vm.refreshPermissions()
        assertTrue(vm.state.showPermissionBanner)
    }

    @Test fun theRemindersSwitchReadsWhatAndroidSaysNotASavedWish() {
        val system = Permissions(notifications = false, exact = true)
        val vm = RemindersViewModel(core(), Prefs(), permissions = system)
        assertFalse(vm.state.notificationsAllowed)
        system.notifications = true
        vm.refreshPermissions()
        assertTrue(vm.state.notificationsAllowed)
        system.notifications = false
        vm.refreshPermissions()
        assertFalse("switching it off in Android's own screen is seen on return", vm.state.notificationsAllowed)
    }

    @Test fun syncNowShowsItsResultUnderTheButton() {
        val vm = RemindersViewModel(core(), Prefs(), main.dispatcher, Permissions(true, true))
        vm.syncNow()
        assertTrue("a sync that worked says so", vm.state.syncedJustNow)
        assertEquals(null, vm.state.problem)
    }

    @Test fun grantedBeforeTheFirstOpenShowsNoBannerAfterAColdStart() {
        val vm = RemindersViewModel(core(), Prefs(), permissions = Permissions(notifications = true, exact = true))
        assertFalse(vm.state.showPermissionBanner)
    }

    @Test fun notNowComesBackAfterAWhileButNotBefore() {
        var now = 1_000_000L
        val prefs = Prefs()
        val system = Permissions(false, true)
        val vm = RemindersViewModel(core(), prefs, permissions = system, clock = { now })
        vm.dismissPermissionBanner()
        assertFalse(vm.state.showPermissionBanner)
        now += PermissionBanner.REOFFER_AFTER_MS - 1
        vm.refreshPermissions()
        assertFalse(vm.state.showPermissionBanner)
        now += 1
        vm.refreshPermissions()
        assertTrue(vm.state.showPermissionBanner)
    }

    @Test fun exactRemindersFollowWhatAndroidAllowsOnReturn() {
        val system = Permissions(true, exact = false)
        val vm = RemindersViewModel(core(), Prefs(), permissions = system)
        var screens = 0
        vm.toggleExact { screens += 1 }
        assertEquals("the system screen opens when it is not allowed", 1, screens)
        assertFalse("the switch does not say on while Android says no", vm.state.exactReminders)
        system.exact = true
        vm.refreshPermissions()
        assertTrue("it reads on once Android allows it", vm.state.exactReminders)
        vm.toggleExact { screens += 1 }
        vm.toggleExact { screens += 1 }
        assertEquals("no screen when it is already allowed", 1, screens)
    }

    @Test fun theAllowButtonAsksOnceThenSendsTheStudentToTheSystemSwitch() {
        assertEquals(NotificationAsk.Step.Ask, NotificationAsk.next(askedBefore = false, canAskAgain = false))
        assertEquals(NotificationAsk.Step.Ask, NotificationAsk.next(askedBefore = true, canAskAgain = true))
        assertEquals(NotificationAsk.Step.OpenSystemSettings, NotificationAsk.next(askedBefore = true, canAskAgain = false))
    }
}
