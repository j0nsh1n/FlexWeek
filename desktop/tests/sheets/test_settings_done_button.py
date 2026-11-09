# ruff: noqa: F811
"""Settings closes with one Done button, not OK and Cancel."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton  # noqa: E402

from desktop.tests.sheets.support_settings import prefs_dialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-settings-done-test"])


def test_settings_has_one_done_button_and_no_ok_or_cancel(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    assert dialog.findChildren(QDialogButtonBox) == []
    # Segments and day pills are choices shown, and a number's − and + are part of its field.
    kinds = ("quiet", "segment", "pill", "step", "outline")
    filled = [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if not any(button.property(kind) for kind in kinds)
    ]
    assert filled == ["Done"]
    closed: list[bool] = []
    dialog.closed.connect(lambda: closed.append(True))
    dialog.done.click()
    assert closed == [True]
