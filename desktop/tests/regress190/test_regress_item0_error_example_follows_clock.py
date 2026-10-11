"""Regression for fix-specs.md item 0, step 5 and "Wording for 0 and 0g": the unreadable-time line is
"Type a time like {example}.", and the example follows the clock setting ("5:30 PM" on the 12-hour clock,
"17:30" on the 24-hour clock). Spec guard: with the 12-hour clock on, the message contains AM/PM and no
24-hour example. Typed through the window system into the block editor's Start and End boxes.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import BlockDialog
from desktop.tests.regress184.test_regress_item0_time_boxes import _up, enter, press, type_text
from desktop.tests.window_support import free, qapp  # noqa: F401

WANTED = {True: "Type a time like 17:30.", False: "Type a time like 5:30 PM."}


@pytest.mark.parametrize("box", ["start", "end"])
@pytest.mark.parametrize("twenty_four", [True, False], ids=["24-hour", "12-hour"])
def test_0_the_unreadable_time_example_follows_the_clock(qapp, box, twenty_four) -> None:
    set_clock_24h(twenty_four)
    dialog = BlockDialog(None, day=1, start="08:30", duration_min=60)
    _up(qapp, dialog)
    try:
        field = getattr(dialog, box)
        enter(field, "tab-in")
        type_text(field, "99")
        press(field, Qt.Key.Key_Tab)
        said = field.problem()
        assert said == WANTED[twenty_four], said
        assert field.accessibleDescription() == said
        if not twenty_four:
            assert "17:30" not in said and ("PM" in said or "AM" in said)
    finally:
        QTest.qWait(20)
        dialog.hide()
        free(dialog)
