# ruff: noqa: F811
"""What the Material shell is told by the window: the theme map and the motion switch, the fonts it
registers, and which navigation it shows on a narrow window.

How the shell looks at each width is a picture (desktop/tests/pictures/_week_g11.py).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402


def test_reduce_motion_runs_the_page_change_in_no_time(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    root = show_material(qapp, material_window)
    bridge = material_window._material_page.bridge
    assert bridge.property("reduceMotion") is False
    assert int(root.property("enterMs")) == 300

    material_window._motion = "off"
    material_window._material_page.publish()
    pump(qapp)

    assert bridge.property("reduceMotion") is True
    assert int(root.property("enterMs")) == 0


def test_the_open_shell_publishes_the_theme_object(qapp: QApplication, material_window: NativeWindow) -> None:
    """The shell's theme map is the Slate light scheme plus the ink aliases and the three flags."""
    show_material(qapp, material_window)
    theme = material_window._material_page.bridge.property("theme")
    assert theme["primary"] == "#3d6fc4"
    assert theme["onSurface"] == "#0f172a"
    assert theme["inkSurface"] == "#0f172a"
    assert theme["inkMuted"] == "#475569"
    assert theme["inverseOnSurface"] == "#f0f0f7"
    assert theme["density"] == "comfortable"
    assert theme["reduceMotion"] is False
    assert theme["highContrast"] is False


def test_register_fonts_returns_the_three_inter_faces(qapp: QApplication) -> None:
    from PySide6.QtGui import QFontDatabase

    from desktop.native.material.theme import INTER, register_fonts

    ids = register_fonts()
    assert len(ids) == 3
    families: list[str] = []
    for ident in ids:
        assert ident >= 0
        families.extend(QFontDatabase.applicationFontFamilies(ident))
    assert INTER in families


def test_opening_material_registers_those_faces(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.material import host as host_mod

    seen: list[tuple[int, ...]] = []
    real = host_mod.register_fonts

    def wrapped() -> tuple[int, ...]:
        found = real()
        seen.append(found)
        return found

    monkeypatch.setattr(host_mod, "register_fonts", wrapped)
    page = material_window._ensure_material()
    assert page is not None
    page._ready = False

    show_material(qapp, material_window)

    assert seen
    assert len(seen[-1]) == 3
    assert all(ident >= 0 for ident in seen[-1])


def test_a_narrow_shell_uses_the_bar_instead_of_the_rail(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """Under 768 the rail is gone, Month sits in the top bar with Day, and the page change still runs
    in 300 ms."""
    root = show_material(qapp, material_window)
    material_window.setMinimumWidth(360)
    material_window.resize(700, 800)
    pump(qapp)
    try:
        assert int(root.property("width")) < 768
        assert root.findChild(QObject, "materialRail") is None
        assert qml(root, "materialBar").property("visible") is True
        assert qml(root, "navMonth").property("visible") is True
        assert qml(root, "navDay").property("visible") is True
        assert int(root.property("enterMs")) == 300
    finally:
        material_window.setMinimumWidth(WINDOW_MIN_WIDTH)
