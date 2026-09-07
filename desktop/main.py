"""FlexWeek desktop shell: one Qt WebEngine window pointed at the hosted app.

Deliberately thin. The page keeps its own login, CSRF headers and cookies, so
there is no WebChannel, no injected js_api and no cookie access from native
code. See DESKTOP.md.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.origin import is_same_origin, resolve_origin

WINDOW_SIZE = (1280, 800)
PROFILE_NAME = "flexweek"


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
        # createWindow returns short-lived pages; holding them stops Qt freeing them mid-signal.
        self._popups: list[QWebEnginePage] = []

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
            QDesktopServices.openUrl(target)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, _window_type: QWebEnginePage.WebWindowType) -> QWebEnginePage:  # noqa: N802
        """target=_blank and window.open: open in the OS browser, not a second Qt window."""
        popup = QWebEnginePage(self.profile(), self)
        self._popups.append(popup)

        def open_externally(url: QUrl) -> None:
            QDesktopServices.openUrl(url)
            if popup in self._popups:
                self._popups.remove(popup)

        popup.urlChanged.connect(open_externally)
        return popup


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
    def __init__(self, origin: str) -> None:
        super().__init__()
        self._origin = origin
        self.setWindowTitle("FlexWeek")
        self.resize(*WINDOW_SIZE)

        root = profile_root()
        # Named profile + explicit paths: the session cookie survives a restart.
        # Parented to the application, not this window: Qt warns and can crash if
        # the profile is released while a page using it is still alive.
        self._profile = QWebEngineProfile(PROFILE_NAME, QApplication.instance())
        self._profile.setPersistentStoragePath(f"{root}/profile")
        self._profile.setCachePath(f"{root}/cache")
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
        origin = resolve_origin()
    except ValueError as error:
        QMessageBox.critical(None, "FlexWeek configuration", str(error))
        return 2
    window = MainWindow(origin)
    window.show()
    window.load_app()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
