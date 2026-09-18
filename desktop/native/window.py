"""Qt widgets window for the native FlexWeek desktop client."""

from __future__ import annotations

import contextlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QGuiApplication, QIcon, QKeyEvent, QPalette
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from backend.slots import minutes_to_hhmm
from desktop.native.calendar import DAY_FULL, FLEX_CATEGORIES, agenda_for, sunday_due
from desktop.native.controller import NativeSession
from desktop.native.files import EXPORT_FORMAT, parse_import_payload
from desktop.native.look import pack_stylesheet, resolved_palette, sanitize_look
from desktop.native.remind import REMINDER_POLL_MS
from desktop.native.reuse import late_from_start, restore_point_label, running_late_refusal, week_label
from desktop.native.settings import (
    AccountDialog,
    AlarmRingDialog,
    FocusPanel,
    PrefsDialog,
    RestoreDialog,
    TransferPreviewDialog,
)
from desktop.native.widgets import (
    AvailabilityDialog,
    BlockDialog,
    CategoryChips,
    DayAgenda,
    FlowLayout,
    HomeworkDialog,
    LateDialog,
    MonthGrid,
    PreviewDialog,
    RoutineDialog,
    SpreadDialog,
    UnfinishedPanel,
    WeekTable,
)

WINDOW_SIZE = (1280, 800)


