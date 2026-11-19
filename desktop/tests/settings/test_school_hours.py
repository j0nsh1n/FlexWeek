"""School hours asks what setup asks, days and times, and saves School as any block is saved."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QWidget,
)

from desktop.native.widgets import SchoolHoursDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window as signed_in  # noqa: F401
from desktop.tests.window_support import host, qapp, settled  # noqa: F401


@pytest.fixture()
def window(qapp: QApplication, signed_in: NativeWindow) -> Iterator[NativeWindow]:
    """Setup skipped, so there is no School yet."""
    signed_in.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, signed_in)
    yield signed_in


def answer(monkeypatch: pytest.MonkeyPatch, change: Callable[[SchoolHoursDialog], None] | None) -> list[dict]:
    """School hours as the student sees it, then Save after `change`, or Cancel with none."""
    seen: list[dict] = []

    def run(dialog: SchoolHoursDialog) -> int:
        seen.append(
            {
                "heading": [label.text() for label in dialog.findChildren(QLabel)][0],
                "days": dialog.days.days(),
                "times": (dialog.times.start.hhmm(), dialog.times.end.hhmm()),
            }
        )
        if change is None:
            dialog.reject()
        else:
            change(dialog)
            dialog.accept()
        return dialog.result()

    monkeypatch.setattr(SchoolHoursDialog, "exec", run)
    return seen


def schools(window: NativeWindow) -> list[tuple]:
    return [
        (block["id"], block["kind"], block["title"], block["days"], block["start"], block["duration_min"])
        for block in window.session.blocks
        if block.get("category") == "class"
    ]


def read_back(qapp: QApplication, window: NativeWindow) -> list[tuple]:
    """The week as the server has it, not as the window last drew it."""
    window.session.blocks = []
    window.session.reload()
    settled(qapp, window)
    return schools(window)








def test_an_end_before_the_start_is_said_and_nothing_is_saved(qapp: QApplication, host: QWidget) -> None:
    dialog = SchoolHoursDialog(host, None)
    dialog.times.end.set_minutes(7 * 60)
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.error.text() == "End needs to be later than Start (08:00)."
    assert dialog.block() is None
    buttons = dialog.findChild(QDialogButtonBox)
    save = buttons.button(QDialogButtonBox.StandardButton.Save)
    # Save is the default button, so Enter saves; that it is the filled one and Cancel the quiet one is
    # the picture settings.school_hours_dialog.
    assert save.isDefault()


def test_no_school_days_is_said_only_when_no_day_is_picked(qapp: QApplication, host: QWidget) -> None:
    """Audit X7: the hint showed under a week of school days, where it read as a warning."""
    dialog = SchoolHoursDialog(host, None)
    dialog.show()
    hint = next(label for label in dialog.findChildren(QLabel) if label.text().startswith("No school days"))
    assert dialog.days.days() and not hint.isVisible()
    for day in list(dialog.days.days()):
        dialog.days.buttons[day].click()
    assert hint.isVisible()
    dialog.days.buttons[2].click()
    assert not hint.isVisible()
    dialog.close()
