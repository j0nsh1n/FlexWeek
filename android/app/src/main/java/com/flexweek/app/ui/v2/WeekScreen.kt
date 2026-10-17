package com.flexweek.app.ui.v2

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.flexweek.app.model.WeekDayWords
import com.flexweek.app.model.WeekRowsState
import com.flexweek.app.ui.components.SyncLineBar

// The phone writes English everywhere, so the day names are fixed, not the device locale's.
private val WEEK_DAY_LABELS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
private const val MINUTES_PER_HOUR = 60
private const val HOURS_PER_DAY = 24
private const val HOURS_PER_HALF_DAY = 12

@Composable
fun WeekScreen(
    state: WeekRowsState,
    syncLine: com.flexweek.app.model.SyncLine,
    onOpenDay: (Int) -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Text(state.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 8.dp))
            Text(state.homeworkTotal, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SyncLineBar(syncLine)
        }
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            items(state.days, key = { it.dayIndex }) { day ->
                WeekDayRow(day, onOpenDay)
            }
        }
    }
}

@Composable
private fun WeekDayRow(day: WeekDayWords, onOpenDay: (Int) -> Unit) {
    Card(Modifier.fillMaxWidth().clickable { onOpenDay(day.dayIndex) }) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("${WEEK_DAY_LABELS[day.dayIndex]} ${day.date}", fontWeight = FontWeight.SemiBold, maxLines = 1)
            Text(
                day.names.joinToString(" · "),
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            val right = if (day.minutes > 0) {
                duration(day.minutes) + if (day.heavy) " · heavy" else ""
            } else {
                day.lastClassEnd?.let { "free after ${shortTime(it)}" } ?: "free"
            }
            Text(right, style = MaterialTheme.typography.labelSmall, color = if (day.heavy) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        }
    }
}

private fun duration(minutes: Int): String {
    val hours = minutes / MINUTES_PER_HOUR
    val rest = minutes % MINUTES_PER_HOUR
    return when {
        hours == 0 -> "$rest min"
        rest == 0 -> "$hours h"
        else -> "$hours h $rest"
    }
}

private fun shortTime(minutes: Int): String {
    val hour24 = minutes / MINUTES_PER_HOUR % HOURS_PER_DAY
    val minute = minutes % MINUTES_PER_HOUR
    val hour12 = if (hour24 % HOURS_PER_HALF_DAY == 0) HOURS_PER_HALF_DAY else hour24 % HOURS_PER_HALF_DAY
    return if (minute == 0) hour12.toString() else "$hour12:${minute.toString().padStart(2, '0')}"
}
