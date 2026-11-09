"""The plan's notice and its review panel say the same sentence about what was placed, and the panel's
Got it is the tonal answer. Whether Got it is drawn loud is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.controller import plan_sentence
from desktop.native.widgets import PlanReview
from desktop.tests.sheets.support_dialogs import WEEK, styled
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-plan-review-test"])


def test_plan_sentence_and_the_panel_share_one_placed_wording() -> None:
    """The toast and the panel both say Placed, in the toast's sentence."""
    assert plan_sentence(2, 1) == "Placed 2 homework blocks. 1 with no time yet."
    assert plan_sentence(1, 0) == "Placed 1 homework block."
    assert plan_sentence(0, 1) == "Nothing placed. 1 with no time yet."


def test_got_it_is_tonal_and_the_panel_uses_the_toast_sentence(qapp: QApplication) -> None:
    host, _palette = styled(qapp)
    panel = PlanReview(host)
    panel.set_trace(
        {
            "placed": [{"id": "essay"}],
            "unplaced": [{"id": "poster", "title": "Poster"}],
            "moves": [],
            "explanations": [],
        },
        {"essay": "Essay", "poster": "Poster"},
        WEEK,
        (2, 1),
    )
    qapp.processEvents()
    assert panel.heading.text() == plan_sentence(2, 1)
    got = panel.findChild(QPushButton, "planReviewDismiss")
    assert got.property("tonal") is True
    free(panel)
    free(host)
