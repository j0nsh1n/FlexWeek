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


def _day(qapp: QApplication, window: NativeWindow, *, weekends: bool = True) -> object:
    set_clock_24h(True)
    _pref(window, show_weekends=weekends, clock_24h=True)
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
    bridge = _bridge(window)
    bridge.showPage("day")
    _pump(qapp)
    settled(qapp, window)
    _pump(qapp)
    # showPage("day") is a no-op when Day is already showing, and leftover
    # contentY would leak. Previous then Next is a new date each time, so the
    # opening scroll runs the same way Previous/Next does for the student.
    day_bridge = bridge.property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    _pump(qapp)
    day_bridge.nextDay()
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
        _scroll_block_into_view(qapp, _day_item(root), school)
        _click(window, school)
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


def _opening_above(view: float, row: int) -> float:
    """45 minutes above now, unless the pane is shorter than that margin plus one hour."""
    margin = NOW_MARGIN / 60 * row
    if view < margin + row:
        return min(margin, max(8.0, view * 0.08))
    return margin


def _scroll_block_into_view(qapp: QApplication, day: object, block: object) -> None:
    scroller = _qml(day, "dayScroller")
    scroller.setProperty("contentY", max(0.0, float(block.property("y")) - 16.0))
    _pump(qapp)


def test_it_opens_scrolled_so_nineteen_is_near_the_top(qapp: QApplication, window: NativeWindow) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    scroller = _qml(day, "dayScroller")
    row = int(_bridge(window).property("dayHourRow"))
    now_y = 19 * row
    essay_y = 18.75 * row
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    assert view_h > 40
    above = _opening_above(view_h, row)
    assert content_y <= now_y <= content_y + view_h
    assert content_y <= essay_y <= content_y + view_h
    assert abs((now_y - content_y) - above) < 2
    assert int(_bridge(window).property("day").property("openingMinute")) == NOW_MINUTE

    quick = window._material_page._quick
    quick.setFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    _pump(qapp)
    day_bridge = _bridge(window).property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    _pump(qapp)
    day_bridge.nextDay()
    settled(qapp, window)
    _pump(qapp)
    row = int(_bridge(window).property("dayHourRow"))
    assert row == 72
    scroller = _qml(_day_item(root), "dayScroller")
    now_y = 19 * row
    essay_y = 18.75 * row
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    above = _opening_above(view_h, row)
    assert content_y <= now_y <= content_y + view_h
    assert content_y <= essay_y <= content_y + view_h
    assert abs((now_y - content_y) - above) < 2


