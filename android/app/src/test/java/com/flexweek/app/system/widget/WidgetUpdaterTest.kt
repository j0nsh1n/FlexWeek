package com.flexweek.app.system.widget

import com.flexweek.app.core.RustPhoneJson
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

private class FakeWidgetHost : WidgetHost {
    override var lastShown: String? = null
    val shown = mutableListOf<WidgetContent>()
    val wakes = mutableListOf<WidgetRefresh.Wake>()

    override fun show(content: WidgetContent) {
        shown += content
        lastShown = content.toString()
    }

    override fun schedule(wake: WidgetRefresh.Wake) {
        wakes += wake
    }
}

class WidgetUpdaterTest {
    private val zone = ZoneId.of("America/Los_Angeles")
    private val now = ZonedDateTime.of(2026, 10, 12, 14, 10, 0, 0, zone).toInstant().toEpochMilli()
    private val synced = """{"paired":true,"state":"synced","line":"Synced just now","has_account":true}"""

    private fun phone(edit: (JSONObject) -> Unit = {}): String {
        val root = JSONObject(javaClass.getResourceAsStream("/phone/today-up-next.json")!!.bufferedReader().use { it.readText() })
        edit(root)
        return RustPhoneJson.today(root.toString(), "2026-10-12", synced)
    }

    private fun updater(host: WidgetHost, read: () -> String?) = WidgetUpdater(read, host, { now }, { zone })

    @Test fun unchangedTextDoesNotRedraw() {
        val host = FakeWidgetHost()
        val updater = updater(host) { phone() }
        updater.refresh()
        updater.refresh()
        updater.refresh()
        assertEquals("the widget redrew with the same text", 1, host.shown.size)
    }

    @Test fun aSyncThatChangesTheHeadlineRedraws() {
        val host = FakeWidgetHost()
        var raw = phone()
        val updater = updater(host) { raw }
        updater.refresh()
        raw = phone {
            it.getJSONArray("rows").getJSONObject(0).put("title", "Algebra set 5")
            it.getJSONObject("now").put("title", "Algebra set 5")
        }
        updater.refresh()
        assertEquals(listOf("Algebra set 4", "Algebra set 5"), host.shown.map { it.headline })
    }

    @Test fun aTickedHomeworkRowRedraws() {
        val host = FakeWidgetHost()
        var raw = phone()
        val updater = updater(host) { raw }
        updater.refresh()
        raw = phone { it.getJSONArray("rows").getJSONObject(1).put("done", true) }
        updater.refresh()
        assertEquals("the tick did not reach the widget", 2, host.shown.size)
        assertEquals(true, host.shown.last().rows.first().done)
    }

    @Test fun aForcedRefreshRedrawsTheSameText() {
        val host = FakeWidgetHost()
        val updater = updater(host) { phone() }
        updater.refresh()
        updater.refresh(force = true)
        assertEquals(2, host.shown.size)
    }

    @Test fun everyRefreshSchedulesTheNextWake() {
        val host = FakeWidgetHost()
        val updater = updater(host) { phone() }
        updater.refresh()
        updater.refresh()
        assertEquals("a wake for each refresh", 2, host.wakes.size)
        val minute = ZonedDateTime.of(2026, 10, 12, 14, 11, 0, 0, zone).toInstant().toEpochMilli()
        assertEquals(WidgetRefresh.Wake(minute, WidgetRefresh.Kind.MINUTE), host.wakes.first())
    }

    @Test fun aFailedReadKeepsTheLastGoodRender() {
        val host = FakeWidgetHost()
        var fail = false
        val updater = updater(host) { if (fail) error("the database is busy") else phone() }
        updater.refresh()
        val good = host.lastShown
        assertNotNull("the first read shows something", good)
        fail = true
        updater.refresh()
        assertEquals("a failed read redrew the widget", 1, host.shown.size)
        assertEquals(good, host.lastShown)
        assertEquals(WidgetRefresh.Wake(now + WidgetRefresh.RETRY_AFTER_MS, WidgetRefresh.Kind.MINUTE), host.wakes.last())
    }

    @Test fun anAnswerThatCannotBeReadKeepsTheLastGoodRender() {
        val host = FakeWidgetHost()
        var raw = phone()
        val updater = updater(host) { raw }
        updater.refresh()
        raw = "not json"
        updater.refresh()
        assertEquals(1, host.shown.size)
    }

    @Test fun aFailedReadWithNothingShownYetShowsThePlaceholder() {
        val host = FakeWidgetHost()
        val updater = updater(host) { error("the database is busy") }
        updater.refresh()
        assertEquals(listOf("Open FlexWeek to see your week."), host.shown.map { it.headline })
    }

    @Test fun aCoreThatIsNotReadyShowsThePlaceholder() {
        val host = FakeWidgetHost()
        val updater = updater(host) { null }
        updater.refresh()
        assertEquals(listOf("Open FlexWeek to see your week."), host.shown.map { it.headline })
    }
}
