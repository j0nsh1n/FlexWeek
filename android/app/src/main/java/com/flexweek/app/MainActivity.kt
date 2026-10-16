package com.flexweek.app

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.flexweek.app.model.SyncLine
import com.flexweek.app.ui.pair.PairScreen
import com.flexweek.app.ui.pair.PairViewModel
import com.flexweek.app.ui.reminders.RemindersScreen
import com.flexweek.app.ui.reminders.RemindersViewModel
import com.flexweek.app.ui.reminders.SharedPreferenceReminderPrefs
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
import com.flexweek.app.ui.v2.SheetScrim
import com.flexweek.app.ui.v2.WeekScreen
import com.flexweek.app.ui.v2.WeekViewModel
import androidx.compose.material3.Surface
import androidx.compose.material3.TextButton
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import com.flexweek.app.system.syncWhileForeground
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.runtime.DisposableEffect
import com.flexweek.app.update.HttpUpdateSource
import com.flexweek.app.update.PackageUpdateInstaller
import com.flexweek.app.update.SharedPreferenceUpdatePrefs
import com.flexweek.app.update.UpdateViewModel
import com.flexweek.app.update.UpdateState

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as FlexWeekApp
        val tweaks = ScreenshotTweaks.fromIntent(intent)
        setContent {
            FlexWeekTheme(darkTheme = tweaks.darkTheme, largeText = tweaks.largeText) {
                val startup by app.startup.collectAsState()
                val core = startup.core
                if (core == null) {
                    StartupScreen(startup.problem)
                } else {
                    if (core is com.flexweek.app.core.FakeFlexWeekCore) {
                        if (tweaks.prePaired && !core.isPaired()) {
                            core.pairWithCode(com.flexweek.app.core.DemoSchedule.VALID_PAIR_CODE)
                        }
                        core.setSyncState(tweaks.syncState)
                    }
                    FlexWeekRoot(core, startup.paired, tweaks, this@MainActivity)
                }
            }
        }
    }
}

