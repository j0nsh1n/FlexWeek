"""The Unfinished panel on the Widgets week: every overdue row has a Plan here and a Delete button,
and Plan here is the tonal one. How tall the buttons are and when the list scrolls are looks:
pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.widgets import UnfinishedPanel
from desktop.tests.sheets.support_dialogs import styled
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-unfinished-panel-test"])


def test_plan_here_is_the_tonal_answer_and_delete_the_outlined_one_on_every_row(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    panel = UnfinishedPanel(parent)
    panel.move(20, 20)
    panel.resize(900, 600)
    panel.set_items(
        [
            {"id": f"a{n}", "title": f"History essay {n}", "remaining_min": 60, "due": "2000-01-15T12:00"}
            for n in range(2)
        ]
    )
    for _ in range(6):
        qapp.processEvents()
    answers = ("planUnfinished", "deleteUnfinished")
    buttons = [b for b in panel.findChildren(QPushButton) if b.objectName().split("-")[0] in answers]
    assert len(buttons) == 4
    plan = panel.findChild(QPushButton, "planUnfinished-a0")
    delete = panel.findChild(QPushButton, "deleteUnfinished-a0")
    assert plan.property("tonal") and not plan.property("outlined")
    assert delete.property("outlined") and not delete.property("quiet")
    free(parent)
