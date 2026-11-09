"""What the sheet and dialog tests share: a window-sized parent dressed in a look, sample blocks, and a
way to act on a sheet while its exec() is running. (Moved out of test_dialogs_look.py and
test_ui_dialogs.py, which other test files still import these names from.)"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from desktop.native.look import pack_stylesheet, resolved_palette, sanitize_look
from desktop.native.widgets import ChooseTimeDialog, control_art
from desktop.tests.window_support import still

WEEK = "2026-09-21"

ESSAY = {"id": "e", "title": "Essay", "due": WEEK, "estimate_min": 60}
WAITING = {"id": "w", "title": "Essay", "duration_min": 60, "days": [1, 2]}

# How long when_open watches for a sheet: 1000 looks, 5 ms apart.
WATCH_LOOKS, WATCH_EVERY_MS = 1000, 5


def soccer(**fields: object) -> dict:
    return {
        "id": "soccer",
        "title": "Soccer practice",
        "kind": "locked",
        "category": "extra",
        "start": "16:00",
        "duration_min": 90,
        "days": [1, 3],
        **fields,
    }


def school(**fields: object) -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        **fields,
    }


def styled(qapp: QApplication, pack: str = "light-frost", text: str = "normal") -> tuple[QWidget, dict]:
    """A window-sized parent dressed in a look, at a text size, as the app's window is."""
    look = sanitize_look({"knobs": {"text": text}})
    palette = resolved_palette(pack, False, look, "default")
    made = QWidget()
    made.setStyleSheet(pack_stylesheet(pack, False, look, "default", palette, control_art(palette)))
    made.resize(1280, 800)
    made.show()
    qapp.processEvents()
    return made, palette


def shown(qapp: QApplication, dialog: QDialog) -> QDialog:
    dialog.show()
    for _ in range(4):
        qapp.processEvents()
    parent = dialog.parentWidget()
    still(dialog, *([parent.window()] if parent is not None else []))
    return dialog


def choose_time(parent: QWidget) -> ChooseTimeDialog:
    return ChooseTimeDialog(parent, WAITING, WEEK, [1, 2], [], None, 1)


def _dialog_classes() -> set[type]:
    import desktop.native.window  # noqa: F401 - brings in every module that defines a dialog

    found, waiting = set(), [QDialog]
    while waiting:
        for kind in waiting.pop().__subclasses__():
            waiting.append(kind)
            if kind.__module__.startswith("desktop.native."):
                found.add(kind)
    return found


def when_open(act: Callable[[QDialog], object]) -> Callable[[], None]:
    """Call `act` with the sheet that the next exec() opens, as soon as it is the active modal widget,
    and close the sheet if `act` left it open. exec() does not return until then, so a test cannot act
    on a sheet after the call that opens it. Returns a function to call once exec() has returned: it
    raises whatever `act` raised, outside Qt's event loop, where the test can report it. If no sheet
    opens in a few seconds the watch ends and that function raises, so a question that was never asked
    does not leave a timer running through the tests after it."""
    failed: list[BaseException] = []
    looks = 0

    def look() -> None:
        nonlocal looks
        sheet = QApplication.activeModalWidget()
        if sheet is None:
            looks += 1
            if looks > WATCH_LOOKS:
                failed.append(AssertionError("no sheet opened"))
            else:
                QTimer.singleShot(WATCH_EVERY_MS, look)
            return
        try:
            act(sheet)
        except BaseException as error:  # noqa: BLE001 - raised again by `check`, outside Qt's event loop
            failed.append(error)
        finally:
            if sheet.isVisible():
                sheet.reject()

    def check() -> None:
        if failed:
            raise failed[0]

    QTimer.singleShot(0, look)
    return check
