package com.flexweek.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.flexweek.app.model.TodayJson
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.flexweek.app.model.SyncLine
import com.flexweek.app.ui.pair.PairScreen
import com.flexweek.app.ui.pair.PairViewModel
import com.flexweek.app.ui.reminders.RemindersScreen
import com.flexweek.app.ui.reminders.RemindersViewModel
import com.flexweek.app.ui.theme.FlexWeekTheme
import com.flexweek.app.ui.today.TodayScreen
import com.flexweek.app.ui.today.TodayViewModel
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as FlexWeekApp
        val tweaks = ScreenshotTweaks.fromIntent(intent)
        if (tweaks.prePaired && !app.core.isPaired()) {
            app.core.pairWithCode(com.flexweek.app.core.DemoSchedule.VALID_PAIR_CODE)
        }
        (app.core as? com.flexweek.app.core.FakeFlexWeekCore)?.setSyncState(tweaks.syncState)
        setContent {
            FlexWeekTheme(darkTheme = tweaks.darkTheme, largeText = tweaks.largeText) {
                FlexWeekRoot(app.core, tweaks)
            }
        }
    }
}

data class ScreenshotTweaks(
    val startScreen: StartScreen = StartScreen.Auto,
    val darkTheme: Boolean = false,
    val largeText: Boolean = false,
    val prePaired: Boolean = false,
    val syncState: com.flexweek.app.core.SyncState = com.flexweek.app.core.SyncState.SYNCED,
) {
    enum class StartScreen {
        Auto,
        Pair,
        Today,
        Reminders,
    }

    companion object {
        fun fromIntent(intent: android.content.Intent): ScreenshotTweaks {
            val screen =
                when (intent.getStringExtra("screen")) {
                    "pair" -> StartScreen.Pair
                    "today" -> StartScreen.Today
                    "reminders" -> StartScreen.Reminders
                    else -> StartScreen.Auto
                }
            val sync =
                when (intent.getStringExtra("sync")) {
                    "busy" -> com.flexweek.app.core.SyncState.SYNCING
                    "off" -> com.flexweek.app.core.SyncState.UNREACHABLE
                    else -> com.flexweek.app.core.SyncState.SYNCED
                }
            return ScreenshotTweaks(
                startScreen = screen,
                darkTheme = intent.getBooleanExtra("darkTheme", false),
                largeText = intent.getBooleanExtra("largeText", false),
                prePaired =
                    when (screen) {
                        StartScreen.Today, StartScreen.Reminders -> true
                        else -> intent.getBooleanExtra("prePaired", false)
                    },
                syncState = sync,
            )
        }
    }
}

private enum class MainTab {
    Today,
    Reminders,
}

@Composable
private fun FlexWeekRoot(core: com.flexweek.app.core.FlexWeekCore, tweaks: ScreenshotTweaks) {
    var paired by remember { mutableStateOf(core.isPaired() || tweaks.prePaired) }
    var tab by remember {
        mutableStateOf(
            when (tweaks.startScreen) {
                ScreenshotTweaks.StartScreen.Reminders -> MainTab.Reminders
                else -> MainTab.Today
            },
        )
    }
    val showPair =
        tweaks.startScreen == ScreenshotTweaks.StartScreen.Pair ||
            (!paired && tweaks.startScreen != ScreenshotTweaks.StartScreen.Today &&
                tweaks.startScreen != ScreenshotTweaks.StartScreen.Reminders)
    if (showPair) {
        val vm =
            remember {
                PairViewModel(core) { paired = true }
            }
        val pairState by vm.uiState
        PairScreen(
            state = pairState,
            onShowCode = vm::showCodeEntry,
            onShowQr = vm::showQr,
            onCodeChange = vm::onCodeChange,
            onPair = vm::submitPair,
        )
        return
    }
    val todayVm = viewModel { TodayViewModel(core) }
    val remindersVm = viewModel { RemindersViewModel(core) }
    val syncLine =
        remember(todayVm.uiState.syncLine, remindersVm.state.syncing) {
            val sync = JSONObject(core.syncStatus())
            SyncLine(sync.getString("state"), sync.getString("line"))
        }
    Scaffold(
        bottomBar = {
            NavigationBar(Modifier.height(64.dp)) {
                NavigationBarItem(
                    selected = tab == MainTab.Today,
                    onClick = { tab = MainTab.Today },
                    icon = { Text("▤") },
                    label = { Text("Today") },
                )
                NavigationBarItem(
                    selected = tab == MainTab.Reminders,
                    onClick = { tab = MainTab.Reminders },
                    icon = { Text("⚙") },
                    label = { Text("Settings") },
                )
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            when (tab) {
                MainTab.Today ->
                    TodayScreen(
                        state = todayVm.uiState,
                        onSelectDay = todayVm::selectDay,
                        onJumpToday = todayVm::jumpToToday,
                        onToggleHomework = todayVm::toggleHomework,
                        onUndo = todayVm::undoLast,
                        onDismissSnack = todayVm::dismissSnackbar,
                    )
                MainTab.Reminders ->
                    RemindersScreen(
                        syncLine = syncLine,
                        state = remindersVm.state,
                        onAllowNotifications = remindersVm::allowNotifications,
                        onLeadChange = remindersVm::setLeadMinutes,
                        onToggleExact = remindersVm::toggleExact,
                        onSyncNow = remindersVm::syncNow,
                    )
            }
        }
    }
}
