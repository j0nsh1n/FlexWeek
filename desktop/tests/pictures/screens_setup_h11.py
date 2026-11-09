"""Setup's pages as pictures: the Style carousel, the one column and left edge of every page, the footer's
fade, the rail's marks and the one filled button. These were drawn-pixel and position checks in code
(test_setup_carousel, test_setup_layout, test_setup_look); the reviewer judges them here."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.setup import DONE, FIRST, HOMEWORK, REMINDERS, STYLE, WEEK, SetupPage
from desktop.native.widgets import Segmented
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen

SETUP_SOURCES = ("desktop/native/setup.py", "desktop/native/look.py", "desktop/native/motion.py")

# Said once, on every page's screen: the one filled button is Next (Open my week on the last page).
ONE_FILLED = (
    "Next is the one button filled in the accent on this page (it reads 'Open my week' on the last page); "
    "Add custom hours, Send a test reminder, Remove and Skip are outlined, not filled"
)


def _open(window: NativeWindow, step: int) -> SetupPage:
    """Setup as a new account sees it, on `step`, with no animation."""
    window._open_setup(step, first_run=True)
    setup = window.setup_page
    setup.motion = "off"
    QApplication.processEvents()
    return setup


def _until(done) -> None:
    """Let the page learn its new height: a scroll area hears of it from posted events."""
    for _ in range(200):
        QApplication.processEvents()
        if done():
            return


def _style_page(window: NativeWindow) -> QWidget:
    return _open(window, STYLE)


def _style_page_second_style(window: NativeWindow) -> QWidget:
    setup = _open(window, STYLE)
    setup.carousel.go_to("night")
    QApplication.processEvents()
    return setup


def _style_page_high_contrast(window: NativeWindow) -> QWidget:
    setup = _open(window, STYLE)
    setup.carousel.look_swatches["preset:high-contrast"].click()
    QApplication.processEvents()
    return setup


def _week_page(window: NativeWindow) -> QWidget:
    return _open(window, WEEK)


def _week_page_card_under_the_fade(window: NativeWindow) -> QWidget:
    """Five activities, scrolled so the second card reaches from 40 px above the footer's fade to below it."""
    setup = _open(window, WEEK)
    for _ in range(5):
        setup._add_activity()
    QApplication.processEvents()
    bar = setup.pages[WEEK].verticalScrollBar()
    bar.setValue(0)
    QApplication.processEvents()
    top = setup.footer.mapTo(setup, QPoint(0, 0)).y()
    row = setup.activities[1]
    bar.setValue(bar.value() + row.mapTo(setup, QPoint(0, 0)).y() - (top - 40))
    QApplication.processEvents()
    return setup


def _week_page_add_row(window: NativeWindow) -> QWidget:
    setup = _open(window, WEEK)
    for _ in range(3):
        setup._add_activity()
    bar = setup.pages[WEEK].verticalScrollBar()
    _until(lambda: bar.maximum() > 0)
    bar.setValue(bar.maximum())
    QApplication.processEvents()
    return setup


def _homework_page(window: NativeWindow) -> QWidget:
    return _open(window, HOMEWORK)


def _homework_page_many_cards(window: NativeWindow) -> QWidget:
    setup = _open(window, HOMEWORK)
    for _ in range(9):
        setup.work_editor.add_button.click()
    bar = setup.pages[HOMEWORK].verticalScrollBar()
    _until(lambda: bar.maximum() > 0)
    bar.setValue(bar.maximum())
    QApplication.processEvents()
    return setup


def _first_homework_page(window: NativeWindow) -> QWidget:
    setup = _open(window, FIRST)
    setup._fill_first()
    QApplication.processEvents()
    return setup


def _reminders_page(window: NativeWindow) -> QWidget:
    return _open(window, REMINDERS)


def _done_page(window: NativeWindow) -> QWidget:
    return _open(window, DONE)


def _rail_after_next(window: NativeWindow) -> QWidget:
    setup = _open(window, STYLE)
    setup.next.click()
    setup.next.click()
    QApplication.processEvents()
    return setup


def _rail_after_skip(window: NativeWindow) -> QWidget:
    setup = _open(window, STYLE)
    setup.skip.click()
    setup.skip.click()
    QApplication.processEvents()
    return setup


def _do_it_at_segments(window: NativeWindow) -> QWidget:
    setup = _open(window, FIRST)
    when = Segmented((("Let FlexWeek pick a time", "plan"), ("Do it at", "fixed")), "homeworkWhen")
    when.setParent(setup)
    when.adjustSize()
    when.move(40, 40)
    when.show()
    QApplication.processEvents()
    return when


