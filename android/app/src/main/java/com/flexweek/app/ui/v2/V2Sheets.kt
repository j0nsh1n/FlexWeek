package com.flexweek.app.ui.v2

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.flexweek.app.core.TimeLabel
import com.flexweek.app.model.HomeworkDraft
import com.flexweek.app.model.PlanRecordState
import com.flexweek.app.model.RunningLatePreview
import com.flexweek.app.model.AddHomeworkWords
import com.flexweek.app.model.DueChips
import java.time.LocalDate
import java.time.ZoneId
import android.app.DatePickerDialog

@Composable
fun SheetScrim(onDismiss: () -> Unit, content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.35f))
                .clickable(onClick = onDismiss),
        )
        Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
            content()
        }
    }
}

@Composable
fun PlanRecordSheet(
    record: PlanRecordState,
    onUndo: () -> Unit,
    onAccept: () -> Unit,
) {
    SheetScrim(onUndo) {
        Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp), color = MaterialTheme.colorScheme.surfaceContainerLow) {
            Column(Modifier.padding(24.dp).verticalScroll(rememberScrollState())) {
                Text("Planned just now", style = MaterialTheme.typography.titleLarge)
                Text(record.summary, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 8.dp))
                record.lines.forEach { line ->
                    Column(Modifier.padding(vertical = 6.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(line.title, fontWeight = FontWeight.SemiBold)
                            Text(line.right, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (line.detail.isNotEmpty()) {
                            Text(line.detail, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                        }
                        line.why?.let {
                            Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onUndo, modifier = Modifier.heightIn(min = 48.dp)) { Text("Undo") }
                    Button(onClick = onAccept, modifier = Modifier.heightIn(min = 48.dp)) { Text("Accept") }
                }
            }
        }
    }
}

const val NOTHING_TO_MOVE = "No homework needs to move. Fixed times stay where they are."

@Composable
fun RunningLateSheet(
    preview: RunningLatePreview?,
    error: String?,
    minutes: Int,
    onMinutes: (Int) -> Unit,
    onCancel: () -> Unit,
    onAccept: () -> Unit,
) {
    SheetScrim(onCancel) {
        Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp), color = MaterialTheme.colorScheme.surfaceContainerLow) {
            Column(Modifier.padding(24.dp).verticalScroll(rememberScrollState())) {
                if (preview != null) {
                    Text("${preview.current.title} is running late", style = MaterialTheme.typography.titleLarge)
                    Text(TimeLabel.nowEnds(preview.current.end, preview.current.endDay), color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    Text("Running late", style = MaterialTheme.typography.titleLarge)
                }
                Text("How late?  $minutes min", modifier = Modifier.padding(top = 8.dp))
                Slider(
                    value = ((minutes.coerceIn(5, 60) - 5) / 55f),
                    onValueChange = { fraction -> onMinutes(LateSlider.minutesAt(fraction)) },
                    valueRange = 0f..1f,
                    steps = 10,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error != null) {
                    Text(error, modifier = Modifier.padding(vertical = 8.dp))
                }
                if (preview != null && preview.moves.isEmpty()) {
                    Text(NOTHING_TO_MOVE, modifier = Modifier.padding(vertical = 8.dp))
                }
                if (preview != null && preview.moves.isNotEmpty()) {
                    Text("What moves and why", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
                }
                preview?.moves?.forEach { move ->
                    Text("${move.title} ${move.detail} · ${move.durationMin} min", modifier = Modifier.padding(vertical = 6.dp))
                    if (move.why.isNotEmpty()) {
                        Text(move.why, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                preview?.warning?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 6.dp)) }
                preview?.stays?.forEach { title ->
                    Text("$title stays · fixed time", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 4.dp))
                }
                Text(
                    "Running late doesn't place homework that has no time yet. Use Plan for that.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onCancel, modifier = Modifier.heightIn(min = 48.dp)) { Text("Cancel") }
                    Button(onClick = onAccept, enabled = preview != null, modifier = Modifier.heightIn(min = 48.dp)) { Text("Accept late start") }
                }
            }
        }
    }
}
