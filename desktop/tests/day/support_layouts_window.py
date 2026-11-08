"""What the tests that were once one file, "Layouts in the real window", share: the signed-in week they
start from, and the small helpers they read the window with. The tests live by area (day, month, myday,
focus, sheets, settings, week, planner, updater, sync); the window comes from the light app."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, QStandardPaths, Qt  # noqa: E402
from PySide6.QtGui import QAction, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QPushButton,
    QWidget,
    QWidgetAction,
)

from desktop.native.calendar import CATEGORIES, sunday_due  # noqa: E402
from desktop.native.layouts.registry import DESIGN_LOOKS, sanitize_layout  # noqa: E402
from desktop.native.motion import FADE_NAME  # noqa: E402
from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.native.widgets import Segmented  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import LightWindows  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import PASSWORD, look_file, settled, still  # noqa: E402, F401

SPOTIFY_TRACK = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-layouts-window-test"])


def add_school_week(qapp: QApplication, made: NativeWindow) -> None:
    """School every weekday morning and a History essay planned for Thursday 18:45, on the clock's
    Thursday 19:00 (backend.tests.fake_clock)."""
    session = made.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, made)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settled(qapp, made)


def school_week(window: NativeWindow) -> None:
    """For a picture's `prepare`: the window the renderer opened gets the same week the tests start from."""
    add_school_week(QApplication.instance(), window)


def busy_thursday(window: NativeWindow) -> None:
    """A realistic Thursday: five more commitments and three homework with no time yet, so every view has
    its usual number of rows."""
    session = window.session
    for index, (title, start) in enumerate(
        (
            ("Soccer", "15:30"),
            ("Dinner", "18:00"),
            ("Chores", "17:15"),
            ("Reading", "20:00"),
            ("Club", "07:00"),
        )
    ):
        session.add_block(
            {"id": f"busy{index}", "title": title, "kind": "locked", "category": "extra",
             "start": start, "duration_min": 30, "days": [3]}
        )  # fmt: skip
    for index in range(3):
        session.add_homework(
            {"id": f"wait{index}", "title": f"Waiting {index}", "due": sunday_due(session.week_start),
             "estimate_min": 45, "revision": 0}
        )  # fmt: skip


@pytest.fixture()
def window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """A light window signed in on this week with School and a History essay planned for Thursday
    evening, the clock at Thursday 19:00."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open()
        add_school_week(qapp, made)
        yield made
    finally:
        windows.close()


def click(window: NativeWindow, name: str) -> None:
    window.findChild(QAbstractButton, name).click()


def one_thing(window: NativeWindow) -> None:
    """One thing as the day screen. Day dial is the default since 0.16; these tests are about One
    thing's own buttons."""
    window._layout = sanitize_layout({**window._layout, "day": "one"})


def use_layout(window: NativeWindow, main: str = "classic", day: str = "one", day_mode: bool = False) -> None:
    """Put a main view and a day screen on and redraw the week."""
    window._layout = {"main": main, "day": day, "options": {}}
    window._day_mode = day_mode
    window.session.set_view("week")
    window._on_week()
    QApplication.processEvents()


def fades(host: QWidget) -> list[QLabel]:
    """The pictures of old pages still fading out. A finished fade deletes its picture later; the wait helper
    does not run deferred deletes as QTest.qWait did, so they are run here."""
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return [label for label in host.findChildren(QLabel, FADE_NAME) if label.isVisible()]


def at_motion_level(qapp: QApplication, window: NativeWindow, level: str) -> None:
    """Set the animation level and let any fade already under way end."""
    window.session.preferences = {**(window.session.preferences or {}), "motion": level}
    window._apply_appearance()
    wait_until(qapp, lambda: fades(window) == [], what="the fades ending")


def waiting_math(qapp: QApplication, window: NativeWindow) -> dict:
    due = sunday_due(window.session.week_start)
    window.session.add_homework({"id": "math", "title": "Math worksheet", "due": due, "estimate_min": 60})
    window.session.save()
    settled(qapp, window)
    return next(block for block in window.session.blocks if block.get("assignment_id") == "math")


def hours_of(window: NativeWindow):
    hours = window.week_table.hours
    if not hours.tracks:
        hours.resize(980, 640)
        hours.relayout()
    return hours


