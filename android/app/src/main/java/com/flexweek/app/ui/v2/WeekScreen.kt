package com.flexweek.app.ui.v2

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.flexweek.app.R
import com.flexweek.app.model.SyncLine
import com.flexweek.app.model.WeekEntry
import com.flexweek.app.model.WeekList
import com.flexweek.app.model.WeekRowWords
import com.flexweek.app.model.WeekRowsState
import com.flexweek.app.model.WeekSession
import com.flexweek.app.ui.components.SyncLineBar
import com.flexweek.app.ui.theme.categoryColor
import com.flexweek.app.ui.today.TimeColumn
import java.time.LocalDate

@Composable
fun WeekScreen(
    state: WeekRowsState,
    today: LocalDate?,
    isCurrentWeek: Boolean,
    syncLine: SyncLine,
    onPreviousWeek: () -> Unit,
    onNextWeek: () -> Unit,
    onThisWeek: () -> Unit,
    onOpenDay: (Int) -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    state.title,
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.weight(1f).padding(vertical = 8.dp),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (!isCurrentWeek) TextButton(onClick = onThisWeek) { Text("This week", maxLines = 1, softWrap = false) }
                IconButton(onClick = onPreviousWeek, modifier = Modifier.size(48.dp)) {
                    Icon(painterResource(R.drawable.ic_chevron_left), contentDescription = "Previous week")
                }
                IconButton(onClick = onNextWeek, modifier = Modifier.size(48.dp)) {
                    Icon(painterResource(R.drawable.ic_chevron_right), contentDescription = "Next week")
                }
            }
            Text(state.homeworkTotal, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SyncLineBar(syncLine)
        }
        val entries = if (today == null) emptyList() else WeekList.build(state.days, today)
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp),
        ) {
            items(entries) { entry ->
                when (entry) {
                    is WeekEntry.Day -> DayBlock(entry, tappable = isCurrentWeek, onOpenDay = onOpenDay)
                    is WeekEntry.Free -> FreeLine(entry.label)
                }
            }
            item { Spacer(Modifier.height(96.dp)) }
        }
    }
}

@Composable
private fun DayBlock(day: WeekEntry.Day, tappable: Boolean, onOpenDay: (Int) -> Unit) {
    // Another week's days cannot be opened on Today, which only shows the current week.
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 12.dp)
            .clip(RoundedCornerShape(12.dp))
            .then(if (tappable) Modifier.clickable { onOpenDay(day.dayIndex) } else Modifier),
    ) {
        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(day.label, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (day.total.isNotEmpty()) {
                Text(
                    day.total,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
        }
        day.sessions.forEach { SessionLine(it) }
    }
}

@Composable
private fun SessionLine(session: WeekSession) {
    val (clock, meridiem) = if (session.start == null) ("" to null) else TimeColumn.split(clockLabel(session.start))
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.width(64.dp).padding(end = 8.dp), horizontalAlignment = Alignment.End) {
            if (clock.isNotEmpty()) Text(clock, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            if (meridiem != null) Text(meridiem, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        }
        Box(Modifier.width(4.dp).height(36.dp).clip(RoundedCornerShape(2.dp)).background(categoryColor(session.category)))
        Column(Modifier.weight(1f).padding(start = 12.dp)) {
            Text(
                session.title,
                style = MaterialTheme.typography.bodyLarge,
                textDecoration = if (session.done) TextDecoration.LineThrough else null,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (session.minutes > 0) {
                Text(WeekRowWords.duration(session.minutes), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun FreeLine(label: String) {
    Row(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text("free", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Minutes after midnight as the phone writes a time: "3:15 PM". */
internal fun clockLabel(minutes: Int): String = com.flexweek.app.core.TimeLabel.short("%02d:%02d".format(minutes / 60, minutes % 60))
