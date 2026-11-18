"""Pictures of Material 3 Help, About, Update and the Sign out question (1.5.0 step 5a)."""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import SIGN_OUT_QUESTION, NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/sheets",
    "desktop/native/material/bridge_info.py",
    "desktop/native/material/bridge_sheets.py",
    "desktop/native/settings_copy.py",
    "desktop/native/material/theme.py",
    "desktop/native/material/tokens.json",
)
UPDATE = {
    "version": "1.5.0",
    "notes": "## What changed\n- Material 3 is the one look.\n- Help, About and Update are Material sheets.\n"
    "- Faster week.\n- Fewer pop-ups.",
}


def _show(milliseconds: int = 200) -> None:
    """Real time for the Quick view's render timer: a second layer that appears after the first (the
    download's bar and problem line) is otherwise grabbed before it is drawn, most often in dark."""
    QTest.qWait(milliseconds)


def _material(window: NativeWindow):
    from desktop.tests.settings.support_material_settings import _pump, _show_material

    qapp = QApplication.instance()
    _show_material(qapp, window)
    _pump(qapp, 10)
    return window._material_page.bridge.sheets, qapp


def _help(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    sheets.openHelp()
    _pump(qapp, 30)
    _show()
    return None


def _about(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    window.session.storage_info = {"mode": "local"}
    sheets.openAbout()
    _pump(qapp, 30)
    _show()
    return None


def _update(window: NativeWindow, *, state: str) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    # The real download would go to the network; the picture only needs the sheet's own state.
    window._updater.download = lambda _update: None
    window._update_asked = True
    window._on_update_found(UPDATE)
    _pump(qapp, 30)
    if state == "downloading":
        sheets.updateInstall()
        window._on_update_progress(40, 100)
        _pump(qapp, 20)
        _show()
    if state == "problem":
        window._on_update_problem("The download stopped. Check your connection and try again.")
        _pump(qapp, 20)
        _show()

    return None


def _sign_out(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    window.session.storage_info = {"mode": "local"}
    window._log_out()
    _pump(qapp, 30)
    assert SIGN_OUT_QUESTION
    return None


def _more(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    sheets.openMore()
    _pump(qapp, 30)
    _show()
    return None


SCREENS: list[Screen] = [
    Screen(
        id="sheets.m3_more",
        area="sheets",
        prepare=_more,
        checks="The More menu: Replan all my homework and Reload this week have different icons.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_help",
        area="sheets",
        prepare=_help,
        checks=(
            "Help as a Material sheet: How planning works, four screen cards, then Keyboard shortcuts "
            "with keycaps; Close at the bottom."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_about",
        area="sheets",
        prepare=_about,
        checks="About: logo, version, what FlexWeek is, where the week is saved, Open folder, Close.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_update",
        area="sheets",
        prepare=lambda window: _update(window, state="ready"),
        checks="Update: FlexWeek 1.5.0 is ready, what changed, Skip this version, Not now, Update now.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_update_downloading",
        area="sheets",
        prepare=lambda window: _update(window, state="downloading"),
        checks="Update while downloading: Downloading..., a progress bar at 40 percent, Update now off.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_update_problem",
        area="sheets",
        prepare=lambda window: _update(window, state="problem"),
        checks="Update after a failed download: the problem in the error colour, Update now on again.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_sign_out",
        area="sheets",
        prepare=_sign_out,
        checks="The Sign out question: Cancel and Sign out, the same words as the Widgets question.",
        sources=SOURCES,
        styles=("material",),
    ),
]