class NativeWindow(QMainWindow):
    def __init__(self, origin: str, icon: QIcon | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = NativeSession(origin, self)
        self._instance_server: QLocalServer | None = None
        self.setWindowTitle("FlexWeek")
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(*WINDOW_SIZE)
        self._stack = QStackedWidget(self)
        self._stack.setObjectName("nativeStack")
        self.setCentralWidget(self._stack)
        self._more_pairs = []
        self._build_auth()
        self._build_recovery()
        self._build_week()
        self.session.account_changed.connect(self._on_account)
        self.session.recovery_codes.connect(self._show_recovery)
        self.session.week_changed.connect(self._on_week)
        self.session.status.connect(self._on_status)
        self.session.busy_changed.connect(self._on_busy)
        self._late_dialog: LateDialog | None = None
        self._pending_spread_ui = False
        self._quitting = False
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_hinted = False
        self._icon = icon or QIcon()
        self._alarm_dialog: AlarmRingDialog | None = None
        self._look = sanitize_look(None)
        self._allow_week_page = True
        self._load_look()
        self.session.look = self._look
        self.session.focus_changed.connect(self._on_focus)
        self.session.focus_replace_needed.connect(self._confirm_replace_focus)
        self.session.alerts.connect(self._present_alerts)
        self.session.alarm_due.connect(self._on_alarm)
        self._focus_tick = QTimer(self)
        self._focus_tick.setInterval(500)
        self._focus_tick.timeout.connect(self.session.tick_focus)
        self._focus_tick.start()
        self._alert_tick = QTimer(self)
        self._alert_tick.setInterval(REMINDER_POLL_MS)
        self._alert_tick.timeout.connect(self.session.check_alerts)
        self._alert_tick.start()
        self._apply_appearance()
        if QSystemTrayIcon.isSystemTrayAvailable() and not self._icon.isNull():
            self._install_tray()
        self._show_page("authPage")

    def listen_for_instances(self, name: str) -> bool:
        server = QLocalServer(self)
        if not server.listen(name):
            QLocalServer.removeServer(name)
            if not server.listen(name):
                return False
        server.newConnection.connect(self._on_instance_knock)
        self._instance_server = server
        return True

    def _on_instance_knock(self) -> None:
        server = self._instance_server
        while server is not None and server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnected.connect(connection.deleteLater)
            connection.disconnectFromServer()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_page(self, name: str) -> None:
        for index in range(self._stack.count()):
            page = self._stack.widget(index)
            if page.objectName() == name:
                self._stack.setCurrentIndex(index)
                return

    def _build_auth(self) -> None:
        page = QWidget()
        page.setObjectName("authPage")
        layout = QVBoxLayout(page)
        heading = QLabel("Create your account")
        heading.setObjectName("authHeading")
        layout.addWidget(heading)
        note = QLabel(
            "FlexWeek fits homework around school and sports. Your week is saved to your account."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.username = QLineEdit()
        self.username.setObjectName("username")
        self.username.setMaxLength(32)
        self.username.setPlaceholderText("Username")
        layout.addWidget(self.username)
        self.password = QLineEdit()
        self.password.setObjectName("password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaxLength(128)
        self.password.setPlaceholderText("Password")
        layout.addWidget(self.password)
        buttons = QHBoxLayout()
        create = QPushButton("Create account")
        create.setObjectName("createAccount")
        create.clicked.connect(self._create_account)
        sign_in = QPushButton("Sign in")
        sign_in.setObjectName("signIn")
        sign_in.clicked.connect(self._sign_in)
        buttons.addWidget(create)
        buttons.addWidget(sign_in)
        layout.addLayout(buttons)
        forgot = QPushButton("Forgot password")
        forgot.setObjectName("forgotPassword")
        forgot.clicked.connect(self._toggle_recover)
        layout.addWidget(forgot)
        self.recovery_code = QLineEdit()
        self.recovery_code.setObjectName("recoveryCode")
        self.recovery_code.setPlaceholderText("Recovery code")
        self.recovery_code.setVisible(False)
        layout.addWidget(self.recovery_code)
        self.new_recovery_password = QLineEdit()
        self.new_recovery_password.setObjectName("recoverPassword")
        self.new_recovery_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_recovery_password.setPlaceholderText("New password")
        self.new_recovery_password.setVisible(False)
        layout.addWidget(self.new_recovery_password)
        self.recover_button = QPushButton("Reset password")
        self.recover_button.setObjectName("recoverAccount")
        self.recover_button.setVisible(False)
        self.recover_button.clicked.connect(self._recover_account)
        layout.addWidget(self.recover_button)
        self.auth_status = QLabel()
        self.auth_status.setObjectName("authStatus")
        self.auth_status.setWordWrap(True)
        layout.addWidget(self.auth_status)
        layout.addStretch()
        self._stack.addWidget(page)

    def _build_recovery(self) -> None:
        page = QWidget()
        page.setObjectName("recoveryPage")
        layout = QVBoxLayout(page)
        heading = QLabel("Save these recovery codes")
        layout.addWidget(heading)
        note = QLabel(
            "They are the only way to reset your password. FlexWeek cannot email you. "
            "Copy them somewhere you will still have if this computer is gone."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.recovery_list = QLabel()
        self.recovery_list.setObjectName("recoveryList")
        self.recovery_list.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.recovery_list)
        self.recovery_ack = QCheckBox("I have saved these codes")
        self.recovery_ack.setObjectName("recoveryAck")
        self.recovery_ack.toggled.connect(self._on_recovery_ack)
        layout.addWidget(self.recovery_ack)
        self.recovery_continue = QPushButton("Continue")
        self.recovery_continue.setObjectName("recoveryContinue")
        self.recovery_continue.setEnabled(False)
        self.recovery_continue.clicked.connect(self._finish_recovery)
        layout.addWidget(self.recovery_continue)
        layout.addStretch()
        self._stack.addWidget(page)

    def _build_week(self) -> None:
        page = QWidget()
        page.setObjectName("weekPage")
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        self.account_name = QLabel()
        self.account_name.setObjectName("accountName")
        bar.addWidget(self.account_name)
        self.prev_nav = QPushButton("Previous week")
        self.prev_nav.setObjectName("prevWeek")
        self.prev_nav.clicked.connect(self._go_previous)
        self.next_nav = QPushButton("Next week")
        self.next_nav.setObjectName("nextWeek")
        self.next_nav.clicked.connect(self._go_next)
        bar.addWidget(self.prev_nav)
        bar.addWidget(self.next_nav)
        for view, label in (("day", "Day"), ("week", "Week"), ("month", "Month")):
            button = QPushButton(label)
            button.setObjectName(f"view{view.title()}")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=view: self.session.set_view(value))
            bar.addWidget(button)
        bar.addStretch()
        sign_out = QPushButton("Log out")
        sign_out.setObjectName("signOut")
        sign_out.clicked.connect(self.session.logout)
        bar.addWidget(sign_out)
        layout.addLayout(bar)
        self.chips = CategoryChips()
        self.chips.category_chosen.connect(self._add_from_chip)
        layout.addWidget(self.chips)
        # Wrapping, because twenty buttons in one row made the window wider than any laptop screen.
        actions = FlowLayout()
        add_fixed = QPushButton("Add fixed time")
        add_fixed.setObjectName("addFixed")
        add_fixed.clicked.connect(self._add_fixed)
        add_homework = QPushButton("Add homework")
        add_homework.setObjectName("addHomework")
        add_homework.clicked.connect(self._add_homework)
        undo = QPushButton("Undo")
        undo.setObjectName("undoButton")
        undo.clicked.connect(self.session.undo)
        redo = QPushButton("Redo")
        redo.setObjectName("redoButton")
        redo.clicked.connect(self.session.redo)
        solve = QPushButton("Plan my homework")
        solve.setObjectName("solveButton")
        solve.clicked.connect(self.session.solve)
        save = QPushButton("Save")
        save.setObjectName("saveButton")
        save.clicked.connect(self.session.save)
        retry = QPushButton("Retry save")
        retry.setObjectName("retrySave")
        retry.clicked.connect(self.session.retry_save)
        reload_week = QPushButton("Reload")
        reload_week.setObjectName("reloadWeek")
        reload_week.clicked.connect(self.session.reload)
        copy_block = QPushButton("Copy")
        copy_block.setObjectName("copyBlock")
        copy_block.clicked.connect(self._copy_selected)
        paste_block = QPushButton("Paste")
        paste_block.setObjectName("pasteBlock")
        paste_block.clicked.connect(self._paste_clipboard)
        duplicate = QPushButton("Duplicate")
        duplicate.setObjectName("duplicateBlock")
        duplicate.clicked.connect(self._duplicate_selected)
        copy_day = QPushButton("Copy day")
        copy_day.setObjectName("copyDay")
        copy_day.clicked.connect(self._copy_day)
        routines = QPushButton("Routines")
        routines.setObjectName("routinesButton")
        routines.clicked.connect(self._open_routines)
        unfinished = QPushButton("Unfinished")
        unfinished.setObjectName("unfinishedOpen")
        unfinished.clicked.connect(self._show_unfinished)
        late = QPushButton("Running late")
        late.setObjectName("runningLate")
        late.clicked.connect(self._open_late)
        availability = QPushButton("Availability")
        availability.setObjectName("availabilityButton")
        availability.clicked.connect(self._open_availability)
        settings = QPushButton("Settings")
        settings.setObjectName("settingsButton")
        settings.clicked.connect(self._open_settings)
        restore = QPushButton("Restore")
        restore.setObjectName("restoreButton")
        restore.clicked.connect(self._open_restore)
        account = QPushButton("Account")
        account.setObjectName("accountButton")
        account.clicked.connect(self._open_account)
        spotify = QPushButton("Spotify")
        spotify.setObjectName("openSpotify")
        spotify.clicked.connect(self._open_spotify)
        more = QPushButton("More")
        more.setObjectName("moreButton")
        overflow = QWidget(page)
        overflow.setObjectName("moreOverflow")
        overflow.hide()
        more_menu = QMenu(more)
        self._more_pairs = []
        for button in (
            copy_day,
            routines,
            unfinished,
            late,
            availability,
            restore,
            account,
            spotify,
            reload_week,
        ):
            button.setParent(overflow)
            action = more_menu.addAction(button.text())
            action.triggered.connect(button.click)
            self._more_pairs.append((action, button))
        more_menu.aboutToShow.connect(self._sync_more_menu)
        more.setMenu(more_menu)
        for button in (
            add_fixed,
            add_homework,
            undo,
            redo,
            copy_block,
            paste_block,
            duplicate,
            settings,
            solve,
            save,
            retry,
            more,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.clipboard_summary = QLabel("Nothing copied")
        self.clipboard_summary.setObjectName("clipboardSummary")
        layout.addWidget(self.clipboard_summary)
        self.focus_panel = FocusPanel()
        self.focus_panel.start_requested.connect(self._start_focus)
        self.focus_panel.quick_requested.connect(self.session.start_quick_focus)
        self.focus_panel.pause_requested.connect(self.session.toggle_focus_pause)
        self.focus_panel.skip_requested.connect(lambda: self.session.advance_focus(False))
        self.focus_panel.reset_requested.connect(self.session.reset_focus)
        self.focus_panel.finished_requested.connect(self.session.finish_focused_homework)
        self.focus_panel.break_requested.connect(self.session.take_focus_break)
        self.focus_panel.more_requested.connect(self.session.add_focus_time)
        layout.addWidget(self.focus_panel)
        self.unfinished_panel = UnfinishedPanel()
        self.unfinished_panel.plan_requested.connect(self._plan_unfinished)
        layout.addWidget(self.unfinished_panel)
        self.planner = QStackedWidget()
        self.planner.setObjectName("plannerStack")
        self.week_table = WeekTable()
        self.week_table.block_activated.connect(self._edit_block)
        self.week_table.slot_activated.connect(self._create_at_slot)
        self.week_table.range_created.connect(self._create_range)
        self.week_table.times_changed.connect(self._apply_times)
        self.week_table.series_drag_refused.connect(self._refuse_series)
        self.week_table.block_selected.connect(self.session.select_block)
        self.planner.addWidget(self.week_table)
        self.day_agenda = DayAgenda()
        self.day_agenda.item_activated.connect(self._edit_block)
        self.day_agenda.homework_activated.connect(self._edit_homework)
        self.day_agenda.plan_requested.connect(self.session.solve)
        self.day_agenda.add_requested.connect(self._add_homework)
        self.planner.addWidget(self.day_agenda)
        self.month_grid = MonthGrid()
        self.month_grid.day_activated.connect(self.session.open_day)
        self.planner.addWidget(self.month_grid)
        for widget in (
            self.week_table,
            self.day_agenda.list,
            self.month_grid.table,
            self.focus_panel.tasks,
        ):
            widget.installEventFilter(self)
        # The calendar is the point of this page, so it takes whatever height the rest does not need.
        layout.addWidget(self.planner, 1)
        self.week_status = QLabel()
        self.week_status.setObjectName("weekStatus")
        self.week_status.setWordWrap(True)
        layout.addWidget(self.week_status)
        self._stack.addWidget(page)

    def _on_account(self, account: object) -> None:
        if account is None:
            self.username.clear()
            self.password.clear()
            self._show_page("authPage")
            return
        self.account_name.setText(account["username"])

    def _on_recovery(self) -> bool:
        return self.findChild(QWidget, "recoveryPage") is self._stack.currentWidget()

    def _finish_recovery(self) -> None:
        self._allow_week_page = True
        self.session.finish_recovery()

    def _show_recovery(self, codes: list) -> None:
        self._allow_week_page = False
        self.recovery_list.setText("\n".join(str(code) for code in codes))
        self.recovery_ack.setChecked(False)
        self.recovery_continue.setEnabled(False)
        self._show_page("recoveryPage")

    def _on_week(self) -> None:
        if self.session.account is None:
            return
        if self._on_recovery() and not self._allow_week_page:
            return
        self.week_table.set_week(self.session.week_start, self.session.blocks, self.session.trace)
        agenda = agenda_for(
            self.session.week_start,
            self.session.selected_day,
            self.session.blocks,
            self.session.assignments,
            self.session.trace,
            self.session.day_data,
        )
        self.day_agenda.set_agenda(self.session.selected_day, agenda, self.session.day_data)
        self.month_grid.set_month(self.session.month_data, self.session.dirty)
        self.chips.set_armed(self.session.armed_category)
        view = self.session.planner_view
        self.planner.setCurrentWidget(
            {"day": self.day_agenda, "month": self.month_grid}.get(view, self.week_table)
        )
        for name in ("viewDay", "viewWeek", "viewMonth"):
            button = self.findChild(QPushButton, name)
            if button is not None:
                button.setChecked(name == f"view{view.title()}")
        month = view == "month"
        day = view == "day"
        if month:
            self.prev_nav.setText("Previous month")
            self.next_nav.setText("Next month")
        elif day:
            self.prev_nav.setText("Previous day")
            self.next_nav.setText("Next day")
        else:
            self.prev_nav.setText("Previous week")
            self.next_nav.setText("Next week")
        self._show_page("weekPage")
        retry = self.findChild(QPushButton, "retrySave")
        if retry is not None:
            retry.setEnabled(self.session.pending_save is not None and not self.session.conflict)
        undo = self.findChild(QPushButton, "undoButton")
        redo = self.findChild(QPushButton, "redoButton")
        if undo is not None:
            undo.setEnabled(self.session.can_undo())
        if redo is not None:
            redo.setEnabled(self.session.can_redo())
        clip = self.session.clipboard
        self.clipboard_summary.setText("Copied: " + clip["label"] if clip else "Nothing copied")
        destination = self.session.paste_destination()
        copy_day = self.findChild(QPushButton, "copyDay")
        paste = self.findChild(QPushButton, "pasteBlock")
        if copy_day is not None:
            if destination is None:
                copy_day.setText("Copy a selected day")
            else:
                copy_day.setText("Copy " + DAY_FULL[destination[0]])
        if paste is not None:
            paste.setEnabled(clip is not None and destination is not None)
            if destination is None:
                paste.setText("Paste into a selected day")
            else:
                paste.setText("Paste into " + DAY_FULL[destination[0]])
        items = self.session.unfinished()
        unfinished = self.findChild(QPushButton, "unfinishedOpen")
        if unfinished is not None:
            unfinished.setEnabled(bool(items))
        prompt = self.session.consume_unfinished()
        if prompt:
            self.unfinished_panel.set_items(prompt)
        elif not items:
            self.unfinished_panel.hide()
        if self._late_dialog is not None and self.session.late_preview:
            titles = {block["id"]: block["title"] for block in self.session.blocks}
            self._late_dialog.show_trace(self.session.late_preview["trace"], titles)
        self.focus_panel.set_state(self.session)
        self._apply_appearance()
        if self._pending_spread_ui and self.session.spread_preview:
            self._pending_spread_ui = False
            preview = self.session.spread_preview
            item = self.session.assignments.get(preview["assignment_id"])
            title = item["title"] if item else "homework"
            QTimer.singleShot(
                0,
                lambda: self._show_preview(
                    "Spread " + title,
                    preview["summary"],
                    preview["rows"],
                    label="spreading " + title,
                    attempt_key=(
                        f"spread|{self.session.account['id']}|{preview['assignment_id']}|"
                        f"{preview['from_date']}|{preview['session_min']}"
                        if self.session.account
                        else None
                    ),
                ),
            )

    def _on_status(self, message: str) -> None:
        self.auth_status.setText(message)
        self.week_status.setText(message)

    def _sync_more_menu(self) -> None:
        for action, button in self._more_pairs:
            action.setEnabled(button.isEnabled())

    def _on_busy(self, busy: bool) -> None:
        names = (
            "createAccount",
            "signIn",
            "recoveryContinue",
            "addFixed",
            "addHomework",
            "solveButton",
            "saveButton",
            "signOut",
            "prevWeek",
            "nextWeek",
            "reloadWeek",
            "viewDay",
            "viewWeek",
            "viewMonth",
            "undoButton",
            "redoButton",
            "copyBlock",
            "pasteBlock",
            "duplicateBlock",
            "copyDay",
            "routinesButton",
            "unfinishedOpen",
            "runningLate",
            "availabilityButton",
            "settingsButton",
            "restoreButton",
            "accountButton",
            "openSpotify",
            "forgotPassword",
            "recoverAccount",
            "moreButton",
        )
        for name in names:
            button = self.findChild(QPushButton, name)
            if button is not None:
                button.setEnabled(not busy)
        retry = self.findChild(QPushButton, "retrySave")
        can_retry = not busy and self.session.pending_save is not None and not self.session.conflict
        if retry is not None:
            retry.setEnabled(can_retry)
        undo = self.findChild(QPushButton, "undoButton")
        redo = self.findChild(QPushButton, "redoButton")
        if undo is not None:
            undo.setEnabled(not busy and self.session.can_undo())
        if redo is not None:
            redo.setEnabled(not busy and self.session.can_redo())
        on_recovery = self.findChild(QWidget, "recoveryPage") is self._stack.currentWidget()
        if not busy and self.session.account is not None and on_recovery:
            self.recovery_continue.setEnabled(self.recovery_ack.isChecked())

    def _on_recovery_ack(self, checked: bool) -> None:
        self.recovery_continue.setEnabled(checked and not self.session.busy)

    def _create_account(self) -> None:
        self.session.register(self.username.text().strip(), self.password.text())

    def _sign_in(self) -> None:
        self.session.login(self.username.text().strip(), self.password.text())

    def _go_previous(self) -> None:
        if self.session.planner_view == "month":
            self.session.shift_month(-1)
            return
        if self.session.planner_view == "day":
            current = date.fromisoformat(self.session.selected_day)
            self.session.open_day((current + timedelta(days=-1)).isoformat())
            return
        self._shift_week(-7)

    def _go_next(self) -> None:
        if self.session.planner_view == "month":
            self.session.shift_month(1)
            return
        if self.session.planner_view == "day":
            current = date.fromisoformat(self.session.selected_day)
            self.session.open_day((current + timedelta(days=1)).isoformat())
            return
        self._shift_week(7)

    def _shift_week(self, days: int) -> None:
        monday = date.fromisoformat(self.session.week_start) + timedelta(days=days)
        self.session.load_week(monday.isoformat())

    def _commit_block(self, dialog: BlockDialog) -> None:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.deleted():
            self.session.delete_block(
                dialog.block()["id"], scope=dialog.scope(), day=dialog.occurrence_day()
            )
        else:
            before = {item["id"] for item in self.session.blocks}
            self.session.add_block(dialog.block(), scope=dialog.scope(), day=dialog.occurrence_day())
            day = dialog.occurrence_day()
            if dialog.recover_missed() and day is not None:
                # "This day only" splits the series and gives that day a new id. recover_missed returns
                # without saving when its block does not hold the day, so it only gets one that does;
                # otherwise the edit is saved the ordinary way instead of staying an unsaved draft.
                ids = {dialog.block()["id"]} | ({item["id"] for item in self.session.blocks} - before)
                holder = next(
                    (item for item in self.session.blocks if item["id"] in ids and day in item["days"]),
                    None,
                )
                if holder is not None:
                    self.session.recover_missed(holder["id"], day)
                    return
        self.session.save()

    def _commit_homework(self, dialog: HomeworkDialog, days: list[int] | None = None) -> None:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.spread_requested():
            self._open_spread(dialog.assignment()["id"])
            return
        self.session.add_homework(dialog.assignment(), days=days)
        self.session.save()

    def _add_fixed(self) -> None:
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            category = "class"
        self._commit_block(BlockDialog(self, category=category))

    def _add_homework(self) -> None:
        category = self.session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        self._commit_homework(
            HomeworkDialog(self, week_start=self.session.week_start, category=category)
        )

    def _add_from_chip(self, category: str) -> None:
        self.session.arm_category(category)
        self.chips.set_armed(category)
        if category in FLEX_CATEGORIES:
            self._commit_homework(
                HomeworkDialog(self, week_start=self.session.week_start, category=category)
            )
            return
        self._commit_block(BlockDialog(self, category=category))

    def _create_at_slot(self, day: int, start: str) -> None:
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            self._commit_homework(
                HomeworkDialog(
                    self,
                    week_start=self.session.week_start,
                    category=category,
                    due=sunday_due(self.session.week_start),
                ),
                days=[day],
            )
            return
        self._commit_block(BlockDialog(self, day=day, start=start, category=category, from_range=True))

    def _create_range(self, day: int, start_min: int, end_min: int) -> None:
        start = minutes_to_hhmm(start_min)
        duration = end_min - start_min
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            self._commit_homework(
                HomeworkDialog(
                    self,
                    week_start=self.session.week_start,
                    category=category,
                    estimate_min=duration,
                    due=sunday_due(self.session.week_start),
                ),
                days=[day],
            )
            return
        self._commit_block(
            BlockDialog(
                self,
                day=day,
                start=start,
                duration_min=duration,
                category=category,
                from_range=True,
            )
        )

    def _apply_times(self, block_id: str, start_min: int, end_min: int) -> None:
        if self.session.apply_times(block_id, start_min, end_min):
            self.session.save()

    def _refuse_series(self, block_id: str, day: int) -> None:
        self.session.select_block(block_id, day)
        self.session.refuse_series_drag(block_id)

    def _edit_homework(self, assignment_id: str) -> None:
        assignment = self.session.assignments.get(assignment_id)
        if assignment is None:
            return
        self._commit_homework(HomeworkDialog(self, assignment, self.session.week_start))

    def _edit_block(self, block_id: str) -> None:
        if self.session.planner_view == "day":
            self.session.select_block(block_id, date.fromisoformat(self.session.selected_day).weekday())
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            return
        assignment_id = block.get("assignment_id")
        if assignment_id and assignment_id in self.session.assignments:
            self._edit_homework(assignment_id)
            return
        if block.get("kind") != "locked":
            return
        dialog = BlockDialog(
            self,
            block,
            occurrence_day=self.session.selected_occurrence_day,
        )
        self._commit_block(dialog)

    def _show_preview(
        self,
        title: str,
        summary: str,
        rows: list[dict] | None,
        *,
        label: str,
        snapshot_label: str | None = None,
        attempt_key: str | None = None,
        existing: list[dict] | None = None,
        destination: str | None = None,
    ) -> None:
        if not rows:
            return
        dialog = PreviewDialog(
            self,
            title,
            summary,
            rows,
            existing if existing is not None else self.session.blocks,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.session.confirm_preview(
            dialog.rows(),
            label=label,
            snapshot_label=snapshot_label,
            attempt_key=attempt_key,
            existing=existing,
            destination=destination,
        )

    def _copy_selected(self) -> None:
        self.session.copy_selected()

    def _paste_clipboard(self) -> None:
        clip = self.session.clipboard
        rows = self.session.paste_proposals()
        label = "the copied day" if clip and clip["kind"] == "day" else "the copied block"
        key = None
        if clip and self.session.account is not None:
            dest = self.session.paste_destination()
            key = (
                f"paste|{self.session.account['id']}|{self.session.week_start}|"
                f"{dest[0] if dest else ''}|{(dest[1] if dest else '') or ''}|"
                f"{clip['fingerprint']}"
            )
        self._show_preview(
            "Preview paste",
            "Nothing changes until you save this preview.",
            rows,
            label=label,
            attempt_key=key,
        )

    def _duplicate_selected(self) -> None:
        rows = self.session.duplicate_selected()
        self._show_preview(
            "Preview paste",
            "Nothing changes until you save this preview.",
            rows,
            label="the copied block",
        )

    def _copy_day(self) -> None:
        self.session.copy_day()

    def _open_routines(self) -> None:
        dialog = RoutineDialog(
            self, self.session.routines, self.session.blocks, self.session.week_start
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.action == "save":
            self.session.save_routine(dialog.name.text(), dialog.selected_block_ids())
            return
        if dialog.action == "delete" and dialog.routine_id:
            self.session.delete_routine(dialog.routine_id)
            return
        if dialog.action == "apply" and dialog.routine_id:
            routine = self.session.routines.get(dialog.routine_id)
            dest = dialog.destination
            rows = self.session.apply_routine_rows(dialog.routine_id, dest, dialog.days)
            name = routine["name"] if routine else "routine"
            key = None
            if routine and self.session.account is not None:
                key = (
                    f"routine|{self.session.account['id']}|{dialog.routine_id}|"
                    f"{routine['revision']}|{dest}|"
                    + ",".join(str(day) for day in dialog.days)
                )

            def show(existing: list[dict]) -> None:
                self._show_preview(
                    "Apply " + name,
                    "Uncheck holidays or adjust one-off times before saving.",
                    rows,
                    label="the " + name + " routine",
                    snapshot_label=restore_point_label("Before applying " + name + " to " + dest),
                    attempt_key=key,
                    existing=existing,
                    destination=dest,
                )

            if dest == self.session.week_start:
                show(self.session.blocks)
                return

            def ok(data: dict) -> None:
                show(list(data.get("blocks") or []))

            def err(error: object) -> None:
                self.session._say(getattr(error, "message", str(error)))

            self.session.client.request("GET", f"/api/week?week_start={dest}", None, ok, err)
            return

    def _show_unfinished(self) -> None:
        self.unfinished_panel.set_items(self.session.unfinished())

    def _plan_unfinished(self, assignment_id: str) -> None:
        item = self.session.assignments.get(assignment_id)
        rows = self.session.plan_unfinished(assignment_id)
        self._show_preview(
            "Plan unfinished homework",
            (item["title"] + " keeps its original deadline and progress.") if item else "",
            rows,
            label="unfinished homework",
            attempt_key=(
                f"unfinished|{self.session.account['id']}|{self.session.week_start}|"
                f"{assignment_id}|{self.session.remaining_for(assignment_id)}"
                if self.session.account
                else None
            ),
        )

    def _open_late(self) -> None:
        now = datetime.now()
        refusal = running_late_refusal(
            week_start=self.session.week_start,
            now=now,
            dirty=self.session.dirty,
            conflict=self.session.conflict,
            block_count=len(self.session.blocks),
        )
        if refusal:
            self.session._say(refusal)
            return
        from_start = late_from_start(now.hour * 60 + now.minute)
        dialog = LateDialog(self, f"Starting from {from_start} today ({DAY_FULL[now.weekday()]}).")
        dialog.preview_requested.connect(
            lambda: self.session.preview_running_late(dialog.chosen_minutes(), now)
        )
        self._late_dialog = dialog
        self.session.status.connect(dialog.error.setText)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        with contextlib.suppress(RuntimeError, TypeError):
            self.session.status.disconnect(dialog.error.setText)
        self._late_dialog = None
        if accepted:
            self.session.accept_running_late()
        else:
            self.session.late_preview = None

    def _open_spread(self, assignment_id: str) -> None:
        item = self.session.assignments.get(assignment_id)
        if item is None or item.get("completed"):
            return
        due_date = item["due"][:10]
        today = date.today().isoformat()
        base = self.session.selected_day if self.session.selected_day > today else today
        from_date = base if base <= due_date else due_date
        dialog = SpreadDialog(self, item, from_date)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._pending_spread_ui = True
        self.session.preview_spread(assignment_id, dialog.session_min(), dialog.from_iso())

    def _open_availability(self) -> None:
        if self.session.preferences is None:
            self.session._say("Still loading your settings…")
            return
        dialog = AvailabilityDialog(self, self.session.preferences)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.session.save_availability(dialog.protected(), dialog.study_windows(), dialog.day_cutoff())

    def _toggle_recover(self) -> None:
        visible = not self.recovery_code.isVisible()
        self.recovery_code.setVisible(visible)
        self.new_recovery_password.setVisible(visible)
        self.recover_button.setVisible(visible)

    def _recover_account(self) -> None:
        self.session.recover(
            self.username.text().strip(),
            self.recovery_code.text().strip(),
            self.new_recovery_password.text(),
        )

    def _start_focus(self, block_id: str, day: object) -> None:
        self.session.start_focus(block_id or None, day if isinstance(day, int) else None)

    def _confirm_replace_focus(self, current: str, incoming: str) -> None:
        answer = QMessageBox.question(
            self,
            "Replace timer",
            f"Stop the timer for {current} and start {incoming} instead?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.session.confirm_replace_focus()

    def _on_focus(self) -> None:
        self.focus_panel.set_state(self.session)

    def _present_alerts(self, notices: list) -> None:
        for notice in notices:
            title = notice.get("title") or "FlexWeek"
            body = notice.get("body") or ""
            if self._tray_icon is not None and self._tray_icon.supportsMessages():
                self._tray_icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)
            else:
                self.session._say(title + (" — " + body if body else ""))

    def _on_alarm(self, alarm: object) -> None:
        if not isinstance(alarm, dict):
            return
        if self._alarm_dialog is not None:
            return
        url = self.session.spotify_url(alarm.get("spotify_url"))
        dialog = AlarmRingDialog(self, alarm, url)
        self._alarm_dialog = dialog
        dialog.exec()
        snoozed = dialog.snoozed
        self._alarm_dialog = None
        self.session.finish_alarm(snoozed)

    def _open_spotify(self) -> None:
        url = self.session.spotify_url()
        if not url:
            self.session._say("This item has no Spotify share link.")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _open_settings(self) -> None:
        if self.session.preferences is None:
            self.session._say("Still loading your settings…")
            return
        dialog = PrefsDialog(self, self.session.preferences, self._look, self.session.reminder_limits)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._look = dialog.look_choice()
        self.session.look = self._look
        self._save_look()
        self.session.save_preferences(dialog.updates())
        self._apply_appearance()

    def _open_restore(self) -> None:
        dialog = RestoreDialog(
            self, self.session.restore_points, self.session.restore_preview, self.session.storage_info
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.action == "create":
            self.session.create_restore_point(dialog.create_label)
        elif dialog.action == "preview" and dialog.selected_id:
            self.session.preview_restore_point(dialog.selected_id, self._open_restore)
        elif dialog.action == "restore" and dialog.selected_id:
            confirm = QMessageBox.question(
                self,
                "Restore",
                "Restore this snapshot? FlexWeek saves a restore point first.",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.session.apply_restore_point(dialog.selected_id)

    def _open_account(self) -> None:
        dialog = AccountDialog(self, self.session.recovery_remaining, self.session.storage_info)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        password = dialog.current_password.text()
        if dialog.action == "password":
            self.session.change_password(password, dialog.new_password.text())
        elif dialog.action == "codes":
            self.session.replace_recovery_codes(password)
        elif dialog.action == "delete":
            confirm = QMessageBox.question(self, "Delete account", "Delete this account and its saved weeks?")
            if confirm == QMessageBox.StandardButton.Yes:
                self.session.delete_account(password)
        elif dialog.action == "export":
            self.session.export_account(password, self._write_account_file)
        elif dialog.action == "import":
            path, _ = QFileDialog.getOpenFileName(self, "Import account", "", "JSON (*.json)")
            if not path:
                return
            try:
                snapshot = json.loads(Path(path).read_text())
            except (OSError, UnicodeDecodeError, ValueError) as error:
                self.session._say("Could not read that file. " + str(error))
                return
            if not isinstance(snapshot, dict):
                self.session._say("Choose a FlexWeek account transfer file.")
                return
            self.session.preview_account_import(snapshot, self._confirm_transfer)
        elif dialog.action == "week":
            self._write_json("flexweek-" + self.session.week_start + ".json", self.session.week_file())
        elif dialog.action == "day":
            destination = self.session.paste_destination()
            if destination is None:
                self.session._say("Select a day first.")
                return
            day = destination[0]
            self._write_json("flexweek-day.json", self.session.day_file(day))
        elif dialog.action == "import-week":
            path, _ = QFileDialog.getOpenFileName(self, "Import week or day", "", "JSON (*.json)")
            if not path:
                return
            try:
                raw = Path(path).read_text()
            except (OSError, UnicodeDecodeError) as error:
                self.session._say("Could not read that file. " + str(error))
                return
            parsed = parse_import_payload(raw)
            if parsed.get("error"):
                self.session._say(parsed["error"])
                return
            if parsed.get("format") == EXPORT_FORMAT and self.session.blocks:
                confirm = QMessageBox.question(
                    self,
                    "Replace week",
                    "Replace blocks in "
                    + week_label(self.session.week_start)
                    + " with the import? Other weeks stay untouched.",
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                self.session.import_week_file(raw, replace=True)
            else:
                self.session.import_week_file(raw)

    def _confirm_transfer(self) -> None:
        preview = self.session.transfer_preview
        if preview is None:
            return
        dialog = TransferPreviewDialog(self, preview)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.apply_account_import()

    def _write_account_file(self, snapshot: dict) -> None:
        name = "flexweek-account-" + snapshot.get("username", "account") + ".json"
        self._write_json(name, snapshot)

    def _write_json(self, name: str, payload: dict) -> None:
        import json

        path, _ = QFileDialog.getSaveFileName(self, "Save FlexWeek file", name, "JSON (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(payload, indent=2) + "\n")
        except OSError as error:
            self.session._say("Could not write that file. " + str(error))

    def _look_path(self) -> Path:
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        return root / "flexweek-look.json"

    def _load_look(self) -> None:
        import json

        path = self._look_path()
        if not path.is_file():
            return
        try:
            self._look = sanitize_look(json.loads(path.read_text()))
        except (OSError, ValueError):
            self._look = sanitize_look(None)

    def _save_look(self) -> None:
        import json

        path = self._look_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._look) + "\n")
        except OSError:
            self.session._say("Could not save the look for this device.")

    def _apply_appearance(self) -> None:
        pack = (self.session.preferences or {}).get("theme_pack") or "system"
        accent = (self.session.preferences or {}).get("accent") or "default"
        system_dark = QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        self.setStyleSheet(pack_stylesheet(pack, system_dark, self._look, accent))
        # Blocks and month cells are painted per item, which a stylesheet cannot reach.
        palette = resolved_palette(pack, system_dark, self._look, accent)
        self.week_table.set_look(self._look, palette)
        self.month_grid.set_palette(palette)

    def _install_tray(self) -> None:
        tray = QSystemTrayIcon(self._icon, self)
        menu = QMenu(self)
        show = menu.addAction("Show FlexWeek")
        show.triggered.connect(self.restore_window)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        tray.setContextMenu(menu)
        tray.setToolTip("FlexWeek")
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray_icon = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason != QSystemTrayIcon.ActivationReason.Context:
            self.restore_window()

    def restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self._quitting = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        tray = self._tray_icon
        prefs = self.session.preferences or {}
        stay = prefs.get("tray_notifications", True) is not False
        if tray is not None and tray.isVisible() and not self._quitting and stay:
            self.hide()
            event.ignore()
            if not self._tray_hinted:
                self._tray_hinted = True
                tray.showMessage(
                    "FlexWeek is still running",
                    "It stays in the tray so reminders and alarms still work.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.session.account is None or QApplication.activeModalWidget() is not None:
            super().keyPressEvent(event)
            return
        if self._on_recovery():
            super().keyPressEvent(event)
            return
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)):
            super().keyPressEvent(event)
            return
        key = event.key()
        mods = event.modifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if key == Qt.Key.Key_Z:
                if mods & Qt.KeyboardModifier.ShiftModifier:
                    self.session.redo()
                else:
                    self.session.undo()
                event.accept()
                return
            if key == Qt.Key.Key_Y:
                self.session.redo()
                event.accept()
                return
            if key == Qt.Key.Key_C:
                self._copy_selected()
                event.accept()
                return
            if key == Qt.Key.Key_V:
                self._paste_clipboard()
                event.accept()
                return
            if key == Qt.Key.Key_D:
                self._duplicate_selected()
                event.accept()
                return
        if key == Qt.Key.Key_Delete:
            if self.session.delete_selected():
                self.session.save()
            event.accept()
            return
        if key == Qt.Key.Key_W:
            self.session.set_view("week")
            event.accept()
            return
        if key == Qt.Key.Key_D:
            self.session.set_view("day")
            event.accept()
            return
        if key == Qt.Key.Key_M:
            self.session.set_view("month")
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        mods = event.modifiers()
        control = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        if not control and key in (Qt.Key.Key_W, Qt.Key.Key_D, Qt.Key.Key_M, Qt.Key.Key_Delete):
            self.keyPressEvent(event)
            return True
        if control and key in (Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_D, Qt.Key.Key_Z, Qt.Key.Key_Y):
            self.keyPressEvent(event)
            return True
        return super().eventFilter(watched, event)
