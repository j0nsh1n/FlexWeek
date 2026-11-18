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
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.sp
import com.flexweek.app.R
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
import androidx.compose.ui.graphics.Color
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
                            TextButton(onClick = onJumpToday, modifier = Modifier.heightIn(min = 48.dp)) {
                                Text("Today")
                            }
                        }
                    }
                }
                val groups = TodayGroups.of(state.rows.filterNot { it is AgendaRow.Now && focusState?.assignmentId == it.assignmentId })
                groups.earlier.takeIf { it.isNotEmpty() && groups.upNext == null }?.let {
                    GroupHeading("Earlier")
                    it.forEach { row -> AgendaItemRow(row, onToggleHomework) }
                }
                groups.upNext?.let { row ->
                    NowRow(row, onFinishHomework, { row.assignmentId?.let(onStartFocus) }, onRunningLate, lateEnabled)
                }
                if (groups.later.isNotEmpty()) {
                    GroupHeading(if (groups.upNext != null || groups.earlier.isNotEmpty()) "Later today" else "Today")
                    groups.later.forEach { row -> AgendaItemRow(row, onToggleHomework) }
                }
                if (groups.upNext != null && groups.earlier.isNotEmpty()) {
                    GroupHeading("Earlier")
                    groups.earlier.forEach { row -> AgendaItemRow(row, onToggleHomework) }
                }
                groups.notes.forEach { row ->
                    when (row) {
                        AgendaRow.NothingLeft ->
                            Text(
                                "Nothing left today",
                                style = MaterialTheme.typography.titleLarge,
                                modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
                            )
                        AgendaRow.EmptyDay ->
                            Text(
                                "Nothing planned",
                                modifier = Modifier.fillMaxWidth().padding(vertical = 40.dp),
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        else -> Unit
                    }
                }
                NoTimeSection(state, v2Extras?.onPlan)
                Spacer(Modifier.height(96.dp))
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
                confirmButton = { Button(onClick = onKeepFocus) { Text(FocusSheetText.keepCurrent) } },
                dismissButton = { TextButton(onClick = onReplaceFocus) { Text(FocusSheetText.replace) } },
            )
        }
        finishPrompt?.let { focus ->
            androidx.compose.material3.AlertDialog(
                onDismissRequest = onKeepGoing,
                title = { Text(FocusSheetText.finishTitle) },
                text = { Text(FocusJson.finishText(focus.elapsedMin(nowMs), focus.title)) },
                confirmButton = { Button(onClick = onKeepGoing) { Text(FocusSheetText.keepGoing) } },
                dismissButton = { TextButton(onClick = onEndSession) { Text(FocusSheetText.endSession) } },
            )
        }
    }
}

data class TodayV2Extras(
    val onPlan: () -> Unit,
)

@Composable
private fun DayChipRow(days: List<DayChip>, onSelectDay: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        days.forEach { day ->
            val selected = day.selected
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .heightIn(min = 64.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .clickable { onSelectDay(day.index) }
                        .padding(vertical = 4.dp)
                        .semantics { contentDescription = "${day.label} ${day.date}" },
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    day.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
                // The number sits in a fixed circle, so a due dot below never moves it.
                Box(
                    Modifier
                        .padding(top = 2.dp)
                        .size(36.dp)
                        .clip(CircleShape)
                        .then(
                            if (selected) {
                                Modifier.background(MaterialTheme.colorScheme.primary)
                            } else if (day.isToday) {
                                Modifier.border(1.dp, MaterialTheme.colorScheme.primary, CircleShape)
                            } else {
                                Modifier
                            },
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        day.date.toString(),
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                    )
                }
                Box(
                    Modifier
                        .padding(top = 2.dp)
                        .size(5.dp)
                        .clip(CircleShape)
                        .then(if (day.hasDot) Modifier.background(categoryColor("hw")) else Modifier),
                )
            }
        }
    }
}

@Composable
private fun GroupHeading(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        modifier = modifier.padding(top = 18.dp, bottom = 4.dp),
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        maxLines = 1,
    )
}

