"""Every choice control in Settings works from the keyboard: Tab lands on the chosen segment, Right/Left
change the value, End picks the last, Home the first, and the keyboard follows the chosen segment. Segments
are accessible radio buttons that say where they are in the group. No mouse event is used."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import Segmented
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_keys import press, tab_into
from desktop.tests.window_support import qapp  # noqa: F401

# (section of Settings, objectName)
CONTROLS = [
    (0, "prefThemeMain"), (0, "lookSurface"), (0, "lookCorners"), (0, "lookDepth"), (0, "lookFont"),
    (0, "lookBlocks"), (0, "lookDensity"), (0, "lookText"), (0, "prefMotion"),
    (1, "prefDragStep"), (4, "prefPreferredView"), (4, "prefClock"),
]


def segmented_in_settings(qapp, window, section: int, name: str) -> Segmented:
    window._open_settings()
    page = window._settings
    page.fine_tune.setChecked(True)
    page.nav.setCurrentRow(section)
    qapp.processEvents()
    found = page.findChild(Segmented, name)
    assert found is not None and found.isVisible(), f"{name} not shown in section {section}"
    return found


@pytest.mark.parametrize(("section", "name"), CONTROLS, ids=[name for _s, name in CONTROLS])
def test_a_choice_control_works_from_the_keyboard(qapp, window, section, name) -> None:
    box = segmented_in_settings(qapp, window, section, name)
    chosen = box.currentIndex()
    landed = tab_into(box)
    assert landed is box.buttons()[chosen], f"Tab landed on {landed and landed.objectName()}, chosen {chosen}"
    step = Qt.Key.Key_Right if chosen < box.count() - 1 else Qt.Key.Key_Left
    press(box, step)
    assert box.currentIndex() != chosen, "Right/Left did not change the value"
    press(box, Qt.Key.Key_End)
    assert box.currentIndex() == box.count() - 1, "End did not pick the last"
    press(box, Qt.Key.Key_Home)
    assert box.currentIndex() == 0, "Home did not pick the first"
    assert QApplication.focusWidget() is box.buttons()[0], "focus did not follow the chosen segment"


def test_segments_are_accessible_radio_buttons_with_their_position(qapp, window) -> None:
    box = segmented_in_settings(qapp, window, 0, "lookSurface")
    chosen = box.currentIndex()
    for index, button in enumerate(box.buttons()):
        interface = QAccessible.queryAccessibleInterface(button)
        assert interface is not None
        assert interface.role() == QAccessible.Role.RadioButton
        assert bool(interface.state().checked) is (index == chosen)
        assert interface.text(QAccessible.Text.Name) == box.itemText(index)
        assert interface.text(QAccessible.Text.Description) == f"{index + 1} of {box.count()}"
