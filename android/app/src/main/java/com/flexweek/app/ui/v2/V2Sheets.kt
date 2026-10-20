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
import com.flexweek.app.model.HomeworkDraft
import com.flexweek.app.model.PlanRecordState
import com.flexweek.app.model.RunningLatePreview
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
        Column(Modifier.align(Alignment.BottomCenter)) {
            content()
        }
    }
}

@Composable
fun AddHomeworkSheet(
    draft: HomeworkDraft,
    recentTitles: List<String> = emptyList(),
    stepProblem: String?,
    onTitleChange: (String) -> Unit,
    onDuePick: (String) -> Unit,
    onWhenMode: (String) -> Unit,
    onEstimate: (Int) -> Unit,
    onSessions: (String) -> Unit,
    onStepJump: (Int) -> Unit,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onCancel: () -> Unit,
) {
    SheetScrim(onCancel) {
        Surface(shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)) {
            Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState())) {
                Text("Add homework", style = MaterialTheme.typography.titleLarge)
                StepCrumbs(draft, onStepJump)
                when (draft.step) {
                    0 -> {
                        Text("What is it?", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
                        OutlinedTextField(
                            value = draft.title,
                            onValueChange = onTitleChange,
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text("e.g. History essay") },
                            isError = stepProblem != null,
                        )
                        if (recentTitles.isNotEmpty()) ChipRow(recentTitles, draft.title, onTitleChange)
                        stepProblem?.let {
                            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
                        }
                    }
                    1 -> {
                        Text("When is it due?", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
                        val context = LocalContext.current
                        val today = LocalDate.now()
                        DueChips.forToday(today).take(3).forEach { chip ->
                            TextButton(onClick = { onDuePick(chip.date.toString()) }) {
                                Text(if (draft.due == chip.date.toString()) "✓ ${chip.label}" else chip.label)
                            }
                        }
                        TextButton(onClick = {
                            DatePickerDialog(context, { _, year, month, day ->
                                onDuePick(LocalDate.of(year, month + 1, day).toString())
                            }, today.year, today.monthValue - 1, today.dayOfMonth).apply {
                                datePicker.minDate = today.atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
                            }.show()
                        }) { Text("Pick a day") }
                        Text("FlexWeek picks the time to do it", modifier = Modifier.padding(top = 8.dp))
                    }
                    else -> {
                        Text("How long will it take?", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
                        ChipRow(listOf("15 min", "30 min", "45 min", "60 min", "90 min"), "${draft.estimateMin} min") { label ->
                            onEstimate(label.removeSuffix(" min").toInt())
                        }
                        Text("Sessions", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 12.dp))
                        ChipRow(listOf("In one go", "Spread over days"), draft.sessions) { label ->
                            onSessions(if (label.startsWith("In")) "one" else "spread")
                        }
                        Text(
                            if (draft.sessions == "one") "In one go means one homework session."
                            else "Spread over days means more than one session.",
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
                stepProblem?.let {
                    if (draft.step > 0) {
                        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (draft.step > 0) {
                        TextButton(onClick = onBack, modifier = Modifier.height(48.dp)) { Text("Back") }
                    }
                    TextButton(onClick = onCancel, modifier = Modifier.height(48.dp)) { Text("Cancel") }
                    Button(onClick = onNext, modifier = Modifier.height(48.dp)) {
                        Text(if (draft.step < 2) "Next" else "Save")
                    }
                }
            }
        }
    }
}

@Composable
private fun StepCrumbs(draft: HomeworkDraft, onStepJump: (Int) -> Unit) {
    Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        if (draft.step > 0) {
            TextButton(onClick = { onStepJump(0) }) { Text("✓ ${draft.title.ifEmpty { "What" }}") }
            Text("·")
        }
        if (draft.step > 1) {
            TextButton(onClick = { onStepJump(1) }) {
                val due = runCatching { DueChips.label(LocalDate.parse(draft.due), LocalDate.now()) }.getOrDefault(draft.due)
                Text("✓ due $due, FlexWeek picks the time")
            }
            Text("·")
        }
        Text(
            "${draft.step + 1} ${listOf("What", "When", "How long")[draft.step]}",
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

@Composable
fun PlanRecordSheet(
    record: PlanRecordState,
    onUndo: () -> Unit,
    onAccept: () -> Unit,
) {
    SheetScrim(onUndo) {
        Surface(shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)) {
            Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState())) {
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
                Row(Modifier.fillMaxWidth().padding(top = 12.dp)) {
                    TextButton(onClick = onUndo, modifier = Modifier.height(48.dp)) { Text("Undo") }
                    Box(Modifier.weight(1f))
                    Button(onClick = onAccept, modifier = Modifier.height(48.dp)) { Text("Accept") }
                }
            }
        }
    }
}

const val NOTHING_TO_MOVE = "Nothing after this time can move. Fixed times stay."

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
        Surface(shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)) {
            Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState())) {
                if (preview != null) {
                    Text("${preview.current.title} is running late", style = MaterialTheme.typography.titleLarge)
                    Text("Ends at ${lateClockLabel(preview.current.end)} (+${minutes} min)", color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                    "Homework with no time yet is not placed by Running late. That is Plan's job.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
                Row(Modifier.fillMaxWidth()) {
                    TextButton(onClick = onCancel, modifier = Modifier.height(48.dp)) { Text("Cancel") }
                    Box(Modifier.weight(1f))
                    Button(onClick = onAccept, enabled = preview != null, modifier = Modifier.height(48.dp)) { Text("Move it") }
                }
            }
        }
    }
}

private fun lateClockLabel(value: String): String {
    val parts = value.split(":")
    if (parts.size != 2) return value
    val hour = parts[0].toIntOrNull() ?: return value
    val minute = parts[1].toIntOrNull() ?: return value
    val displayHour = when (hour % 12) { 0 -> 12; else -> hour % 12 }
    val suffix = if (hour < 12) "AM" else "PM"
    return if (minute == 0) "$displayHour $suffix" else "$displayHour:${minute.toString().padStart(2, '0')} $suffix"
}

@Composable
private fun ChipRow(options: List<String>, selected: String, onPick: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { opt ->
            val on = opt == selected || (opt.startsWith("FlexWeek") && selected == "pick") ||
                (opt.startsWith("I'll") && selected == "at") ||
                (opt.startsWith("In one") && selected == "one") ||
                (opt.startsWith("Spread") && selected == "spread")
            TextButton(
                onClick = { onPick(opt) },
                modifier =
                    Modifier
                        .heightIn(min = 44.dp)
                        .clip(RoundedCornerShape(999.dp))
                        .background(if (on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface),
            ) {
                Text(
                    opt,
                    color = if (on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}
