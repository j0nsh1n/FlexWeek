"""Screens for the sheets area (chunk H9): the Material week's long homework title. A look the old
regression tests measured in code: it is judged on this picture."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.window_support import settled

MATERIAL = ("material",)


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


SCREENS: list[Screen] = [
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
]
