"""The wrapping row the bar's actions, the waiting chips and Settings' buttons sit in: it wraps onto more rows
instead of demanding the width."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.widgets import FlowLayout


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-flow-layout"])


def test_a_flow_layout_wraps_instead_of_demanding_the_width(qapp: QApplication) -> None:
    host = QWidget()
    flow = FlowLayout(host)
    buttons = [QPushButton(f"Action number {index}") for index in range(20)]
    for button in buttons:
        flow.addWidget(button)
    widest = max(button.sizeHint().width() for button in buttons)
    margins = flow.contentsMargins()
    assert flow.minimumSize().width() == widest + margins.left() + margins.right()
    assert flow.heightForWidth(400) > flow.heightForWidth(4000), "a narrow row must wrap onto more rows"
    flow.setGeometry(QRect(0, 0, 400, flow.heightForWidth(400)))
    for button in buttons:
        assert button.geometry().right() <= 400, f"{button.text()} overflows the row"
    assert len({button.geometry().top() for button in buttons}) > 1
