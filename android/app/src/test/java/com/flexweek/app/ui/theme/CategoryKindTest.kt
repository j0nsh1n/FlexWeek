package com.flexweek.app.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

// Today drew real homework bars grey: the real core says "homework", the colour table only knew the fake
// core's "hw". Every category the real core sends must have a colour.
class CategoryKindTest {
    @Test fun everyCategoryInTheRealTodayHasAColour() {
        val stream = javaClass.getResourceAsStream("/phone/today-up-next.json")
        assertNotNull("the real today fixture is on the test classpath", stream)
        val categories = Regex("\"category\"\\s*:\\s*\"([a-z_]+)\"").findAll(stream!!.bufferedReader().readText())
            .map { it.groupValues[1] }.toSet()
        assertTrue("the fixture has categories to check", categories.isNotEmpty())
        val uncoloured = categories.filter { categoryKind(it) == null }
        assertTrue("categories the real core sends but Today has no colour for: $uncoloured", uncoloured.isEmpty())
    }

    @Test fun homeworkIsHomeworkWhicheverCoreSaysIt() {
        assertEquals(CategoryKind.Homework, categoryKind("homework"))
        assertEquals(CategoryKind.Homework, categoryKind("hw"))
    }
}
