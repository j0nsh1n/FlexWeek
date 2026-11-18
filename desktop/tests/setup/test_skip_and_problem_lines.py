"""A time box's problem line shows under the box: the block editor's bad start says so."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import BlockDialog
from desktop.tests.sheets.support_dialogs import school, shown, styled
from desktop.tests.test_regress_item0_time_boxes import enter, press, type_text
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-setup-skip-test"])


def _gone(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.hide()
        free(widget)


def test_the_block_editors_bad_start_says_so_in_a_line_under_the_box(qapp: QApplication) -> None:
    set_clock_24h(False)
    window, _palette = styled(qapp)
    # Add is stepped (What / When / Category); Edit stays one page with Start beside End.
    dialog = BlockDialog(window, school(), occurrence_day=1)
    shown(qapp, dialog)
    try:
        start = dialog.start
        enter(start, "tab-in")
        type_text(start, "abc")
        press(start, Qt.Key.Key_Tab)
        for _ in range(4):
            qapp.processEvents()
        assert start.problem()
        assert start._line.isVisible()
    finally:
        _gone(dialog, window)
