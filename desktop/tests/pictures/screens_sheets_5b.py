"""Pictures of Material 3 Manage account and Restore points (1.5.0 step 5b)."""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/sheets",
    "desktop/native/material/bridge_manage.py",
    "desktop/native/material/bridge_sheets.py",
    "desktop/native/settings_copy.py",
    "desktop/native/account_copy.py",
    "desktop/native/material/theme.py",
    "desktop/native/material/tokens.json",
)
POINTS = [
    {"id": "a", "label": "Before term 2", "created_at": "2026-11-10 18:02", "weeks": 4},
    {"id": "b", "label": "Before restore — 2026-11-12 09:30", "created_at": "2026-11-12 09:30", "weeks": 5},
    {"id": "c", "label": "Weekend plan", "created_at": "2026-11-14 20:15", "weeks": 5},
]
STORAGE = {"mode": "local", "username": "student", "label": "This computer, in the FlexWeek folder"}


def _material(window: NativeWindow):
    from desktop.tests.settings.support_material_settings import _pump, _show_material

    qapp = QApplication.instance()
    _show_material(qapp, window)
    _pump(qapp, 10)
    window.session.storage_info = STORAGE
    return window._material_page.bridge.sheets, qapp


def _account(window: NativeWindow, *, asking: bool = False) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    window.session.recovery_remaining = 7
    sheets.openAccount()
    _pump(qapp, 30)
    if asking:
        sheets.accountAct("delete", "typed-password", "")
        _pump(qapp, 30)
        # The Quick view draws on a timer: a second layer that appears after the first has drawn needs
        # real time, not only processed events, or the picture is taken before it is painted.
        QTest.qWait(200)
    return None


def _restore(window: NativeWindow, *, asking: bool = False) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    sheets, qapp = _material(window)
    window.session.restore_points = list(POINTS)
    window.session.restore_preview = {
        "id": "c",
        "changes": {"weeks": {"changed": ["2026-11-09"]}, "assignments": {"added": ["x", "y"]}},
    }
    sheets.openRestore()
    _pump(qapp, 30)
    if asking:
        sheets.restoreSelected()
        _pump(qapp, 30)
        QTest.qWait(200)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="sheets.m3_account",
        area="sheets",
        prepare=_account,
        checks=(
            "Manage account: who is signed in, the two password fields in dots with Show, Replace password, "
            "recovery codes left, the five file buttons, Delete account apart from them, Close."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_account_delete",
        area="sheets",
        prepare=lambda window: _account(window, asking=True),
        checks="Delete account over Manage account: the whole question, Cancel first, then Delete student.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_restore",
        area="sheets",
        prepare=_restore,
        checks=(
            "Restore points: where copies are kept, a name box and Save restore point, three copies with "
            "times and weeks, the chosen one ticked, what going back would change, Preview, Close, Restore."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_restore_question",
        area="sheets",
        prepare=lambda window: _restore(window, asking=True),
        checks="Restore over Restore points: Not now first, then Restore, and a copy is saved first.",
        sources=SOURCES,
        styles=("material",),
    ),
]
