package com.flexweek.app.ui.today

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Badge
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.flexweek.app.model.AgendaRow
import com.flexweek.app.model.DayChip
import com.flexweek.app.model.TodayUiState
import com.flexweek.app.model.FocusUiState
import com.flexweek.app.model.FocusJson
import com.flexweek.app.model.FocusSheetText
import com.flexweek.app.ui.components.SyncLineBar
import com.flexweek.app.ui.theme.categoryColor

data class NowRowActions(
    val finishHomework: Boolean,
    val startFocus: Boolean,
    val runningLate: Boolean,
)

fun nowRowActions(row: AgendaRow.Now, lateEnabled: Boolean): NowRowActions =
    NowRowActions(row.showFinishFocus, row.showFinishFocus, row.showRunningLate && lateEnabled)

@Composable
fun TodayScreen(
    state: TodayUiState,
    onSelectDay: (Int) -> Unit,
    onJumpToday: () -> Unit,
    onToggleHomework: (String) -> Unit,
    onUndo: () -> Unit,
    onDismissSnack: () -> Unit,
    onFinishHomework: (String) -> Unit = onToggleHomework,
    onStartFocus: (String) -> Unit = {},
    onRunningLate: () -> Unit = {},
    focusState: FocusUiState? = null,
    onPauseFocus: () -> Unit = {},
    onCompleteFocus: () -> Unit = {},
    onFinishFocus: () -> Unit = {},
    replacePrompt: Pair<String, String>? = null,
    onKeepFocus: () -> Unit = {},
    onReplaceFocus: () -> Unit = {},
    finishPrompt: FocusUiState? = null,
    onKeepGoing: () -> Unit = {},
    onEndSession: () -> Unit = {},
    lateEnabled: Boolean = false,
    v2Extras: TodayV2Extras? = null,
) {
    Box(Modifier.fillMaxSize()) {
        var nowMs by remember { mutableLongStateOf(System.currentTimeMillis()) }
        LaunchedEffect(focusState?.endsAt, focusState?.running) {
            while (focusState?.running == true) {
                nowMs = System.currentTimeMillis()
                if (focusState.remaining(nowMs) == 0L) {
                    onCompleteFocus()
                    break
                }
                delay(1000)
            }
        }
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.padding(horizontal = 16.dp)) {
                Text(state.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(vertical = 8.dp))
                SyncLineBar(state.syncLine)
            }
            Column(
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
            ) {
                DayChipRow(state.days, onSelectDay)
                focusState?.let { FocusTimerCard(it, nowMs, onPauseFocus, onFinishFocus) }
                state.daySubtitle?.let { sub ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(sub, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (state.showTodayJump) {
                            TextButton(onClick = onJumpToday, modifier = Modifier.height(48.dp)) {
                                Text("Today")
                            }
                        }
                    }
                }
                if (focusState != null) {
                    Text("After this", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
                }
                state.rows.filterNot { it is AgendaRow.Now && focusState?.assignmentId == it.assignmentId }.forEach { row ->
                    when (row) {
                        is AgendaRow.Item -> AgendaItemRow(row, onToggleHomework)
                        is AgendaRow.Now ->
                            NowRow(
                                row,
                                onFinishHomework,
                                { row.assignmentId?.let(onStartFocus) },
                                onRunningLate,
                                lateEnabled,
                            )
                        AgendaRow.NothingLeft ->
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                tonalElevation = 1.dp,
                                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                            ) {
                                Column(Modifier.padding(14.dp)) {
                                    Text("Nothing left today", style = MaterialTheme.typography.titleLarge)
                                }
                            }
                        AgendaRow.EmptyDay ->
                            Text(
                                "Nothing planned",
                                modifier = Modifier.fillMaxWidth().padding(vertical = 40.dp),
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                    }
                }
                NoTimeSection(state, v2Extras?.onPlan)
            }
        }
        v2Extras?.let { extras ->
            if (extras.showFab) {
                Button(
                    onClick = extras.onAdd,
                    modifier =
                        Modifier
                            .align(Alignment.BottomEnd)
                            .padding(end = 16.dp, bottom = 88.dp)
                            .height(56.dp),
                ) {
                    Text("+ Add")
                }
            }
        }
        state.snackbar?.let { snack ->
            SnackbarBar(
                snack.message,
                onUndo,
                onDismissSnack,
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }
        replacePrompt?.let { (current, incoming) ->
            androidx.compose.material3.AlertDialog(
                onDismissRequest = onKeepFocus,
                title = { Text(FocusSheetText.replaceTitle) },
                text = { Text(FocusJson.replaceText(current, incoming)) },
                confirmButton = { TextButton(onClick = onKeepFocus) { Text(FocusSheetText.keepCurrent) } },
                dismissButton = { TextButton(onClick = onReplaceFocus) { Text(FocusSheetText.replace) } },
            )
        }
        finishPrompt?.let { focus ->
            androidx.compose.material3.AlertDialog(
                onDismissRequest = onKeepGoing,
                title = { Text(FocusSheetText.finishTitle) },
                text = { Text(FocusJson.finishText(((focus.workMin * 60_000L - focus.remaining(nowMs)) / 60_000L).toInt().coerceAtLeast(0), focus.title)) },
                confirmButton = { TextButton(onClick = onKeepGoing) { Text(FocusSheetText.keepGoing) } },
                dismissButton = { TextButton(onClick = onEndSession) { Text(FocusSheetText.endSession) } },
            )
        }
    }
}

data class TodayV2Extras(
    val showFab: Boolean,
    val onAdd: () -> Unit,
    val onPlan: () -> Unit,
)

