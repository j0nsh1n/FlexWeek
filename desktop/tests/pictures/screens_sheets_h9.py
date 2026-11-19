"""Screens for the sheets area (chunk H9): button labels in every sheet and the week, the Material week's
long homework title, and the week list opened from the keyboard. Looks the old regression
tests measured in code: they are judged on these pictures."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.layout_choice import LAYOUTS
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_button_labels import LATE_WORDS, sheet_makers
from desktop.tests.window_support import settled

# Widgets designs only: the screens below build Widgets sheets and pages.
WIDGETS = tuple(spec.id for spec in LAYOUTS.values() if spec.role == "plan")
MATERIAL = ("material",)

BUTTON_RULE = (
    "No button has its label cut off or squeezed: the words (and icon) fit inside the box the style "
    "leaves for them, with the stylesheet's padding, in every design and look at Small, Normal and "
    "Large text. Every button with words, except steps, segments, pills, chips, small buttons and "
    "the view buttons, is at least 40 px wider than its words (20 px each side) and at least 36 px "
    "tall (40 px at Large text)."
)

WEEK_WINDOW_CHECKS = (
    BUTTON_RULE
    + " In Retro the shortcut buttons (retroIcon1) and in Bento the day names for Saturday and "
    "Sunday keep their words at 1280 px and at 1024 px wide, at Normal and at Large text."
)


def week_window(window: NativeWindow) -> None:
    return None


def sheet(name: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        qapp = QApplication.instance()
        dialog = sheet_makers(window)[name]()
        dialog.show()
        qapp.processEvents()
        settled(qapp, window)
        return dialog

    return prepare


def running_late_after_preview(window: NativeWindow) -> object:
    qapp = QApplication.instance()
    from desktop.native.widgets import LateDialog

    dialog = LateDialog(window, LATE_WORDS)
    dialog.show()
    qapp.processEvents()
    dialog.show_trace({"moves": [], "unplaced": []}, {})
    dialog.findChild(QPushButton, "latePreview").setVisible(False)
    dialog.accept_button.setVisible(True)
    qapp.processEvents()
    return dialog


def running_late_after_text_size_changes(window: NativeWindow) -> object:
    """Running late open, then the text size changed Large, Small, Large: Qt kept each button's first size."""
    qapp = QApplication.instance()
    from desktop.native.widgets import LateDialog

    dialog = LateDialog(window, LATE_WORDS)
    dialog.show()
    qapp.processEvents()
    for size in ("large", "small", "large"):
        look = dict(window._look)
        window._look = {**look, "knobs": {**look.get("knobs", {}), "text": size}}
        window.session.look = window._look
        window._apply_appearance()
        qapp.processEvents()
    return dialog


def long_homework_title(window: NativeWindow) -> None:
    # Imported here: it needs the views lane's Material helpers, which a screens module need not load.
    from desktop.tests.sheets.support_material_sheets import material_week

    qapp = QApplication.instance()
    material_week(qapp, window)
    window.session.add_homework({**window.session.assignments["essay"], "title": "W" * 40})
    window.session.save()
    settled(qapp, window)
    from desktop.tests.material_support import pump

    pump(qapp)


def week_with_school(window: NativeWindow) -> None:
    qapp = QApplication.instance()
    window.session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:30",
            "duration_min": 405,
            "days": [0, 1, 2, 3, 4],
        }
    )
    settled(qapp, window)


def week_list_closed(window: NativeWindow) -> None:
    week_with_school(window)




SCREENS: list[Screen] = [
    Screen(
        id="sheets.buttons_week_window",
        area="sheets",
        prepare=week_window,
        checks=WEEK_WINDOW_CHECKS,
        sources=("desktop/native/window.py", "desktop/native/look.py"),
        main=True,
    ),
    *(
        Screen(
            id=f"sheets.buttons_{name.replace('-', '_')}",
            area="sheets",
            prepare=sheet(name),
            checks=BUTTON_RULE,
            sources=("desktop/native/widgets.py", "desktop/native/look.py"),
            styles=WIDGETS,
        )
        for name in (
            "add-homework",
            "block-editor",
            "school-hours",
            "choose-a-time",
            "routines",
            "running-late",
            "study-hours",
        )
    ),
    Screen(
        id="sheets.running_late_after_preview",
        area="sheets",
        prepare=running_late_after_preview,
        checks=(
            "After Preview, Accept late start and Cancel share one row: neither is squeezed (each is "
            "at least as "
            "wide as its natural width), they do not overlap, and Cancel ends inside the sheet. The "
            "sheet keeps "
            "its width at Large text, and the longest label, 'Accept late start', is not cut off in "
            "Retro's pixel "
            "font at Large text (the old 'ccept late sta')."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        styles=WIDGETS,
    ),
    Screen(
        id="sheets.running_late_after_text_size_changes",
        area="sheets",
        prepare=running_late_after_text_size_changes,
        checks=(
            "With Running late open, the text size is changed Large, Small, Large: Preview and "
            "Cancel measure "
            "again, and each label is not cut off (the sheet's buttons do not keep their first size)."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        styles=WIDGETS,
    ),
    Screen(
        id="sheets.material_week_long_homework_title",
        area="sheets",
        prepare=long_homework_title,
        checks=(
            "A homework block whose title is 40 capital W letters: the title ends to the left of the round "
            "finish tick and never runs under it."
        ),
        sources=("desktop/native/material",),
        styles=MATERIAL,
    ),
    Screen(
        id="week.week_list_closed",
        area="week",
        prepare=week_list_closed,
        checks=(
            "The week list is hidden and takes no room: with the grid shown, note the top edge of "
            "the grid, to "
            "compare with week.week_list_open."
        ),
        sources=("desktop/native/window.py", "desktop/native/hours"),
        styles=("classic",),
    ),
]
