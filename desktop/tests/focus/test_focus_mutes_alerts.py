"""Material's "mute alerts while I focus" rule: reminders wait during a work phase and come when it ends;
the timer's own notices still pass; nothing is held when the rule is off or a Widgets style is in use."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    material_focus_window,
    rules,
)
from desktop.tests.window_support import qapp  # noqa: F401

REMINDER = {"title": "Soccer", "body": "Starts in 5 minutes", "kind": "reminder"}
FOCUS_NOTICE = {"title": "Break", "body": "History essay", "kind": "focus", "tone": "soft"}

WORDS = "Soccer — Starts in 5 minutes"  # how the window words a reminder when it does show it


@pytest.fixture()
def toasted(material_focus_window: NativeWindow) -> Iterator[list[str]]:
    """The reminder words the window really put on screen, after the session's holding back."""
    window = material_focus_window
    seen: list[str] = []
    original = window._say_in_toast

    def spy(words: str, *args: object, **kwargs: object) -> None:
        seen.append(words)
        original(words, *args, **kwargs)  # type: ignore[arg-type]

    window._say_in_toast = spy  # type: ignore[method-assign]
    yield seen
    del window._say_in_toast


def test_reminders_wait_during_a_focus_work_phase_and_come_when_it_ends(
    qapp: QApplication, material_focus_window: NativeWindow, toasted: list[str]
) -> None:
    window = material_focus_window
    session = window.session
    with rules(window):
        assert session.hold_alerts([REMINDER]) == [REMINDER]  # no focus: nothing is held
        assert session.start_quick_focus()
        assert session.focus_mutes_alerts()
        assert session.hold_alerts([FOCUS_NOTICE]) == [FOCUS_NOTICE]  # the timer's own still pass
        session.alerts.emit([REMINDER])
        assert toasted == []  # still working: the reminder is held back
        session.toggle_focus_pause()
        assert session.focus_mutes_alerts()  # paused is still inside focus
        assert toasted == []
        session.advance_focus(False)  # Skip to the break
        assert session.focus["phase"] == "break"
        assert not session.focus_mutes_alerts()
        assert toasted.count(WORDS) == 1  # reminder shown once the work phase was over
        assert session.release_held_alerts() == []  # and only once


@pytest.mark.parametrize(
    ("owned", "prefs"),
    [(True, {"focus_auto_mute": False}), (False, {})],
)
def test_nothing_is_held_when_the_rule_is_off_or_a_widgets_style_is_in_use(
    qapp: QApplication, material_focus_window: NativeWindow, owned: bool, prefs: dict
) -> None:
    window = material_focus_window
    with rules(window, owned, **prefs):
        assert window.session.start_quick_focus()
        assert not window.session.focus_mutes_alerts()
        assert window.session.hold_alerts([REMINDER]) == [REMINDER]


def test_a_reminder_that_arrives_during_focus_is_not_shown_until_focus_ends(
    qapp: QApplication, material_focus_window: NativeWindow, toasted: list[str]
) -> None:
    window = material_focus_window
    with rules(window):
        assert window.session.start_quick_focus()
        window.session.alerts.emit([REMINDER])
        assert toasted == []
        window.session.reset_focus()  # Finish
        assert toasted == [WORDS]


def test_a_reminder_shows_at_once_when_the_rule_is_off(
    qapp: QApplication, material_focus_window: NativeWindow, toasted: list[str]
) -> None:
    window = material_focus_window
    with rules(window, focus_auto_mute=False):
        assert window.session.start_quick_focus()
        window.session.alerts.emit([REMINDER])
        assert toasted == [WORDS]