@Composable
private fun AgendaItemRow(row: AgendaRow.Item, onToggle: (String) -> Unit) {
    val (clock, meridiem) = TimeColumn.split(row.timeLabel)
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .alpha(if (row.past || row.done) 0.75f else 1f)
                .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.width(56.dp).padding(end = 8.dp), horizontalAlignment = Alignment.End) {
            Text(clock, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            if (meridiem != null) {
                Text(meridiem, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            }
        }
        Box(
            Modifier
                .width(4.dp)
                .height(40.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(categoryColor(row.category)),
        )
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(
                row.title,
                style = MaterialTheme.typography.bodyLarge,
                textDecoration = if (row.done) TextDecoration.LineThrough else null,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(row.detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        if (row.homework) {
            Box(
                Modifier.size(48.dp).clip(CircleShape).clickable { onToggle(row.id) }.semantics {
                    contentDescription = if (row.done) "Mark ${row.title} not finished" else "Mark ${row.title} finished"
                },
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    Modifier
                        .size(26.dp)
                        .border(2.dp, if (row.done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline, CircleShape)
                        .background(if (row.done) MaterialTheme.colorScheme.primary else Color.Transparent, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    if (row.done) {
                        Icon(painterResource(R.drawable.ic_check), null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onPrimary)
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
    val colors = MaterialTheme.colorScheme
    val actions = nowRowActions(row, lateEnabled)
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp)
                .clip(RoundedCornerShape(24.dp))
                .background(colors.primaryContainer)
                .padding(16.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                row.kick.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = colors.onPrimaryContainer,
                maxLines = 1,
            )
            Text(
                row.minsLabel.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = colors.onPrimaryContainer,
                maxLines = 1,
            )
        }
        Text(row.title, style = MaterialTheme.typography.titleLarge, color = colors.onPrimaryContainer, modifier = Modifier.padding(top = 4.dp))
        Text(row.whenLine, style = MaterialTheme.typography.bodyMedium, color = colors.onPrimaryContainer)
        if (row.thenTitle != null && row.thenTime != null) {
            Text(
                "then ${row.thenTitle} at ${row.thenTime}",
                style = MaterialTheme.typography.bodyMedium,
                color = colors.onPrimaryContainer,
            )
        }
        if (actions.finishHomework || actions.startFocus || actions.runningLate) {
            BoxWithConstraints(Modifier.fillMaxWidth().padding(top = 14.dp)) {
                val layout = UpNextLayout.of(actions, maxWidth.value, LocalDensity.current.fontScale)
                val onCard = ButtonDefaults.filledTonalButtonColors(containerColor = colors.surfaceContainerLowest, contentColor = colors.primary)
                val pad = PaddingValues(horizontal = 12.dp)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (layout.startFocus) {
                        Button(onClick = onStartFocus, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), contentPadding = pad) {
                            Icon(painterResource(R.drawable.ic_timer), null, Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(UpNextLayout.START_FOCUS, maxLines = 1, softWrap = false)
                        }
                    }
                    val done: @Composable (Modifier) -> Unit = { m ->
                        FilledTonalButton(onClick = { onFinishHomework(row.id) }, modifier = m.heightIn(min = 48.dp), colors = onCard, contentPadding = pad) {
                            Icon(painterResource(R.drawable.ic_check), null, Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(UpNextLayout.DONE, maxLines = 1, softWrap = false)
                        }
                    }
                    val late: @Composable (Modifier) -> Unit = { m ->
                        FilledTonalButton(onClick = onRunningLate, modifier = m.heightIn(min = 48.dp), colors = onCard, contentPadding = pad) {
                            Icon(painterResource(R.drawable.ic_schedule), null, Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(UpNextLayout.RUNNING_LATE, maxLines = 1, softWrap = false)
                        }
                    }
                    if (layout.stacked) {
                        done(Modifier.fillMaxWidth())
                        late(Modifier.fillMaxWidth())
                    } else if (layout.done && layout.late) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            done(Modifier.weight(1f))
                            late(Modifier.weight(1f))
                        }
                    } else {
                        if (layout.done) done(Modifier.fillMaxWidth())
                        if (layout.late) late(Modifier.fillMaxWidth())
                    }
                }
            }
        }
    }
}

@Composable
private fun FocusTimerCard(state: FocusUiState, nowMs: Long, onPause: () -> Unit, onFinish: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Surface(
        shape = RoundedCornerShape(24.dp),
        color = colors.primaryContainer,
        contentColor = colors.onPrimaryContainer,
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.size(76.dp).border(4.dp, colors.primary, CircleShape), contentAlignment = Alignment.Center) {
                Text(FocusJson.countdown(state.remaining(nowMs)), fontWeight = FontWeight.Bold, maxLines = 1)
            }
            Column(Modifier.weight(1f)) {
                Text("FOCUS", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
                Text(state.title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
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
            .padding(top = 18.dp, bottom = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            if (state.noTimeCount == 0) "No time yet" else "No time yet · ${state.noTimeCount}",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
            maxLines = 1,
            modifier = Modifier.weight(1f),
        )
        if (onPlan != null && state.noTimeCount > 0) {
            FilledTonalButton(onClick = onPlan, modifier = Modifier.heightIn(min = 40.dp), contentPadding = PaddingValues(horizontal = 16.dp)) {
                Text("Plan", maxLines = 1, softWrap = false)
            }
        }
    }
    if (state.noTime.isEmpty()) {
        Text("Everything has a time.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    } else {
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(MaterialTheme.colorScheme.surfaceContainerLow)
                .padding(vertical = 4.dp),
        ) {
            state.noTime.forEach { chip ->
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.width(4.dp).height(40.dp).clip(RoundedCornerShape(2.dp)).background(categoryColor("homework")))
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(chip.title, style = MaterialTheme.typography.bodyLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Text(
                            "${chip.lengthLabel} · due ${chip.dueLabel}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
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
                .padding(start = 12.dp, end = 12.dp, bottom = 88.dp)
                .heightIn(min = 48.dp)
                .background(MaterialTheme.colorScheme.inverseSurface, RoundedCornerShape(8.dp))
                .padding(start = 16.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(message, color = MaterialTheme.colorScheme.inverseOnSurface, modifier = Modifier.weight(1f))
        TextButton(onClick = onUndo, modifier = Modifier.heightIn(min = 48.dp)) {
            Text("Undo", color = MaterialTheme.colorScheme.primary)
        }
        TextButton(onClick = onDismiss, modifier = Modifier.heightIn(min = 48.dp)) {
            Text("✕")
        }
    }
}
