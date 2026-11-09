"""The row of look swatches under the Style page's carousel: each design lists its own looks, and a pick
is kept. That the preview redraws is judged in the picture review."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop.native.layouts.registry import DESIGN_LOOKS
from desktop.native.setup import STYLE, STYLES, SetupPage
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def style_page(qapp: QApplication, window: NativeWindow) -> SetupPage:
    return show_setup(qapp, window, STYLE)


def test_every_style_lists_its_designs_looks_and_the_first_is_picked(style_page: SetupPage) -> None:
    setup = style_page
    carousel = setup.carousel
    swatches = list(carousel.look_swatches.values())
    assert list(carousel.look_swatches) == [token for token, _name in DESIGN_LOOKS["classic"]]
    assert swatches[0].isChecked()
    assert all(button.isVisibleTo(setup) for button in swatches)
    assert all(button.focusPolicy() & Qt.FocusPolicy.TabFocus for button in swatches)
    for style in STYLES:
        carousel.go_to(style.key)
        assert list(carousel.look_swatches) == [token for token, _name in DESIGN_LOOKS[style.main]]


def test_picking_a_look_is_kept_and_comes_back_kept(
    qapp: QApplication,
    style_page: SetupPage,
) -> None:
    setup = style_page
    carousel = setup.carousel
    choice = carousel.look_swatches["preset:high-contrast"]
    assert choice.property("lookToken") == "preset:high-contrast"
    assert choice.accessibleName() == "High contrast"
    assert choice.toolTip() == "High contrast"
    choice.click()
    qapp.processEvents()
    assert choice.isChecked()
    assert setup._layout["options"]["classic"]["look"] == "preset:high-contrast"

    # Another design shows its own looks with its signature picked; coming back keeps this setup's pick.
    carousel.go_to("dashboard")
    assert carousel.key() == "dashboard"
    bento = list(carousel.look_swatches.values())
    assert bento[0].isChecked() and bento[0].property("lookToken") == DESIGN_LOOKS["bento"][0][0]
    assert setup._layout["options"]["bento"]["look"] == DESIGN_LOOKS["bento"][0][0]
    carousel.go_to("plain")
    assert carousel.look_swatches["preset:high-contrast"].isChecked()