data class ScreenshotTweaks(
    val startScreen: StartScreen = StartScreen.Auto,
    // null follows the phone's light or dark setting; true or false is a screenshot forcing one.
    val darkTheme: Boolean? = null,
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
            val extras = intent.extras
            return parse(extras?.keySet()?.associateWith { extras.get(it) } ?: emptyMap())
        }

        fun parse(extras: Map<String, Any?>): ScreenshotTweaks {
            val screen =
                when (extras["screen"] as? String) {
                    "pair" -> StartScreen.Pair
                    "today" -> StartScreen.Today
                    "reminders" -> StartScreen.Reminders
                    "week" -> StartScreen.Week
                    else -> StartScreen.Auto
                }
            val sync =
                when (extras["sync"] as? String) {
                    "busy" -> com.flexweek.app.core.SyncState.SYNCING
                    "off" -> com.flexweek.app.core.SyncState.UNREACHABLE
                    else -> com.flexweek.app.core.SyncState.SYNCED
                }
            val sheet =
                when (extras["sheet"] as? String) {
                    "add" -> V2Sheet.Add
                    "plan" -> V2Sheet.Plan
                    "late" -> V2Sheet.Late
                    else -> null
                }
            return ScreenshotTweaks(
                startScreen = screen,
                darkTheme = extras["darkTheme"] as? Boolean,
                largeText = extras["largeText"] as? Boolean ?: false,
                prePaired =
                    when (screen) {
                        StartScreen.Today, StartScreen.Reminders, StartScreen.Week -> true
                        else -> extras["prePaired"] as? Boolean ?: false
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
private fun StartupScreen(problem: String?) {
    Surface(Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxSize().padding(24.dp)) {
            Text(problem ?: "Opening FlexWeek…", style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun FlexWeekRoot(
    core: com.flexweek.app.core.FlexWeekCore,
    initiallyPaired: Boolean,
    tweaks: ScreenshotTweaks,
    activity: ComponentActivity,
) {
    val v2 = BuildConfig.V2_ENABLED
    val demo = core is com.flexweek.app.core.FakeFlexWeekCore
    var paired by remember { mutableStateOf(initiallyPaired || (demo && tweaks.prePaired)) }
    var pairingRequested by remember { mutableStateOf(false) }
    // Survives rotation so a second pair screen cannot start while the first pairing is still running.
    var pairEpoch by rememberSaveable { mutableIntStateOf(0) }
    var pendingNotifPrompt by remember { mutableStateOf(false) }
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
        pairingRequested || tweaks.startScreen == ScreenshotTweaks.StartScreen.Pair ||
            (!paired && !demo) ||
            (!paired && tweaks.startScreen != ScreenshotTweaks.StartScreen.Today &&
                tweaks.startScreen != ScreenshotTweaks.StartScreen.Reminders &&
                tweaks.startScreen != ScreenshotTweaks.StartScreen.Week)
    if (showPair) {
        val vm = viewModel(key = "pair-$pairEpoch") { PairViewModel(core) }
        val pairState by vm.uiState
        LaunchedEffect(pairState.paired) {
            if (pairState.paired) {
                paired = true
                pairingRequested = false
                pendingNotifPrompt = true
            }
        }
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
    val remindersVm = viewModel { RemindersViewModel(core, SharedPreferenceReminderPrefs(activity)) }
    val updateVm = viewModel { UpdateViewModel(BuildConfig.VERSION_NAME, HttpUpdateSource(), PackageUpdateInstaller(activity), SharedPreferenceUpdatePrefs(activity), activity.filesDir.resolve("updates")) }
    val updateState by updateVm.state
    DisposableEffect(updateVm) {
        com.flexweek.app.update.UpdateInstallReceiver.onResult = updateVm::onInstallResult
        onDispose { com.flexweek.app.update.UpdateInstallReceiver.onResult = null }
    }
    var showUpdateSteps by remember { mutableStateOf(false) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, updateVm) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_CREATE || event == Lifecycle.Event.ON_RESUME) {
                updateVm.onResumed()
                updateVm.onResumeCheck()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(core, lifecycleOwner) {
        if (!demo) {
            syncWhileForeground(core, lifecycleOwner.lifecycle) {
                todayVm.tick(java.time.LocalTime.now().let { it.hour * 60 + it.minute })
                remindersVm.reload()
            }
        }
    }
    LaunchedEffect(pendingNotifPrompt) {
        if (pendingNotifPrompt) {
            remindersVm.showPostPairBanner()
            pendingNotifPrompt = false
        }
    }
    LaunchedEffect(tweaks.prePaired) {
        if (tweaks.prePaired) {
            remindersVm.showPostPairBanner()
        }
    }
    val notifLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            remindersVm.onNotificationPermissionResult(granted)
        }
    val weekVm = if (v2) viewModel { WeekViewModel(core) } else null
    val syncLine = remindersVm.state.problem?.let { SyncLine("unreachable", it) } ?: todayVm.uiState.syncLine
    val closeSheet: () -> Unit = {
        sheet = ActiveSheet.None
        todayVm.refreshAgenda()
        weekVm?.refresh()
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
                            onToggleHomework = {
                                todayVm.toggleHomework(it)
                            },
                            onUndo = {
                                todayVm.undoLast()
                            },
                            onDismissSnack = todayVm::dismissSnackbar,
                            onFinishHomework = {
                                todayVm.toggleHomework(it)
                            },
                            onRunningLate = { if (v2) sheet = ActiveSheet.Late },
                            focusEnabled = false,
                            lateEnabled = v2,
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
                            onAllowNotifications = {
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                    notifLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                                } else {
                                    remindersVm.allowNotifications()
                                }
                            },
                            onDismissPermissionBanner = remindersVm::dismissPermissionBanner,
                            onLeadChange = {
                                remindersVm.setLeadMinutes(it)
                            },
                            onToggleExact = {
                                remindersVm.toggleExact {
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                        activity.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM))
                                    }
                                }
                            },
                            onSyncNow = {
                                remindersVm.syncNow()
                            },
                            onUnpair = {
                                remindersVm.unpair {
                                    pairEpoch += 1
                                    pairingRequested = true
                                }
                            },
                            updateState = updateState,
                            updateDaily = updateVm.checkDaily,
                            onCheckUpdates = updateVm::checkNow,
                            onDownloadUpdate = updateVm::downloadAndInstall,
                            onUpdateDaily = updateVm::setDailyCheck,
                            onUpdateLater = updateVm::later,
                            onUpdateSteps = { showUpdateSteps = !showUpdateSteps },
                            onUpdatePermission = {
                                activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, android.net.Uri.parse("package:${activity.packageName}")))
                            },
                            showUpdateSteps = showUpdateSteps,
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
                } ?: planVm.error?.let { err ->
                    SheetScrim({ sheet = ActiveSheet.None }) {
                        Surface(shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)) {
                            Column(Modifier.padding(16.dp)) {
                                Text(err, color = MaterialTheme.colorScheme.error)
                                TextButton(onClick = { sheet = ActiveSheet.None }) { Text("Close") }
                            }
                        }
                    }
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
