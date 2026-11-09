"""The length hint of Add and Edit homework speaks only when the length is wrong: a value that is not a
multiple of 15 shows it in the error colour, picking a good one takes it away, and a wrong one cannot be
saved."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.tests.sheets.support_homework import go_length, host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_the_multiple_of_15_hint_shows_only_for_a_value_that_is_wrong(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    go_length(dialog)
    hint = dialog.estimate_hint
    assert not hint.isVisible(), "60 is fine: nothing to say"
    dialog.estimate.setValue(50)
    dialog.estimate.editingFinished.emit()
    assert hint.isVisible()
    assert hint.property("problem") is True, "in the error colour"
    dialog.stepper.chips[3].click()  # 60
    assert dialog.estimate.value() == 60
    assert not hint.isVisible(), "choosing 60 takes it away"
    free(dialog)
    free(parent)


def test_an_off_grid_length_cannot_be_saved(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("Essay")
    go_length(dialog)
    dialog.estimate.setValue(50)
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.estimate_hint.isVisible()
    free(dialog)
    free(parent)
