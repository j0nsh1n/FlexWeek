"""The homework editor refuses what the server would refuse, in words beside the field: a length under 15
minutes or over 24 hours, and each other field in its own sentence."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.sheets.support_plan import opened_with, settled, window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def typed(box: QWidget, text: str) -> None:
    box.setFocus()
    box.selectAll()
    QTest.keyClicks(box, text)


def test_a_length_under_15_minutes_or_over_24_hours_is_refused_beside_the_box(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    said: list[tuple[str, int, bool, bool]] = []

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        dialog.title.setText("Science poster")
        hint = dialog.estimate_hint

        def saved_as(text: str) -> None:
            typed(dialog.estimate, text)
            dialog.accept()
            problem = bool(hint.property("problem"))
            said.append((hint.text(), dialog.estimate.value(), problem, dialog.isVisible()))

        saved_as("0")
        saved_as("1500")
        typed(dialog.estimate, "1440")
        QTest.keyClick(dialog.estimate, Qt.Key.Key_Up)
        said.append(("cap", dialog.estimate.value(), False, False))
        saved_as("90")
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._add_homework()
    settled(qapp, window)
    zero, long, cap, fine = said
    assert zero == ("Give it at least 15 minutes.", 0, True, True), "0 is kept as typed and refused in words"
    assert long[1:] == (1500, True, True) and "Split it into parts" in long[0]
    assert cap[1] == 1440, "the arrows stop at 24 hours"
    assert fine[2:] == (False, False), "a length in range saves"
    saved = next(item for item in window.session.assignments.values() if item["title"] == "Science poster")
    assert saved["estimate_min"] == 90


@pytest.mark.parametrize(
    ("field", "value", "said"),
    [
        ("title", "", "Give the homework a title."),
        ("title", "x" * 81, "Keep the homework title under 80 characters."),
        ("notes", "x" * 4001, "Keep notes under 4,000 characters."),
        ("link", "not-a-link", "A link needs an http:// or https:// address."),
        ("checklist", "x" * 81, "Keep each checklist step under 80 characters."),
        ("due", "yesterday", "Choose a valid due date."),
    ],
)
def test_homework_editor_refuses_each_field_in_its_own_words(
    qapp: QApplication,  # noqa: F811
    field: str,
    value: str,
    said: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = HomeworkDialog(today="2026-09-24")
    try:
        dialog.show()
        dialog.title.setText("Science poster")
        if field == "title":
            if len(value) > 80:
                dialog.title.setMaxLength(len(value))
            dialog.title.setText(value)
        elif field == "notes":
            dialog.notes.setPlainText(value)
        elif field == "link":
            dialog.link_label.setText("Class notes")
            dialog.link_url.setText(value)
            dialog.findChild(QPushButton, "addHomeworkLink").click()
        elif field == "checklist":
            dialog._append_check("step", value, False)
        else:
            # On the class: undone on the instance, the patch left the dialog's own bound method in its
            # dict, a cycle the collector later freed in another test.
            monkeypatch.setattr(HomeworkDialog, "_chosen_due", lambda _dialog: value)
        dialog.accept()
        assert dialog.isVisible(), "invalid homework stays open"
        error = dialog.title_problem if field == "title" else dialog.error
        assert error.text() == said
        assert "Value error" not in error.text()
    finally:
        dialog.close()
