"""Focus panel, preferences, restore points and account dialogs."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from backend.comfort import TIMER_PRESETS, snap_minutes
from backend.models import valid_spotify_url
from backend.slots import SLOT_MIN
from desktop.native import autostart
from desktop.native.calendar import DAY_FULL
from desktop.native.focus import FOCUS_PHASE_LABEL, format_countdown, more_time_choices, remaining_ms
from desktop.native.look import (
    ACCENTS,
    LOOK_KNOBS,
    effective_look,
    known_pack,
    look_menu_items,
    look_menu_token,
    look_menu_value,
    look_overrides,
    parse_look_menu_token,
    sanitize_look,
)
from desktop.native.remind import ALARM_SNOOZE_MIN
from desktop.native.reuse import format_duration
from desktop.native.sound import Bell
from desktop.native.tones import FALLBACK, RECIPES, SOUNDS
from desktop.native.widgets import FlowLayout

ALARM_MIN_WIDTH = 380
ALARM_PAD = 20
ALARM_GAP = 12
ALARM_BUTTON_HEIGHT = 44
PREFS_MAX_BODY = 560
PREFS_MIN_WIDTH = 560
ACCOUNT_MAX_WIDTH = 520
ACCOUNT_MIN_WIDTH = 560


def _heading(words: str) -> QLabel:
    """A section label inside a form, so eighteen settings stop reading as one list."""
    made = QLabel(words.upper())
    made.setObjectName("prefsHeading")
    return made


class FocusPanel(QWidget):
    start_requested = Signal(str, object)
    quick_requested = Signal()
    pause_requested = Signal()
    skip_requested = Signal()
    reset_requested = Signal()
    finished_requested = Signal()
    break_requested = Signal()
    more_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focusPanel")
        layout = QVBoxLayout(self)
        self.now_next = QLabel()
        self.now_next.setObjectName("nowNext")
        self.now_next.setWordWrap(True)
        layout.addWidget(self.now_next)
        # One status line, not four stacked labels. Over a design of its own the timer used to
        # arrive as loose text: the homework, then "Focus session", then "30:00", each on its own row.
        status = QHBoxLayout()
        self.task = QLabel()
        self.task.setObjectName("focusTask")
        self.phase = QLabel()
        self.phase.setObjectName("focusPhase")
        self.time = QLabel()
        self.time.setObjectName("focusTime")
        for widget in (self.task, self.phase, self.time):
            status.addWidget(widget)
        status.addStretch(1)
        layout.addLayout(status)
        controls = QHBoxLayout()
        self.pause = QPushButton("Pause")
        self.pause.setObjectName("focusPause")
        self.pause.clicked.connect(self.pause_requested.emit)
        self.skip = QPushButton("Skip")
        self.skip.setObjectName("focusSkip")
        self.skip.clicked.connect(self.skip_requested.emit)
        self.reset = QPushButton("Reset")
        self.reset.setObjectName("focusReset")
        self.reset.clicked.connect(self.reset_requested.emit)
        self.quick = QPushButton("Quick focus")
        self.quick.setObjectName("focusQuick")
        self.quick.clicked.connect(self.quick_requested.emit)
        for button in (self.pause, self.skip, self.reset, self.quick):
            controls.addWidget(button)
        # Without this the four buttons split the window between them, 439px each over a layout
        # of its own. They keep their natural width and the row fills with space instead.
        controls.addStretch(1)
        layout.addLayout(controls)
        choices = QHBoxLayout()
        self.finished = QPushButton("Finished")
        self.finished.setObjectName("focusFinished")
        self.finished.clicked.connect(self.finished_requested.emit)
        self.take_break = QPushButton("Take a break")
        self.take_break.setObjectName("focusBreak")
        self.take_break.clicked.connect(self.break_requested.emit)
        self.more_min = QComboBox()
        self.more_min.setObjectName("focusMoreMin")
        self.more = QPushButton("Need more time")
        self.more.setObjectName("focusMoreAdd")
        self.more.clicked.connect(self._emit_more)
        for widget in (self.finished, self.take_break, self.more_min, self.more):
            choices.addWidget(widget)
        choices.addStretch(1)
        layout.addLayout(choices)
        self.tasks = QListWidget()
        self.tasks.setObjectName("focusTasks")
        self.tasks.itemActivated.connect(self._start_item)
        layout.addWidget(self.tasks)
        self._ended_widgets = (self.finished, self.take_break, self.more_min, self.more)
        self._run_widgets = (self.pause, self.skip, self.reset)
        # Nothing to show until a timer runs or the plan places work, and blank rows cost the calendar height.
        for widget in (self.task, self.phase, self.time, self.tasks):
            widget.setVisible(False)

    def _emit_more(self) -> None:
        self.more_requested.emit(int(self.more_min.currentData() or 0))

    def _start_item(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        self.start_requested.emit(payload.get("id") or "", payload.get("day"))

    def set_state(self, session) -> None:
        self.now_next.setText(session.now_next_text())
        state = session.focus
        running = state is not None and state.get("phase") != "ended"
        ended = state is not None and state.get("phase") == "ended"
        self.task.setText("" if state is None else state.get("title") or "")
        self.phase.setText("" if state is None else FOCUS_PHASE_LABEL.get(state.get("phase"), ""))
        if state is None:
            self.time.setText("")
        else:
            self.time.setText(format_countdown(remaining_ms(state, session.now_ms())))
        self.pause.setText("Pause" if state and state.get("running") else "Resume")
        for widget in self._run_widgets:
            widget.setVisible(running)
        assignment = None if state is None else session.assignments.get(state.get("assignmentId"))
        choices = more_time_choices(int((assignment or {}).get("estimate_min") or 0)) if ended else []
        self.more_min.clear()
        for minutes in choices:
            self.more_min.addItem(format_duration(minutes), minutes)
        for widget in self._ended_widgets:
            widget.setVisible(ended)
        self.more.setEnabled(bool(choices))
        tasks = [
            (item.get("id"), item.get("start"), item.get("focus_sessions"), item.get("title"))
            for item in session.focus_tasks()
        ]
        if tasks != getattr(self, "_shown_tasks", None):
            self._shown_tasks = tasks
            self.tasks.clear()
            for item in session.focus_tasks():
                row = QListWidgetItem(
                    f"{item['title']}  {item.get('start') or ''} · {item.get('focus_sessions') or 0} sessions"
                )
                row.setData(Qt.ItemDataRole.UserRole, item)
                self.tasks.addItem(row)
        for label in (self.task, self.phase, self.time):
            label.setVisible(bool(label.text()))
        # An empty list still asks for about 190 pixels, and a long one would bury the calendar, so it
        # is hidden when empty and never taller than four rows; the rest scrolls.
        shown = min(self.tasks.count(), 4)
        self.tasks.setVisible(shown > 0)
        if shown:
            rows = shown * self.tasks.sizeHintForRow(0)
            self.tasks.setMaximumHeight(rows + 2 * self.tasks.frameWidth() + 8)


class PrefsDialog(QDialog):
    def __init__(self, parent: QWidget | None, preferences: dict, look: dict, reminder_limits: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._preferences = deepcopy(preferences)
        self._look = sanitize_look(look)
        self._alarms = [deepcopy(item) for item in preferences.get("alarms") or []]
        self._bell = Bell(self)
        layout = QVBoxLayout(self)
        # Eighteen rows in one undivided column stood 1056 pixels tall, taller than the laptop the
        # app is built for. Everything but the buttons scrolls, and the rows sit under headings.
        # The width has to be set too: a scroll area does not claim its content's width, so capping
        # only the height left the dialog 400 pixels wide with the fields cut off and scrolling
        # sideways.
        self.setMinimumWidth(PREFS_MIN_WIDTH)
        self._pack = known_pack(preferences.get("theme_pack"))
        self.look = QComboBox()
        self.look.setObjectName("prefTheme")
        for name, label, kind in look_menu_items():
            self.look.addItem(label, look_menu_token(kind, name))
        index = self.look.findData(look_menu_value(self._pack, self._look))
        self.look.setCurrentIndex(max(0, index))
        self.accent = QComboBox()
        for name in ACCENTS:
            self.accent.addItem(name.title(), name)
        index = self.accent.findData(preferences.get("accent") or "default")
        self.accent.setCurrentIndex(max(0, index))
        self.accent_chips = QCheckBox("Use the accent on category chips")
        self.accent_chips.setObjectName("prefAccentChips")
        self.accent_chips.setChecked(bool(preferences.get("accent_chips")))
        self.knobs = {}
        shown = effective_look(self._look)
        self.fine_host = QWidget()
        self.fine_host.setObjectName("prefFineHost")
        fine_form = QFormLayout(self.fine_host)
        fine_form.setContentsMargins(0, 0, 0, 0)
        for knob, values in LOOK_KNOBS.items():
            box = QComboBox()
            box.setObjectName("look" + knob.title())
            for value in values:
                box.addItem(value.title(), value)
            box.setCurrentIndex(max(0, box.findData(shown[knob])))
            self.knobs[knob] = box
            fine_form.addRow(knob.title(), box)
        self.fine_tune = QCheckBox("Fine-tune this look")
        self.fine_tune.setObjectName("prefFineTune")
        self.fine_tune.setChecked(bool(self._look.get("knobs")))
        self.fine_host.setVisible(self.fine_tune.isChecked())
        self.fine_tune.toggled.connect(self.fine_host.setVisible)
        self.look.currentIndexChanged.connect(self._apply_look_menu)
        self.work = QSpinBox()
        self.work.setRange(1, 180)
        self.work.setSingleStep(1)
        self.work.setValue(int(preferences.get("timer_work_min") or 30))
        self.break_min = QSpinBox()
        self.break_min.setRange(1, 60)
        self.break_min.setSingleStep(1)
        self.break_min.setValue(int(preferences.get("timer_break_min") or 15))
        self.long_break = QSpinBox()
        self.long_break.setRange(1, 120)
        self.long_break.setSingleStep(1)
        self.long_break.setValue(int(preferences.get("timer_long_break_min") or 30))
        self.preset_timer = QComboBox()
        self.preset_timer.setObjectName("timerPreset")
        self.preset_timer.addItem("Custom", None)
        for item in TIMER_PRESETS:
            self.preset_timer.addItem(item["label"], item["id"])
        chosen = None
        for item in TIMER_PRESETS:
            if (
                item["timer_work_min"] == self.work.value()
                and item["timer_break_min"] == self.break_min.value()
                and item["timer_long_break_min"] == self.long_break.value()
            ):
                chosen = item["id"]
                break
        self.preset_timer.setCurrentIndex(max(0, self.preset_timer.findData(chosen)))
        self.preset_timer.activated.connect(self._apply_timer_preset)
        self.long_every = QSpinBox()
        self.long_every.setObjectName("prefLongEvery")
        self.long_every.setRange(2, 12)
        self.long_every.setValue(int(preferences.get("timer_long_break_every") or 4))
        self.auto_split = QCheckBox("Split long homework into focus sessions")
        self.auto_split.setObjectName("prefAutoSplit")
        self.auto_split.setChecked(bool(preferences.get("auto_split_pomodoro")))
        self.reminders = QCheckBox("Reminders")
        self.reminders.setObjectName("prefReminders")
        self.reminders.setChecked(bool(preferences.get("reminders_enabled")))
        self.lead = QSpinBox()
        self.lead.setRange(0, 120)
        lead = preferences.get("reminder_lead_min")
        self.lead.setValue(5 if lead is None else int(lead))
        self.reminder_sound = QCheckBox("Play a sound")
        self.reminder_sound.setObjectName("prefReminderSound")
        self.reminder_sound.setChecked(preferences.get("reminder_sound", True) is not False)
        self.dnd_override = QCheckBox("Keep alerts visible until handled")
        self.dnd_override.setObjectName("prefDndOverride")
        self.dnd_override.setChecked(bool(preferences.get("reminder_dnd_override")))
        self.volume = QSpinBox()
        self.volume.setObjectName("prefAlertVolume")
        self.volume.setRange(0, 100)
        self.volume.setValue(int(preferences.get("alert_volume", 80)))
        self.preview_tone = QComboBox()
        self.preview_tone.setObjectName("prefPreviewTone")
        for name in RECIPES:
            self.preview_tone.addItem(name.title(), name)
        self.preview = QPushButton("Test")
        self.preview.setObjectName("prefPreviewAlert")
        self.preview.clicked.connect(self._preview_alert)
        self.end_chime = QCheckBox("Chime when a session ends")
        self.end_chime.setObjectName("prefEndChime")
        self.end_chime.setChecked(bool(preferences.get("end_chime")))
        self.tray = QCheckBox("Stay in the tray")
        self.tray.setChecked(preferences.get("tray_notifications", True) is not False)
        self.start_at_login = QCheckBox("Start FlexWeek when I log in")
        self.start_at_login.setObjectName("prefStartAtLogin")
        self.start_at_login.setChecked(autostart.enabled_on_disk())
        self.preferred_view = QComboBox()
        self.preferred_view.setObjectName("prefPreferredView")
        self.preferred_view.addItem("Whatever I had open", None)
        self.preferred_view.addItem("Week", "week")
        self.preferred_view.addItem("Day", "day")
        self.preferred_view.setCurrentIndex(
            max(0, self.preferred_view.findData(preferences.get("preferred_view")))
        )
        self.spotify = QLineEdit(preferences.get("default_spotify_url") or "")
        self.spotify.setObjectName("prefSpotify")
        appearance = QWidget()
        appear = QFormLayout(appearance)
        appear.addRow(_heading("Look"))
        appear.addRow("Look", self.look)
        appear.addRow("Accent", self.accent)
        appear.addRow(self.accent_chips)
        appear.addRow(
            QLabel("Layout stays in the Layout dialog. It is how the week is drawn, not these colours.")
        )
        appear.addRow(self.fine_tune)
        appear.addRow(self.fine_host)
        focus = QWidget()
        focus_form = QFormLayout(focus)
        focus_form.addRow(_heading("Focus timer"))
        focus_form.addRow("Focus minutes", self.work)
        focus_form.addRow("Break minutes", self.break_min)
        focus_form.addRow("Long break", self.long_break)
        focus_form.addRow("Timer preset", self.preset_timer)
        focus_form.addRow("Long break after", self.long_every)
        focus_form.addRow(self.auto_split)
        alerts = QWidget()
        alerts_form = QFormLayout(alerts)
        alerts_form.addRow(_heading("Reminders"))
        alerts_form.addRow(self.reminders)
        alerts_form.addRow("Lead minutes", self.lead)
        alerts_form.addRow(self.reminder_sound)
        alerts_form.addRow(self.dnd_override)
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume)
        volume_row.addWidget(self.preview_tone)
        volume_row.addWidget(self.preview)
        alerts_form.addRow("Alert volume", volume_row)
        alerts_form.addRow(self.end_chime)
        alerts_form.addRow(self.tray)
        keys = ("desktop_background", "spotify", "duplicate")
        limits = QLabel(" ".join(reminder_limits.get(key, "") for key in keys))
        limits.setWordWrap(True)
        limits.setObjectName("reminderLimits")
        alerts_form.addRow(limits)
        alerts_form.addRow(_heading("Alarms"))
        self.alarm_list = QListWidget()
        self.alarm_list.setObjectName("alarmList")
        self.alarm_list.setMaximumHeight(110)
        alerts_form.addRow(self.alarm_list)
        alarm_row = QHBoxLayout()
        self.alarm_name = QLineEdit()
        self.alarm_name.setPlaceholderText("Alarm name")
        self.alarm_time = QTimeEdit()
        self.alarm_time.setDisplayFormat("HH:mm")
        self.alarm_sound = QComboBox()
        self.alarm_sound.setObjectName("alarmSound")
        self.alarm_name.setMinimumWidth(120)
        self.alarm_sound.setMinimumContentsLength(8)
        for name in SOUNDS:
            self.alarm_sound.addItem("Spotify link" if name == "spotify" else name.title(), name)
        for widget in (self.alarm_name, self.alarm_time, self.alarm_sound):
            alarm_row.addWidget(widget)
        alerts_form.addRow(alarm_row)
        self.alarm_spotify = QLineEdit()
        self.alarm_spotify.setObjectName("alarmSpotify")
        self.alarm_spotify.setPlaceholderText("Spotify link for this alarm (optional)")
        alerts_form.addRow(self.alarm_spotify)
        day_row = QHBoxLayout()
        self.alarm_days: list[QCheckBox] = []
        for index, name in enumerate(DAY_FULL):
            day_box = QCheckBox(name[:3])
            day_box.setObjectName(f"alarmDay{index}")
            day_box.setChecked(index < 5)
            self.alarm_days.append(day_box)
            day_row.addWidget(day_box)
        add_alarm = QPushButton("Add alarm")
        add_alarm.setObjectName("addAlarm")
        add_alarm.clicked.connect(self._add_alarm)
        remove_alarm = QPushButton("Remove alarm")
        remove_alarm.setObjectName("removeAlarm")
        remove_alarm.clicked.connect(self._remove_alarm)
        day_row.addStretch(1)
        alerts_form.addRow(day_row)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(add_alarm)
        button_row.addWidget(remove_alarm)
        alerts_form.addRow(button_row)
        computer = QWidget()
        computer_form = QFormLayout(computer)
        computer_form.addRow(_heading("This computer"))
        computer_form.addRow(self.start_at_login)
        computer_form.addRow("Open on", self.preferred_view)
        computer_form.addRow("Default Spotify link", self.spotify)
        self.nav = QListWidget()
        self.nav.setObjectName("prefsNav")
        self.nav.setFixedWidth(160)
        for name in ("Appearance", "Focus", "Alerts", "This computer"):
            self.nav.addItem(name)
        self.stack = QStackedWidget()
        self.stack.setObjectName("prefsStack")
        for page in (appearance, focus, alerts, computer):
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidget(page)
            self.stack.addWidget(area)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        body = QWidget()
        body.setObjectName("prefsBody")
        split = QHBoxLayout(body)
        split.setContentsMargins(0, 0, 0, 0)
        split.addWidget(self.nav)
        split.addWidget(self.stack, 1)
        area = QScrollArea()
        area.setObjectName("prefsScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(body)
        area.setMaximumHeight(PREFS_MAX_BODY)
        layout.addWidget(area)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._render_alarms()

    def accept(self) -> None:
        """The server refuses auto-splitting with off-grid lengths, so the refusal is met here where
        the numbers are, rather than as a failed save after the dialog has closed."""
        off_grid = [
            box.value() for box in (self.work, self.break_min, self.long_break) if box.value() % SLOT_MIN
        ]
        if self.auto_split.isChecked() and off_grid:
            answer = QMessageBox.question(
                self,
                "Focus splitting",
                f"Splitting into focus sessions needs {SLOT_MIN}-minute lengths. Round them and save?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            for box, ceiling in ((self.work, 180), (self.break_min, 60), (self.long_break, 120)):
                box.setValue(snap_minutes(box.value(), 1, ceiling))
        super().accept()

    def _apply_timer_preset(self, _index: int = 0) -> None:
        chosen = self.preset_timer.currentData()
        if chosen is None:
            return
        preset = next((item for item in TIMER_PRESETS if item["id"] == chosen), None)
        if preset is None:
            return
        self.work.setValue(preset["timer_work_min"])
        self.break_min.setValue(preset["timer_break_min"])
        self.long_break.setValue(preset["timer_long_break_min"])

    def _preview_alert(self) -> None:
        """Sound the alert at the volume currently in the box, not the saved one, so the slider can be
        set by ear."""
        if not self.reminder_sound.isChecked():
            self.preview.setText("Sound is off")
            return
        tone = str(self.preview_tone.currentData() or FALLBACK)
        self.preview.setText("Test" if self._bell.once(tone, self.volume.value()) else "No sound card")

    def _render_alarms(self) -> None:
        self.alarm_list.clear()
        for alarm in self._alarms:
            days = ",".join(DAY_FULL[day][:3] for day in alarm.get("days") or [])
            sound = str(alarm.get("sound") or FALLBACK)
            label = "Spotify" if sound == "spotify" else sound.title()
            self.alarm_list.addItem(f"{alarm.get('name')} {alarm.get('time')} {days} · {label}")

    def _add_alarm(self) -> None:
        if len(self._alarms) >= 20:
            return
        days = [index for index, box in enumerate(self.alarm_days) if box.isChecked()]
        if not days:
            # An alarm on no days never rings, so say so rather than storing one that cannot fire.
            self.alarm_name.setPlaceholderText("Pick at least one day")
            return
        link = self.alarm_spotify.text().strip()
        if link:
            # valid_spotify_url raises on a bad link rather than returning None.
            try:
                link = valid_spotify_url(link) or ""
            except ValueError:
                self.alarm_spotify.setPlaceholderText("Use an https://open.spotify.com share link.")
                self.alarm_spotify.clear()
                return
        self._alarms.append(
            {
                "id": str(uuid4()),
                "name": self.alarm_name.text().strip() or "Alarm",
                "time": self.alarm_time.time().toString("HH:mm"),
                "days": days,
                "enabled": True,
                "sound": str(self.alarm_sound.currentData() or FALLBACK),
                "spotify_url": link or None,
            }
        )
        self.alarm_name.clear()
        self.alarm_spotify.clear()
        self._render_alarms()

    def _remove_alarm(self) -> None:
        row = self.alarm_list.currentRow()
        if row < 0 or row >= len(self._alarms):
            return
        self._alarms.pop(row)
        self._render_alarms()

    def updates(self) -> dict:
        spotify = self.spotify.text().strip() or None
        return {
            "theme_pack": self._pack,
            "accent": self.accent.currentData(),
            "timer_work_min": self.work.value(),
            "timer_break_min": self.break_min.value(),
            "timer_long_break_min": self.long_break.value(),
            "reminders_enabled": self.reminders.isChecked(),
            "reminder_lead_min": self.lead.value(),
            "tray_notifications": self.tray.isChecked(),
            "default_spotify_url": spotify,
            "alarms": deepcopy(self._alarms),
            # These eight could only be set from the web client, which stopped being the way most
            # students meet FlexWeek when the browser shell was retired.
            "timer_long_break_every": self.long_every.value(),
            "auto_split_pomodoro": self.auto_split.isChecked(),
            "reminder_sound": self.reminder_sound.isChecked(),
            "reminder_dnd_override": self.dnd_override.isChecked(),
            "alert_volume": self.volume.value(),
            "end_chime": self.end_chime.isChecked(),
            "accent_chips": self.accent_chips.isChecked(),
            "start_at_login": self.start_at_login.isChecked(),
            "preferred_view": self.preferred_view.currentData(),
        }

    def _apply_look_menu(self) -> None:
        """Keep knobs moved by hand; the chosen look fills in only the rest."""
        previous = self._look.get("preset") or "default"
        shown = {knob: box.currentData() for knob, box in self.knobs.items()}
        kept = look_overrides(previous, shown)
        parsed = parse_look_menu_token(self.look.currentData())
        if parsed is None:
            return
        kind, name = parsed
        if kind == "pack":
            self._pack = name
            preset = "default"
        else:
            preset = name
        self._look = sanitize_look({"preset": preset, "knobs": kept})
        bundle = effective_look(self._look)
        for knob, box in self.knobs.items():
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(bundle[knob])))
            box.blockSignals(False)

    def look_choice(self) -> dict:
        parsed = parse_look_menu_token(self.look.currentData())
        preset = parsed[1] if parsed and parsed[0] == "preset" else "default"
        shown = {knob: box.currentData() for knob, box in self.knobs.items()}
        return sanitize_look({"preset": preset, "knobs": look_overrides(preset, shown)})


class SetupCard(QWidget):
    """School hours, one sport, then the first homework. Each step can be skipped."""

    finished = Signal(dict)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("setupCard")
        self._step = 0
        self._payload: dict = {}
        layout = QVBoxLayout(self)
        self.kicker = QLabel()
        self.kicker.setObjectName("setupKicker")
        layout.addWidget(self.kicker)
        self.heading = QLabel()
        self.heading.setObjectName("setupHeading")
        layout.addWidget(self.heading)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName("setupNote")
        layout.addWidget(self.note)
        self.school_start = QLineEdit("08:00")
        self.school_start.setObjectName("setupSchoolStart")
        self.school_end = QLineEdit("14:30")
        self.school_end.setObjectName("setupSchoolEnd")
        school = QHBoxLayout()
        school.addWidget(QLabel("Starts"))
        school.addWidget(self.school_start)
        school.addWidget(QLabel("Ends"))
        school.addWidget(self.school_end)
        self.school_row = QWidget()
        self.school_row.setLayout(school)
        layout.addWidget(self.school_row)
        self.sport_title = QLineEdit("Soccer")
        self.sport_title.setObjectName("setupSportTitle")
        self.sport_start = QLineEdit("15:30")
        self.sport_start.setObjectName("setupSportStart")
        self.sport_end = QLineEdit("17:00")
        self.sport_end.setObjectName("setupSportEnd")
        sport = QFormLayout()
        sport.addRow("Name", self.sport_title)
        sport.addRow("Starts", self.sport_start)
        sport.addRow("Ends", self.sport_end)
        self.sport_row = QWidget()
        self.sport_row.setLayout(sport)
        layout.addWidget(self.sport_row)
        self.homework_title = QLineEdit()
        self.homework_title.setObjectName("setupHomeworkTitle")
        self.homework_title.setPlaceholderText("History essay")
        self.homework_minutes = QSpinBox()
        self.homework_minutes.setObjectName("setupHomeworkMinutes")
        self.homework_minutes.setRange(15, 600)
        self.homework_minutes.setSingleStep(15)
        self.homework_minutes.setValue(60)
        self.homework_due = QLineEdit()
        self.homework_due.setObjectName("setupHomeworkDue")
        self.homework_due.setPlaceholderText("2026-09-18T23:59")
        work = QFormLayout()
        work.addRow("Name", self.homework_title)
        work.addRow("Minutes", self.homework_minutes)
        work.addRow("Due", self.homework_due)
        self.work_row = QWidget()
        self.work_row.setLayout(work)
        layout.addWidget(self.work_row)
        actions = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("setupSkip")
        skip.setFlat(True)
        skip.clicked.connect(self._skip)
        nxt = QPushButton("Next")
        nxt.setObjectName("setupNext")
        nxt.clicked.connect(self._next)
        actions.addWidget(skip)
        actions.addStretch(1)
        actions.addWidget(nxt)
        layout.addLayout(actions)
        self._show_step()

    def _show_step(self) -> None:
        pages = (
            ("FIRST WEEK · 1 OF 3", "When is school?", "Locked time the planner will not move."),
            ("FIRST WEEK · 2 OF 3", "One sport or club?", "Skip if you do not have one."),
            ("FIRST WEEK · 3 OF 3", "What homework is due first?", "You can add the rest later."),
        )
        kicker, heading, note = pages[self._step]
        self.kicker.setText(kicker)
        self.heading.setText(heading)
        self.note.setText(note)
        self.school_row.setVisible(self._step == 0)
        self.sport_row.setVisible(self._step == 1)
        self.work_row.setVisible(self._step == 2)

    def _skip(self) -> None:
        self._advance(keep=False)

    def _next(self) -> None:
        self._advance(keep=True)

    def _advance(self, keep: bool) -> None:
        if keep and self._step == 0:
            self._payload["school"] = (self.school_start.text().strip(), self.school_end.text().strip())
        if keep and self._step == 1:
            self._payload["sport"] = (
                self.sport_title.text().strip() or "Soccer",
                self.sport_start.text().strip(),
                self.sport_end.text().strip(),
            )
        if keep and self._step == 2:
            self._payload["homework"] = (
                self.homework_title.text().strip() or "Homework",
                self.homework_minutes.value(),
                self.homework_due.text().strip(),
            )
        if self._step >= 2:
            self.finished.emit(self._payload)
            return
        self._step += 1
        self._show_step()


class RestoreDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        points: list[dict],
        preview: dict | None,
        storage: dict | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Restore points")
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        location = QLabel((storage or {}).get("label") or "Backup location unavailable")
        location.setObjectName("storageLocation")
        layout.addWidget(location)
        self.label = QLineEdit()
        self.label.setObjectName("restoreLabel")
        self.label.setPlaceholderText("Restore point name")
        layout.addWidget(self.label)
        create = QPushButton("Save restore point")
        create.setObjectName("restoreCreate")
        create.clicked.connect(self._create)
        layout.addWidget(create)
        self.list = QListWidget()
        self.list.setObjectName("restoreList")
        for point in points:
            item = QListWidgetItem(
                f"{point.get('label')} · {point.get('created_at') or ''} · "
                f"{point.get('weeks_count', point.get('week_count', 0))} weeks"
            )
            item.setData(Qt.ItemDataRole.UserRole, point.get("id"))
            self.list.addItem(item)
        layout.addWidget(self.list)
        self.summary = QLabel()
        self.summary.setObjectName("restorePreviewSummary")
        if preview:
            changes = preview.get("changes") or {}
            weeks = changes.get("weeks") or {}
            homework = changes.get("assignments") or {}
            added = len(weeks.get("added") or []) + len(homework.get("added") or [])
            changed = len(weeks.get("changed") or []) + len(homework.get("changed") or [])
            removed = len(weeks.get("removed") or []) + len(homework.get("removed") or [])
            self.summary.setText(f"{added} added, {changed} changed, {removed} removed.")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        preview_btn = QPushButton("Preview")
        preview_btn.setObjectName("restorePreview")
        preview_btn.clicked.connect(self._preview)
        restore_btn = QPushButton("Restore")
        restore_btn.setObjectName("restoreApply")
        restore_btn.clicked.connect(self._restore)
        actions.addWidget(preview_btn)
        actions.addWidget(restore_btn)
        layout.addLayout(actions)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.reject)
        layout.addWidget(close)
        self.action: str | None = None
        self.create_label = ""
        self.selected_id: str | None = None
        preview_id = None if not preview else preview.get("id")
        if preview_id:
            for index in range(self.list.count()):
                item = self.list.item(index)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == preview_id:
                    self.list.setCurrentRow(index)
                    break

    def _selected(self) -> str | None:
        item = self.list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _create(self) -> None:
        self.action = "create"
        self.create_label = self.label.text().strip()
        self.accept()

    def _preview(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.summary.setText("Choose a restore point.")
            return
        self.selected_id = chosen
        self.action = "preview"
        self.accept()

    def _restore(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.summary.setText("Choose a restore point.")
            return
        self.selected_id = chosen
        self.action = "restore"
        self.accept()


class AccountDialog(QDialog):
    def __init__(self, parent: QWidget | None, remaining: int | None, storage: dict | None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Account")
        self.action: str | None = None
        layout = QVBoxLayout(self)
        info = QLabel(
            "Signed in as "
            + ((storage or {}).get("username") or "")
            + ". "
            + ((storage or {}).get("label") or "")
        )
        info.setWordWrap(True)
        # Word wrap alone does not bound a label: it still claims the width of its longest
        # unwrapped line, which made this dialog 1338 pixels wide. The button row was not the
        # cause; with the label bounded a plain row measures 560 by 260.
        info.setMaximumWidth(ACCOUNT_MAX_WIDTH)
        info.setObjectName("accountLocation")
        layout.addWidget(info)
        remaining_text = "Recovery-code status unavailable."
        if remaining == 0:
            remaining_text = "No unused recovery codes remain. Replace them before logging out."
        elif remaining == 1:
            remaining_text = "1 unused recovery code remains."
        elif isinstance(remaining, int):
            remaining_text = f"{remaining} unused recovery codes remain."
        status = QLabel(remaining_text)
        status.setObjectName("recoveryStatus")
        layout.addWidget(status)
        form = QFormLayout()
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_password.setObjectName("currentPassword")
        form.addRow("Current password", self.current_password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setObjectName("newPassword")
        form.addRow("New password", self.new_password)
        layout.addLayout(form)
        self.setMinimumWidth(ACCOUNT_MIN_WIDTH)
        row = FlowLayout()
        change = QPushButton("Replace password")
        change.setObjectName("changePassword")
        change.clicked.connect(lambda: self._set("password"))
        codes = QPushButton("Replace recovery codes")
        codes.setObjectName("replaceCodes")
        codes.clicked.connect(lambda: self._set("codes"))
        delete = QPushButton("Delete account")
        delete.setObjectName("deleteAccount")
        delete.clicked.connect(lambda: self._set("delete"))
        export_btn = QPushButton("Export account")
        export_btn.setObjectName("exportAccount")
        export_btn.clicked.connect(lambda: self._set("export"))
        import_btn = QPushButton("Import account")
        import_btn.setObjectName("importAccount")
        import_btn.clicked.connect(lambda: self._set("import"))
        week_btn = QPushButton("Export week")
        week_btn.setObjectName("exportWeek")
        week_btn.clicked.connect(lambda: self._set("week"))
        day_btn = QPushButton("Export day")
        day_btn.setObjectName("exportDay")
        day_btn.clicked.connect(lambda: self._set("day"))
        import_week = QPushButton("Import week or day file")
        import_week.setObjectName("importFile")
        import_week.clicked.connect(lambda: self._set("import-week"))
        for button in (change, codes, delete, export_btn, import_btn, week_btn, day_btn, import_week):
            row.addWidget(button)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _set(self, action: str) -> None:
        self.action = action
        self.accept()


class AlarmRingDialog(QDialog):
    def __init__(self, parent: QWidget | None, alarm: dict, spotify: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Alarm")
        self.setModal(True)
        self.snoozed = False
        self.open_spotify = False
        self._url = spotify
        # It came up 209px wide, which is smaller than a notification and easy to miss. An alarm is
        # the one thing in the app that is meant to interrupt, so it is given room to be seen.
        self.setMinimumWidth(ALARM_MIN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ALARM_PAD, ALARM_PAD, ALARM_PAD, ALARM_PAD)
        layout.setSpacing(ALARM_GAP)
        title = QLabel(alarm.get("name") or "Alarm")
        title.setObjectName("alarmTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        detail = QLabel((alarm.get("time") or "") + " · Alarm is ringing")
        detail.setObjectName("alarmDetail")
        layout.addWidget(detail)
        layout.addSpacing(ALARM_GAP)
        if spotify:
            link = QPushButton("Open Spotify")
            link.setObjectName("alarmOpenSpotify")
            link.setMinimumHeight(ALARM_BUTTON_HEIGHT)
            link.clicked.connect(self._spotify)
            layout.addWidget(link)
        snooze = QPushButton(f"Snooze {ALARM_SNOOZE_MIN} minutes")
        snooze.setObjectName("alarmSnooze")
        snooze.clicked.connect(self._snooze)
        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("alarmDismiss")
        dismiss.setDefault(True)
        dismiss.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.setSpacing(ALARM_GAP)
        for button in (snooze, dismiss):
            button.setMinimumHeight(ALARM_BUTTON_HEIGHT)
            row.addWidget(button)
        layout.addLayout(row)

    def _snooze(self) -> None:
        self.snoozed = True
        self.accept()

    def _spotify(self) -> None:
        self.open_spotify = True
        if self._url:
            QDesktopServices.openUrl(QUrl(self._url))


class TransferPreviewDialog(QDialog):
    def __init__(self, parent: QWidget | None, preview: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Account transfer")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("From " + str(preview.get("source_username") or "another account")))
        changes = preview.get("changes") or {}
        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(str(changes))
        layout.addWidget(detail)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
