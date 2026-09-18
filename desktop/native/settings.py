"""Focus panel, preferences, restore points and account dialogs."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from backend.comfort import TIMER_PRESETS
from desktop.native.calendar import DAY_FULL
from desktop.native.focus import FOCUS_PHASE_LABEL, format_countdown, more_time_choices, remaining_ms
from desktop.native.look import (
    ACCENTS,
    LOOK_KNOBS,
    LOOK_PRESETS,
    PACKS,
    effective_look,
    look_overrides,
    preset_knobs,
    sanitize_look,
)
from desktop.native.reuse import format_duration


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
        self.task = QLabel()
        self.task.setObjectName("focusTask")
        layout.addWidget(self.task)
        self.phase = QLabel()
        self.phase.setObjectName("focusPhase")
        layout.addWidget(self.phase)
        self.time = QLabel()
        self.time.setObjectName("focusTime")
        layout.addWidget(self.time)
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
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.pack = QComboBox()
        self.pack.setObjectName("prefTheme")
        for name in PACKS:
            self.pack.addItem(name.replace("-", " ").title(), name)
        index = self.pack.findData(preferences.get("theme_pack") or "system")
        self.pack.setCurrentIndex(max(0, index))
        form.addRow("Look pack", self.pack)
        self.accent = QComboBox()
        for name in ACCENTS:
            self.accent.addItem(name.title(), name)
        index = self.accent.findData(preferences.get("accent") or "default")
        self.accent.setCurrentIndex(max(0, index))
        form.addRow("Accent", self.accent)
        self.preset = QComboBox()
        self.preset.setObjectName("lookPreset")
        for name in LOOK_PRESETS:
            self.preset.addItem(name.title(), name)
        index = self.preset.findData(self._look.get("preset") or "default")
        self.preset.setCurrentIndex(max(0, index))
        form.addRow("Device preset", self.preset)
        self.knobs = {}
        # Each box shows what is on screen now: the preset's value unless the student moved that knob.
        shown = effective_look(self._look)
        for knob, values in LOOK_KNOBS.items():
            box = QComboBox()
            box.setObjectName("look" + knob.title())
            for value in values:
                box.addItem(value.title(), value)
            box.setCurrentIndex(max(0, box.findData(shown[knob])))
            self.knobs[knob] = box
            form.addRow(knob.title(), box)
        # Connected after the boxes exist, and after the stored preset was selected above, so opening
        # Settings never resets a student's own knobs; only picking a preset does.
        self.preset.currentIndexChanged.connect(self._apply_look_preset)
        self.work = QSpinBox()
        self.work.setRange(15, 180)
        self.work.setSingleStep(15)
        self.work.setValue(int(preferences.get("timer_work_min") or 30))
        form.addRow("Focus minutes", self.work)
        self.break_min = QSpinBox()
        self.break_min.setRange(15, 60)
        self.break_min.setSingleStep(15)
        self.break_min.setValue(int(preferences.get("timer_break_min") or 15))
        form.addRow("Break minutes", self.break_min)
        self.long_break = QSpinBox()
        self.long_break.setRange(15, 120)
        self.long_break.setSingleStep(15)
        self.long_break.setValue(int(preferences.get("timer_long_break_min") or 30))
        form.addRow("Long break", self.long_break)
        self.preset_timer = QComboBox()
        self.preset_timer.setObjectName("timerPreset")
        for item in TIMER_PRESETS:
            self.preset_timer.addItem(item["label"], item["id"])
        self.preset_timer.currentIndexChanged.connect(self._apply_timer_preset)
        form.addRow("Timer preset", self.preset_timer)
        self.reminders = QCheckBox("Reminders")
        self.reminders.setObjectName("prefReminders")
        self.reminders.setChecked(bool(preferences.get("reminders_enabled")))
        form.addRow(self.reminders)
        self.lead = QSpinBox()
        self.lead.setRange(0, 120)
        lead = preferences.get("reminder_lead_min")
        self.lead.setValue(5 if lead is None else int(lead))
        form.addRow("Lead minutes", self.lead)
        self.tray = QCheckBox("Stay in the tray")
        self.tray.setChecked(preferences.get("tray_notifications", True) is not False)
        form.addRow(self.tray)
        self.spotify = QLineEdit(preferences.get("default_spotify_url") or "")
        self.spotify.setObjectName("prefSpotify")
        form.addRow("Default Spotify link", self.spotify)
        layout.addLayout(form)
        keys = ("desktop_background", "spotify", "duplicate")
        limits = QLabel(" ".join(reminder_limits.get(key, "") for key in keys))
        limits.setWordWrap(True)
        limits.setObjectName("reminderLimits")
        layout.addWidget(limits)
        layout.addWidget(QLabel("Alarms"))
        self.alarm_list = QListWidget()
        self.alarm_list.setObjectName("alarmList")
        layout.addWidget(self.alarm_list)
        alarm_row = QHBoxLayout()
        self.alarm_name = QLineEdit()
        self.alarm_name.setPlaceholderText("Alarm name")
        self.alarm_time = QTimeEdit()
        self.alarm_time.setDisplayFormat("HH:mm")
        add_alarm = QPushButton("Add alarm")
        add_alarm.setObjectName("addAlarm")
        add_alarm.clicked.connect(self._add_alarm)
        remove_alarm = QPushButton("Remove alarm")
        remove_alarm.clicked.connect(self._remove_alarm)
        for widget in (self.alarm_name, self.alarm_time, add_alarm, remove_alarm):
            alarm_row.addWidget(widget)
        layout.addLayout(alarm_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._render_alarms()

    def _apply_timer_preset(self) -> None:
        chosen = self.preset_timer.currentData()
        preset = next((item for item in TIMER_PRESETS if item["id"] == chosen), None)
        if preset is None:
            return
        self.work.setValue(preset["timer_work_min"])
        self.break_min.setValue(preset["timer_break_min"])
        self.long_break.setValue(preset["timer_long_break_min"])

    def _render_alarms(self) -> None:
        self.alarm_list.clear()
        for alarm in self._alarms:
            days = ",".join(DAY_FULL[day][:3] for day in alarm.get("days") or [])
            self.alarm_list.addItem(f"{alarm.get('name')} {alarm.get('time')} {days}")

    def _add_alarm(self) -> None:
        if len(self._alarms) >= 20:
            return
        name = self.alarm_name.text().strip() or "Alarm"
        time = self.alarm_time.time().toString("HH:mm")
        self._alarms.append(
            {
                "id": str(uuid4()),
                "name": name,
                "time": time,
                "days": [0, 1, 2, 3, 4],
                "enabled": True,
                "sound": "chime",
            }
        )
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
            "theme_pack": self.pack.currentData(),
            "accent": self.accent.currentData(),
            "timer_work_min": self.work.value(),
            "timer_break_min": self.break_min.value(),
            "timer_long_break_min": self.long_break.value(),
            "reminders_enabled": self.reminders.isChecked(),
            "reminder_lead_min": self.lead.value(),
            "tray_notifications": self.tray.isChecked(),
            "default_spotify_url": spotify,
            "alarms": deepcopy(self._alarms),
        }

    def _apply_look_preset(self) -> None:
        """One tap is the whole look: every knob moves to what the chosen preset sets."""
        bundle = preset_knobs(self.preset.currentData())
        for knob, box in self.knobs.items():
            box.setCurrentIndex(max(0, box.findData(bundle[knob])))

    def look_choice(self) -> dict:
        # Only knobs moved away from the preset are overrides. Recording all seven made every box beat
        # the preset, so choosing Terminal changed its colours and none of its knobs.
        preset = self.preset.currentData()
        shown = {knob: box.currentData() for knob, box in self.knobs.items()}
        return sanitize_look({"preset": preset, "knobs": look_overrides(preset, shown)})


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

    def _selected(self) -> str | None:
        item = self.list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _create(self) -> None:
        self.action = "create"
        self.create_label = self.label.text().strip()
        self.accept()

    def _preview(self) -> None:
        self.selected_id = self._selected()
        self.action = "preview"
        self.accept()

    def _restore(self) -> None:
        self.selected_id = self._selected()
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
        row = QHBoxLayout()
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
        layout = QVBoxLayout(self)
        title = QLabel(alarm.get("name") or "Alarm")
        title.setObjectName("alarmTitle")
        layout.addWidget(title)
        detail = QLabel((alarm.get("time") or "") + " · Alarm is ringing")
        detail.setObjectName("alarmDetail")
        layout.addWidget(detail)
        if spotify:
            link = QPushButton("Open Spotify")
            link.setObjectName("alarmOpenSpotify")
            link.clicked.connect(self._spotify)
            layout.addWidget(link)
        snooze = QPushButton("Snooze")
        snooze.setObjectName("alarmSnooze")
        snooze.clicked.connect(self._snooze)
        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("alarmDismiss")
        dismiss.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addWidget(snooze)
        row.addWidget(dismiss)
        layout.addLayout(row)

    def _snooze(self) -> None:
        self.snoozed = True
        self.accept()

    def _spotify(self) -> None:
        self.open_spotify = True


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
