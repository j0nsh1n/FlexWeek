package com.flexweek.app.core

import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/**
 * Remembers where each agenda row lives so a tick can name its day. A tick marks that session done for
 * that day only; finishing a whole homework is a separate act, so the homework's other sessions stay planned.
 */
internal class RowTicks(
    private val markBlock: (week: String, blockId: String, day: Int, done: Boolean, opId: String) -> Unit,
) {
    private data class Place(val week: String, val day: Int)
    private val places = ConcurrentHashMap<String, Place>()

    fun remember(todayJson: String) {
        val root = JSONObject(todayJson)
        val rows = root.getJSONArray("rows")
        for (i in 0 until rows.length()) {
            places[rows.getJSONObject(i).getString("id")] = Place(root.getString("week_start"), root.getInt("day"))
        }
    }

    fun mark(id: String, done: Boolean, opId: String) {
        val place = places[id] ?: error("Homework row is no longer available. Open the day again.")
        markBlock(place.week, id, place.day, done, opId)
    }
}
