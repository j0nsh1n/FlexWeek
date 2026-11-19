"""Pictures from the views lane's group G06: the focus strip, Material's focus screen, and the keyboard
rings of the top bar and Manage account. The lead gathers this fragment into screens_focus.py (and routes
the `week.` and `sheets.` ids to their areas).

Each one is what an old pixel, position or style-property test read back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.look import sanitize_look
from desktop.tests.material_support import pump, show_material
from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow

MATERIAL_SOURCES = ("desktop/native/material", "desktop/native/window.py")
BAR_SOURCES = ("desktop/native/widgets.py", "desktop/native/window.py", "desktop/native/look.py")




def _material_focus(running: bool, paused: bool = False):
    def prepare(window: NativeWindow) -> object:
        app = QApplication.instance()
        show_material(app, window)
        window._open_focus_screen()
        pump(app)
        focus = window._material_page.bridge.focus
        if running:
            focus.begin()
            pump(app)
        if paused:
            focus.togglePause()
            pump(app)
        return None

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="focus.material_ready",
        area="focus",
        prepare=_material_focus(running=False),
        checks=(
            "Material's Focus screen before Start. Exactly one filled button is visible: Start. Pause, "
            "Skip and Finish are not shown."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="focus.material_running",
        area="focus",
        prepare=_material_focus(running=True),
        checks=(
            "Material's Focus screen with a timer running. Exactly one filled button is visible: Pause. "
            "Skip and Finish are not filled. Pause, Skip and Finish keep the same left edge and width "
            "when the timer is paused (compare focus.material_paused)."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="focus.material_paused",
        area="focus",
        prepare=_material_focus(running=True, paused=True),
        checks=(
            "Material's Focus screen paused: the first button reads Resume and is still the one filled "
            "button, never two filled at once. Pause or Resume, Skip and Finish are at the same left "
            "edge with the same width as in focus.material_running."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
]


def _bar_ring(preset: str, name: str):
    """The top bar with the keyboard on one of its buttons, worn in this look preset."""

    def prepare(window: NativeWindow) -> object:
        window._look = sanitize_look({"preset": preset})
        window._apply_appearance()
        button = window.findChild(QAbstractButton, name)
        if button is not None:
            button.clearFocus()
            button.setFocus(Qt.FocusReason.TabFocusReason)
        return None

    return prepare


_RING_CHECKS = (
    "A top bar button reached with the keyboard (here {which}) wears a ring {width} in the accent, with a "
    "2 px gap of the page's own colour between the button and the ring: the 2 px next to the button are "
    "the page colour, the next 2 px (4 to 2 px outside the button) are the ring, and the ring is {where}. "
    "The ring's rectangle is 4 px larger than the button on every side. {contrast}"
)

SCREENS += [
    Screen(
        id="week.top_bar_ring_default",
        area="week",
        prepare=_bar_ring("default", "prevWeek"),
        checks=_RING_CHECKS.format(
            which="the previous-week arrow",
            width="2 px wide",
            where="the accent itself (#3d6fc4 in Light, #7fa8ff in Dark)",
            contrast="The accent reads at least 3:1 on the page. Every other bar button (Next week, Today, "
            "Add, its arrow, Plan, More, the settings gear) gets the same ring.",
        ),
        sources=BAR_SOURCES,
    ),
    Screen(
        id="week.top_bar_ring_paper",
        area="week",
        prepare=_bar_ring("paper", "prevWeek"),
        checks=_RING_CHECKS.format(
            which="the previous-week arrow in the Paper look",
            width="2 px wide",
            where="#1f3a68",
            contrast="It reads at least 3:1 on the page.",
        ),
        sources=BAR_SOURCES,
    ),
    Screen(
        id="week.top_bar_ring_ink",
        area="week",
        prepare=_bar_ring("ink", "prevWeek"),
        checks=_RING_CHECKS.format(
            which="the previous-week arrow in the Ink look",
            width="2 px wide",
            where="#7fa8ff",
            contrast="It reads at least 3:1 on the page.",
        ),
        sources=BAR_SOURCES,
    ),
    Screen(
        id="week.top_bar_ring_high_contrast",
        area="week",
        prepare=_bar_ring("high-contrast", "prevWeek"),
        checks=_RING_CHECKS.format(
            which="the previous-week arrow in the High contrast look",
            width="2 px wide",
            where="the look's yellow accent",
            contrast="The yellow reads at least 3:1 on the page.",
        ),
        sources=BAR_SOURCES,
    ),
    Screen(
        id="week.top_bar_ring_plan_button",
        area="week",
        prepare=_bar_ring("default", "solveButton"),
        checks=_RING_CHECKS.format(
            which="the Plan button",
            width="2 px wide",
            where="the accent itself",
            contrast="A button with words gets the same ring as the arrows.",
        ),
        sources=BAR_SOURCES,
    ),
    Screen(
        id="week.top_bar_ring_view_control",
        area="week",
        prepare=_bar_ring("default", "viewWeek"),
        checks=_RING_CHECKS.format(
            which="the Week segment of the view control",
            width="2 px wide",
            where="the accent itself",
            contrast="Inside the view control's own track the 2 px gap is the track's colour, not the "
            "page's.",
        ),
        sources=BAR_SOURCES,
    ),
]
