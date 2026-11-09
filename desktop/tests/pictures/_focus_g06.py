"""Pictures from the views lane's group G06: the focus screen's buttons, ring and look, the end-session
sheet, Material's focus screen, and the keyboard rings of the top bar and Manage account. The lead gathers
this fragment into screens_focus.py (and routes the `week.` and `sheets.` ids to their areas).

Each one is what an old pixel, position or style-property test read back."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from desktop.native.look import sanitize_look
from desktop.native.settings import AccountDialog
from desktop.native.widgets import ConfirmSheet
from desktop.tests.material_support import pump, show_material
from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow

SCREEN_SOURCES = (
    "desktop/native/focus_screen.py",
    "desktop/native/ring.py",
    "desktop/native/look.py",
    "desktop/native/window.py",
)
MATERIAL_SOURCES = ("desktop/native/material", "desktop/native/window.py")
BAR_SOURCES = ("desktop/native/widgets.py", "desktop/native/window.py", "desktop/native/look.py")


def _widgets_focus_screen(window: NativeWindow) -> object:
    """The focus timer opened ready, as the Quick focus button does. The Widgets focus screen is
    returned; Material draws its own timer, so for it the whole window is photographed (None)."""
    window._open_focus_screen()
    screen = window.focus_screen
    return screen if window._stack.currentWidget() is screen else None


def _ready(window: NativeWindow) -> object:
    return _widgets_focus_screen(window)


def _running(window: NativeWindow) -> object:
    _widgets_focus_screen(window)
    window._start_quick_focus()
    screen = window.focus_screen
    return screen if window._stack.currentWidget() is screen else None


def _paused(window: NativeWindow) -> object:
    _running(window)
    window.session.toggle_focus_pause()
    screen = window.focus_screen
    return screen if window._stack.currentWidget() is screen else None


def _end_session_sheet(window: NativeWindow) -> object:
    if _running(window) is None:
        return None
    # Shown beside the window instead of waiting for an answer, so it can be photographed.
    with mock.patch.object(ConfirmSheet, "exec", lambda sheet: (sheet.show(), 0)[1]):
        window._stop_focus()
    return window.findChild(ConfirmSheet)


def _strip_running(window: NativeWindow) -> object:
    window.session.start_quick_focus()
    return window.focus_panel


def _look(pack: str, preset: str):
    """The focus screen ready, worn in this pack and look preset."""

    def prepare(window: NativeWindow) -> object:
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": pack}
        window._look = sanitize_look({"preset": preset})
        window._apply_appearance()
        return _widgets_focus_screen(window)

    return prepare


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


_BUTTONS_STILL = (
    "Pause and Resume, Skip and Finish keep the same left edge and the same width when the timer is "
    "paused and resumed (compare this picture with focus.{other}). "
)

SCREENS: list[Screen] = [
    Screen(
        id="focus.screen_ready",
        area="focus",
        prepare=_ready,
        checks=(
            "The focus screen before Start. Back is words with a left chevron (not an outlined button) "
            "at the top left. Start is the one filled button under the ring. Every button, shown or not, "
            "reserves the same height, at least the tallest one's own, so the row does not change height "
            "when Pause, Skip and Finish take Start's place. The task label (Quick focus) inside the ring "
            "and the ring itself are in the same place as in focus.screen_running (compare the two "
            "pictures): pressing Start moves neither."
        ),
        sources=SCREEN_SOURCES,
    ),
    Screen(
        id="focus.screen_running",
        area="focus",
        prepare=_running,
        checks=(
            "A timer running on the focus screen. Pause is the one filled button; Skip and Finish are "
            "outlined with words, not filled. Back is words with a left chevron. The three buttons are "
            "in one row, centred on one line, in the order Pause, Skip, Finish from left to right, "
            "and all of them sit below the ring's bottom edge. The task label and the ring are where "
            "they were in focus.screen_ready. " + _BUTTONS_STILL.format(other="screen_paused")
        ),
        sources=SCREEN_SOURCES,
        main=True,
    ),
    Screen(
        id="focus.screen_paused",
        area="focus",
        prepare=_paused,
        checks=(
            "The same screen paused: the phase reads Focus, Paused and the first button reads Resume, "
            "still the one filled button. " + _BUTTONS_STILL.format(other="screen_running")
        ),
        sources=SCREEN_SOURCES,
    ),
    Screen(
        id="focus.end_session_sheet",
        area="focus",
        prepare=_end_session_sheet,
        checks=(
            "The sheet Finish opens, headed End this session?: Keep going is an outlined button (the "
            "safe answer) and End session is the filled one. The question reads the minutes done."
        ),
        sources=SCREEN_SOURCES,
    ),
    Screen(
        id="focus.strip_running",
        area="focus",
        prepare=_strip_running,
        checks=(
            "The strip over the week with a timer running is one line: the task, the time and a Focus "
            "screen button. The Focus screen button is outlined, not filled and not quiet."
        ),
        sources=("desktop/native/settings.py", "desktop/native/look.py"),
    ),
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

_LOOK_CHECKS = (
    "The focus timer set but not started, worn in {look}. The ring is painted in the look's accent "
    "(the arc is drawn in it, not only told it) and the arc reads at least 3:1 against the window "
    "colour. The screen's background is the look's window colour and the Back chevron follows its text "
    "colour."
)
_LOOKS = {
    "pack_system": ("system", "default", "the System pack"),
    "pack_dark_frost": ("dark-frost", "default", "the Dark pack"),
    "pack_nocturne": ("nocturne", "default", "the Nocturne pack"),
    "pack_slate": ("slate", "default", "the Slate pack"),
    "preset_high_contrast": ("light-frost", "high-contrast", "the High contrast look"),
    "preset_paper": ("light-frost", "paper", "the Paper look"),
    "preset_ink": ("light-frost", "ink", "the Ink look"),
    "preset_terminal": ("light-frost", "terminal", "the Terminal look"),
    "preset_poster": ("light-frost", "poster", "the Poster look"),
    "preset_pastel": ("light-frost", "pastel", "the Pastel look"),
}
SCREENS += [
    Screen(
        id=f"focus.ring_before_start_{name}",
        area="focus",
        prepare=_look(pack, preset),
        checks=_LOOK_CHECKS.format(look=words),
        sources=SCREEN_SOURCES,
    )
    for name, (pack, preset, words) in _LOOKS.items()
]


def _manage_account(window: NativeWindow) -> object:
    # Shown instead of waiting for an answer, so it can be photographed; the keyboard is put on
    # Delete account as Tab would.
    with mock.patch.object(AccountDialog, "exec", lambda dialog: (dialog.show(), 0)[1]):
        window._open_account()
    dialog = window.findChild(AccountDialog)
    if dialog is not None:
        button = dialog.findChild(QPushButton, "deleteAccount")
        if button is not None:
            button.setFocus(Qt.FocusReason.TabFocusReason)
    return dialog


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
    Screen(
        id="sheets.manage_account_keyboard_ring",
        area="sheets",
        prepare=_manage_account,
        checks=(
            "The Manage account sheet with the keyboard on Delete account. Delete account is a danger "
            "button drawn outlined (a red outline, not a red fill) and wears the keyboard focus ring "
            "of a danger outlined button; Close is an outlined button that wears the same kind of ring "
            "when it has the keyboard. The sheet wears the window's design colours."
        ),
        sources=("desktop/native/settings.py", "desktop/native/look.py", "desktop/native/widgets.py"),
    ),
]
