# ruff: noqa: F811
"""Settings > Layout: Material 3 sits beside the six Widgets designs, and choosing a design leaves it."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-style-picker"])
    yield application


def test_material_sits_with_the_designs_and_a_design_leaves_it(qapp: QApplication) -> None:
    page = SettingsPage(None, {}, {}, {}, None)
    page.resize(900, 700)
    page.show()
    pump(qapp)
    names = [
        "Today's app",
        "Timeline",
        "Mission control",
        "Bento",
        "Retro desktop",
        "Clay deck",
    ]
    main = page.findChild(QWidget, "layoutMain")
    assert [main.itemText(index) for index in range(main.count())] == names
    button = page.findChild(QPushButton, "chooseMaterial")
    assert button is not None and button.text() == "Material 3"
    section = page.layout_sections[0]
    assert section.surface() == "widgets"
    assert section.chosen() == "classic"
    heard: list[str] = []
    section.changed.connect(lambda: heard.append("changed"))

    section.show_surface("material")

    assert heard == []
    assert button.isChecked() is True
    assert section.surface() == "material"
    assert section.chosen() == "classic"
    look = page.findChild(QWidget, "layoutMain-look")
    assert look.isVisible() is False

    section.pick.cards[section.pick.currentIndex()].chosen.emit()
    pump(qapp)
    assert section.surface() == "widgets"
    assert heard == ["changed"]
    look = page.findChild(QWidget, "layoutMain-look")
    assert look.isVisible() is True

    section.show_surface("material")
    timeline = next(card for card in section.pick.cards if card.accessibleName() == "Timeline")
    timeline.chosen.emit()
    assert section.chosen() == "timeline"
    assert section.surface() == "widgets"
    assert page.layout_sections[1].surface() == "widgets"
    page.hide()
