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
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
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

from desktop.origin import configured_origin, is_same_origin
from desktop.server import LocalServer

WINDOW_SIZE = (1280, 800)
PROFILE_NAME = "flexweek"
NOTIFICATION_TIMEOUT_MS = 10_000
NOTIFY_STAY_TAG = "flexweek-stay"


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
        self.setWindowTitle("FlexWeek")
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
        if tray_enabled:
            self._install_tray()

    def _install_tray(self) -> None:
        icon = QIcon(str(Path(__file__).resolve().parents[1] / "frontend" / "logo.png"))
        self.setWindowIcon(icon)

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
        if self._tray_icon is not None and not self._quitting:
            self.hide()
            event.ignore()
            return
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


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    # Application name drives profile_root(); set it before any profile exists.
    app.setApplicationName("FlexWeek")

    try:
        origin = configured_origin()
    except ValueError as error:
        QMessageBox.critical(None, "FlexWeek configuration", str(error))
        return 2

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
    window.show()
    window.load_app()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
