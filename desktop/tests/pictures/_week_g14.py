"""Week screens for the window chrome: the top bar, its buttons and scroll bars, the view switcher, the
window's size, the not-placed chips and the Material rows at larger text. These are the look checks the
window-chrome tests used to make in code (test_top_bar, test_window_screens, test_window_layout,
test_r11_view_group, test_tray_chip, test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from desktop.native.hours.chips import TrayChip
from desktop.native.hours.hand import Hand
from desktop.native.hours.rail import PAD, RAIL_PX, RailChip
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.weekmodel import Waiting
from desktop.native.widgets import SegmentTrack
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
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


def _retro_bar(window: NativeWindow) -> None:
    # Motion off: the switch between designs fades through a held picture, which a picture would catch.
    window.session.preferences = {**(window.session.preferences or {}), "motion": "off"}
    window._layout = sanitize_layout({"main": "retro", "day": "one"})
    window._apply_appearance()
    window.resize(1280, 800)
    show_view(window, "week")
    window._on_week()
    idle(window)
    pump(5)
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


def _suggest_times_and_retry(window: NativeWindow) -> None:
    show_view(window, "week")
    window.session.preferences = {**(window.session.preferences or {}), "planning_style": "manual"}
    window.retry_button.setVisible(True)
    window._sync_chrome()
    text_size(window, "large")
    window.resize(640, 768)
    pump()
    return None


def _while_the_week_saves(window: NativeWindow) -> None:
    """A save on its way, a reply landing on the week: Retry save must not show and the view buttons must
    stay where they are."""
    show_view(window, "month")
    wait_until(None, lambda: window.session.month_data is not None and not window.session.busy)
    window.session.client.hold()
    window.session.dirty = True
    window.session.save()
    window.session.week_changed.emit()
    window._week_page.layout().activate()
    pump()
    return None


def _hours_scroll_bar(window: NativeWindow) -> QWidget:
    window.resize(1280, 800)
    show_view(window, "week")
    return window.week_table.scroll


def _hours_scroll_bar_under_the_pointer(window: NativeWindow) -> QWidget:
    area = _hours_scroll_bar(window)
    QApplication.sendEvent(area.verticalScrollBar(), QEvent(QEvent.Type.Enter))
    pump()
    return area


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


def _view_switcher(window: NativeWindow) -> QWidget:
    window.resize(1280, 860)
    show_view(window, "week")
    return window.findChild(SegmentTrack, "segments")


def _not_placed_chips(window: NativeWindow) -> QWidget:
    """A tray chip made wider than its words at 11 pt and then given 16 pt, and a rail chip at the rail's
    width with 16 pt: the large title must give way before the length does."""
    host = QWidget()
    host.setObjectName("notPlacedChips")
    host.setStyleSheet("QPushButton { font-size: 11pt; padding: 4px 8px; }")
    waiting = Waiting("poster", "Science poster for the fair", "assignments", 90, "poster", None, "")
    tray = TrayChip(Hand(lambda *_args: None, host), waiting, host)
    rail = RailChip(Hand(lambda *_args: None, host), waiting, host)
    rail.setMaximumWidth(RAIL_PX - 2 * PAD)
    column = QVBoxLayout(host)
    column.addWidget(tray)
    column.addWidget(rail)
    host.show()
    pump()
    tray.setFixedWidth(tray.sizeHint().width())
    pump()
    host.setStyleSheet("QPushButton { font-size: 16pt; padding: 4px 8px; }")
    pump()
    return host


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
        id="week.top_bar_retro",
        area="week",
        prepare=_retro_bar,
        checks=(
            "While Retro is the week's layout the bar strip wears the title bar's colour and Add is raised "
            "on its light end, whatever look is worn; another layout leaves the frost bar alone."
        ),
        sources=BAR_SOURCES + ("desktop/native/layouts/retro.py", "desktop/native/feel.py"),
        styles=("retro",),
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
        id="week.top_bar_suggest_and_retry",
        area="week",
        prepare=_suggest_times_and_retry,
        checks=(
            "At 640 px with Large text, Suggest times (or Suggest) and Retry save, which widen the bar, "
            "are never cut and nothing runs past the window's edge."
        ),
        sources=BAR_SOURCES,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.top_bar_while_saving",
        area="week",
        prepare=_while_the_week_saves,
        checks=(
            "A save is on its way and the week is drawn again by a reply: Retry save is not showing and "
            "the Day / Week / Month / My day buttons are where they are when no save is running (they "
            "once jumped 129 px left under the pointer)."
        ),
        sources=BAR_SOURCES,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.hours_scroll_bar",
        area="week",
        prepare=_hours_scroll_bar,
        checks=(
            "The hours' scroll bar lies over their right edge, thin (at most 6 px), not in a strip beside "
            "them."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/hours"),
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.hours_scroll_bar_under_the_pointer",
        area="week",
        prepare=_hours_scroll_bar_under_the_pointer,
        checks="With the pointer on it the hours' scroll bar is wider than at rest and still over the hours.",
        sources=("desktop/native/widgets.py", "desktop/native/hours"),
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
        id="week.view_switcher_labels",
        area="week",
        prepare=_view_switcher,
        checks=(
            "At Small, Normal and Large text, in every design and look preset, each of Day / Week / Month "
            "/ My day shows its whole label inside its button (not clipped) in both the regular and the "
            "strong weight, each button is at least 24x24 px, and at Large text all four have equal "
            "padding around their words."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py", "desktop/native/window.py"),
        main=True,
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="week.not_placed_chips",
        area="week",
        prepare=_not_placed_chips,
        checks=(
            "A Not placed yet chip given larger words after it was sized keeps all of them inside: the "
            "title gives way with an ellipsis and the length '1 h 30 min' stays whole. A rail chip at the "
            "rail's width wraps its title inside the rail and nothing is drawn past the rail's edge."
        ),
        sources=(
            "desktop/native/hours/chips.py",
            "desktop/native/hours/rail.py",
            "desktop/native/widgets.py",
        ),
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
