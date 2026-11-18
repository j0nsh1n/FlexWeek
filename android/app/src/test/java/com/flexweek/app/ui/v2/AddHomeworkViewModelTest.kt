package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AddHomeworkViewModelTest {
    @get:org.junit.Rule val main = com.flexweek.app.testing.MainThreadRule()

    private val core = FakeFlexWeekCore()

    @Test
    fun saveNeedsATitleADueDayAndALength() {
        val vm = AddHomeworkViewModel(core, main.dispatcher) {}
        assertFalse("nothing typed, no length", vm.draft.canSave)
        vm.onTitleChange("Lab report")
        assertFalse("a title but no length", vm.draft.canSave)
        vm.onEstimate(45)
        assertTrue(vm.draft.canSave)
        vm.onTitleChange("   ")
        assertFalse("a blank title", vm.draft.canSave)
        vm.onTitleChange("Lab report")
        vm.onDuePick("")
        assertFalse("no due day", vm.draft.canSave)
    }

    @Test
    fun saveWithNoTitleAsksForOneAndDoesNotCallTheCore() {
        var saved: String? = null
        val vm = AddHomeworkViewModel(core, main.dispatcher) { saved = it }
        vm.onEstimate(30)
        vm.save()
        assertEquals("Give the homework a title.", vm.problem)
        assertNull(saved)
    }

    @Test
    fun otherLengthTakesMinutesFromTheField() {
        val vm = AddHomeworkViewModel(core, main.dispatcher) {}
        vm.onEstimate(30)
        vm.onOtherLength()
        assertEquals("Other clears the chip's length until minutes are typed", 0, vm.draft.estimateMin)
        vm.onOtherMinutes("1a2")
        assertEquals(12, vm.draft.estimateMin)
        assertTrue(vm.draft.otherLength)
        vm.onEstimate(60)
        assertFalse("a chip turns Other off", vm.draft.otherLength)
    }

    @Test
    fun saveCallsTheCoreOnce() {
        var saved: String? = null
        val vm = AddHomeworkViewModel(core, main.dispatcher) { saved = it }
        vm.onTitleChange("Lab report")
        vm.onEstimate(60)
        vm.save()
        assertNotNull(saved)
        assertEquals(true, saved!!.contains("added"))
    }

    @Test
    fun theSheetOpensWhenRecentTitlesCannotBeRead() {
        val failing = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun recentTitles(): List<String> = throw IllegalStateException("the core could not answer")
        }
        val vm = runCatching { AddHomeworkViewModel(failing, main.dispatcher) {} }
        assertEquals("the sheet opens without recent titles", emptyList<String>(), vm.getOrNull()?.recentTitles)
    }
}
