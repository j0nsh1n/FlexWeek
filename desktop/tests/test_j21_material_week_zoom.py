"""Material Week hour zoom: remembered levels, keys, wheel, and the − + pill.

Expected values come from the J21 brief (levels 32–128, density until a level is
remembered) and from the account's own blocks, not from reading what the QML prints.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QStandardPaths, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.hours.zoom import sanitize_zoom  # noqa: E402
from desktop.native.material.theme import advanced_default, hour_row_px  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import PASSWORD, look_file, settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    _block_named,
    _bridge,
    _click,
    _homework,
    _look,
    _named,
    _qml,
    _reset,
)
from desktop.tests.test_material_window import _pump  # noqa: E402

WIDTH = 1280


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-week-zoom"])
    yield application


@pytest.fixture(scope="module")
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeWindow]:
    """Signed in, clock held at Thursday 19:00, School on weekday mornings and a History essay."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path_factory.mktemp("material-week-zoom") / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    made.resize(WIDTH, 800)
    try:
        made.username.setText("material_week_zoom")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        made.home_week = session.week_start
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
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
                "due": (date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat(),
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
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()
        look_file().unlink(missing_ok=True)


def _forget_week_zoom(window: NativeWindow) -> None:
    window._zoom.pop("material.week", None)


def _week(qapp: QApplication, window: NativeWindow) -> object:
    root = _reset(window, qapp)
    _forget_week_zoom(window)
    window._material_page.publish()
    _pump(qapp)
    return root


def _row(window: NativeWindow) -> int:
    return int(_bridge(window).property("hourRow"))


def _wheel(quick: object, at: QPointF, notches: float, ctrl: bool = True) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event = QWheelEvent(
        at,
        QPointF(quick.mapToGlobal(at.toPoint())),
        QPoint(),
        QPoint(0, round(120 * notches)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(quick, event)


def test_hour_row_follows_density_until_zoom_and_reset_forgets_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _week(qapp, window)
    comfortable = hour_row_px("comfortable", advanced_default())
    compact = hour_row_px("compact", advanced_default())
    assert comfortable == 56 and compact == 44
    assert _row(window) == comfortable
    bridge = _bridge(window)
    assert bridge.property("canZoomIn") is True
    assert bridge.property("canZoomOut") is True

    bridge.zoomBy(1)
    _pump(qapp)
    assert _row(window) == 72
    assert window._zoom["material.week"] == 72

    for _ in range(8):
        bridge.zoomBy(1)
    _pump(qapp)
    assert _row(window) == 128
    assert bridge.property("canZoomIn") is False
    assert bridge.property("canZoomOut") is True
    bridge.zoomBy(1)
    assert _row(window) == 128

    for _ in range(12):
        bridge.zoomBy(-1)
    _pump(qapp)
    assert _row(window) == 32
    assert bridge.property("canZoomIn") is True
    assert bridge.property("canZoomOut") is False
    bridge.zoomBy(-1)
    assert _row(window) == 32

    bridge.zoomReset()
    _pump(qapp)
    assert _row(window) == comfortable
    assert "material.week" not in window._zoom

    _look(window, density="compact")
    _forget_week_zoom(window)
    window._material_page.publish()
    _pump(qapp)
    assert _row(window) == compact
    assert root is not None


def test_a_remembered_level_is_saved_and_kept_when_the_look_is_reread(
    qapp: QApplication, window: NativeWindow
) -> None:
    _week(qapp, window)
    bridge = _bridge(window)
    bridge.zoomBy(1)
    _pump(qapp)
    assert window._zoom["material.week"] == 72
    stored = json.loads(look_file().read_text())
    assert sanitize_zoom(stored.get("zoom"))["material.week"] == 72
    window._zoom = sanitize_zoom(stored.get("zoom"))
    window._material_page.publish()
    _pump(qapp)
    assert _row(window) == 72


def test_ctrl_equal_zooms_the_week_and_ctrl_zero_resets_and_month_ignores_them(
    qapp: QApplication, window: NativeWindow
) -> None:
    _week(qapp, window)
    quick = window._material_page._quick
    quick.setFocus()
    _pump(qapp)
    assert _row(window) == 56
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 56
    assert "material.week" not in window._zoom

    # Month leaves a remembered Week level alone: neither zooms nor resets it.
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72 and window._zoom.get("material.week") == 72
    _bridge(window).showPage("month")
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72 and window._zoom.get("material.week") == 72
    _bridge(window).showPage("week")
    _pump(qapp)
    _forget_week_zoom(window)


def test_ctrl_wheel_over_the_grid_zooms_about_the_pointer_and_plain_wheel_does_not(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _week(qapp, window)
    scroller = _qml(root, "weekScroller")
    row = _row(window)
    scroller.setProperty("contentY", float(10 * row - 80))
    _pump(qapp)
    view_y = 120.0
    before = (float(scroller.property("contentY")) + view_y) / row * 60
    at = scroller.mapToScene(QPointF(68.0 + 40.0, view_y))
    quick = window._material_page._quick
    _wheel(quick, at, 1)
    _pump(qapp)
    assert _row(window) == 72
    after_row = _row(window)
    after = (float(scroller.property("contentY")) + view_y) / after_row * 60
    assert abs(after - before) <= 15

    held = _row(window)
    _wheel(quick, at, -1, ctrl=False)
    _pump(qapp)
    assert _row(window) == held


def test_the_pill_plus_zooms_in_and_minus_is_disabled_at_the_smallest_level(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _week(qapp, window)
    plus = _qml(root, "weekZoomIn")
    minus = _qml(root, "weekZoomOut")
    assert plus.property("accessName") == "Zoom in"
    assert minus.property("accessName") == "Zoom out"
    assert plus.property("enabled") is True
    _click(window, plus)
    assert _row(window) == 72
    bridge = _bridge(window)
    for _ in range(10):
        bridge.zoomBy(-1)
    _pump(qapp)
    assert _row(window) == 32
    minus = _qml(root, "weekZoomOut")
    assert minus.property("enabled") is False
    plus = _qml(root, "weekZoomIn")
    assert plus.property("enabled") is True


def test_a_block_at_ten_sits_at_ten_times_the_hour_row_at_two_levels(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _week(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "clinic",
            "title": "Clinic",
            "kind": "locked",
            "category": "activity",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    session.save()
    window._material_page.publish()
    _pump(qapp)
    block = _block_named(root, "Clinic")
    assert int(block.property("y")) == 10 * 56
    _bridge(window).zoomBy(1)
    _pump(qapp)
    block = _block_named(root, "Clinic")
    assert int(block.property("y")) == 10 * 72
    assert _named(root, "weekBlock")


def _zoom_keys_change_nothing(qapp: QApplication, window: NativeWindow, quick: object) -> None:
    """Each zoom chord in turn, checked after each one, so a zoom in and a zoom out cannot cancel."""
    before = (_row(window), window._zoom.get("material.week"))
    for key in (Qt.Key.Key_Equal, Qt.Key.Key_Plus, Qt.Key.Key_Minus, Qt.Key.Key_0):
        QTest.keyClick(quick, key, Qt.KeyboardModifier.ControlModifier)
        _pump(qapp)
        assert (_row(window), window._zoom.get("material.week")) == before, key


def test_zoom_keys_wait_while_a_block_menu_is_open(qapp: QApplication, window: NativeWindow) -> None:
    root = _week(qapp, window)
    quick = window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72
    block = _block_named(root, "History essay")
    block.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    _zoom_keys_change_nothing(qapp, window, quick)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 56
    _forget_week_zoom(window)


def test_zoom_keys_wait_while_a_homework_card_menu_is_open(qapp: QApplication, window: NativeWindow) -> None:
    root = _week(qapp, window)
    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    _homework(window, "lab", "Lab notes", 30, due)
    _pump(qapp)
    quick = window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert _row(window) == 72
    try:
        card = _named(root, "homeworkCard")[0]
        card.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
        _pump(qapp)
        menu = _named(root, "cardMenu")[0]
        assert menu.property("open") is True
        _zoom_keys_change_nothing(qapp, window, quick)
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert menu.property("open") is False
    finally:
        window.session.delete_homework("lab")
        window.session.save()
        settled(qapp, window)
        _forget_week_zoom(window)
