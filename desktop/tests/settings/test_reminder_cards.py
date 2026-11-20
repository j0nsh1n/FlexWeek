"""A reminder kept on screen as a card with Snooze and Close, followed to what the student sees.

The clock is held on Thursday evening (support_reminders). Guitar practice starts at 18:45 with a
10-minute lead, so its reminder is due from 18:35. A card shows when the computer shows no pop-ups
(no tray, or a tray that cannot show messages) or when "Leave reminders on screen" is on.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.grid_support import key
from desktop.tests.light_app import account, open_light  # noqa: F401
from desktop.tests.settings.support_reminders import (
    PRACTICE_NOTICE,
    REMINDER,
    Tray,
    add_practice,
    at,
    choose,
    tick,
    with_stand_ins,
)
from desktop.tests.week.support_material import _click, _named, _qml, _snack
from desktop.tests.window_support import qapp, settled  # noqa: F401

SOON = ("Guitar practice starts soon", "6:45 PM · Thu")
NOW = "Guitar practice starts now — 6:45 PM · Thu"


class QuietTray(Tray):
    """A tray the desktop has, which cannot show a message."""

    def supportsMessages(self) -> bool:  # noqa: N802
        return False


@pytest.fixture()
def new_window(open_light: Callable[..., NativeWindow]) -> NativeWindow:
    return with_stand_ins(open_light(size=(1280, 860)))


def cards(window: NativeWindow) -> list[tuple[str, str]]:
    """The reminder cards the student can see, top first, as (title, body)."""
    root = window._material_page.root
    return [
        (
            str(_qml(card, "reminderCardTitle").property("text")),
            str(_qml(card, "reminderCardBody").property("text")),
        )
        for card in _named(root, "reminderCard")
        if card.property("visible") is True
    ]


def press(window: NativeWindow, button: str) -> None:
    """Snooze or Close on the top card, with a real click."""
    root = window._material_page.root
    card = next(item for item in _named(root, "reminderCard") if item.property("visible") is True)
    _click(window, _qml(card, button))


def ready(qapp: QApplication, window: NativeWindow, *, tray: bool = True, **prefs: object) -> None:
    """From 18:30: a 10-minute lead, and Guitar practice at 18:45 on the week."""
    if not tray:
        window._tray_icon = None
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10, **prefs)
    add_practice(qapp, window)


def test_a_tray_that_shows_messages_and_the_setting_off_make_no_card(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window)
    tick(qapp, window, 35)
    assert cards(window) == []
    assert window._tray_icon.shown == [PRACTICE_NOTICE]
    assert _snack(window) == REMINDER


def test_no_tray_makes_a_card_and_not_a_notice_line(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    assert cards(window) == [SOON]
    assert _snack(window) == "", "a card says it once; the notice bar does not repeat it"


def test_a_tray_that_cannot_show_messages_makes_a_card(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    window._tray_icon = QuietTray()
    ready(qapp, window)
    tick(qapp, window, 35)
    assert cards(window) == [SOON]
    assert window._tray_icon.shown == []


def test_leave_reminders_on_screen_makes_a_card_even_with_a_tray(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window, reminder_dnd_override=True)
    tick(qapp, window, 35)
    assert cards(window) == [SOON]
    assert window._tray_icon.shown == [PRACTICE_NOTICE], "the tray still gets its message"
    assert _snack(window) == ""


def test_snooze_hides_the_card_and_it_comes_back_five_minutes_later(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    press(window, "reminderCardSnooze")
    assert cards(window) == []
    for minute in range(36, 40):
        tick(qapp, window, minute)
        assert cards(window) == [], f"back too early at 18:{minute}"
    tick(qapp, window, 40)
    assert cards(window) == [SOON]
    assert _snack(window) == ""


def test_a_snooze_near_the_start_comes_back_at_the_start_as_starts_now(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 43)
    assert cards(window) == [SOON]
    press(window, "reminderCardSnooze")
    tick(qapp, window, 44)
    assert cards(window) == []
    assert _snack(window) == ""
    tick(qapp, window, 45)
    assert cards(window) == []
    assert _snack(window) == NOW


def test_close_drops_the_card_for_good(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    press(window, "reminderCardClose")
    assert cards(window) == []
    for minute in range(36, 45):
        tick(qapp, window, minute)
        assert cards(window) == [], f"came back at 18:{minute}"


def test_the_card_stays_until_the_block_starts_then_starts_now_takes_over(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    for minute in range(36, 45):
        tick(qapp, window, minute)
        assert cards(window) == [SOON], f"gone early at 18:{minute}"
    tick(qapp, window, 45)
    assert cards(window) == []
    assert _snack(window) == NOW


def test_moving_the_block_drops_its_card(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    window.session.place_block("practice", 3, 4, 19 * 60, 19 * 60 + 30)
    settled(qapp, window)
    moved = next(item for item in window.session.blocks if item["id"] == "practice")
    assert (moved["days"], moved["start"]) == ([4], "19:00"), "the move itself did not happen"
    assert cards(window) == []


def test_deleting_the_block_drops_its_card(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    window.session.delete_block("practice")
    settled(qapp, window)
    assert not any(item["id"] == "practice" for item in window.session.blocks)
    assert cards(window) == []


def test_renaming_the_block_renames_its_card(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    next(item for item in window.session.blocks if item["id"] == "practice")["title"] = "Piano lesson"
    window.session.week_changed.emit()
    assert cards(window) == [("Piano lesson starts soon", "6:45 PM · Thu")]


def test_two_reminders_stack_with_the_newest_on_top(qapp: QApplication, new_window: NativeWindow) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    window.session.add_block(
        {"id": "chess", "title": "Chess", "kind": "locked", "category": "class", "start": "18:50",
         "duration_min": 30, "days": [3]}
    )
    window.session.save()
    settled(qapp, window)
    tick(qapp, window, 40)
    assert cards(window) == [("Chess starts soon", "6:50 PM · Thu"), SOON]


def test_a_screen_reader_hears_the_card_and_the_keyboard_stays_put(
    qapp: QApplication, new_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = new_window
    spoken: list[str] = []
    monkeypatch.setattr(
        "desktop.native.fields.announce", lambda _widget, words, **_rest: spoken.append(words)
    )
    ready(qapp, window, tray=False)
    page = window._material_page
    before = page.activeFocusItem()
    tick(qapp, window, 35)
    assert spoken == [REMINDER]
    assert page.activeFocusItem() is before


def test_snooze_and_close_are_tab_stops_and_escape_does_not_close_the_card(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    ready(qapp, window, tray=False)
    tick(qapp, window, 35)
    card = next(item for item in _named(window._material_page.root, "reminderCard"))
    assert _qml(card, "reminderCardSnooze").property("activeFocusOnTab") is True
    assert _qml(card, "reminderCardClose").property("activeFocusOnTab") is True
    key(window, Qt.Key.Key_Escape)
    assert cards(window) == [SOON]
