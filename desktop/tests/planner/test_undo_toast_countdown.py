"""The Undo notice's clock on Material's snackbar: it waits while the pointer, the keyboard or the window's
absence says the student is not ready, shows how long is left, is announced once, and follows the Animations
setting. The Widgets toast showed "Undo · 7 s" and a progress line; where Material does not, the test is a
strict xfail."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.real_surface

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.planner.undo_support import MATERIAL_PLACED, planned_in_material
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _bridge, _pump, _qml, _snack
from desktop.tests.window_support import qapp  # noqa: F401

# Leaving the notice starts its clock again with at least this much left (bridge.resumeSnack).
RESUME_MS = 1_000
SAYS_SECONDS = r"UNDO · (\d+) s"


def _planned_and_let_go(qapp: QApplication, window: NativeWindow):
    """Plan puts the keyboard on the snackbar so Undo is reachable, which holds the clock. The tests of
    the pointer and the window start from the clock running, as it does once the student looks away."""
    root = planned_in_material(qapp, window)
    root.forceActiveFocus()
    wait_until(qapp, lambda: _bridge(window)._snack_timer.isActive(), what="the notice's clock to run")
    return root


def _action_centre(window: NativeWindow, snackbar) -> QPoint:
    """The middle of the UNDO word, where the pointer rests on the button."""
    spot = snackbar.mapToScene(snackbar.boundingRect().center())
    return QPoint(int(spot.x()) + int(snackbar.property("width")) // 2 - 40, int(spot.y()))


def test_the_undo_timer_pauses_while_its_button_has_the_keyboard(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _planned_and_let_go(qapp, window)
    bridge = _bridge(window)
    snackbar = _qml(root, "materialSnackbar")
    snackbar.forceActiveFocus()
    wait_until(qapp, lambda: not bridge._snack_timer.isActive(), what="the clock to wait for the keyboard")
    root.forceActiveFocus()
    wait_until(qapp, lambda: bridge._snack_timer.isActive(), what="the clock to start again")
    assert bridge._snack_timer.interval() >= RESUME_MS


def test_the_undo_timer_pauses_while_the_pointer_is_over_its_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _planned_and_let_go(qapp, window)
    bridge = _bridge(window)
    quick = window._material_page._quick
    snackbar = _qml(root, "materialSnackbar")
    QTest.mouseMove(quick, QPoint(5, 5))
    _pump(qapp)
    assert bridge._snack_timer.isActive()
    QTest.mouseMove(quick, _action_centre(window, snackbar))
    wait_until(qapp, lambda: not bridge._snack_timer.isActive(), what="the clock to wait for the pointer")
    QTest.mouseMove(quick, QPoint(5, 5))
    wait_until(qapp, lambda: bridge._snack_timer.isActive(), what="the clock to start again")
    assert bridge._snack_timer.interval() >= RESUME_MS


def test_the_notice_counts_the_pointer_over_its_card_above_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The pointer on the notice's words, not on its button, over the week grid beneath it."""
    root = _planned_and_let_go(qapp, window)
    bridge = _bridge(window)
    quick = window._material_page._quick
    snackbar = _qml(root, "materialSnackbar")
    spot = snackbar.mapToScene(snackbar.boundingRect().center())
    QTest.mouseMove(quick, QPoint(int(spot.x()) - 60, int(spot.y())))
    wait_until(qapp, lambda: bool(snackbar.property("pointerHovered")), what="the card to count the pointer")
    assert not bridge._snack_timer.isActive()


@pytest.mark.xfail(
    strict=True,
    reason="Material's snackbar clock does not look at the window: it keeps running while the window is hidden,"
    " minimized or not the active one; the Widgets toast held its remaining time",
)
@pytest.mark.parametrize("which", ["hidden", "minimized", "inactive"])
def test_the_notice_holds_its_remaining_time_while_the_window_is_unavailable(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    _planned_and_let_go(qapp, window)
    bridge = _bridge(window)
    if which == "hidden":
        window.hide()
    elif which == "minimized":
        window.showMinimized()
    else:
        monkeypatch.setattr(window, "isActiveWindow", lambda: False)
    _pump(qapp)
    wait_until(qapp, lambda: not bridge._snack_timer.isActive(), timeout=2, what="the clock to hold")


def test_the_notice_is_one_item_for_a_screen_reader(qapp: QApplication, window: NativeWindow) -> None:
    """The snackbar's accessible name is its message and its Undo, and it is one item, so a reader says it
    once."""
    root = planned_in_material(qapp, window)
    snackbar = _qml(root, "materialSnackbar")
    face = QAccessible.queryAccessibleInterface(snackbar)
    assert face is not None
    name = face.text(QAccessible.Text.Name)
    assert name == f"{MATERIAL_PLACED}, UNDO (Ctrl+Z)", name


@pytest.mark.xfail(
    strict=True,
    reason="Material's snackbar does not call announce(); only a sheet notice does. The Widgets toast"
    " announced its message once, politely",
)
def test_the_snackbar_announces_once_and_politely(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[str] = []
    def keep(_widget: object, words: str, *, assertive: bool = False) -> None:
        said.append(words)

    monkeypatch.setattr("desktop.native.fields.announce", keep)
    monkeypatch.setattr("desktop.native.material.bridge_sheets.announce", keep)
    planned_in_material(qapp, window)
    assert said.count(MATERIAL_PLACED) == 1, said


@pytest.mark.xfail(
    strict=True,
    reason="Material's snackbar shows no countdown: its button says UNDO, not UNDO and the seconds left, and it"
    " has no progress line. The Widgets toast counted down and followed the Animations setting",
)
@pytest.mark.parametrize("motion", ["reduce", "off"])
def test_the_undo_countdown_keeps_its_accessible_name_and_decreases(
    qapp: QApplication, window: NativeWindow, motion: str
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "motion": motion}
    window._apply_appearance()
    root = planned_in_material(qapp, window)
    snackbar = _qml(root, "materialSnackbar")
    initial = re.fullmatch(SAYS_SECONDS, str(snackbar.property("actionText")))
    assert initial
    CLOCK.move(seconds=3)
    _pump(qapp)
    remaining = re.fullmatch(SAYS_SECONDS, str(snackbar.property("actionText")))
    assert remaining and int(remaining.group(1)) < int(initial.group(1))
    assert _snack(window) == MATERIAL_PLACED
