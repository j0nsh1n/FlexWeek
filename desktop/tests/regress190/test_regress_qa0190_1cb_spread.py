"""Regression for QA's 1c-B (fix-specs-0190.md, "Fix first if Joo says yes"; not decided yet): the two Plan
settings rows. The solver rules (150 min daily cap, finish a day early, 30 min after school) are already
our backend/tests/regress184/test_regress_item1c_spread.py's three known failures, which 0.19.0's own copy
deleted. Not covered: the amber "Over your 2.5 h limit" day header, which is painted inside the hours with
no widget or accessible object to read yet; the fix gives it an accessible name, and a test can follow.
If Joo says no, delete this file and those three tests. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from desktop.native.settings import SECTIONS
from desktop.tests.window_support import qapp, server, settled, signed_out, window  # noqa: F401

KNOWN = "known failure (1c-B, if Joo says yes): Planning has no '{row}' row"


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(row, marks=pytest.mark.xfail(strict=True, reason=KNOWN.format(row=row)))
        for row in ("Most homework per day", "Break after school")
    ],
)
def test_1cb_planning_settings_have_the_spread_rows(qapp, window, row) -> None:
    window._open_settings()
    page = window._settings
    try:
        page.nav.setCurrentRow(SECTIONS.index("Planning"))
        settled(qapp, window)
        words = [label.text() for label in page.findChildren(QLabel) if label.isVisibleTo(page)]
        assert any(row in text for text in words), words
    finally:
        window._close_settings(save=False)
        settled(qapp, window)
