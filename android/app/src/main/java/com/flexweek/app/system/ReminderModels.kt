package com.flexweek.app.system

import org.json.JSONArray
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

data class ReminderItem(
    val key: String,
    val fireAtLocal: LocalDateTime,
    val title: String,
    val body: String,
) {
    fun fireAtEpochMs(zone: ZoneId = ZoneId.systemDefault()): Long =
        fireAtLocal.atZone(zone).toInstant().toEpochMilli()
}

object ReminderJson {
    private val localFormatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME

    fun parseArray(json: String): List<ReminderItem> {
        val arr = JSONArray(json)
        return buildList {
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                add(
                    ReminderItem(
                        key = o.getString("key"),
                        fireAtLocal = LocalDateTime.parse(o.getString("fire_at_local"), localFormatter),
                        title = o.getString("title"),
                        body = o.getString("body"),
                    ),
                )
            }
        }
    }
}
