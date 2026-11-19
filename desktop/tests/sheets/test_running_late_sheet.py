# ruff: noqa: F811
"""The Material Running late sheet: it previews what moves, then accepts or drops the preview through the
session.

Expected words and values come from the Widgets sheet's wording and from the week the fixtures build (a
History essay Thursday 18:45 for an hour, the clock at Thursday 19:00).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.reuse import late_locked_line  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.logic_support import fail_once  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_material import _snack  # noqa: E402


def test_running_late_previews_then_accepts_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    before = len(shell.session.blocks)
    known = {item["id"] for item in shell.session.blocks}
    sheets.openLate()
    form = sheets.form
    assert sheets.kind == "late"
    assert form["heading"] == "Running late"
    assert form["intro"] == (
        "Say how late you are and preview what moves. Nothing changes until you accept it."
    )
    assert [choice["value"] for choice in form["choices"]] == [15, 30, 60]
    assert form["minutes"] == 30
    assert form["previewed"] is False
    assert form["context"].startswith("History essay,")
    assert form["context"].endswith("moves 30 min later")
    sheets.setLate(60)
    assert sheets.form["context"].endswith("moves 60 min later")
    sheets.setLate(30)
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None)
    wait_until(qapp, lambda: sheets.form["previewed"] is True)
    assert sheets.form["changes"]
    assert any("History essay" in line for line in sheets.form["changes"])
    assert shell.session.late_preview is not None
    assert len(shell.session.blocks) == before
    sheets.acceptLate()
    assert sheets.kind == ""
    assert shell.session.late_preview is None
    assert len(shell.session.blocks) == before + 1
    late = next(item for item in shell.session.blocks if item["id"] not in known)
    assert late["duration_min"] == 30
    assert late["days"] == [3]
    settle(qapp, shell)


def test_cancelling_running_late_drops_the_preview(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    before = len(shell.session.blocks)
    sheets.openLate()
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None)
    sheets.closeSheet()
    assert sheets.kind == ""
    assert shell.session.late_preview is None
    assert len(shell.session.blocks) == before


def test_a_blocked_running_late_says_why_and_opens_nothing(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell.session.dirty = True
    sheets.openLate()
    assert sheets.kind == ""
    assert sheets.notice == "Saving your last change… Running late will work in a moment."
    shell.session.dirty = False
    shell.session.conflict = True
    sheets.openLate()
    assert sheets.kind == ""
    assert sheets.notice == (
        "This week changed in another window. Choose More > Reload this week, then try again."
    )


def _accept_late(qapp: QApplication, shell: NativeWindow, sheets) -> tuple[dict, str]:
    sheets.openLate()
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None and not shell.session.busy)
    preview = shell.session.late_preview
    moved = len((preview.get("trace") or {}).get("moves") or [])
    block = preview["block"]
    sheets.acceptLate()
    return block, late_locked_line(block, moved)


def test_accepting_running_late_says_locked_once_it_is_saved(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block, said = _accept_late(qapp, shell, sheets)
    assert shell.session.selected_block_id == block["id"]
    # "Locked" is not said before the save answers: until then the late start is not kept anywhere.
    assert sheets.notice != said
    wait_until(qapp, lambda: sheets.notice == said, what=lambda: sheets.notice)
    assert shell.session.dirty is False
    assert any(item["id"] == block["id"] for item in shell.session.blocks)


def test_a_save_without_the_late_start_does_not_confirm_it(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    """A save already in flight when Running late was accepted stores the week without it."""
    said = "Running late: 19:00–19:30 is now locked."
    sheets._late_waiting = ("b-late-not-stored-yet", said)
    shell.session.save_finished.emit(True, "Saved.")
    qapp.processEvents()
    assert sheets.notice != said
    assert sheets._late_waiting is not None, "still waiting for the save that carries it"


def test_a_late_start_that_fails_to_save_says_so_instead(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    fail_once(shell.session, "POST", "/api/changes", 409)
    _block, said = _accept_late(qapp, shell, sheets)
    wait_until(qapp, lambda: _snack(shell).startswith("Not saved."), what=lambda: _snack(shell))
    assert sheets.notice != said
    assert shell.session.conflict is True


def test_cancelling_running_late_after_a_preview_leaves_no_words_behind(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openLate()
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None and not shell.session.busy)
    wait_until(qapp, lambda: sheets.form["previewed"] is True)
    assert sheets.form["summary"] == "1 task moves"
    sheets.closeSheet()
    assert shell.session.late_preview is None
    assert sheets.kind == "" and sheets.notice == ""
