# ruff: noqa: F811
"""A toast never takes the pointer: clicks go through it to the page under it. (That it sits at the
bottom right is the picture sheets.toast_corner.)"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from desktop.native.widgets import Toast  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-toast-clicks-test"])


def test_toast_pointer_events_pass_through_it(qapp: QApplication) -> None:
    """W5: the toast and its card are transparent for mouse events."""
    parent = QWidget()
    parent.resize(1280, 800)
    over = QWidget(parent)
    over.setGeometry(0, 0, 1280, 800)
    toast = Toast(parent, over)
    toast.show_message("Test message", "Undo")
    toast.reposition()
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert toast.card.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    parent.close()