@Composable
private fun DayChipRow(days: List<DayChip>, onSelectDay: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        days.forEach { day ->
            val selected = day.selected
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .heightIn(min = 52.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .then(
                            if (selected) {
                                Modifier.background(MaterialTheme.colorScheme.primary)
                            } else if (day.isToday) {
                                Modifier.border(1.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(8.dp))
                            } else {
                                Modifier
                            },
                        )
                        .clickable { onSelectDay(day.index) }
                        .padding(vertical = 4.dp)
                        .semantics { contentDescription = "${day.label} ${day.date}" },
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    day.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    day.date.toString(),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                )
                if (day.hasDot) {
                    Box(
                        Modifier
                            .padding(top = 2.dp)
                            .size(5.dp)
                            .clip(CircleShape)
                            .background(
                                if (selected) {
                                    MaterialTheme.colorScheme.onPrimary
                                } else {
                                    categoryColor("hw")
                                },
                            ),
                    )
                }
            }
        }
    }
}

@Composable
private fun AgendaItemRow(row: AgendaRow.Item, onToggle: (String) -> Unit) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .alpha(if (row.past) 0.55f else 1f)
                .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            row.timeLabel,
            modifier = Modifier.width(62.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Box(
            Modifier
                .width(4.dp)
                .height(36.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(categoryColor(row.category)),
        )
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(
                row.title,
                fontWeight = FontWeight.SemiBold,
                textDecoration = if (row.done) TextDecoration.LineThrough else null,
                color = if (row.done) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(row.detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        }
        if (row.homework) {
            TextButton(
                onClick = { onToggle(row.id) },
                modifier = Modifier.size(48.dp),
            ) {
                Box(
                    Modifier
                        .size(26.dp)
                        .border(2.dp, if (row.done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline, CircleShape)
                        .background(if (row.done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    if (row.done) {
                        Text("✓", color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        } else {
            Spacer(Modifier.width(48.dp))
        }
    }
}

@Composable
private fun NowRow(
    row: AgendaRow.Now,
    onFinishHomework: (String) -> Unit,
    onStartFocus: () -> Unit,
    onRunningLate: () -> Unit,
    lateEnabled: Boolean,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(width = 1.dp, color = MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp)),
    ) {
        Box(
            Modifier
                .width(4.dp)
                .heightIn(min = 120.dp)
                .background(MaterialTheme.colorScheme.primary),
        )
        Column(Modifier.weight(1f).padding(14.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    row.kick.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    row.minsLabel.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(row.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 4.dp))
            Text(row.whenLine, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (row.thenTitle != null && row.thenTime != null) {
                Text(
                    "then ${row.thenTitle} at ${row.thenTime}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            val actions = nowRowActions(row, lateEnabled)
            val acts = actions.finishHomework || actions.startFocus || actions.runningLate
            if (acts) {
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (actions.finishHomework) {
                        Button(onClick = { onFinishHomework(row.id) }, modifier = Modifier.weight(1f).height(48.dp)) {
                            Text("Homework finished")
                        }
                        if (actions.startFocus) {
                            Button(onClick = onStartFocus, modifier = Modifier.weight(1f).height(48.dp)) { Text("Start focus") }
                        }
                    }
                    if (actions.runningLate) {
                        FilledTonalButton(onClick = onRunningLate, modifier = Modifier.height(48.dp)) {
                            Text("Running late")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FocusTimerCard(state: FocusUiState, nowMs: Long, onPause: () -> Unit, onFinish: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp).border(1.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(12.dp)),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.size(72.dp).border(4.dp, MaterialTheme.colorScheme.primary, CircleShape), contentAlignment = Alignment.Center) {
                Text(FocusJson.countdown(state.remaining(nowMs)), fontWeight = FontWeight.Bold)
            }
            Column(Modifier.weight(1f)) {
                Text("FOCUS", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(state.title, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Row {
                    TextButton(onClick = onPause) { Text(if (state.running) "Pause" else "Resume") }
                    TextButton(onClick = onFinish) { Text("Finish") }
                }
            }
        }
    }
}

@Composable
private fun NoTimeSection(state: TodayUiState, onPlan: (() -> Unit)? = null) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 18.dp, bottom = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            if (state.noTimeCount == 0) "No time yet" else "No time yet · ${state.noTimeCount}",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (onPlan != null && state.noTimeCount > 0) {
            BadgedBox(
                badge = {
                    Badge { Text(state.noTimeCount.toString()) }
                },
            ) {
                FilledTonalButton(onClick = onPlan, modifier = Modifier.height(40.dp)) {
                    Text("Plan")
                }
            }
        }
    }
    if (state.noTime.isEmpty()) {
        Text("Everything has a time.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    } else {
        state.noTime.forEach { chip ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp)
                    .padding(vertical = 4.dp)
                    .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(chip.title, fontWeight = FontWeight.SemiBold)
                    Text("${chip.lengthLabel} · due ${chip.dueLabel}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        if (onPlan == null) {
            Text(
                "Plan these on your computer, or drag them onto a day there. The phone shows what it planned.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}

@Composable
private fun SnackbarBar(
    message: String,
    onUndo: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 76.dp)
                .heightIn(min = 48.dp)
                .background(MaterialTheme.colorScheme.inverseSurface, RoundedCornerShape(8.dp))
                .padding(start = 16.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(message, color = MaterialTheme.colorScheme.inverseOnSurface, modifier = Modifier.weight(1f))
        TextButton(onClick = onUndo, modifier = Modifier.height(48.dp)) {
            Text("Undo", color = MaterialTheme.colorScheme.primary)
        }
        TextButton(onClick = onDismiss, modifier = Modifier.height(48.dp)) {
            Text("✕")
        }
    }
}
