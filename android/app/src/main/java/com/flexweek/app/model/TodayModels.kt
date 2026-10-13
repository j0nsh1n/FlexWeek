package com.flexweek.app.model

import org.json.JSONObject

data class DayChip(
    val index: Int,
    val label: String,
    val date: Int,
    val isToday: Boolean,
    val selected: Boolean,
    val hasDot: Boolean,
)

sealed class AgendaRow {
    data class Item(
        val id: String,
        val title: String,
        val category: String,
        val timeLabel: String,
        val detail: String,
        val homework: Boolean,
        val done: Boolean,
        val past: Boolean,
    ) : AgendaRow()

    data class Now(
        val id: String,
        val title: String,
        val kick: String,
        val minsLabel: String,
        val whenLine: String,
        val homework: Boolean,
        val thenTitle: String?,
        val thenTime: String?,
    ) : AgendaRow()

    data object NothingLeft : AgendaRow()

    data object EmptyDay : AgendaRow()
}

data class NoTimeItem(
    val id: String,
    val title: String,
    val lengthLabel: String,
    val dueLabel: String,
)

data class SyncLine(
    val state: String,
    val line: String,
)

data class TodayUiState(
    val title: String,
    val daySubtitle: String?,
    val showTodayJump: Boolean,
    val days: List<DayChip>,
    val rows: List<AgendaRow>,
    val noTime: List<NoTimeItem>,
    val noTimeCount: Int,
    val syncLine: SyncLine,
    val snackbar: SnackbarState? = null,
)

data class SnackbarState(
    val message: String,
    val undoBlockId: String?,
)

object TodayJson {
    fun parse(json: String): TodayUiState {
        val root = JSONObject(json)
        val daysArr = root.getJSONArray("days")
        val days = buildList {
            for (i in 0 until daysArr.length()) {
                val d = daysArr.getJSONObject(i)
                add(
                    DayChip(
                        index = d.getInt("index"),
                        label = d.getString("label"),
                        date = d.getInt("date"),
                        isToday = d.getBoolean("is_today"),
                        selected = d.getBoolean("selected"),
                        hasDot = d.getBoolean("has_dot"),
                    ),
                )
            }
        }
        val rowsArr = root.getJSONArray("rows")
        val rows = buildList {
            for (i in 0 until rowsArr.length()) {
                val r = rowsArr.getJSONObject(i)
                when (r.getString("type")) {
                    "item" ->
                        add(
                            AgendaRow.Item(
                                id = r.getString("id"),
                                title = r.getString("title"),
                                category = r.getString("category"),
                                timeLabel = r.getString("time_label"),
                                detail = r.getString("detail"),
                                homework = r.getBoolean("homework"),
                                done = r.getBoolean("done"),
                                past = r.getBoolean("past"),
                            ),
                        )
                    "now" ->
                        add(
                            AgendaRow.Now(
                                id = r.getString("id"),
                                title = r.getString("title"),
                                kick = r.getString("kick"),
                                minsLabel = r.getString("mins_label"),
                                whenLine = r.getString("when_line"),
                                homework = r.getBoolean("homework"),
                                thenTitle = r.optString("then_title", null),
                                thenTime = r.optString("then_time", null),
                            ),
                        )
                    "nothing_left" -> add(AgendaRow.NothingLeft)
                    "empty" -> add(AgendaRow.EmptyDay)
                }
            }
        }
        val noTimeArr = root.getJSONArray("no_time")
        val noTime = buildList {
            for (i in 0 until noTimeArr.length()) {
                val n = noTimeArr.getJSONObject(i)
                add(
                    NoTimeItem(
                        id = n.getString("id"),
                        title = n.getString("title"),
                        lengthLabel = n.getString("length_label"),
                        dueLabel = n.getString("due_label"),
                    ),
                )
            }
        }
        val sync = root.getJSONObject("sync")
        return TodayUiState(
            title = root.getString("day_title"),
            daySubtitle =
                if (root.getInt("selected_day") != root.getInt("today_index")) {
                    root.getString("day_subtitle")
                } else {
                    null
                },
            showTodayJump = root.getInt("selected_day") != root.getInt("today_index"),
            days = days,
            rows = rows,
            noTime = noTime,
            noTimeCount = noTime.size,
            syncLine =
                SyncLine(
                    state = sync.getString("state"),
                    line = sync.getString("line"),
                ),
        )
    }
}
