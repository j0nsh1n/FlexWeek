"""Qt widgets window for the native FlexWeek desktop client."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
import weakref
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from flexweek_engine import SyncService  # type: ignore[import-untyped]
from PySide6.QtCore import (
    QEvent,
    QEventLoop,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPalette,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from backend import clock as wall_clock
from backend.slots import DAY_END_MIN, SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm
from desktop.native import autostart, cpu_drawing, icons
from desktop.native.account_copy import (
    ACCOUNT_SAVED,
    DELETE_ACCOUNT_QUESTION,
    READ_FAILED,
    READ_WEEK_FAILED,
    RECOVERY_FILE,
    RECOVERY_KEEP,
    REPLACE_WEEK_QUESTION,
    WRITE_FAILED,
)
from desktop.native.ambient import FocusAudio
from desktop.native.calendar import (
    CATEGORIES,
    DAY_FULL,
    FLEX_CATEGORIES,
    SETUP_SCHOOL_ID,
    block_family,
    date_for_day,
    day_full_names,
    is_series,
    is_setup_block,
    sunday_due,
    this_week_line,
)
from desktop.native.controller import ROUTINE_STATUS, NativeSession, _late_summary, left_sentence
from desktop.native.custom_look import sanitize_saved
from desktop.native.devices import SyncDot, SyncHost, live_phones, run_off_ui
from desktop.native.feel import Context, apply_feel, context_for, extra_stylesheet, set_current
from desktop.native.fields import announce, week_start_day, week_start_notice
from desktop.native.files import EXPORT_FORMAT, parse_import_payload
from desktop.native.focus import focus_now, phase_duration_ms
from desktop.native.fonts import load_fonts, without_ligatures
from desktop.native.hours.canvas import Drawn, HoursCanvas, plan_placed
from desktop.native.hours.classic import ClassicDay, ClassicWeek
from desktop.native.hours.geometry import Span, drag_step, next_slot
from desktop.native.hours.hand import Create, Gesture, Hand, Move, MoveDate, Place, span_words
from desktop.native.hours.hand import Verdict as HandVerdict
from desktop.native.hours.month import MonthGrid
from desktop.native.hours.rail import MonthCard, Rail
from desktop.native.hours.zoom import ZOOM_KEYS, HoursScroll, sanitize_zoom
from desktop.native.kept import KeptSession
from desktop.native.layouts.base import NARROW_WIDTH, LayoutView, Scene
from desktop.native.layouts.empty import EmptyWeek, start_here_week
from desktop.native.layouts.registry import options_for, sanitize_layout, sanitize_surface, tokens_for
from desktop.native.layouts.views import VIEW_CLASSES
from desktop.native.look import (
    MENU_EDGE,
    design_look,
    effective_look,
    look_measures,
    look_motion,
    pack_stylesheet,
    resolved_palette,
    sanitize_look,
    text_scale,
    toast_colours,
)
from desktop.native.material.theme import kept_material, read_letter_keys, read_shortcuts
from desktop.native.menus import Menu, mark, menu_colours
from desktop.native.motion import (
    DRIFT_PX,
    apply_ui_effects,
    fade_away,
    fade_through,
    hold_picture,
    motion_level,
    moves,
    raise_pictures,
    retake_slide,
    settle,
    slide_down,
    slide_view,
    sliding_in,
    switch_page,
    trim_picture,
)
from desktop.native.outside import OutsideWatch, differs
from desktop.native.remind import REMINDER_POLL_MS, clock_parts
from desktop.native.reuse import (
    due_point,
    late_from_start,
    late_locked_line,
    planner_title,
    restore_point_label,
    running_late_refusal,
    week_label,
)
from desktop.native.settings import (
    AboutDialog,
    AccountDialog,
    AlarmRingDialog,
    FocusPanel,
    HelpDialog,
    RestoreDialog,
    TransferPreviewDialog,
    UpdateDialog,
)
from desktop.native.settings_copy import sync_state
from desktop.native.setup_steps import REMINDERS, SETUP_VERSION, STYLE, SetupState
from desktop.native.sheet_rules import moved_day_names, same_weekday, turn_days_keeping_weekdays
from desktop.native.sound import Bell
from desktop.native.spotify import LISTENING, STARTING, SpotifyPlayer, open_in_app
from desktop.native.tokens import SHADOW_SMALL, SPACING
from desktop.native.tones import FALLBACK
from desktop.native.update import (
    RELEASE_PAGE,
    due_for_check,
    sanitize_updates,
)
from desktop.native.updater import Updater, apply_update
from desktop.native.version import VERSION
from desktop.native.weekmodel import (
    added_words,
    build_week,
    clock_text,
    dated_words,
    hhmm_text,
    homework_time_sentence,
    set_clock_24h,
)
from desktop.native.widgets import (
    REPLAN_TIP,
    AddMenu,
    AlertStrip,
    AvailabilityDialog,
    BlockDialog,
    ChooseTimeDialog,
    ConfirmSheet,
    Dialog,
    EndsLayout,
    FittedLabel,
    FlowLayout,
    HomeworkDialog,
    LateDialog,
    MoreButton,
    PlanButton,
    PlanReview,
    PreviewDialog,
    RoutineDialog,
    SchoolHoursDialog,
    Segment,
    SegmentTrack,
    Toast,
    UnfinishedPanel,
    add_heading,
    confirm,
    control_art,
    dim_window,
    drop_waiting_dim,
    fit_buttons,
    keyboard_focus_rings,
    overdue_unfinished,
    steady_wheel,
    swatch,
    use_app_style,
)

WINDOW_SIZE = (1280, 800)
# The smallest window FlexWeek is for: at 800 the top bar still fits and nothing is cut in half.
WINDOW_MIN_WIDTH = 800
# The longest the old week's picture waits for the next one before it fades anyway.
TRAVEL_WAIT_MS = 900
# Greyed while the session is busy, but only once it has been busy this long: a plan takes a few
# milliseconds, and greying for them flashed the whole top bar (Grok Bot's 0.17.0 audit, T7). They
# take no clicks, keys or shortcuts from the moment it is busy (BusyGuard).
BUSY_LOOK_MS = 250
# How often the window looks for another program's change to its database: one small file read each
# time, and a look inside only after a commit.
OUTSIDE_CHECK_MS = 2000
# Boxes that keep Ctrl+Z for the text typed in them.
EDITABLE = (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)
# A shared one-key shortcut is the bare key: with Shift, Ctrl, Alt or Meta it is something else.
KEY_MODIFIERS = (
    Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
)
BUSY_BUTTONS = (
    "addFixed",
    "addHomework",
    "addButton",
    "addArrow",
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
    "restoreButton",
    "accountButton",
    "openSpotify",
    "checkUpdates",
    "moreButton",
)
# The views in the order the top bar's segments show them, which a change of view slides along.
VIEW_ORDER = ("day", "week", "month")
# The week list for screen readers opens over the grid, so the grid never moves. More and
# Ctrl+Shift+L are the way in; the list floats at this width (the whole planner on a narrow window).
WEEK_LIST_NAME = "Week as a list"
WEEK_LIST_PANEL_WIDTH = 360


class LeftChip(QFrame):
    """The overdue card. It says when its width changes, so the window can move its buttons."""

    resized = Signal()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.resized.emit()


class ClickyTitle(FittedLabel):
    """The week range in the bar: a click opens the mini month, which is not on the rail."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, minimum: int = 96) -> None:
        super().__init__(parent, minimum)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)
PLAN_LABEL = "Plan my homework"
SUGGEST_LABEL = "Suggest times"
PLAN_TIP = (
    "Find a time for homework that has none, around your fixed times and before it's due. Homework "
    "that already has a time keeps it."
)
SUGGEST_TIP = "Give homework without a time a suggested time. Drag any of them somewhere else if you like."
NOTHING_UNFINISHED = "None left"
QUICK_FOCUS_TIP = (
    "Open the focus timer, ready to start {minutes} minutes without picking homework. "
    "Change its length in Settings > Focus."
)
# The More menu's submenu, named for what it holds (decision 22 of 0.17); it was "Advanced".
EDIT_MENU = "Undo, copy and save"
EDIT_HEADING = "Edit"
HELP_HEADING = "Help and info"
ACCOUNT_HEADING = "Account"
# Unfinished's row while there is nothing under it, beside its greyed name.
NONE_UNFINISHED = "None left"
# The icon on each row of More, by the object name of the button the row presses.
MORE_ICONS = {
    "runningLate": "clock",
    "unfinishedOpen": "list-todo",
    "weekListRow": "list",
    "routinesButton": "repeat",
    "quickFocusAction": "timer",
    "openSpotify": "circle-play",
    "replanAll": "calendar-sync",
    "undoButton": "undo-2",
    "redoButton": "redo-2",
    "copyBlock": "copy",
    "pasteBlock": "clipboard-paste",
    "duplicateBlock": "copy-plus",
    "copyDay": "calendar-days",
    "saveButton": "save",
    "restoreButton": "archive-restore",
    "reloadWeek": "rotate-ccw",
    "helpButton": "circle-question-mark",
    "aboutButton": "info",
    "signOut": "log-out",
}
# Hover words for More and its submenu, by the object name of the button each action presses.
MORE_TIPS = {
    "addHomework": (
        "Add an assignment with its due date and how long it will take. FlexWeek finds time for it."
    ),
    "schoolHours": "Set the days and times you're at school, so nothing is planned then.",
    "addFixed": (
        "Add something that happens at a set time, like practice or a lesson. Homework is planned around it."
    ),
    "runningLate": (
        "Behind today? Say how late you are, and FlexWeek moves the rest of today's homework later."
    ),
    "unfinishedOpen": "Overdue and earlier-week homework that still needs time. Plan it into this week.",
    "weekListRow": "Every block this week, day by day, in time order. Ctrl+Shift+L",
    "routinesButton": "Save this week's fixed times as a routine, or add a saved routine to a week.",
    "openSpotify": "Open the Spotify link from Settings in the Spotify app.",
    "replanAll": REPLAN_TIP,
    "undoButton": "Undo your last change. Ctrl+Z",
    "redoButton": "Redo the change you just undid. Ctrl+Y",
    "copyBlock": "Copy the selected block to paste into another day. Ctrl+C",
    "pasteBlock": "Paste what you copied into the selected day, with a preview first. Ctrl+V",
    "duplicateBlock": "Make a copy of the selected block, with a preview first. Ctrl+D",
    "copyDay": "Copy every block on the selected day to paste into another day.",
    "saveButton": "Save now. FlexWeek already saves after every change. Ctrl+S",
    "restoreButton": (
        "Save a copy of this week, or go back to an earlier one. FlexWeek keeps a restore point "
        "before big changes."
    ),
    "reloadWeek": "Load this week again as it's saved. Use it if something looks out of date.",
    "helpButton": "What each screen is for, and the keyboard shortcuts.",
    "aboutButton": "The version, and where your plans are saved.",
    "signOut": "Sign out on this computer. Your plans stay saved in your account.",
}
# Why an action is greyed, when the reason is not simply that FlexWeek is busy.
GREYED_TIPS = {
    "unfinishedOpen": NOTHING_UNFINISHED,
    "weekListRow": "Open the week to use the week as a list.",
    "undoButton": "Nothing to undo yet.",
    "redoButton": "Nothing to redo.",
    "pasteBlock": "Copy a block or a day first.",
    "runningLate": "Open this week to use Running late.",
}
WAIT_TIP = "Saving your last change… this will work in a moment."
PLANNING_TIP = "Planning… one moment."
CONFLICT_TIP = "This week changed in another window. Choose More > Reload this week, then try again."
SIGN_OUT_QUESTION = "Your week is saved on {where}, under this account. Sign in again to see it."
RECOVERY_CHOOSE = "Choose where to save"
# What they say on a top bar with no room for the whole words.
PLAN_SHORT = "Plan homework"
# The last of #83's steps: Plan my homework, Plan homework, then this.
PLAN_TINY = "Plan"
SUGGEST_SHORT = "Suggest"
# The top bar's icons, the larger of the system's two sizes (decision 7).
BAR_ICON_PX = 20
# Between the week's date and the view switcher beside it: at 6 px they ran together at Large text (#84).
TITLE_SWITCHER_GAP = 16
# The pages Material 3 answers for, as its own screens.
MATERIAL_ACCOUNT_PAGES = ("authPage", "recoveryPage", "setupPage")
# Pages that the draw-error page stands in for when Material cannot be drawn at all.
DRAW_ERROR_COVERS = ("weekPage", *MATERIAL_ACCOUNT_PAGES)
# Long enough for the student to read that the update installed before the window goes.
UPDATE_QUIT_MS = 1200
# How long after the last change the week saves itself. Long enough that dragging a block does not
# post on every pixel, short enough that closing the laptop straight after a change keeps it.
AUTOSAVE_AFTER_MS = 1500
# A failed save keeps its payload and its operation id, so trying again writes the same thing once.
AUTOSAVE_RETRY_MS = 6000
AUTOSAVE_TICK_MS = 500
LAYOUT_TICK_MS = 20_000
# Leaving the app waits this long, checking this often, for what is unsaved to reach the server.
LEAVE_WAIT_MS = 5000
LEAVE_POLL_MS = 100
# Homework named on a Find a new time notice before the rest is counted.
NOTICE_LINES = 3




class BusyGuard(QObject):
    """Takes no clicks, keys or shortcuts on the buttons it watches while the session is busy, from
    the first moment: they are greyed only after BUSY_LOOK_MS."""

    SWALLOWED = (
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.Shortcut,
    )

    def __init__(self, parent: QObject, busy: Callable[[], bool]) -> None:
        super().__init__(parent)
        self._busy = busy

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        return event.type() in self.SWALLOWED and self._busy()


class LastInput(QObject):
    """Whether the student's last press was a key or the pointer, so keyboard focus put back on the
    week is shown with its ring after a key and without one after a click. One for the whole
    application: a filter for each window slowed every event down by the number of windows made."""

    _shared: LastInput | None = None

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.keyboard = False
        QApplication.instance().installEventFilter(self)

    @classmethod
    def shared(cls) -> LastInput:
        if cls._shared is None or not isValid(cls._shared):
            cls._shared = cls(QApplication.instance())
        return cls._shared

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            self.keyboard = True
        elif kind == QEvent.Type.MouseButtonPress:
            self.keyboard = False
        return False


class _BarStrip(QWidget):
    """Retro's title-bar colour behind the top bar (T14): sized to the bar's rows across the page, under
    every widget on it, and passing clicks through. Hidden for every other design."""

    def __init__(self, page: QWidget, bar: QLayout) -> None:
        super().__init__(page)
        self._bar = bar
        self.setObjectName("appBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()
        page.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt virtual
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show):
            self.follow()
        return False

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt virtual
        self.follow()
        super().showEvent(event)

    def follow(self) -> None:
        page = self.parentWidget()
        if page is None:
            return
        bottom = self._bar.geometry().bottom() + 1 + page.layout().contentsMargins().top()
        self.setGeometry(0, 0, page.width(), max(0, bottom))
        self.lower()


