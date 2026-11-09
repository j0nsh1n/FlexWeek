"""Helpers for tests of the Add fixed time sheet: the steps that take it to its second and third
question."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.widgets import BlockDialog


def go_when(dialog: BlockDialog) -> None:
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("Club")
    dialog._save.click()
    QApplication.processEvents()


def go_length(dialog: BlockDialog) -> None:
    go_when(dialog)
    if dialog._add_step is None or dialog._add_step >= 2:
        return
    dialog._save.click()
    QApplication.processEvents()
