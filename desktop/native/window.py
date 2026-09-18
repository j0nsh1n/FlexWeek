"""Qt widgets window for the native FlexWeek desktop client."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.native.controller import NativeSession
from desktop.native.widgets import BlockDialog, HomeworkDialog, WeekTable

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
        self._build_auth()
        self._build_recovery()
        self._build_week()
        self.session.account_changed.connect(self._on_account)
        self.session.recovery_codes.connect(self._show_recovery)
        self.session.week_changed.connect(self._on_week)
        self.session.status.connect(self._on_status)
        self.session.busy_changed.connect(self._on_busy)
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
        note = QLabel("FlexWeek fits homework around school and sports. Your week is saved to your account.")
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
        self.recovery_continue.clicked.connect(self.session.finish_recovery)
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
        prev_week = QPushButton("Previous week")
        prev_week.setObjectName("prevWeek")
        prev_week.clicked.connect(lambda: self._shift_week(-7))
        next_week = QPushButton("Next week")
        next_week.setObjectName("nextWeek")
        next_week.clicked.connect(lambda: self._shift_week(7))
        bar.addWidget(prev_week)
        bar.addWidget(next_week)
        bar.addStretch()
        sign_out = QPushButton("Log out")
        sign_out.setObjectName("signOut")
        sign_out.clicked.connect(self.session.logout)
        bar.addWidget(sign_out)
        layout.addLayout(bar)
        actions = QHBoxLayout()
        add_fixed = QPushButton("Add fixed time")
        add_fixed.setObjectName("addFixed")
        add_fixed.clicked.connect(self._add_fixed)
        add_homework = QPushButton("Add homework")
        add_homework.setObjectName("addHomework")
        add_homework.clicked.connect(self._add_homework)
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
        for button in (add_fixed, add_homework, solve, save, retry, reload_week):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.week_table = WeekTable()
        self.week_table.block_activated.connect(self._edit_block)
        self.week_table.slot_activated.connect(self._create_at_slot)
        layout.addWidget(self.week_table)
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

    def _show_recovery(self, codes: list) -> None:
        self.recovery_list.setText("\n".join(str(code) for code in codes))
        self.recovery_ack.setChecked(False)
        self.recovery_continue.setEnabled(False)
        self._show_page("recoveryPage")

    def _on_week(self) -> None:
        if self.session.account is None:
            return
        self.week_table.set_week(self.session.week_start, self.session.blocks, self.session.trace)
        self._show_page("weekPage")
        retry = self.findChild(QPushButton, "retrySave")
        if retry is not None:
            retry.setEnabled(self.session.pending_save is not None and not self.session.conflict)

    def _on_status(self, message: str) -> None:
        self.auth_status.setText(message)
        self.week_status.setText(message)

    def _on_busy(self, busy: bool) -> None:
        for name in (
            "createAccount", "signIn", "recoveryContinue", "addFixed", "addHomework",
            "solveButton", "saveButton", "signOut", "prevWeek", "nextWeek", "reloadWeek",
        ):
            button = self.findChild(QPushButton, name)
            if button is not None:
                button.setEnabled(not busy)
        retry = self.findChild(QPushButton, "retrySave")
        can_retry = not busy and self.session.pending_save is not None and not self.session.conflict
        if retry is not None:
            retry.setEnabled(can_retry)
        on_recovery = self.findChild(QWidget, "recoveryPage") is self._stack.currentWidget()
        if not busy and self.session.account is not None and on_recovery:
            self.recovery_continue.setEnabled(self.recovery_ack.isChecked())

    def _on_recovery_ack(self, checked: bool) -> None:
        self.recovery_continue.setEnabled(checked and not self.session.busy)

    def _create_account(self) -> None:
        self.session.register(self.username.text().strip(), self.password.text())

    def _sign_in(self) -> None:
        self.session.login(self.username.text().strip(), self.password.text())

    def _shift_week(self, days: int) -> None:
        monday = date.fromisoformat(self.session.week_start) + timedelta(days=days)
        self.session.load_week(monday.isoformat())

    def _add_fixed(self) -> None:
        dialog = BlockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.add_block(dialog.block())
            self.session.save()

    def _add_homework(self) -> None:
        dialog = HomeworkDialog(self, week_start=self.session.week_start)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.add_homework(dialog.assignment())
            self.session.save()

    def _create_at_slot(self, day: int, start: str) -> None:
        dialog = BlockDialog(self, day=day, start=start)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.add_block(dialog.block())
            self.session.save()

    def _edit_block(self, block_id: str) -> None:
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            return
        assignment_id = block.get("assignment_id")
        if assignment_id and assignment_id in self.session.assignments:
            dialog = HomeworkDialog(self, self.session.assignments[assignment_id], self.session.week_start)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.session.add_homework(dialog.assignment())
                self.session.save()
            return
        if block.get("kind") != "locked":
            return
        dialog = BlockDialog(self, block)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.add_block(dialog.block())
            self.session.save()
