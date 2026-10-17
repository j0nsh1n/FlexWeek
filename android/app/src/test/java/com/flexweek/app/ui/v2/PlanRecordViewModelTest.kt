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
    fun acceptReturnsPlacedIds() {
        var ids: List<String>? = null
        val vm = PlanRecordViewModel(core, onAccepted = { ids = it }, onDismiss = {})
        vm.accept()
        assertNotNull(ids)
        assertTrue(ids!!.isNotEmpty())
    }

    @Test
    fun undoDismissesWithoutAccepting() {
        var dismissed = false
        val vm = PlanRecordViewModel(core, onAccepted = {}, onDismiss = { dismissed = true })
        vm.undo()
        assertEquals(true, dismissed)
    }
}
