"""Pictures of the Material 3 week and shell: what the old size, position and colour checks of the
Material window tests looked at. (A fragment: the lead gathers these into screens_week.py.)"""

from __future__ import annotations

from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/week",
    "desktop/native/material/qml/Main.qml",
    "desktop/native/material/bridge_week.py",
    "desktop/native/material/theme.py",
)


def _material_week(window: object) -> None:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.day.support_material_window import seed_week
    from desktop.tests.material_support import show_material

    qapp = QApplication.instance()
    seed_week(qapp, window)
    show_material(qapp, window)


def _school_block_and_drawer(window: object) -> None:
    _material_week(window)
    return None


def _now_line_at_eight(window: object) -> None:
    from PySide6.QtWidgets import QApplication

    from backend.tests.fake_clock import CLOCK, START
    from desktop.tests.material_support import pump

    _material_week(window)
    CLOCK.set(START.replace(hour=20, minute=0))
    window._layout_tick.timeout.emit()
    pump(QApplication.instance())
    return None


def _category_blocks(window: object) -> None:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.day.support_material_window import settle
    from desktop.tests.material_support import pump

    qapp = QApplication.instance()
    _material_week(window)
    session = window.session
    for block_id, title, category, start in (
        ("soccer", "Soccer", "exercise", "16:00"),
        ("clubs", "Chess club", "extra", "15:00"),
        ("reading", "Reading", "study", "17:30"),
    ):
        session.add_block(
            {
                "id": block_id,
                "title": title,
                "kind": "locked",
                "category": category,
                "start": start,
                "duration_min": 60,
                "days": [0, 1, 2, 3, 4],
            }
        )
    session.save()
    settle(qapp, window)
    window._material_page.bridge.refresh()
    pump(qapp)
    return None


def _narrow_shell(window: object) -> None:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.material_support import pump

    _material_week(window)
    window.setMinimumWidth(360)
    window.resize(700, 800)
    pump(QApplication.instance())
    return None


SCREENS: list[Screen] = [
    Screen(
        id="week.material_school_block_and_drawer",
        area="week",
        prepare=_school_block_and_drawer,
        checks=(
            "The navigation rail is 80 px wide. The Add button is a 56 x 56 button. "
            "School starts at 8:00, so its block top is 8 hour rows x 56 px = 448 px below the top of the "
            "hours; it is filled #e4ebf7 (light) with a 6 px corner radius, and its title wraps to at most "
            "two lines. The homework drawer is 320 px wide and sits against the right edge of the week."
        ),
        sources=SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="week.material_now_line_at_eight_pm",
        area="week",
        prepare=_now_line_at_eight,
        checks=(
            "With the clock at 20:00 the now line sits 20 hour rows x 56 px = 1120 px below the top of the "
            "hours, and the clock in the shell reads 8:00 PM (or 20:00 in 24 hour words)."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_category_blocks",
        area="week",
        prepare=_category_blocks,
        checks=(
            "Each category block is filled with the spec colour (light / dark): School #e4ebf7 / #1e2c44, "
            "Soccer #e1f0e9 / #1a352e, Chess club #ddefef / #133336, Reading #f6e7ec / #3e2633, "
            "History essay (homework) #f3ecde / #382e1a. The title and time on every fill are readable "
            "(text contrast at least 4.5:1) in both light and dark."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_narrow_shell",
        area="week",
        prepare=_narrow_shell,
        checks=(
            "At 700 px wide (under 768) the rail is gone and an 80 px bar carries the destinations, with "
            "Month in the top bar. The Add button is 56 x 56, 16 px in from the right edge and 96 px up from "
            "the bottom. The week keeps 96 px of scroll clearance below its last hour so the Add button "
            "never covers a block, and the homework drawer is as wide as the week."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
]
