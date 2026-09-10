"""FlexWeek desktop app: one Qt WebEngine window over the FlexWeek backend.

By default the backend runs in this process on a loopback port, so the app needs
nothing else installed or running. Set FLEXWEEK_DESKTOP_ORIGIN (or
FLEXWEEK_ORIGIN) to use a hosted deployment instead.

Deliberately thin. The page keeps its own login, CSRF headers and cookies, so
there is no WebChannel, no injected js_api and no cookie access from native
code. See DESKTOP.md.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEngineNewWindowRequest,
    QWebEngineNotification,
    QWebEnginePage,
    QWebEnginePermission,
    QWebEngineProfile,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import backend
from desktop.origin import configured_origin, is_same_origin
from desktop.sandbox import disable_sandbox_if_blocked
from desktop.server import LocalServer

WINDOW_SIZE = (1280, 800)
PROFILE_NAME = "flexweek"
NOTIFICATION_TIMEOUT_MS = 10_000
NOTIFY_STAY_TAG = "flexweek-stay"
TRAY_HINT_MS = 6_000
INSTANCE_WAIT_MS = 500
DESKTOP_FILE_NAME = "flexweek"
SMOKE_FLAG = "--smoke-test"
SMOKE_TIMEOUT_MS = 90_000
SMOKE_POLL_MS = 250
# The first screen only reads this once app.js and auth.js have run against the server.
SMOKE_READY_JS = (
    "Boolean(document.getElementById('status') && "
    "document.getElementById('status').textContent.includes('Create an account'))"
)


def app_icon_path() -> Path:
    """logo.png from the frontend the backend serves.

    Anchored on the backend package, not this file: Nuitka compiles this file as
    the bundle's __main__ at the bundle root, so a path relative to it points one
    directory above the bundle and the tray silently gets no icon.
    """
    return Path(backend.__file__).resolve().parents[1] / "frontend" / "logo.png"


def instance_name(root: str) -> str:
    """One running app per data directory, so two copies never share a database."""
    return "flexweek-" + hashlib.sha256(root.encode()).hexdigest()[:16]


def show_running_instance(name: str) -> bool:
    """Ask an already running FlexWeek to show its window. True if one answered."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(INSTANCE_WAIT_MS):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(INSTANCE_WAIT_MS)
    socket.disconnectFromServer()
    return True


def notification_timeout_ms(tag: str) -> int:
    # Qt does not expose requireInteraction; the page puts flexweek-stay in the tag instead.
    return 0 if tag == NOTIFY_STAY_TAG else NOTIFICATION_TIMEOUT_MS


def profile_root() -> str:
    """Per-user data location; cookies and local storage live under here.

    Qt derives this from the application name, so main() must set that before
    the profile is built.
    """
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)


