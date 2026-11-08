"""Opening another week keeps the week on screen when the load fails, keeps unsaved work, and stays
on the edge week at the ends of the supported dates. Runs on the light window, where the clock is
the fake clock and the backend answers in this process."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import fail_once, fixed, settled_session, titles
from desktop.tests.window_support import qapp  # noqa: F401

STORAGE_DOWN = "Storage is unavailable. Keep your changes and try again shortly."


def week_after(week_start: str) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(week_start) + timedelta(days=7)).isoformat()


def two_saved_weeks(qapp: QApplication, session: NativeSession) -> tuple[str, str, int, int]:
    """Soccer in the first week and Piano in the next, each saved once, with the first on screen.
    Returns both weeks and the revision each had before its save."""
    first = session.week_start
    second = week_after(first)
    first_before = session.revision
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled_session(qapp, session)
    session.load_week(second)
    settled_session(qapp, session)
    second_before = session.revision
    session.add_block(fixed("piano", "Piano", 1, "17:00"))
    session.save()
    settled_session(qapp, session)
    session.load_week(first)
    settled_session(qapp, session)
    assert (session.week_start, titles(session.blocks), session.revision) == (
        first,
        ["Soccer"],
        first_before + 1,
    )
    return first, second, first_before, second_before


def test_a_failed_week_load_keeps_the_week_on_screen(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    first, second, _, _ = two_saved_weeks(qapp, session)
    fail_once(session, "GET", "/api/week")
    session.load_week(second)
    settled_session(qapp, session)
    assert session.message == STORAGE_DOWN
    assert session.week_start == first
    assert titles(session.blocks) == ["Soccer"]


def test_a_save_after_a_failed_week_load_does_not_overwrite_the_other_week(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    first, second, first_before, second_before = two_saved_weeks(qapp, session)
    fail_once(session, "GET", "/api/week")
    session.load_week(second)
    settled_session(qapp, session)
    session.add_block(fixed("chess", "Chess", 2, "15:00"))
    session.save()
    settled_session(qapp, session)
    assert session.message == "Saved."
    session.load_week(second)
    settled_session(qapp, session)
    assert (session.week_start, titles(session.blocks), session.revision) == (
        second,
        ["Piano"],
        second_before + 1,
    )
    session.load_week(first)
    settled_session(qapp, session)
    assert (session.week_start, titles(session.blocks), session.revision) == (
        first,
        ["Soccer", "Chess"],
        first_before + 2,
    )


def test_stepping_outside_the_supported_dates_stays_on_the_edge_week(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    session.load_week("1999-12-27")
    settled_session(qapp, session)
    assert session.week_start == "1999-12-27"
    session.add_block(fixed("soccer", "Soccer", 5, "16:00"))
    session.save()
    settled_session(qapp, session)
    session.load_week("1999-12-20")
    settled_session(qapp, session)
    assert session.week_start == "1999-12-27"
    assert titles(session.blocks) == ["Soccer"]
    session.load_week("2099-12-28")
    settled_session(qapp, session)
    assert session.week_start == "2099-12-28"
    session.load_week("2100-01-04")
    settled_session(qapp, session)
    assert session.week_start == "2099-12-28"


def test_a_failed_open_day_leaves_day_view_inside_the_week_on_screen(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    first = session.week_start
    fail_once(session, "GET", "/api/week")
    session.open_day(week_after(first))
    settled_session(qapp, session)
    assert session.week_start == first


def test_a_failed_assignments_load_does_not_switch_the_week(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    first, second, _, _ = two_saved_weeks(qapp, session)
    fail_once(session, "GET", "/api/assignments")
    session.load_week(second)
    settled_session(qapp, session)
    assert session.week_start == first
    assert titles(session.blocks) == ["Soccer"]
    session.add_block(fixed("chess", "Chess", 2, "15:00"))
    session.save()
    settled_session(qapp, session)
    session.undo()
    settled_session(qapp, session)
    assert titles(session.blocks) == ["Soccer"]


def test_an_unsaved_week_is_kept_when_opening_another(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    first = session.week_start
    second = week_after(first)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled_session(qapp, session)
    session.add_block(fixed("chess", "Chess", 2, "15:00"))
    wednesday = date_for_day(first, 2)
    session.selected_day = wednesday
    session.load_week(second)
    settled_session(qapp, session)
    assert session.week_start == second
    assert titles(session.blocks) == []
    assert session.selected_day == date_for_day(second, 2)
    session.load_week(first)
    settled_session(qapp, session)
    assert session.week_start == first
    assert titles(session.blocks) == ["Soccer", "Chess"]
    assert session.selected_day == wednesday
    session.reload()
    settled_session(qapp, session)
    assert titles(session.blocks) == ["Soccer"]
