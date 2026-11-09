"""Saving the recovery codes: Continue stays off, with a line saying why, until the codes are confirmed
kept; Save... asks on a sheet to keep the file private before the system's file dialog opens in
Documents. How readable the off button is is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native import window as window_module
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import when_open
from desktop.tests.window_support import still


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-recovery-sheets-test"])


def test_continue_to_my_week_is_off_with_a_line_saying_why_until_the_box_is_ticked(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    window._show_recovery(["aaaa-bbbb", "cccc-dddd"])
    for _ in range(4):
        qapp.processEvents()
    still(window)
    button = window.recovery_continue
    hint = window.findChild(QLabel, "whyOff")
    assert not button.isEnabled() and hint.isVisible() and hint.text() == "Tick the box above to continue."
    window.recovery_ack.setChecked(True)
    qapp.processEvents()
    assert button.isEnabled() and not hint.isVisible()


def test_the_recovery_file_sheet_says_to_keep_it_private_then_opens_the_file_dialog_on_documents(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sheet comes first, and the system's file dialog starts in Documents."""
    asked: list[str] = []

    def answer(_parent: object, _caption: str, start: str, _kinds: str) -> tuple[str, str]:
        asked.append(start)
        return "/somewhere/codes.txt", ""

    monkeypatch.setattr(window_module.QFileDialog, "getSaveFileName", staticmethod(answer))
    said: list[str] = []

    def choose(sheet: object) -> None:
        said.append(sheet.question.text())
        sheet.buttons["choose"].click()

    check = when_open(choose)
    assert window._choose_recovery_file() == "/somewhere/codes.txt"
    check()
    assert said[0].startswith("Keep this file somewhere private")
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    assert asked == [f"{documents}/flexweek-recovery-codes.txt"]
