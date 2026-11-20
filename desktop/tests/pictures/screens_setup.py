"""Pictures of Material first-run setup (each step, simple and with the detailed controls) and of the
Advanced look page (each tier)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native import setup_steps
from desktop.native.material import theme
from desktop.native.window import NativeWindow
from desktop.tests.material_support import material_showing
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

SETUP_SOURCES = (
    "desktop/native/material/qml/setup",
    "desktop/native/material/bridge_account.py",
    "desktop/native/setup_steps.py",
)
LOOK_SOURCES = (
    "desktop/native/material/qml/settings",
    "desktop/native/material/bridge_settings.py",
    "desktop/native/material/theme.py",
)
THREE_STEP = hasattr(setup_steps, "MATERIAL_RAIL")


def _setup_at(step: int, power: bool = False):
    def prepare(window: NativeWindow) -> object:
        window.resize(1280, 800)
        window.show()
        window._run_setup_again()
        qapp = QApplication.instance()
        wait_until(
            qapp, lambda: material_showing(window), what="Material setup"
        )
        bridge = window._account_bridge()
        if power:
            bridge.setSchoolPreset("custom")
            bridge.setStudyPreset("custom")
            bridge.setSoundOpen(True)
        bridge._show(step)
        for _ in range(40):
            qapp.processEvents()
        return None

    return prepare


def _advanced(tier: str | None):
    def prepare(window: NativeWindow) -> object:
        from desktop.tests.sheets.support_material_settings import open_settings, panel

        qapp = QApplication.instance()
        open_settings(qapp, window, "look")
        panel(window).openAdvanced()
        if tier is not None:
            panel(window).setLookTier(tier)
        for _ in range(40):
            qapp.processEvents()
        return None

    return prepare


def _setup_screen(name: str, step: int, checks: str, power: bool = False, main: bool = False) -> Screen:
    return Screen(
        id=f"setup.m3_{name}",
        area="setup",
        prepare=_setup_at(step, power),
        checks=checks,
        sources=SETUP_SOURCES,
        main=main,
        styles=("material",),
    )


SCREENS: list[Screen] = []
if THREE_STEP:
    SCREENS += [
        _setup_screen(
            "school_hours",
            setup_steps.WEEK,
            "Step 1 of 3: four school-hours cards on the left, a week preview on the right that shows only "
            "the school block the student picked. Nothing invented. One column when narrow.",
            main=True,
        ),
        _setup_screen(
            "school_hours_power",
            setup_steps.WEEK,
            "Same step with the detailed controls opened by the 'Different times, sports, or a job' card: "
            "clock, week start, school days and times, sports and jobs, and the evening cutoff.",
            power=True,
        ),
        _setup_screen(
            "study_hours",
            setup_steps.HOMEWORK,
            "Step 2 of 3: three planning cards, four study-hours cards, and a preview that adds only the "
            "study hours picked.",
            main=True,
        ),
        _setup_screen(
            "study_hours_power",
            setup_steps.HOMEWORK,
            "Same step with the drag step and the per-day study windows shown.",
            power=True,
        ),
        _setup_screen(
            "look_alerts",
            setup_steps.REMINDERS,
            "Step 3 of 3: reminder cards, preset, light or dark, row size, and Open my week.",
            main=True,
        ),
        _setup_screen(
            "look_alerts_power",
            setup_steps.REMINDERS,
            "Same step with the alarm sound, Spotify link and test reminder shown.",
            power=True,
        ),
    ]
else:
    SCREENS += [
        _setup_screen("old_week", setup_steps.WEEK, "Your week page.", main=True),
        _setup_screen("old_homework", setup_steps.HOMEWORK, "Homework time page.", main=True),
        _setup_screen("old_reminders", setup_steps.REMINDERS, "Reminders and alarm page.", main=True),
        _setup_screen("old_first", setup_steps.FIRST, "First homework page.", main=True),
        _setup_screen("old_done", setup_steps.DONE, "Done page.", main=True),
    ]

if hasattr(theme, "read_look_tier"):
    LOOK = (
        ("simple", "Simple tier: preset, mode, corners, block style, row size and text size."),
        ("more", "More tier: the layout and grid dials added under the simple ones."),
        ("all", "All tier: the colour codes and the readability check added."),
    )
    SCREENS += [
        Screen(
            id=f"settings.m3_look_{tier}",
            area="settings",
            prepare=_advanced(tier),
            checks=checks,
            sources=LOOK_SOURCES,
            styles=("material",),
        )
        for tier, checks in LOOK
    ]
else:
    SCREENS.append(
        Screen(
            id="settings.m3_look_old_advanced",
            area="settings",
            prepare=_advanced(None),
            checks="The Advanced settings page as it was.",
            sources=LOOK_SOURCES,
            styles=("material",),
        )
    )
