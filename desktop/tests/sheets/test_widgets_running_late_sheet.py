"""The Widgets Running late sheet: Preview comes first and Accept late start takes its place after it,
the summary line shows only once there is a preview, and the top bar's button is greyed on another
week with the reason. How the buttons are drawn is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QPushButton

from desktop.native.widgets import LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import shown, styled
from desktop.tests.window_support import free, settled, still

NO_MOVES = {"moves": [], "unplaced": []}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-widgets-running-late-test"])


def test_running_lates_accept_says_to_preview_first_and_is_off_until_there_is_one(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    late = shown(qapp, LateDialog(parent, "School"))
    hint = late.findChild(QLabel, "whyOff")
    assert not late.accept_button.isEnabled() and hint.isVisible()
    late.show_trace(NO_MOVES, {})
    for _ in range(6):
        qapp.processEvents()
    assert late.accept_button.isEnabled() and not hint.isVisible()
    free(late)
    free(parent)


def test_running_late_shows_its_summary_line_only_once_there_is_a_preview(qapp: QApplication) -> None:
    """Running late left an empty line for its summary before there was one."""
    parent, _palette = styled(qapp)
    late = shown(qapp, LateDialog(parent, "School"))
    assert late.summary.isHidden()
    late.show_trace(NO_MOVES, {})
    assert not late.summary.isHidden()
    free(late)
    free(parent)


def test_running_late_has_preview_then_accept_in_its_place_and_a_bare_cancel(qapp: QApplication) -> None:
    """Preview is filled; after preview, Accept replaces it on one row. Cancel stays bare."""
    parent, _palette = styled(qapp)
    late = shown(qapp, LateDialog(parent, "School"))
    preview = late.findChild(QPushButton, "latePreview")
    cancel = next(button for button in late.findChildren(QPushButton) if button.text() == "Cancel")
    assert not preview.property("outlined")
    assert preview.property("quiet") is not True
    assert cancel.property("quiet") is True
    assert late.accept_button.isEnabled() is False
    assert not late.accept_button.isVisible()
    late.show_trace(NO_MOVES, {})
    qapp.processEvents()
    still(late)
    assert not preview.isVisible()
    assert late.accept_button.isVisible()
    free(late)
    free(parent)


def test_running_late_is_greyed_on_another_week_with_the_reason(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    """Greyed while viewing next week, instead of refusing after the click."""
    window.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, window)
    late = window.findChild(QPushButton, "runningLate")
    assert late.isEnabled()
    window.session.load_week(
        (date.fromisoformat(window.session.week_start) + timedelta(days=7)).isoformat()
    )
    settled(qapp, window)
    assert late.isEnabled() is False
    assert late.toolTip() == "Open this week to use Running late."
    opened: list[str] = []
    window._open_late = lambda: opened.append("opened")  # type: ignore[method-assign]
    late.click()
    assert opened == []
