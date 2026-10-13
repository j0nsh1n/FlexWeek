package com.flexweek.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
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
import com.flexweek.app.ui.today.TodayV2Extras
import com.flexweek.app.ui.today.TodayViewModel
import com.flexweek.app.ui.v2.AddHomeworkSheet
import com.flexweek.app.ui.v2.AddHomeworkViewModel
import com.flexweek.app.ui.v2.PlanRecordSheet
import com.flexweek.app.ui.v2.PlanRecordViewModel
import com.flexweek.app.ui.v2.RunningLateSheet
import com.flexweek.app.ui.v2.RunningLateViewModel
import com.flexweek.app.ui.v2.WeekScreen
import com.flexweek.app.ui.v2.WeekViewModel
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
    val openSheet: V2Sheet? = null,
) {
    enum class StartScreen {
        Auto,
        Pair,
        Today,
        Reminders,
        Week,
    }

    enum class V2Sheet {
        Add,
        Plan,
        Late,
    }

    companion object {
        fun fromIntent(intent: android.content.Intent): ScreenshotTweaks {
            val screen =
                when (intent.getStringExtra("screen")) {
                    "pair" -> StartScreen.Pair
                    "today" -> StartScreen.Today
                    "reminders" -> StartScreen.Reminders
                    "week" -> StartScreen.Week
                    else -> StartScreen.Auto
                }
            val sync =
                when (intent.getStringExtra("sync")) {
                    "busy" -> com.flexweek.app.core.SyncState.SYNCING
                    "off" -> com.flexweek.app.core.SyncState.UNREACHABLE
                    else -> com.flexweek.app.core.SyncState.SYNCED
                }
            val sheet =
                when (intent.getStringExtra("sheet")) {
                    "add" -> V2Sheet.Add
                    "plan" -> V2Sheet.Plan
                    "late" -> V2Sheet.Late
                    else -> null
                }
            return ScreenshotTweaks(
                startScreen = screen,
                darkTheme = intent.getBooleanExtra("darkTheme", false),
                largeText = intent.getBooleanExtra("largeText", false),
                prePaired =
                    when (screen) {
                        StartScreen.Today, StartScreen.Reminders, StartScreen.Week -> true
                        else -> intent.getBooleanExtra("prePaired", false)
                    },
                syncState = sync,
                openSheet = sheet,
            )
        }
    }
}

private enum class MainTab {
    Today,
    Week,
    Reminders,
}

private enum class ActiveSheet {
    None,
    Add,
    Plan,
    Late,
}

