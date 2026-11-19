"""Week screens for the window chrome: the top bar, its buttons and scroll bars, the view switcher, the
window's size, the not-placed chips and the Material rows at larger text. These are the look checks the
window-chrome tests used to make in code (test_top_bar, test_window_screens, test_window_layout,
test_r11_view_group, test_tray_chip, test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_bar_pictures import (
    WIDGETS_DESIGNS,
    idle,
    pump,
    show_view,
    text_size,
)

BAR_SOURCES = ("desktop/native/window.py", "desktop/native/widgets.py", "desktop/native/look.py")


def _top_bar(window: NativeWindow) -> None:
    window.resize(1280, 800)
    show_view(window, "week")
    pump()
    return None


class _HoverButton(QPushButton):
    """Draws itself as the style does with the pointer on it, since a pointer cannot be put on one."""

    def paintEvent(self, event: object) -> None:  # noqa: N802
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state |= QStyle.StateFlag.State_MouseOver
        painter = QPainter(self)
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)
        painter.end()


def _button_states(window: NativeWindow) -> QWidget:
    """Add, Preview and More (rows) at rest, hovered, pressed, off and reached by the keyboard (columns),
    on the window's own look."""
    host = QWidget(window)
    host.setObjectName("buttonStates")
    grid = QGridLayout(host)
    focused: list[QPushButton] = []
    for row, (words, kind) in enumerate((("Add", None), ("Preview", "secondary"), ("More", "quiet"))):
        for column in range(5):
            button = (_HoverButton if column == 1 else QPushButton)(words)
            if kind:
                button.setProperty(kind, True)
            if column == 2:
                button.setDown(True)
            if column == 3:
                button.setEnabled(False)
            if column == 4:
                button.setProperty("keyfocus", True)
                focused.append(button)
            grid.addWidget(button, row, column)
    host.adjustSize()
    host.move(24, 24)
    host.show()
    host.raise_()
    pump()
    for button in focused:
        button.setFocus(Qt.FocusReason.TabFocusReason)
    pump()
    return host


def _narrowest_bar(window: NativeWindow) -> None:
    show_view(window, "week")
    window.resize(800, 768)
    pump()
    return None


def _bar_at_1150(window: NativeWindow) -> None:
    show_view(window, "week")
    window.resize(1150, 768)
    pump()
    return None


def _large_text_bar_just_wide_enough(window: NativeWindow) -> None:
    # A week whose title is short, which is where a bar left unfitted showed on two rows.
    window.session.load_week("2026-10-05")
    idle(window)
    show_view(window, "week")
    window.resize(1195, 768)
    pump()
    text_size(window, "large")
    pump()
    return None










def _laptop_window(window: NativeWindow) -> None:
    window.resize(1366, 768)
    show_view(window, "week")
    pump()
    return None


def _calendar_room(window: NativeWindow) -> None:
    window.resize(1280, 820)
    show_view(window, "week")
    pump()
    return None






def _material_week_rows(window: NativeWindow) -> None:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("week")
    pump_material(QApplication.instance(), 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="week.top_bar",
        area="week",
        prepare=_top_bar,
        checks=(
            "Order, left to right: the arrows and Today, then the date title, then the Day / Week / Month / "
            "My day switcher, then Add, Plan and More and the gear; the arrows and Today do not move "
            "sideways between Day, Week and Month, and the title keeps at least 16 px from the switcher "
            "(was 6 px). The four view buttons sit level with Today (within 2 px), not 32 px below it. "
            "The week title's chevron is no wider than an icon button. Icons (arrows, gear, Add's arrow, "
            "the zoom's minus and plus) are drawn, in the words' colour on the page and the accent's ink "
            "on Add, and follow the look in light and dark. Add and its arrow are one pill split by a "
            "line of Add's ink, never two buttons 2 px apart. Plan is accent words with no fill and More "
            "is in the text colour; Add is the only filled action. The chosen view is raised: the card "
            "colour on a track of 6 % of the text colour with a small shadow (Dark keeps a visible edge; "
            "High contrast keeps its outlined track, a yellow choice and no shadow). The zoom is a "
            "24 px pill of two icon buttons with a line between, quiet at rest. No status strip sits "
            "under the bar and the planner starts under 32 px below it. The page keeps the style's "
            "layout margins on all four sides. At 1024x640 with Large text every control (Add, its "
            "arrow, Plan, More, the gear) is whole and inside the window."
        ),
        sources=BAR_SOURCES + ("desktop/native/icons.py", "desktop/native/hours/zoom.py"),
        main=True,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.button_states",
        area="week",
        prepare=_button_states,
        checks=(
            "Columns are rest, hover, pressed, off and reached by the keyboard. Hover is 6 % of the text "
            "colour over the button's fill and pressed 10 %; a quiet button shows its press. A filled "
            "button that is off is a pale tint of the text colour with readable words, a tinted one at "
            "40 %. The key-reached button has a 2 px ring at 40 % of the accent; the others have none. "
            "The zoom's minus and plus follow the quiet kind: nothing behind them at rest, 6 % on hover, "
            "10 % pressed."
        ),
        sources=BAR_SOURCES,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.top_bar_narrow",
        area="week",
        prepare=_narrowest_bar,
        checks=(
            "At the window's narrowest (800 px) the date title is its whole long or short form, never "
            "cut short; every button on the bar is as wide as its words; Plan reads Plan my homework, "
            "Plan homework or Plan; the bar wraps to a second row instead of squeezing; and nothing on "
            "it runs past the window's right edge. The window cannot be made narrower than the bar's "
            "buttons at their smallest."
        ),
        sources=BAR_SOURCES + ("desktop/native/reuse.py",),
        main=True,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.top_bar_1150",
        area="week",
        prepare=_bar_at_1150,
        checks=(
            "At 1150 px with Normal text the bar is one row (Plan sits above the foot of the title) and "
            "no button on it is cut."
        ),
        sources=BAR_SOURCES,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.top_bar_large_text_one_row",
        area="week",
        prepare=_large_text_bar_just_wide_enough,
        checks=(
            "At 1195 px with Large text just arrived, the bar is one row (Plan sits above the foot of "
            "the title) and does not go to two rows later: Large text refits Plan, More and the view "
            "buttons at once, not on a later refit. The title keeps at least 16 px from the switcher, "
            "also at High contrast."
        ),
        sources=BAR_SOURCES,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.laptop_window",
        area="week",
        prepare=_laptop_window,
        checks=(
            "On a 1366x768 laptop screen the Week page fits: the window does not ask for more than 1366 "
            "px of width or 768 px of height, and a 1280x760 window keeps exactly that size."
        ),
        sources=("desktop/native/window.py", "desktop/native/hours"),
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.calendar_room",
        area="week",
        prepare=_calendar_room,
        checks="In a 1280x820 window the calendar is at least half of the window's height (410 px).",
        sources=("desktop/native/window.py", "desktop/native/hours"),
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.material_larger_text_rows",
        area="week",
        prepare=_material_week_rows,
        checks=(
            "Material's Week at Normal text has 56 px hour rows; at Larger text they are at least 1.5 "
            "times that (84 px), and the rows' text is not clipped."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
