"""First-week setup is three skippable steps, not a blocked wizard."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication, QPushButton

    from desktop.native.settings import SetupCard


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-setup-test"])
    yield application


def test_skipping_sport_still_keeps_school(qapp: QApplication) -> None:
    card = SetupCard()
    found: list[dict] = []
    card.finished.connect(found.append)
    card.findChild(QPushButton, "setupNext").click()
    card.findChild(QPushButton, "setupSkip").click()
    card.findChild(QPushButton, "setupNext").click()
    assert found
    assert "school" in found[0]
    assert "sport" not in found[0]
    assert "homework" in found[0]
