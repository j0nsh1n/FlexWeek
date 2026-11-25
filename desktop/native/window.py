"""Qt widgets window for the native FlexWeek desktop client."""

from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from flexweek_engine import SyncService  # type: ignore[import-untyped]
from PySide6.QtCore import (
    QEvent,
    QEventLoop,
    QObject,
    QPoint,
    QRect,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QKeyEvent,
    QPixmap,
)
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from backend import clock as wall_clock
from backend.slots import minutes_to_hhmm
from desktop.native import autostart, cpu_drawing
from desktop.native.account_copy import (
    ACCOUNT_SAVED,
    RECOVERY_FILE,
    RECOVERY_KEEP,
    WRITE_FAILED,
)
from desktop.native.ambient import FocusAudio
from desktop.native.calendar import (
    this_week_line,
)
from desktop.native.controller import ROUTINE_STATUS, NativeSession, left_sentence
from desktop.native.custom_look import sanitize_saved
from desktop.native.devices import SyncHost, live_phones, run_off_ui
from desktop.native.fields import announce, week_start_day, week_start_notice
from desktop.native.fonts import load_fonts
from desktop.native.hours.scale import sanitize_zoom
from desktop.native.kept import KeptSession
from desktop.native.kept_alerts import KeptAlerts
from desktop.native.layout_choice import sanitize_layout, sanitize_surface
from desktop.native.look import effective_look, look_motion, sanitize_look
from desktop.native.material.sheet_preview import PreviewDraft
from desktop.native.material.theme import kept_material
from desktop.native.motion import apply_ui_effects
from desktop.native.motion_level import motion_level
from desktop.native.outside import OutsideWatch, differs
from desktop.native.remind import REMINDER_POLL_MS, clock_parts
from desktop.native.settings import AlarmRingDialog
from desktop.native.setup_steps import REMINDERS, SETUP_VERSION, STYLE, SetupState
from desktop.native.sound import Bell
from desktop.native.spotify import LISTENING, STARTING, SpotifyPlayer, open_in_app
from desktop.native.tones import FALLBACK
from desktop.native.update import (
    RELEASE_PAGE,
    due_for_check,
    sanitize_updates,
)
from desktop.native.updater import Updater, apply_update
from desktop.native.version import VERSION
from desktop.native.weekmodel import (
    set_clock_24h,
)
from desktop.native.widgets import (
    overdue_unfinished,
    steady_wheel,
    use_app_style,
)

WINDOW_SIZE = (1280, 800)
# The smallest window FlexWeek is for: at 800 the top bar still fits and nothing is cut in half.
WINDOW_MIN_WIDTH = 800
# How often the window looks for another program's change to its database: one small file read each
# time, and a look inside only after a commit.
OUTSIDE_CHECK_MS = 2000




SIGN_OUT_QUESTION = "Your week is saved on {where}, under this account. Sign in again to see it."
RECOVERY_CHOOSE = "Choose where to save"
# The pages Material 3 answers for, as its own screens.
MATERIAL_ACCOUNT_PAGES = ("authPage", "recoveryPage", "setupPage")
# Pages that the draw-error page stands in for when Material cannot be drawn at all.
DRAW_ERROR_COVERS = MATERIAL_ACCOUNT_PAGES
# Long enough for the student to read that the update installed before the window goes.
UPDATE_QUIT_MS = 1200
# How often the window asks the session whether the week should save itself (the waits are in
# engine/app/src/session/autosave.rs).
AUTOSAVE_TICK_MS = 500
LAYOUT_TICK_MS = 20_000
# Leaving the app waits this long, checking this often, for what is unsaved to reach the server.
LEAVE_WAIT_MS = 5000
LEAVE_POLL_MS = 100
# Homework named on a Find a new time notice before the rest is counted.
NOTICE_LINES = 3






