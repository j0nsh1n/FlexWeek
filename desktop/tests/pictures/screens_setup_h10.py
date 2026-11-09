"""Setup's pages as pictures: what the audit of setup checked by pixels and positions (cards whole,
chips drawn as pills, the example homework in the muted colour, time fields at one x, the open
calendar, the focus ring) is judged on these, not in code."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.setup import COLOURS, FIRST, HOMEWORK, LOOK, REMINDERS, STYLE, WEEK, SetupPage
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.window_support import still

SOURCES = ("desktop/native/setup.py", "desktop/native/look.py")
NARROW = (810, 800)


def _pump() -> None:
    # Layout and queued paints settle in a few turns of the event loop; nothing waits on a time.
    for _ in range(10):
        QApplication.processEvents()


def _setup_on(window: NativeWindow, step: int, size: tuple[int, int] | None = None) -> SetupPage | None:
    """Setup opened again, as Settings' Run setup again does, on `step`. Material shows its own setup
    page, which is photographed whole; None says there is no widgets page to work on."""
    if size is not None:
        window.resize(*size)
    window._open_setup(STYLE, first_run=False)
    if window._surface == "material":
        _pump()
        return None
    setup = window.setup_page
    setup._show(step)
    _pump()
    still(setup)
    return setup


def style_page(window: NativeWindow) -> object:
    return _setup_on(window, STYLE)


def look_page_end(window: NativeWindow, size: tuple[int, int] | None = None) -> object:
    setup = _setup_on(window, LOOK, size)
    if setup is None:
        return None
    bar = setup.pages[LOOK].verticalScrollBar()
    bar.setValue(bar.maximum())
    _pump()
    return setup


def look_page_end_narrow(window: NativeWindow) -> object:
    return look_page_end(window, NARROW)


def week_page(window: NativeWindow, size: tuple[int, int] | None = None) -> object:
    setup = _setup_on(window, WEEK, size)
    if setup is not None:
        setup._add_activity(title="Band", days=[2], start="16:00", minutes=60)
        _pump()
    return setup


def week_page_narrow(window: NativeWindow) -> object:
    return week_page(window, NARROW)


def planning_hours_page(window: NativeWindow) -> object:
    return _setup_on(window, HOMEWORK)


def reminders_page(window: NativeWindow) -> object:
    return _setup_on(window, REMINDERS)


def first_homework_page(window: NativeWindow) -> object:
    return _setup_on(window, FIRST)


def first_homework_calendar(window: NativeWindow) -> object:
    setup = _setup_on(window, FIRST)
    if setup is None:
        return None
    field = setup.homework_rows[0].due.date
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    _pump()
    month = field.calendarWidget()
    popup: QWidget = month.parentWidget()
    return popup


def clock_radio_focused(window: NativeWindow) -> object:
    setup = _setup_on(window, WEEK)
    if setup is None:
        return None
    button = setup.clock_buttons[False]
    button.setFocus(Qt.FocusReason.TabFocusReason)
    _pump()
    return button.parentWidget()


def colours_page(window: NativeWindow) -> object:
    setup = _setup_on(window, LOOK)
    if setup is not None:
        setup._show(COLOURS)
        _pump()
    return setup


SCREENS: list[Screen] = [
    Screen(
        id="setup.style_carousel",
        area="setup",
        prepare=style_page,
        checks=(
            "the Style page's middle picture is whole: its left edge is not left of the page and its right "
            "edge is inside it (the neighbours may run off the sides on purpose); the style's name and note "
            "under it are not cut off, each label as tall as its wrapped text needs"
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="setup.look_cards_end_of_page",
        area="setup",
        prepare=look_page_end,
        checks=(
            "scrolled to the end of the Look page, every picture card lies whole inside the page: none "
            "cut at the left or right edge, none cut at the bottom, and no wrapped label inside a card is "
            "shorter than its text; Today's app and Timeline sit above the heading 'Experimental styles' "
            "and the four other designs sit below it"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.look_cards_end_of_page_narrow",
        area="setup",
        prepare=look_page_end_narrow,
        checks=(
            "the same page with the window 810 pixels wide, where two cards a row once ran off the right "
            "edge and nothing scrolls sideways: every picture card is whole, none cut at the side or "
            "bottom, no wrapped label cut"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.week_times",
        area="setup",
        prepare=week_page,
        checks=(
            "a sport's Start and End fields begin at the same x and are the same width as School's; the "
            "'Start' and 'End' labels sit level with their fields, their middles within 3 pixels of the "
            "field's middle (at Small, Normal and Large text); no label or field text is cut off at Large "
            "text"
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="setup.week_times_narrow",
        area="setup",
        prepare=week_page_narrow,
        checks=(
            "at 810 pixels wide, a sport's Start and End fields still begin at the same x and have the "
            "same width as School's, and their labels still sit level with them"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.planning_hours_chips",
        area="setup",
        prepare=planning_hours_page,
        checks=(
            "'+ After school', '+ Evenings' and '+ Weekend mornings' are drawn as pills: the same fill "
            "as the day picker's unchecked day on the Week page and the same height, never plain words; "
            "none looks chosen; 'Add custom hours' is an outlined button (an edge, no fill) because Next "
            "is the page's one filled button"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.reminders_sounds",
        area="setup",
        prepare=reminders_page,
        checks=(
            "each alarm sound's Play button sits in one column and level with its sound's radio, middles "
            "within 2 pixels; 'Send a test reminder' is an outlined button: an edge in the strong hairline "
            "colour and the card's own fill inside, not words alone in the page's colour"
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="setup.first_homework_example",
        area="setup",
        prepare=first_homework_page,
        checks=(
            "the empty homework name shows 'e.g. History essay' in the muted colour (its strongest pixel "
            "within 30 colour steps in total of the palette's muted), so it reads as an example and not as "
            "a typed value; the page lists no homework until one is typed"
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="setup.first_homework_calendar",
        area="setup",
        prepare=first_homework_calendar,
        checks=(
            "the Due date's calendar, open, draws the day numbers of the month in the text colour on the "
            "panel (within 3 steps a channel) and the weekday row above them, not only the weekday letters "
            "and one square"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.clock_focus_ring",
        area="setup",
        prepare=clock_radio_focused,
        checks=(
            "the 12-hour clock radio, reached by Tab, draws a ring that is at least 3 to 1 against the "
            "pixels just outside it, in each look: light, dark, high contrast, nocturne, slate, poster, "
            "terminal, paper, ink and pastel"
        ),
        sources=SOURCES,
    ),
    Screen(
        id="setup.day_screen_chips",
        area="setup",
        prepare=colours_page,
        checks=(
            "the day screen is one choice across two rows: the first design's chip above the heading "
            "'Experimental styles', the second below it; exactly one chip shows as chosen"
        ),
        sources=SOURCES,
    ),
]
