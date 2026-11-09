"""More details on Add and Edit homework: the toggle names what it will do, Notes has a label, and the
empty links and steps lists say so in one grey line and give way to entries."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.tests.sheets.support_homework import essay, host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_the_toggle_names_what_it_will_do(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    toggle = dialog.more_details
    assert toggle.text() == "More details"
    toggle.click()
    assert toggle.text() == "Fewer details"
    toggle.click()
    assert toggle.text() == "More details"
    free(dialog)
    free(parent)


def test_notes_has_a_label(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    dialog.more_details.click()
    found = dialog._details.findChildren(QLabel)
    labels = [label.text() for label in found if label.objectName() == "fieldLabel"]
    assert "Notes" in labels
    free(dialog)
    free(parent)


def test_empty_lists_say_so_in_one_grey_line_and_give_way_to_entries(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    dialog.more_details.click()
    none_links, none_steps = dialog.no_links, dialog.no_steps
    assert none_links.text() == "No links yet" and none_steps.text() == "No steps yet"
    assert none_links.isVisible() and none_steps.isVisible()
    assert not dialog.links.isVisible() and not dialog.checks.isVisible()
    dialog.link_label.setText("Notes")
    dialog.link_url.setText("https://example.org/notes")
    dialog.findChild(QPushButton, "addHomeworkLink").click()
    dialog.check_text.setText("Read chapter 4")
    dialog.findChild(QPushButton, "addHomeworkCheck").click()
    assert dialog.links.isVisible() and dialog.checks.isVisible()
    assert not none_links.isVisible() and not none_steps.isVisible()
    free(dialog)
    free(parent)


def test_homework_with_entries_opens_with_the_lists_not_the_grey_lines(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(
        parent,
        essay(
            links=[{"label": "Sources", "url": "https://example.org/a"}],
            checklist=[{"id": "c1", "text": "Outline", "done": False}],
        ),
    )
    assert dialog.links.isVisible() and dialog.checks.isVisible()
    assert not dialog.no_links.isVisible()
    assert not dialog.no_steps.isVisible()
    free(dialog)
    free(parent)