class NativeWindow(QObject):
    """The controller. Material's own Qt Quick window (`_material_page`) is what the student sees; this
    object owns it, answers for it (show, hide, close, size) and keeps what the app does around it.
    The draw-error page is a separate small window until it gets its own page."""

    def __init__(
        self,
        database: str | Path,
        icon: QIcon | None = None,
        parent: QObject | None = None,
        kept: KeptSession | None = None,
        sync: SyncHost | None = None,
    ) -> None:
        super().__init__(parent)
        application = QApplication.instance()
        if isinstance(application, QApplication):
            steady_wheel(application)
            use_app_style(application)
            # Hiding Material's window to the tray must not end the app: this controller decides when it
            # quits (quit_app, a real close), never Qt's "last window closed".
            application.setQuitOnLastWindowClosed(False)
        # Where the window is, until the Material window exists to hold it.
        self._title = "FlexWeek"
        self._size = QSize(*WINDOW_SIZE)
        self._min_width = WINDOW_MIN_WIDTH
        # show() has been asked for and hide() has not; the faces below follow it.
        self._shown = False
        # The plain draw-error window, made when Material cannot be drawn at all.
        self._draw_error_window: QWidget | None = None
        self._on_error_face = False
        self._shut_down = False
        # main() has loaded them already; a window made anywhere else, as in the tests, is drawn alike.
        load_fonts()
        self.session = NativeSession(database, self, kept)
        self.session.use_sync_host(sync)
        # The week's first day is kept on this computer, not on the account; the session is told it.
        self.session.follow_first_weekday(week_start_day())
        week_start_notice().changed.connect(self._on_week_start)
        self._instance_server: QLocalServer | None = None
        # This computer's sync host, and the running service once it has started (None until then). The
        # generation is the one the week was last loaded at; a change in it means a linked phone's edits
        # arrived. The phone list is read off this thread, so it lags the service by up to a second.
        self._sync_host = sync
        self._sync = sync.service if sync is not None else None
        self._sync_generation = self._sync.generation() if self._sync is not None else None
        self._phones: list[dict] = []
        self._phones_user: int | None = None
        self._phones_reading = False
        if sync is not None:
            # The window owns its host, so Qt, not the garbage collector, frees it with the window.
            sync.setParent(self)
            sync.started.connect(self._sync_started)
        # Another program's changes to this database, such as the assistant's, shown without a restart.
        self._outside: OutsideWatch | None = None
        self._outside_timer = QTimer(self)
        self._outside_timer.setInterval(OUTSIDE_CHECK_MS)
        self._outside_timer.timeout.connect(self._outside_tick)
        if sync is not None:
            self.watch_database(sync.database)
        # The Animations level, set from the look in _apply_appearance.
        self._motion = "normal"
        # What the window was last dressed in, so a change that leaves the look alone skips restyling.
        self._dressed: tuple = ()
        self._layout = sanitize_layout(None)
        self._rail_month = True
        # Material 3 is the only style. The QML page is built the first time it is shown.
        self._surface = sanitize_surface(None)
        self._material_page = None
        self._account_showing = False
        self._material_gave_up = False
        # The app version that must draw Material on the CPU, or "" when the graphics card may be used.
        self._cpu_drawing_version = ""
        self._relaunching = False
        self._updates = sanitize_updates(None)
        self._zoom: dict[str, int] = {}
        # The student's own looks, kept by name (custom_look.py); Settings will list them.
        self._saved_looks: list[dict] = []
        self._new_look_notice_seen: set[str] = set()
        self._new_look_notice_exempt: set[str] = set()
        self._update_asked = False
        self._update_on_material = False
        # An update found while Material is not on screen. The draw-error page offers it, since an update
        # may be what fixes the drawing.
        self._draw_error_update: dict | None = None
        self._updater = Updater(self)
        self._updater.found.connect(self._on_update_found)
        self._updater.none_found.connect(self._no_update)
        self._updater.unreachable.connect(self._update_unreachable)
        # Connected once here, not per dialog: a second check would otherwise wire them again and
        # every later signal would arrive as many times as the dialog had been opened.
        self._updater.progress.connect(self._on_update_progress)
        self._updater.failed.connect(self._on_update_problem)
        self._updater.ready.connect(self._on_update_ready)
        # Setup is on screen, and this sign-in has decided whether it should be. What setup has kept
        # to write lives on the session.
        self._setup_active = False
        self._setup_checked = False
        self._leaving: QTimer | None = None
        self._saved_to_leave = False
        # What a drag changed, said with Undo once its save lands: the words for the save on its way,
        # and words waiting for the pointer to let go, since nothing new appears under a held block.
        self._change_saving: str | None = None
        self._change_saved: str | None = None
        # The Undo step the toast offers to take back.
        self._notice_step: dict | None = None
        # Something asked for is under way; the next thing the session says is what it did.
        self._telling = False
        # The last reminder the toast said, so Got it on the same reminder takes it away.
        self._reminder_said = ""
        self._autosave = QTimer(self)
        self._autosave.setInterval(AUTOSAVE_TICK_MS)
        self._autosave.timeout.connect(self._autosave_tick)
        self._autosave.start()
        self.alert_strip = KeptAlerts(self)
        self.alert_strip.handled.connect(self._reminder_handled)
        # Once a second: the phones' sync state, and the week reloaded when a linked phone's edits arrive.
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(1000)
        self._sync_timer.timeout.connect(self._sync_tick)
        if self._sync is not None:
            self._sync_timer.start()
        self._build_focus_audio()
        self.session.account_changed.connect(self._on_account)
        self.session.recovery_codes.connect(self._show_recovery)
        self.session.week_changed.connect(self._on_week)
        self.session.status.connect(self._on_status)
        self.session.busy_changed.connect(self._on_busy)
        self.session.save_finished.connect(self._on_save_finished)
        self.session.hand_placed.connect(self._say_when_saved)
        self.session.repeats_kept.connect(self._say_repeats_kept)
        self.session.plan_conflicts.connect(self._on_plan_conflicts)
        self.session.planned.connect(self._on_planned)
        self._quitting = False
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._tray_hinted = False
        self._icon = icon or QIcon()
        self._alarm_dialog: AlarmRingDialog | None = None
        # An alarm is ringing on Material's own screen, not in the Widgets dialog.
        self._alarm_on_material = False
        self._bell = Bell(self)
        # A Spotify alarm plays in the student's Spotify app. Until it is heard the tone rings, so an
        # alarm is never silent, and once it is the tone stops.
        self._spotify = SpotifyPlayer(self)
        self._spotify.late.connect(self._spotify_late)
        self._spotify.heard.connect(self._spotify_heard)
        self._look = sanitize_look(None)
        # Read once, and again at sign-out: signing in writes the file, which must not change the card
        # the student is still looking at.
        self._carried = self._read_carried()
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
        self._layout_tick = QTimer(self)
        self._layout_tick.setInterval(LAYOUT_TICK_MS)
        self._layout_tick.timeout.connect(self._tick_material_clock)
        self._layout_tick.start()
        self._deadline_tick = QTimer(self)
        self._deadline_tick.setSingleShot(True)
        self._deadline_tick.timeout.connect(self._deadline_changed)
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._application_state_changed)
        self._apply_appearance()
        if QSystemTrayIcon.isSystemTrayAvailable() and not self._icon.isNull():
            self._install_tray()
        self._show_page("authPage")
        # After the window exists, so a kept session opens the week the ordinary way.
        QTimer.singleShot(0, self.session.resume)

    # The window the student sees. Material's own Qt Quick window is the face, except while the draw-error
    # page stands in for it; these pass what the app and the tests ask of a window to whichever is current.

    def _face(self):
        """Material's window, or the draw-error window while that one stands in for it; None before either."""
        if self._on_error_face and self._draw_error_window is not None:
            return self._draw_error_window
        return self._material_page

    def _faces(self) -> list:
        return [face for face in (self._material_page, self._draw_error_window) if face is not None]

    def _material_current(self):
        """Material's window while it is the face, else None. The one question every caller asks."""
        return None if self._on_error_face else self._material_page

    def _sync_faces(self) -> None:
        """Show the current face when the window is open, and nothing else."""
        current = self._face()
        for face in self._faces():
            want = self._shown and face is current
            if face.isVisible() != want:
                face.setVisible(want)

    def show(self) -> None:
        self._shown = True
        self._sync_faces()

    def hide(self) -> None:
        self._shown = False
        self._sync_faces()

    def showNormal(self) -> None:  # noqa: N802 - the name the widget window had
        self._shown = True
        self._sync_faces()
        face = self._face()
        if face is not None:
            face.showNormal()

    def showMinimized(self) -> None:  # noqa: N802
        self._shown = True
        face = self._face()
        if face is not None:
            face.showMinimized()

    def raise_(self) -> None:
        face = self._face()
        if face is not None:
            face.raise_()

    def activateWindow(self) -> None:  # noqa: N802
        face = self._face()
        if isinstance(face, QWidget):
            face.activateWindow()
        elif face is not None:
            face.requestActivate()

    def isVisible(self) -> bool:  # noqa: N802
        return any(face.isVisible() for face in self._faces())

    def isActiveWindow(self) -> bool:  # noqa: N802
        face = self._face()
        if isinstance(face, QWidget):
            return face.isActiveWindow()
        return face is not None and face.isActive()

    def isMinimized(self) -> bool:  # noqa: N802
        face = self._face()
        if isinstance(face, QWidget):
            return face.isMinimized()
        return face is not None and bool(face.windowStates() & Qt.WindowState.WindowMinimized)

    def resize(self, width: int, height: int) -> None:
        # A widget window never went below its smallest size; a Qt Quick window only hints it to the window
        # manager, and not every platform keeps to the hint.
        self._size = QSize(max(width, self._min_width), max(height, self.minimumHeight()))
        for face in self._faces():
            face.resize(self._size)

    def size(self) -> QSize:
        face = self._face()
        return self._size if face is None else face.size()

    def width(self) -> int:
        return self.size().width()

    def height(self) -> int:
        return self.size().height()

    def geometry(self) -> QRect:
        face = self._face()
        return QRect(0, 0, self._size.width(), self._size.height()) if face is None else face.geometry()

    def move(self, x: int, y: int) -> None:
        for face in self._faces():
            if isinstance(face, QWidget):
                face.move(x, y)
            else:
                face.setPosition(x, y)

    def setMinimumWidth(self, width: int) -> None:  # noqa: N802
        self._min_width = width
        if self._material_page is not None:
            self._material_page.setMinimumWidth(width)

    def minimumWidth(self) -> int:  # noqa: N802
        return self._min_width

    def minimumHeight(self) -> int:  # noqa: N802
        page = self._material_page
        return 0 if page is None else page.minimumHeight()

    def setMinimumHeight(self, height: int) -> None:  # noqa: N802
        if self._material_page is not None:
            self._material_page.setMinimumHeight(height)

    def mapToGlobal(self, point: QPoint) -> QPoint:  # noqa: N802
        face = self._face()
        return point if face is None else face.mapToGlobal(point)

    def mapFromGlobal(self, point: QPoint) -> QPoint:  # noqa: N802
        face = self._face()
        return point if face is None else face.mapFromGlobal(point)

    def setMinimumSize(self, width: int, height: int) -> None:  # noqa: N802
        self._min_width = width
        if self._material_page is not None:
            self._material_page.setMinimumSize(QSize(width, height))

    def windowHandle(self):  # noqa: N802
        """Material's window: what a key or a mouse event is sent to."""
        return self._material_page

    def windowTitle(self) -> str:  # noqa: N802
        return self._title

    def windowIcon(self) -> QIcon:  # noqa: N802
        return self._icon

    def grab(self) -> QPixmap:
        face = self._face()
        if isinstance(face, QWidget):
            return face.grab()
        return QPixmap() if face is None else QPixmap.fromImage(face.grabWindow())

    def close(self) -> bool:
        """What the window's close button does, from the code: hide to the tray, or save and quit."""
        event = QCloseEvent()
        self._on_close(event)
        if event.isAccepted():
            for face in self._faces():
                face.hide()
        return event.isAccepted()

    def _dress_view(self, page) -> None:
        """Title, icon, smallest width and the starting size, which Material's window holds."""
        page.setTitle(self._title)
        page.setIcon(self._icon)
        page.setMinimumWidth(self._min_width)
        page.resize(self._size)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt virtual
        kind = event.type()
        if kind == QEvent.Type.Close and watched in self._faces() and isinstance(event, QCloseEvent):
            self._on_close(event)
            return not event.isAccepted()
        if kind == QEvent.Type.KeyPress and watched is self._material_page and isinstance(event, QKeyEvent):
            return self._on_key(event)
        return False

    def _autosave_tick(self) -> None:
        """Save the week without being asked, when the session says it is time (autosave.rs: after the
        student stops changing things, never while a request is in flight or after a 409, and a failed save
        again every few seconds)."""
        session = self.session
        due = session.client.command(
            {
                "cmd": "autosave",
                "signed_in": session.account is not None,
                "conflict": bool(session.conflict),
                "dirty": bool(session.dirty),
                "pending": session.pending_save is not None,
            }
        )["save"]
        if due:
            session.save()

    # When the last change was made and when a save was last tried, on the session's steady clock.
    @property
    def _changed_ms(self) -> int:
        return int(self.session.client.view("autosave")["changed_ms"])

    @_changed_ms.setter
    def _changed_ms(self, value: int) -> None:
        self.session.client.command({"cmd": "autosave_times", "changed_ms": int(value)})

    @property
    def _last_try_ms(self) -> int:
        return int(self.session.client.view("autosave")["last_try_ms"])

    @_last_try_ms.setter
    def _last_try_ms(self, value: int) -> None:
        self.session.client.command({"cmd": "autosave_times", "last_try_ms": int(value)})

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
        if self._material_gave_up and name in DRAW_ERROR_COVERS:
            self._show_draw_error()
            return
        # Sign-in, recovery and setup are Material's screens.
        if self._material_account_page(name):
            return
        if name == "materialPage" and self._material_page is not None:
            self._on_error_face = False
            self._sync_faces()

    def _account_bridge(self):
        """The Material sign-in and setup bridge, or None before Material has been built."""
        page = self._material_page
        return None if page is None else page.bridge.account

    def _material_account_page(self, name: str, codes: list | None = None) -> bool:
        """Show sign-in, the recovery codes or setup as Material screens. True when they are on screen.

        False when this version gave up on Material or it could not load: the error page or a new copy
        drawing on the CPU takes over. A page that is not an account page takes Material back to the week.
        """
        bridge = self._account_bridge()
        if name not in MATERIAL_ACCOUNT_PAGES:
            if bridge is not None and bridge.phase != "app" and not self._account_showing:
                bridge.show_app()
            return False
        if self._material_gave_up:
            return False
        page = self._ensure_material(quiet=True)
        if page is None:
            return False
        bridge = page.bridge.account
        if name == "authPage":
            bridge.show_sign_in(clear=True)
        elif name == "recoveryPage":
            bridge.show_recovery(codes or [])
        self._account_showing = True
        try:
            self._show_page("materialPage")
            try:
                loaded = page.load()
                if loaded:
                    page.publish()
                    page.requestActivate()
            except Exception as error:
                logging.getLogger("flexweek.material").warning("Material 3 could not load: %s", error)
                loaded = False
        finally:
            self._account_showing = False
        if not loaded:
            self._give_up_material(show_week=False)
            self._drop_partial_material()
            return False
        return True

    def _material_owns(self) -> bool:
        """Material is the saved surface and this version has not given up on it.

        Focus can cover it. It does not hand the window to the Widgets week.
        """
        return self._surface == "material" and not self._setup_active and not self._material_gave_up

    def _cover_holds(self) -> bool:
        """Setup is the page the student is looking at."""
        return self._setup_active

    def _show_surface(self) -> bool:
        """Show the surface that owns the window. True when Material is on screen."""
        if self._material_owns():
            return self._present_material()
        if self._material_gave_up:
            self._show_draw_error()
        return False

    def _ensure_material(self, *, quiet: bool = False):
        """The Material page, or None when it cannot be built. `quiet`: there is no week to fall back to."""
        if self._material_page is not None:
            return self._material_page
        try:
            from desktop.native.material.host import MaterialPage

            page = MaterialPage(self)
        except Exception as error:
            logging.getLogger("flexweek.material").warning("Material 3 could not be built: %s", error)
            self._drop_partial_material()
            self._give_up_material(show_week=not quiet)
            return None
        page.failed.connect(self._on_material_failed)
        page.installEventFilter(self)
        self._dress_view(page)
        self._material_page = page
        # Material's focus rules (hold reminders, finish the block) ask whether Material is in use.
        self.session.material_owns = self._material_owns
        return page

    def _drop_partial_material(self) -> None:
        """A failed build must not leave a half-made window or its bridges behind."""
        self._stop_material_ring()
        page = self._material_page
        self._material_page = None
        doomed: list[QObject] = []
        if page is not None:
            page.hide()
            doomed.append(page)
        doomed.extend(self.findChildren(QObject, "materialBridge"))
        seen: set[int] = set()
        # The bridges are the controller's own children, not the window's: cut their session signals
        # before the deleteLater below, so a week change on this turn finds no listener.
        for bridge in self.findChildren(QObject, "materialBridge"):
            dispose = getattr(bridge, "dispose", None)
            if callable(dispose):
                dispose()
        for item in doomed:
            if id(item) in seen:
                continue
            seen.add(id(item))
            item.setParent(None)
            item.deleteLater()

    def _give_up_material(self, *, show_week: bool = True) -> None:
        """Material could not draw. With the graphics card: remember this version must use the CPU and
        start a new copy that does. Already on the CPU: a plain error page, never the Widgets week.

        `show_week` is kept for the callers that name where the student was; neither path uses it.
        """
        if self._relaunching or self._material_gave_up:
            return
        self._stop_material_ring()
        if cpu_drawing.drawing_on_cpu():
            self._material_gave_up = True
            self._show_draw_error()
            return
        self._relaunching = True
        self._material_gave_up = True
        self._cpu_drawing_version = VERSION
        self._save_look()
        self._relaunch(cpu=True)

    def _relaunch(self, *, cpu: bool) -> None:
        """Wait for unsaved edits to reach the server, then start a new copy and quit this one."""
        again = "try again"

        def go() -> None:
            server = self._instance_server
            if server is not None:
                # The new copy must not find this one and just ask it to show itself.
                server.close()
            try:
                cpu_drawing.start_new_copy(cpu=cpu)
            except OSError as error:
                logging.getLogger("flexweek.material").warning("FlexWeek could not start again: %s", error)
                self._relaunching = False
                self._show_draw_error()
                return
            self._quit_now()

        if self._save_before_leaving(go, again=again):
            go()

    def _show_draw_error(self) -> None:
        """A plain page for a window that cannot be drawn at all: what happened, the version, two buttons."""
        page = self._draw_error_window
        if page is None:
            # Its own top-level window: Material's window cannot hold a widget page.
            page = QWidget()
            page.setObjectName("drawErrorPage")
            page.setWindowTitle(self._title)
            page.setWindowIcon(self._icon)
            page.resize(self._size)
            page.installEventFilter(self)
            self._draw_error_window = page
            box = QVBoxLayout(page)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line = QLabel(cpu_drawing.DRAW_ERROR)
            line.setObjectName("drawErrorLine")
            line.setWordWrap(True)
            line.setAlignment(Qt.AlignmentFlag.AlignCenter)
            version = QLabel(f"FlexWeek {VERSION}")
            version.setObjectName("drawErrorVersion")
            version.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row = QHBoxLayout()
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            quit_button = QPushButton("Quit")
            quit_button.setObjectName("drawErrorQuit")
            quit_button.clicked.connect(self.quit_app)
            retry = QPushButton("Try again")
            retry.setObjectName("drawErrorRetry")
            retry.clicked.connect(self._try_graphics_again)
            row.addWidget(quit_button)
            row.addWidget(retry)
            update_line = QLabel()
            update_line.setObjectName("drawErrorUpdateLine")
            update_line.setWordWrap(True)
            update_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
            update_line.hide()
            install = QPushButton("Update now")
            install.setObjectName("drawErrorInstall")
            install.clicked.connect(self._install_from_draw_error)
            install.hide()
            update_row = QHBoxLayout()
            update_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            update_row.addWidget(install)
            box.addWidget(line)
            box.addWidget(version)
            box.addLayout(row)
            box.addWidget(update_line)
            box.addLayout(update_row)
        self._on_error_face = True
        self._sync_faces()
        self._offer_update_on_draw_error()

    def _try_graphics_again(self) -> None:
        """Forget that this version failed and start a new copy that uses the graphics card."""
        self._cpu_drawing_version = ""
        self._save_look()
        self._relaunching = True
        self._relaunch(cpu=False)

    def _on_material_failed(self, _message: str) -> None:
        self._give_up_material()

    def _present_material(self) -> bool:
        """Show the QML week. False means the Widgets week is up and the saved choice is unchanged."""
        if self._material_gave_up:
            return False
        page = self._ensure_material()
        if page is None or self._material_gave_up:
            return False
        # Show first. The quick widget builds its scene when it is shown, and a bridge installed
        # earlier is not the one that scene reads.
        self._show_page("materialPage")
        try:
            loaded = page.load()
        except Exception as error:
            logging.getLogger("flexweek.material").warning("Material 3 could not load: %s", error)
            loaded = False
        if not loaded:
            if not self._material_gave_up:
                self._give_up_material()
            return False
        try:
            page.publish()
        except Exception as error:
            logging.getLogger("flexweek.material").warning("Material 3 could not be shown: %s", error)
            # Show the week before the failed page is removed. Removing the current page first
            # makes the stack land on whatever is underneath, often Settings.
            if not self._material_gave_up:
                self._give_up_material()
            self._drop_partial_material()
            return False
        if self.session.account is not None and os.environ.pop(cpu_drawing.NOTICE_ENV, ""):
            self.session._say(cpu_drawing.NOTICE)
        return True

    def _tick_material_clock(self) -> None:
        """Move Material's clock and now line. A tick must not redraw the Widgets week or take a prompt."""
        page = self._material_current()
        if page is None or not page._ready or not self._material_owns():
            return
        page.bridge.refresh()

    def _wears_carried_look(self) -> bool:
        """Nobody is signed in: the sign-in screens wear the look carried on this computer."""
        return self.session.account is None

    def _worn_look(self) -> dict:
        """The look on screen: before sign-in only the text size and High contrast of the last look
        worn here, else the one kept here."""
        if not self._wears_carried_look():
            return self._look
        if self._carried is None:
            return sanitize_look(None)
        text, contrast = self._carried
        return sanitize_look({"preset": "high-contrast" if contrast else "default", "knobs": {"text": text}})

    def _read_carried(self) -> tuple[str, bool] | None:
        return self.session.kept.carried_look() if self.session.kept is not None else None

    def _carry_look(self) -> None:
        """Keep the two things the sign-in screens borrow from the look, when it changes."""
        kept, account = self.session.kept, self.session.account
        if kept is None or account is None:
            return
        custom = self._look.get("custom")
        contrast = (custom["base"] if custom is not None else self._look["preset"]) == "high-contrast"
        # Only the sign-in screens' look, so a failed write is left for the next change to retry.
        with contextlib.suppress(OSError):
            kept.carry_look(str(account["id"]), effective_look(self._look)["text"], contrast)

    def _account_id(self) -> str | None:
        account = self.session.account
        return str(account["id"]) if account else None

    def _schedule_deadline_tick(self) -> None:
        self._deadline_tick.stop()
        if self.session.account is None:
            return
        moment = datetime.fromtimestamp(self.session.now_ms() / 1000)
        deadlines = []
        for item in self.session.assignments.values():
            raw = item.get("due")
            if not isinstance(raw, str) or not raw:
                continue
            try:
                due = datetime.fromisoformat(raw)
                if len(raw) == 10:
                    due = due.replace(hour=23, minute=59)
            except ValueError:
                continue
            if due > moment:
                deadlines.append(due)
        if deadlines:
            delay = round((min(deadlines) - moment).total_seconds() * 1000)
            self._deadline_tick.start(min(max(delay, 1), 2_147_483_647))

    def _deadline_changed(self) -> None:
        if self.session.account is None:
            return
        self._announce_overdue()
        # Material's overdue row and words come from the same list, so a deadline passing updates them too.
        self._tick_material_clock()
        self._schedule_deadline_tick()

    def _application_state_changed(self, state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            self._deadline_changed()
            # Back from the background the line may be minutes behind: no waiting for the next tick.
            self._tick_material_clock()

    def _set_clock(self) -> bool:
        """Whether the clock changed. Only a change redraws the week, so this is safe to call from
        the redraw itself."""
        return set_clock_24h((self.session.preferences or {}).get("clock_24h", False) is True)

    def _on_account(self, account: object) -> None:
        if account is None:
            self._setup_active = False
            self._setup_checked = False
            self._setup_prefs = {}
            self._setup_work_windows = None
            self._setup_week = False
            self._carried = self._read_carried()
            self._apply_appearance()
            self._show_page("authPage")
            return
        self._carry_look()
        self._apply_appearance()

    def _on_recovery(self) -> bool:
        bridge = self._account_bridge()
        return bridge is not None and bridge.phase == "recovery"

    def _finish_recovery(self) -> None:
        self._allow_week_page = True
        self.session.finish_recovery()

    def _maybe_open_setup(self) -> None:
        """Setup opens once a sign-in, for an account that has neither finished nor skipped it.

        A new account opens it at once. Any other waits for its preferences, which say whether setup
        was finished and, if not, the step to resume on. An account from before setup kept its place
        opens it only when it has nothing in it yet, as the first-week card did.
        """
        session = self.session
        if self._setup_active or self._setup_checked or session.account is None:
            return
        prefs = session.preferences
        if prefs is None and not session.new_account:
            return
        self._setup_checked = True
        progress = (prefs or {}).get("setup")
        if progress is None:
            if session.new_account or (not session.blocks and not session.assignments):
                self._open_setup(STYLE, first_run=True)
            return
        if not progress.get("finished_at"):
            step = int(progress.get("step") or STYLE)
            self._open_setup(step, first_run=step <= REMINDERS)

    def _setup_state(self, first_run: bool) -> SetupState:
        session = self.session
        prefs = session.preferences or {}
        courses = {str(item.get("course") or "").strip() for item in session.assignments.values()}
        return SetupState(
            pack=str(prefs.get("theme_pack") or "system"),
            look=self._look,
            layout=self._layout,
            preferences=dict(prefs),
            blocks=list(session.repeats),
            this_week=this_week_line(
                session.blocks, session.repeats, prefs.get("clock_24h") is True, session.week_start
            ),
            week_start=session.week_start,
            subjects=sorted(course for course in courses if course),
            first_run=first_run,
        )

    def _open_setup(self, step: int, *, first_run: bool) -> None:
        self._setup_active = True
        state = self._setup_state(first_run)
        if self._material_gave_up:
            return
        page = self._ensure_material(quiet=True)
        if page is not None:
            page.bridge.account.open_setup(state, step)
            self._show_page("setupPage")

    def _run_setup_again(self) -> None:
        self._setup_checked = True
        self._open_setup(STYLE, first_run=False)

    @property
    def _setup_prefs(self) -> dict:
        return self.session.setup_prefs

    @_setup_prefs.setter
    def _setup_prefs(self, value: dict) -> None:
        self.session.setup_prefs = value

    @property
    def _setup_work_windows(self) -> list[dict] | None:
        return self.session.setup_work_windows

    @_setup_work_windows.setter
    def _setup_work_windows(self, value: list[dict] | None) -> None:
        self.session.setup_work_windows = value

    @property
    def _setup_week(self) -> bool:
        return self.session.setup_week

    @_setup_week.setter
    def _setup_week(self, value: bool) -> None:
        self.session.setup_week = value

    def _setup_step_left(self, _step: int, destination: int, answer: object) -> None:
        """Keep what a page answered, and where the student went, so a quit resumes there."""
        updates: dict = {"setup": {"version": SETUP_VERSION, "step": destination}}
        work_windows = None
        save_week = False
        standing = None
        if isinstance(answer, dict):
            if "layout" in answer:
                self._look = answer["look"]
                self.session.look = self._look
                self._layout = answer["layout"]
                self._save_look()
                updates["theme_pack"] = answer["pack"]
            if "blocks" in answer:
                standing = self.session.setup_repeats(answer["blocks"])
                updates["day_cutoff"] = answer["day_cutoff"]
                save_week = True
            if "homework" in answer:
                auto = (self.session.preferences or {}).get("planning_style") == "auto"
                for item in answer["homework"]:
                    self.session.add_homework(item)
                    if auto:
                        self.session.plan_after_save(item["id"])
                save_week = True
            for key in (
                "planning_style",
                "drag_step_min",
                "reminders_enabled",
                "reminder_lead_min",
                "alarm_tone",
                "default_spotify_url",
                "clock_24h",
            ):
                if key in answer:
                    updates[key] = answer[key]
            if "work_windows" in answer:
                work_windows = answer["work_windows"]
        edited = answer.get("edited") if isinstance(answer, dict) else None
        if standing is not None and not self._apply_standing(
            standing, "setting up your week", edited=edited
        ):
            return
        self.session.keep_setup(updates, work_windows=work_windows, save_week=save_week)

    def _flush_setup(self) -> None:
        self.session.flush_setup()

    def _finish_setup(self) -> None:
        stamp = wall_clock.now().strftime("%Y-%m-%dT%H:%M")
        bridge = self._account_bridge()
        step = bridge.setup_step if bridge is not None else STYLE
        progress = {"version": SETUP_VERSION, "step": step, "finished_at": stamp}
        if self.session.new_account and self.session.account is not None:
            self._new_look_notice_exempt.add(str(self.session.account["id"]))
            self._save_look()
        self._setup_active = False
        self.session.keep_setup({"setup": progress})
        self._on_week()

    def _show_recovery(self, codes: list) -> None:
        self._allow_week_page = False
        self._material_account_page("recoveryPage", codes)

    @staticmethod
    def recovery_file_question() -> dict:
        """The question before the file dialog, for Material's prompt: the same words and answers."""
        return {
            "id": "recovery-file",
            "title": "Save recovery codes",
            "body": RECOVERY_KEEP,
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "choose", "label": RECOVERY_CHOOSE, "kind": "filled", "default": True},
            ],
        }

    def _pick_recovery_file(self) -> str:
        """The file dialog, opened on Documents (#50); a test answers it with a path."""
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        start = str(Path(documents or Path.home()) / RECOVERY_FILE)
        path, _ = QFileDialog.getSaveFileName(None, "Save recovery codes", start, "Text (*.txt)")
        return path

    def _on_week_start(self, _value: str) -> None:
        """The week's first day changed in Settings or Setup: every open screen follows at once."""
        self.session.follow_first_weekday(week_start_day())

    def _on_week(self) -> None:
        if self.session.account is None:
            return
        if self.session.dirty:
            # Every change reaches here, so this is where the clock on "stopped changing" restarts.
            self.session.client.command({"cmd": "autosave_changed"})
        if self._on_recovery() and not self._allow_week_page:
            return
        self._set_clock()
        self._check_updates(asked=False)
        self._maybe_open_setup()
        if self._setup_prefs or self._setup_work_windows is not None or self._setup_week:
            # The account's preferences may only now have arrived, and what setup kept before they did,
            # a skip included, is written with them.
            QTimer.singleShot(0, self, self._flush_setup)
        # Setup stays where it is. Anything else shows the surface that owns the window.
        if not self._cover_holds():
            self._show_surface()
        self._announce_overdue()
        self._apply_appearance()
        self._schedule_deadline_tick()
        if getattr(self, "_plan_focus_pending", False):
            self._plan_focus_pending = False
            QTimer.singleShot(0, self, self._focus_after_plan)

    def _on_status(self, message: str) -> None:
        """What the session says goes on Material's snackbar, on every screen: it is the shell's and is
        never covered, unless it is still going ("Saving…") or routine ("Saved."). The student's own
        request is answered either way."""
        snack = self._snack_bridge()
        if not message:
            # The session took back what it said, as Cancel on Running late's preview does.
            if snack is not None and snack.snackText and snack.snackAction == "":
                snack.note("")
            return
        if message.endswith("…"):
            return
        asked, self._telling = self._telling, False
        if not (asked or message not in ROUTINE_STATUS):
            return
        if snack is not None:
            self._say_in_snack(snack, message)

    def _snack_bridge(self):
        """Material's bridge while Material is what the student sees; its snackbar takes the notices."""
        page = self._material_current()
        if page is None or not self._material_owns():
            return None
        return page.bridge

    def _say_in_snack(self, snack, message: str) -> None:
        """The same notice is not said twice, and Plan finding nothing new
        leaves its Undo where it is."""
        if snack.snackText == message:
            return
        if snack.snackAction == "UNDO" and snack.snackText and self._keeps_undo(message):
            snack.bump_snack()
            return
        self._notice_step = None
        snack.note(message, action="")

    def _keeps_undo(self, message: str) -> bool:
        """Plan finding nothing new leaves a visible Undo toast. So does a plain repeat from the
        same button in the first second. An error or a reminder still replaces it."""
        if not self._toast_offers_undo():
            return False
        if getattr(self.session, "_plan_idle", False):
            return True
        shown = getattr(self, "_undo_at", None)
        button = getattr(self, "_undo_button", "")
        if shown is None or not button or time.monotonic() - shown > 1:
            return False
        if self._focus_name() != button:
            return False
        if message == self._reminder_said:
            return False
        return not any(part in message for part in ("Try again", "Wait a moment", "could not", "Couldn't"))

    def _focus_name(self) -> str:
        """The name of what holds the keyboard: Material's window, or the widget with focus, else empty."""
        page = self._material_page
        if page is not None and QApplication.focusWindow() is page:
            return str(page.objectName())
        focus = QApplication.focusWidget()
        return str(focus.objectName()) if focus is not None else ""

    def _reminder_handled(self) -> None:
        """Got it on a reminder left on screen: the snackbar saying the same goes too."""
        snack = self._snack_bridge()
        if snack is not None and snack.snackText == self._reminder_said:
            snack.note("")

    def _toast_offers_undo(self) -> bool:
        snack = self._snack_bridge()
        return snack is not None and bool(snack.snackText) and snack.snackAction == "UNDO"

    def _on_busy(self, busy: bool) -> None:
        if not busy and (self._setup_prefs or self._setup_work_windows is not None or self._setup_week):
            # A moment later, so a plan that finished just now saves its week before setup writes.
            QTimer.singleShot(0, self, self._flush_setup)

    def confirm_standing(self, after: list) -> str | None:
        """The answer for a setup week change, asked before that page keeps anything.

        None is Cancel: the page stays as the student left it and nothing is saved. Nothing is
        remembered after this returns, so a later save asks for itself."""
        changes = self.session.repeat_diff(after)
        if not changes:
            return "keep"
        return self._choice_for_edits(changes)

    def _repeat_view(self) -> tuple:
        """The account, week and repeats a preview was asked about."""
        account = self.session.account
        rows = tuple(
            (
                item.get("id"),
                item.get("start"),
                item.get("duration_min"),
                tuple(item.get("days") or []),
            )
            for item in self.session.repeats
        )
        return (None if account is None else account.get("id"), self.session.week_start, rows)

    def _arm_epoch(self, loop: QEventLoop) -> tuple[QTimer, int]:
        """Quit `loop` if the client is signed out or switched while it waits."""
        epoch = self.session.client.epoch
        timer = QTimer(self)
        timer.setInterval(50)

        def tick() -> None:
            if self.session.client.epoch != epoch:
                loop.quit()

        timer.timeout.connect(tick)
        timer.start()
        return timer, epoch

    def _apply_standing(self, after: list, label: str, *, edited: str | None = None) -> bool:
        """Put `after` in place from this week on, after asking when a later week has its own edit.
        False when the student cancels, or the week changed while the question was up: nothing is
        changed. A setup page passes the answer it already asked for."""
        view = self._repeat_view()
        if edited is None:
            changes = self.session.repeat_diff(after)
            edited = "keep"
            if changes:
                asked = self._choice_for_edits(changes)
                if asked is None:
                    return False
                edited = asked
        if self._repeat_view() != view:
            return False
        self.session.change_repeats(after, label, edited=edited)
        return True

    def _save_standing(self, after: list, label: str, notice: Callable[[], None]) -> None:
        if not self._apply_standing(after, label):
            return
        self.session.save()
        notice()

    def _choice_for_edits(self, changes: list) -> str | None:
        """keep, replace or from_today. None when the preview fails or the student cancels.
        No question when no later week has its own edit."""
        holder: dict = {}
        view = self._repeat_view()
        loop = QEventLoop(self)
        timer, epoch = self._arm_epoch(loop)

        def ok(data: dict) -> None:
            holder["line"] = data.get("line") or None
            loop.quit()

        def err(error: object) -> None:
            holder["error"] = error
            loop.quit()

        self.session.preview_repeats(changes, ok, err)
        loop.exec()
        timer.stop()
        timer.deleteLater()
        loop.deleteLater()
        if self.session.client.epoch != epoch or self._repeat_view() != view:
            return None
        if "error" in holder:
            self._set_notice("Not saved. " + holder["error"].message, "", None)
            return None
        line = holder.get("line")
        if not line:
            return "keep"
        choice = self._pose_edited(line)
        if self._repeat_view() != view:
            return None
        return choice

    def _pose_edited(self, line: str) -> str | None:
        """The three answers, or None for Cancel. Asked on Material's answers sheet, Except edited the
        default. Material not on screen means no answer, so nothing changes."""
        bridge = self._account_bridge()
        material = self._surface == "material" and not self._material_gave_up
        if material and bridge is not None and bridge.phase == "setup":
            return self._pose_edited_on(line, bridge.pose_edited)
        page = getattr(self, "_material_page", None)
        if material and page is not None and self._material_owns():
            return self._pose_edited_on(line, page.bridge._sheets.pose_edited)
        return None

    def _pose_edited_on(self, line: str, pose: Callable) -> str | None:
        holder: dict = {}
        loop = QEventLoop(self)
        timer, epoch = self._arm_epoch(loop)

        def done(choice: str | None) -> None:
            holder["choice"] = choice
            loop.quit()

        pose(self._edited_ask(line), done)
        loop.exec()
        timer.stop()
        timer.deleteLater()
        loop.deleteLater()
        if self.session.client.epoch != epoch:
            return None
        return holder.get("choice")

    @staticmethod
    def _edited_ask(line: str) -> dict:
        return {
            "id": "edited-weeks",
            "title": "Edited weeks",
            "body": line,
            "answers": [
                {"id": "keep", "label": "Except edited", "kind": "filled", "default": True},
                {"id": "replace", "label": "All weeks", "kind": "danger"},
                {"id": "from_today", "label": "From today on", "kind": "danger"},
                {"id": "stay", "label": "Cancel", "kind": "text"},
            ],
            "cards": [
                {
                    "id": "keep",
                    "title": "Keep my edited weeks",
                    "line": "Updates the other weeks. Weeks you changed yourself keep their own times.",
                },
                {
                    "id": "from_today",
                    "title": "From today on",
                    "line": (
                        "Days before today keep their times. Weeks you changed are replaced. "
                        "Can't be undone."
                    ),
                },
                {
                    "id": "replace",
                    "title": "Every week",
                    "line": (
                        "Replaces the times in all weeks, including the ones you changed. "
                        "Can't be undone."
                    ),
                },
            ],
            "confirm": "Save changes",
        }

    def _today(self) -> str:
        return clock_parts(self.session.now_ms())["iso"]

    def _announce_overdue(self) -> None:
        """Keep count announcements on the active page's accessibility tree."""
        stamp = self.session.now_ms() / 1000
        overdue = overdue_unfinished(self.session.unfinished(), datetime.fromtimestamp(stamp))
        words = f"{len(overdue)} overdue"
        previous = getattr(self, "_overdue_words", None)
        if words != previous and (previous is not None or overdue):
            announce(self, words)
        self._overdue_words = words

    def _remember_zoom(self, key: str, px: int) -> None:
        """How close a surface's hours are is kept for this device, as the look is."""
        # In place: every design holds this dict and reads it for the hours it makes later.
        self._zoom[key] = px
        self._save_look()

    def _set_notice(self, text: str, button: str, callback) -> None:
        """Words with one thing to do about them, such as Undo, on Material's snackbar."""
        self._notice_step = None
        if self._material_owns() and self._material_page is not None:
            if button == "Undo":
                self._material_page.bridge.note(text)
            else:
                self._material_page.bridge.note(text, action=button, on_action=callback if button else None)
        if button == "Undo":
            self._undo_at = time.monotonic()
            self._undo_button = self._focus_name()

    def _undo_from_notice(self) -> None:
        self._notice_step = None
        self.session.undo()

    def _say_repeats_kept(self, words: str) -> None:
        """Later weeks kept their own change when School or an activity changed from this week on: said
        on Material's snackbar, without Undo (later weeks have none) and without blocking."""
        if self._material_owns() and self._material_page is not None:
            self._material_page.bridge.note(words, action="")

    def _say_when_saved(self, words: str) -> None:
        """`words` say what the save now on its way changes, once it lands, with Undo. A change that
        started no save says nothing."""
        self._change_saving = words if self.session.busy else None

    def _show_change(self) -> None:
        if self._change_saved is None:
            return
        words, self._change_saved = self._change_saved, None
        self._set_notice(words, "Undo", self._undo_from_notice)
        self._notice_step = self.session.last_step()

    def _told(self, act) -> None:
        """Do what the student asked, and once it is done say what it did in the toast: the first thing
        the session says, bar words ending in "…", which say it is still going. Asked for, even a
        routine "Saved." is the answer."""
        self._telling = True
        act()
        if not self.session.busy:
            # Done at once, or a dialog closed without doing anything.
            self._telling = False

    def _on_planned(self, said: str) -> None:
        # The answer to Plan my homework, so no later status is taken for it.
        self._telling = False
        if self._material_owns():
            if self.session.placed_where:
                said = self.session.placed_where
            else:
                placed = self.session.plan_counts[0]
                said = f"Placed {placed} of {placed + self.session.plan_open}"
                if self.session.plan_remainders:
                    said = f"{said}.{left_sentence(self.session.plan_remainders)}"
                for item in (self.session.trace or {}).get("notices") or []:
                    if item.get("kind") == "spread_same_day" and item.get("message"):
                        said = f"{said}. {item['message']}"
                        break
        self._set_notice(said, "Undo", self._undo_from_notice)
        # Plan caused this Undo, even when the click has already moved the keyboard.
        self._undo_button = "solveButton"
        self._undo_at = time.monotonic()
        self._notice_step = self.session.last_step()
        # Focusing on the next turn lands after the week redraws and could take the keyboard.
        self._plan_focus_pending = True

    def _focus_after_plan(self) -> None:
        self.activateWindow()

    def _on_plan_conflicts(self, lost: list) -> None:
        if not lost:
            return
        self._notice_ids = {item["block_id"] for item in lost}
        # Every homework that lost its time is named. Find a new time moves all of them, and the notice
        # showed only the first.
        said = [item["message"] for item in lost[:NOTICE_LINES]]
        if len(lost) > NOTICE_LINES:
            said.append(f"And {len(lost) - NOTICE_LINES} more.")
        self._set_notice("\n".join(said), "Find a new time", self._find_new_time)

    def _find_new_time(self) -> None:
        ids = getattr(self, "_notice_ids", set())
        if ids:
            self.session.solve(only=ids)

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
        done: str | None = None,
        confirm: str = "Save preview",
    ) -> None:
        """`done` is the verb that says what saving the rows did, as in "Pasted Piano". `confirm` is what
        Material's button says."""
        if not rows:
            return

        def save(saved: list[dict]) -> None:
            chosen = [row for row in saved if row.get("checked")]
            what = chosen[0]["block"]["title"] if len(chosen) == 1 else f"{len(chosen)} blocks"
            said = f"{done} {what}." if done and chosen else None
            self.session.confirm_preview(
                saved,
                label=label,
                snapshot_label=snapshot_label,
                attempt_key=attempt_key,
                existing=existing,
                destination=destination,
                said=said,
            )

        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.open_preview(
                PreviewDraft(
                    title,
                    summary,
                    rows,
                    existing if existing is not None else self.session.blocks,
                    save,
                    confirm,
                )
            )

    def _paste_clipboard(self) -> None:
        self._paste_preview(self.session.paste_destination(), self.session.paste_proposals())

    def _paste_at(self, day: int, minute: int) -> None:
        start = minutes_to_hhmm(minute)
        self._paste_preview((day, start), self.session.paste_proposals(day, start))

    def _paste_preview(self, dest: tuple[int, str | None] | None, rows: list[dict] | None) -> None:
        clip = self.session.clipboard
        label = "pasting " + clip["label"] if clip else "pasting"
        key = None
        if clip and self.session.account is not None:
            key = (
                f"paste|{self.session.account['id']}|{self.session.week_start}|"
                f"{dest[0] if dest else ''}|{(dest[1] if dest else '') or ''}|"
                f"{clip['fingerprint']}"
            )
        self._show_preview(
            "Preview paste",
            "Nothing changes until you choose Paste.",
            rows,
            label=label,
            attempt_key=key,
            done="Pasted",
            confirm="Paste",
        )

    def _duplicate_selected(self) -> None:
        chosen = next(
            (item for item in self.session.blocks if item["id"] == self.session.selected_block_id), None
        )
        rows = self.session.duplicate_selected()
        self._show_preview(
            "Preview duplicate",
            "Nothing changes until you choose Duplicate.",
            rows,
            label="duplicating " + (chosen or {}).get("title", "a block"),
            done="Duplicated",
            confirm="Duplicate",
        )

    def _copy_day(self) -> None:
        self.session.copy_day()

    def _unfinished_items(self, items: list[dict] | None = None) -> list[dict]:
        """The engine classifies overdue and earlier-week homework against the held session clock."""
        return self.session.unfinished() if items is None else items

    def _plan_left(self) -> None:
        items = self._unfinished_items()
        self.session.plan_left([item["id"] for item in items])

    def _did_left(self) -> None:
        left = self._unfinished_items()
        if not left:
            return
        self.session.did_these([item["id"] for item in left])
        words = left[0]["title"] if len(left) == 1 else f"{len(left)} homework"
        self._set_notice(f"Marked {words} finished.", "Undo", self._undo_from_notice)

    def _plan_with_left_over(self, everything: bool = False) -> None:
        items = self._unfinished_items()
        if not items:
            if everything:
                self.session.solve(everything=True)
            else:
                self.session.solve()
            return
        overdue = sum(item.get("left_over_state") == "overdue" for item in items)
        carried = len(items) - overdue
        parts = []
        if overdue:
            parts.append(f"{overdue} overdue")
        if carried:
            parts.append(f"{carried} left from last week")
        def plan_them() -> None:
            self.session.plan_left([item["id"] for item in items])

        def did_them() -> None:
            self.session.did_these([item["id"] for item in items])

        def not_now() -> None:
            self.session.plan_asked_week = self.session.week_start

        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.pose_question(
                self.before_planning_question(", ".join(parts)),
                {"plan": plan_them, "did": did_them, "not": not_now, "stay": not_now, "dismiss": not_now},
            )

    @staticmethod
    def before_planning_question(body: str) -> dict:
        """What Plan asks when homework is left over, for Material's prompt: three choice cards, Not now
        picked first as the answer that changes nothing (Jonathan, 2026-11-18)."""
        return {
            "id": "before-planning",
            "title": "Before planning",
            "body": body,
            "answers": [{"id": "stay", "label": "Cancel", "kind": "text"}],
            "cards": [
                {"id": "plan", "title": "Plan into this week", "line": "Give them times this week."},
                {
                    "id": "did",
                    "title": "Mark as finished",
                    "line": "You already did them. They leave the list.",
                },
                {
                    "id": "not",
                    "title": "Not now",
                    "line": "They stay on the list, and you won't be asked again this week.",
                },
            ],
            "pick": 2,
            "confirm": "Continue",
        }

    def _copy_last_week_fixed(self) -> None:
        def offer(rows: list[dict] | None) -> None:
            if not rows:
                return
            self._show_preview(
                "Copy last week's fixed times",
                "Uncheck anything you don't want before saving.",
                rows,
                label="last week's fixed times",
                existing=self.session.blocks,
            )

        self.session.copy_last_week_fixed_rows(offer)

    def _plan_unfinished(self, assignment_id: str) -> None:
        # Time the week already holds without a time (a waiting or missed session) is placed where it
        # is; only minutes no session holds become a new session through the preview.
        missed = self.session.missed_block_ids()
        held = any(
            block.get("assignment_id") == assignment_id
            and not block.get("completed")
            and (not block.get("start") or block["id"] in missed)
            for block in self.session.blocks
        )
        if (
            held
            or assignment_id in self.session._overdue_assignment_ids()
            or self.session.remaining_for(assignment_id) < 15
        ):
            self.session.plan_left([assignment_id])
            return
        item = self.session.assignments.get(assignment_id)
        rows = self.session.plan_unfinished(assignment_id)
        self._show_preview(
            "Plan homework",
            (item["title"] + " keeps its original deadline and progress.") if item else "",
            rows,
            label="homework",
            attempt_key=(
                f"unfinished|{self.session.account['id']}|{self.session.week_start}|"
                f"{assignment_id}|{self.session.remaining_for(assignment_id)}"
                if self.session.account
                else None
            ),
        )

    def _on_save_finished(self, stored: bool, said: str) -> None:
        if not stored:
            # The retry wait starts at a failure, whoever started the save: one started by a button
            # left the timer's last try long ago, and it tried again on its very next tick.
            self.session.client.command({"cmd": "autosave_failed"})
        change, self._change_saving = self._change_saving, None
        if stored and change is not None:
            self._change_saved = change
            self._show_change()
        elif stored and self._notice_step is not None and self.session.last_step() is not self._notice_step:
            # A later change, or an Undo, has taken the notice's step off the top: its Undo would now
            # take back something else.
            snack = self._snack_bridge()
            if snack is not None and snack.snackAction == "UNDO":
                snack.note("")
            self._notice_step = None

    def start_material_focus(self, block_id: str | None, day: object) -> None:
        """Day and My day's Start focus: the session's timer, then Material's Focus screen."""
        self._start_focus(block_id or "", day)

    def _start_focus(self, block_id: str, day: object) -> None:
        if self.session.start_focus(block_id or None, day if isinstance(day, int) else None):
            self._open_focus_screen()

    def _quick_focus(self) -> None:
        """The focus screen, ready: nothing starts until Start, as with F (decision 19 of 0.17)."""
        self._open_focus_screen()

    @staticmethod
    def replace_focus_question(current: str, incoming: str) -> dict:
        """The Widgets "Replace timer" question for Material's prompt: same words and answers, keep first."""
        return {
            "id": "replace-focus",
            "title": "Replace timer",
            "body": f"Stop the timer for {current} and start {incoming} instead?",
            "answers": [
                {"id": "keep", "label": "Keep current timer", "kind": "text", "default": True},
                {"id": "replace", "label": "Replace timer", "kind": "danger"},
            ],
        }

    def _confirm_replace_focus(self, current: str, incoming: str) -> None:
        def replace() -> None:
            if self.session.confirm_replace_focus():
                self._open_focus_screen()

        page = self._material_shown()
        if page is not None:
            question = self.replace_focus_question(current, incoming)
            page.bridge.sheets.pose_question(question, {"replace": replace})

    def _build_focus_audio(self) -> None:
        # Rain, lo-fi or white noise while the focus timer works; the timer's own phases drive it.
        self._focus_audio = FocusAudio(self.session, self)

    def _material_focus(self):
        """Material's Focus screen when Material owns the window and is built, else None."""
        page = self._material_page
        if page is None or not self._material_owns() or not page._ready:
            return None
        return page.bridge.focus

    def _open_focus_screen(self) -> None:
        if self.session.account is None or not self._material_owns():
            return
        if self._material_current() is None and not self._show_surface():
            return
        material = self._material_focus()
        if material is not None:
            material.show()

    def _on_focus(self) -> None:
        released = self.session.release_held_alerts()
        if released:
            self._present_alerts(released)

    def _present_alerts(self, notices: list) -> None:
        notices = self.session.hold_alerts(notices)
        if not notices:
            return
        prefs = self.session.preferences or {}
        if notices and prefs.get("reminder_sound", True) is not False:
            # Reminders ring the chosen alarm sound. A focus notice keeps its own two tones until the
            # student picks a sound, then uses theirs. A Spotify sound never starts music for these.
            tone = prefs.get("alarm_tone")
            short = FALLBACK if tone in (None, "spotify") else str(tone)
            focus = [notice for notice in notices if notice.get("kind") == "focus"]
            if len(focus) < len(notices):
                self._bell.once(short, prefs.get("alert_volume", 80))
            elif prefs.get("end_chime"):
                own = str(focus[0].get("tone") or FALLBACK)
                self._bell.once(own if tone is None else short, prefs.get("alert_volume", 80))
        tray = self._tray_icon if self._tray_icon is not None and self._tray_icon.supportsMessages() else None
        # A tray message is gone in eight seconds and a machine may suppress it outright. With no pop-ups
        # to rely on, or "Leave reminders on screen" on, a reminder sits in the window as a card until
        # its block starts or the student deals with it.
        keeps = tray is None or bool(prefs.get("reminder_dnd_override"))
        reminders = []
        for notice in notices:
            title = notice.get("title") or "FlexWeek"
            body = notice.get("body") or ""
            words = title + (" — " + body if body else "")
            if tray is not None:
                tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)
            if notice.get("kind") == "reminder":
                if not (keeps and self.session.reminder_cards.add(notice)):
                    reminders.append(words)
            elif tray is None:
                self.session._say(words)
        if reminders:
            # A desktop can hide a tray message, and FlexWeek cannot tell that it did, so the window
            # says it as well, wherever the student is.
            self._reminder_said = "; ".join(reminders)
            snack = self._snack_bridge()
            if snack is not None:
                self._say_in_snack(snack, self._reminder_said)
        if prefs.get("reminder_dnd_override"):
            # Reminders are cards; any other notice (focus) still sits in the strip with its Got it.
            others = [notice for notice in notices if notice.get("kind") != "reminder"]
            if others:
                self.alert_strip.add(others)

    def _on_alarm(self, alarm: object) -> None:
        if not isinstance(alarm, dict):
            return
        if self._alarm_dialog is not None or self._alarm_on_material:
            return
        url = self.session.spotify_url(alarm.get("spotify_url"))
        if self._ring_on_material(alarm, url):
            return
        # Only when Material is not on screen: the draw-error window stands in, and the alarm opens over it.
        face = self._face()
        dialog = AlarmRingDialog(face if isinstance(face, QWidget) else None, alarm, url)
        self._alarm_dialog = dialog
        self._ring(alarm, url)
        try:
            dialog.exec()
        finally:
            # Whatever closed the dialog, including the window shutting, the noise stops with it,
            # Spotify included.
            self._bell.stop()
            self._spotify.stop()
        snoozed = dialog.snoozed
        self._alarm_dialog = None
        self.session.finish_alarm(snoozed)

    def _ring_on_material(self, alarm: dict, url: str) -> bool:
        """Ring on Material's screen when Material is what the window shows. False leaves it to the dialog."""
        page = self._material_current()
        if page is None or not self._material_owns():
            return False
        self._alarm_on_material = True
        self._ring(alarm, url)
        page.bridge.ring.show_alarm(alarm, url, self._finish_material_alarm)
        return True

    def _stop_material_ring(self) -> None:
        """The window closes or Material gives up while an alarm rings on its screen: the screen has no
        dialog to stop the noise as it closes, so the ring is ended here, as a dismiss."""
        if not self._alarm_on_material:
            return
        page = self._material_page
        ring = getattr(getattr(page, "bridge", None), "ring", None)
        if ring is not None and ring.open:
            ring.dismiss()
        else:
            self._finish_material_alarm(False)

    def _finish_material_alarm(self, snoozed: bool) -> None:
        # The same ending as the dialog's: the noise stops, Spotify included, then the next alarm rings.
        self._bell.stop()
        self._spotify.stop()
        self._alarm_on_material = False
        self.session.finish_alarm(snoozed)

    def _ring(self, alarm: dict, url: str) -> None:
        """Play the alarm's own sound. "spotify" means the linked song or playlist in the student's
        Spotify app. Whatever it cannot be sure will play gets the tone too: a silent alarm is not an
        alarm."""
        prefs = self.session.preferences or {}
        tone = str(alarm.get("sound") or prefs.get("alarm_tone") or FALLBACK)
        if tone == "spotify" and not url:
            url = self.session.spotify_url(prefs.get("default_spotify_url") or "")
        if tone == "spotify" and url and self._spotify.play(url) in (LISTENING, STARTING):
            # Listening: the tone waits for `late`, and stops when Spotify is heard.
            return
        self._bell.start(FALLBACK if tone == "spotify" else tone, prefs.get("alert_volume", 80))

    def _spotify_late(self) -> None:
        if self._alarm_dialog is not None or self._alarm_on_material:
            self._bell.start(FALLBACK, (self.session.preferences or {}).get("alert_volume", 80))

    def _spotify_heard(self, words: str) -> None:
        if self._alarm_dialog is not None:
            self._bell.stop()
            self._alarm_dialog.show_playing(words)
        elif self._alarm_on_material and self._material_page is not None:
            self._bell.stop()
            self._material_page.bridge.ring.show_playing(words)

    def _check_updates(self, *, asked: bool) -> None:
        """Look for a newer release. Asked for by the student, or once a day on its own.

        A check that finds nothing says nothing unless the student asked, because an app that
        interrupts to report that it is already up to date is an app people turn off.
        """
        if self._updater.busy:
            return
        if not asked and not due_for_check(self._updates, self.session.now_ms()):
            return
        self._update_asked = asked
        self._updates["last_ms"] = self.session.now_ms()
        self._save_look()
        if asked:
            self.session._say("Checking for updates…")
        self._updater.check(developer=bool(self._updates.get("developer_builds")))

    def _on_update_found(self, update: object) -> None:
        if not isinstance(update, dict):
            return
        if not self._update_asked and update["version"] == self._updates.get("skip"):
            return
        page = self._material_shown()
        if page is None:
            self._draw_error_update = update
            self._offer_update_on_draw_error()
            return
        self._update_on_material = True

        def finished(skip: bool) -> None:
            self._update_on_material = False
            if skip:
                self._updates["skip"] = update["version"]
                self._save_look()

        page.bridge.sheets.open_update(update, VERSION, lambda: self._updater.download(update), finished)

    def _update_sheet(self):
        """Material's update sheet while it is the one showing the update, else None."""
        page = self._material_page if self._update_on_material else None
        sheets = None if page is None else page.bridge.sheets
        return sheets if sheets is not None and sheets.update_open() else None

    def _draw_error_update_row(self) -> tuple[QLabel, QPushButton] | None:
        """The draw-error page's update line and Update now button while that page is up and offers one."""
        page = self._draw_error_window
        if page is None or self._draw_error_update is None or not self._on_error_face:
            return None
        return page.findChild(QLabel, "drawErrorUpdateLine"), page.findChild(QPushButton, "drawErrorInstall")

    def _offer_update_on_draw_error(self) -> None:
        if (row := self._draw_error_update_row()) is None or self._draw_error_update is None:
            return
        line, install = row
        line.setText(f"FlexWeek {self._draw_error_update['version']} is ready")
        line.show()
        install.show()

    def _install_from_draw_error(self) -> None:
        if (row := self._draw_error_update_row()) is None or self._draw_error_update is None:
            return
        line, install = row
        install.setEnabled(False)
        line.setText("Downloading…")
        self._updater.download(self._draw_error_update)

    def _on_update_progress(self, got: int, total: int) -> None:
        if (sheet := self._update_sheet()) is not None:
            sheet.update_progress(got, total)
        elif (row := self._draw_error_update_row()) is not None and total > 0:
            row[0].setText(f"Downloading… {min(100, got * 100 // total)}%")

    def _on_update_problem(self, why: str) -> None:
        if (sheet := self._update_sheet()) is not None:
            sheet.update_problem(why)
        elif (row := self._draw_error_update_row()) is not None:
            row[0].setText(why)
            row[1].setEnabled(True)
        elif self._update_asked:
            self.session._say(why)

    def _on_update_ready(self, path: str) -> None:
        """The download is verified and on disk. Putting it in place replaces the running app, so
        the app is closed either way: on Windows the installer takes over, and on Linux the files
        under it have just been swapped."""
        problem = apply_update(path)
        if problem is not None:
            if (sheet := self._update_sheet()) is not None:
                sheet.update_problem(problem + " Open the release page to update by hand.")
            elif (row := self._draw_error_update_row()) is not None:
                row[0].setText(problem + " Open the release page to update by hand.")
                row[1].setEnabled(True)
            return
        if (sheet := self._update_sheet()) is not None:
            sheet.update_done()
        installed = "Update installed. FlexWeek will close so the new version can start."
        if (row := self._draw_error_update_row()) is not None:
            row[0].setText(installed)
        self.session._say(installed)
        QTimer.singleShot(UPDATE_QUIT_MS, self.quit_app)

    def _no_update(self) -> None:
        if self._update_asked:
            self.session._say(f"FlexWeek {VERSION} is the latest version.")

    def _update_unreachable(self, why: str) -> None:
        """A check nobody asked for fails quietly and tries again tomorrow. One the student asked for
        says so; saying nothing left "Checking for updates…" on screen as if it were still going."""
        if not self._update_asked:
            return
        self.session._say(why)
        self._set_notice(why, "Open release page", lambda: QDesktopServices.openUrl(QUrl(RELEASE_PAGE)))

    def _open_spotify(self) -> None:
        url = self.session.spotify_url()
        if not url:
            self.session._say("Add a Spotify link in Settings, under Alerts.")
            return
        open_in_app(url)

    def _sync_started(self, service: SyncService) -> None:
        self._sync = service
        self._sync_generation = service.generation()
        self._sync_timer.start()

    def _sync_tick(self) -> None:
        """Once a second: the sync status dot, and the week reloaded when a linked phone's edits arrive."""
        service = self._sync
        if service is None:
            return
        account = self.session.account
        if account is not None and not self._phones_reading:
            # The phone list is a database read; it runs off this thread and lands in _phones_read.
            self._phones_reading = True
            user_id = account["id"]
            run_off_ui(
                self,
                lambda: live_phones(service, user_id),
                lambda rows, _problem: self._phones_read(user_id, rows),
            )
        generation = service.generation()
        if generation != self._sync_generation and self._sync_arrived(service):
            self._sync_generation = generation

    def _phones_read(self, user_id: int, rows: list[dict] | None) -> None:
        self._phones_reading = False
        self._phones = rows or []
        self._phones_user = user_id

    def _linked_phones(self) -> list[dict]:
        account = self.session.account
        if account is None or self._phones_user != account["id"]:
            return []
        return self._phones

    def _sync_arrived(self, _service: SyncService) -> bool:
        """Loads the week again after a phone's edits land. With unsaved edits here, it marks the week
        as changed instead, so the existing Reload and Keep mine choice is offered. False while a
        request is in flight; the next tick asks again."""
        names = [row["name"] for row in self._linked_phones()]
        who = names[0] if len(names) == 1 else "a linked phone"
        return self.session.accept_remote_week(who)

    def watch_database(self, database: Path) -> None:
        """Show changes another program makes to `database`, the one this window saves to."""
        self._outside = OutsideWatch(database)
        self._outside_timer.start()

    def _outside_tick(self) -> None:
        """Every few seconds: the week loaded again after another program, such as the assistant, changed
        this account's schedule. With unsaved edits here it marks the week as changed instead, as a
        phone's edits do. It waits while a sheet is open, a request is in flight, or a phone's edits are
        still to be shown, and a change this window saved itself is never taken for another's."""
        watch, session = self._outside, self.session
        account = session.account
        if watch is None or account is None or session.busy or QApplication.activeModalWidget() is not None:
            return
        if self._sync is not None and self._sync.generation() != self._sync_generation:
            return
        weeks = session.stored_weeks()
        stored = watch.look(int(account["id"]), [week for week, _revision in weeks])
        if stored is None:
            return
        assistant = watch.assistant_wrote(stored)
        unsaved = session.dirty_assignments
        held = [revision for _week, revision in weeks]
        changed = assistant or differs(stored, held, session.assignments, unsaved)
        if changed and not session.accept_remote_week("your assistant" if assistant else "another program"):
            return
        watch.settle(stored)

    def _apply_start_at_login(self, wanted: bool) -> None:
        """The setting used to be stored on the account and obeyed by nothing. It is applied to this
        machine, since starting at login is a property of the machine rather than of the account."""
        if autostart.sync(wanted) is None and wanted:
            self.session._say("This machine doesn't support starting at login.")

    def _log_out(self) -> None:
        question = SIGN_OUT_QUESTION.format(where="this computer")
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.ask_sign_out(question, self._sign_out_confirmed)

    def _sign_out_confirmed(self) -> None:
        # Same wait as closing: an unsent Settings change has to reach the server, or stay on screen.
        if self._save_before_leaving(self.session.logout, again="sign out again"):
            self.session.logout()

    def _material_shown(self):
        """The Material page while it is the page on screen and built, else None."""
        page = self._material_current()
        if page is None or page.root is None:
            return None
        return page

    def _open_help(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openHelp()

    def _open_about(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openAbout()

    def _open_account(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openAccount()

    def _write_account_file(self, snapshot: dict) -> None:
        name = "flexweek-account-" + snapshot.get("username", "account") + ".json"
        path = self._write_json(name, snapshot)
        if path:
            self.session._say(ACCOUNT_SAVED.format(path=path))

    def _write_json(self, name: str, payload: dict) -> str:
        """Writes the file the student picks and returns its path, or "" when nothing was written."""
        import json

        path, _ = QFileDialog.getSaveFileName(None, "Save FlexWeek file", name, "JSON (*.json)")
        if not path:
            return ""
        try:
            Path(path).write_text(json.dumps(payload, indent=2) + "\n")
        except OSError:
            self.session._say(WRITE_FAILED)
            return ""
        return path

    def _look_path(self) -> Path:
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        return root / "flexweek-look.json"

    def _load_look(self) -> None:
        import json

        self._new_look_notice_seen = set()
        self._new_look_notice_exempt = set()
        path = self._look_path()
        if not path.is_file():
            self._cpu_drawing_version = ""
            self._material_gave_up = False
            return
        try:
            stored = json.loads(path.read_text())
        except OSError, ValueError:
            stored = None
        self._look = sanitize_look(stored)
        self._layout = sanitize_layout(stored.get("layout") if isinstance(stored, dict) else None)
        self._surface = sanitize_surface(stored)
        self._cpu_drawing_version = cpu_drawing.saved_version(stored)
        self._material_gave_up = False
        self._updates = sanitize_updates(stored.get("updates") if isinstance(stored, dict) else None)
        self._zoom = sanitize_zoom(stored.get("zoom") if isinstance(stored, dict) else None)
        self._saved_looks = sanitize_saved(stored.get("saved_looks") if isinstance(stored, dict) else None)
        rail = stored.get("rail") if isinstance(stored, dict) else None
        self._rail_month = not (isinstance(rail, dict) and rail.get("month") is False)
        seen = stored.get("new_look_notice_seen") if isinstance(stored, dict) else None
        if isinstance(seen, list):
            self._new_look_notice_seen = {item for item in seen if isinstance(item, str) and item}
        exempt = stored.get("new_look_notice_exempt") if isinstance(stored, dict) else None
        if isinstance(exempt, list):
            self._new_look_notice_exempt = {item for item in exempt if isinstance(item, str) and item}

    def _save_look(self) -> None:
        import json

        self._carry_look()
        path = self._look_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            body = {
                **self._look,
                "surface": sanitize_surface(self._surface),
                "layout": self._layout,
                "updates": self._updates,
                "zoom": self._zoom,
                "saved_looks": self._saved_looks,
                "rail": {"month": self._rail_month},
                "new_look_notice_seen": sorted(self._new_look_notice_seen),
                "new_look_notice_exempt": sorted(self._new_look_notice_exempt),
            }
            if self._cpu_drawing_version:
                body[cpu_drawing.LOOK_KEY] = self._cpu_drawing_version
            # Settings writes the material object into this file. Keep it when the widgets look saves.
            material = kept_material(path)
            if material is not None:
                body["material"] = material
            path.write_text(json.dumps(body) + "\n")
        except OSError:
            self.session._say("Could not save the look for this device.")

    def _apply_appearance(self) -> None:
        """Set the Animations level from the preference and the look worn."""
        chosen_motion = (self.session.preferences or {}).get("motion")
        self._motion = motion_level(chosen_motion, look_motion(self._worn_look()))
        # Every change to the week comes through here; the Qt effects are set only when the level moves.
        dressed = (self._motion,)
        if dressed != self._dressed:
            self._dressed = dressed
            apply_ui_effects(self._motion)

    def _install_tray(self) -> None:
        tray = QSystemTrayIcon(self._icon, self)
        # A widget menu cannot have this controller as its parent, so the controller holds it.
        menu = QMenu()
        self._tray_menu = menu
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
        if self._save_before_leaving(self._quit_now):
            self._quit_now()

    def _quit_now(self) -> None:
        self._quitting = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        QApplication.quit()

    def _save_before_leaving(self, leave: Callable[[], None], *, again: str = "close FlexWeek again") -> bool:
        """Leave once what is unsaved has reached the server. Returns True when there was nothing to
        wait for and `leave` has not been called; otherwise it saves in the background and calls
        `leave` when done, or stays open and says so when the save fails or takes too long.

        `again` is the action named in that sentence. Closing says to close again. Signing out says
        to sign out again, so the two paths do not tell the student to do the other one.
        """
        session = self.session
        if self._leaving is not None:
            return False
        if session.account is None or not (session._held() or session.parked_unsaved_week()):
            return True
        timer = QTimer(self)
        timer.setInterval(LEAVE_POLL_MS)
        self._leaving = timer
        # Which step each poll takes is the session's (engine/app/src/session/leaving.rs).
        session.client.command({"cmd": "leaving_start", "limit_ms": LEAVE_WAIT_MS, "again": again})

        def stop() -> None:
            timer.stop()
            timer.deleteLater()
            self._leaving = None

        def poll() -> None:
            answer = session.client.command(
                {
                    "cmd": "leaving_poll",
                    "poll_ms": LEAVE_POLL_MS,
                    "held": bool(session._held()),
                    "parked": session.parked_unsaved_week() is not None,
                }
            )
            step = answer["step"]
            if step == "give_up":
                stop()
                session._say(answer["words"])
                self.restore_window()
            elif step == "save":
                session.save()
            elif step == "load":
                session.load_week(session.parked_unsaved_week())
            elif step == "leave":
                stop()
                self._saved_to_leave = True
                try:
                    leave()
                finally:
                    self._saved_to_leave = False

        timer.timeout.connect(poll)
        timer.start()
        return False

    def _on_close(self, event: QCloseEvent) -> None:
        """The close button, from the window's own event or from `close()`: with the tray up and the
        setting on the window only hides; otherwise what is unsaved is saved first, and then the app quits."""
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
        if not self._saved_to_leave and not self._save_before_leaving(self.close):
            event.ignore()
            return
        self._shutdown()
        event.accept()

    def _shutdown(self) -> None:
        """Leave for good, once however many closes arrive: the ring stops, the bridges let go, then quit."""
        if self._shut_down:
            return
        self._shut_down = True
        self._stop_material_ring()
        for bridge in self.findChildren(QObject, "materialBridge"):
            dispose = getattr(bridge, "dispose", None)
            if callable(dispose):
                dispose()
        self._quit_now()

    def _on_key(self, event: QKeyEvent) -> bool:
        """Ctrl+S (Cmd+S) saves; True when this took the key. The QML shell has its own Undo, Redo, More."""
        if self.session.account is None or QApplication.activeModalWidget() is not None:
            return False
        if self._material_current() is None:
            return False
        if event.key() == Qt.Key.Key_S and event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ):
            self._told(self.session.save)
            event.accept()
            return True
        return False
