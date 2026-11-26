"""A verified update saves what is unsaved before it is put in place.

With nothing waiting, it installs at once. When the save fails or runs out of time, nothing is
installed, the app stays open, and the student is told in the same words as closing, with "update
again", and can try again from the update sheet.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import desktop.native.window as window_module  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.audit_support import refuse_all  # noqa: E402
from desktop.tests.logic_support import fixed  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import database, qapp, signed_out, window  # noqa: E402, F401

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811

PATH = "/downloaded/flexweek"
UPDATE_WAITS = (
    "FlexWeek is still saving before it closes, so the update wasn't installed. "
    "Choose Update now again once that's done."
)
UPDATE_FAILED = (
    "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. "
    "Choose Retry save, then update again."
)


class Offer:
    """The update sheet's two answers, without opening Material."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.done = False

    def update_problem(self, why: str) -> None:
        self.problems.append(why)

    def update_done(self) -> None:
        self.done = True


def _watch(
    window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], list[bool], list[bool], Offer]:
    """Records each install, whether the week was already saved then, and each quit."""
    applied: list[str] = []
    saved_first: list[bool] = []
    quits: list[bool] = []
    offer = Offer()
    session = window.session

    def apply(path: str) -> None:
        saved_first.append(not (session.dirty or session.dirty_assignments or session.pending_save))
        applied.append(path)

    monkeypatch.setattr(window_module, "apply_update", apply)
    monkeypatch.setattr(window_module, "UPDATE_QUIT_MS", 0)
    monkeypatch.setattr(window, "quit_app", lambda: quits.append(True))
    monkeypatch.setattr(window, "_update_sheet", lambda: offer)
    return applied, saved_first, quits, offer


def test_an_unsaved_change_is_saved_before_the_update_is_installed(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    applied, saved_first, quits, offer = _watch(window, monkeypatch)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    assert session.dirty

    window._on_update_ready(PATH)

    assert applied == [] and quits == []
    wait_until(qapp, lambda: applied == [PATH] and quits == [True])
    assert saved_first == [True]
    assert offer.done is True and offer.problems == []
    session.reload()
    wait_until(qapp, lambda: not session.busy and [block["id"] for block in session.blocks] == ["soccer"])


def test_a_save_that_fails_installs_nothing_and_says_so(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    applied, _saved_first, quits, offer = _watch(window, monkeypatch)
    refuse_all(window, "POST", "/api/changes")
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is not None)

    window._on_update_ready(PATH)

    assert applied == []
    wait_until(qapp, lambda: session.message == UPDATE_FAILED and not window._quitting)
    assert applied == [] and quits == []
    assert window._quitting is False
    assert offer.done is False and offer.problems == [UPDATE_FAILED]
    assert session.pending_save is not None


def test_nothing_unsaved_installs_the_update_at_once(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    applied, saved_first, quits, offer = _watch(window, monkeypatch)
    assert not session.dirty and not session.dirty_assignments and session.pending_save is None

    window._on_update_ready(PATH)

    assert applied == [PATH] and saved_first == [True]
    assert offer.done is True and offer.problems == []
    wait_until(qapp, lambda: quits == [True])


def test_an_update_ready_while_closing_waits_installs_nothing_and_frees_the_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A close or sign-out already waiting on its save does not run the install; the sheet must not stay
    on "Downloading…"."""
    session = window.session
    applied, _saved_first, quits, offer = _watch(window, monkeypatch)
    monkeypatch.setattr(window, "_leaving", object())

    window._on_update_ready(PATH)

    assert applied == [] and quits == []
    assert session.message == UPDATE_WAITS
    assert offer.done is False and offer.problems == [UPDATE_WAITS]