def _send(widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(widget.mapFromGlobal(at)),
        QPointF(at),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def drop_chip(qapp: QApplication, window: NativeWindow, block_id: str, hhmm: str, day: int) -> None:
    """Drag a homework chip from the tray onto the week's hours at `hhmm` on `day`."""
    click(window, "viewWeek")
    window.move(0, 0)
    window.resize(760, 720)
    for _ in range(5):
        qapp.processEvents()
    hours = hours_of(window)
    minute = int(hhmm[:2]) * 60 + int(hhmm[3:])
    hours.reveal(day, max(minute - 60, 0), minute + 90)
    qapp.processEvents()
    if window.rail.folded:
        window.rail.waiting_chip.click()
        qapp.processEvents()
    chip = next(
        widget
        for widget in window.findChildren(QPushButton)
        if widget.property("block_id") == block_id and widget.property("tray") and widget.isVisible()
    )
    start = chip.mapToGlobal(chip.rect().center())
    end = hours.point_for(day, minute)
    _send(chip, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        moved = QPoint(
            start.x() + (end.x() - start.x()) * step // 8,
            start.y() + (end.y() - start.y()) * step // 8,
        )
        _send(hours, QEvent.Type.MouseMove, moved, True)
    _send(hours, QEvent.Type.MouseButtonRelease, end, False)
    qapp.processEvents()


def drag_on_the_week(
    qapp: QApplication,
    window: NativeWindow,
    day: int,
    hhmm: str,
    to_day: int,
    to: str,
    between: Callable[[], None] | None = None,
) -> None:
    """Press on the week's hours, move and let go, as a mouse does. `between` runs while it is held."""
    click(window, "viewWeek")
    window.move(0, 0)
    window.resize(760, 720)
    for _ in range(5):
        qapp.processEvents()
    hours = hours_of(window)
    start_min = int(hhmm[:2]) * 60 + int(hhmm[3:])
    end_min = int(to[:2]) * 60 + int(to[3:])
    hours.reveal(day, max(min(start_min, end_min) - 60, 0), max(start_min, end_min) + 90)
    qapp.processEvents()

    def point(on: int, when: str) -> QPoint:
        return hours.point_for(on, int(when[:2]) * 60 + int(when[3:]))

    start, end = point(day, hhmm), point(to_day, to)
    _send(hours, QEvent.Type.MouseButtonPress, start, True)
    middle = QPoint((start.x() + end.x()) // 2, (start.y() + end.y()) // 2)
    _send(hours, QEvent.Type.MouseMove, middle, True)
    _send(hours, QEvent.Type.MouseMove, end, True)
    if between is not None:
        between()
        qapp.processEvents()
    _send(hours, QEvent.Type.MouseButtonRelease, end, False)
    qapp.processEvents()


def press(dialog: QDialog, name: str) -> int:
    """What a student does in the homework editor: press one button, which closes it."""
    dialog.findChild(QPushButton, name).click()
    return QDialog.DialogCode.Accepted


# Settings -------------------------------------------------------------------------------------------


def combo(dialog: SettingsPage, name: str) -> QComboBox:
    """A choice by name, whether a dropdown, a segmented control or the design cards: all three
    answer a dropdown's calls."""
    return dialog.findChild(QWidget, name)


def rows(dialog: SettingsPage, slot: str) -> list[str]:
    return sorted(
        box.objectName()
        for box in dialog.findChildren(QWidget)
        if isinstance(box, (QComboBox, Segmented)) and box.objectName().startswith(f"layout{slot}-")
    )


def open_settings(window: NativeWindow) -> SettingsPage:
    """Settings as the gear opens it, in place of the week."""
    window._open_settings()
    page = window._settings
    assert page is not None and window._stack.currentWidget() is page
    return page


def prefs_layout(choice: dict | None = None) -> SettingsPage:
    return SettingsPage(None, {}, {}, {}, choice)


def preference_puts(window: NativeWindow) -> list[dict]:
    """Every preferences save the session sends, with what it sent."""
    sent: list[dict] = []
    real = window.session.client.request

    def spy(method, path, payload, on_success, on_error):  # type: ignore[no-untyped-def]
        if method == "PUT" and path == "/api/preferences":
            sent.append(dict(payload))
        return real(method, path, payload, on_success, on_error)

    window.session.client.request = spy  # type: ignore[method-assign]
    return sent


def signature(layout_id: str) -> str:
    """The first curated look is each design's signature."""
    return DESIGN_LOOKS[layout_id][0][0]


def own_accent(layout_id: str) -> str:
    return signature(layout_id)


# The More menu and the Add menu ---------------------------------------------------------------------


def more_actions(window: NativeWindow) -> dict[str, bool]:
    """The items, without the section headings. addSection makes a separator that carries text.
    Undo, copy and save is a submenu, so its entries are included under their own names."""
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    offered: dict[str, bool] = {}
    for action in menu.actions():
        if action.isSeparator() or not action.text() or not action.isVisible():
            continue
        submenu = action.menu()
        offered[action.text()] = action.isEnabled()
        if submenu is None:
            continue
        for inner in submenu.actions():
            if inner.text() and not inner.isSeparator() and inner.isVisible():
                offered[inner.text()] = inner.isEnabled()
    return offered


def more_sections(window: NativeWindow) -> list[str]:
    """The heading rows. Fusion never drew `addSection` titles, so the menu uses a label row instead."""
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    return [
        action.defaultWidget().text()
        for action in menu.actions()
        if isinstance(action, QWidgetAction) and isinstance(action.defaultWidget(), QLabel)
    ]


def menu_swatches(window: NativeWindow) -> dict:
    """The colour beside each type in the Add menu, read back off its icon."""
    faces = {}
    for key in CATEGORIES:
        action = window.add_menu.findChild(QAction, f"addMenu-{key}")
        assert action is not None, key
        image = action.icon().pixmap(12, 12).toImage()
        faces[key] = image.pixelColor(6, 6).name()
    return faces


# Words on screen -------------------------------------------------------------------------------------


def visible_copy(root: QWidget) -> str:
    bits = []
    for child in [root, *root.findChildren(QWidget)]:
        if not child.isVisible():
            continue
        if isinstance(child, (QLabel, QPushButton)):
            # One label's words, even where the label breaks them over two lines (One thing's ring title).
            text = " ".join(child.text().split())
            if text:
                bits.append(text)
    return "\n".join(bits)


# Sounds and updates the window is given instead of the real ones ------------------------------------


class RingRecorder:
    """Stands in for the window's Bell so the ringing decision is visible without a sound card."""

    def __init__(self) -> None:
        self.started: list[tuple[str, object]] = []
        self.stops = 0
        self.ringing = False

    def start(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        self.ringing = True
        return True

    def once(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        return True

    def stop(self) -> None:
        self.stops += 1
        self.ringing = False


def no_spotify(monkeypatch: pytest.MonkeyPatch, opened: list) -> None:
    """Nothing in a test may hand a URL to the real desktop, which would open a browser."""
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: bool(opened.append(url.toString())) or True),
    )


class FakeUpdater:
    """Stands in for the real one so no test reaches the network."""

    def __init__(self) -> None:
        self.checks = 0
        self.downloads: list[dict] = []
        self.busy = False

    def check(self, *, developer: bool = False) -> None:
        self.checks += 1
        self.developer = developer

    def download(self, update: dict) -> None:
        self.downloads.append(update)


# Homework editor steps ---------------------------------------------------------------------------------


def go_when(dialog) -> None:
    """Add homework's second question. The demo hides Due until What has a title."""
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("History essay")
    dialog._save.click()
    QApplication.processEvents()


def go_length(dialog) -> None:
    """Add homework's third question. Estimated time is not on the first page."""
    go_when(dialog)
    if dialog._add_step is None or dialog._add_step >= 2:
        return
    dialog._save.click()
    QApplication.processEvents()


def monday_of_week(window: NativeWindow) -> datetime:
    return datetime.fromisoformat(window.session.week_start)


def thursday_at(window: NativeWindow, hours: int, minutes: int = 0) -> datetime:
    return monday_of_week(window) + timedelta(days=3, hours=hours, minutes=minutes)


__all__ = [
    "PASSWORD",
    "SPOTIFY_TRACK",
    "FakeUpdater",
    "RingRecorder",
    "add_school_week",
    "at_motion_level",
    "busy_thursday",
    "click",
    "combo",
    "drag_on_the_week",
    "drop_chip",
    "fades",
    "go_length",
    "go_when",
    "hours_of",
    "look_file",
    "menu_swatches",
    "monday_of_week",
    "more_actions",
    "more_sections",
    "no_spotify",
    "one_thing",
    "open_settings",
    "own_accent",
    "preference_puts",
    "prefs_layout",
    "press",
    "qapp",
    "rows",
    "school_week",
    "settled",
    "signature",
    "still",
    "thursday_at",
    "use_layout",
    "visible_copy",
    "wait_until",
    "waiting_math",
    "window",
]
