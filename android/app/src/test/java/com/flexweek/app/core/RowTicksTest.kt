package com.flexweek.app.core

import org.junit.Assert.assertEquals
import org.junit.Test

class RowTicksTest {
    // One 3 h essay planned as Monday, Wednesday and Friday sessions; the student ticks Wednesday's.
    private val today = """{"week_start":"2026-10-05","day":2,"rows":[
        {"id":"essay-wed","assignment_id":"essay","homework":true,"done":false}]}"""

    @Test fun tickingASessionMarksThatBlockDoneForThatDayOnly() {
        val calls = mutableListOf<String>()
        val ticks = RowTicks { week, block, day, done, op -> calls += "$week:$block:$day:$done:$op" }
        ticks.remember(today)
        ticks.mark("essay-wed", true, "op-1")
        assertEquals(listOf("2026-10-05:essay-wed:2:true:op-1"), calls)
    }

    @Test fun unticking_marksTheSameBlockNotDone() {
        val calls = mutableListOf<String>()
        val ticks = RowTicks { week, block, day, done, op -> calls += "$week:$block:$day:$done:$op" }
        ticks.remember(today)
        ticks.mark("essay-wed", false, "op-2")
        assertEquals(listOf("2026-10-05:essay-wed:2:false:op-2"), calls)
    }

    @Test(expected = IllegalStateException::class)
    fun aRowThatWasNeverReadIsRefused() {
        RowTicks { _, _, _, _, _ -> }.mark("ghost", true, "op")
    }
}
