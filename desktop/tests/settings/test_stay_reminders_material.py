"""The Material style's reminder card, for a computer with no notification service: the same behaviour as the
plain look's strip. It stays until closed or the block starts, Snooze comes back after five minutes and never
past the start, the start replaces it with the "starts now" notice once, and it never takes the keyboard.

Guitar practice is Thursday 18:45 on the held clock; the default lead is five minutes."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native import widgets
from desktop.native.material import bridge as bridge_module
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.material_support import named, pump, show_material
from desktop.tests.settings.support_reminders import add_practice, at, choose, tick, with_stand_ins
from desktop.tests.settings.support_stay_reminders import NOW, SOON, QuietTray
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def material(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> tuple[NativeWindow, QObject]:
    window = with_stand_ins(open_light(size=(1280, 860)))
    window._tray_icon = QuietTray()
    at(18, 20)
    choose(qapp, window, reminders_enabled=True, reminder_lead_min=5)
    add_practice(qapp, window)
    return window, show_material(qapp, window)


def card(root: QObject) -> QObject:
    found = named(root, "materialReminder")
    assert found, "no reminder card in Material"
    return found[0]


def shown(root: QObject) -> str:
    item = card(root)
    return str(item.property("message")) if item.property("visible") else ""


def beat(qapp: QApplication, window: NativeWindow, minute: int) -> None:
    tick(qapp, window, minute)
    pump(qapp)


def test_the_card_stays_until_the_block_starts_and_the_start_notice_replaces_it(
    qapp: QApplication, material
) -> None:
    window, root = material
    said: list[str] = []
    window.session.alerts.connect(lambda items: said.extend(item["title"] for item in items))
    beat(qapp, window, 40)
    assert shown(root) == SOON
    for minute in (41, 42, 43, 44):
        beat(qapp, window, minute)
        assert shown(root) == SOON, f"gone at 18:{minute}"
    beat(qapp, window, 45)
    assert shown(root) == ""
    assert window.toast.text() == NOW
    beat(qapp, window, 45)
    beat(qapp, window, 46)
    assert shown(root) == ""
    assert said == ["Guitar practice starts soon", "Guitar practice starts now"]


def test_the_card_takes_the_new_name_when_its_block_is_renamed(qapp: QApplication, material) -> None:
    window, root = material
    beat(qapp, window, 40)
    assert shown(root) == SOON
    block = next(item for item in window.session.blocks if item["id"] == "practice")
    window.session.add_block({**block, "title": "Violin practice"})
    beat(qapp, window, 41)
    assert shown(root) == "Violin practice starts soon — 6:45 PM · Thu"


def surfaces(window: NativeWindow, root: QObject) -> list[str]:
    """Which reminder surfaces the student can see: Material's card, the plain look's toast and strip."""
    visible = []
    if shown(root):
        visible.append("card")
    if window.toast.isVisible():
        visible.append("toast")
    if window.alert_strip.isVisible():
        visible.append("strip")
    return visible


def test_only_the_card_shows_the_reminder_through_snooze_and_the_toast_comes_back_for_starts_now(
    qapp: QApplication, material
) -> None:
    window, root = material
    choose(qapp, window, reminder_lead_min=15)
    beat(qapp, window, 30)
    assert surfaces(window, root) == ["card"]
    beat(qapp, window, 31)
    material_bridge = window._material_page.bridge
    material_bridge.snoozeReminder(material_bridge.property("reminderKey"))
    pump(qapp)
    assert surfaces(window, root) == []
    for minute in (32, 33, 34, 35):
        beat(qapp, window, minute)
        assert surfaces(window, root) == [], f"something showed at 18:{minute}"
    beat(qapp, window, 36)
    assert surfaces(window, root) == ["card"]
    beat(qapp, window, 44)
    assert surfaces(window, root) == ["card"]
    beat(qapp, window, 45)
    assert surfaces(window, root) == ["toast"]
    assert window.toast.text() == NOW


def test_a_reminder_with_the_card_hidden_by_settings_still_has_the_toast(
    qapp: QApplication, material
) -> None:
    window, root = material
    window._open_settings_at(0)
    pump(qapp)
    assert window._stack.currentWidget() is window._settings
    beat(qapp, window, 40)
    assert window.toast.isVisible() and window.toast.text() == SOON


def test_snooze_hides_the_card_and_it_comes_back_at_the_start_as_starts_now(
    qapp: QApplication, material
) -> None:
    window, root = material
    beat(qapp, window, 40)
    beat(qapp, window, 41)
    material_bridge = window._material_page.bridge
    material_bridge.snoozeReminder(material_bridge.property("reminderKey"))
    pump(qapp)
    assert shown(root) == ""
    for minute in (42, 43, 44):
        beat(qapp, window, minute)
        assert shown(root) == ""
    beat(qapp, window, 45)
    assert shown(root) == ""
    assert window.toast.text() == NOW


def test_got_it_closes_it_for_good(qapp: QApplication, material) -> None:
    window, root = material
    beat(qapp, window, 40)
    material_bridge = window._material_page.bridge
    material_bridge.closeReminder(material_bridge.property("reminderKey"))
    pump(qapp)
    for minute in range(41, 48):
        beat(qapp, window, minute)
        assert shown(root) == ""


def test_the_two_actions_are_reachable_by_tab_named_for_a_screen_reader_and_press_with_space_and_enter(
    qapp: QApplication, material
) -> None:
    window, root = material
    beat(qapp, window, 40)
    snooze, close = named(root, "reminderSnooze")[0], named(root, "reminderClose")[0]
    for item in (snooze, close):
        assert item.property("activeFocusOnTab") is True
    names = [
        QAccessible.queryAccessibleInterface(item).text(QAccessible.Text.Name) for item in (snooze, close)
    ]
    assert names == ["Snooze this reminder for 5 minutes", "Got it"]
    assert QAccessible.queryAccessibleInterface(card(root)).text(QAccessible.Text.Name) == SOON
    quick = window._material_page._quick
    snooze.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Return)
    pump(qapp)
    assert shown(root) == ""
    beat(qapp, window, 41)
    assert shown(root) == ""


def test_the_card_arriving_does_not_take_the_keyboard(qapp: QApplication, material) -> None:
    window, root = material
    root.forceActiveFocus()
    pump(qapp)
    assert root.property("activeFocus") is True
    beat(qapp, window, 40)
    assert shown(root) == SOON
    assert root.property("activeFocus") is True
    for name in ("reminderSnooze", "reminderClose"):
        assert named(root, name)[0].property("activeFocus") is False


def test_a_screen_reader_is_told_the_reminder_once_politely_and_again_when_a_snooze_ends(
    qapp: QApplication, material, monkeypatch: pytest.MonkeyPatch
) -> None:
    window, root = material
    heard: list[tuple[str, bool]] = []

    def hear(_widget: object, words: str, assertive: bool = False) -> None:
        heard.append((words, assertive))

    # The card reads a new reminder once, and again when it comes back from a snooze.
    monkeypatch.setattr(widgets, "announce", hear)
    monkeypatch.setattr(bridge_module, "announce", hear)
    choose(qapp, window, reminder_lead_min=15)
    beat(qapp, window, 30)
    beat(qapp, window, 31)
    assert heard == [(SOON, False)]
    material_bridge = window._material_page.bridge
    material_bridge.snoozeReminder(material_bridge.property("reminderKey"))
    for minute in (32, 33, 34, 35):
        beat(qapp, window, minute)
    assert heard == [(SOON, False)]
    beat(qapp, window, 36)
    assert shown(root) == SOON
    assert heard == [(SOON, False), (SOON, False)]


def test_tab_walks_from_the_week_page_to_snooze_then_got_it_and_back(qapp: QApplication, material) -> None:
    window, root = material
    beat(qapp, window, 40)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    snooze, close = named(root, "reminderSnooze")[0], named(root, "reminderClose")[0]

    def press(key: Qt.Key) -> object:
        QTest.keyClick(quick, key)
        pump(qapp)
        return scene.activeFocusItem()

    # The card is last in the page's order: the Week's own controls come first, a block's chip is the stop
    # just before it.
    named(root, "toggleWeekends")[0].forceActiveFocus()
    pump(qapp)
    stops = []
    for _ in range(80):
        stops.append(press(Qt.Key.Key_Tab))
        if stops[-1] is snooze:
            break
    assert stops[-1] is snooze, "Tab never reached Snooze from the Week's first control"
    assert str(stops[-2].objectName()) == "weekBlock"
    before = stops[-2]
    assert press(Qt.Key.Key_Tab) is close
    assert press(Qt.Key.Key_Backtab) is snooze
    assert press(Qt.Key.Key_Backtab) is before
    assert press(Qt.Key.Key_Tab) is snooze


@pytest.mark.parametrize("action", ["reminderSnooze", "reminderClose"])
def test_after_snooze_or_got_it_by_keyboard_focus_goes_back_where_it_was_not_to_the_page_start(
    qapp: QApplication, material, action: str
) -> None:
    window, root = material
    beat(qapp, window, 40)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    snooze = named(root, "reminderSnooze")[0]
    pressed = named(root, action)[0]

    def press(key: Qt.Key) -> object:
        QTest.keyClick(quick, key)
        pump(qapp)
        return scene.activeFocusItem()

    named(root, "toggleWeekends")[0].forceActiveFocus()
    pump(qapp)
    stops = []
    for _ in range(80):
        stops.append(press(Qt.Key.Key_Tab))
        if stops[-1] is snooze:
            break
    assert stops[-1] is snooze
    before = stops[-2]
    if action == "reminderClose":
        assert press(Qt.Key.Key_Tab) is pressed
    assert press(Qt.Key.Key_Space) is before
    assert shown(root) == ""
    assert before.property("visible") is True
    after = press(Qt.Key.Key_Tab)
    assert after is not None and after.property("visible") is True
    assert after is not before


def test_a_long_block_name_keeps_the_card_inside_the_narrowest_window(qapp: QApplication, material) -> None:
    window, root = material
    window.resize(800, 800)
    pump(qapp)
    title = "Advanced piano and music theory rehearsal with the big bands"
    assert len(title) == 60
    add_practice(qapp, window, title=title)
    beat(qapp, window, 40)
    item = card(root)
    assert shown(root).startswith(title)
    left = item.mapToScene(QPointF(0, 0)).x()
    assert left >= 0
    assert left + item.width() <= root.width()
    assert QAccessible.queryAccessibleInterface(item).text(QAccessible.Text.Name) == shown(root)
