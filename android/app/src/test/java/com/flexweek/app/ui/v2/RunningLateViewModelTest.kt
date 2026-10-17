package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class RunningLateViewModelTest {
    private val core = FakeFlexWeekCore()

    @Test
    fun previewListsEssayAndSoccer() {
        var accepted = false
        val vm = RunningLateViewModel(core, onAccepted = { accepted = true }, onDismiss = {})
        assertNotNull(vm.preview)
        assertEquals(2, vm.preview!!.moves.size)
        vm.accept()
        assertEquals(true, accepted)
    }

    @Test
    fun minutesChangeReloadsPreview() {
        val vm = RunningLateViewModel(core, onAccepted = {}, onDismiss = {})
        vm.pickMinutes(15)
        assertEquals(15, vm.minutes)
        assertNotNull(vm.preview)
    }

    @Test
    fun failedPreviewShowsTheCoresMessage() {
        val refusing = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun runningLate(dayIndex: Int, minutes: Int, opId: String) =
                """{"ok":false,"error":"Open this week before using Running late."}"""
        }
        val vm = RunningLateViewModel(refusing, onAccepted = {}, onDismiss = {})
        assertNull(vm.preview)
        assertEquals("Open this week before using Running late.", vm.error)
    }
}
