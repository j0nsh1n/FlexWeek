package com.flexweek.app.ui.v2

import android.app.DatePickerDialog
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.flexweek.app.R
import com.flexweek.app.model.AddHomeworkWords
import com.flexweek.app.model.DueChips
import com.flexweek.app.model.HomeworkDraft
import java.time.LocalDate
import java.time.ZoneId

/** Add homework: one full-screen form with every question on the page. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AddHomeworkScreen(
    draft: HomeworkDraft,
    recentTitles: List<String>,
    problem: String?,
    onTitleChange: (String) -> Unit,
    onDuePick: (String) -> Unit,
    onEstimate: (Int) -> Unit,
    onOtherLength: () -> Unit,
    onOtherMinutes: (String) -> Unit,
    onSessions: (String) -> Unit,
    onSave: () -> Unit,
    onClose: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    Surface(Modifier.fillMaxSize(), color = colors.surface) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose, modifier = Modifier.size(48.dp)) {
                    Icon(painterResource(R.drawable.ic_close), contentDescription = "Close")
                }
                Text("Add homework", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f).padding(start = 8.dp), maxLines = 1)
                Button(onClick = onSave, enabled = draft.canSave, modifier = Modifier.padding(end = 12.dp).heightIn(min = 48.dp)) {
                    Text("Save", maxLines = 1, softWrap = false)
                }
            }
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
                val focus = remember { FocusRequester() }
                // Open ready to type, but a rotation with a title already typed does not pop the keyboard again.
                LaunchedEffect(Unit) { if (draft.title.isEmpty()) focus.requestFocus() }
                OutlinedTextField(
                    value = draft.title,
                    onValueChange = onTitleChange,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp).focusRequester(focus),
                    label = { Text("What is it?") },
                    singleLine = true,
                    isError = problem != null && draft.title.isBlank(),
                )
                problem?.let { Text(it, color = colors.error, modifier = Modifier.padding(top = 4.dp)) }

                SectionLabel("Due")
                val context = LocalContext.current
                val today = LocalDate.now()
                val chips = DueChips.forToday(today)
                val picked = runCatching { LocalDate.parse(draft.due.take(10)) }.getOrNull()
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    chips.forEach { chip ->
                        ChoiceChip(chip.label, draft.due == chip.date.toString()) { onDuePick(chip.date.toString()) }
                    }
                    // A day picked from the calendar that is not one of the quick chips still shows as chosen.
                    if (picked != null && chips.none { it.date == picked }) {
                        ChoiceChip(DueChips.label(picked, today), true) {}
                    }
                    SuggestionChip(
                        onClick = {
                            DatePickerDialog(context, { _, year, month, day ->
                                onDuePick(LocalDate.of(year, month + 1, day).toString())
                            }, today.year, today.monthValue - 1, today.dayOfMonth).apply {
                                datePicker.minDate = today.atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
                            }.show()
                        },
                        label = { Text("Pick a day") },
                        icon = { Icon(painterResource(R.drawable.ic_today), null, Modifier.size(18.dp)) },
                    )
                }

                SectionLabel("How long?")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    AddHomeworkWords.LENGTHS.forEach { (label, minutes) ->
                        ChoiceChip(label, !draft.otherLength && draft.estimateMin == minutes) { onEstimate(minutes) }
                    }
                    ChoiceChip(AddHomeworkWords.OTHER, draft.otherLength) { onOtherLength() }
                }
                if (draft.otherLength) {
                    OutlinedTextField(
                        value = if (draft.estimateMin > 0) draft.estimateMin.toString() else "",
                        onValueChange = onOtherMinutes,
                        modifier = Modifier.padding(top = 8.dp),
                        label = { Text("Minutes") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    )
                }

                SectionLabel("Sessions")
                val options = listOf("In one go" to "one", "Spread over days" to "spread")
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    options.forEachIndexed { i, (label, value) ->
                        SegmentedButton(
                            selected = draft.sessions == value,
                            onClick = { onSessions(value) },
                            shape = SegmentedButtonDefaults.itemShape(i, options.size),
                            label = { Text(label, maxLines = 1) },
                        )
                    }
                }
                Text(
                    if (draft.sessions == "one") "In one go means one homework session."
                    else "Spread over days means more than one session.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = colors.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )

                if (recentTitles.isNotEmpty()) {
                    Text("Recent", style = MaterialTheme.typography.labelSmall, color = colors.onSurfaceVariant, modifier = Modifier.padding(top = 20.dp, bottom = 4.dp))
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        recentTitles.forEach { title ->
                            SuggestionChip(onClick = { onTitleChange(title) }, label = { Text(title, maxLines = 1) })
                        }
                    }
                }
                Text(
                    AddHomeworkWords.TIME_NOTE,
                    style = MaterialTheme.typography.bodyMedium,
                    color = colors.onSurfaceVariant,
                    modifier = Modifier.padding(top = 20.dp, bottom = 24.dp),
                )
            }
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 20.dp, bottom = 8.dp))
}

@Composable
private fun ChoiceChip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label, maxLines = 1) },
        leadingIcon = if (selected) { { Icon(painterResource(R.drawable.ic_check), null, Modifier.size(18.dp)) } } else null,
    )
}
