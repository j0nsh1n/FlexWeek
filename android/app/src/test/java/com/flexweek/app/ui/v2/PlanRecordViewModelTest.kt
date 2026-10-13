package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanRecordViewModelTest {
    private val core = FakeFlexWeekCore()

    @Test
    fun loadPlanBuildsRecordSheet() {
        var accepted = false
        val vm = PlanRecordViewModel(core, onAccepted = { accepted = true }, onDismiss = {})
        assertNotNull(vm.record)
        assertTrue(vm.record!!.summary.startsWith("Placed"))
        vm.accept()
        assertEquals(true, accepted)
    }

    @Test
    fun undoDismissesWithoutAccepting() {
        var dismissed = false
        val vm = PlanRecordViewModel(core, onAccepted = {}, onDismiss = { dismissed = true })
        vm.undo()
        assertEquals(true, dismissed)
    }
}
