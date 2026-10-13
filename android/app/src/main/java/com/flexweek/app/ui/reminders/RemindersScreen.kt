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

@Composable
fun RemindersScreen(
    syncLine: SyncLine,
    state: RemindersUiState,
    onAllowNotifications: () -> Unit,
    onLeadChange: (Int) -> Unit,
    onToggleExact: () -> Unit,
    onSyncNow: () -> Unit,
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
                            TextButton(onClick = {}, modifier = Modifier.height(48.dp)) { Text("Not now") }
                        }
                    }
                }
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
                    TextButton(onClick = {}, modifier = Modifier.height(48.dp)) { Text("Unpair") }
                },
            )
            Text(
                "Add another device from the computer, not from here: Settings › Devices › Link a device.",
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
