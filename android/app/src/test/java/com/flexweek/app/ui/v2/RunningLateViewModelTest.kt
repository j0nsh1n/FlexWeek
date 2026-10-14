package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
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
}
