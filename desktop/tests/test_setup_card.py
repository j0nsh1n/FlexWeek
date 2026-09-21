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


def test_the_card_is_opaque_so_the_week_does_not_show_through_it(qapp: QApplication) -> None:
    """It is positioned over the calendar rather than placed in a layout. A QWidget honours a
    stylesheet background but a subclass of one does not unless it is told to, so the card came up
    transparent and the day headings and hour lines were drawn through its own text."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QWidget

    from desktop.native.look import pack_stylesheet, resolved_palette

    page = QWidget()
    page.resize(700, 500)
    page.setStyleSheet(pack_stylesheet("light-frost", False, None, "default"))
    card = SetupCard(page)
    card.setFixedWidth(420)
    card.move(20, 20)
    card.show()
    page.show()
    qapp.processEvents()
    card.adjustSize()
    qapp.processEvents()
    # Something loud behind it: if any of it survives inside the card, the card is see-through.
    behind = QWidget(page)
    behind.setGeometry(card.geometry())
    behind.setStyleSheet("background: #ff00ff;")
    behind.lower()
    qapp.processEvents()
    image = page.grab().toImage()
    panel = QColor(resolved_palette("light-frost", False, None, "default")["panel"])
    middle = image.pixelColor(card.x() + card.width() // 2, card.y() + card.height() // 2)
    assert middle != QColor("#ff00ff"), "the week shows through the first-week card"
    assert middle == panel, f"the card is not painted on its own panel: {middle.name()}"
    page.close()