def test_a_focused_block_keeps_focus_across_an_unchanged_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    essay = _block_named(day, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    assert essay.property("activeFocus") is True
    _bridge(window).refresh()
    _pump(qapp)
    essay = _block_named(_day_item(root), "History essay")
    assert essay.property("activeFocus") is True

    _bridge(window).showPage("week")
    _pump(qapp)
    week = _qml(root, "materialWeek")
    essay = _block_named(week, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    assert essay.property("activeFocus") is True
    _bridge(window).refresh()
    _pump(qapp)
    essay = _block_named(_qml(root, "materialWeek"), "History essay")
    assert essay.property("activeFocus") is True


def test_day_shows_saturday_when_week_hides_weekends(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    saturday = {
        "id": "sat-club",
        "title": "Saturday club",
        "kind": "locked",
        "category": "extra",
        "start": "10:00",
        "duration_min": 60,
        "days": [5],
    }
    try:
        session.add_block(saturday)
        session.save()
        settled(qapp, window)
        root = _day(qapp, window, weekends=False)
        day_bridge = _bridge(window).property("day")
        day_bridge.nextDay()
        settled(qapp, window)
        _pump(qapp)
        day_bridge.nextDay()
        settled(qapp, window)
        _pump(qapp)
        assert int(day_bridge.property("dayIndex")) == 5
        day = _day_item(root)
        assert "Saturday club" in _blocks_by_title(day)
        _bridge(window).showPage("week")
        _pump(qapp)
        assert int(_bridge(window).property("week").property("columns")) == 5
        assert len(_named(root, "dayHeader")) == 5
        week_blocks = _named(_qml(root, "materialWeek"), "weekBlock")
        week_titles = [str(block.property("title")) for block in week_blocks]
        assert "Saturday club" not in week_titles
    finally:
        _pref(window, show_weekends=True)
        if any(block["id"] == "sat-club" for block in session.blocks):
            session.delete_block("sat-club")
            session.save()
            settled(qapp, window)
        session.open_day((date.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)).isoformat())
        settled(qapp, window)


def test_a_clock_tick_does_not_move_day_scroll_or_a_zoom_anchor(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    scroller = _qml(day, "dayScroller")
    row = int(_bridge(window).property("dayHourRow"))
    school_y = 8 * row
    scroller.setProperty("contentY", float(school_y))
    _pump(qapp)
    held = float(scroller.property("contentY"))
    assert abs(held - school_y) < 2
    real_now = window.session.now_ms
    later = datetime.fromisoformat(window.session.week_start) + timedelta(days=NOW_DAY, hours=19, minutes=1)
    try:
        window.session.now_ms = lambda: int(later.timestamp() * 1000)
        _bridge(window).refresh()
        _pump(qapp)
        assert abs(float(scroller.property("contentY")) - held) < 2

        view_y = float(scroller.property("height")) / 2
        minute = ((float(scroller.property("contentY")) + view_y) / row) * 60
        quick = window._material_page._quick
        quick.setFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
        _pump(qapp)
        row = int(_bridge(window).property("dayHourRow"))
        assert row == 72
        after_zoom = ((float(scroller.property("contentY")) + view_y) / row) * 60
        assert abs(after_zoom - minute) < 1
        _bridge(window).refresh()
        _pump(qapp)
        after_tick = ((float(scroller.property("contentY")) + view_y) / row) * 60
        assert abs(after_tick - minute) < 1
    finally:
        window.session.now_ms = real_now
        _bridge(window).refresh()
        _pump(qapp)


def test_every_day_block_opens_from_a_click_tab_and_enter_and_space_toggles_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    sheets = _bridge(window).property("sheets")
    quick = window._material_page._quick
    blocks = _blocks_by_title(day)
    school = blocks["School"]
    soccer = blocks["Soccer"]
    essay = blocks["History essay"]
    assert school.property("activeFocusOnTab") is True
    assert soccer.property("activeFocusOnTab") is True
    assert essay.property("activeFocusOnTab") is True

    _scroll_block_into_view(qapp, day, soccer)
    _click(window, soccer)
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets._block is not None
    assert sheets._block.original["id"] == "soccer"
    sheets.forceClose()
    _pump(qapp)

    school.forceActiveFocus()
    _pump(qapp)
    assert school.property("activeFocus") is True
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    _pump(qapp)
    soccer = _blocks_by_title(_day_item(root))["Soccer"]
    assert soccer.property("activeFocus") is True
    QTest.keyClick(quick, Qt.Key.Key_Return)
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets._block is not None
    assert sheets._block.original["id"] == "soccer"
    sheets.forceClose()
    _pump(qapp)

    essay = _blocks_by_title(_day_item(root))["History essay"]
    essay.forceActiveFocus()
    _pump(qapp)
    assert essay.property("activeFocus") is True
    assert window.session.assignments["essay"].get("completed") in (None, False)
    QTest.keyClick(quick, Qt.Key.Key_Space)
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed")),
    )
    assert sheets.kind == ""
    window.session.complete_homework("essay", False)
    window.session.save()
    settled(qapp, window)


def test_day_blocks_leave_a_sixteen_pixel_gutter_for_the_now_line(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _day(qapp, window)
    day = _day_item(root)
    scroller = _qml(day, "dayScroller")
    essay = _blocks_by_title(day)["History essay"]
    pane_right = int(scroller.property("width"))
    block_right = int(essay.property("x")) + int(essay.property("width"))
    assert pane_right - block_right == 16
    line = _qml(day, "nowLine")
    line_right = int(line.property("x")) + int(line.property("width"))
    assert line_right > block_right


def _no_blank_past_midnight(scroller: object, row: int) -> None:
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    if 24 * row >= view_h:
        assert content_y + view_h <= 24 * row + 1, (content_y, view_h, row)


def test_an_evening_zoom_keeps_the_essay_and_no_blank_past_midnight(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Day opens with the evening near the top and room past midnight; zooming from there anchors a
    time in the day and never leaves midnight above the bottom while earlier time could show."""
    root = _day(qapp, window)
    quick = window._material_page._quick
    quick.setFocus()
    _pump(qapp)
    try:
        for expected, key in ((72, Qt.Key.Key_Equal), (96, Qt.Key.Key_Equal), (56, Qt.Key.Key_0)):
            QTest.keyClick(quick, key, Qt.KeyboardModifier.ControlModifier)
            _pump(qapp)
            row = int(_bridge(window).property("dayHourRow"))
            assert row == expected
            scroller = _qml(_day_item(root), "dayScroller")
            _no_blank_past_midnight(scroller, row)
            content_y = float(scroller.property("contentY"))
            view_h = float(scroller.property("height"))
            assert content_y <= 18.75 * row and 19.75 * row <= content_y + view_h, (
                expected,
                content_y,
                view_h,
            )
    finally:
        _forget_zoom(window)


def test_opening_a_date_in_the_next_week_waits_for_that_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Next past Sunday loads the next week; Day opens at that Monday's first block once it lands,
    not at the fallback hour it had while the week was loading."""
    session = window.session
    home = window.home_week
    following = (date.fromisoformat(home) + timedelta(days=7)).isoformat()
    art = {
        "id": "mon-art",
        "title": "Art club",
        "kind": "locked",
        "category": "extra",
        "start": "14:00",
        "duration_min": 60,
        "days": [0],
    }
    session.load_week(following)
    settled(qapp, window)
    session.add_block(art)
    session.save()
    settled(qapp, window)
    try:
        root = _day(qapp, window)
        day_bridge = _bridge(window).property("day")
        for _ in range(4):
            day_bridge.nextDay()
            settled(qapp, window)
            _pump(qapp)
        wait_until(qapp, lambda: session.week_start == following)
        settled(qapp, window)
        _pump(qapp)
        assert int(day_bridge.property("dayIndex")) == 0
        assert int(day_bridge.property("openingMinute")) == 14 * 60
        scroller = _qml(_day_item(root), "dayScroller")
        row = int(_bridge(window).property("dayHourRow"))
        view_h = float(scroller.property("height"))
        wait_until(
            qapp,
            lambda: abs(14 * row - float(scroller.property("contentY")) - _opening_above(view_h, row)) < 2,
        )
    finally:
        if session.week_start != following:
            session.load_week(following)
            settled(qapp, window)
        if any(block["id"] == "mon-art" for block in session.blocks):
            session.delete_block("mon-art")
            session.save()
            settled(qapp, window)
        session.load_week(home)
        settled(qapp, window)
