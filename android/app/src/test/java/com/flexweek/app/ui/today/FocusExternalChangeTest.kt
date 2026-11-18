package com.flexweek.app.ui.today

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import com.flexweek.app.core.FocusGuard
import com.flexweek.app.testing.MainThreadRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class FocusExternalChangeTest {
    @get:Rule val main = MainThreadRule()

    private val running = """{"assignmentId":"essay","title":"History essay","phase":"work","running":true,"endsAt":1755000600000,"remainingMs":0,"workMin":30,"sessionId":"s1"}"""
    private val paused = """{"assignmentId":"essay","title":"History essay","phase":"work","running":false,"remainingMs":600000,"workMin":30,"sessionId":"s1"}"""

    @Test fun pausingFromTheNotificationShowsOnTheOpenCard() {
        var saved = running
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun focusState() = saved
        }
        val vm = TodayViewModel(core, workerDispatcher = main.dispatcher)
        assertTrue(vm.focusState!!.running)
        saved = paused // the notification's Pause button wrote this while the app was open
        vm.tick(600)
        assertFalse("the card follows the saved timer", vm.focusState!!.running)
    }

    @Test fun aTimerEndedFromTheNotificationLeavesTheCard() {
        var saved = running
        val core = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun focusState() = saved
        }
        val vm = TodayViewModel(core, workerDispatcher = main.dispatcher)
        assertNotNull(vm.focusState)
        saved = "null"
        vm.tick(600)
        assertNull(vm.focusState)
    }

    @Test fun aPausedTimerIsNeverFinishedAsAFullSession() {
        val answer = FocusGuard.holdIfPaused(paused, completed = true)
        assertNotNull("completing a paused timer is refused", answer)
        assertEquals(false, org.json.JSONObject(answer!!).getJSONObject("state").getBoolean("running"))
        assertNull("a running timer may finish", FocusGuard.holdIfPaused(running, completed = true))
        assertNull("skipping credits nothing, so it passes through", FocusGuard.holdIfPaused(paused, completed = false))
        assertTrue(FocusGuard.isPaused(paused))
        assertFalse(FocusGuard.isPaused(running))
        assertFalse(FocusGuard.isPaused("null"))
    }
}
