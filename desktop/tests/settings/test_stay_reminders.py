"""A reminder that stays in FlexWeek when the computer shows no system notifications: it stays until the
student closes it or the block starts, Snooze brings it back after five minutes but never past the start,
and at the start it is replaced by the ordinary "starts now" notice, once. With a notification service the
reminder behaves as it always has.

Guitar practice is Thursday 18:45 on the held clock; the default lead is five minutes, so it is due from
18:40 (lead 15: from 18:30)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from desktop.native import widgets
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.settings.support_reminders import add_practice, at, choose, tick, with_stand_ins
from desktop.tests.settings.support_stay_reminders import NOW, SOON, QuietTray
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def no_service(open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """A new account past setup on a computer with no notification service."""
    window = with_stand_ins(open_light(size=(1280, 860)))
    window._tray_icon = QuietTray()
    return window


def notices_of(window: NativeWindow) -> list[str]:
    said: list[str] = []
    window.session.alerts.connect(lambda items: said.extend(item["title"] for item in items))
    return said


def shown(window: NativeWindow) -> str:
    strip = window.alert_strip
    return strip.text.text() if strip.isVisible() else ""


def ready(qapp: QApplication, window: NativeWindow, lead: int = 5) -> None:
    at(18, 20)
    choose(qapp, window, reminders_enabled=True, reminder_lead_min=lead)
    add_practice(qapp, window)


def test_the_reminder_stays_on_screen_until_the_block_starts_and_the_start_notice_replaces_it(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    said = notices_of(window)
    ready(qapp, window)
    tick(qapp, window, 40)
    assert shown(window) == SOON
    for minute in (41, 42, 43, 44):
        tick(qapp, window, minute)
        assert shown(window) == SOON, f"gone at 18:{minute}"
    tick(qapp, window, 45)
    assert shown(window) == ""
    assert window.toast.text() == NOW
    tick(qapp, window, 45)
    tick(qapp, window, 46)
    assert shown(window) == ""
    assert said == ["Guitar practice starts soon", "Guitar practice starts now"]


def test_the_plain_look_alone_shows_both_its_strip_and_its_toast(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    assert shown(window) == SOON
    assert window.toast.isVisible() and window.toast.text() == SOON


def test_snooze_hides_it_and_it_comes_back_at_the_start_as_starts_now_not_a_minute_later(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    said = notices_of(window)
    ready(qapp, window)
    tick(qapp, window, 40)
    tick(qapp, window, 41)
    window.alert_strip.snooze.click()
    assert shown(window) == ""
    for minute in (42, 43, 44):
        tick(qapp, window, minute)
        assert shown(window) == ""
    tick(qapp, window, 45)
    assert shown(window) == ""
    assert window.toast.text() == NOW
    assert said == ["Guitar practice starts soon", "Guitar practice starts now"]


def practice(window: NativeWindow) -> dict:
    return next(block for block in window.session.blocks if block["id"] == "practice")


def test_a_kept_reminder_goes_when_its_block_moves_to_another_time(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    assert shown(window) == SOON
    window.session.add_block({**practice(window), "start": "19:30"})
    tick(qapp, window, 41)
    assert shown(window) == ""
    assert window.session.visible_reminders() == []
    tick(qapp, window, 45)
    assert window.toast.text() != NOW


def test_a_kept_reminder_goes_when_its_block_is_deleted(qapp: QApplication, no_service: NativeWindow) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    assert shown(window) == SOON
    window.session.delete_block("practice")
    tick(qapp, window, 41)
    assert shown(window) == ""
    tick(qapp, window, 45)
    assert window.toast.text() != NOW


def test_a_kept_reminder_stays_when_its_block_changes_in_a_way_that_leaves_the_start_alone(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    window.session.add_block({**practice(window), "duration_min": 45})
    tick(qapp, window, 41)
    assert shown(window) == SOON


def test_with_a_lead_of_fifteen_a_snooze_comes_back_five_minutes_later_and_is_gone_at_the_start(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window, lead=15)
    tick(qapp, window, 30)
    assert shown(window) == SOON
    tick(qapp, window, 31)
    window.alert_strip.snooze.click()
    for minute in (32, 33, 34, 35):
        tick(qapp, window, minute)
        assert shown(window) == "", f"back early at 18:{minute}"
    tick(qapp, window, 36)
    assert shown(window) == SOON
    tick(qapp, window, 44)
    assert shown(window) == SOON
    tick(qapp, window, 45)
    assert shown(window) == ""
    assert window.toast.text() == NOW


def test_got_it_closes_it_for_good_with_no_start_notice_either(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    said = notices_of(window)
    ready(qapp, window)
    tick(qapp, window, 40)
    window.alert_strip.dismiss.click()
    for minute in range(41, 48):
        tick(qapp, window, minute)
        assert shown(window) == ""
    assert said == ["Guitar practice starts soon"]


def test_two_reminders_at_once_are_both_reachable_and_snooze_acts_on_the_one_shown(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    add_practice(qapp, window, id="chess", title="Chess club")
    tick(qapp, window, 40)
    first = shown(window)
    assert first.endswith("(+1 more)")
    window.alert_strip.snooze.click()
    second = shown(window)
    assert second and second != first and "(+1 more)" not in second
    assert first.split(" — ")[0] not in second
    window.alert_strip.dismiss.click()
    assert shown(window) == ""
    tick(qapp, window, 41)
    assert shown(window) == ""


def test_a_reminder_arriving_does_not_take_the_keyboard_from_a_text_box(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    edit = QLineEdit(window)
    edit.show()
    window.activateWindow()
    edit.setFocus()
    wait_until(qapp, lambda: window.focusWidget() is edit)
    QTest.keyClicks(edit, "ab")
    tick(qapp, window, 40)
    assert shown(window) == SOON
    assert window.focusWidget() is edit
    QTest.keyClicks(edit, "cd")
    assert edit.text() == "abcd"


def test_snooze_then_got_it_are_reached_in_order_by_tab_and_named_for_a_screen_reader(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    strip = window.alert_strip
    assert strip.snooze.text() == "Snooze"
    assert strip.snooze.accessibleName() == "Snooze this reminder for 5 minutes"
    assert strip.dismiss.text() == "Got it"
    for button in (strip.snooze, strip.dismiss):
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert strip.snooze.nextInFocusChain() is strip.dismiss


@pytest.mark.parametrize("key", [Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_space_and_enter_press_snooze_and_got_it(
    qapp: QApplication, no_service: NativeWindow, key: Qt.Key
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    QTest.keyClick(window.alert_strip.snooze, key)
    assert shown(window) == ""
    tick(qapp, window, 41)
    assert shown(window) == ""


def test_a_screen_reader_is_told_the_reminder_once_politely_when_it_appears(
    qapp: QApplication, no_service: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = no_service
    heard: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        widgets, "announce", lambda _widget, words, assertive=False: heard.append((words, assertive))
    )
    ready(qapp, window)
    tick(qapp, window, 40)
    tick(qapp, window, 41)
    tick(qapp, window, 42)
    assert heard == [(SOON, False)]


def test_with_a_notification_service_nothing_stays_and_the_tray_and_toast_work_as_before(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    window = with_stand_ins(open_light(size=(1280, 860)))
    ready(qapp, window)
    tick(qapp, window, 40)
    assert window._tray_icon.shown == [("Guitar practice starts soon", "6:45 PM · Thu")]
    assert window.toast.text() == SOON
    assert not window.alert_strip.isVisible()


def test_signing_out_and_in_as_someone_else_leaves_no_reminder_or_snooze(
    qapp: QApplication, no_service: NativeWindow
) -> None:
    window = no_service
    ready(qapp, window)
    tick(qapp, window, 40)
    tick(qapp, window, 41)
    window.alert_strip.snooze.click()
    window.session._clear_local()
    assert window.session.visible_reminders() == []
    assert window.session.snoozed_reminders == {}
    assert shown(window) == ""


def test_a_snoozed_reminder_is_read_out_again_when_it_comes_back(
    qapp: QApplication, no_service: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = no_service
    heard: list[str] = []
    monkeypatch.setattr(widgets, "announce", lambda _widget, words, assertive=False: heard.append(words))
    ready(qapp, window, lead=15)
    tick(qapp, window, 30)
    tick(qapp, window, 31)
    window.alert_strip.snooze.click()
    tick(qapp, window, 35)
    assert heard == [SOON]
    tick(qapp, window, 36)
    assert shown(window) == SOON
    assert heard == [SOON, SOON]
