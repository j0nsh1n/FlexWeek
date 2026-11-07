"""Screens of the style feel (Retro's windows, Bento's hero, Night owl's paper, and Plain as the baseline) on
Settings, the Add homework sheet and Setup. These are the looks the code tests of the feel used to
measure: title bars and their contrast, titles at Large text, caption buttons, bevels and card depth."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.layouts import retro
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.setup import STYLE as SETUP_STEP
from desktop.native.widgets import HomeworkDialog
from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/feel.py",
    "desktop/native/layouts/retro.py",
    "desktop/native/settings.py",
    "desktop/native/setup.py",
    "desktop/native/tokens.py",
)

# The main view each feel belongs to (feel.feel_for).
FEELS = (
    ("plain", "classic", "Plain"),
    ("night_owl", "timeline", "Night owl"),
    ("dashboard", "bento", "Bento"),
    ("retro", "retro", "Retro"),
)

# What every title picture checks; Large text comes from the edge set, which every feel screen is in.
TITLE_CHECKS = (
    "the page's title is whole at 800 and 1280 pixels wide (its words fit the label, neither cut off nor "
    "wrapped past the label's height) at Large text"
)
SCROLL_CHECK = (
    "at Large text the page scrolls no more than the Plain feel's does (Retro's frame and Setup's style "
    "picker may make Settings and Add homework scroll)"
)


def _wear(window, main: str) -> None:  # noqa: ANN001
    window._layout = sanitize_layout({"main": main, "day": "one"})
    window._apply_appearance()


def _settings(main: str) -> Callable[..., object]:
    def prepare(window):  # noqa: ANN001, ANN202
        _wear(window, main)
        window._open_settings()
        return window._settings

    return prepare


def _sheet(main: str) -> Callable[..., object]:
    def prepare(window):  # noqa: ANN001, ANN202
        _wear(window, main)
        dialog = HomeworkDialog(window, today=CLOCK.today().isoformat())
        dialog.show()
        return dialog

    return prepare


def _setup(main: str) -> Callable[..., object]:
    def prepare(window):  # noqa: ANN001, ANN202
        _wear(window, main)
        window._open_setup(SETUP_STEP, first_run=True)
        return window.setup_page

    return prepare


def _bevel_swatch(window) -> QWidget:  # noqa: ANN001
    """Retro's sunken bevel on a white field, enlarged so its edge pixels can be seen."""
    colours = retro.Scheme(
        face="#c0c0c0", light="#dfdfdf", hi="#ffffff", shadow="#808080", dark="#0a0a0a",
        field="#ffffff", ink="#000000", tip="#ffffe1", folder="#f3d36b", rule="#e3e3e3",
        desk="#008080", desk_ink="#ffffff", title="#000080", title_end="#0000ff",
        title_ink="#ffffff", accent="#008080", danger="#ff0000",
    )
    image = QImage(12, 12, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    retro.bevel(painter, QRect(1, 1, 10, 10), colours, "sunken", "#ffffff", "#333333")
    painter.end()
    label = QLabel(window)
    label.setPixmap(QPixmap.fromImage(image.scaled(96, 96)))
    label.resize(96, 96)
    label.show()
    return label


SCREENS: list[Screen] = []

for key, main, name in FEELS:
    extra = {
        "plain": "the baseline the other feels' scrolling is compared with",
        "night_owl": "cards wear the paper edge and the titles the serif face",
        "dashboard": (
            "the title sits on the hero bar and its text is at least 4.5 to 1 against the bar's fill in "
            "the light and the dark pack; cards have the small shadow (0 offset across, 1 down, 3 blur) "
            "in the Bento corner radius"
        ),
        "retro": (
            "the title bar runs the full width of the page less the 8 pixel frame (page width - 8); its "
            "words are at least 4.5 to 1 against the bar in the light and the dark pack; the caption "
            "buttons lie wholly inside the bar and are at least their size hint at Normal and Large "
            "text; the bevels are not drawn over the footer; cards have no shadow and square corners"
        ),
    }[key]
    SCREENS.append(
        Screen(
            id=f"settings.feel_{key}_settings",
            area="settings",
            prepare=_settings(main),
            checks=f"Settings in the {name} feel: {extra}; {TITLE_CHECKS}; {SCROLL_CHECK}",
            sources=SOURCES,
            main=True,
        )
    )
    if key == "plain":
        continue
    SCREENS.append(
        Screen(
            id=f"settings.feel_{key}_sheet",
            area="settings",
            prepare=_sheet(main),
            checks=(
                f"The Add homework sheet in the {name} feel: the sheet's title is whole at Large text "
                "(not cut off) and the sheet scrolls no more than Plain's does at Large text; "
                + (
                    "the caption buttons lie wholly inside the title bar, which runs the card's width less 8"
                    if key == "retro"
                    else "the card has this feel's depth and corner radius"
                )
            ),
            sources=SOURCES + ("desktop/native/widgets.py",),
            main=True,
        )
    )
    SCREENS.append(
        Screen(
            id=f"settings.feel_{key}_setup",
            area="settings",
            prepare=_setup(main),
            checks=(
                f"Setup's style page in the {name} feel: the setup title is whole at 800 and 1280 pixels "
                "wide at Large text, and the page scrolls no more than Plain's (Setup's style picker may "
                "make it scroll in Retro)"
            ),
            sources=SOURCES,
            main=True,
        )
    )

SCREENS.append(
    Screen(
        id="settings.feel_retro_bevel_edges",
        area="settings",
        prepare=_bevel_swatch,
        checks=(
            "A Retro sunken bevel drawn on a white field: its right and bottom edge lines are at least "
            "3 to 1 against the white field, so they do not vanish where the highlight would be white"
        ),
        sources=("desktop/native/layouts/retro.py",),
    )
)
