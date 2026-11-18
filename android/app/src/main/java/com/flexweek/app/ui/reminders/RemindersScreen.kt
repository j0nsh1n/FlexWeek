package com.flexweek.app.ui.reminders

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.flexweek.app.BuildConfig
import com.flexweek.app.R
import com.flexweek.app.model.SyncLine
import com.flexweek.app.ui.components.SyncLineBar
import com.flexweek.app.ui.pair.DESKTOP_PAIR_PATH
import com.flexweek.app.ui.theme.syncOkColor
import com.flexweek.app.update.UpdateState
import com.flexweek.app.update.UpdateWords

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
    onReportProblem: () -> Unit = {},
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
    if (showUpdateSteps) {
        Column(Modifier.fillMaxSize().padding(24.dp)) {
            Text(
                "Install FlexWeek ${((updateState as? UpdateState.Available)?.offer?.version).orEmpty()}",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(vertical = 12.dp),
            )
            Text(
                "1. Download and check the update.\n2. Allow FlexWeek to install updates if Android asks.\n3. Android shows its own Install button.",
                style = MaterialTheme.typography.bodyLarge,
            )
            Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onUpdateSteps, modifier = Modifier.height(48.dp)) { Text("Back") }
                TextButton(onClick = onUpdateLater, modifier = Modifier.height(48.dp)) { Text("Later") }
            }
        }
        return
    }
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
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            "Let FlexWeek send notifications so it can tell you when to start homework.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.End) {
                            TextButton(onClick = onDismissPermissionBanner, modifier = Modifier.heightIn(min = 48.dp)) { Text("Not now") }
                            Button(onClick = onAllowNotifications, modifier = Modifier.heightIn(min = 48.dp)) { Text("Allow") }
                        }
                    }
                }
            }

            Heading("This phone")
            SettingRow(
                icon = R.drawable.ic_notifications,
                title = "Reminders",
                subtitle = if (state.notificationsAllowed) "Allowed" else "Not allowed. Switch on to let FlexWeek send them.",
                trailing = {
                    Switch(
                        checked = state.notificationsAllowed,
                        onCheckedChange = { onAllowNotifications() },
                        modifier = Modifier.semantics { contentDescription = "Reminders" },
                    )
                },
            )
            SettingRow(icon = R.drawable.ic_alarm, title = "Remind me before homework", subtitle = null)
            LeadPicker(state.leadMinutes, onLeadChange)
            SettingRow(
                icon = R.drawable.ic_timer,
                title = "On-time reminders",
                subtitle = "Android may send them up to 5 min late unless you allow this",
                trailing = {
                    Switch(
                        checked = state.exactReminders,
                        onCheckedChange = { onToggleExact() },
                        modifier = Modifier.semantics { contentDescription = "On-time reminders" },
                    )
                },
            )
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceContainerLow,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                Column(Modifier.padding(14.dp)) {
                    Text("What a reminder looks like", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(ReminderSample.TITLE, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
                    Text(ReminderSample.body(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            Heading("Your computer")
            ComputerCard(state, onSyncNow, onUnpair)

            Heading("Help")
            SettingRow(
                icon = R.drawable.ic_bug_report,
                title = "Report a problem",
                subtitle = "Opens a short form with your app version filled in",
                onClick = onReportProblem,
                trailing = { Icon(painterResource(R.drawable.ic_open_in_new), null, tint = MaterialTheme.colorScheme.onSurfaceVariant) },
            )
            UpdatesBlock(
                updateState, updateDaily, onCheckUpdates, onDownloadUpdate, onUpdateDaily, onUpdateLater, onUpdateSteps, onUpdatePermission,
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Heading(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 22.dp, bottom = 4.dp),
        maxLines = 1,
    )
}

@Composable
private fun ComputerCard(state: RemindersUiState, onSyncNow: () -> Unit, onUnpair: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(painterResource(R.drawable.ic_computer), null, Modifier.padding(end = 12.dp))
                Text(DeviceWords.title(state), style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Row(Modifier.padding(top = 4.dp, start = 36.dp), verticalAlignment = Alignment.Top) {
                if (state.paired) {
                    Box(
                        Modifier.padding(top = 6.dp, end = 8.dp).size(8.dp).clip(CircleShape)
                            .background(if (state.reachable) syncOkColor() else MaterialTheme.colorScheme.onSurfaceVariant),
                    )
                }
                Text(DeviceWords.line(state), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (!state.paired) {
                Text(
                    "Pair from the computer: $DESKTOP_PAIR_PATH.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp, start = 36.dp),
                )
            }
            Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (state.paired) {
                    FilledTonalButton(onClick = onSyncNow, enabled = !state.syncing, modifier = Modifier.heightIn(min = 48.dp)) {
                        Icon(painterResource(R.drawable.ic_sync), null, Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(if (state.syncing) "Syncing…" else "Sync now", maxLines = 1, softWrap = false)
                    }
                }
                // With no computer linked this is still the one way back to the pairing screen.
                TextButton(onClick = onUnpair, enabled = !state.syncing, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(if (state.paired) "Unpair" else "Pair again", maxLines = 1, softWrap = false)
                }
            }
            val result = state.problem ?: if (state.syncedJustNow) "Synced just now" else null
            result?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (state.problem != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
    }
}

@Composable
private fun UpdatesBlock(
    updateState: UpdateState,
    updateDaily: Boolean,
    onCheckUpdates: () -> Unit,
    onDownloadUpdate: () -> Unit,
    onUpdateDaily: (Boolean) -> Unit,
    onUpdateLater: () -> Unit,
    onUpdateSteps: () -> Unit,
    onUpdatePermission: () -> Unit,
) {
    SettingRow(
        icon = R.drawable.ic_system_update,
        title = "Updates",
        subtitle = "FlexWeek ${BuildConfig.VERSION_NAME}" + if (updateDaily) " · checks once a day" else "",
        trailing = {
            Switch(
                checked = updateDaily,
                onCheckedChange = onUpdateDaily,
                modifier = Modifier.semantics { contentDescription = "Check once a day" },
            )
        },
    )
    Column(Modifier.padding(start = 40.dp)) {
        when (val update = updateState) {
            is UpdateState.Available -> {
                Text("FlexWeek ${update.offer.version} is ready.")
                if (update.offer.size != null) Text("${update.offer.size / (1024 * 1024)} MB", style = MaterialTheme.typography.bodyMedium)
                update.offer.notes.forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
                Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onUpdateSteps, modifier = Modifier.heightIn(min = 48.dp)) { Text("See the steps", maxLines = 1) }
                    Button(onClick = onDownloadUpdate, modifier = Modifier.heightIn(min = 48.dp)) { Text("Download and install", maxLines = 1) }
                }
                update.message?.let { Text(it) }
            }
            is UpdateState.NeedsPermission -> {
                Text("To install FlexWeek, allow this app to install updates.")
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onUpdateLater, modifier = Modifier.heightIn(min = 48.dp)) { Text("Later") }
                    Button(onClick = onUpdatePermission, modifier = Modifier.heightIn(min = 48.dp)) { Text("Open the setting") }
                }
            }
            is UpdateState.Downloading -> {
                if (update.total > 0) LinearProgressIndicator(
                    progress = { update.received.toFloat() / update.total.toFloat() },
                    modifier = Modifier.fillMaxWidth(),
                ) else LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(UpdateWords.downloading(update.received, update.total))
            }
            is UpdateState.Verifying -> Text("Checking the downloaded file…")
            is UpdateState.Failed -> Text(update.reason, color = MaterialTheme.colorScheme.error)
            UpdateState.Checking -> Text("Checking for updates…")
            UpdateState.UpToDate -> Text(UpdateWords.latest(BuildConfig.VERSION_NAME), style = MaterialTheme.typography.bodyMedium)
            else -> Unit
        }
        TextButton(onClick = onCheckUpdates, enabled = updateState !is UpdateState.Checking, modifier = Modifier.heightIn(min = 48.dp)) { Text("Check now") }
    }
}

@Composable
private fun SettingRow(
    icon: Int,
    title: String,
    subtitle: String?,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .then(if (onClick != null) Modifier.clip(RoundedCornerShape(12.dp)).clickable(onClick = onClick) else Modifier)
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(icon), null, Modifier.padding(end = 16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            if (subtitle != null) {
                Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (trailing != null) {
            Spacer(Modifier.width(12.dp))
            trailing()
        }
    }
}

@Composable
private fun LeadPicker(selected: Int, onSelect: (Int) -> Unit) {
    val options = listOf(5, 10, 15)
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(start = 40.dp)) {
        options.forEachIndexed { i, min ->
            SegmentedButton(
                selected = selected == min,
                onClick = { onSelect(min) },
                shape = SegmentedButtonDefaults.itemShape(i, options.size),
                label = { Text("$min min", maxLines = 1, softWrap = false) },
            )
        }
    }
}
