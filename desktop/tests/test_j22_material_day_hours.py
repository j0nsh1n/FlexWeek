"""Material Day as one hour column: blocks, now line, zoom, and opening scroll.

Expected values come from the J22 brief (hour y = start/60 * dayHourRow, now at
19:00, zoom key material.day, opening_minute) and from the account's own
blocks, not from reading what the QML prints.
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

from desktop.native.hours.zoom import NOW_MARGIN, sanitize_zoom  # noqa: E402
from desktop.native.material.theme import advanced_default, hour_row_px  # noqa: E402
from desktop.native.weekmodel import set_clock_24h  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import PASSWORD, look_file, settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import _click, _look, _named, _pref, _qml  # noqa: E402
from desktop.tests.test_material_window import _pump, _show_material, _visuals  # noqa: E402

WIDTH = 1280
NOW_DAY = 3
NOW_MINUTE = 19 * 60


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-day-hours"])
    yield application


@pytest.fixture(scope="module")
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeWindow]:
    """Signed in, clock held at Thursday 19:00, School, Soccer, and a pinned History essay."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path_factory.mktemp("material-day-hours") / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    made.resize(WIDTH, 800)
    try:
        made.username.setText("material_day_hours")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        made.home_week = session.week_start
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY, hours=19)
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
        session.add_block(
            {
                "id": "soccer",
                "title": "Soccer",
                "kind": "locked",
                "category": "exercise",
                "start": "16:00",
                "duration_min": 90,
                "days": [NOW_DAY],
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
        work.update({"start": "18:45", "days": [NOW_DAY], "duration_min": 60})
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


def _forget_zoom(window: NativeWindow) -> None:
    window._zoom.pop("material.week", None)
    window._zoom.pop("material.day", None)


def _bridge(window: NativeWindow) -> object:
    return window._material_page.bridge


def _day(qapp: QApplication, window: NativeWindow) -> object:
    set_clock_24h(True)
    _pref(window, show_weekends=True, clock_24h=True)
    session = window.session
    if session.week_start != window.home_week:
        session.load_week(window.home_week)
        settled(qapp, window)
    thursday = (date.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)).isoformat()
    if session.selected_day != thursday:
        session.open_day(thursday)
        settled(qapp, window)
    _forget_zoom(window)
    essay = session.assignments.get("essay")
    if essay is not None and essay.get("completed"):
        session.complete_homework("essay", False)
        session.save()
        settled(qapp, window)
    look_file().unlink(missing_ok=True)
    root = _show_material(qapp, window)
    sheets = getattr(window._material_page.bridge, "sheets", None)
    if sheets is not None:
        sheets.forceClose()
    window._material_page.publish()
    _pump(qapp)
    _bridge(window).showPage("day")
    _pump(qapp)
    settled(qapp, window)
    _pump(qapp)
    return root


def _day_item(root: object) -> object:
    return _qml(root, "materialDay")


def _block_named(node: object, title: str) -> object:
    for block in _named(node, "weekBlock"):
        if str(block.property("title")) == title:
            return block
        if any(str(label.property("text")) == title for label in _named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def _blocks_by_title(node: object) -> dict[str, object]:
    found: dict[str, object] = {}
    for block in _named(node, "weekBlock"):
        title = str(block.property("title") or "")
        if not title:
            titles = [str(label.property("text")) for label in _named(block, "title")]
            title = titles[0] if titles else ""
        if title:
            found[title] = block
    return found


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


def test_day_shows_the_three_blocks_at_their_hour_rows_and_hides_the_lists(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    bridge = _bridge(window)
    row = int(bridge.property("dayHourRow"))
    assert row == hour_row_px("comfortable", advanced_default()) == 56
    assert int(bridge.property("hourRow")) == 56
    assert int(bridge.property("day").property("dayIndex")) == NOW_DAY

    blocks = _blocks_by_title(day)
    assert set(blocks) == {"School", "Soccer", "History essay"}
    assert int(blocks["School"].property("y")) == 8 * row
    assert int(blocks["Soccer"].property("y")) == 16 * row
    assert int(blocks["History essay"].property("y")) == int(18.75 * row)
    assert blocks["School"].property("past") is True
    assert blocks["Soccer"].property("past") is True
    assert blocks["History essay"].property("past") is False
    assert blocks["History essay"].property("homework") is True

    names = {str(item.objectName()) for item in _visuals(day)}
    assert "dayUpNext" not in names
    assert "dayDone" not in names
    assert "dayFinish" not in names
    assert "dayLeftLine" in names
    assert "dayPrevious" in names
    assert "dayNow" in names

    bridge.showPage("myday")
    _pump(qapp)
    myday = _qml(root, "materialMyDay")
    my_names = {str(item.objectName()) for item in _visuals(myday)}
    assert "myDayUpNext" in my_names
    assert "myDayDone" in my_names
    bridge.showPage("day")
    _pump(qapp)


def test_the_now_line_is_on_today_at_nineteen_and_absent_on_another_day_and_sits_behind_blocks(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    row = int(_bridge(window).property("dayHourRow"))
    line = _qml(day, "nowLine")
    dot = _qml(day, "nowDot")
    assert line.property("visible") is True
    assert int(line.property("y")) == 19 * row
    assert int(_bridge(window).property("nowMinute")) == NOW_MINUTE
    line_z = float(line.property("z"))
    dot_z = float(dot.property("z"))
    blocks = _named(day, "weekBlock")
    assert blocks
    for block in blocks:
        block_z = float(block.property("z"))
        assert line_z < block_z
        assert dot_z > block_z

    _bridge(window).property("day").nextDay()
    settled(qapp, window)
    _pump(qapp)
    day = _day_item(root)
    line = _qml(day, "nowLine")
    assert line.property("visible") is False
    _bridge(window).property("day").previousDay()
    settled(qapp, window)
    _pump(qapp)


def test_the_previous_day_shows_that_days_blocks_and_a_date_outside_the_week_is_empty(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day_bridge = _bridge(window).property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    _pump(qapp)
    assert int(day_bridge.property("dayIndex")) == NOW_DAY - 1
    day = _day_item(root)
    blocks = _blocks_by_title(day)
    assert set(blocks) == {"School"}
    row = int(_bridge(window).property("dayHourRow"))
    assert int(blocks["School"].property("y")) == 8 * row

    session = window.session
    outside = (date.fromisoformat(session.week_start) + timedelta(days=14)).isoformat()
    session.selected_day = outside
    day_bridge.reload(str(day_bridge._mode))
    window._material_page.publish()
    _pump(qapp)
    assert int(day_bridge.property("dayIndex")) == -1
    day = _day_item(root)
    assert _named(day, "weekBlock") == []
    session.open_day((date.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)).isoformat())
    settled(qapp, window)
    _pump(qapp)


def test_zoom_on_day_changes_day_hour_row_and_leaves_week_untouched(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    bridge = _bridge(window)
    quick = window._material_page._quick
    quick.setFocus()
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 56
    assert int(bridge.property("hourRow")) == 56
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 72
    assert int(bridge.property("hourRow")) == 56
    assert window._zoom["material.day"] == 72
    assert "material.week" not in window._zoom
    stored = json.loads(look_file().read_text())
    assert sanitize_zoom(stored.get("zoom"))["material.day"] == 72

    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 56
    assert "material.day" not in window._zoom

    plus = _qml(_day_item(root), "weekZoomIn")
    assert plus.property("accessName") == "Zoom in"
    _click(window, plus)
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 72
    assert int(bridge.property("hourRow")) == 56

    scroller = _qml(_day_item(root), "dayScroller")
    view_y = 120.0
    at = scroller.mapToScene(QPointF(68.0 + 40.0, view_y))
    held_week = int(bridge.property("hourRow"))
    _wheel(quick, at, 1)
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 96
    assert int(bridge.property("hourRow")) == held_week
    _wheel(quick, at, -1, ctrl=False)
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 96

    _look(window, density="compact")
    _forget_zoom(window)
    window._material_page.publish()
    _pump(qapp)
    assert int(bridge.property("dayHourRow")) == 44
    assert int(bridge.property("hourRow")) == 44


def test_toggling_the_essay_and_opening_school_use_the_week_bridge_calls(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    session = window.session
    sheets = _bridge(window).property("sheets")
    toggled: list[tuple[str, bool]] = []
    real_complete = session.complete_homework

    def spy_complete(assignment_id: str, completed: bool = True) -> None:
        toggled.append((assignment_id, completed))
        real_complete(assignment_id, completed)

    session.complete_homework = spy_complete
    try:
        essay = _block_named(day, "History essay")
        finish = _named(essay, "weekBlockFinish")[0]
        _click(window, finish)
        wait_until(
            qapp,
            lambda: not session.busy and bool(session.assignments["essay"].get("completed")),
        )
        assert toggled == [("essay", True)]
        assert session.assignments["essay"].get("completed") is True

        school = _block_named(_day_item(root), "School")
        school.opened.emit()
        wait_until(qapp, lambda: sheets.kind == "block")
        draft = sheets._block
        assert draft is not None
        assert draft.original["id"] == "school"
        assert draft.occurrence_day == NOW_DAY
        sheets.forceClose()
        _pump(qapp)
    finally:
        session.complete_homework = real_complete
        if session.assignments["essay"].get("completed"):
            session.complete_homework("essay", False)
            session.save()
            settled(qapp, window)


def test_it_opens_scrolled_so_nineteen_is_near_the_top(qapp: QApplication, window: NativeWindow) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    scroller = _qml(day, "dayScroller")
    row = int(_bridge(window).property("dayHourRow"))
    now_y = 19 * row
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    assert view_h > 40
    assert content_y <= now_y <= content_y + view_h
    assert now_y - content_y <= NOW_MARGIN / 60 * row + row
    assert int(_bridge(window).property("day").property("openingMinute")) == NOW_MINUTE
