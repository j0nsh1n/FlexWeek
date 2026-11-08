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

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheets import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402


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
