"""FlexWeek desktop app: native Qt over the Rust service, in this process.

`python -m desktop.main` starts the window, not Chromium. Requests are answered
by the service on worker threads, with no server and no network port;
`--database` names the saved data to open instead of the profile's own.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def report_missing_part(error: ImportError) -> None:
    # Qt may be the part that failed, so this uses only the standard library and, on Windows,
    # the system message box. The Windows build runs without a console, so stderr alone is not seen.
    message = f"FlexWeek could not start because a part it needs did not load:\n{error}"
    if sys.platform.startswith("linux"):
        message += "\nThe Linux libraries section of the README lists what it needs."
    print(message, file=sys.stderr)
    if sys.platform == "win32":
        mb_iconerror = 0x10
        ctypes.windll.user32.MessageBoxW(None, message, "FlexWeek", mb_iconerror)


MCP_FLAG = "--mcp"


def run_mcp_helper() -> None:
    # --mcp starts the assistant helper instead of the window, so it is handled
    # before the Qt imports: the helper speaks on stdin and stdout and needs
    # neither a display nor the window's libraries. The helper is the sibling of
    # this program in the Linux package; Windows does not ship it. Only a
    # first-argument --mcp dispatches, the way the package launchers treat it,
    # and the arguments after it go to the helper unchanged.
    helper = Path(sys.argv[0]).resolve().with_name("flexweek-mcp")
    if not helper.is_file():
        print(
            f"FlexWeek {MCP_FLAG}: the assistant helper is not next to {sys.argv[0]}."
            " It ships with the Linux download; Windows does not include it.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    args = [str(helper), *sys.argv[2:]]
    os.execv(helper, args)


if len(sys.argv) > 1 and sys.argv[1] == MCP_FLAG:
    run_mcp_helper()

try:
    from PySide6.QtCore import QStandardPaths, QTimer
    from PySide6.QtGui import QIcon, QImage
    from PySide6.QtNetwork import QLocalSocket
    from PySide6.QtWidgets import QApplication, QMessageBox

    import backend
    from backend.storage import initialize
    from desktop.native.calendar import sunday_due
    from desktop.native.client import stop_workers
    from desktop.native.collector import WindowThreadCollector
    from desktop.native.cpu_drawing import apply_saved as apply_saved_cpu_drawing
    from desktop.native.devices import SyncHost
    from desktop.native.fonts import load_fonts
    from desktop.native.kept import KeptSession
    from desktop.native.listening import listening_sockets
    from desktop.native.updater import collect_stale_downloads
    from desktop.native.version import VERSION
    from desktop.native.window import NativeWindow
except ImportError as error:
    report_missing_part(error)
    raise SystemExit(1) from error

INSTANCE_WAIT_MS = 500
SMOKE_FLAG = "--smoke-test"
SMOKE_TIMEOUT_MS = 90_000
SMOKE_POLL_MS = 250
SMOKE_PASSED = "week shown after setup Solve"
PAINTED_MIN_COLORS = 8
DESKTOP_FILE_NAME = "flexweek"


def app_icon_path() -> Path:
    return Path(backend.__file__).resolve().parents[1] / "desktop" / "assets" / "logo.png"


def instance_name(root: str) -> str:
    return "flexweek-" + hashlib.sha256(root.encode()).hexdigest()[:16]


def show_running_instance(name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(INSTANCE_WAIT_MS):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(INSTANCE_WAIT_MS)
    socket.disconnectFromServer()
    return True


def profile_root() -> str:
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)


def parse_database(argv: list[str]) -> tuple[list[str], Path | None]:
    filtered = [argv[0]]
    database: Path | None = None
    index = 1
    while index < len(argv):
        if argv[index] == "--database" and index + 1 < len(argv):
            database = Path(argv[index + 1])
            index += 2
            continue
        filtered.append(argv[index])
        index += 1
    return filtered, database


def smoke_report_path(argv: list[str]) -> Path | None:
    if SMOKE_FLAG not in argv:
        return None
    index = argv.index(SMOKE_FLAG)
    if index + 1 >= len(argv):
        raise SystemExit(f"{SMOKE_FLAG} needs a file path for the report")
    return Path(argv[index + 1])


def painted_colors(image: QImage, step: int = 8) -> int:
    colors = set()
    for y in range(0, image.height(), step):
        for x in range(0, image.width(), step):
            colors.add(image.pixel(x, y))
    return len(colors)


def material_state(window: NativeWindow) -> tuple[str, int]:
    """Whether Material's Qt Quick window, not the draw-error page, is the one on screen.

    "fallback" means this build gave up on Material; "waiting" means the window is not visible, not built
    or not drawn yet. "shown" needs the window visible, its shell built, and what `grabWindow` drew to
    hold PAINTED_MIN_COLORS colours.
    """
    if window._material_gave_up:
        return "fallback", 0
    page = window._material_current()
    if page is None or not page._ready or page.root is None or not page.isVisible():
        return "waiting", 0
    colors = painted_colors(page.grabWindow())
    return ("shown" if colors >= PAINTED_MIN_COLORS else "waiting"), colors


class NativeSmoke:
    """Registers a throwaway account, places a week, and writes a startup report."""

    def __init__(self, window: NativeWindow, report: Path) -> None:
        self._window = window
        self._report = report
        self._done = False
        self._stage = "first screen"
        self._material_ok = False
        self._material_colors = 0
        self._verdict: tuple[bool, str] | None = None
        self._poll = QTimer(window)
        self._poll.setInterval(SMOKE_POLL_MS)
        self._poll.timeout.connect(self._check)
        QTimer.singleShot(SMOKE_TIMEOUT_MS, self._time_out)
        QTimer.singleShot(0, self._poll.start)

    def _time_out(self) -> None:
        self._finish(False, f"timed out waiting for {self._stage}")

    def _check(self) -> None:
        if self._done:
            return
        window = self._window
        if not window.isVisible():
            return
        face = window._face()
        page = face.objectName() if face is not None else ""
        bridge = window._account_bridge()
        phase = bridge.phase if bridge is not None else ""
        if self._stage == "first screen":
            if page != "materialPage" or phase != "sign-in":
                return
            username = "smoke_" + secrets.token_hex(6)
            password = secrets.token_urlsafe(18)
            bridge.showCreate()
            bridge.setUsername(username)
            bridge.setPassword(password)
            bridge.submit()
            self._stage = "recovery codes"
            return
        if self._stage == "recovery codes":
            if phase != "recovery" or len(bridge.codes) != 8:
                return
            bridge.setRecoveryAck(True)
            if not bridge.recoveryReady:
                return
            bridge.finishRecovery()
            self._stage = "setup"
            return
        if self._stage == "setup":
            # Every page of setup is skipped at once; the pages themselves are drawn by the tests.
            if phase == "setup":
                bridge.setupSkipAll()
                return
            if phase == "app":
                self._stage = "week"
            return
        if self._stage == "week":
            if phase != "app" or window.session.account is None or window.session.busy:
                return
            if window._setup_prefs or window._setup_week:
                return
            session = window.session
            session.add_block(
                {
                    "id": "soccer",
                    "title": "Soccer",
                    "kind": "locked",
                    "duration_min": 60,
                    "days": [0],
                    "start": "16:00",
                    "category": "exercise",
                }
            )
            session.add_homework(
                {
                    "id": "math",
                    "title": "Math worksheet",
                    "due": sunday_due(session.week_start),
                    "estimate_min": 60,
                    "revision": 0,
                }
            )
            session.save()
            self._stage = "saved week"
            return
        if self._stage == "saved week":
            session = window.session
            # A week that starts on another day than Monday spans two stored weeks, one revision each; the
            # save bumps the one that holds the new blocks.
            revision = session.revision
            saved = max(revision) if isinstance(revision, list) else revision
            if session.busy or saved < 1:
                return
            if not any(block.get("id") == "soccer" for block in session.blocks):
                self._finish(False, "window blank after setup Solve")
                return
            self._facts_colors = painted_colors(window.grab().toImage())
            # The release must show the Material window itself, not the draw-error page.
            self._stage = "material window"
            return
        if self._stage == "material window":
            state, colors = material_state(window)
            if state == "waiting":
                return
            self._material_colors = colors
            if state == "fallback":
                self._verdict = (False, "Material 3 did not open: the draw-error page is showing")
            else:
                self._material_ok = True
                self._verdict = (True, SMOKE_PASSED)
            self._finish(*self._verdict)

    def _finish(self, ok: bool, stage: str) -> None:
        if self._done:
            return
        self._done = True
        self._poll.stop()
        window = self._window
        facts = {
            "ok": ok and self._material_ok,
            "stage": stage,
            "window_visible": window.isVisible(),
            "window_icon_loaded": not window.windowIcon().isNull(),
            "tray_icon_installed": window._tray_icon is not None,
            "block_count": len(window.session.blocks),
            "painted_colors": getattr(self, "_facts_colors", 0),
            "material_ok": self._material_ok,
            "material_painted_colors": self._material_colors,
            "message": window.session.message,
            # With no phone paired the app listens on nothing (None: not readable on this system).
            "listening": listening_sockets(),
        }
        self._report.write_text(json.dumps(facts, indent=2) + "\n")
        window.quit_app()
        application = QApplication.instance()
        if application is not None:
            application.exit(0 if facts["ok"] else 1)


def main(argv: list[str] | None = None) -> int:
    arguments, database_arg = parse_database(list(argv if argv is not None else sys.argv))
    report = smoke_report_path(arguments)
    app = QApplication(arguments)
    collector = WindowThreadCollector(app)  # noqa: F841 - the app keeps it as a child
    app.setApplicationName("FlexWeek")
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    if report is None:
        # Qt Quick reads its backend when the first Material window is made, so this is early enough.
        apply_saved_cpu_drawing(Path(profile_root()) / "flexweek-look.json", VERSION)
    load_fonts()
    collect_stale_downloads()

    root = tempfile.mkdtemp(prefix="flexweek-smoke-") if report is not None else profile_root()
    instance = instance_name(str(database_arg) if database_arg is not None else root)
    if report is None and show_running_instance(instance):
        return 0

    database = database_arg if database_arg is not None else Path(root) / "flexweek.db"
    try:
        database.parent.mkdir(parents=True, exist_ok=True)
        initialize(database)
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as error:
        if report is not None:
            # A smoke run is read by CI from its report; a dialog there says nothing to anyone.
            stage = f"saved data did not open: {error}"
            payload = {"ok": False, "stage": stage, "window_visible": False}
            report.write_text(json.dumps(payload) + "\n")
            shutil.rmtree(root, ignore_errors=True)
            return 3
        QMessageBox.critical(None, "FlexWeek", f"Could not start FlexWeek: {error}")
        return 3
    sync = SyncHost(database)
    app.aboutToQuit.connect(sync.stop)
    sync.start_if_paired()

    # Keep me signed in is per database, like the running-instance check.
    kept = KeptSession(Path(root) / "signed-in" / f"{instance}.json")
    window = NativeWindow(database, icon=QIcon(str(app_icon_path())), kept=kept, sync=sync)
    if report is None:
        window.listen_for_instances(instance)
    smoke = NativeSmoke(window, report) if report is not None else None
    window.show()
    status = app.exec()
    del smoke
    # Answers still being made finish before the smoke run's folder is removed or the process ends.
    stop_workers()
    if report is not None:
        shutil.rmtree(root, ignore_errors=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
