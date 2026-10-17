package com.flexweek.app.ui.v2

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.flexweek.app.model.WeekUiState
import com.flexweek.app.ui.components.SyncLineBar
import com.flexweek.app.ui.theme.categoryColor

// The phone writes English everywhere, so the day names are fixed, not the device locale's.
private val WEEK_DAY_LABELS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

@Composable
fun WeekScreen(
    state: WeekUiState,
    syncLine: com.flexweek.app.model.SyncLine,
    onOpenDay: (Int) -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Text(state.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(vertical = 8.dp))
            SyncLineBar(syncLine)
        }
        Row(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            state.days.forEach { day ->
                Column(
                    modifier =
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(MaterialTheme.shapes.small)
                            .then(
                                if (day.isToday) {
                                    Modifier.border(1.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small)
                                } else {
                                    Modifier
                                },
                            )
                            .clickable { onOpenDay(day.dayIndex) }
                            .padding(2.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        WEEK_DAY_LABELS[day.dayIndex],
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Box(
                        Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .height(280.dp)
                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f)),
                    ) {
                        day.bars.forEach { bar ->
                            Box(
                                Modifier
                                    .align(Alignment.TopCenter)
                                    .fillMaxWidth(0.85f)
                                    .padding(top = (280 * bar.topFraction).dp)
                                    .height((280 * bar.heightFraction).coerceAtLeast(0.02f).dp)
                                    .background(categoryColor(bar.category))
                                    .then(
                                        if (bar.isNew) {
                                            Modifier.border(1.dp, MaterialTheme.colorScheme.primary)
                                        } else {
                                            Modifier
                                        },
                                    ),
                            )
                        }
                    }
                }
            }
        }
    }
}