class ShellPage(QWebEnginePage):
    """Keeps app navigation in the window and sends everything else to the OS browser."""

    def __init__(self, profile: QWebEngineProfile, origin: str, parent: QWidget | None = None) -> None:
        super().__init__(profile, parent)
        self._origin = origin
        self._sent_to_browser = False
        # Handle the request before Qt creates or navigates a hidden popup page.
        self.newWindowRequested.connect(self._open_new_window)
        self.permissionRequested.connect(self._handle_permission)

    @property
    def sent_to_browser(self) -> bool:
        """True when the last finished load was a link we handed to the OS browser."""
        return self._sent_to_browser

    def clear_external_flag(self) -> None:
        self._sent_to_browser = False

    def acceptNavigationRequest(  # noqa: N802 - Qt virtual
        self, url: QUrl | str, nav_type: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        # Qt declares this as QUrl | str; normalize before comparing origins.
        target = QUrl(url) if isinstance(url, str) else url
        if is_main_frame and not is_same_origin(target.toString(), self._origin):
            self._sent_to_browser = True
            self._open_external(target)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    @staticmethod
    def _open_external(url: QUrl) -> None:
        if url.isValid() and url.scheme() in {"https", "http"} and url.host():
            QDesktopServices.openUrl(url)

    def _open_new_window(self, request: QWebEngineNewWindowRequest) -> None:
        self._open_external(request.requestedUrl())

    def _handle_permission(self, permission: QWebEnginePermission) -> None:
        same_origin_notification = (
            permission.permissionType() == QWebEnginePermission.PermissionType.Notifications
            and is_same_origin(permission.origin().toString(), self._origin)
        )
        if same_origin_notification:
            permission.grant()
        else:
            permission.deny()


class RetryPanel(QWidget):
    """Native offline screen. No HTML, so it works when nothing loaded at all."""

    def __init__(self, origin: str, on_retry) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch()
        heading = QLabel("FlexWeek is not responding")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        detail = QLabel(f"Could not reach {origin}.\nCheck that the server is running, then reload.")
        self.button = QPushButton("Reload")
        self.button.clicked.connect(on_retry)
        for widget in (heading, detail, self.button):
            layout.addWidget(widget)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self, origin: str, tray_enabled: bool | None = None) -> None:
        super().__init__()
        self._origin = origin
        self._quitting = False
        self._notification: QWebEngineNotification | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._tray_hinted = False
        self._instance_server: QLocalServer | None = None
        self._icon = QIcon(str(app_icon_path()))
        self.setWindowTitle("FlexWeek")
        self.setWindowIcon(self._icon)
        self.resize(*WINDOW_SIZE)

        root = profile_root()
        # Named profile + explicit paths: the session cookie survives a restart.
        # Parented to the application, not this window: Qt warns and can crash if
        # the profile is released while a page using it is still alive.
        self._profile = QWebEngineProfile(PROFILE_NAME, QApplication.instance())
        self._profile.setPersistentStoragePath(f"{root}/profile")
        self._profile.setCachePath(f"{root}/cache")
        self._profile.downloadRequested.connect(self._save_download)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )

        self._view = QWebEngineView(self)
        self._page = ShellPage(self._profile, origin, self._view)
        self._view.setPage(self._page)
        self._view.loadFinished.connect(self._on_load_finished)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._view)
        self._stack.addWidget(RetryPanel(origin, self.reload))
        self.setCentralWidget(self._stack)

        if tray_enabled is None:
            tray_enabled = QSystemTrayIcon.isSystemTrayAvailable()
        # Without an icon the tray entry is invisible, and a window hidden into it
        # would leave a running app with no way back.
        if tray_enabled and not self._icon.isNull():
            self._install_tray()

    def listen_for_instances(self, name: str) -> bool:
        """Show this window when a second launch knocks, instead of starting another app."""
        server = QLocalServer(self)
        if not server.listen(name):
            # A crashed run can leave a stale socket file behind on Linux.
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
        self.restore_window()

    def _install_tray(self) -> None:
        icon = self._icon
        menu = QMenu(self)
        open_action = QAction("Open FlexWeek", self)
        open_action.triggered.connect(self.restore_window)
        menu.addAction(open_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("FlexWeek")
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.messageClicked.connect(self._on_notification_clicked)
        tray.show()

        self._tray_menu = menu
        self._tray_icon = tray
        self._profile.setNotificationPresenter(self._present_notification)
        QApplication.setQuitOnLastWindowClosed(False)
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self._shutdown_tray)

    def _present_notification(self, notification: QWebEngineNotification) -> None:
        if self._notification is not None:
            self._close_notification(self._notification)
        self._notification = notification
        notification.closed.connect(lambda: self._forget_notification(notification))
        notification.show()
        timeout_ms = notification_timeout_ms(notification.tag())
        if self._tray_icon is not None and self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                notification.title(),
                notification.message(),
                QSystemTrayIcon.MessageIcon.Information,
                timeout_ms,
            )
        if timeout_ms:
            QTimer.singleShot(
                timeout_ms,
                lambda: self._close_notification(notification),
            )

    def _forget_notification(self, notification: QWebEngineNotification) -> None:
        if self._notification is notification:
            self._notification = None

    def _close_notification(self, notification: QWebEngineNotification) -> None:
        if self._notification is not notification:
            return
        self._notification = None
        # Qt may already have destroyed the C++ side when the page closed it first.
        with contextlib.suppress(RuntimeError):
            notification.close()

    def _on_notification_clicked(self) -> None:
        notification = self._notification
        if notification is not None:
            self._notification = None
            try:
                notification.click()
                notification.close()
            except RuntimeError:
                pass
        self.restore_window()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.restore_window()

    def restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self._quitting = True
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def _shutdown_tray(self) -> None:
        self._quitting = True
        if self._notification is not None:
            self._close_notification(self._notification)
        if self._tray_icon is not None:
            self._tray_icon.hide()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt virtual
        # Closing keeps FlexWeek in the tray so reminders and alarms still fire,
        # but only while the tray icon is actually on screen to bring it back.
        tray = self._tray_icon
        if tray is not None and tray.isVisible() and not self._quitting:
            self.hide()
            event.ignore()
            if not self._tray_hinted:
                self._tray_hinted = True
                tray.showMessage(
                    "FlexWeek is still running",
                    "It stays in the tray so reminders and alarms still work. "
                    "Right-click the tray icon and choose Quit to close it.",
                    QSystemTrayIcon.MessageIcon.Information,
                    TRAY_HINT_MS,
                )
            return
        if tray is not None:
            QApplication.quit()
        super().closeEvent(event)

    def _save_download(self, download: QWebEngineDownloadRequest) -> None:
        name = Path(download.suggestedFileName()).name or "flexweek.json"
        destination, _ = QFileDialog.getSaveFileName(self, "Save FlexWeek download", name)
        if not destination:
            download.cancel()
            return
        target = Path(destination)
        download.setDownloadDirectory(str(target.parent))
        download.setDownloadFileName(target.name)
        download.accept()

    def load_app(self) -> None:
        self._stack.setCurrentIndex(0)
        self._view.load(QUrl(self._origin))

    def reload(self) -> None:
        self.load_app()

    def _on_load_finished(self, ok: bool) -> None:
        if self._page.sent_to_browser:
            # A blocked external link also reports failure; the window is fine.
            self._page.clear_external_flag()
            return
        self._stack.setCurrentIndex(0 if ok else 1)


