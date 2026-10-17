package com.flexweek.app.system.widget

import com.flexweek.app.core.RustPhoneJson
import com.flexweek.app.core.TimeLabel
import org.json.JSONObject

data class WidgetRow(
    val id: String,
    val time: String,
    val title: String,
    val length: String,
    val category: String,
    val homework: Boolean,
    val done: Boolean,
)

/** The widget's text, apart from how it is drawn. Equal content is drawn once: a redraw needs a change. */
data class WidgetContent(
    val kicker: String?,
    val headline: String,
    val headlineTime: String?,
    val rows: List<WidgetRow>,
    val note: String?,
)

/** Reads the phone's Today answer (`core.today`) into the widget's words; the times come from [TimeLabel]. */
object WidgetWords {
    const val NOTHING_LEFT = "Nothing left today"
    const val OPEN_APP = "Open FlexWeek to see your week."
    const val MAX_ROWS = 2

    // The countdown ("in 20 min", "20 min left") is redrawn every minute only inside this window.
    const val COUNTDOWN_WINDOW_MIN = 60

    fun placeholder(): WidgetContent = message(OPEN_APP, null)

    fun from(today: String): WidgetContent {
        val root = JSONObject(today)
        val sync = root.optJSONObject("sync")
        val line = sync?.optString("line").orEmpty()
        if (sync != null && !sync.optBoolean("paired", true)) return message(line, null)
        val note = line.takeIf { sync?.optString("state") == "unreachable" && it.isNotEmpty() }
        val items = items(root)
        val head = items.indexOfFirst { it.getString("type") == "now" }
        if (head < 0) return message(NOTHING_LEFT, note)
        val now = items[head]
        val rows = items.drop(head + 1).filterNot { it.getBoolean("past") }.take(MAX_ROWS).map {
            WidgetRow(
                id = it.getString("id"),
                time = TimeLabel.short(it.getString("start")),
                title = it.getString("title"),
                length = RustPhoneJson.length(it.getLong("duration_min")),
                category = it.getString("category"),
                homework = it.getBoolean("homework"),
                done = it.getBoolean("done"),
            )
        }
        return WidgetContent(
            kicker = "${now.getString("kick")} · ${now.getString("mins_label")}",
            headline = now.getString("title"),
            headlineTime = "${range(now.getString("start"), now.getString("end"))} · ${RustPhoneJson.length(now.getLong("duration_min"))}",
            rows = rows,
            note = note,
        )
    }

    /** "2:30–4 PM": the first time drops its AM or PM when both are in the same half of the day. */
    fun range(start: String, end: String): String {
        val from = TimeLabel.short(start)
        val to = TimeLabel.short(end)
        val sameHalf = from.substringAfterLast(' ') == to.substringAfterLast(' ')
        return if (sameHalf) "${from.substringBeforeLast(' ')}–$to" else "$from–$to"
    }

    fun tickLabel(title: String): String = "Mark $title finished"

    /** Every start and end minute of today's rows, sorted: the moments the text can change on its own. */
    fun boundaryMinutes(today: String): List<Int> = items(JSONObject(today))
        .flatMap { listOf(it.getInt("start_min"), it.getInt("end_min")) }
        .distinct()
        .sorted()

    fun countdownShowing(today: String): Boolean =
        JSONObject(today).optJSONObject("now")?.let { it.getInt("minutes_left") <= COUNTDOWN_WINDOW_MIN } ?: false

    private fun message(text: String, note: String?) = WidgetContent(null, text, null, emptyList(), note)

    private fun items(root: JSONObject): List<JSONObject> {
        val rows = root.getJSONArray("rows")
        return (0 until rows.length()).map { rows.getJSONObject(it) }.filter { it.getString("type") in listOf("item", "now") }
    }
}
