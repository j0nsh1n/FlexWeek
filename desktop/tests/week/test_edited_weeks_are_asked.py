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
from desktop.native.client import ApiError  # noqa: E402
from desktop.native.fields import week_starts_on  # noqa: E402
from desktop.native.material.bridge_sheets import SheetsBridge  # noqa: E402
from desktop.native.setup import WEEK  # noqa: E402
from desktop.native.widgets import ConfirmSheet, SchoolHoursDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.material_support import named, show_material  # noqa: E402
from desktop.tests.sheets.support_material_sheets import click  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.test_repeats_from_the_open_week import WEDNESDAY, block, school_of  # noqa: E402
from desktop.tests.week.test_standing_week import (  # noqa: E402, F401
    JOB,
    SCHOOL,
    SOCCER,
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
        seen["filled"] = sheet.buttons["keep"].property("filled") is True
        seen["others_outlined"] = (
            sheet.buttons["replace"].property("outlined") is True
            and sheet.buttons["from_today"].property("outlined") is True
        )
        sheet.buttons["keep"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    school_hours(qapp, window, monkeypatch)
    assert seen["body"] == "The week of 16 November has its own School times."
    assert seen["default"] == "keep"
    assert seen["label"] == "Except edited"
    assert seen["marked"] is True
    assert seen["filled"] is True
    assert seen["others_outlined"] is True
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


def test_cancel_on_the_setup_week_page_stays_there_and_saves_nothing(
    qapp, window, after_setup, monkeypatch
) -> None:
    skip_wednesday(qapp, after_setup)
    before = school_of(after_setup)
    cutoff_before = (after_setup.preferences or {}).get("day_cutoff")
    starts = week_starts_on()
    window._open_setup(WEEK, first_run=False)
    page = window.setup_page
    page.school_times.set_span("08:30", 360)
    page.cutoff.setCurrentIndex(page.cutoff.findData("21:00"))
    page.week_start.setCurrentIndex(page.week_start.findData("wednesday"))

    def cancel(sheet: ConfirmSheet) -> int:
        sheet.buttons["stay"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", cancel)
    page.next.click()
    assert page._step == WEEK
    assert page.school_times.span() == ("08:30", 360)
    assert page.cutoff.currentData() == "21:00"
    assert page.week_start.currentData() == "wednesday"
    assert week_starts_on() == starts
    assert school_of(after_setup) == before
    assert (after_setup.preferences or {}).get("day_cutoff") == cutoff_before
    assert not after_setup.dirty


def test_cancel_on_the_material_setup_week_page_stays_there_and_saves_nothing(
    qapp, window, after_setup
) -> None:
    show_material(qapp, window)
    skip_wednesday(qapp, after_setup)
    before = school_of(after_setup)
    cutoff_before = (after_setup.preferences or {}).get("day_cutoff")
    starts = week_starts_on()
    window._open_setup(WEEK, first_run=False)
    bridge = window._material_page.bridge.account
    bridge.setSchoolEnd("14:30")
    bridge.setCutoff("21:00")
    bridge.setWeekStart("wednesday")
    root = window._material_page.root
    tries = {"n": 0}

    def poke() -> None:
        tries["n"] += 1
        prompts = [item for item in named(root, "sheetPrompt") if item.property("visible")]
        stay = named(prompts[0], "prompt_stay") if prompts else []
        if not stay and tries["n"] < 80:
            QTimer.singleShot(0, poke)
            return
        assert stay, "the edited-weeks question did not appear"
        click(window, stay[0])

    QTimer.singleShot(0, poke)
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    assert bridge._school_end == "14:30"
    assert bridge.cutoff == "21:00"
    assert bridge.weekStart == "wednesday"
    assert week_starts_on() == starts
    assert school_of(after_setup) == before
    assert (after_setup.preferences or {}).get("day_cutoff") == cutoff_before
    assert not after_setup.dirty


def _shorter() -> list[dict]:
    return [{**SCHOOL, "duration_min": 360}, dict(SOCCER), dict(JOB)]


def test_a_failed_save_keeps_all_weeks_for_the_next_save(
    qapp, window, after_setup, monkeypatch
) -> None:
    skip_wednesday(qapp, after_setup)
    sent: list[dict] = []
    real = window.session.client.request

    def request(method, path, payload, ok, err):
        if method == "POST" and path == "/api/changes":
            sent.append(payload)
            err(ApiError(0, "down"))
            return None
        return real(method, path, payload, ok, err)

    monkeypatch.setattr(window.session.client, "request", request)
    window.session.set_setup_blocks(_shorter(), edited="replace")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    window.session._touch("a note")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    assert len(sent) == 2
    edited = {item["id"]: item.get("edited") for item in sent[1]["repeats"]}
    assert edited["school"] == "replace"


def test_a_second_change_before_save_keeps_the_first(qapp, window, after_setup) -> None:
    window.session.set_setup_blocks(_shorter(), edited="replace")
    moved = {**SOCCER, "start": "17:00"}
    window.session.change_repeats([_shorter()[0], moved, dict(JOB)], "moving Soccer", edited="keep")
    by_id = {item["id"]: item for item in window.session._repeat_send or []}
    assert by_id["school"]["edited"] == "replace"
    assert "edited" not in by_id["activity-1"]


def test_two_changes_to_school_before_a_save_goes_through_both_reach_later_weeks(
    qapp, window, after_setup, monkeypatch
) -> None:
    # School moves to 9:00, that save fails, then School is shortened to 360 minutes. A later week
    # gets both changes, as it would if the first save had gone through.
    real = window.session.client.request
    down = {"on": True}

    def request(method, path, payload, ok, err):
        if down["on"] and method == "POST" and path == "/api/changes":
            err(ApiError(0, "down"))
            return None
        return real(method, path, payload, ok, err)

    monkeypatch.setattr(window.session.client, "request", request)
    moved = {**SCHOOL, "start": "09:00"}
    window.session.change_repeats([moved, dict(SOCCER), dict(JOB)], "moving School")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    shorter = {**moved, "duration_min": 360}
    window.session.change_repeats([shorter, dict(SOCCER), dict(JOB)], "shortening School")
    down["on"] = False
    save_and_settle(qapp, window.session)
    go_to(qapp, window.session, LATER)
    _days, start, length, _missed = school_of(window.session)
    assert (start, length) == ("09:00", 360)


def _failing_changes(window, monkeypatch) -> tuple[list[dict], dict]:
    """Every /api/changes payload, and a switch: while it is on, those saves fail."""
    sent: list[dict] = []
    down = {"on": True}
    real = window.session.client.request

    def request(method, path, payload, ok, err):
        if method == "POST" and path == "/api/changes":
            sent.append(payload)
            if down["on"]:
                err(ApiError(0, "down"))
                return None
        return real(method, path, payload, ok, err)

    monkeypatch.setattr(window.session.client, "request", request)
    return sent, down


def test_reload_drops_a_school_change_it_throws_away(qapp, window, after_setup, monkeypatch) -> None:
    # All weeks was chosen, that save failed, and Reload threw the change away. A later save of
    # something else must not send it.
    sent, down = _failing_changes(window, monkeypatch)
    window.session.set_setup_blocks(_shorter(), edited="replace")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    down["on"] = False
    window.session.reload()
    wait_until(qapp, lambda: not window.session.busy)
    window.session._touch("a note")
    save_and_settle(qapp, window.session)
    assert "repeats" not in sent[-1]
    go_to(qapp, window.session, LATER)
    _days, _start, length, _missed = school_of(window.session)
    assert length == SCHOOL["duration_min"]


def test_a_school_change_waits_with_its_own_week(qapp, window, after_setup, monkeypatch) -> None:
    # School shortened in this week, that save failed, then another week is opened and saved: its
    # save does not carry this week's change. Back in this week, saving sends it.
    sent, down = _failing_changes(window, monkeypatch)
    home = window.session.week_start
    window.session.set_setup_blocks(_shorter(), edited="replace")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    down["on"] = False
    go_to(qapp, window.session, LATER)
    window.session._touch("a note")
    save_and_settle(qapp, window.session)
    assert "repeats" not in sent[-1]
    go_to(qapp, window.session, home)
    save_and_settle(qapp, window.session)
    edited = {item["id"]: item.get("edited") for item in sent[-1].get("repeats", [])}
    assert edited.get("school") == "replace"


@pytest.mark.parametrize("edited", ["replace", "keep", "from_today"])
def test_the_save_after_a_school_change_is_not_a_conflict(qapp, window, after_setup, edited) -> None:
    # School shortened with each answer and saved, then something else in the same week is saved.
    # The second save goes through: the first save's reply has the week as the server now holds it.
    window.session.set_setup_blocks(_shorter(), edited=edited)
    save_and_settle(qapp, window.session)
    assert not window.session.conflict
    window.session._touch("a note")
    save_and_settle(qapp, window.session)
    assert not window.session.conflict
    assert not window.session.dirty


def test_a_second_school_change_in_a_week_left_and_come_back_to_keeps_the_first(
    qapp, window, after_setup, monkeypatch
) -> None:
    # School moves to 9:00 and that save fails; another week is opened, then this one again, where
    # School is shortened and saved. A later week gets both changes: the waiting one went and came
    # back with this week's draft.
    sent, down = _failing_changes(window, monkeypatch)
    home = window.session.week_start
    moved = {**SCHOOL, "start": "09:00"}
    window.session.change_repeats([moved, dict(SOCCER), dict(JOB)], "moving School")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy)
    down["on"] = False
    go_to(qapp, window.session, LATER)
    go_to(qapp, window.session, home)
    shorter = {**moved, "duration_min": 360}
    window.session.change_repeats([shorter, dict(SOCCER), dict(JOB)], "shortening School")
    save_and_settle(qapp, window.session)
    go_to(qapp, window.session, LATER)
    _days, start, length, _missed = school_of(window.session)
    assert (start, length) == ("09:00", 360)


def test_closing_the_material_prompt_finishes_the_wait(qapp, window) -> None:
    sheets = SheetsBridge(window, window)
    got: dict = {}
    sheets.pose_edited(
        {"id": "edited-weeks", "title": "Edited weeks", "body": "Later.", "answers": []},
        lambda choice: got.setdefault("choice", choice),
    )
    sheets.forceClose()
    assert got["choice"] is None


def test_a_preview_does_not_apply_after_the_week_changes(
    qapp, window, after_setup, monkeypatch
) -> None:
    skip_wednesday(qapp, after_setup)
    before = school_of(after_setup)

    def preview(_changes, ok, _err) -> None:
        window.session.week_start = "2026-11-23"
        QTimer.singleShot(
            0, lambda: ok({"line": "The week of 16 November has its own School times.", "weeks": [LATER]})
        )

    def answer(sheet: ConfirmSheet) -> int:
        sheet.buttons["keep"].click()
        return 0

    monkeypatch.setattr(window.session, "preview_repeats", preview)
    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    monkeypatch.setattr(window_module.SchoolHoursDialog, "exec", lambda dialog: shorten(dialog))
    window._school_hours()
    wait_until(qapp, lambda: not window.session.busy)
    assert school_of(after_setup) == before


def test_answering_setup_does_not_skip_the_next_question(
    qapp, window, after_setup, monkeypatch
) -> None:
    skip_wednesday(qapp, after_setup)
    asked = {"n": 0}

    def answer(sheet: ConfirmSheet) -> int:
        asked["n"] += 1
        sheet.buttons["keep"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    assert window.confirm_standing(_shorter()) == "keep"
    school_hours(qapp, window, monkeypatch)
    assert asked["n"] == 2


def test_a_sign_out_during_the_preview_ends_the_wait(qapp, window, after_setup, monkeypatch) -> None:
    real = window.session.client.request

    def request(method, path, payload, ok, err):
        if path == "/api/repeat-edits":
            window.session.client.epoch += 1
            return None
        return real(method, path, payload, ok, err)

    monkeypatch.setattr(window.session.client, "request", request)
    assert (
        window._choice_for_edits([{"id": "school", "scope": "from", "from_date": "2026-11-02"}])
        is None
    )


def test_deleting_from_this_week_on_asks_and_keeps_the_edited_week(
    qapp, window, after_setup, monkeypatch
) -> None:
    skip_wednesday(qapp, after_setup)
    seen: dict = {}

    def answer(sheet: ConfirmSheet) -> int:
        seen["body"] = sheet.question.text()
        sheet.buttons["keep"].click()
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    school = block(after_setup, "school")
    assert school is not None
    window._delete_block(school, "series", None, True)
    wait_until(qapp, lambda: not after_setup.busy and not after_setup.dirty)
    assert seen["body"] == "The week of 16 November has its own School times."
    assert block(after_setup, "school") is None
    go_to(qapp, after_setup, LATER)
    assert school_of(after_setup) == ([0, 1, 3, 4], "08:30", 405, [])
