"""Material Week hour zoom: remembered levels, keys, wheel, and the - + pill.

Expected values come from the J21 brief (levels 32-128, density until a level is remembered; round 2 adds
192 and 256) and from the account's own blocks, not from reading what the QML prints. Every test zooms
and some leave a remembered level behind, so each one gets a fresh light window with School on weekday
mornings and the History essay planned for 18:45 on Thursday (the clock starts on Thursday evening)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.zoom import sanitize_zoom  # noqa: E402
from desktop.native.material.theme import advanced_default, hour_row_px  # noqa: E402
from desktop.native.weekmodel import set_clock_24h  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests import light_app  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import (  # noqa: E402
    add_homework,
    block_named,
    bridge_of,
    click_item,
    named,
    pump,
    qml,
    show_material,
    wheel,
)
from desktop.tests.window_support import look_file  # noqa: E402

qapp = support_zoom.qapp  # fixtures are found by their name in the test module
open_light = light_app.open_light

WIDTH = 1280


@pytest.fixture()
def material(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:
    """A fresh light window with School Monday to Friday and the History essay planned for 18:45 on
    Thursday, on the Material week with weekends shown and the 24-hour clock, and no zoom remembered."""
    made = open_light((WIDTH, 800))
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
            "due": (date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat(),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    set_clock_24h(True)
    session.preferences = {**(session.preferences or {}), "show_weekends": True, "clock_24h": True}
    yield made
    look_file().unlink(missing_ok=True)


def week_on_screen(qapp: QApplication, window: NativeWindow):
    """Material on the week with no zoom remembered; returns the QML root."""
    root = show_material(qapp, window)
    window._zoom.pop("material.week", None)
    window._material_page.publish()
    pump(qapp)
    return root


def row_of(window: NativeWindow) -> int:
    return int(bridge_of(window).property("hourRow"))


def test_hour_row_follows_density_until_zoom_and_reset_forgets_it(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    week_on_screen(qapp, window)
    comfortable = hour_row_px("comfortable", advanced_default())
    compact = hour_row_px("compact", advanced_default())
    assert comfortable == 56 and compact == 44
    assert row_of(window) == comfortable
    bridge = bridge_of(window)
    assert bridge.property("canZoomIn") is True
    assert bridge.property("canZoomOut") is True

    bridge.zoomBy(1)
    pump(qapp)
    assert row_of(window) == 72
    assert window._zoom["material.week"] == 72

    for _ in range(8):
        bridge.zoomBy(1)
    pump(qapp)
    assert row_of(window) == 256
    assert bridge.property("canZoomIn") is False
    assert bridge.property("canZoomOut") is True
    bridge.zoomBy(1)
    assert row_of(window) == 256

    for _ in range(12):
        bridge.zoomBy(-1)
    pump(qapp)
    assert row_of(window) == 32
    assert bridge.property("canZoomIn") is True
    assert bridge.property("canZoomOut") is False
    bridge.zoomBy(-1)
    assert row_of(window) == 32

    bridge.zoomReset()
    pump(qapp)
    assert row_of(window) == comfortable
    assert "material.week" not in window._zoom

    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**stored, "material": {**stored.get("material", {}), "density": "compact"}}))
    window._zoom.pop("material.week", None)
    window._material_page.publish()
    pump(qapp)
    assert row_of(window) == compact


def test_a_remembered_level_is_saved_and_kept_when_the_look_is_reread(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    week_on_screen(qapp, window)
    bridge_of(window).zoomBy(1)
    pump(qapp)
    assert window._zoom["material.week"] == 72
    stored = json.loads(look_file().read_text())
    assert sanitize_zoom(stored.get("zoom"))["material.week"] == 72
    window._zoom = sanitize_zoom(stored.get("zoom"))
    window._material_page.publish()
    pump(qapp)
    assert row_of(window) == 72


def test_ctrl_equal_zooms_the_week_and_ctrl_zero_resets_and_month_ignores_them(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    week_on_screen(qapp, window)
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    assert row_of(window) == 56
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 56
    assert "material.week" not in window._zoom

    # Month leaves a remembered Week level alone: neither zooms nor resets it.
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72 and window._zoom.get("material.week") == 72
    bridge_of(window).showPage("month")
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72 and window._zoom.get("material.week") == 72


def test_ctrl_wheel_over_the_grid_zooms_about_the_pointer_and_plain_wheel_does_not(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    root = week_on_screen(qapp, window)
    scroller = qml(root, "weekScroller")
    row = row_of(window)
    scroller.setProperty("contentY", float(10 * row - 80))
    pump(qapp)
    view_y = 120.0
    before = (float(scroller.property("contentY")) + view_y) / row * 60
    at = scroller.mapToScene(QPointF(68.0 + 40.0, view_y))
    quick = window._material_page._quick
    wheel(quick, at, 1)
    pump(qapp)
    assert row_of(window) == 72
    after = (float(scroller.property("contentY")) + view_y) / row_of(window) * 60
    assert abs(after - before) <= 15

    held = row_of(window)
    wheel(quick, at, -1, ctrl=False)
    pump(qapp)
    assert row_of(window) == held


def test_the_pill_plus_zooms_in_and_minus_is_disabled_at_the_smallest_level(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    root = week_on_screen(qapp, window)
    plus = qml(root, "weekZoomIn")
    minus = qml(root, "weekZoomOut")
    assert plus.property("accessName") == "Zoom in"
    assert minus.property("accessName") == "Zoom out"
    assert plus.property("enabled") is True
    click_item(window, plus)
    assert row_of(window) == 72
    bridge = bridge_of(window)
    for _ in range(10):
        bridge.zoomBy(-1)
    pump(qapp)
    assert row_of(window) == 32
    assert qml(root, "weekZoomOut").property("enabled") is False
    assert qml(root, "weekZoomIn").property("enabled") is True


def zoom_keys_change_nothing(qapp: QApplication, window: NativeWindow, quick) -> None:
    """Each zoom chord in turn, checked after each one, so a zoom in and a zoom out cannot cancel."""
    before = (row_of(window), window._zoom.get("material.week"))
    for key in (Qt.Key.Key_Equal, Qt.Key.Key_Plus, Qt.Key.Key_Minus, Qt.Key.Key_0):
        QTest.keyClick(quick, key, Qt.KeyboardModifier.ControlModifier)
        pump(qapp)
        assert (row_of(window), window._zoom.get("material.week")) == before, key


def test_zoom_keys_wait_while_a_block_menu_is_open(qapp: QApplication, material: NativeWindow) -> None:
    window = material
    root = week_on_screen(qapp, window)
    quick = window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72
    block = block_named(root, "History essay")
    block.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    zoom_keys_change_nothing(qapp, window, quick)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    QTest.keyClick(quick, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 56


def test_zoom_keys_wait_while_a_homework_card_menu_is_open(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    root = week_on_screen(qapp, window)
    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    add_homework(window, "lab", "Lab notes", 30, due)
    pump(qapp)
    quick = window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert row_of(window) == 72
    card = named(root, "homeworkCard")[0]
    card.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    pump(qapp)
    menu = named(root, "cardMenu")[0]
    assert menu.property("open") is True
    zoom_keys_change_nothing(qapp, window, quick)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False


def test_the_buttons_step_through_the_two_closer_levels_and_stop_at_256(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    week_on_screen(qapp, window)
    bridge = bridge_of(window)
    seen = [row_of(window)]
    for _ in range(5):
        bridge.zoomBy(1)
        pump(qapp)
        seen.append(row_of(window))
    assert seen == [56, 72, 96, 128, 192, 256]
    assert bridge.property("canZoomIn") is False
    bridge.zoomBy(1)
    assert row_of(window) == 256
    for _ in range(12):
        bridge.zoomBy(-1)
    pump(qapp)
    assert row_of(window) == 32
    assert bridge.property("canZoomOut") is False


def test_ctrl_equal_and_ctrl_minus_stop_at_the_new_closest_level_and_at_32(
    qapp: QApplication, material: NativeWindow
) -> None:
    window = material
    week_on_screen(qapp, window)
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    for _ in range(9):
        QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
        pump(qapp)
    assert row_of(window) == 256
    for _ in range(12):
        QTest.keyClick(quick, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        pump(qapp)
    assert row_of(window) == 32


@pytest.mark.parametrize("old", [32, 44, 56, 72, 96, 128])
def test_a_level_remembered_before_the_closer_ones_keeps_its_size(
    qapp: QApplication, material: NativeWindow, old: int
) -> None:
    window = material
    week_on_screen(qapp, window)
    window._zoom = sanitize_zoom({"material.week": old})
    window._material_page.publish()
    pump(qapp)
    assert row_of(window) == old


def test_a_block_and_the_now_line_keep_their_times_at_the_closest_level(
    qapp: QApplication, material: NativeWindow
) -> None:
    """The History essay runs 18:45 to 19:45 and the clock reads 19:00: the line sits a quarter of an hour
    below the block's top, and the block is an hour tall."""
    window = material
    root = week_on_screen(qapp, window)
    bridge = bridge_of(window)
    for _ in range(6):
        bridge.zoomBy(1)
    pump(qapp)
    assert row_of(window) == 256
    essay = block_named(root, "History essay")
    line = named(root, "nowLine")[0]
    row = row_of(window)
    assert round((float(line.property("y")) - float(essay.property("y"))) / row * 60) == 15
    assert round((float(essay.property("height")) + 2) / row * 60) == 60
