package com.flexweek.app.ui.v2

import com.flexweek.app.core.FakeFlexWeekCore
import com.flexweek.app.core.FlexWeekCore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class AddHomeworkViewModelTest {
    private val core = FakeFlexWeekCore()

    @Test
    fun stepWhatBlocksOnEmptyTitle() {
        var saved: String? = null
        val vm = AddHomeworkViewModel(core) { saved = it }
        vm.nextOrSave()
        assertEquals("Give the homework a title.", vm.stepProblem)
        assertEquals(0, vm.draft.step)
    }

    @Test
    fun stepWhenAdvancesAfterTitle() {
        val vm = AddHomeworkViewModel(core) {}
        vm.onTitleChange("Lab report")
        vm.nextOrSave()
        assertEquals(null, vm.stepProblem)
        assertEquals(1, vm.draft.step)
    }

    @Test
    fun stepHowLongSaveCallsCore() {
        var saved: String? = null
        val vm = AddHomeworkViewModel(core) { saved = it }
        vm.onTitleChange("Lab report")
        vm.nextOrSave()
        vm.nextOrSave()
        vm.nextOrSave()
        assertNotNull(saved)
        assertEquals(true, saved!!.contains("added"))
    }

    @Test
    fun theSheetOpensWhenRecentTitlesCannotBeRead() {
        val failing = object : FlexWeekCore by FakeFlexWeekCore() {
            override fun recentTitles(): List<String> = throw IllegalStateException("the core could not answer")
        }
        val vm = runCatching { AddHomeworkViewModel(failing) {} }
        assertEquals("the sheet opens without recent titles", emptyList<String>(), vm.getOrNull()?.recentTitles)
    }
}
