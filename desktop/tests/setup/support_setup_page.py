"""Setup opened inside the light window, as a new account sees it on its first run."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import monday_of
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.setup import STYLE, SetupPage, SetupState
from desktop.native.window import NativeWindow

SIZE = (1280, 800)


def show_setup(
    qapp: QApplication,
    window: NativeWindow,
    step: int = STYLE,
    *,
    size: tuple[int, int] = SIZE,
    pack: str = "light-frost",
    look: dict | None = None,
    layout: dict | None = None,
    preferences: dict | None = None,
    blocks: list[dict] | None = None,
    first_run: bool = True,
    motion: str = "off",
) -> SetupPage:
    """The window's setup page, filled from this state and open on `step`, with no animation unless
    `motion` says so."""
    window.resize(*size)
    window._close_settings(show_week=False)
    window._setup_active = True
    state = SetupState(
        pack,
        sanitize_look(look or {"preset": "default", "knobs": {}}),
        sanitize_layout(layout),
        preferences or {},
        blocks or [],
        monday_of(CLOCK.today().isoformat()),
    )
    state.first_run = first_run
    setup = window.setup_page
    setup.motion = motion
    setup.open(state, step)
    window._show_page("setupPage")
    qapp.processEvents()
    return setup