@Composable
private fun FlexWeekRoot(core: com.flexweek.app.core.FlexWeekCore, tweaks: ScreenshotTweaks) {
    val v2 = BuildConfig.V2_ENABLED
    var paired by remember { mutableStateOf(core.isPaired() || tweaks.prePaired) }
    var tab by remember {
        mutableStateOf(
            when (tweaks.startScreen) {
                ScreenshotTweaks.StartScreen.Reminders -> MainTab.Reminders
                ScreenshotTweaks.StartScreen.Week -> if (v2) MainTab.Week else MainTab.Today
                else -> MainTab.Today
            },
        )
    }
    var sheet by remember {
        mutableStateOf(
            when (tweaks.openSheet) {
                ScreenshotTweaks.V2Sheet.Add -> ActiveSheet.Add
                ScreenshotTweaks.V2Sheet.Plan -> ActiveSheet.Plan
                ScreenshotTweaks.V2Sheet.Late -> ActiveSheet.Late
                else -> ActiveSheet.None
            },
        )
    }
    val showPair =
        tweaks.startScreen == ScreenshotTweaks.StartScreen.Pair ||
            (!paired && tweaks.startScreen != ScreenshotTweaks.StartScreen.Today &&
                tweaks.startScreen != ScreenshotTweaks.StartScreen.Reminders &&
                tweaks.startScreen != ScreenshotTweaks.StartScreen.Week)
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
    val weekVm = if (v2) viewModel { WeekViewModel(core) } else null
    val syncLine =
        remember(todayVm.uiState.syncLine, remindersVm.state.syncing) {
            val sync = JSONObject(core.syncStatus())
            SyncLine(sync.getString("state"), sync.getString("line"))
        }
    val closeSheet: () -> Unit = {
        sheet = ActiveSheet.None
        todayVm.refreshAgenda()
        weekVm?.refresh()
        Unit
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
                if (v2) {
                    NavigationBarItem(
                        selected = tab == MainTab.Week,
                        onClick = { tab = MainTab.Week },
                        icon = { Text("▦") },
                        label = { Text("Week") },
                    )
                }
                NavigationBarItem(
                    selected = tab == MainTab.Reminders,
                    onClick = { tab = MainTab.Reminders },
                    icon = { Text("⚙") },
                    label = { Text("Settings") },
                )
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            Column(Modifier.fillMaxSize()) {
                when (tab) {
                    MainTab.Today ->
                        TodayScreen(
                            state = todayVm.uiState,
                            onSelectDay = todayVm::selectDay,
                            onJumpToday = todayVm::jumpToToday,
                            onToggleHomework = todayVm::toggleHomework,
                            onUndo = todayVm::undoLast,
                            onDismissSnack = todayVm::dismissSnackbar,
                            onFinishHomework = todayVm::toggleHomework,
                            onStartFocus = { todayVm.showMessage("Focus timer: a notification with the countdown, Pause and Finish.") },
                            onRunningLate = { if (v2) sheet = ActiveSheet.Late },
                            v2Extras =
                                if (v2) {
                                    TodayV2Extras(
                                        showFab = sheet == ActiveSheet.None,
                                        onAdd = { sheet = ActiveSheet.Add },
                                        onPlan = {
                                            sheet = ActiveSheet.Plan
                                        },
                                    )
                                } else {
                                    null
                                },
                        )
                    MainTab.Week ->
                        weekVm?.let { vm ->
                            WeekScreen(
                                state = vm.state,
                                syncLine = syncLine,
                                onOpenDay = { day ->
                                    todayVm.selectDay(day)
                                    tab = MainTab.Today
                                },
                            )
                        }
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
            if (v2 && sheet == ActiveSheet.Add) {
                val addVm =
                    remember {
                        AddHomeworkViewModel(core) { message ->
                            todayVm.showMessage(message)
                            closeSheet()
                        }
                    }
                AddHomeworkSheet(
                    draft = addVm.draft,
                    stepProblem = addVm.stepProblem,
                    onTitleChange = addVm::onTitleChange,
                    onDuePick = addVm::onDuePick,
                    onWhenMode = addVm::onWhenMode,
                    onEstimate = addVm::onEstimate,
                    onSessions = addVm::onSessions,
                    onStepJump = addVm::goToStep,
                    onBack = addVm::back,
                    onNext = addVm::nextOrSave,
                    onCancel = closeSheet,
                )
            }
            if (v2 && sheet == ActiveSheet.Plan) {
                val planVm =
                    remember(sheet) {
                        PlanRecordViewModel(
                            core,
                            onAccepted = closeSheet,
                            onDismiss = { sheet = ActiveSheet.None },
                        )
                    }
                planVm.record?.let { record ->
                    PlanRecordSheet(record, onUndo = planVm::undo, onAccept = planVm::accept)
                }
            }
            if (v2 && sheet == ActiveSheet.Late) {
                val lateVm =
                    remember {
                        RunningLateViewModel(
                            core,
                            onAccepted = closeSheet,
                            onDismiss = { sheet = ActiveSheet.None },
                        )
                    }
                lateVm.preview?.let { preview ->
                    RunningLateSheet(
                        preview = preview,
                        minutes = lateVm.minutes,
                        onMinutes = lateVm::pickMinutes,
                        onCancel = lateVm::cancel,
                        onAccept = lateVm::accept,
                    )
                }
            }
        }
    }
}
