"""Changing School from this week on asks first when a later week has its own edit.

Except edited is the default and is what a change did before it asked. Cancel saves nothing. With no
such later week, nothing is asked. Real dates: the clock is Thursday 5 November 2026, so the open week
is 2 November and the later week is 16 November.
"""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from desktop.native import window as window_module  # noqa: E402
from desktop.native.widgets import ConfirmSheet, SchoolHoursDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.material_support import named, show_material  # noqa: E402
from desktop.tests.sheets.support_material_sheets import click  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.test_repeats_from_the_open_week import WEDNESDAY, school_of  # noqa: E402
from desktop.tests.week.test_standing_week import (  # noqa: E402, F401
    after_setup,
    go_to,
    save_and_settle,
)
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401

LATER = "2026-11-16"
END = 14 * 60 + 30


def shorten(dialog: SchoolHoursDialog) -> QDialog.DialogCode:
    dialog.times.end.set_minutes(END)
    dialog.accept()
    return QDialog.DialogCode.Accepted


def skip_wednesday(qapp: QApplication, session) -> str:
    """A one-week edit in the week of 16 November, then back to the week the change starts from."""
    home = session.week_start
    go_to(qapp, session, LATER)
    session.delete_block("school", scope="occurrence", day=WEDNESDAY)
    save_and_settle(qapp, session)
    go_to(qapp, session, home)
    return home


def school_hours(qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(window_module.SchoolHoursDialog, "exec", lambda dialog: shorten(dialog))
    window._school_hours()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    settled(qapp, window)


def test_school_hours_asks_nothing_when_no_later_week_was_edited(
    qapp, window, after_setup, monkeypatch
) -> None:
    def asked(sheet: ConfirmSheet) -> int:
        pytest.fail(f"asked: {sheet.question.text()}")

    monkeypatch.setattr(ConfirmSheet, "exec", asked)
    school_hours(qapp, window, monkeypatch)
    assert school_of(after_setup)[:3] == ([0, 1, 2, 3, 4], "08:30", 360)


def test_the_question_defaults_to_except_edited(qapp, window, after_setup, monkeypatch) -> None:
    skip_wednesday(qapp, after_setup)
    seen: dict = {}

    def answer(sheet: ConfirmSheet) -> int:
        seen["body"] = sheet.question.text()
        seen["default"] = sheet._default
        seen["label"] = sheet.buttons["keep"].text()
        seen["marked"] = sheet.buttons["keep"].isDefault()
        sheet.buttons["keep"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    school_hours(qapp, window, monkeypatch)
    assert seen["body"] == "The week of 16 November has its own School times."
    assert seen["default"] == "keep"
    assert seen["label"] == "Except edited"
    assert seen["marked"] is True
    go_to(qapp, after_setup, LATER)
    assert school_of(after_setup) == ([0, 1, 3, 4], "08:30", 360, [])


def test_cancel_saves_nothing(qapp, window, after_setup, monkeypatch) -> None:
    home = skip_wednesday(qapp, after_setup)
    before = school_of(after_setup)

    def cancel(sheet: ConfirmSheet) -> int:
        sheet.buttons["stay"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", cancel)
    monkeypatch.setattr(window_module.SchoolHoursDialog, "exec", lambda dialog: shorten(dialog))
    window._school_hours()
    wait_until(qapp, lambda: not window.session.busy)
    assert school_of(after_setup) == before
    assert not after_setup.dirty
    go_to(qapp, after_setup, LATER)
    assert school_of(after_setup) == ([0, 1, 3, 4], "08:30", 405, [])
    go_to(qapp, after_setup, home)
    assert school_of(after_setup) == before


def test_material_asks_nothing_when_no_later_week_was_edited(
    qapp, window, after_setup, monkeypatch
) -> None:
    show_material(qapp, window)

    def asked(*_args) -> None:
        pytest.fail("asked")

    monkeypatch.setattr(window._material_page.bridge._sheets, "pose_edited", asked)
    monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("widgets sheet"))
    school_hours(qapp, window, monkeypatch)
    assert school_of(after_setup)[:3] == ([0, 1, 2, 3, 4], "08:30", 360)


def test_material_defaults_to_except_edited_and_cancel_saves_nothing(
    qapp, window, after_setup, monkeypatch
) -> None:
    show_material(qapp, window)
    skip_wednesday(qapp, after_setup)
    before = school_of(after_setup)
    seen: dict = {}
    root = window._material_page.root
    tries = {"n": 0}

    def poke() -> None:
        tries["n"] += 1
        prompts = [item for item in named(root, "sheetPrompt") if item.property("visible")]
        button = named(prompts[0], "prompt_keep") if prompts else []
        focused = bool(button) and button[0].property("activeFocus") is True
        if (not prompts or not focused) and tries["n"] < 40:
            QTimer.singleShot(0, poke)
            return
        assert prompts, "the edited-weeks question did not appear"
        assert button, "Except edited was not on the question"
        seen["label"] = str(button[0].property("text"))
        seen["focused"] = focused
        ask = prompts[0].property("ask")
        seen["body"] = ask["body"] if isinstance(ask, dict) else ""
        click(window, named(prompts[0], "prompt_stay")[0])

    QTimer.singleShot(0, poke)
    monkeypatch.setattr(window_module.SchoolHoursDialog, "exec", lambda dialog: shorten(dialog))
    window._school_hours()
    assert seen["label"] == "Except edited"
    assert seen["focused"] is True
    assert seen["body"] == "The week of 16 November has its own School times."
    assert school_of(after_setup) == before
    assert not after_setup.dirty
    go_to(qapp, after_setup, LATER)
    assert school_of(after_setup) == ([0, 1, 3, 4], "08:30", 405, [])
