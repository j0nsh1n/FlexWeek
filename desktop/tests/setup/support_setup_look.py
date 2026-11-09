"""Setup in Light on a host of its own, with the window's stylesheet: the fixtures other setup tests
import from the old test_setup_look.py."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator

import pytest

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QWidget

    from desktop.native.calendar import monday_of
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import pack_stylesheet, resolved_palette
    from desktop.native.setup import SetupPage, SetupState
    from desktop.native.widgets import control_art


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-setup-look-test"])


@pytest.fixture()
def dressed(qapp: QApplication) -> Iterator[tuple[SetupPage, dict]]:
    """Setup in Light, with the window's stylesheet, as a new account sees it."""
    palette = resolved_palette("light-frost", False, None)
    host = QWidget()
    host.setStyleSheet(pack_stylesheet("light-frost", False, None, "default", palette, control_art(palette)))
    setup = SetupPage(host)
    setup.motion = "off"
    setup.set_palette(palette)
    look = {"preset": "default", "knobs": {}}
    setup.open(SetupState("light-frost", look, sanitize_layout(None), {}, [], monday_of("2026-09-23")))
    host.resize(1600, 800)
    setup.resize(1600, 800)
    host.show()
    qapp.processEvents()
    yield setup, palette
    host.close()
    host.deleteLater()
    qapp.processEvents()
