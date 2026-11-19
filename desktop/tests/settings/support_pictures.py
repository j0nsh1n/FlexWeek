"""What the settings pictures do to a light window before it is photographed. Nothing here asserts: a
picture is judged by the reviewer from the checks its screen lists."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QVBoxLayout,
    QWidget,
)

from desktop.native.look import resolved_palette, sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.settings.support_tokens import LOOKS
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still


def pump(done: Callable[[], bool]) -> None:
    """Wait for `done`, and go on when it does not come: a picture of a screen that did not finish is
    still a picture the reviewer can judge."""
    try:
        wait_until(None, done, timeout=5.0)
    except AssertionError:
        return


def wear(window: NativeWindow, name: str) -> None:
    """Dress the window in one of the ten looks of support_tokens.LOOKS, as a student's choice does."""
    pack, _dark, chosen = LOOKS[name]
    look = sanitize_look(chosen or {"preset": "default", "knobs": {}})
    window._look = look
    window.session.look = look
    if window.session.preferences is not None:
        window.session.preferences = {**window.session.preferences, "theme_pack": pack}
    window._apply_appearance()
    still(window)


def palette_of(window: NativeWindow) -> dict:
    pack, system_dark, accent = window._look_inputs()
    return resolved_palette(pack, system_dark, window._worn_look(), accent)








def dropdown_list(window: NativeWindow) -> QWidget:
    """A dropdown with its list open and the third choice chosen."""
    sample = QFrame(window)
    sample.setObjectName("dropdownSample")
    column = QVBoxLayout(sample)
    combo = QComboBox()
    combo.addItems(["Calendar · Today's app", "Agenda · Timeline", "Dashboard · Bento"])
    combo.setCurrentIndex(2)
    column.addWidget(combo)
    sample.setGeometry(20, 20, 320, 80)
    sample.raise_()
    sample.show()
    combo.showPopup()
    pump(lambda: combo.view().isVisible())
    return combo.view()
