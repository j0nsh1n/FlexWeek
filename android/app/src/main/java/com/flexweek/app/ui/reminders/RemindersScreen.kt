package com.flexweek.app.ui.reminders

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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.flexweek.app.ui.components.SyncLineBar
import com.flexweek.app.model.SyncLine
import com.flexweek.app.ui.pair.DESKTOP_PAIR_PATH
import com.flexweek.app.update.UpdateState

@Composable
fun RemindersScreen(
    syncLine: SyncLine,
    state: RemindersUiState,
    onAllowNotifications: () -> Unit,
    onDismissPermissionBanner: () -> Unit = {},
    onLeadChange: (Int) -> Unit,
    onToggleExact: () -> Unit,
    onSyncNow: () -> Unit,
    onUnpair: () -> Unit,
    updateState: UpdateState = UpdateState.Idle,
    updateDaily: Boolean = true,
    onCheckUpdates: () -> Unit = {},
    onDownloadUpdate: () -> Unit = {},
    onUpdateDaily: (Boolean) -> Unit = {},
    onUpdateLater: () -> Unit = {},
    onUpdateSteps: () -> Unit = {},
    onUpdatePermission: () -> Unit = {},
    showUpdateSteps: Boolean = false,
) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Text("Settings", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(vertical = 8.dp))
            SyncLineBar(syncLine)
        }
        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        ) {
            if (state.showPermissionBanner) {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(
                            "Let FlexWeek send notifications so it can tell you when to start homework.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Row(Modifier.padding(top = 8.dp), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                            Button(onClick = onAllowNotifications, modifier = Modifier.height(48.dp)) {
                                Text("Allow")
                            }
                            TextButton(onClick = onDismissPermissionBanner, modifier = Modifier.height(48.dp)) { Text("Not now") }
                        }
                    }
                }
            }
            Text("Updates", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 18.dp, bottom = 6.dp))
            SettingRow("Check once a day", "Look when you open the app.", trailing = {
                Switch(checked = updateDaily, onCheckedChange = onUpdateDaily,
                    modifier = Modifier.semantics { contentDescription = "Check once a day" })
            })
            when (val update = updateState) {
                is UpdateState.Available -> {
                    Text("FlexWeek ${update.offer.version} is ready.")
                    if (update.offer.size != null) Text("${update.offer.size / (1024 * 1024)} MB")
                    update.offer.notes.forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    Row {
                        Button(onClick = onDownloadUpdate, modifier = Modifier.height(48.dp)) { Text("Download and install") }
                        TextButton(onClick = onUpdateSteps, modifier = Modifier.height(48.dp)) { Text("See the steps") }
                    }
                    update.message?.let { Text(it) }
                }
                is UpdateState.NeedsPermission -> {
                    Text("To install FlexWeek, allow this app to install updates.")
                    Button(onClick = onUpdatePermission) { Text("Open the setting") }
                    TextButton(onClick = onUpdateLater) { Text("Later") }
                }
                is UpdateState.Downloading -> {
                    if (update.total > 0) LinearProgressIndicator(
                        progress = { update.received.toFloat() / update.total.toFloat() },
                        modifier = Modifier.fillMaxWidth(),
                    ) else LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    Text("Downloading ${update.received} / ${update.total}")
                }
                is UpdateState.Failed -> Text(update.reason)
                UpdateState.Checking -> Text("Checking for updates…")
                else -> Unit
            }
            TextButton(onClick = onCheckUpdates, enabled = updateState !is UpdateState.Checking) { Text("Check now") }
            if (showUpdateSteps) {
                Text("Install FlexWeek ${((updateState as? UpdateState.Available)?.offer?.version).orEmpty()}",
                    style = MaterialTheme.typography.titleMedium)
                Text("1. Download and check the update.\n2. Allow FlexWeek to install updates if Android asks.\n3. Android shows its own Install button.")
                TextButton(onClick = onUpdateSteps) { Text("Back") }
            }
            SettingRow(
                title = "Remind me before homework",
                subtitle = "The same lead time as your computer uses.",
                trailing = {
                    LeadPicker(state.leadMinutes, onLeadChange)
                },
            )
            SettingRow(
                title = "Exact reminders",
                subtitle =
                    "Android turns exact alarms off for new apps. Without it a reminder may come up to 5 minutes late.",
                trailing = {
                    Switch(
                        checked = state.exactReminders,
                        onCheckedChange = { onToggleExact() },
                        modifier = Modifier.semantics { contentDescription = "Exact reminders" },
                    )
                },
            )
            SettingRow(
                title = "Sound",
                subtitle = "Chime, as on your computer. Alarm sounds stay on the computer.",
            )
            Text(
                "What a reminder looks like",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 18.dp, bottom = 6.dp),
            )
            Surface(shape = RoundedCornerShape(16.dp), tonalElevation = 2.dp, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text("FlexWeek · now", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("History essay starts in ${state.leadMinutes} min", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
                    Text("7:00 PM · 1 h · then free until 10 PM", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(
                "Devices",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 18.dp, bottom = 6.dp),
            )
            SettingRow(
                title = state.deviceName,
                subtitle = "Paired ${state.pairedAt} · ${if (state.reachable) "on the same Wi‑Fi" else "not reachable now"}",
                trailing = {
                    TextButton(onClick = onUnpair, enabled = !state.syncing, modifier = Modifier.height(48.dp)) { Text("Unpair") }
                },
            )
            Text(
                "Add another device from the computer: $DESKTOP_PAIR_PATH.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(vertical = 8.dp),
            )
            Button(
                onClick = onSyncNow,
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp).height(48.dp),
                enabled = !state.syncing,
            ) {
                Text(if (state.syncing) "Syncing…" else "Sync now")
            }
        }
    }
}

@Composable
private fun SettingRow(
    title: String,
    subtitle: String,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Medium)
            Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        trailing?.invoke()
    }
}

@Composable
private fun LeadPicker(selected: Int, onSelect: (Int) -> Unit) {
    Row {
        listOf(5, 10, 15).forEach { min ->
            TextButton(onClick = { onSelect(min) }, modifier = Modifier.height(48.dp)) {
                Text(
                    "$min min",
                    fontWeight = if (selected == min) FontWeight.SemiBold else FontWeight.Normal,
                )
            }
        }
    }
}