class NativeWindow(QMainWindow):
    def __init__(
        self,
        origin: str,
        icon: QIcon | None = None,
        parent: QWidget | None = None,
        kept: KeptSession | None = None,
        sync: SyncHost | None = None,
    ) -> None:
        super().__init__(parent)
        application = QApplication.instance()
        if isinstance(application, QApplication):
            steady_wheel(application)
            keyboard_focus_rings(application)
            use_app_style(application)
        # main() has loaded them already; a window made anywhere else, as in the tests, is drawn alike.
        load_fonts()
        self.session = NativeSession(origin, self, kept)
        self.session.use_sync_host(sync)
        # The week's first day is kept on this computer, not on the account; the session is told it.
        self.session.follow_first_weekday(week_start_day())
        week_start_notice().changed.connect(self._on_week_start)
        self._instance_server: QLocalServer | None = None
        self.setWindowTitle("FlexWeek")
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
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(*WINDOW_SIZE)
        self._stack = QStackedWidget(self)
        # The Animations level, set from the look in _apply_appearance, and the picture of the planner
        # held while the student moves to another week.
        self._motion = "normal"
        # What the window was last dressed in, so a change that leaves the look alone skips restyling.
        self._dressed: tuple = ()
        self._travel_picture: QLabel | None = None
        self._travel_direction = 0
        # What the planner last showed (_planner_now), so a change of view, My day or design is seen.
        self._planner_shown: tuple | None = None
        self._stack.setObjectName("nativeStack")
        self.setCentralWidget(self._stack)
        self._more_pairs = []
        self._layout = sanitize_layout(None)
        # Material 3 is the only style. The QML page is built the first time it is shown.
        self._surface = sanitize_surface(None)
        self._material_page = None
        self._account_showing = False
        self._material_gave_up = False
        # The app version that must draw Material on the CPU, or "" when the graphics card may be used.
        self._cpu_drawing_version = ""
        self._relaunching = False
        self._day_mode = False
        self._opened_on_preference = False
        # Number keys and Letter keys as the look file holds them, and the file's stamp when read.
        self._key_stamp: tuple[int, int] | None = None
        self._key_values = (True, False)
        self._views: dict[str, LayoutView] = {}
        self._updates = sanitize_updates(None)
        self._zoom: dict[str, int] = {}
        # The student's own looks, kept by name (custom_look.py); Settings will list them.
        self._saved_looks: list[dict] = []
        self._new_look_notice_seen: set[str] = set()
        self._new_look_notice_exempt: set[str] = set()
        self._has_saved_design_look = False
        self._shown: tuple | None = None
        self._hours_week: tuple | None = None
        self._update_asked = False
        self._update_dialog: UpdateDialog | None = None
        self._update_on_material = False
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
        self._block_spare: BlockDialog | None = None
        self._block_spare_account: str | None = None
        self._block_prepare_scheduled = False
        # What a student typed into a new Add sheet that Esc closed, by kind, for the next plain Add of that
        # kind: plain values only (never a sheet), the days a drag gave a homework, and the account it is for.
        # Each with the open week its day numbers count from.
        self._kept_adds: dict[str, tuple[dict, list[int] | None, str]] = {}
        self._kept_adds_account: str | None = None
        self._leaving: QTimer | None = None
        self._saved_to_leave = False
        # A chip let go on another date while a save is under way, moved once that save has landed.
        self._date_waiting: MoveDate | None = None
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
        self._month_revealed: tuple | None = None
        self._changed_ms = 0
        self._last_try_ms = 0
        self._autosave = QTimer(self)
        self._autosave.setInterval(AUTOSAVE_TICK_MS)
        self._autosave.timeout.connect(self._autosave_tick)
        self._autosave.start()
        self._build_week()
        self._build_focus_audio()
        self.session.account_changed.connect(self._on_account)
        self.session.recovery_codes.connect(self._show_recovery)
        self.session.week_changed.connect(self._on_week)
        self.session.status.connect(self._on_status)
        self._busy_guard = BusyGuard(self, lambda: self.session.busy)
        self._last_input = LastInput.shared()
        self._last_input.keyboard = False
        self._relaying = False
        QApplication.instance().focusChanged.connect(self._watch_field)
        self._busy_look = QTimer(self)
        self._busy_look.setSingleShot(True)
        self._busy_look.setInterval(BUSY_LOOK_MS)
        self._busy_look.timeout.connect(self._grey_while_busy)
        self.session.busy_changed.connect(self._on_busy)
        self.session.save_finished.connect(self._on_save_finished)
        self.session.hand_placed.connect(self._say_when_saved)
        self.session.repeats_kept.connect(self._say_repeats_kept)
        self.session.plan_conflicts.connect(self._on_plan_conflicts)
        self.session.planned.connect(self._on_planned)
        self._late_dialog: LateDialog | None = None
        # The late start accepted but not stored yet, and the sentence its save will confirm.
        self._late_waiting: tuple[str, str] | None = None
        self._quitting = False
        self._tray_icon: QSystemTrayIcon | None = None
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
        for hours in (self.week_table.scroll, self.day_view.scroll):
            hours.restore(self._zoom)
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
        # A day screen is about the minute, so it is looked at again well inside one.
        self._filled_at_clock: tuple | None = None
        self._layout_tick = QTimer(self)
        self._layout_tick.setInterval(LAYOUT_TICK_MS)
        self._layout_tick.timeout.connect(self._refresh_layout)
        self._layout_tick.timeout.connect(self._count_down)
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
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        # After the window exists, so a kept session opens the week the ordinary way.
        QTimer.singleShot(0, self.session.resume)

    def _autosave_tick(self) -> None:
        """Save the week without being asked.

        Save stopped being a button, so this has to be dependable rather than clever. It waits for
        the student to stop changing things, refuses while a request is in flight, and never touches
        a week whose save came back 409: a conflict means another window wrote this week, and
        answering that is the student's decision, not a timer's.
        """
        session = self.session
        if session.account is None or session.busy or session.conflict:
            return
        # Time since the last change, not the time of day: a clock set back must not hold a save.
        now = int(time.monotonic() * 1000)
        if session.pending_save is not None:
            # A save that failed. Its payload and operation id are kept, so this writes the same
            # thing once however many times it is tried.
            if now - self._last_try_ms >= AUTOSAVE_RETRY_MS:
                self._last_try_ms = now
                session.save()
            return
        if not session.dirty or now - self._changed_ms < AUTOSAVE_AFTER_MS:
            return
        self._last_try_ms = now
        session.save()

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
        for index in range(self._stack.count()):
            page = self._stack.widget(index)
            if page.objectName() == name:
                leaving = self._stack.currentWidget()
                if page is not leaving:
                    # What the toast said was about the page the student is leaving.
                    self.toast.hide()
                switch_page(self._stack, page, self._motion)
                return

    def _week_keys(self, enabled: bool) -> None:
        shortcut = getattr(self, "_week_list_shortcut", None)
        if shortcut is not None:
            shortcut.setEnabled(enabled)

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
                    page._quick.setFocus(Qt.FocusReason.OtherFocusReason)
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
        if self._surface == "material" and self._material_gave_up:
            self._show_draw_error()
            return False
        self._show_page("weekPage")
        # Only the tests' Widgets start reaches the Widgets week. The Material page built for sign-in
        # goes, as it was never built before: left behind the week, its window-wide keys took Esc and
        # Ctrl+Shift+L, and its bridges answered changes no one saw.
        if self._material_page is not None:
            self._drop_partial_material()
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
        self._material_page = page
        # Material's focus rules (hold reminders, finish the block) ask whether Material is in use.
        self.session.material_owns = self._material_owns
        self._stack.addWidget(page)
        return page

    def _drop_partial_material(self) -> None:
        """A failed build must not leave a half-made page in the stack or as a child."""
        self._stop_material_ring()
        page = self._material_page
        self._material_page = None
        doomed: list[QObject] = []
        if page is not None:
            doomed.append(page)
        doomed.extend(self.findChildren(QWidget, "materialPage"))
        doomed.extend(self.findChildren(QObject, "materialBridge"))
        seen: set[int] = set()
        # The bridges are the window's own children, not the page's: cut their session signals
        # before the deleteLater below, so a week change on this turn finds no listener.
        for bridge in self.findChildren(QObject, "materialBridge"):
            dispose = getattr(bridge, "dispose", None)
            if callable(dispose):
                dispose()
        for item in doomed:
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, QWidget) and self._stack.indexOf(item) >= 0:
                self._stack.removeWidget(item)
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
            self._week_keys(False)
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
        page = self.findChild(QWidget, "drawErrorPage")
        if page is None:
            page = QWidget()
            page.setObjectName("drawErrorPage")
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
            box.addWidget(line)
            box.addWidget(version)
            box.addLayout(row)
            self._stack.addWidget(page)
        if self._stack.currentWidget() is not page:
            self._stack.setCurrentWidget(page)

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
        self._week_keys(False)
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
        page = self._material_page
        if page is None or not page._ready or not self._material_owns():
            return
        if self._stack.currentWidget() is not page:
            return
        page.bridge.refresh()

    def _build_week(self) -> None:
        page = QWidget()
        page.setObjectName("weekPage")
        layout = QVBoxLayout(page)
        # Where you are at the left, what to show and do at the right; on a narrow window the second
        # goes under the first rather than both being cut.
        # The date keeps 16 px from the view switcher beside it, even where that shortens Plan (#84).
        bar = EndsLayout(between=TITLE_SWITCHER_GAP)
        where = QHBoxLayout()
        self._bar_views = QHBoxLayout()
        bar.add_group(where)
        bar.add_group(self._bar_views)
        # ‹ › Today, then where you are, said once and said large. After the title, the arrows moved
        # sideways with its width on every switch between Day, Week and Month (decision 11).
        self.prev_nav = QPushButton()
        self.prev_nav.setObjectName("prevWeek")
        self.prev_nav.setToolTip("Previous week")
        self.prev_nav.clicked.connect(self._go_previous)
        self.next_nav = QPushButton()
        self.next_nav.setObjectName("nextWeek")
        self.next_nav.setToolTip("Next week")
        self.next_nav.clicked.connect(self._go_next)
        today = QPushButton("Today")
        today.setObjectName("todayWeek")
        today.setToolTip("Jump to today")
        today.clicked.connect(self._go_today)
        today.setProperty("quiet", True)
        for arrow, name in ((self.prev_nav, "chevron-left"), (self.next_nav, "chevron-right")):
            arrow.setProperty("quiet", True)
            arrow.setIconSize(QSize(BAR_ICON_PX, BAR_ICON_PX))
            icons.tint(arrow, name)
            where.addWidget(arrow)
        where.addWidget(today)
        where.addSpacing(SPACING[1])
        # Thirteen buttons of equal weight and no title at all was the clutter: nothing told the eye
        # where to land.
        self.week_title = ClickyTitle()
        self.week_title.setObjectName("weekTitle")
        self.week_title.clicked.connect(self._toggle_week_month)
        where.addWidget(self.week_title)
        self.week_title_mark = QPushButton()
        self.week_title_mark.setObjectName("weekTitleMark")
        self.week_title_mark.setProperty("quiet", True)
        self.week_title_mark.setIconSize(QSize(BAR_ICON_PX, BAR_ICON_PX))
        icons.tint(self.week_title_mark, "chevron-down")
        self.week_title_mark.setAccessibleName("Pick a week")
        self.week_title_mark.clicked.connect(self._toggle_week_month)
        where.addWidget(self.week_title_mark)
        # One control, not four loose buttons: switching view is one decision.
        segments = SegmentTrack()
        segments.setObjectName("segments")
        segment_row = QHBoxLayout(segments)
        segment_row.setContentsMargins(0, 0, 0, 0)
        segment_row.setSpacing(2)
        for view, label, tip in (
            ("day", "Day", "One day as a list"),
            ("week", "Week", "The week you're planning"),
            ("month", "Month", "The month as a calendar"),
        ):
            button = Segment(label)
            button.setObjectName(f"view{view.title()}")
            button.setCheckable(True)
            button.setToolTip(tip)
            button.clicked.connect(lambda checked=False, value=view: self._choose_view(value))
            segments.add(button)
        my_day = Segment("My day")
        my_day.setObjectName("viewMyDay")
        my_day.setCheckable(True)
        my_day.setToolTip("Watch today")
        my_day.clicked.connect(self._enter_day)
        segments.add(my_day)
        self._bar_views.addWidget(segments)
        self.account_name = QLabel()
        self.account_name.setObjectName("accountName")
        self.account_name.setVisible(False)
        self._bar_views.addWidget(self.account_name)
        sign_out = QPushButton("Sign out")
        sign_out.setObjectName("signOut")
        sign_out.clicked.connect(self._log_out)
        sign_out.setVisible(False)
        self._bar_views.addWidget(sign_out)
        self._top_bar = bar
        layout.addLayout(bar)
        # Retro's title bar (T14) is a strip painted behind the bar, not a box around it, so the bar
        # keeps its place on the page for every other design.
        self._bar_strip = _BarStrip(page, bar)
        # Everything between the bar and the calendar is for planning, so a day screen can put it away.
        self.plan_chrome = QWidget()
        self.plan_chrome.setObjectName("planChrome")
        chrome = QVBoxLayout(self.plan_chrome)
        chrome.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plan_chrome)
        # Wrapping, because twenty buttons in one row made the window wider than any laptop screen.
        actions = FlowLayout()
        self.add_menu = AddMenu(self)
        self.add_menu.homework_requested.connect(self._add_homework)
        self.add_menu.fixed_requested.connect(self._add_fixed)
        self.add_menu.school_requested.connect(self._school_hours)
        self.add_menu.category_chosen.connect(self._add_from_chip)
        for action_name, tip in (
            ("addMenuHomework", "addHomework"),
            ("addMenuFixed", "addFixed"),
            ("addMenuSchool", "schoolHours"),
        ):
            self.add_menu.findChild(QAction, action_name).setToolTip(MORE_TIPS[tip])
        # The one filled button on the bar. A click adds homework, the thing a student adds most; the
        # arrow beside it offers the rest.
        add_button = QPushButton("Add")
        add_button.setObjectName("addButton")
        add_button.setToolTip(MORE_TIPS["addHomework"])
        add_button.clicked.connect(self._add_now)
        add_arrow = QPushButton()
        add_arrow.setObjectName("addArrow")
        icons.tint(add_arrow, "chevron-down")
        add_arrow.setAccessibleName("More ways to add")
        add_arrow.setToolTip("Add fixed time or school hours, or pick a type to drag onto the calendar.")
        add_arrow.setMenu(self.add_menu)
        add_split = QHBoxLayout()
        add_split.setSpacing(0)
        add_split.addWidget(add_button)
        add_split.addWidget(add_arrow)
        # Kept so the shortcuts and the tests that press them still have something to
        # press; the Add menu reaches the same actions.
        add_fixed = QPushButton("Add fixed time")
        add_fixed.setObjectName("addFixed")
        add_fixed.clicked.connect(self._add_fixed)
        add_fixed.setVisible(False)
        add_homework = QPushButton("Add homework")
        add_homework.setObjectName("addHomework")
        add_homework.clicked.connect(self._add_homework)
        add_homework.setVisible(False)
        school_hours = QPushButton("School hours")
        school_hours.setObjectName("schoolHours")
        school_hours.clicked.connect(self._school_hours)
        school_hours.setVisible(False)
        undo = QPushButton("Undo")
        undo.setObjectName("undoButton")
        undo.clicked.connect(self.session.undo)
        redo = QPushButton("Redo")
        redo.setObjectName("redoButton")
        redo.clicked.connect(self._redo_with_focus)
        solve = PlanButton(PLAN_LABEL, PLAN_SHORT)
        solve.setObjectName("solveButton")
        # Quiet accent words: Add stays the only filled bar action.
        solve.setProperty("quiet", True)
        solve.clicked.connect(self._plan_with_left_over)
        replan = QPushButton("Replan all my homework")
        replan.setObjectName("replanAll")
        replan.clicked.connect(lambda: self._plan_with_left_over(everything=True))
        save = QPushButton("Save this week now")
        save.setObjectName("saveButton")
        save.clicked.connect(self.session.save)
        retry = QPushButton("Retry save")
        retry.setObjectName("retrySave")
        retry.clicked.connect(self.session.retry_save)
        reload_week = QPushButton("Reload this week")
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
        week_list = QPushButton(WEEK_LIST_NAME)
        week_list.setObjectName("weekListRow")
        week_list.setAccessibleName(WEEK_LIST_NAME)
        week_list.clicked.connect(self._toggle_week_access_list)
        late = QPushButton("Running late")
        late.setObjectName("runningLate")
        late.clicked.connect(self._open_late)
        availability = QPushButton("Study hours")
        availability.setObjectName("availabilityButton")
        availability.clicked.connect(self._open_availability)
        restore = QPushButton("Copies of this week…")
        restore.setObjectName("restoreButton")
        restore.clicked.connect(self._open_restore)
        account = QPushButton("Account")
        account.setObjectName("accountButton")
        account.clicked.connect(self._open_account)
        updates = QPushButton("Check for updates")
        updates.setObjectName("checkUpdates")
        updates.clicked.connect(lambda: self._check_updates(asked=True))
        spotify = QPushButton("Open Spotify link")
        spotify.setObjectName("openSpotify")
        spotify.clicked.connect(self._open_spotify)
        more = MoreButton()
        more.setObjectName("moreButton")
        more.setProperty("quiet", True)
        overflow = QWidget(page)
        overflow.setObjectName("moreOverflow")
        overflow.hide()
        more_menu = Menu(more)
        self._more_pairs = []
        self._spotify_action = None
        self.quick_focus = QPushButton("Quick focus")
        self.quick_focus.setObjectName("quickFocusAction")
        self.quick_focus.clicked.connect(self._quick_focus)
        # Adding moved to the Add button's menu.
        school_hours.setParent(overflow)
        self._groups = (
            ("Planning", (late, unfinished, week_list, routines, self.quick_focus, spotify, replan)),
        )
        self._advanced = (
            undo,
            redo,
            copy_block,
            paste_block,
            duplicate,
            copy_day,
            restore,
            reload_week,
        )
        save.setParent(overflow)
        save.hide()
        for leftover in (availability, account, updates):
            leftover.setParent(overflow)
            leftover.hide()
        for index, (heading, buttons) in enumerate(self._groups):
            if index:
                more_menu.addSeparator()
            add_heading(more_menu, heading)
            for button in buttons:
                if button.parent() is not overflow:
                    button.setParent(overflow)
                action = mark(more_menu.addAction(button.text()), MORE_ICONS[button.objectName()])
                action.triggered.connect(button.click)
                self._more_pairs.append((action, button))
                if button is spotify:
                    self._spotify_action = action
        # Every group under a heading of its own; only Planning had one (T23 of the 0.17.0 audit).
        more_menu.addSeparator()
        add_heading(more_menu, EDIT_HEADING)
        advanced_menu = more_menu.add_menu(EDIT_MENU, "pencil")
        for button in self._advanced:
            if button.parent() is not overflow:
                button.setParent(overflow)
            action = mark(advanced_menu.addAction(button.text()), MORE_ICONS[button.objectName()])
            action.triggered.connect(lambda _=False, pressed=button: self._told(pressed.click))
            self._more_pairs.append((action, button))
        help_button = QPushButton("Help")
        help_button.setObjectName("helpButton")
        help_button.clicked.connect(self._open_help)
        about = QPushButton("About FlexWeek")
        about.setObjectName("aboutButton")
        about.clicked.connect(self._open_about)
        # Its own line, so Help and About stay together and Sign out stays apart (Decision 22).
        more_menu.addSeparator()
        add_heading(more_menu, HELP_HEADING)
        for button in (help_button, about, sign_out):
            if button.parent() is not overflow:
                button.setParent(overflow)
            button.hide()
            if button is sign_out:
                # Set apart from Help and About: leaving is not one of the things to look up.
                more_menu.addSeparator()
                add_heading(more_menu, ACCOUNT_HEADING)
            action = mark(more_menu.addAction(button.text()), MORE_ICONS[button.objectName()])
            action.triggered.connect(button.click)
            self._more_pairs.append((action, button))
        more_menu.aboutToShow.connect(self._sync_more_menu)
        more.setMenu(more_menu)
        self.more_menu = more_menu
        # The week saves itself. Ctrl+S still flushes. Retry appears only when a save has failed.
        self.sync_dot = SyncDot()
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(1000)
        self._sync_timer.timeout.connect(self._sync_tick)
        if self._sync is not None:
            self._sync_timer.start()
        self._bar_views.addLayout(add_split)
        for shown in (solve, retry, more):
            self._bar_views.addWidget(shown)
        self._bar_views.addWidget(self.sync_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self._retry_bar_index = self._bar_views.indexOf(retry)
        self.solve_button = solve
        self.more_button = more
        self.week_list_row = week_list
        for hidden in (add_homework, add_fixed, save, self.quick_focus):
            actions.addWidget(hidden)
        for hidden in (add_homework, add_fixed, save, self.quick_focus):
            hidden.setVisible(False)
        chrome.addLayout(actions)
        self.retry_button = retry
        self._sync_retry_bar_slot()
        self.clipboard_summary = QLabel("Nothing copied")
        self.clipboard_summary.setObjectName("clipboardSummary")
        chrome.addWidget(self.clipboard_summary)
        self.focus_panel = FocusPanel()
        self.focus_panel.quick_requested.connect(self._quick_focus)
        self.focus_panel.screen_requested.connect(self._open_focus_screen)
        self.focus_panel.finished_requested.connect(self.session.finish_focused_homework)
        self.focus_panel.break_requested.connect(self.session.take_focus_break)
        self.focus_panel.more_requested.connect(self.session.add_focus_time)
        # Today's app keeps a rail left of its Day and Week; the notices and the planner are beside it.
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._rail_row = body
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        self._column = column
        column.addWidget(self.focus_panel)
        # Neither is inside the planning chrome, which a design of its own hides: More > Unfinished
        # and Plan can be pressed from any design, and what they show is the point of pressing them.
        self.unfinished_panel = UnfinishedPanel()
        # Opened by the student, from More: a change to the week refreshes it, never folds it.
        self._unfinished_opened = False
        self.unfinished_panel.plan_requested.connect(self._plan_unfinished)
        self.unfinished_panel.focus_requested.connect(lambda item_id: self._start_focus(item_id, None))
        self.unfinished_panel.delete_requested.connect(self._delete_homework)
        self.unfinished_panel.collapsed.connect(self._collapse_unfinished)
        column.addWidget(self.unfinished_panel)
        # Item 1b: after Plan, homework whose time was in an earlier week and never ticked done. Plan
        # never moves it on its own; the student says which.
        self.left_chip = LeftChip()
        self.left_chip.setObjectName("leftChip")
        chip_column = QVBoxLayout(self.left_chip)
        # The words and their buttons share one line while the card is wide enough for both whole. When
        # it is not, the buttons move to the row under the words (see _fit_left_chip).
        self._chip_line = QHBoxLayout()
        chip_column.addLayout(self._chip_line)
        self._chip_below = QWidget()
        self._chip_below.setObjectName("leftChipBelow")
        # The window's sheet paints a plain widget's background; the row belongs to the card's white.
        self._chip_below.setStyleSheet("QWidget#leftChipBelow { background: transparent; }")
        self._chip_below_row = QHBoxLayout(self._chip_below)
        # Under the words, not under the icon.
        self._chip_below_row.setContentsMargins(16 + self._chip_line.spacing(), 0, 0, 0)
        self._chip_below_row.addStretch(1)
        chip_column.addWidget(self._chip_below)
        self._chip_below.hide()
        self._chip_wrapped = False
        self.left_chip_icon = QLabel()
        self.left_chip_icon.setObjectName("leftChipIcon")
        self.left_chip_icon.setFixedSize(16, 16)
        self._chip_line.addWidget(self.left_chip_icon)
        self.left_chip_text = QLabel()
        self.left_chip_text.setObjectName("leftChipText")
        self.left_chip_text.setWordWrap(True)
        self._chip_line.addWidget(self.left_chip_text, 1)
        plan_them = QPushButton("Plan into this week")
        plan_them.setObjectName("leftPlan")
        plan_them.setProperty("tonal", True)
        plan_them.clicked.connect(self._plan_left)
        self._chip_line.addWidget(plan_them)
        did_these = QPushButton("Mark as finished")
        did_these.setObjectName("leftDone")
        did_these.setProperty("outlined", True)
        did_these.clicked.connect(self._did_left)
        self._chip_line.addWidget(did_these)
        self.left_chip.resized.connect(self._fit_left_chip)
        self.left_chip.hide()
        column.addWidget(self.left_chip)
        self.plan_review = PlanReview()
        self.plan_review.replan_requested.connect(lambda: self._plan_with_left_over(everything=True))
        self.plan_review.allow_split_requested.connect(self.session.allow_splitting)
        self.alert_strip = AlertStrip()
        self.alert_strip.handled.connect(self._reminder_handled)
        column.addWidget(self.alert_strip)
        self.planner = QStackedWidget()
        self.planner.setObjectName("plannerStack")
        # The list opens over the grid from More or Ctrl+Shift+L, so Tab never moves the week.
        self.week_list_panel = QFrame(page)
        self.week_list_panel.setObjectName("weekListPanel")
        self.week_list_panel.hide()
        panel_layout = QVBoxLayout(self.week_list_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        # Where Esc puts the keyboard back: whatever had it when the list opened.
        self._week_list_return: QWidget | None = None
        self.week_access_list = QListWidget()
        self.week_access_list.setObjectName("weekAccessList")
        self.week_access_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.week_access_list.setAccessibleName("Week as a list")
        self.week_access_list.setAccessibleDescription(
            "Every block this week, day by day, in time order. Press Enter to open one."
        )
        panel_layout.addWidget(self.week_access_list)
        self.week_access_list.itemActivated.connect(self._week_access_activate)
        self.week_access_list.installEventFilter(self)
        self._week_list_shortcut = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self._week_list_shortcut.activated.connect(self._focus_week_access_list)
        # One pointer for every gesture on every surface: it follows a drag and reports one change.
        self.hand = Hand(self._hand_judge, self)
        self.hand.committed.connect(self._apply_change)
        self.hand.refused.connect(self.session._say)
        self.hand.opened.connect(self._edit_block)
        self.hand.menu_requested.connect(self._block_menu)
        self.hand.spot_menu_requested.connect(self._spot_menu)
        self.hand.selected.connect(self.session.select_block)
        self.hand.cleared.connect(lambda: self.session.select_block(None, None))
        self.hand.holding.connect(self._hold_renders)
        self.hand.date_judge = self._date_judge
        # Today's app, as Daily Scheduler draws it: a Week that scrolls and a full-width Day.
        self.week_table = ClassicWeek(self.hand)
        self.week_table.day_opened.connect(self._open_week_day)
        self.planner.addWidget(self.week_table)
        self.rail = Rail(self.hand)
        self.rail.focus_requested.connect(self._start_focus)
        self.rail.date_chosen.connect(self._go_to_date)
        self.rail.allow_split_requested.connect(self.session.allow_splitting)
        self.rail.month_shown_changed.connect(self._keep_rail)
        self.month_pop = QWidget(self, Qt.WindowType.Popup)
        self.month_pop.setObjectName("weekMonthPopover")
        self.month_pop.hide()
        pop_box = QVBoxLayout(self.month_pop)
        pop_box.setContentsMargins(8, 8, 8, 8)
        self.month_pick = MonthCard()
        self.month_pick.fold.hide()
        self.month_pick.date_chosen.connect(self._pick_week_date)
        pop_box.addWidget(self.month_pick)
        body.addWidget(self.rail)
        body.addLayout(column, 1)
        self.day_view = ClassicDay(self.hand)
        self.planner.addWidget(self.day_view)
        for hours in (self.week_table.scroll, self.day_view.scroll):
            hours.zoomed.connect(self._remember_zoom)
        self.month_grid = MonthGrid(hand=self.hand)
        self.month_grid.day_activated.connect(self.session.open_day)
        self.planner.addWidget(self.month_grid)
        self.empty_week = EmptyWeek()
        self.empty_week.add_requested.connect(self._add_homework)
        self.empty_week.copy_last_requested.connect(self._copy_last_week_fixed)
        self.empty_week.routine_requested.connect(self._open_routines)
        self.planner.addWidget(self.empty_week)
        for widget in (
            self.week_table.hours,
            self.day_view.hours,
            self.month_grid.canvas,
            self.rail.tasks,
        ):
            widget.installEventFilter(self)
        # The calendar is the point of this page, so it takes whatever height the rest does not need,
        # down to the window's foot. Notices float over it rather than taking a row.
        column.addWidget(self.planner, 1)
        self.planner.installEventFilter(self)
        layout.addLayout(body, 1)
        self._stack.addWidget(page)
        self._week_page = page
        self.plan_review.setParent(page)
        self.plan_review.hide()
        # Month's rows shrink to fit while either panel is open (#28).
        for panel in (self.plan_review, self.unfinished_panel):
            panel.installEventFilter(self)
        self.toast = Toast(self, self.planner)
        self._toast_week: str | None = None

    def _planner_widget(self, view: str) -> QWidget:
        """The chosen main view stands in for the week grid, and for Day and Month too.

        Today's app keeps the clock-order Day list and the chip Month. My day is still its own
        screen. A design of its own rebuilds Day and Month in that design, so the app is not two
        programs once you leave the week. A new account's empty week shows Today's app one button
        instead of empty hours.
        """
        if self._day_mode:
            self._hide_empty_card()
            return self._layout_view(self._layout["day"])
        main = self._layout["main"]
        if main in VIEW_CLASSES and view in {"week", "day", "month"}:
            self._hide_empty_card()
            return self._layout_view(main)
        session = self.session
        if view in {"week", "day"} and self._layout["main"] == "classic":
            week = build_week(session.week_start, session.blocks, session.assignments, session.trace)
            if not session.blocks:
                start = start_here_week(week, session.assignments, session.week_start, session.saved_weeks)
                self.empty_week.set_blank(not start)
                if start:
                    self._host_empty_week(self.planner)
                    return self.empty_week
                host = self.day_view if view == "day" else self.week_table
                self._host_empty_week(host)
                return host
        self._hide_empty_card()
        return {"day": self.day_view, "month": self.month_grid}.get(view, self.week_table)

    def _host_empty_week(self, host: QWidget) -> None:
        card = self.empty_week
        over = host is not self.planner
        card.set_over_hours(over)
        if over:
            if card.parent() is not host:
                card.setParent(host)
            if not host.property("emptyCardWatched"):
                host.setProperty("emptyCardWatched", True)
                host.installEventFilter(self)
            card.show()
            card.raise_()
            self._center_empty_card()
            return
        if card.parent() is not self.planner:
            self.planner.addWidget(card)
        card.show()

    def _hide_empty_card(self) -> None:
        card = self.empty_week
        parent = card.parentWidget()
        if parent in (self.week_table, self.day_view):
            card.hide()
            card.set_over_hours(False)
            self.planner.addWidget(card)

    def _center_empty_card(self) -> None:
        card = self.empty_week
        host = card.parentWidget()
        if host is None or host is self.planner:
            return
        card.adjustSize()
        card.move(
            max(0, (host.width() - card.width()) // 2),
            max(0, (host.height() - card.height()) // 2),
        )

    def _layout_view(self, layout_id: str) -> LayoutView:
        view = self._views.get(layout_id)
        if view is None:
            view = VIEW_CLASSES[layout_id](hand=self.hand)
            # A layout only says what the student wants. What happens is what the window already does.
            view.add_requested.connect(
                lambda category: self._add_from_chip(category) if category else self._add_homework()
            )
            view.plan_requested.connect(self._plan_with_left_over)
            view.block_activated.connect(self._edit_block)
            view.finished_requested.connect(self._finish_homework)
            view.focus_requested.connect(self._start_focus)
            view.late_requested.connect(self._open_late)
            view.my_day_requested.connect(self._enter_day)
            view.back_requested.connect(self._leave_day)
            view.menu_requested.connect(self._menu_from)
            view.day_activated.connect(self.session.open_day)
            view.watched_day_changed.connect(self._watched_day_title)
            view.remembered_zoom = self._zoom
            view.zoomed.connect(self._remember_zoom)
            view.option_set.connect(lambda key, value, chosen=layout_id: self._set_option(chosen, key, value))
            self.planner.addWidget(view)
            self._views[layout_id] = view
        view.show_week(self._scene_for(layout_id))
        return view

    def _finish_homework(self, assignment_id: str) -> None:
        item = self.session.assignments.get(assignment_id) or {}
        title = item.get("title") or "Homework"
        self.session.complete_homework(assignment_id, True)
        self.session.save()
        self._set_notice(f"Finished {title}.", "Undo", self._undo_from_notice)

    def _wears_carried_look(self) -> bool:
        """Nobody is signed in: the sign-in screens wear the look carried on this computer."""
        return self.session.account is None

    def _look_inputs(self) -> tuple[str, bool, str]:
        system_dark = QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if self._wears_carried_look():
            # Nobody is signed in: the device's own look, not the last account's (#74).
            return "system", system_dark, "default"
        pack = (self.session.preferences or {}).get("theme_pack") or "system"
        accent = (self.session.preferences or {}).get("accent") or "default"
        return pack, system_dark, accent

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

    def _scene_for(self, layout_id: str) -> Scene:
        clock = clock_parts(self.session.now_ms())
        options = options_for(self._layout, layout_id)
        pack, system_dark, accent = self._look_inputs()
        palette, applied_look = design_look(options["look"], pack, system_dark, self._worn_look(), accent)
        session = self.session
        surface = "week"
        if not self._day_mode and layout_id in VIEW_CLASSES and session.planner_view in {"day", "month"}:
            surface = session.planner_view
        week = self._week_with_history(
            build_week(session.week_start, session.blocks, session.assignments, session.trace)
        )
        running = session.focus_elapsed_min()
        if running:
            # A running session counts as it goes; the homework is credited only when it ends.
            week = replace(week, focus_min=week.focus_min + running)
        return Scene(
            week=week,
            today=session.today_column(clock["iso"]),
            minute=clock["minute"],
            options=options,
            tokens=tokens_for(layout_id, options["look"], palette),
            scale=text_scale(applied_look),
            surface=surface,
            month=session.month_data,
            month_key=session.selected_month,
            iso_day=session.selected_day,
            dirty=session.dirty,
            unsaved_weeks=session.unsaved_weeks(),
            focus=focus_now(session.focus),
            today_iso=clock["iso"],
            account=self._account_id(),
            missed=session.missed_block_ids(),
        )

    def _week_with_history(self, week):
        states = {
            item["id"]: "Overdue" if item.get("left_over_state") == "overdue" else "Left from last week"
            for item in self.session.unfinished()
        }
        return replace(
            week,
            occurrences=tuple(
                replace(item, history=states.get(item.assignment_id, "")) for item in week.occurrences
            ),
            homework_sentence=homework_time_sentence(
                self.session.unfinished(), self.session.homework_time_needed()
            ),
        )

    def _clock_state(self) -> tuple:
        """What on screen depends on the clock beyond the minute: which day is today and which sessions
        have passed unfinished."""
        return self._clock_in_week()[0], self.session.missed_block_ids()

    def _refresh_layout(self) -> None:
        if self.session.account is not None and self._clock_state() != self._filled_at_clock:
            # A new day or a session that has just passed: the header's today mark and the rail's
            # "Everything has a time" line change without any click.
            self._fill_classic()
            self.solve_button.set_count(len(self.session.homework_time_needed()))
        shown = self.planner.currentWidget()
        if isinstance(shown, LayoutView) and self.session.account is not None:
            shown.show_week(self._scene_for(shown.layout_id))
        elif shown in (self.week_table, self.day_view) and self.session.account is not None:
            # The line that says now moves with the minute.
            today, minute = self._clock_in_week()
            for hours in (self.week_table.hours, self.day_view.hours):
                hours.set_clock(today, minute)

    def _hours_shown(self) -> list[HoursScroll]:
        """The hours on screen now, in Today's app or a design, for the zoom keys."""
        page = self.planner.currentWidget()
        return [hours for hours in page.findChildren(HoursScroll) if hours.isVisible()] if page else []

    def _count_down(self) -> None:
        """The countdown in "Next: … (in 23m)" moves on with the minute, whether or not a focus timer
        is running to redraw it."""
        self._show_next()

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
        self._fill_classic()
        self._refresh_layout()
        if self.unfinished_panel.isVisible():
            self._fill_unfinished(self._panel_items())
        self._sync_left_chip()
        self._show_next()
        self.rail.set_tasks(self.session.focus_tasks(), self._clock_in_week()[0])
        self._schedule_deadline_tick()

    def _application_state_changed(self, state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            self._deadline_changed()
            # Back from the background the line may be minutes behind: no waiting for the next tick.
            self._tick_material_clock()

    def _rail_shown(self) -> bool:
        """Whether Today's app's rail is beside the planner: on its Day and Week."""
        return self.planner.currentWidget() in (self.week_table, self.day_view)

    def _show_next(self) -> None:
        """What is next goes in the rail when it is on screen, else above the planner."""
        words = self.session.now_next_text()
        today, minute = self._clock_in_week()
        self.rail.set_clock(today, minute)
        month = self.session.planner_view == "month" and not self._day_mode
        self.focus_panel.show_now_next("" if self._rail_shown() or month else words)

    def _sync_chrome(self) -> None:
        """Planning chips and the clipboard line step aside for a design of its own. Plan my
        homework and More stay in the top bar in every layout, every view, and My day. The hand
        drags in the step the student chose, and times are written on the clock they chose."""
        if self._set_clock():
            self._on_week()
        self.hand.step = drag_step((self.session.preferences or {}).get("drag_step_min"))
        manual = (self.session.preferences or {}).get("planning_style") == "manual"
        # A student who places homework by hand asks for ideas; the plan is theirs.
        self.solve_button.set_texts(*((SUGGEST_LABEL, SUGGEST_SHORT) if manual else (PLAN_LABEL, PLAN_SHORT)))
        self.solve_button.setToolTip(SUGGEST_TIP if manual else PLAN_TIP)
        # Retry save goes back in the row before the window's narrowest is measured from it.
        self._sync_retry_bar_slot()
        self._keep_bar_whole()
        self._fit_plan_and_more()
        own = isinstance(self.planner.currentWidget(), LayoutView)
        # The rail holds what is next and the focus list, so beside it the panel is only the running
        # timer, which is the rail's first card (decision 15 of 0.17).
        side = self._rail_shown()
        self.plan_chrome.setVisible(not own)
        self._place_rail(side)
        self.focus_panel.setVisible((not own and not side) or self.session.focus is not None)
        self._show_next()
        self.rail.set_tasks(self.session.focus_tasks(), self._clock_in_week()[0])
        # Quick focus is in the action row whenever there is one, so the panel's own copy would be
        # the same button twice; it belongs to the panel only where no action row is shown.
        self.focus_panel.quick.setVisible(own and self._day_mode)
        needed = self.session.homework_time_needed()
        self.more_button.set_count(0)
        self.solve_button.set_count(len(needed))

    def _set_clock(self) -> bool:
        """Whether the clock changed. Only a change redraws the week, so this is safe to call from
        the redraw itself."""
        changed = set_clock_24h((self.session.preferences or {}).get("clock_24h", False) is True)
        if changed:
            # Every design's hours, shown or not: a redraw that finds no new blocks does not tell
            # them their labels got wider or narrower.
            for scroll in self.planner.findChildren(HoursScroll):
                scroll.canvas.labels_changed.emit()
                scroll.canvas.update()
        return changed

    def _sync_retry_bar_slot(self) -> None:
        """Hidden Retry save must not reserve bar width; its minimum was keeping the row wrapped."""
        retry = self.retry_button
        row = self._bar_views
        at = row.indexOf(retry)
        if retry.isVisible():
            if at < 0:
                after = row.indexOf(self.solve_button)
                row.insertWidget(after + 1 if after >= 0 else self._retry_bar_index, retry)
        elif at >= 0:
            row.takeAt(at)
        self._top_bar.invalidate()

    def _schedule_bar_refit(self) -> None:
        """After Large text, Plan and More refit from FontChange before their row's width settles."""
        timer = getattr(self, "_bar_refit_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._fit_plan_and_more)
            self._bar_refit_timer = timer
        timer.start(0)

    def _fit_plan_and_more(self, total_width: int | None = None) -> None:
        """#83's one order as the bar runs short of room: the date shortens, More drops to its icon,
        Plan my homework drops "my", then reads "Plan". Each step's words are set and the bar's own
        parts say what room they need; the first step that keeps the bar on one row is kept, and
        with none the bar goes onto two rows at the last step."""
        if getattr(self, "_fitting_plan_row", False):
            return
        self._fitting_plan_row = True
        bar = self._top_bar
        more, plan, title = self.more_button, self.solve_button, self.week_title
        page = self._week_page
        width = total_width if total_width is not None else (page.width() or self.width())
        page_margins = page.layout().contentsMargins()
        margins = bar.contentsMargins()
        inner = width - page_margins.left() - page_margins.right() - margins.left() - margins.right()
        tiny = PLAN_TINY if plan._full == PLAN_LABEL else plan._short
        long_date = title._full
        short_date = title._short or title._full
        steps = (
            (long_date, plan._full, more._full),
            (short_date, plan._full, more._full),
            (short_date, plan._full, ""),
            (short_date, plan._short, ""),
            (short_date, tiny, ""),
        )
        first, second = bar.itemAt(0), bar.itemAt(1)
        for date_words, plan_words, more_words in steps:
            title.setText(date_words)
            plan.setText(plan_words)
            more.setText(more_words)
            # More as its icon alone takes an icon button's sides, not a word button's 20 pixels each.
            icon_only = not more_words
            if more.property("iconOnly") != icon_only:
                more.setProperty("iconOnly", icon_only)
                more.style().unpolish(more)
                more.style().polish(more)
            for widget in (title, plan, more):
                widget.updateGeometry()
            # Each group keeps its own size until told; the bar's invalidate does not reach them.
            for part in (first, second, bar):
                part.invalidate()
            for group in (first, second):
                if isinstance(group, QHBoxLayout):
                    group.activate()
            if first.sizeHint().width() + bar.between + second.sizeHint().width() <= inner:
                break
        bar.invalidate()
        self._fitting_plan_row = False

    def _dress_plan_button(self, palette: dict) -> None:
        """Plan is accent words with no fill, so Add stays the only filled bar action."""
        words = palette.get("accent_text", palette["accent"])
        pal = self.solve_button.palette()
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(words))
        self.solve_button.setPalette(pal)

    def _keep_bar_whole(self) -> None:
        """The window is never narrower than the top bar's buttons at their smallest, which large
        text, Suggest times and Retry save each widen."""
        # Add and its chevron are one pill, so the chevron, an icon, is as tall as Add's words.
        add = self.findChild(QPushButton, "addButton")
        add.ensurePolished()
        self.findChild(QPushButton, "addArrow").setFixedHeight(add.sizeHint().height())
        self._bar_views.invalidate()
        margins = self._bar_views.parentWidget().layout().contentsMargins()
        plan = self.solve_button
        # Measured with Plan at its last step, whatever it shows now: that is what the narrowest shows.
        tiny = PLAN_TINY if plan._full == PLAN_LABEL else plan._short
        least = self._bar_views.minimumSize().width() - plan.minimumSizeHint().width()
        needed = least + plan._wide(tiny) + margins.left() + margins.right()
        self.setMinimumWidth(max(WINDOW_MIN_WIDTH, needed))

    def _choose_view(self, view: str) -> None:
        self._day_mode = False
        self.session.set_view(view)

    def _honour_preferred_view(self) -> None:
        """Open on whatever "Open on" says, once per sign-in. The web reads the same preference at
        startup; here it was saved and never looked at, so the app always came up on the week."""
        if self._opened_on_preference or self.session.preferences is None:
            return
        self._opened_on_preference = True
        wanted = (self.session.preferences or {}).get("preferred_view")
        if wanted == "day":
            self._day_mode = True
        elif wanted == "week":
            self._day_mode = False

    def _menu_from(self, point: QPoint) -> None:
        """More's menu, opening up from `point` on the screen, as Retro desktop's Start opens it."""
        menu = self.more_menu
        menu.popup(point - QPoint(0, menu.sizeHint().height() - 2 * MENU_EDGE))

    def _enter_day(self) -> None:
        if self.session.account is None:
            return
        self._day_mode = True
        self._on_week()
        self._views[self._layout["day"]].setFocus()

    def _watched_day_title(self, iso: str) -> None:
        if self._day_mode:
            self.week_title.set_full_text(
                planner_title(self.session, "day", selected_day=iso),
                planner_title(self.session, "day", short=True, selected_day=iso),
            )

    def _leave_day(self) -> None:
        self._day_mode = False
        self._on_week()

    def _on_account(self, account: object) -> None:
        if account is None or str(account["id"]) != self._kept_adds_account:  # type: ignore[index]
            self._kept_adds.clear()
        if account is None:
            self._discard_block_spare()
            self._day_mode = False
            self._opened_on_preference = False
            self._setup_active = False
            self._setup_checked = False
            self._setup_prefs = {}
            self._setup_work_windows = None
            self._setup_week = False
            self._carried = self._read_carried()
            self._apply_appearance()
            self._show_page("authPage")
            return
        if self._block_spare_account != str(account["id"]):
            self._discard_block_spare()
        self._carry_look()
        self._apply_appearance()
        self.account_name.setText(account["username"])

    def _on_recovery(self) -> bool:
        bridge = self._account_bridge()
        return bridge is not None and bridge.phase == "recovery"

    def _finish_recovery(self) -> None:
        self._allow_week_page = True
        self.session.finish_recovery()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        self.week_table.set_narrow(False)
        self._place_rail(self._rail_shown())
        self._fit_plan_and_more(event.size().width())
        super().resizeEvent(event)
        self._fit_plan_and_more()
        if self.toast.isVisible():
            self.toast.reposition()
        if self.plan_review.isVisible():
            self._layout_plan_review()

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

    def _preview_setup_look(self, choice: dict) -> None:
        """Dress the whole window in a look the student is trying, without keeping it. The old look
        fades out over the new one rather than snapping."""
        picture = hold_picture(self._stack, self._motion)
        self._look = choice["look"]
        self.session.look = self._look
        self._layout = choice["layout"]
        if self.session.preferences is not None:
            self.session.preferences = {**self.session.preferences, "theme_pack": choice["pack"]}
        self._apply_appearance()
        fade_away(picture, self._motion)

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
                standing = answer["blocks"]
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
        self._sync_chrome()
        self._on_week()

    def _show_recovery(self, codes: list) -> None:
        self._allow_week_page = False
        self._material_account_page("recoveryPage", codes)

    def _choose_recovery_file(self) -> str:
        """Its own method so a test can answer it without a sheet on screen. The sheet says what the file
        is before the system's file dialog, which is the system's to show, picks where it goes."""
        sheet = ConfirmSheet(
            self,
            "Save recovery codes",
            RECOVERY_KEEP,
            (("stay", "Cancel", "outlined"), ("choose", RECOVERY_CHOOSE, "")),
            default="choose",
        )
        sheet.exec()
        if sheet.answer != "choose":
            return ""
        return self._pick_recovery_file()

    def _pick_recovery_file(self) -> str:
        """The file dialog, opened on Documents (#50); a test answers it with a path."""
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        start = str(Path(documents or Path.home()) / RECOVERY_FILE)
        path, _ = QFileDialog.getSaveFileName(self, "Save recovery codes", start, "Text (*.txt)")
        return path

    def _on_week_start(self, _value: str) -> None:
        """The week's first day changed in Settings or Setup: every open screen follows at once."""
        self.session.follow_first_weekday(week_start_day())

    def _on_week(self) -> None:
        # The hand names days of the open week, which may start on any day.
        self.hand.week_start = self.session.week_start
        if self.session.account is None:
            return
        if self.plan_review.isVisible() and self.plan_review.week_start != self.session.week_start:
            self.plan_review.hide()
        if self.hand.busy and self._where() != self._shown:
            # Somewhere else was asked for while a block was held: another view, week, day or design.
            # The block goes back and nothing moves, as Escape does.
            self.hand.cancel()
        if not self.hand.busy:
            self._shown = self._where()
        if self.session.week_start != self._toast_week:
            # Another week: Undo applies to the week where the change was saved, so a toast still
            # offering it would offer nothing. Another view, day or design keeps it.
            self._toast_week = self.session.week_start
            self.toast.hide()
        if self.unfinished_panel.isVisible():
            # A row deleted, planned or finished leaves the list, and an Undo brings it back.
            # Overdue and carried homework stay listed when the week changes; they are not the
            # "still needs a time" count.
            self._fill_unfinished(self._panel_items())
        self._sync_left_chip()
        if self.session.dirty:
            # Every change reaches here, so this is where the clock on "stopped changing" restarts.
            self._changed_ms = int(time.monotonic() * 1000)
        if self._on_recovery() and not self._allow_week_page:
            return
        current = (self.session.account["id"], self.session.week_start)
        if current != self._hours_week:
            if self._hours_week is not None and (
                current[0] != self._hours_week[0] or self._clock_in_week()[0] is not None
            ):
                self._reset_hours(clear_all=current[0] != self._hours_week[0])
            self._hours_week = current
        turn = self._begin_turn()
        self._honour_preferred_view()
        self._set_clock()
        self._check_updates(asked=False)
        self._fill_classic()
        self.month_grid.set_month(
            self.session.month_data, self.session.dirty,
            datetime.fromtimestamp(self.session.now_ms() / 1000).date().isoformat(),
            self._account_id(), self.session.selected_month,
        )
        opened = (self.session.planner_view, self.session.selected_month, self.session.month_data is not None)
        if opened[0] == "month" and opened[2] and opened != self._month_revealed:
            # Once, when a month opens: after that it stays wherever the student scrolled it, through
            # saves and refreshes. After the month has been laid out, or there is nothing to measure.
            self._month_revealed = opened
            QTimer.singleShot(0, lambda day=self.session.selected_day: self.month_grid.reveal(day))
        elif opened[0] != "month":
            self._month_revealed = None
        self._sync_add_button()
        view = self.session.planner_view
        shown = self._planner_widget(view)
        # The rail goes with Today's app's Day and Week. Put away before the page changes, another
        # design is laid out once at its whole width, not first cramped beside the rail and again.
        self._place_rail(shown in (self.week_table, self.day_view))
        if turn is None:
            switch_page(self.planner, shown, self._motion)
        else:
            self.planner.setCurrentWidget(shown)
        self._show_next()
        self._release_travel()
        for name in ("viewDay", "viewWeek", "viewMonth", "viewMyDay"):
            button = self.findChild(QRadioButton, name)
            if button is not None:
                button.setChecked(name == ("viewMyDay" if self._day_mode else f"view{view.title()}"))
        month = view == "month"
        day = view == "day"
        period = "month" if month else ("day" if day else "week")
        self.prev_nav.setToolTip(f"Previous {period}")
        self.next_nav.setToolTip(f"Next {period}")
        self.prev_nav.setAccessibleName(f"Previous {period}")
        self.next_nav.setAccessibleName(f"Next {period}")
        self._show_week_list_row(view == "week" and not self._day_mode)
        title_view = "myday" if self._day_mode else view
        watched = shown.watched_date() if self._day_mode and isinstance(shown, LayoutView) else None
        self.week_title.set_full_text(
            planner_title(self.session, title_view, selected_day=watched),
            planner_title(self.session, title_view, short=True, selected_day=watched),
        )
        self._maybe_open_setup()
        if self._setup_prefs or self._setup_work_windows is not None or self._setup_week:
            # The account's preferences may only now have arrived, and what setup kept before they did,
            # a skip included, is written with them.
            QTimer.singleShot(0, self, self._flush_setup)
        # Setup stays where it is. Anything else shows the surface that owns
        # the window. A failed Material open falls through to the Widgets week inside _show_surface.
        if not self._cover_holds():
            self._show_surface()
        self._maybe_prepare_block_spare()
        if self.plan_review.isVisible():
            self._layout_plan_review()
        can_retry = self.session.pending_save is not None and not self.session.conflict
        # Hidden, not merely greyed: a button that is never pressable is a permanent piece of
        # furniture that says a save failed when none has. A save on its way has a pending save too,
        # so only a finished one shows or hides it: drawn mid-save, as Month's fetch landing does,
        # Retry showed and pushed the view buttons aside.
        if not self.session.busy:
            self.retry_button.setVisible(can_retry)
        self.retry_button.setEnabled(can_retry and not self.session.busy)
        self._sync_retry_bar_slot()
        undo = self.findChild(QPushButton, "undoButton")
        redo = self.findChild(QPushButton, "redoButton")
        if undo is not None:
            self._sync_undo_enabled()
        if redo is not None:
            redo.setEnabled(self.session.can_redo())
        clip = self.session.clipboard
        # A permanent line saying nothing has happened is noise. It appears when there is something
        # on the clipboard and goes away again when there is not.
        self.clipboard_summary.setVisible(clip is not None)
        self.clipboard_summary.setText("Copied: " + clip["label"] if clip else "")
        destination = self.session.paste_destination()
        copy_day = self.findChild(QPushButton, "copyDay")
        paste = self.findChild(QPushButton, "pasteBlock")
        if copy_day is not None:
            if destination is None:
                copy_day.setText("Copy a selected day")
            else:
                copy_day.setText("Copy " + day_full_names(self.session.week_start)[destination[0]])
        if paste is not None:
            paste.setEnabled(clip is not None and destination is not None)
            if destination is None:
                paste.setText("Paste into a selected day")
            else:
                paste.setText("Paste into " + day_full_names(self.session.week_start)[destination[0]])
        needed = self.session.homework_time_needed()
        unfinished = self.findChild(QPushButton, "unfinishedOpen")
        if unfinished is not None:
            unfinished.setEnabled(bool(self._panel_items()))
        self.more_button.set_count(0)
        self.solve_button.set_count(len(needed))
        self._announce_overdue()
        # These one-shot prompts belong to the Widgets week, including while its Settings is open.
        # Material keeps them even when Focus or Settings covers it, or a swap back would find them gone.
        if not self._material_owns():
            prompt = self._unfinished_items(self.session.consume_unfinished())
            if prompt:
                self._fill_unfinished(prompt)
                self._unfinished_opened = True
            elif self._unfinished_opened and not self.unfinished_panel.isHidden():
                self._fill_unfinished(self._panel_items())
            else:
                self._unfinished_opened = False
                self.unfinished_panel.hide()
        if self._late_dialog is not None and self.session.late_preview:
            titles = {block["id"]: block["title"] for block in self.session.blocks}
            self._late_dialog.show_trace(self.session.late_preview["trace"], titles)
        self.focus_panel.set_state(self.session)
        if not self._material_owns():
            fresh = self.session.consume_plan_review()
            if fresh is not None:
                titles = {block["id"]: block["title"] for block in self.session.blocks}
                was_open = self.plan_review.isVisible()
                self.plan_review.set_trace(
                    fresh,
                    titles,
                    self.session.week_start,
                    self.session.plan_counts,
                    self.session.assignments,
                    self.session.plan_remainders,
                )
                self._reveal_placed()
                if self.plan_review.isVisible():
                    self._layout_plan_review()
                    if not was_open:
                        slide_down(self.plan_review, self._motion)
        self._sync_running_late()
        self._sync_chrome()
        self._apply_appearance()
        self._schedule_deadline_tick()
        # A month that arrives while it is still sliding in: its picture is taken again once the
        # month has scrolled to its first row, which is a turn of the event loop after this.
        if sliding_in(self.planner):
            QTimer.singleShot(0, self, self._retake_slide)
        if getattr(self, "_plan_focus_pending", False):
            self._plan_focus_pending = False
            QTimer.singleShot(0, self, self._focus_after_plan)
        if getattr(self, "_redo_focus_pending", False):
            self._redo_focus_pending = False
            QTimer.singleShot(0, self, self._focus_after_redo)
        self._finish_turn(turn)

    def _retake_slide(self) -> None:
        self._week_page.layout().activate()
        retake_slide(self.planner)

    def _on_status(self, message: str) -> None:
        """What the session says goes in the toast, on the week's page, unless it is still going
        ("Saving…") or routine ("Saved."). The student's own request is answered either way."""
        if not message:
            # The session took back what it said, as Cancel on Running late's preview does.
            if not self.toast.button.isVisible():
                self.toast.hide()
            return
        if message.endswith("…"):
            return
        asked, self._telling = self._telling, False
        if (asked or message not in ROUTINE_STATUS) and self._stack.currentWidget() is self._week_page:
            self._say_in_toast(message)

    def _say_in_toast(self, message: str) -> None:
        if self.toast.isVisible() and self.toast.text() == message:
            # Said again as its save lands: the toast already says it, perhaps with its Undo.
            return
        if self._keeps_undo(message):
            self.toast.bump()
            return
        self._notice_step = None
        self.toast.show_message(message)

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
        focus = QApplication.focusWidget()
        if focus is None or focus.objectName() != button:
            return False
        if message == self._reminder_said:
            return False
        return not any(part in message for part in ("Try again", "Wait a moment", "could not", "Couldn't"))

    def _reminder_handled(self) -> None:
        """Got it on a reminder left on screen: the toast saying the same goes too."""
        if self.toast.isVisible() and self.toast.text() == self._reminder_said:
            self.toast.hide()

    def _toast_offers_undo(self) -> bool:
        return (
            self.toast.isVisible()
            and self.toast.button.isVisible()
            and self.toast.button.accessibleName() == "Undo"
        )

    def _sync_undo_enabled(self) -> None:
        undo = self.findChild(QPushButton, "undoButton")
        if undo is not None:
            undo.setEnabled(not self.session.busy and (self.session.can_undo() or self._toast_offers_undo()))

    def _sync_more_menu(self) -> None:
        self._sync_undo_enabled()
        needed = self.session.homework_time_needed()
        count = len(needed)
        unfinished = self.findChild(QPushButton, "unfinishedOpen")
        if unfinished is not None:
            # Worked out as the menu opens: the busy flag turns every action back on when a save
            # ends, and left to that "Unfinished" was pressable with nothing to show.
            unfinished.setEnabled(not self.session.busy and bool(self._panel_items()))
        listed = self.findChild(QPushButton, "weekListRow")
        if listed is not None:
            listed.setEnabled(self.session.planner_view == "week" and not self._day_mode)
        for action, button in self._more_pairs:
            action.setEnabled(button.isEnabled())
            tip = self._more_tip(button.objectName(), button.isEnabled())
            # Greyed with nothing to show, Unfinished says so on its row, not only in a tooltip (T23).
            said = f"\t{NONE_UNFINISHED}" if tip == NOTHING_UNFINISHED else ""
            if button.objectName() == "unfinishedOpen":
                said = f"\t{count} left" if count else f"\t{NONE_UNFINISHED}"
            action.setText(button.text() + said)
            action.setToolTip(tip)
        if self._spotify_action is not None:
            self._spotify_action.setVisible(bool(self.session.spotify_url()))

    def _more_tip(self, name: str, enabled: bool) -> str:
        if name == "quickFocusAction":
            minutes = phase_duration_ms("work", self.session.preferences) // 60_000
            return QUICK_FOCUS_TIP.format(minutes=minutes)
        if enabled:
            return MORE_TIPS.get(name, "")
        session = self.session
        if session.conflict:
            return CONFLICT_TIP
        if session.planning:
            return PLANNING_TIP
        if session.busy or session.dirty or session.pending_save is not None:
            return WAIT_TIP
        if name == "pasteBlock" and session.clipboard is not None:
            return "Click a day first, then paste into it."
        return GREYED_TIPS.get(name, "")

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self._leave_greyed_button()
        for name in BUSY_BUTTONS:
            button = self.findChild(QAbstractButton, name)
            if button is not None and button.property("busyGuard") is None:
                button.setProperty("busyGuard", True)
                button.installEventFilter(self._busy_guard)
        if busy:
            self._busy_look.start()
            if self.session.planning:
                # At once, not after the busy look's delay: a second click in that gap was a second plan.
                self.solve_button.setEnabled(False)
        else:
            self._busy_look.stop()
            self._grey_while_busy()
        retry = self.findChild(QPushButton, "retrySave")
        can_retry = not busy and self.session.pending_save is not None and not self.session.conflict
        if retry is not None:
            retry.setEnabled(can_retry)
        undo = self.findChild(QPushButton, "undoButton")
        redo = self.findChild(QPushButton, "redoButton")
        if undo is not None:
            self._sync_undo_enabled()
        if redo is not None:
            redo.setEnabled(not busy and self.session.can_redo())
        if not busy and self._date_waiting is not None:
            dated, self._date_waiting = self._date_waiting, None
            QTimer.singleShot(0, lambda: self._move_to_date(dated))
        if not busy and (self._setup_prefs or self._setup_work_windows is not None or self._setup_week):
            # A moment later, so a plan that finished just now saves its week before setup writes.
            QTimer.singleShot(0, self, self._flush_setup)

    def _leave_greyed_button(self) -> None:
        """A button greyed with the keyboard on it hands the keyboard to the next one along, such as the
        previous-week arrow; it goes to the week instead."""
        focus = QApplication.focusWidget()
        if isinstance(focus, QAbstractButton) and focus.objectName() in BUSY_BUTTONS:
            self._focus_week()

    def _grey_while_busy(self) -> None:
        busy = self.session.busy
        if busy:
            self._leave_greyed_button()
        for name in BUSY_BUTTONS:
            button = self.findChild(QAbstractButton, name)
            if button is not None:
                button.setEnabled(not busy)
        self._sync_running_late()

    def _planner_now(self) -> tuple:
        """What the planner shows, as far as a change of it is a new page."""
        return (self._day_mode, self.session.planner_view, self._layout["main"], self._layout["day"])

    def _turn_pieces(self) -> tuple[QWidget, ...]:
        """What sits under the top bar beside the planner, and may come or go with a view."""
        return (
            self.plan_chrome,
            self.rail,
            self.focus_panel,
            self.unfinished_panel,
            self.plan_review,
            self.alert_strip,
            self.planner,
        )

    def _places(self) -> dict[QWidget, QRect | None]:
        page = self._week_page
        return {
            piece: QRect(piece.mapTo(page, QPoint(0, 0)), piece.size()) if piece.isVisibleTo(page) else None
            for piece in self._turn_pieces()
        }

    def _begin_turn(self) -> tuple[QLabel, dict, int, str] | None:
        """Before another view, My day or another design is shown: a picture of everything under the
        top bar, where each part of it was, and which way the segments go, so the new page, with its
        chrome and colours, fades through in one frame once it is built (decisions 28 and 29). In
        Retro, Month is not faded to but slid in over the dimmed desk, as Settings is (J17). The title
        is in the top bar, outside the picture, and changes at once."""
        was, now = self._planner_shown, self._planner_now()
        self._planner_shown = now
        page = self._week_page
        if was is None or was == now or self._stack.currentWidget() is not page:
            return None
        # A month still sliding in holds the planner's painting back until it lands.
        settle(self.planner)
        top = self._top_bar.geometry().bottom() + 1
        picture = hold_picture(page, self._motion, QRect(0, top, page.width(), page.height() - top))
        if picture is None:
            return None
        direction = 0
        # Day, Week and Month slide toward the segment chosen; My day and a new design only fade.
        if not was[0] and not now[0] and was[2:] == now[2:] and {was[1], now[1]} <= set(VIEW_ORDER):
            step = VIEW_ORDER.index(now[1]) - VIEW_ORDER.index(was[1])
            direction = (step > 0) - (step < 0)
        over = ""
        if direction and now[2] == "retro" and "month" in (was[1], now[1]) and moves(self._motion):
            over = "back" if was[1] == "month" else "in"
        return picture, self._places(), direction, over

    def _finish_turn(self, turn: tuple[QLabel, dict, int, str] | None) -> None:
        """The new page is built and dressed: what changed fades through to it. The parts that stayed
        where they were are left out of the picture, so they neither blink nor drift. When the rail
        comes or goes the whole page moves sideways, so it slides as Settings does rather than jump
        (#29), which also keeps a panel from being drawn at both of its places."""
        if turn is None:
            return
        picture, before, direction, over = turn
        self._week_page.layout().activate()
        # A piece that changed parent (the timer from the rail to the column) came up over the picture.
        raise_pictures(self._week_page)
        after = self._places()
        if not over and moves(self._motion) and (before[self.rail] is None) != (after[self.rail] is None):
            over = "in" if after[self.rail] is None else "back"
        if over:
            slide_view(self._week_page, picture, self.planner, self._motion, back=over == "back")
            return
        changed = [piece for piece in self._turn_pieces() if before[piece] != after[piece]]
        area = before[self.planner] or QRect()
        for piece in changed:
            area = area.united(before[piece] or QRect())
        if area.isEmpty():
            picture.deleteLater()
            return
        trim_picture(picture, area)
        incoming = [piece for piece in changed if piece is not self.planner and piece.isVisible()]
        fade_through(picture, [*incoming, self.planner.currentWidget()], self._motion, direction)

    def _travel(self, direction: int) -> None:
        """Hold a picture of the planner while the next week, day or month loads, then let it drift
        away in the direction the student went. Without it the old week blinked to the new one."""
        self._release_travel()
        self._travel_picture = hold_picture(self.planner, self._motion)
        self._travel_direction = direction
        if self._travel_picture is not None:
            QTimer.singleShot(TRAVEL_WAIT_MS, self._release_travel)

    def _release_travel(self) -> None:
        picture, self._travel_picture = self._travel_picture, None
        fade_away(picture, self._motion, drift=self._travel_direction * DRIFT_PX)

    def _go_previous(self) -> None:
        self._travel(1)
        if self.session.planner_view == "month":
            self.session.shift_month(-1)
            return
        if self.session.planner_view == "day":
            current = date.fromisoformat(self.session.selected_day)
            self.session.open_day((current + timedelta(days=-1)).isoformat())
            return
        self._shift_week(-7)

    def _go_next(self) -> None:
        self._travel(-1)
        if self.session.planner_view == "month":
            self.session.shift_month(1)
            return
        if self.session.planner_view == "day":
            current = date.fromisoformat(self.session.selected_day)
            self.session.open_day((current + timedelta(days=1)).isoformat())
            return
        self._shift_week(7)

    def _go_today(self) -> None:
        self._travel(0)
        today = datetime.fromtimestamp(self.session.now_ms() / 1000).date()
        if self._clock_in_week()[0] is not None:
            # From another week, the week changing to this one opens it at now (_on_week), and that
            # other week stays where it was left.
            self._reset_hours()
        self.session.load_week(today.isoformat())
        if self.session.planner_view == "day" or self._day_mode:
            self.session.open_day(today.isoformat())

    def _shift_week(self, days: int) -> None:
        monday = date.fromisoformat(self.session.week_start) + timedelta(days=days)
        self.session.load_week(monday.isoformat())

    @contextlib.contextmanager
    def _material_keys_held(self) -> Iterator[None]:
        """While a dialog of this window is up over the Material page, Material's window-wide keys wait:
        their Shortcuts stay live under it and took Esc and the number keys first. The keyboard goes back
        to Material afterwards."""
        current = self._stack.currentWidget()
        page = self._material_page
        root = page.root if page is not None and current is page else None
        if root is None or not isValid(root):
            yield
            return
        was_open = root.property("widgetsDialogOpen")
        root.setProperty("widgetsDialogOpen", True)
        try:
            yield
        finally:
            if isValid(root):
                root.setProperty("widgetsDialogOpen", was_open)
                QMetaObject.invokeMethod(root, "focusDestination")

    def _run_sheet(self, dialog: QDialog) -> bool:
        """Open a sheet and wait for it. Once it is closed the keyboard is back on the week, not on the
        button that opened it."""
        # What the student pressed in the sheet says nothing about the week: the ring comes back only if
        # the keyboard, not the pointer, took them to the sheet.
        keyboard = self._last_input.keyboard
        try:
            with self._material_keys_held():
                accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            # A dim made for this sheet that it never took, because it could not open.
            drop_waiting_dim(self)
        self._last_input.keyboard = keyboard
        self._focus_week()
        return accepted

    def _sheet[D: QDialog](self, build: Callable[[], D]) -> D:
        """Build a sheet with the window already dimming behind it (J15). The dim starts at the click, and
        the sheet shows over it once built; a sheet that cannot be built leaves no dim."""
        dim_window(self)
        try:
            return build()
        except BaseException:
            drop_waiting_dim(self)
            raise

    def _keep_add(self, kind: str, dialog: Dialog, days: list[int] | None = None) -> None:
        """Esc closed a new Add sheet with typing in it: keep what was typed, as plain values, and let the
        sheet go. The next plain Add of this kind opens a new sheet filled in with it."""
        draft = dialog.draft()
        if days is not None and isinstance(dialog, HomeworkDialog):
            # A drag gave the day, the due and the length together; the next sheet keeps all three.
            fields = dialog._draft_fields()
            draft = {"due": fields["due"], "estimate": fields["estimate"], **draft}
        self._kept_adds[kind] = (draft, days, self.session.week_start)
        self._kept_adds_account = self._account_id()
        dialog.deleteLater()

    def _take_kept_add(
        self, kind: str
    ) -> tuple[dict | None, list[int] | None, list[tuple[int, str, str]]]:
        """What Esc kept for this kind of Add, once, with the days a drag gave it; or nothing. Its days keep
        their weekdays when the open week now starts on another day. Third is the moved ticks the sheet
        shows, as (new day, old "Monday 2" label, new label) triples."""
        kept = self._kept_adds.pop(kind, None)
        if kept is None:
            return None, None, []
        draft, days, week = kept
        open_now = self.session.week_start

        def turned(day: int) -> int:
            return same_weekday(day, week, open_now)

        def marked(
            shown: list[int],
        ) -> list[tuple[int, str, str]]:
            """The visible ticks the turn moved, as (new day, old label, new label) triples."""
            _, moved = turn_days_keeping_weekdays(shown, week, open_now)
            return [(new, *moved_day_names(old, week, new, open_now)) for old, new in moved]

        marks: list[tuple[int, str, str]] = []
        if kind == "block" and "days" in draft:
            turned_days, _ = turn_days_keeping_weekdays(draft["days"], week, open_now)
            marks = marked(draft["days"])
            draft = {**draft, "days": turned_days}
        else:
            if "days" in draft:
                draft = {**draft, "days": sorted(turned(day) for day in draft["days"])}
            if isinstance(draft.get("pin_day"), int):
                if kind == "homework":
                    marks = marked([draft["pin_day"]])
                draft = {**draft, "pin_day": turned(draft["pin_day"])}
        return draft, None if days is None else [turned(day) for day in days], marks

    def _commit_block(self, dialog: BlockDialog) -> None:
        if not self._run_sheet(dialog):
            if dialog.kept_on_escape:
                self._keep_add("block", dialog)
            return
        if dialog.deleted():
            self._delete_block(
                dialog.block(), dialog.scope(), dialog.occurrence_day(), every_week=dialog.delete_every_week()
            )
            return
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
        self._keyboard_to_new_block(before)

    def _keyboard_to_new_block(self, before: set[str]) -> None:
        """A block the sheet made is where the keyboard goes on the week, on the day the spot was on if the
        block is there."""
        made = next(
            (item for item in self.session.blocks if item["id"] not in before and item.get("days")), None
        )
        surfaces = self._week_surfaces()
        if made is None or not surfaces or not made.get("start"):
            return
        spot = surfaces[0].focus_slot()
        day = spot[0] if spot is not None and spot[0] in made["days"] else made["days"][0]
        placed = (made["id"], day, hhmm_to_minutes(made["start"]))
        self._focus_week(placed)

    def _commit_homework(self, dialog: HomeworkDialog, days: list[int] | None = None) -> None:
        if not self._run_sheet(dialog):
            if dialog.kept_on_escape:
                self._keep_add("homework", dialog, days)
            return
        if dialog.spread_requested():
            body = dialog.assignment()
            plan = dialog.spread_plan()
            self.session.add_homework(body, spread=True)
            self.session.spread_after_save(body["id"], plan["session_min"], plan["from_date"])
            self.session.save()
            return
        if dialog.requested() == "choose":
            self._choose_time(dialog.assignment()["id"])
            return
        if dialog.requested() == "unpin":
            if self.session.unpin_assignment(dialog.assignment()["id"]):
                self.session.save()
            return
        if dialog.requested() == "delete":
            # The editor has asked already.
            self._delete_homework(dialog.assignment()["id"], ask=False)
            return
        body = dialog.assignment()
        known = self.session.assignments.get(body.get("id") or "")
        self.session.add_homework(body, days=days)
        style = (self.session.preferences or {}).get("planning_style")
        if style == "auto" and known is None and not body.get("completed") and days is None:
            # Plan it for me as I add it: new homework gets its time once it is saved, in the same step.
            self.session.plan_after_save(body["id"])
        self.session.save()
        if body.get("completed") and not (known or {}).get("completed"):
            self._set_notice(f"Finished {body.get('title') or 'Homework'}.", "Undo", self._undo_from_notice)

    def _add_fixed(self) -> None:
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            category = None
        day, start = self._new_event_values()
        draft, _, moved = self._take_kept_add("block")
        self._commit_new_block(day, start, category, draft=draft, moved=moved)

    def _commit_new_block(
        self,
        day: int,
        start: str,
        category: str | None,
        duration_min: int = 60,
        *,
        from_range: bool = False,
        draft: dict | None = None,
        moved: list[tuple[int, str, str]] | None = None,
    ) -> None:
        try:
            self._commit_block(
                self._sheet(
                    lambda: self._take_block_dialog(
                        day=day,
                        start=start,
                        category=category,
                        duration_min=duration_min,
                        from_range=from_range,
                        draft=draft,
                        moved=moved,
                    )
                )
            )
        finally:
            self._maybe_prepare_block_spare()

    def _take_block_dialog(
        self,
        *,
        day: int,
        start: str,
        category: str | None,
        duration_min: int = 60,
        from_range: bool = False,
        draft: dict | None = None,
        moved: list[tuple[int, str, str]] | None = None,
    ) -> BlockDialog:
        spare = self._block_spare
        if spare is not None and self._block_spare_account == self._account_id() and isValid(spare):
            self._block_spare = None
            self._block_spare_account = None
            spare.fill_new(
                day=day, start=start, category=category, duration_min=duration_min, from_range=from_range
            )
            dialog = spare
        else:
            self._discard_block_spare()
            dialog = BlockDialog(
                self,
                day=day,
                start=start,
                duration_min=duration_min,
                category=category,
                from_range=from_range,
            )
        if draft:
            dialog.apply_draft(draft)
        if moved:
            dialog.show_moved_days(moved)
        return dialog

    def _new_event_values(self) -> tuple[int, str]:
        """A new event opens on the next quarter hour still ahead today, or with none left, the first one
        tomorrow. The usual start stays for another week, which has no "now", and for tomorrow when that is
        a day of the next week, which the open one cannot hold."""
        today, minute = self._clock_in_week()
        if today is None or minute is None:
            return 0, "16:00"
        ahead, slot = next_slot(minute)
        if today + ahead > 6:
            return 0, "16:00"
        return today + ahead, minutes_to_hhmm(slot)

    def _add_fixed_at(self, day: int, minute: int) -> None:
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            category = None
        self._commit_new_block(day, minutes_to_hhmm(minute), category)

    def _maybe_prepare_block_spare(self) -> None:
        if (
            self._block_spare is not None
            or self._block_prepare_scheduled
            or self.session.account is None
            or self.session.preferences is None
            or self._setup_active
            or QApplication.activeModalWidget() is not None
        ):
            return
        self._block_prepare_scheduled = True
        QTimer.singleShot(0, self, self._prepare_block_spare)

    def _prepare_block_spare(self) -> None:
        self._block_prepare_scheduled = False
        if (
            self._block_spare is not None
            or self.session.account is None
            or self.session.preferences is None
            or self._setup_active
            or QApplication.activeModalWidget() is not None
        ):
            return
        account_id = self._account_id()
        try:
            spare = BlockDialog(self)
        except Exception:
            return
        if account_id != self._account_id():
            spare.deleteLater()
            return
        self._block_spare = spare
        self._block_spare_account = account_id

    def _discard_block_spare(self) -> None:
        spare, self._block_spare = self._block_spare, None
        self._block_spare_account = None
        if spare is not None and isValid(spare):
            spare.deleteLater()

    def _add_homework_due(self, due: str) -> None:
        category = self.session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        self._commit_homework(
            self._sheet(lambda: HomeworkDialog(self, today=self._today(), category=category, due=due))
        )

    def _delete_block(
        self, block: dict, scope: str, day: int | None, every_week: bool | None = None
    ) -> None:
        title = block.get("title") or "this fixed time"
        whole = scope != "occurrence" or len(block.get("days") or []) <= 1
        if every_week is None and whole and is_setup_block(block):
            # School and Setup's activities are in every week, so taking one out asks which.
            sheet = ConfirmSheet(
                self,
                f"Delete {title}?",
                (
                    "Delete it from this week only, or from this week and every week after? "
                    "Earlier weeks keep it."
                ),
                (
                    ("stay", "Cancel", "outlined"),
                    ("week", "This week only", ""),
                    ("every", "This week and later", "danger"),
                ),
                default="week",
                note="This week and later can't be undone.",
            )
            sheet.exec()
            if sheet.answer not in ("week", "every"):
                return
            every_week = sheet.answer == "every"
        if every_week and is_setup_block(block):
            family = block_family(block["id"])
            after = [item for item in self.session.repeats if item["id"] != family]
            if not self._apply_standing(after, f"deleting {title}"):
                return
            self.session.save()
            self._set_notice(f"Deleted {title} from this week and every week after.", "", None)
            return
        self.session.delete_block(block["id"], scope=scope, day=day, every_week=bool(every_week))
        self.session.save()
        if every_week:
            # Undo takes back this week only, so the toast offers none.
            self._set_notice(f"Deleted {title} from this week and every week after.", "", None)
            return
        if scope == "occurrence" and day is not None:
            words = f"Deleted {title} on {day_full_names(self.session.week_start)[day]} from this week."
            self._set_notice(words, "Undo", self._undo_from_notice)
            return
        self._set_notice(f"Deleted {title} from this week.", "Undo", self._undo_from_notice)

    def _school_hours(self) -> None:
        """School's days and times every week, asked as setup asks them: the usual School (the repeat,
        never this week's copy of it), with a line naming what this week does differently, or Monday
        to Friday 08:00-14:30 to start from. Saved from this week on; no day ticked takes School off the
        calendar."""
        repeats = self.session.repeats
        school = next((item for item in repeats if item["id"] == SETUP_SCHOOL_ID), None)
        clock_24h = (self.session.preferences or {}).get("clock_24h") is True
        line = (
            this_week_line(self.session.blocks, [school], clock_24h, self.session.week_start)
            if school is not None
            else None
        )
        dialog = SchoolHoursDialog(self, school, this_week=line)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        made = dialog.block()
        if made is not None:
            after = [made if item["id"] == SETUP_SCHOOL_ID else item for item in repeats]
            if school is None:
                after = [made, *repeats]
            start = hhmm_text(made["start"])
            end = hhmm_text(minutes_to_hhmm(hhmm_to_minutes(made["start"]) + made["duration_min"]))
            # Later weeks change with no Undo, so the toast offers none.
            self._save_standing(
                after,
                "editing School hours",
                lambda: self._set_notice(f"School now {start}–{end} every week", "", None),
            )
        elif school is not None:
            self._delete_block(school, "series", None, every_week=True)

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
        """The three answers, or None for Cancel. Material uses its answers sheet; Widgets a confirm
        sheet. Except edited is the default."""
        bridge = self._account_bridge()
        material = self._surface == "material" and not self._material_gave_up
        if material and bridge is not None and bridge.phase == "setup":
            return self._pose_edited_on(line, bridge.pose_edited)
        page = getattr(self, "_material_page", None)
        if material and page is not None and self._material_owns():
            return self._pose_edited_on(line, page.bridge._sheets.pose_edited)
        sheet = ConfirmSheet(
            self,
            "Edited weeks",
            line,
            (
                ("stay", "Cancel", "outlined"),
                ("from_today", "From today on", "outlined"),
                ("replace", "All weeks", "outlined"),
                ("keep", "Except edited", "filled"),
            ),
            default="keep",
        )
        sheet.exec()
        if sheet.answer in ("keep", "replace", "from_today"):
            return sheet.answer
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
                {"id": "replace", "label": "All weeks", "kind": "tonal"},
                {"id": "from_today", "label": "From today on", "kind": "tonal"},
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

    def _add_now(self) -> None:
        """Add adds homework, or the type picked in its menu for a drag, which the button then names."""
        armed = self.session.armed_category
        if armed:
            self._add_from_chip(armed, plain=True)
        else:
            self._add_homework()

    def _add_homework(self) -> None:
        category = self.session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        draft, days, moved = self._take_kept_add("homework")

        def build() -> HomeworkDialog:
            dialog = HomeworkDialog(self, today=self._today(), category=category)
            if draft:
                dialog.apply_draft(draft)
            if moved:
                dialog.show_moved_days(moved)
            return dialog

        self._commit_homework(self._sheet(build), days)

    def _today(self) -> str:
        return clock_parts(self.session.now_ms())["iso"]

    def _sync_add_button(self) -> None:
        """The Add button carries the type a drag on the calendar will make, so the armed type is
        still visible now that the chip strip is gone."""
        armed = self.session.armed_category
        self.add_menu.set_armed(armed)
        button = self.findChild(QPushButton, "addButton")
        info = CATEGORIES.get(armed or "")
        if button is not None:
            button.setText(f"Add {info['label'].lower()}" if info else "Add")
            icons.tint(button, None if info else "plus")
            if info:
                button.setIcon(QIcon(swatch(info["mark"])))

    def _clock_in_week(self) -> tuple[int | None, int | None]:
        """Today's weekday and minute when the open week is this week, else nothing to mark."""
        moment = datetime.fromtimestamp(self.session.now_ms() / 1000.0)
        column = self.session.today_column(moment.date().isoformat())
        if column is None:
            return None, None
        return column, moment.hour * 60 + moment.minute

    def _fill_classic(self) -> None:
        """Today's app's Day and Week from the open week. Held while the pointer holds something."""
        if self.hand.busy:
            return
        # Read before the fill, so a session that passes while it runs brings one more refill.
        clock_state = self._clock_state()
        week = self._week_with_history(
            build_week(
                self.session.week_start, self.session.blocks, self.session.assignments, self.session.trace
            )
        )
        today, minute = self._clock_in_week()
        self._sync_week_access_list(week)
        self.week_table.set_week(week, today, minute)
        self.day_view.set_day(week, self._selected_column(), today, minute)
        trace = self.session.trace or {}
        one_go_unplaced = (
            {
                item.get("assignment_id")
                for item in trace.get("unplaced") or []
                if item.get("assignment_id")
            }
            if trace.get("week_start") == self.session.week_start
            else set()
        )
        self.rail.set_week(
            week,
            today,
            minute,
            self.session.assignments,
            self.session.homework_time_needed(),
            one_go_unplaced,
            self.session.unfinished(),
        )
        self.month_grid.set_unsaved(self.session.unsaved_weeks())
        self.month_grid.set_week(week)
        self._filled_at_clock = clock_state
        self._announce_overdue()

    def _sync_week_access_list(self, week) -> None:
        selected = self.week_access_list.currentItem()
        selected_key = selected.data(Qt.ItemDataRole.UserRole) if selected is not None else None
        self.week_access_list.clear()
        for day in range(7):
            items = sorted(week.on_day(day), key=lambda item: (item.start, item.end, item.title))
            if not items:
                words = f"{week.day_full(day)}: Nothing planned"
                row = QListWidgetItem(words)
                self.week_access_list.addItem(row)
                continue
            for occurrence in items:
                drawn = Drawn(
                    occurrence.block_id,
                    occurrence.title,
                    occurrence.category,
                    occurrence.work,
                    Span(day, occurrence.start, occurrence.end),
                    0,
                    1,
                    done=occurrence.done,
                    missed=occurrence.missed,
                    pinned=occurrence.pinned,
                    history=occurrence.history,
                    history_due=occurrence.due,
                    placed_by_plan=plan_placed(occurrence),
                )
                detail = drawn.detail
                if not occurrence.work:
                    detail += " · Fixed time"
                words = f"{week.day_full(day)}: {occurrence.title}, {detail}"
                row = QListWidgetItem(words)
                row.setData(Qt.ItemDataRole.UserRole, (occurrence.block_id, day))
                self.week_access_list.addItem(row)
        self._show_week_list_row(self.session.planner_view == "week" and not self._day_mode)
        if selected_key is not None:
            for index in range(self.week_access_list.count()):
                row = self.week_access_list.item(index)
                if row.data(Qt.ItemDataRole.UserRole) == selected_key:
                    self.week_access_list.setCurrentRow(index)
                    break

    def _show_week_list_row(self, shown: bool) -> None:
        self.week_list_row.setEnabled(shown)
        if not shown:
            self._close_week_access_list(restore_focus=False)

    def _announce_overdue(self) -> None:
        """Keep count announcements on the active page's accessibility tree."""
        stamp = self.session.now_ms() / 1000
        overdue = overdue_unfinished(self.session.unfinished(), datetime.fromtimestamp(stamp))
        words = f"{len(overdue)} overdue"
        previous = getattr(self, "_overdue_words", None)
        if words != previous and (previous is not None or overdue):
            target = self.more_button if self.more_button.isVisible() else self
            announce(target, words)
        self._overdue_words = words

    def _toggle_week_month(self) -> None:
        if self.month_pop.isVisible():
            self.month_pop.hide()
            return
        week = self.session.week_start
        today, _minute = self._clock_in_week()
        now = wall_clock.today() if today is None else date.fromisoformat(week) + timedelta(days=today)
        due = frozenset(
            str(item.get("due") or "")[:10]
            for item in (self.session.assignments or {}).values()
            if item.get("due") and not item.get("completed")
        )
        self.month_pick.dates.look = self._look
        self.month_pick.dates.colours = self.rail.colours
        self.month_pick.show_week(week, now, due)
        at = self.week_title.mapToGlobal(QPoint(0, self.week_title.height() + 4))
        self.month_pop.adjustSize()
        self.month_pop.move(at)
        self.month_pop.show()
        self.month_pop.raise_()

    def _pick_week_date(self, iso: str) -> None:
        self.month_pop.hide()
        self._go_to_date(iso)

    def _focus_week_access_list(self) -> None:
        """Open the week list over the grid with the keyboard on its first row."""
        if not self.week_list_row.isEnabled():
            return
        if not self.week_list_panel.isVisible():
            focus = QApplication.focusWidget()
            self._week_list_return = None if focus is self.week_access_list else focus
        self.week_list_panel.show()
        self._layout_week_list()
        if self.week_access_list.count():
            self.week_access_list.setCurrentRow(0)
        self.week_access_list.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _toggle_week_access_list(self) -> None:
        if self.week_list_panel.isVisible():
            self._close_week_access_list()
        else:
            self._focus_week_access_list()

    def _close_week_access_list(self, restore_focus: bool = True) -> None:
        if not self.week_list_panel.isVisible():
            return
        back = self._week_list_return
        self._week_list_return = None
        self.week_list_panel.hide()
        if not restore_focus:
            return
        if back is None or not isValid(back) or not back.isVisible():
            back = self.more_button
        if back.isVisible():
            back.setFocus(Qt.FocusReason.OtherFocusReason)

    def _layout_week_list(self) -> None:
        """The list floats over the planner: the right-hand side of it, or all of it on a narrow window."""
        host = self._week_page
        origin = self.planner.mapTo(host, QPoint(0, 0))
        width = self.planner.width()
        if self.width() >= NARROW_WIDTH:
            width = min(width, WEEK_LIST_PANEL_WIDTH)
        self.week_list_panel.setGeometry(
            origin.x() + self.planner.width() - width, origin.y(), width, self.planner.height()
        )
        self.week_list_panel.raise_()
        raise_pictures(host)

    def _week_access_activate(self, row: QListWidgetItem) -> None:
        target = row.data(Qt.ItemDataRole.UserRole)
        if target is not None:
            block_id, day = target
            self.session.select_block(block_id, day)
            self._edit_block(block_id)

    def _where(self) -> tuple:
        """What the planner is showing: a held block belongs to this, and to nothing else."""
        session = self.session
        return (
            session.planner_view,
            session.week_start,
            session.selected_day,
            self._day_mode,
            repr(self._layout),
        )

    def _set_option(self, layout_id: str, key: str, value: str) -> None:
        """An option a design changed on its own page, kept with the look as Settings keeps one: only
        while it differs from how the design ships."""
        options = {name: dict(values) for name, values in self._layout["options"].items()}
        chosen = options.setdefault(layout_id, {})
        chosen[key] = value
        if value == options_for(None, layout_id)[key]:
            del chosen[key]
        self._layout = sanitize_layout({**self._layout, "options": options})
        self._save_look()
        self._on_week()

    def _remember_zoom(self, key: str, px: int) -> None:
        """How close a surface's hours are is kept for this device, as the look is."""
        # In place: every design holds this dict and reads it for the hours it makes later.
        self._zoom[key] = px
        self._save_look()

    def _place_rail(self, shown: bool) -> None:
        """The Agenda rail stays beside the planner at a fixed width. The running timer sits at its
        top while the rail shows."""
        if self.rail.folded:
            for home in (self._rail_row, self._column):
                home.removeWidget(self.rail)
            self._rail_row.insertWidget(0, self.rail)
            self.rail.set_folded(False)
        self.rail.setVisible(shown)
        in_rail = shown
        slot = self.rail.timer_slot
        if in_rail and slot.indexOf(self.focus_panel) < 0:
            self._column.removeWidget(self.focus_panel)
            slot.addWidget(self.focus_panel)
        elif not in_rail and self._column.indexOf(self.focus_panel) < 0:
            slot.removeWidget(self.focus_panel)
            self._column.insertWidget(0, self.focus_panel)
        self.focus_panel.set_compact(in_rail)

    def _reset_hours(self, *, clear_all: bool = False) -> None:
        # Designs park cached grids outside the window and may reuse an unchanged scene.
        today, minute = self._clock_in_week()
        for scroll in QApplication.allWidgets():
            if isinstance(scroll, HoursScroll) and scroll.canvas.hand is self.hand:
                key = scroll._opened
                scroll.forget(None if clear_all else self.session.week_start)
                if scroll._opened is None and minute is not None and (
                    not isinstance(key, tuple) or key[1] == today
                ):
                    scroll.scroll_to(minute, None)

    def _reveal_placed(self) -> None:
        """After Plan, the hours on screen scroll to the first homework it placed, so what it did is
        seen (decision 34 of 0.17). On Day, only when that is the day shown."""
        first = self.session.plan_first
        shown = self.planner.currentWidget()
        if first is None or shown not in (self.week_table, self.day_view):
            return
        day, minute = first
        if shown is self.day_view and day != shown.day:
            return
        shown.scroll.reveal(minute, 60, self._motion)

    def _keep_rail(self, _shown: bool) -> None:
        """The month folded or shown in the rail is kept on this computer, as the zoom is."""
        self._save_look()

    def _go_to_date(self, iso: str) -> None:
        """A date picked in the rail's month: that day on Day, else its week."""
        if self.session.planner_view == "day":
            self.session.open_day(iso)
        else:
            self.session.load_week(iso)

    def _selected_column(self) -> int:
        """The selected day's place in the open week (0 its first day)."""
        column = self.session.today_column(self.session.selected_day)
        return 0 if column is None else column

    def _open_week_day(self, day: int) -> None:
        self.session.open_day(date_for_day(self.session.week_start, day))

    def _hand_judge(self, block_id: str, from_day: int, span) -> HandVerdict:
        return self._judge_span(block_id, from_day, span.day, span.start, span.end)

    def _apply_change(self, change: object) -> None:
        """What the pointer did, turned into the change the week keeps."""
        if isinstance(change, Move):
            span = change.span
            self._move_block(change.block_id, change.from_day, span.day, span.start, span.end)
            self._focus_week((change.block_id, span.day, span.start))
        elif isinstance(change, Place):
            span = change.span
            self._move_block(change.block_id, -1, span.day, span.start, span.end)
            self._focus_week((change.block_id, span.day, span.start))
        elif isinstance(change, Create):
            span = change.span
            # After the release has been handled: Add is a dialog with its own event loop.
            QTimer.singleShot(0, lambda: self._create_by_drag(span))
        elif isinstance(change, MoveDate):
            self._move_to_date(change)

    def _date_judge(self, block_id: str, from_iso: str, to_iso: str) -> HandVerdict:
        """Whether a block carried on Month can go on a date: the same rule a save applies. A chip
        from a week that is not loaded is judged by the time and homework the month reply gives it."""
        days = (self.session.month_data or {}).get("days") or []
        day = next((item for item in days if item.get("date") == from_iso), {})
        chip = next((item for item in day.get("blocks") or [] if item.get("id") == block_id), {})
        problem = self.session.date_problem(
            block_id,
            from_iso,
            to_iso,
            start=chip.get("start"),
            duration_min=chip.get("duration_min"),
            assignment_id=chip.get("assignment_id"),
        )
        return HandVerdict(problem is None, problem or "")

    def _move_to_date(self, change: MoveDate) -> None:
        """A chip let go on another date. While a save is on its way it waits for it, as a block let
        go on the hours does; nothing is shown moved until the server has it. A change that did not
        save is not waited on: the drop is refused in words, not kept to happen later."""
        if self.session.busy:
            self._date_waiting = change
            return
        if self.session.pending_save is not None or self.session.conflict:
            self.session._say("Not moved: your last change has not saved yet. Try again once it has.")
            return
        if self.session.move_to_date(change.block_id, change.from_iso, change.to_iso):
            title = self._title_of(change.block_id, change.from_iso)
            self._say_when_saved(dated_words(title, change.to_iso, self._today()))

    def _title_of(self, block_id: str, iso: str) -> str:
        """A block's title, from this week or, for a chip from another week, from what Month shows."""
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            days = (self.session.month_data or {}).get("days") or []
            day = next((item for item in days if item.get("date") == iso), {})
            block = next((item for item in day.get("blocks") or [] if item.get("id") == block_id), None)
        return (block or {}).get("title") or "the block"

    def _hold_renders(self, holding: bool) -> None:
        """Nothing a press started on is rebuilt until it is let go, whether it becomes a drag or a tap."""
        for view in self._views.values():
            view.hold(holding)
        if not holding:
            refresh_week = self.hand.release_kind is not Gesture.CREATE
            QTimer.singleShot(0, self, lambda: self._refresh_after_hold(refresh_week=refresh_week))

    def _refresh_after_hold(self, *, refresh_week: bool = True) -> None:
        if self.session.account is not None and not self.hand.busy:
            if refresh_week:
                self._fill_classic()
            self._show_change()

    def _set_notice(self, text: str, button: str, callback) -> None:
        """Words with one thing to do about them, such as Undo, in the active surface's presenter."""
        self._notice_step = None
        if button == "Undo" and self._material_owns() and self._material_page is not None:
            self.toast.hide()
            self._material_page.bridge.note(text)
        else:
            self.toast.show_message(text, button, callback)
        if button == "Undo":
            self._undo_at = time.monotonic()
            focus = QApplication.focusWidget()
            self._undo_button = focus.objectName() if focus is not None else ""

    def _first_placed(self) -> tuple[str, int, int] | None:
        """The block the plan placed first: its id, the day it is on and where it starts."""
        placed = (self.session.trace or {}).get("placed") or []
        for item in placed:
            block = next((b for b in self.session.blocks if b["id"] == item.get("id")), None)
            if block is not None and block.get("start") and block.get("days"):
                return block["id"], block["days"][0], hhmm_to_minutes(block["start"])
        return None

    def _undo_from_notice(self) -> None:
        self._notice_step = None
        self.session.undo()
        self._focus_week()

    def _say_repeats_kept(self, words: str) -> None:
        """Later weeks kept their own change when School or an activity changed from this week on: said
        in the active surface's message area, without Undo (later weeks have none) and without blocking."""
        if self._material_owns() and self._material_page is not None:
            self.toast.hide()
            self._material_page.bridge.note(words, action="")
        else:
            self.toast.show_message(words, "", None)

    def _say_when_saved(self, words: str) -> None:
        """`words` say what the save now on its way changes, once it lands, with Undo. A change that
        started no save says nothing."""
        self._change_saving = words if self.session.busy else None

    def _show_change(self) -> None:
        # Not while a block is held: nothing new appears beside the hours until the release.
        if self._change_saved is None or self.hand.busy:
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
        self._sync_undo_enabled()
        self._notice_step = self.session.last_step()
        # The week redraws in this same turn and can take the keyboard (a Clay day header, or More
        # on Dial). Focusing on the next turn lands after that.
        self._focus_placed = self._first_placed()
        self._plan_focus_pending = True

    def _focus_after_plan(self) -> None:
        self.activateWindow()
        self._focus_week(getattr(self, "_focus_placed", None))

    def _focus_after_redo(self) -> None:
        self.activateWindow()
        self._focus_week()

    def _redo_with_focus(self) -> None:
        self._redo_focus_pending = True
        self.session.redo()
        if self.session._traveling != "redo":
            self._redo_focus_pending = False

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

    def _add_from_chip(self, category: str, plain: bool = False) -> None:
        """Add of this type. `plain` is the Add button (or C) with the type already picked: a plain Add,
        so it opens on what Esc kept, as Ctrl+N does. A pick from the menu brings its own type and
        leaves the kept typing for the next plain Add."""
        self.session.arm_category(category)
        self._sync_add_button()
        if category in FLEX_CATEGORIES:
            draft, days, moved = self._take_kept_add("homework") if plain else (None, None, [])

            def build() -> HomeworkDialog:
                dialog = HomeworkDialog(self, today=self._today(), category=category)
                if draft:
                    dialog.apply_draft(draft)
                if moved:
                    dialog.show_moved_days(moved)
                return dialog

            self._commit_homework(self._sheet(build), days)
            return
        day, start = self._new_event_values()
        kept = self._take_kept_add("block") if plain else (None, None, [])
        self._commit_new_block(day, start, category, draft=kept[0], moved=kept[2])

    def _create_by_drag(self, span: Span) -> None:
        before = {item["id"] for item in self.session.blocks}
        self._create_range(span.day, span.start, span.end)
        made = [item for item in self.session.blocks if item["id"] not in before]
        if made:
            self._say_when_saved(added_words(made[0], self.session.week_start))

    def _create_range(self, day: int, start_min: int, end_min: int) -> None:
        start = minutes_to_hhmm(start_min)
        duration = end_min - start_min
        category = self.session.armed_category
        if category in FLEX_CATEGORIES:
            self._commit_homework(
                self._sheet(
                    lambda: HomeworkDialog(
                        self,
                        category=category,
                        estimate_min=duration,
                        due=sunday_due(self.session.week_start),
                    )
                ),
                days=[day],
            )
            return
        self._commit_new_block(day, start, category, duration, from_range=True)

    def _due_point(self, block_id: str) -> tuple[int, int] | None:
        """The day and minute a homework session is due, for the calendar to refuse a drag past it."""
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        assignment = self.session.assignments.get((block or {}).get("assignment_id") or "")
        if not assignment:
            return None
        return due_point(assignment.get("due"), self.session.week_start)

    def _delete_homework(self, assignment_id: str, ask: bool = True) -> None:
        """Homework and its times in every week, gone in one step that Undo brings back."""
        assignment = self.session.assignments.get(assignment_id)
        if assignment is None:
            return
        title = assignment.get("title") or "this homework"
        words = f"Delete {title}? Its times on the calendar go too, in every week. You can undo this."
        if ask and not confirm(self, "Delete homework", words, "Delete"):
            return
        if self.session.delete_homework(assignment_id):
            self._say_when_saved(f"Deleted {title}.")

    def _edit_homework(self, assignment_id: str) -> None:
        assignment = self.session.assignments.get(assignment_id)
        if assignment is None:
            return
        sessions = [block for block in self.session.blocks if block.get("assignment_id") == assignment_id]
        waiting = any(not block.get("start") and not block.get("completed") for block in sessions)
        pinned = any(block.get("pinned") for block in sessions)
        self._commit_homework(
            self._sheet(lambda: HomeworkDialog(self, assignment, waiting=waiting, pinned=pinned))
        )

    def _choose_time_for_homework(self) -> None:
        """The first homework this week that still needs a time, opened in Choose a time."""
        for assignment in sorted(
            self.session.assignments.values(),
            key=lambda item: (bool(item.get("completed")), item.get("due") or "", item.get("title") or ""),
        ):
            waiting = [
                block
                for block in self.session.blocks
                if block.get("assignment_id") == assignment["id"]
                and not block.get("start")
                and not block.get("completed")
            ]
            if waiting:
                self._choose_time(assignment["id"])
                return
        self.session._say(
            homework_time_sentence(self.session.unfinished(), self.session.homework_time_needed())
        )

    def _choose_time(self, assignment_id: str) -> None:
        """A time for this homework's first session that needs one, picked rather than dragged."""
        waiting = [
            item
            for item in self.session.blocks
            if item.get("assignment_id") == assignment_id
            and not item.get("start")
            and not item.get("completed")
        ]
        if not waiting:
            return
        block = waiting[0]
        due = self._due_point(block["id"])
        days = list(block["days"])
        clock = clock_parts(self.session.now_ms())
        today = self.session.today_column(clock["iso"])
        dialog = ChooseTimeDialog(
            self,
            block,
            self.session.week_start,
            days,
            self.session.blocks,
            due,
            today,
            clock["minute"],
            now=(clock["iso"], int(clock["minute"])),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        day, start = dialog.choice()
        if self.session.hand_move(block["id"], -1, day, start, start + dialog.length_min()):
            self.session.save()

    def _judge_span(self, block_id: str, from_day: int, day: int, start: int, end: int) -> HandVerdict:
        """Whether a block can go where it is being dragged, and the words for it. One rule for the
        calendar and every design: another block there is allowed, and said, as in Daily Scheduler;
        time FlexWeek does not plan in, and homework ending after it is due, are not."""
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            return HandVerdict(False, "")
        answer = self.session.judge_hand_move(block_id, from_day, day, start, end)
        if not answer["moved"]:
            return HandVerdict(False, answer["problem"])
        words = span_words(Span(day, start, end), self.hand.day_name) + (
            f" · beside {answer['beside']}" if answer["beside"] else ""
        )
        return HandVerdict(True, words)

    def _move_block(self, block_id: str, from_day: int, day: int, start: int, end: int) -> None:
        """A block let go at a time, on the calendar or in a design. The session applies it, or keeps
        it when a save is already on its way."""
        self.session.place_block(block_id, from_day, day, start, end)

    def _edit_block(self, block_id: str) -> None:
        if QApplication.activeModalWidget() is not None:
            # One editor at a time: a click that lands while one is opening opens nothing more.
            return
        if self.session.planner_view == "day":
            self.session.select_block(block_id, self._selected_column())
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            return
        assignment_id = block.get("assignment_id")
        if assignment_id and assignment_id in self.session.assignments:
            self._edit_homework(assignment_id)
            return
        if block.get("kind") != "locked":
            return
        self._commit_block(
            self._sheet(lambda: BlockDialog(self, block, occurrence_day=self.session.selected_occurrence_day))
        )

    def _block_menu(self, block_id: str, day: int, at: QPoint) -> None:
        """A block's right-click menu: Open, Duplicate, Finished for homework, and Delete, each the
        path its button or key already takes. `day` is -1 for homework with no time yet."""
        block = next((item for item in self.session.blocks if item["id"] == block_id), None)
        if block is None:
            return
        on = day if day >= 0 else None
        self.session.select_block(block_id, on)
        assignment = self.session.assignments.get(block.get("assignment_id") or "")
        menu = Menu(self)
        menu.setObjectName("blockMenu")
        menu.set_colours(self.more_menu.colours())
        menu.add("Open", "pencil", keys="Enter", name="blockMenuOpen")
        if block.get("start"):
            menu.add("Duplicate", "copy-plus", keys="Ctrl+D", name="blockMenuDuplicate")
            menu.add("Copy", "copy", keys="Ctrl+C", name="blockMenuCopy")
        if assignment is not None and not assignment.get("completed"):
            menu.add("Finished", "circle-check", name="blockMenuFinished")
        menu.addSeparator()
        menu.add("Delete", "trash", keys="Del", danger=True, name="blockMenuDelete")
        chosen = menu.exec(at)
        menu.deleteLater()
        picked = chosen.objectName() if chosen is not None else ""
        if picked == "blockMenuOpen":
            self._edit_block(block_id)
        elif picked == "blockMenuDuplicate":
            self._duplicate_selected()
        elif picked == "blockMenuCopy":
            self.session.select_block(block_id, on)
            self._copy_selected()
        elif picked == "blockMenuFinished" and assignment is not None:
            self._finish_homework(assignment["id"])
        elif picked == "blockMenuDelete":
            self._delete_from_block_menu(block, assignment, on)

    def _delete_from_block_menu(self, block: dict, assignment: dict | None, on: int | None) -> None:
        if assignment is None:
            one_day = is_series(block) and on is not None
            if is_setup_block(block) and not (one_day and len(block.get("days") or []) > 1):
                # _delete_block asks this week or every week.
                self._delete_block(block, "occurrence" if one_day else "series", on)
                return
            name = block.get("title") or "this event"
            if one_day and on is not None:
                name += f" on {day_full_names(self.session.week_start)[on]}"
            if confirm(self, "Delete fixed time", f"Delete {name}? You can undo this.", "Delete"):
                self._delete_block(block, "occurrence" if one_day else "series", on)
            return
        if not block.get("start"):
            self._delete_homework(assignment["id"])
            return
        title = assignment.get("title") or "this homework"
        sessions = [
            item
            for item in self.session.blocks
            if item.get("assignment_id") == assignment["id"] and item.get("start")
        ]
        if len(sessions) <= 1:
            self._delete_homework(assignment["id"])
            return
        sheet = ConfirmSheet(
            self,
            "Delete homework",
            f"Delete {title}? Its times on the calendar go too, in every week. You can undo this.",
            (
                ("stay", "Cancel", "outlined"),
                ("time", "This time", ""),
                ("all", "Delete", "danger"),
            ),
            default="stay",
        )
        sheet.exec()
        if sheet.answer == "time":
            self._delete_block(block, "occurrence", on)
        elif sheet.answer == "all":
            self._delete_homework(assignment["id"], ask=False)

    def _spot_menu(self, day: int, minute: int, at: QPoint) -> None:
        """What an empty spot in the hours offers: fixed time at the step under the pointer, homework
        due that day, and the copied blocks pasted there. Each opens the sheet the Add and Paste
        buttons open, with the day and time filled in."""
        menu = Menu(self)
        menu.setObjectName("spotMenu")
        menu.set_colours(self.more_menu.colours())
        menu.add(f"Add fixed time at {clock_text(minute)}", "clock", name="spotMenuFixed")
        menu.add("Add homework due this day", "book-open", name="spotMenuHomework")
        paste = menu.add("Paste", "clipboard-paste", name="spotMenuPaste")
        session = self.session
        if session.clipboard is None or session.busy:
            # Greyed as in More, with its reason: on the row when nothing is copied, else on hover.
            paste.setEnabled(False)
            waiting = session.busy or session.dirty or session.pending_save is not None
            paste.setToolTip(WAIT_TIP if waiting else GREYED_TIPS["pasteBlock"])
        chosen = menu.exec(at)
        menu.deleteLater()
        picked = chosen.objectName() if chosen is not None else ""
        if picked == "spotMenuFixed":
            self._add_fixed_at(day, minute)
        elif picked == "spotMenuHomework":
            self._add_homework_due(date_for_day(session.week_start, day))
        elif picked == "spotMenuPaste":
            self._told(lambda: self._paste_at(day, minute))

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
    ) -> None:
        """`done` is the verb that says what saving the rows did, as in "Pasted Piano"."""
        if not rows:
            return
        dialog = PreviewDialog(
            self,
            title,
            summary,
            rows,
            existing if existing is not None else self.session.blocks,
        )
        if not self._run_sheet(dialog):
            return
        chosen = [row for row in dialog.rows() if row.get("checked")]
        what = chosen[0]["block"]["title"] if len(chosen) == 1 else f"{len(chosen)} blocks"
        said = f"{done} {what}." if done and chosen else None
        self.session.confirm_preview(
            dialog.rows(),
            label=label,
            snapshot_label=snapshot_label,
            attempt_key=attempt_key,
            existing=existing,
            destination=destination,
            said=said,
        )

    def _copy_selected(self) -> None:
        self.session.copy_selected()

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
            "Nothing changes until you save this preview.",
            rows,
            label=label,
            attempt_key=key,
            done="Pasted",
        )

    def _duplicate_selected(self) -> None:
        chosen = next(
            (item for item in self.session.blocks if item["id"] == self.session.selected_block_id), None
        )
        rows = self.session.duplicate_selected()
        self._show_preview(
            "Preview paste",
            "Nothing changes until you save this preview.",
            rows,
            label="duplicating " + (chosen or {}).get("title", "a block"),
            done="Duplicated",
        )

    def _copy_day(self) -> None:
        self.session.copy_day()

    def _open_routines(self) -> None:
        dialog = RoutineDialog(self, self.session.routines, self.session.blocks, self.session.week_start)
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
                    f"{routine['revision']}|{dest}|" + ",".join(str(day) for day in dialog.days)
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

            self.session.week_blocks(dest, show)
            return

    def _collapse_unfinished(self) -> None:
        self._unfinished_opened = False

    def _counted_items(self) -> list[dict]:
        """The homework the More count counts, as the panel lists it: the time each still needs, and
        Plan only where it would place something."""
        return [
            {
                "id": item["assignment_id"],
                "title": item["title"],
                "remaining_min": item["minutes"],
                "plannable": self.session.remaining_for(item["assignment_id"]) >= 15,
            }
            for item in self.session.homework_time_needed()
        ]

    def _unfinished_items(self, items: list[dict] | None = None) -> list[dict]:
        """The engine classifies overdue and earlier-week homework against the held session clock."""
        return self.session.unfinished() if items is None else items

    def _fill_unfinished(self, items: list[dict]) -> None:
        self.unfinished_panel.set_items(
            items, datetime.fromtimestamp(self.session.now_ms() / 1000), {item["id"] for item in items}
        )

    def _fit_left_chip(self) -> None:
        """Both buttons beside the words when the card is wide enough for the words and both whole;
        otherwise under them. A button is never squeezed to fit its line."""
        plan_them = self.left_chip.findChild(QPushButton, "leftPlan")
        did_these = self.left_chip.findChild(QPushButton, "leftDone")
        margins = self.left_chip.layout().contentsMargins()
        gap = self._chip_line.spacing()
        words = QFontMetrics(self.left_chip_text.font()).horizontalAdvance(self.left_chip_text.text())
        widths = (
            self.left_chip_icon.width(),
            words,
            plan_them.sizeHint().width(),
            did_these.sizeHint().width(),
        )
        beside = margins.left() + margins.right() + sum(widths) + 3 * gap
        wrapped = self.left_chip.width() < beside
        if wrapped == self._chip_wrapped:
            return
        self._chip_wrapped = wrapped
        below = self._chip_below_row
        source, target = (self._chip_line, below) if wrapped else (below, self._chip_line)
        for button in (plan_them, did_these):
            source.removeWidget(button)
            if target is below:
                target.insertWidget(target.count() - 1, button)
            else:
                target.addWidget(button)
        self._chip_below.setVisible(wrapped)

    def _sync_left_chip(self) -> None:
        """Offer overdue and carried homework from the same list used by Plan and More."""
        left = self._unfinished_items()
        overdue = sum(item.get("left_over_state") == "overdue" for item in left)
        carried = len(left) - overdue
        parts = []
        if overdue:
            parts.append(f"{overdue} overdue")
        if carried:
            parts.append(f"{carried} left from last week")
        words = " · ".join(parts)
        self.left_chip_text.setText(words)
        self.left_chip.setAccessibleName(words)
        self.left_chip_icon.setPixmap(
            icons.pixmap("history", self.palette().color(QPalette.ColorRole.Mid).name(), 16)
        )
        self.left_chip.setVisible(bool(left) and not self.unfinished_panel.isVisible())
        self._fit_left_chip()
        if words and words != getattr(self, "_left_chip_words", ""):
            announce(self.left_chip_text, words)
        self._left_chip_words = words

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
        sheet = ConfirmSheet(
            self,
            "Before planning",
            ", ".join(parts),
            (
                ("plan", "Plan into this week", ""),
                ("did", "Mark as finished", "outlined"),
                ("not", "Not now", "quiet"),
            ),
            default="not",
            close_button=False,
        )
        sheet.exec()
        if sheet.answer == "plan":
            self.session.plan_left([item["id"] for item in items])
        elif sheet.answer == "did":
            self.session.did_these([item["id"] for item in items])
        else:
            self.session.plan_asked_week = self.session.week_start
            self._sync_left_chip()

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

    def _panel_items(self) -> list[dict]:
        """Overdue and carried homework, then homework that still needs a time and is not already listed."""
        left = self._unfinished_items()
        seen = {item["id"] for item in left}
        return left + [item for item in self._counted_items() if item["id"] not in seen]

    def _show_unfinished(self) -> None:
        items = self._panel_items()
        if not items:
            self.session._say(NOTHING_UNFINISHED)
        self._fill_unfinished(items)
        self._unfinished_opened = bool(items)
        self._sync_left_chip()

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

    def _late_other_week(self) -> bool:
        now = datetime.fromtimestamp(self.session.now_ms() / 1000)
        return self.session.today_column(now.date().isoformat()) is None

    def _sync_running_late(self) -> None:
        late = self.findChild(QPushButton, "runningLate")
        if late is None:
            return
        other = self._late_other_week()
        late.setEnabled(not self.session.busy and not other)
        late.setToolTip(GREYED_TIPS["runningLate"] if other else MORE_TIPS["runningLate"])

    def _open_late(self) -> None:
        if self._late_other_week():
            return
        now = datetime.fromtimestamp(self.session.now_ms() / 1000)
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
        # Rounded up: a start in the quarter hour that has already begun was a time gone by. After 23:45
        # there is no quarter left today, so it stays the last one.
        ahead, minute = next_slot(now.hour * 60 + now.minute)
        if ahead:
            minute = DAY_END_MIN - SLOT_MIN
        starting = now.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
        from_start = late_from_start(minute)
        now_minute = now.hour * 60 + now.minute
        running = next(
            (
                block
                for block in self.session.blocks
                if block.get("kind") == "flexible"
                and not block.get("completed")
                and block.get("start")
                and self.session.today_column(now.date().isoformat()) in (block.get("days") or [])
                and hhmm_to_minutes(block["start"]) <= now_minute
                < hhmm_to_minutes(block["start"]) + int(block.get("duration_min") or 0)
            ),
            None,
        )
        context = (
            f"{running['title']}, {hhmm_text(running['start'])}, moves 30 min later"
            if running is not None
            else f"Starting from {hhmm_text(from_start)} today ({DAY_FULL[now.weekday()]})."
        )
        dialog = LateDialog(self, context)
        if running is not None:
            dialog.minutes.currentIndexChanged.connect(
                lambda _index: dialog.context.setText(
                    f"{running['title']}, {hhmm_text(running['start'])}, moves "
                    f"{dialog.chosen_minutes()} min later"
                )
            )
        dialog.preview_requested.connect(
            lambda: self.session.preview_running_late(dialog.chosen_minutes(), starting)
        )
        self._late_dialog = dialog
        def say(text: str) -> None:
            self._late_problem(dialog, text)

        self.session.status.connect(say)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        with contextlib.suppress(RuntimeError, TypeError):
            self.session.status.disconnect(say)
        preview = self.session.late_preview
        self._late_dialog = None
        if accepted:
            self._commit_late(preview)
        else:
            self.session.late_preview = None
            if preview is not None:
                # The preview's "N tasks move" stood under the week as if something had moved.
                self.session._say("")

    def _late_problem(self, dialog: LateDialog, text: str) -> None:
        """The dialog's red line is for real problems. The session also says "Replanning…" and the
        preview's "3 tasks move" through the same signal; the dialog shows that count itself, as status."""
        preview = self.session.late_preview or {}
        trace = preview.get("trace") or {}
        summary = _late_summary(len(trace.get("moves") or []))
        if text == "Replanning…" or (preview and text == summary):
            text = ""
        dialog.error.setText(text)

    def _commit_late(self, preview: dict | None) -> None:
        block = None if preview is None else preview.get("block")
        moved = len(((preview or {}).get("trace") or {}).get("moves") or [])
        if not self.session.accept_running_late() or not isinstance(block, dict):
            return
        self.session.select_block(block["id"], (block.get("days") or [0])[0])
        # "Is now locked" waits for the save that stores it. Said at once, it stood on screen for six
        # seconds even when that save failed and the late start was never kept.
        self._late_waiting = (block["id"], late_locked_line(block, moved))

    def _on_save_finished(self, stored: bool, said: str) -> None:
        if not stored:
            # The retry wait starts at a failure, whoever started the save: one started by a button
            # left the timer's last try long ago, and it tried again on its very next tick.
            self._last_try_ms = int(time.monotonic() * 1000)
        change, self._change_saving = self._change_saving, None
        if stored and change is not None:
            self._change_saved = change
            self._show_change()
        elif stored and self._notice_step is not None and self.session.last_step() is not self._notice_step:
            # A later change, or an Undo, has taken the notice's step off the top: its Undo would now
            # take back something else.
            self.toast.hide()
            self._notice_step = None
        if self._late_waiting is None:
            return
        block_id, message = self._late_waiting
        if not stored:
            # "Not saved. …", which the toast has already said.
            self._late_waiting = None
        elif any(item["id"] == block_id for item in self.session.blocks):
            # A save already in flight when Running late was accepted finishes without the late start;
            # the wait is for the one that carries it.
            self._late_waiting = None
            self.session._say(message)

    def _open_availability(self) -> None:
        if self.session.preferences is None:
            self.session._say("Still loading your settings…")
            return
        subjects = sorted(
            {str(item["course"]).strip() for item in self.session.assignments.values() if item.get("course")}
        )
        pack, system_dark, accent = self._look_inputs()
        palette = resolved_palette(pack, system_dark, self._look, accent)
        dialog = AvailabilityDialog(self, self.session.preferences, subjects, palette)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.session.save_availability(dialog.protected(), dialog.day_cutoff(), dialog.work_windows())

    def start_material_focus(self, block_id: str | None, day: object) -> None:
        """Day and My day's Start focus: the session's timer, then Material's Focus screen."""
        self._start_focus(block_id or "", day)

    def _start_focus(self, block_id: str, day: object) -> None:
        if self.session.start_focus(block_id or None, day if isinstance(day, int) else None):
            self._open_focus_screen()

    def _quick_focus(self) -> None:
        """The focus screen, ready: nothing starts until Start, as with F (decision 19 of 0.17)."""
        self._open_focus_screen()

    def _confirm_replace_focus(self, current: str, incoming: str) -> None:
        sheet = ConfirmSheet(
            self,
            "Replace timer",
            f"Stop the timer for {current} and start {incoming} instead?",
            (("keep", "Keep current timer", "quiet"), ("replace", "Replace timer", "danger")),
            default="keep",
        )
        sheet.exec()
        if sheet.answer == "replace" and self.session.confirm_replace_focus():
            self._open_focus_screen()

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
        if self._stack.currentWidget() is not self._material_page and not self._show_surface():
            return
        material = self._material_focus()
        if material is not None:
            material.show()

    def _close_focus_screen(self) -> None:
        material = self._material_focus()
        if material is not None:
            material.hide()

    def _on_focus(self) -> None:
        self.focus_panel.set_state(self.session)
        self._sync_chrome()
        self._refresh_layout()
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
        reminders = []
        for notice in notices:
            title = notice.get("title") or "FlexWeek"
            body = notice.get("body") or ""
            words = title + (" — " + body if body else "")
            if tray is not None:
                tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)
            if notice.get("kind") == "reminder":
                reminders.append(words)
            elif tray is None:
                self.session._say(words)
        if reminders:
            # A desktop can hide a tray message, and FlexWeek cannot tell that it did, so the window
            # says it as well, wherever the student is.
            self._reminder_said = "; ".join(reminders)
            self._say_in_toast(self._reminder_said)
        if notices and prefs.get("reminder_dnd_override"):
            # A tray message is gone in eight seconds and a machine may suppress it outright. This
            # one sits in the window until it is dealt with, which is what the setting promises.
            self.alert_strip.add(notices)

    def _on_alarm(self, alarm: object) -> None:
        if not isinstance(alarm, dict):
            return
        if self._alarm_dialog is not None or self._alarm_on_material:
            return
        url = self.session.spotify_url(alarm.get("spotify_url"))
        if self._ring_on_material(alarm, url):
            return
        dialog = AlarmRingDialog(self, alarm, url)
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
        page = self._material_page
        if page is None or not self._material_owns() or self._stack.currentWidget() is not page:
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
        if page is not None:
            self._update_on_material = True

            def finished(skip: bool) -> None:
                self._update_on_material = False
                if skip:
                    self._updates["skip"] = update["version"]
                    self._save_look()

            page.bridge.sheets.open_update(update, VERSION, lambda: self._updater.download(update), finished)
            return
        dialog = UpdateDialog(self, update, VERSION)
        self._update_dialog = dialog
        dialog.install.clicked.connect(lambda: self._updater.download(update))
        dialog.exec()
        if dialog.skip_this:
            self._updates["skip"] = update["version"]
            self._save_look()
        self._update_dialog = None

    def _update_sheet(self):
        """Material's update sheet while it is the one showing the update, else None."""
        page = self._material_page if self._update_on_material else None
        sheets = None if page is None else page.bridge.sheets
        return sheets if sheets is not None and sheets.update_open() else None

    def _on_update_progress(self, got: int, total: int) -> None:
        if self._update_dialog is not None:
            self._update_dialog.show_progress(got, total)
        elif (sheet := self._update_sheet()) is not None:
            sheet.update_progress(got, total)

    def _on_update_problem(self, why: str) -> None:
        if self._update_dialog is not None:
            self._update_dialog.show_problem(why)
        elif (sheet := self._update_sheet()) is not None:
            sheet.update_problem(why)
        elif self._update_asked:
            self.session._say(why)

    def _on_update_ready(self, path: str) -> None:
        """The download is verified and on disk. Putting it in place replaces the running app, so
        the app is closed either way: on Windows the installer takes over, and on Linux the files
        under it have just been swapped."""
        problem = apply_update(path)
        if problem is not None:
            if self._update_dialog is not None:
                self._update_dialog.show_problem(problem + " Open the release page to update by hand.")
            elif (sheet := self._update_sheet()) is not None:
                sheet.update_problem(problem + " Open the release page to update by hand.")
            return
        if self._update_dialog is not None:
            self._update_dialog.accept()
        elif (sheet := self._update_sheet()) is not None:
            sheet.update_done()
        self.session._say("Update installed. FlexWeek will close so the new version can start.")
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

    def _layout_plan_review(self) -> None:
        """The plan bar floats over the planner, under the panels above it, without pushing them."""
        host = self._week_page
        # The column is a layout, so its rectangle is already in the page's coordinates.
        anchor = self._column.geometry()
        top = anchor.top()
        for piece in (self.focus_panel, self.unfinished_panel):
            if piece.isVisibleTo(host):
                top = max(top, piece.mapTo(host, QPoint(0, piece.height())).y())
        width = anchor.width()
        self.plan_review.setFixedWidth(width)
        height = self.plan_review.sizeHint().height()
        self.plan_review.setGeometry(anchor.left(), top, width, height)
        self.plan_review.raise_()
        # Raised over everything, it would be drawn over a picture sliding or fading across the page.
        raise_pictures(host)

    def _sync_started(self, service: SyncService) -> None:
        self._sync = service
        self._sync_generation = service.generation()
        self._sync_timer.start()
        self._show_sync_dot()

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
        self._show_sync_dot()

    def _phones_read(self, user_id: int, rows: list[dict] | None) -> None:
        self._phones_reading = False
        self._phones = rows or []
        self._phones_user = user_id
        self._show_sync_dot()

    def _linked_phones(self) -> list[dict]:
        account = self.session.account
        if account is None or self._phones_user != account["id"]:
            return []
        return self._phones

    def _show_sync_dot(self) -> None:
        if self._sync is None:
            return
        self.sync_dot.show_state(sync_state(self._sync.status(), bool(self._linked_phones())))

    def _sync_arrived(self, _service: SyncService) -> bool:
        """Loads the week again after a phone's edits land. With unsaved edits here, it marks the week
        as changed instead, so the existing Reload and Keep mine choice is offered. False while a
        request is in flight; the next tick asks again."""
        names = [row["name"] for row in self._linked_phones()]
        who = names[0] if len(names) == 1 else "a linked phone"
        return self.session.accept_remote_week(who)

    def watch_database(self, database: Path) -> None:
        """Show changes another program makes to `database`, the one the local server keeps."""
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

    def _open_restore(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openRestore()
            return
        dialog = RestoreDialog(
            self, self.session.restore_points, self.session.restore_preview, self.session.storage_info
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.action == "create":
            self.session.create_restore_point(dialog.create_label)
        elif dialog.action == "preview" and dialog.selected_id:
            self.session.preview_restore_point(dialog.selected_id, lambda: self._told(self._open_restore))
        elif dialog.action == "restore" and dialog.selected_id:
            sheet = ConfirmSheet(
                self,
                "Restore",
                "Restore this snapshot? FlexWeek saves a restore point first.",
                (("not", "Not now", "quiet"), ("restore", "Restore", "danger")),
                default="not",
            )
            sheet.exec()
            if sheet.answer == "restore":
                self.session.apply_restore_point(dialog.selected_id)

    def _log_out(self) -> None:
        where = (
            "your FlexWeek server"
            if (self.session.storage_info or {}).get("mode") == "hosted"
            else "this computer"
        )
        question = SIGN_OUT_QUESTION.format(where=where)
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.ask_sign_out(question, self._sign_out_confirmed)
            return
        if confirm(self, "Sign out", question, "Sign out", danger=False):
            self._sign_out_confirmed()

    def _sign_out_confirmed(self) -> None:
        # Same wait as closing: an unsent Settings change has to reach the server, or stay on screen.
        if self._save_before_leaving(self.session.logout, again="sign out again"):
            self.session.logout()

    def _material_shown(self):
        """The Material page while it is the page on screen and built, else None."""
        page = self._material_page
        if page is None or page.root is None or self._stack.currentWidget() is not page:
            return None
        return page

    def _open_help(self) -> None:
        page = self._material_shown()
        if page is None:
            HelpDialog(self, self._key_switches()).exec()
            return
        page.bridge.sheets.openHelp()

    def _open_about(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openAbout()
            return
        AboutDialog(self, self.session.storage_info, str(self._look_path().parent)).exec()

    def _open_account(self) -> None:
        page = self._material_shown()
        if page is not None:
            page.bridge.sheets.openAccount()
            return
        qml_focus_item = None
        if hasattr(self, "_material_page") and self._material_page is not None:
            quick = getattr(self._material_page, "_quick", None)
            if quick is not None and quick.quickWindow() is not None:
                qml_focus_item = quick.quickWindow().activeFocusItem()
        origin = QApplication.focusWidget()
        dialog = AccountDialog(self, self.session.recovery_remaining, self.session.storage_info)
        pack, dark, accent = self._look_inputs()
        eye = resolved_palette(pack, dark, self._look, accent)["muted"]
        for field in (dialog.current_password, dialog.new_password):
            field.set_colour(eye)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            password = dialog.current_password.text()
            if dialog.action == "password":
                self.session.change_password(password, dialog.new_password.text())
            elif dialog.action == "codes":
                self.session.replace_recovery_codes(password)
            elif dialog.action == "delete":
                name = (self.session.account or {}).get("username") or "this account"
                where = (
                    "your FlexWeek server"
                    if (self.session.storage_info or {}).get("mode") == "hosted"
                    else "this computer"
                )
                question = DELETE_ACCOUNT_QUESTION.format(name=name, where=where)
                if confirm(self, "Delete account", question, f"Delete {name}"):
                    self.session.delete_account(password)
            elif dialog.action == "export":
                self.session.export_account(password, self._write_account_file)
            elif dialog.action == "import":
                path, _ = QFileDialog.getOpenFileName(self, "Import backup file", "", "JSON (*.json)")
                if not path:
                    return
                try:
                    snapshot = json.loads(Path(path).read_text())
                except (OSError, UnicodeDecodeError, ValueError):
                    self.session._say(READ_FAILED)
                    return
                if not isinstance(snapshot, dict):
                    self.session._say(READ_FAILED)
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
                except (OSError, UnicodeDecodeError):
                    self.session._say(READ_WEEK_FAILED)
                    return
                parsed = parse_import_payload(raw)
                if parsed.get("error"):
                    self.session._say(parsed["error"])
                    return
                if parsed.get("format") == EXPORT_FORMAT and self.session.blocks:
                    question = REPLACE_WEEK_QUESTION.format(
                        week=week_label(self.session.week_start, self._today())
                    )
                    if not confirm(self, "Replace week", question, "Replace week"):
                        return
                    self.session.import_week_file(raw, replace=True)
                else:
                    self.session.import_week_file(raw)
        finally:
            if qml_focus_item is not None:
                qml_focus_item.forceActiveFocus()
            elif origin is not None:
                origin.setFocus()

    def _confirm_transfer(self) -> None:
        preview = self.session.transfer_preview
        if preview is None:
            return
        dialog = TransferPreviewDialog(self, preview)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.apply_account_import()

    def _write_account_file(self, snapshot: dict) -> None:
        name = "flexweek-account-" + snapshot.get("username", "account") + ".json"
        path = self._write_json(name, snapshot)
        if path:
            self.session._say(ACCOUNT_SAVED.format(path=path))

    def _write_json(self, name: str, payload: dict) -> str:
        """Writes the file the student picks and returns its path, or "" when nothing was written."""
        import json

        path, _ = QFileDialog.getSaveFileName(self, "Save FlexWeek file", name, "JSON (*.json)")
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
        self._has_saved_design_look = False
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
        raw_layout = stored.get("layout") if isinstance(stored, dict) else None
        self._has_saved_design_look = self._layout_has_saved_look(raw_layout)
        self._layout = sanitize_layout(raw_layout)
        self._surface = sanitize_surface(stored)
        self._cpu_drawing_version = cpu_drawing.saved_version(stored)
        self._material_gave_up = False
        self._updates = sanitize_updates(stored.get("updates") if isinstance(stored, dict) else None)
        self._zoom = sanitize_zoom(stored.get("zoom") if isinstance(stored, dict) else None)
        self._saved_looks = sanitize_saved(stored.get("saved_looks") if isinstance(stored, dict) else None)
        rail = stored.get("rail") if isinstance(stored, dict) else None
        self.rail.set_month_shown(not (isinstance(rail, dict) and rail.get("month") is False))
        seen = stored.get("new_look_notice_seen") if isinstance(stored, dict) else None
        if isinstance(seen, list):
            self._new_look_notice_seen = {item for item in seen if isinstance(item, str) and item}
        exempt = stored.get("new_look_notice_exempt") if isinstance(stored, dict) else None
        if isinstance(exempt, list):
            self._new_look_notice_exempt = {item for item in exempt if isinstance(item, str) and item}

    @staticmethod
    def _layout_has_saved_look(layout: object) -> bool:
        if not isinstance(layout, dict):
            return False
        options = layout.get("options")
        return isinstance(options, dict) and any(
            isinstance(values, dict) and isinstance(values.get("look"), str) and bool(values["look"])
            for values in options.values()
        )

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
                "rail": {"month": self.rail.month_shown},
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
            self._has_saved_design_look = self._layout_has_saved_look(body["layout"])
        except OSError:
            self.session._say("Could not save the look for this device.")

    def _apply_appearance(self) -> None:
        """Dress the app chrome and current design from the design's selected look."""
        pack, system_dark, accent = self._look_inputs()
        look = self._worn_look()
        if not self._wears_carried_look():
            layout_id = self._layout["day"] if self._day_mode else self._layout["main"]
            token = options_for(self._layout, layout_id)["look"]
        else:
            token = "your"
        # Blocks and month cells are painted per item, which a stylesheet cannot reach.
        palette, look = design_look(token, pack, system_dark, look, accent)
        art = control_art(palette)
        sheet = pack_stylesheet(pack, system_dark, look, accent, palette, art)
        ctx = context_for(self._layout, look, palette, sheet)
        heroes = ("settingsTitle", "sheetTitle", "setupTitle", "authBrand")
        extra = extra_stylesheet(sheet, ctx.feel, palette, ctx.tokens, look, heroes)
        chips = bool((self.session.preferences or {}).get("accent_chips"))
        chosen_motion = (self.session.preferences or {}).get("motion")
        self._motion = motion_level(chosen_motion, look_motion(look))
        dressed = (sheet, repr(look), repr(palette), chips, self._motion, ctx.feel.key)
        # Every change to the week comes through here. Restyling the whole window each time, when the
        # look had not changed, cost about 26 ms a change and repainted everything on screen.
        if dressed != self._dressed:
            self._discard_block_spare()
        set_current(ctx)
        if dressed != self._dressed:
            self._dressed = dressed
            # Retro sets its words letter by letter (fonts.without_ligatures). Only the features change, so
            # a time keeps its even figures and a strong word its weight; each sweep also reaches widgets made
            # since the last, and leaving Retro gives every widget back the font it had, or its parent's.
            if ctx.feel.key == "retro":
                if not hasattr(self, "_retro_fonts"):
                    self._retro_fonts = weakref.WeakKeyDictionary()
                for child in (self, *self.findChildren(QWidget)):
                    if child not in self._retro_fonts:
                        own = child.testAttribute(Qt.WidgetAttribute.WA_SetFont)
                        self._retro_fonts[child] = (QFont(child.font()), own)
                    child.setFont(without_ligatures(child.font()))
            elif hasattr(self, "_retro_fonts"):
                for child, (font, own) in list(self._retro_fonts.items()):
                    if isValid(child):
                        child.setFont(font if own else QFont())
                del self._retro_fonts
            from desktop.native.feel import bar_chrome

            retro_bar = ctx.feel.key == "retro"
            self.setStyleSheet(sheet + (bar_chrome(ctx.tokens) if retro_bar else ""))
            self._bar_strip.setVisible(retro_bar)
            self._keep_bar_whole()
            apply_ui_effects(self._motion)
            self.toast.motion = self._motion
            self._dress_overlays(palette)
            self.week_table.set_look(look, palette)
            self.day_view.set_look(look, palette)
            self.rail.set_look(look, palette)
            self.more_button.set_palette(palette)
            self.solve_button.set_palette(palette)
            self._dress_plan_button(palette)
            self.month_grid.set_palette(palette)
            self.add_menu.set_palette(palette, chips)
            self._dress_feel(ctx, sheet, extra)
            self._maybe_prepare_block_spare()
            fit_buttons(self)
            self._keep_bar_whole()
        self._sync_add_button()
        self._refresh_layout()

    def _feel_roots(self) -> list[QWidget]:
        """What J13 dresses: the open dialogs. Not the week, day, rail or bar."""
        roots: list[QWidget] = []
        roots.extend(dialog for dialog in self.findChildren(QDialog) if dialog.isVisible())
        return roots

    def _dress_feel(self, ctx: Context, sheet: str, extra: str) -> None:
        for root in self._feel_roots():
            root.setStyleSheet(sheet + extra if extra else "")
            apply_feel(root, ctx)

    def _dress_overlays(self, palette: dict) -> None:
        """What a style sheet cannot reach in the focus screen, the toast, Ctrl+K and the menus: the
        ring's colours, icons in the text's colour, and shadows, which a look without depth goes
        without (decisions 6 and 19 to 22 of 0.17)."""
        knobs = effective_look(self._look)
        lifted = knobs["depth"] == "soft"
        dark = palette.get("axis") == "dark"
        corner = look_measures(self._look)["card_radius"]
        self.toast.set_look(toast_colours(palette)["action"], SHADOW_SMALL if lifted else None, dark)
        colours = menu_colours(palette, lifted=lifted, corner=corner)
        for menu in (self.more_menu, self.add_menu):
            menu.set_colours(colours)

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
        tried = {"week": False}
        waited = 0

        def stop() -> None:
            timer.stop()
            timer.deleteLater()
            self._leaving = None

        def give_up() -> None:
            stop()
            session._say(
                "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. "
                f"Choose Retry save, then {again}."
            )
            self.restore_window()

        def poll() -> None:
            nonlocal waited
            waited += LEAVE_POLL_MS
            if waited > LEAVE_WAIT_MS:
                give_up()
                return
            if session.busy:
                return
            if session._held():
                if tried["week"]:
                    give_up()
                    return
                tried["week"] = True
                session.save()
                return
            parked = session.parked_unsaved_week()
            if parked is not None:
                tried["week"] = False
                session.load_week(parked)
                return
            stop()
            self._saved_to_leave = True
            try:
                leave()
            finally:
                self._saved_to_leave = False

        timer.timeout.connect(poll)
        timer.start()
        return False

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """Qt gives a right-click's context menu to the widget under the pointer only when the pointer
        did not move between the press and the release. A hand or a touchpad nearly always moves a few
        pixels, and the menu then came to the window instead, so a block's or free time's menu opened about
        one time in ten. It goes on to the widget the pointer is over."""
        target = QApplication.widgetAt(event.globalPos())
        by_mouse = event.reason() == QContextMenuEvent.Reason.Mouse
        if not by_mouse or target is None or target is self or self._relaying:
            super().contextMenuEvent(event)
            return
        self._relaying = True
        try:
            relayed = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse, target.mapFromGlobal(event.globalPos()), event.globalPos()
            )
            QApplication.sendEvent(target, relayed)
        finally:
            self._relaying = False
        event.setAccepted(relayed.isAccepted())

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
        if not self._saved_to_leave and not self._save_before_leaving(self.close):
            event.ignore()
            return
        self._stop_material_ring()
        for bridge in self.findChildren(QObject, "materialBridge"):
            dispose = getattr(bridge, "dispose", None)
            if callable(dispose):
                dispose()
        super().closeEvent(event)

    def _week_surfaces(self) -> list:
        page = self.planner.currentWidget()
        if page is None or self._stack.currentWidget() is not self._week_page:
            return []
        # The design's own order: Clay's front card first, and Dial's ring, which is not an hours canvas.
        found = page.hours_surfaces() if hasattr(page, "hours_surfaces") else page.findChildren(HoursCanvas)
        return [hours for hours in found if hours.isVisible() and hasattr(hours, "take_focus")]

    def _focus_week(self, placed: tuple[str, int, int] | None = None) -> None:
        """Keyboard focus back on the week: on `placed` (a block's id, day and start) when it is shown,
        else on the hours. Left alone it falls to whatever button comes next in the top bar, and a stray
        Space or Enter then turns the page. The ring is drawn when the student was last on the keyboard,
        never after a click."""
        surfaces = self._week_surfaces()
        if not surfaces:
            return
        shown = next(
            (hours for hours in surfaces if placed and hours.track_for(placed[1], placed[2])), surfaces[0]
        )
        shown.take_focus(self._last_input.keyboard, placed)

    def _focus_top_bar(self) -> None:
        """Esc in the hours: the keyboard goes up to the button for the view shown, which does nothing
        when pressed by mistake."""
        name = {"day": "viewDay", "month": "viewMonth"}.get(self.session.planner_view, "viewWeek")
        button = self.findChild(QRadioButton, name)
        if button is not None:
            button.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _watch_field(self, _old: QWidget | None, now: QWidget | None) -> None:
        """A box on the week page that takes keys of its own is watched, so Ctrl+Z and Ctrl+Y reach the
        week through it while it has nothing typed to undo."""
        if (
            isinstance(now, EDITABLE)
            and not now.property("undoWatched")
            and self._week_page.isAncestorOf(now)
        ):
            now.setProperty("undoWatched", True)
            now.installEventFilter(self)

    @staticmethod
    def _undo_passes(box: QWidget, event: QKeyEvent) -> bool:
        """Whether Ctrl+Z or Ctrl+Y in `box` belongs to the week: the box has no typed text of its own
        to undo or redo."""
        control = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        if not control or event.key() not in (Qt.Key.Key_Z, Qt.Key.Key_Y):
            return False
        line = box.findChild(QLineEdit) if isinstance(box, (QAbstractSpinBox, QComboBox)) else box
        if isinstance(line, QLineEdit):
            return not (line.isUndoAvailable() or line.isRedoAvailable())
        if isinstance(line, QPlainTextEdit):
            return not (line.document().isUndoAvailable() or line.document().isRedoAvailable())
        return True

    def _key_switches(self) -> tuple[bool, bool]:
        """Number keys and Letter keys: the two saved settings Material's Settings also writes
        (`material.shortcuts` and `material.letters` in the look file), so a switch turned over in one look
        is turned over in the other. Read again when the file changes."""
        path = self._look_path()
        try:
            info = path.stat()
        except OSError:
            stamp = None
        else:
            stamp = (info.st_mtime_ns, info.st_size)
        if stamp != self._key_stamp:
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stored = None
            self._key_values = (read_shortcuts(stored), read_letter_keys(stored))
            self._key_stamp = stamp
        return self._key_values

    def _shared_key_action(self, event: QKeyEvent) -> Callable[[], None] | None:
        """What a bare 1 to 4 or letter does in the plain look, when its switch is on: the one key set
        Material shares. None for any other key, a key with a modifier, or a page that is not the week or
        the focus screen. Typing in a box and open dialogs are ruled out before this is asked."""
        if event.modifiers() & KEY_MODIFIERS:
            return None
        current = self._stack.currentWidget()
        if current is not self.findChild(QWidget, "weekPage"):
            return None
        numbers, letters = self._key_switches()
        views: dict[Qt.Key, Callable[[], None]] = {}
        if numbers:
            views |= {
                Qt.Key.Key_1: lambda: self._choose_view("day"),
                Qt.Key.Key_2: lambda: self._choose_view("week"),
                Qt.Key.Key_3: lambda: self._choose_view("month"),
                Qt.Key.Key_4: self._enter_day,
            }
        if letters:
            views |= {
                Qt.Key.Key_T: self._go_today,
                Qt.Key.Key_D: lambda: self._choose_view("day"),
                Qt.Key.Key_W: lambda: self._choose_view("week"),
                Qt.Key.Key_M: lambda: self._choose_view("month"),
                Qt.Key.Key_J: self._next_if_shown,
                Qt.Key.Key_K: self._previous_if_shown,
                Qt.Key.Key_C: self._add_now,
                Qt.Key.Key_P: self._plan_with_left_over,
                Qt.Key.Key_Z: lambda: self._told(self.session.undo),
                Qt.Key.Key_F: self._open_focus_screen,
            }
        action = views.get(event.key())
        if action is None:
            return None
        return action

    def _next_if_shown(self) -> None:
        """J: the next week, day or month, whichever is shown. My day is today only."""
        if not self._day_mode:
            self._go_next()

    def _previous_if_shown(self) -> None:
        if not self._day_mode:
            self._go_previous()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.session.account is None or QApplication.activeModalWidget() is not None:
            super().keyPressEvent(event)
            return
        current = self._stack.currentWidget()
        if current is not None and current.objectName() == "materialPage":
            mods = event.modifiers()
            if event.key() == Qt.Key.Key_S and mods & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            ):
                self._told(self.session.save)
                event.accept()
                return
            # The QML shell has its own Undo, Redo and More. The week shortcuts stay off.
            super().keyPressEvent(event)
            return
        if self._on_recovery():
            super().keyPressEvent(event)
            return
        focus = QApplication.focusWidget()
        key = event.key()
        mods = event.modifiers()
        if isinstance(focus, EDITABLE) and not self._undo_passes(focus, event):
            super().keyPressEvent(event)
            return
        if (
            key == Qt.Key.Key_Escape
            and not mods
            and self.toast.isVisible()
            and bool(self.toast.card.property("card"))
        ):
            self.toast.close_button.click()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and not mods and isinstance(focus, HoursCanvas) and not self._day_mode:
            self._focus_top_bar()
            event.accept()
            return
        planning = self._stack.currentWidget() is self.findChild(QWidget, "weekPage")
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if key == Qt.Key.Key_N and planning:
                self._add_homework()
                event.accept()
                return
            if key == Qt.Key.Key_Z:
                if mods & Qt.KeyboardModifier.ShiftModifier:
                    self._told(self._redo_with_focus)
                else:
                    self._told(self.session.undo)
                event.accept()
                return
            if key == Qt.Key.Key_Y:
                self._told(self._redo_with_focus)
                event.accept()
                return
            if key == Qt.Key.Key_C:
                self._told(self._copy_selected)
                event.accept()
                return
            if key == Qt.Key.Key_V:
                self._told(self._paste_clipboard)
                event.accept()
                return
            if key == Qt.Key.Key_D:
                self._told(self._duplicate_selected)
                event.accept()
                return
            if key == Qt.Key.Key_S:
                self._told(self.session.save)
                event.accept()
                return
            if key == Qt.Key.Key_F and mods & Qt.KeyboardModifier.ShiftModifier and planning:
                self._quick_focus()
                event.accept()
                return
            if key in ZOOM_KEYS:
                for hours in self._hours_shown():
                    hours.zoom_by(ZOOM_KEYS[key])
                event.accept()
                return
        if key == Qt.Key.Key_Delete:
            if self.session.delete_selected():
                self.session.save()
            event.accept()
            return
        if key == Qt.Key.Key_F1 and planning:
            self._open_help()
            event.accept()
            return
        shared = self._shared_key_action(event)
        if shared is not None:
            shared()
            event.accept()
            return
        if self._day_mode and key in (Qt.Key.Key_B, Qt.Key.Key_Escape):
            self._leave_day()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        planner = getattr(self, "planner", None)
        week_list_panel = getattr(self, "week_list_panel", None)
        week_access_list = getattr(self, "week_access_list", None)
        if (
            planner is not None
            and watched is planner
            and event.type() == QEvent.Type.Resize
            and week_list_panel is not None
            and week_list_panel.isVisible()
        ):
            self._layout_week_list()
        typed = event.type() == QEvent.Type.KeyPress
        if week_access_list is not None and watched is week_access_list and typed:
            key = event.key()
            if key == Qt.Key.Key_Escape and not event.modifiers():
                self._close_week_access_list()
                return True
            if key == Qt.Key.Key_Menu or (
                key == Qt.Key.Key_F10 and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
            ):
                row = self.week_access_list.currentItem()
                target = row.data(Qt.ItemDataRole.UserRole) if row is not None else None
                if target is not None:
                    block_id, day = target
                    point = self.week_access_list.mapToGlobal(
                        self.week_access_list.visualItemRect(row).center()
                    )
                    self._block_menu(block_id, day, point)
                return True
        if event.type() == QEvent.Type.Resize and watched in (
            getattr(self, "week_table", None),
            getattr(self, "day_view", None),
        ):
            self._center_empty_card()
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide) and watched in (
            getattr(self, "plan_review", None),
            getattr(self, "unfinished_panel", None),
        ):
            self.month_grid.set_tight(
                any(panel.isVisibleTo(self._week_page) for panel in (self.plan_review, self.unfinished_panel))
            )
            if watched is self.unfinished_panel:
                self._sync_left_chip()
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        if isinstance(watched, EDITABLE):
            # Only Ctrl+Z and Ctrl+Y, and only past a box with nothing of its own to undo.
            if watched.property("undoWatched") and self._undo_passes(watched, event):
                self.keyPressEvent(event)
                return True
            return super().eventFilter(watched, event)
        key = event.key()
        mods = event.modifiers()
        control = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        if (not control and key in (Qt.Key.Key_F1, Qt.Key.Key_Delete)) or (
            self._shared_key_action(event) is not None
        ):
            self.keyPressEvent(event)
            return True
        if control and key == Qt.Key.Key_F and mods & Qt.KeyboardModifier.ShiftModifier:
            self.keyPressEvent(event)
            return True
        if control and key in (
            Qt.Key.Key_C,
            Qt.Key.Key_V,
            Qt.Key.Key_D,
            Qt.Key.Key_Z,
            Qt.Key.Key_Y,
            Qt.Key.Key_S,
            Qt.Key.Key_K,
            Qt.Key.Key_N,
        ):
            self.keyPressEvent(event)
            return True
        return super().eventFilter(watched, event)