SCREENS: list[Screen] = [
    Screen(
        id="setup.style_page",
        area="setup",
        prepare=_style_page,
        checks=(
            "the chosen style's picture stands in the middle of the stage (its centre within 1 px of the "
            "stage's) and is the big one, more than twice as wide as the part of the next card that shows; "
            "the next and the previous cards peek in from the sides, at least PEEK_PX of each showing, and "
            "are dimmed (opacity below 0.8, the middle at 1.0); "
            "the chosen card is ringed in the accent (its edge pixel is the accent, not only flagged); "
            "nothing on the Style page scrolls, at 1280x800 and at 1280x680; "
            "every pager dot is one size, centred level with the arrows, only the current dot is filled in "
            "the accent, the others one flat fill with no radio mark, and each dot is at most half the "
            "width of a look swatch; "
            "the look swatches are 24x24, whole and in a row of height 24 that fits the page, also at "
            "1024x640 with Large text (the row sits wholly inside the visible page); "
            "Choose my own look is an outlined button (its edge pixel differs from the one 6 px inside); "
            + ONE_FILLED
        ),
        sources=SETUP_SOURCES,
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="setup.style_page_second_style",
        area="setup",
        prepare=_style_page_second_style,
        checks=(
            "after the card that peeked is brought to the middle (by a click, an arrow or a dot) it stands "
            "in the middle (centre within 1 px of the stage's) at full opacity, ringed in the accent, and "
            "the old middle is dimmed on the other side"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.style_page_high_contrast",
        area="setup",
        prepare=_style_page_high_contrast,
        checks=(
            "picking the High contrast swatch redraws the Plain calendar preview with more of the "
            "high-contrast window colour than the default preview had, and the picked swatch is ringed"
        ),
        sources=SETUP_SOURCES + ("desktop/native/layouts/registry.py",),
        styles=("widgets",),
    ),
    Screen(
        id="setup.week_page",
        area="setup",
        prepare=_week_page,
        checks=(
            "every setup page's title and column start at one left edge (a page that scrolls sat 6 px left "
            "of one that did not, and the rail changed width with the bold step), at Normal and Large "
            "text and at 1280x800 and 1100x720; "
            "the page and its buttons are centred in a column up to 880 px wide, Next ends where the "
            "column ends and not at the window's edge, and a narrower window (1024 wide) gives the column "
            "all the room it has; "
            "the day pills are level with the time boxes (their middles within 1 px) for school and for "
            "the first activity; "
            "the bedtime card starts at the same left edge as the school card and is as wide; "
            "Remove and Skip are outlined buttons with an edge drawn; " + ONE_FILLED
        ),
        sources=SETUP_SOURCES,
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="setup.week_page_card_under_the_fade",
        area="setup",
        prepare=_week_page_card_under_the_fade,
        checks=(
            "where an activity card passes under the footer's fade, a row of pixels dissolves from the "
            "card's colour into the page's: above the fade the card is as it is; inside it the colour is "
            "neither the card's nor the page's, and is nearer the page's the nearer the buttons (24 px fade)"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.week_page_add_row",
        area="setup",
        prepare=_week_page_add_row,
        checks=(
            "with the page scrolled to its end, '+ Add a sport, club or job' sits wholly above the "
            "footer's fade (its bottom no lower than the fade's top), so it is not dimmed or hard to "
            "read, at 1100x810 and at the edge size 1024x640"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.homework_page",
        area="setup",
        prepare=_homework_page,
        checks=ONE_FILLED,
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.homework_page_many_cards",
        area="setup",
        prepare=_homework_page_many_cards,
        checks=(
            "with ten work-time cards the page scrolls, and scrolled to its end the last card ends above "
            "the footer (its bottom no lower than the footer's top), at 1280x800 and 1100x720"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.first_homework_page",
        area="setup",
        prepare=_first_homework_page,
        checks=(
            "in a homework row Name, the Takes stepper and the length chips share one left edge (the "
            "stepper sat 10 px right of Name when an empty grid column pushed it in); "
            "the Due label sits level with Takes (same top) and at least 16 px right of the stepper; "
            "Takes and Due labels share one text baseline; "
            "the Remove button's bottom is level with the Name field's bottom and Remove is an outlined "
            "button with an edge drawn"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.reminders_page",
        area="setup",
        prepare=_reminders_page,
        checks=(
            "each Play button is an icon (no text) drawn wholly in the look's accent, in light and dark: "
            "every inked pixel is within 3 per channel of the accent; " + ONE_FILLED
        ),
        sources=SETUP_SOURCES + ("desktop/native/icons.py",),
        styles=("widgets",),
    ),
    Screen(
        id="setup.done_page",
        area="setup",
        prepare=_done_page,
        checks=(
            "the small picture of the week beside the summary is the colour page's preview size "
            "(400 px wide) and shows a week; " + ONE_FILLED
        ),
        sources=SETUP_SOURCES,
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="setup.rail_after_next",
        area="setup",
        prepare=_rail_after_next,
        checks=(
            "after Next twice the first two steps show a tick on a circle filled in the accent, the third "
            "an accent ring with its number, and the later ones an unfilled muted ring (transparent above "
            "the number); every future step's label reads at 4.5 to 1 or better on the rail (it was a "
            "2.3 to 1 grey), in Light and Dark"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.rail_after_skip",
        area="setup",
        prepare=_rail_after_skip,
        checks=(
            "after Skip twice the first two steps show a dash in a dashed ring, clearly not the tick of a "
            "finished step, and the third is the current step"
        ),
        sources=SETUP_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="setup.do_it_at_segments",
        area="setup",
        prepare=_do_it_at_segments,
        checks=(
            "in the 'Let FlexWeek pick a time / Do it at' segmented control each segment is inset from "
            "its track by at least 2 px on all four sides"
        ),
        sources=("desktop/native/widgets.py",),
        styles=("widgets",),
    ),
]