def smoke_report_path(argv: list[str]) -> Path | None:
    """Where `--smoke-test PATH` asks for a startup report, or None for a normal launch."""
    if SMOKE_FLAG not in argv:
        return None
    index = argv.index(SMOKE_FLAG)
    if index + 1 >= len(argv):
        raise SystemExit(f"{SMOKE_FLAG} needs a file path for the report")
    return Path(argv[index + 1])


class SmokeTest:
    """Proves a packaged build starts on a fresh machine, then quits.

    Passes once the window is visible and the page has run far enough to show
    the Create account status line. A crashed renderer or a timeout fails it.
    Release checks run this on fresh Linux containers and the Windows runner.
    """

    def __init__(self, window: MainWindow, report: Path, sandbox_reason: str | None) -> None:
        self._window = window
        self._report = report
        self._facts: dict[str, object] = {
            "sandbox_disabled_by": sandbox_reason,
            "qt_platform": QApplication.platformName(),
        }
        self._done = False
        self._poll = QTimer(window)
        self._poll.setInterval(SMOKE_POLL_MS)
        self._poll.timeout.connect(self._check)
        window._view.loadFinished.connect(self._on_load)
        window._page.renderProcessTerminated.connect(self._on_renderer_gone)
        QTimer.singleShot(SMOKE_TIMEOUT_MS, lambda: self._finish(False, "timed out before the first screen"))

    def _on_load(self, ok: bool) -> None:
        if not ok:
            self._finish(False, "page failed to load")
            return
        self._poll.start()

    def _on_renderer_gone(self, status: object, exit_code: int) -> None:
        self._finish(False, f"renderer stopped ({status}, exit {exit_code})")

    def _check(self) -> None:
        self._window._page.runJavaScript(SMOKE_READY_JS, self._on_ready)

    def _on_ready(self, ready: object) -> None:
        if ready and self._window.isVisible():
            self._finish(True, "first screen shown")

    def _finish(self, ok: bool, stage: str) -> None:
        if self._done:
            return
        self._done = True
        self._poll.stop()
        window = self._window
        self._facts.update({
            "ok": ok,
            "stage": stage,
            "window_visible": window.isVisible(),
            "window_icon_loaded": not window._icon.isNull(),
            "tray_icon_installed": window._tray_icon is not None,
        })
        self._report.write_text(json.dumps(self._facts, indent=2) + "\n")
        window.quit_app()
        application = QApplication.instance()
        if application is not None:
            application.exit(0 if ok else 1)


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv)
    report = smoke_report_path(arguments)
    # Chromium reads this while QApplication starts, so it has to be decided first.
    sandbox_reason = disable_sandbox_if_blocked(os.environ)
    if sandbox_reason is not None:
        print(f"FlexWeek: Chromium sandbox unavailable ({sandbox_reason}); running without it.",
              file=sys.stderr)
    app = QApplication(arguments)
    # Application name drives profile_root(); set it before any profile exists.
    app.setApplicationName("FlexWeek")
    # Matches flexweek.desktop, so Linux docks show the FlexWeek icon for this window.
    app.setDesktopFileName(DESKTOP_FILE_NAME)

    try:
        origin = configured_origin()
    except ValueError as error:
        QMessageBox.critical(None, "FlexWeek configuration", str(error))
        return 2

    instance = instance_name(profile_root())
    if show_running_instance(instance):
        return 0

    if origin is None:
        # No hosted server named, so run our own. The database lives beside the
        # browser profile, not inside the read-only application bundle.
        database = Path(profile_root()) / "flexweek.db"
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
            server = LocalServer(database)
            origin = server.start()
        except (OSError, RuntimeError, TimeoutError) as error:
            QMessageBox.critical(None, "FlexWeek", f"Could not start FlexWeek: {error}")
            return 3
        app.aboutToQuit.connect(server.stop)

    window = MainWindow(origin)
    window.listen_for_instances(instance)
    smoke = SmokeTest(window, report, sandbox_reason) if report is not None else None
    window.show()
    window.load_app()
    status = app.exec()
    del smoke
    return status


if __name__ == "__main__":
    raise SystemExit(main())
