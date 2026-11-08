"""The words on the top bar as the window narrows and the text grows: the title is its whole long or short
form, Plan steps down through its three whole forms, Suggest times is never half a word, and Retry save
shows only after a save has failed. Whether it all fits, in one row and inside the window, is a picture
(desktop/tests/pictures/_week_g14.py, week.top_bar_narrow and its neighbours)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QAbstractButton, QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.reuse import planner_title
from desktop.native.window import PLAN_LABEL, PLAN_SHORT, PLAN_TINY, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import fail_once, fixed
from desktop.tests.waiting import wait_until

PLAN_WORDS = (PLAN_LABEL, PLAN_SHORT, PLAN_TINY)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-top-bar-words"])


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def layout_settles(qapp: QApplication, count: int = 4) -> None:
    for _ in range(count):
        qapp.processEvents()


@pytest.fixture()
def planned_week(qapp: QApplication, window: NativeWindow, clock: FakeClock) -> NativeWindow:
    """School on weekdays, soccer on Tuesday and Thursday at 16:00, the History essay placed on
    Thursday at 19:00, and the Science poster waiting for a time, at Thursday 15:40."""
    session = window.session
    clock.set(datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40))
    window.resize(1280, 860)
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "category": "class",
         "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}
    )
    session.add_block(
        {"id": "soccer", "title": "Soccer", "kind": "locked", "category": "exercise",
         "start": "16:00", "duration_min": 90, "days": [1, 3]}
    )
    due = sunday_due(session.week_start)
    for key, title, minutes in (("essay", "History essay", 60), ("poster", "Science poster", 90)):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0})
    session.save()
    settled(qapp, window)
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
    session.save()
    settled(qapp, window)
    return window


def text_size(window: NativeWindow, size: str) -> None:
    window._look = sanitize_look({**window._look, "knobs": {**window._look.get("knobs", {}), "text": size}})
    window._apply_appearance()


def test_the_title_and_plan_always_say_a_whole_form_as_the_window_narrows(
    qapp: QApplication, planned_week: NativeWindow
) -> None:
    """Down to the window's narrowest, in normal and large text, on Week, Day and Month: the title is its
    whole long or short form and Plan one of its three whole forms. At 900 pixels the bar read
    "21 – 2…" and "n my homew"."""
    window, session = planned_week, planned_week.session
    sizes = (("normal", (1280, 1100, 1000, 900, 800)), ("large", (1150, 1000, 900, 800)))
    for text, widths in sizes:
        text_size(window, text)
        for view in ("week", "day", "month"):
            window.findChild(QAbstractButton, f"view{view.title()}").click()
            wait_until(qapp, lambda: not session.busy)
            whole = (planner_title(session, view), planner_title(session, view, short=True))
            for width in widths:
                window.resize(width, 768)
                layout_settles(qapp)
                where = f"{text} text, {view}, {window.width()} px"
                said = window.week_title.text()
                assert said in whole, f"{where}: the title reads {said!r}"
                assert window.solve_button.isVisible(), where
                assert window.solve_button.text() in PLAN_WORDS, where


def test_suggest_times_keeps_a_whole_word_at_the_narrowest_window(
    qapp: QApplication, planned_week: NativeWindow
) -> None:
    """Suggest times and Retry save, which widen the bar, are never half a word at Large text."""
    window, session = planned_week, planned_week.session
    session.preferences = {**(session.preferences or {}), "planning_style": "manual"}
    window.retry_button.setVisible(True)
    window._sync_chrome()
    text_size(window, "large")
    window.resize(640, 768)
    layout_settles(qapp)
    assert window.solve_button.text() in ("Suggest times", "Suggest")


def test_on_timeline_day_at_large_text_plan_and_more_keep_whole_words(
    qapp: QApplication, planned_week: NativeWindow
) -> None:
    """The bar wrapped to two rows here and pushed the Due chips off screen; the cure is a shorter Plan,
    the last of its steps, where it keeps the bar on one row."""
    window = planned_week
    text_size(window, "large")
    window._layout = sanitize_layout({"main": "timeline", "day": "one"})
    window._day_mode = True
    window._on_week()
    window.resize(1150, 768)
    layout_settles(qapp, 6)
    assert window.more_button.text() in ("More", "")
    assert window.solve_button.text() in PLAN_WORDS


def test_retry_save_shows_only_after_a_save_fails(qapp: QApplication, planned_week: NativeWindow) -> None:
    """A save on its way is not a failed one. Month's own fetch landing while the week saved drew the
    week with Retry save showing. A save that failed keeps Retry showing, greyed, while it is tried
    again. (The view buttons not jumping under the pointer is a picture, week.top_bar_while_saving.)"""
    window, session = planned_week, planned_week.session
    window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(qapp, lambda: session.month_data is not None and not session.busy)
    page = window._week_page.layout()
    page.activate()

    def drawn_mid_save() -> None:
        # What a reply landing during the save does: the week is drawn again.
        assert session.busy and session.pending_save is not None, "the save is no longer on its way"
        session.week_changed.emit()
        page.activate()

    session.blocks = [*session.blocks, fixed("lab", "Lab", 1, "09:00")]
    session.dirty = True
    session.save()
    drawn_mid_save()
    assert not window.retry_button.isVisible(), "Retry save showed while the save was still on its way"
    settled(qapp, window)
    assert not window.retry_button.isVisible()

    fail_once(session, "POST", "/api/changes")
    session.blocks = [*session.blocks, fixed("art", "Art", 2, "10:00")]
    session.dirty = True
    session.save()
    wait_until(qapp, lambda: not session.busy)
    assert window.retry_button.isVisible() and window.retry_button.isEnabled(), "a failed save offers Retry"
    window.retry_button.click()
    drawn_mid_save()
    assert window.retry_button.isVisible(), "Retry save went away while its own retry was on its way"
    assert not window.retry_button.isEnabled(), "Retry save was pressable while it was retrying"
    settled(qapp, window)
    assert not window.retry_button.isVisible(), "Retry save stayed after the retry saved"
