"""The Clay deck, Retro desktop and Timeline weeks as pictures: what the old layout tests asserted about
where things sit, how big they are, their colours and what fits. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QPushButton

from desktop.native import motion
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_timeline import canvas, centre_of, handle_of, over, press

CLAY = ("desktop/native/layouts/clay.py", "desktop/native/hours", "desktop/native/layouts/base.py")
RETRO = ("desktop/native/layouts/retro.py", "desktop/native/hours", "desktop/native/layouts/base.py")
TIMELINE = ("desktop/native/layouts/timeline.py", "desktop/native/hours", "desktop/native/layouts/base.py")
LOOKS = ("desktop/native/look.py", "desktop/native/tokens.py", "desktop/native/layouts/registry.py")


def design(
    name: str,
    *,
    clock: tuple[int, int] = (13, 40),
    size: tuple[int, int] | None = None,
    extra: tuple[dict, ...] = (),
    shared: bool = False,
    **options: str,
) -> Callable[[NativeWindow], object]:
    """Window on `name` showing the seeded week at `clock`, at `size` when given."""

    def prepare(window: NativeWindow) -> object:
        at(*clock)
        seed_week(window, shared=shared, extra=extra)
        if size is not None:
            window.resize(*size)
        return show_design(window, name, **options)

    return prepare


# Clay: the row of cards


# Short blocks on Wednesday's card, which sits beside the one in front: a half hour (Dinner is on every
# day), quarter hours one after the other, a lesson with room for its icon, and two blocks that share
# their time on Tuesday.
CLAY_SIDE_BLOCKS = (
    locked("call", "Call", "extra", "15:00", 15, [2]),
    locked("tidy", "Tidy", "extra", "15:15", 15, [2]),
    locked("stretch", "Stretch", "extra", "16:30", 15, [2]),
    locked("piano", "Piano lesson", "extra", "17:00", 30, [2]),
    locked("soccer", "Soccer practice", "extra", "16:00", 90, [1]),
    locked("choir", "Choir", "extra", "16:00", 90, [1]),
)


def clay_slide(window: NativeWindow, *, on_day: bool, last: bool) -> object:
    """The row of cards part-way (or at the end of) its slide to Friday, under Normal motion."""
    at(13, 40)
    seed_week(window, shared=False)
    motion.apply_ui_effects("normal")
    view = show_design(window, "clay", surface="day" if on_day else "week")
    if on_day:
        session = window.session
        session.open_day("2026-11-06")
        window._on_week()
    else:
        view.findChild(QPushButton, "clayAhead").click()
    row = view.row
    wait_until(None, lambda: row._snaps is not None, what="the row starting to slide")
    row._slide.pause()
    if last:
        row._on_clock(float(row._slide.duration()))
    else:
        row._slid(0.3)
    row.repaint()
    return row


# Retro: the desktop


def retro_match(preset: str | None) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        at(13, 40)
        seed_week(window, shared=False)
        if preset is not None:
            window._look = sanitize_look({"preset": preset, "knobs": {}})
        return show_design(window, "retro", look="your")

    return prepare


RETRO_WEEKEND = (
    locked("shift", "Saturday shift at the cafe", "extra", "09:00", 240, [5]),
    locked("choir", "Sunday choir practice and coffee", "extra", "10:00", 180, [6]),
)


# Timeline: the planner spread


SCHOOL_EVERY_DAY = (locked("school-all", "School", "class", "08:00", 390, [0, 1, 2, 3, 4, 5, 6]),)


def timeline_fold(left: int, *, two_notes: bool = False) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        at(13, 40)
        seed_week(window, shared=False)
        if two_notes:
            window.session.add_homework(
                {"id": "lab", "title": "Lab", "due": "2026-11-07T20:00", "estimate_min": 60, "revision": 0}
            )
            window.session.save()
            wait_until(None, lambda: not window.session.busy and not window.session.dirty)
        return show_design(window, "timeline", fold=str(left))

    return prepare


def timeline_tall(window: NativeWindow) -> object:
    at(13, 40)
    seed_week(window, shared=False)
    window.resize(1280, 1400)
    view = show_design(window, "timeline")
    canvas(view)._scroll_area().zoom_by(-1)
    return view


def timeline_mid_drag(window: NativeWindow) -> object:
    """The fold handle held and carried over Wednesday's first third, not yet let go."""
    at(13, 40)
    seed_week(window, shared=False)
    view = show_design(window, "timeline")
    hours = canvas(view)
    hours.reveal(2, 21 * 60, 23 * 60)
    handle = handle_of(view)
    start = centre_of(handle)
    to = over(view, 2, 0.3)
    press(handle, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 7):
        press(handle, QEvent.Type.MouseMove, start + (to - start) * (step / 6), True)
    return view


SCREENS: list[Screen] = [
    # Clay
    Screen(
        id="week.clay_deck_row",
        area="week",
        prepare=design("clay"),
        checks=(
            "At 1280 wide the card in front is 452 px wide at x 414 and 600 px tall (row 632 px high); each "
            "neighbour is 70 % of that (316 by 420), centred on the same line, with 32 px between cards, "
            "and the leftmost neighbour starts near x 66. The day after a neighbour waits wholly past the "
            "window's edge rather than being cut by it. A card is seen whole or not at all, whichever day "
            "is in front and at 900, 1024, 1150 (Large text), 1280 and 1600 wide. The fade at the row's "
            "ends reaches no further in than the room outside the two cards in view. The cards beside "
            "the front label their whole hours to the left of their blocks, as the front does. Neighbours "
            "sit under a veil of the page colour (60 % page over 40 % card, in the Slate look where they "
            "differ the most); the card in front shows its own colour with no veil."
        ),
        sources=CLAY,
        main=True,
    ),
    Screen(
        id="week.clay_deck_dark_veil",
        area="week",
        prepare=design("clay", look="pack:dark-frost"),
        checks=(
            "On a dark look the neighbours still sit under the 60 % veil of the page colour, a pixel of "
            "Friday's card beside its hours is the page laid 60 % over the card colour, and the card in "
            "front shows its own colour."
        ),
        sources=(*CLAY, *LOOKS),
    ),
    Screen(
        id="week.clay_side_card_blocks",
        area="week",
        prepare=design("clay", extra=CLAY_SIDE_BLOCKS, shared=True),
        checks=(
            "On Wednesday's card at 70 % a half hour (Dinner, 10 px tall) is still named, with the name "
            "shortened at a word and an ellipsis where the block is narrow, and left as its colour alone "
            "where not even three letters fit, at 9 pt and at 13 pt. The icon gives way where it would "
            "cost the name: room for 'Piano lesson' says the name, room for the icon and 'Piano' says "
            "the name shortened, room for both has both. A half hour says its start time rather than its "
            "icon: name, then time, then icon, only when all three fit. The quarter hours Call (15:00), "
            "Tidy (15:15) and Stretch (16:30) are under 8 px tall and each is named by its name or else "
            "its start time, beside its bar, inside the card, not over each other nor over School or "
            "Dinner. Two blocks that share their time (Soccer practice and Choir on Tuesday) sit side by "
            "side with no dot at the corner of either."
        ),
        sources=CLAY,
    ),
    Screen(
        id="week.clay_slide_midway",
        area="week",
        prepare=lambda window: clay_slide(window, on_day=False, last=False),
        checks=(
            "Part-way into the slide to Friday each moving picture of a card is scaled by one factor on "
            "both sides (its words are not stretched) and clipped to its card's own rectangle."
        ),
        sources=CLAY,
    ),
    Screen(
        id="week.clay_slide_last_frame",
        area="week",
        prepare=lambda window: clay_slide(window, on_day=False, last=True),
        checks=(
            "At the last frame of the slide the row already looks as it does once landed: no hour, "
            "heading or card is in another place than in the landed row (the biggest difference in any "
            "colour channel between the two stays under 16 apart from a sliver of antialiasing at the "
            "arrows' and cards' edges)."
        ),
        sources=CLAY,
    ),
    # Retro
    Screen(
        id="week.retro_desktop",
        area="week",
        prepare=design("retro", shared=True),
        checks=(
            "Week.exe, deadlines.txt and Up next sit on the desk with the taskbar below; the desktop icons "
            "have their room at 1280 by 708 (Week.exe's left edge at x 100, Notepad 380 wide and 13 px "
            "right of Week.exe). Windows 98's scroll bar beside the hours is 17 px wide. Week blocks say "
            "their start alone. The status bar cells show their whole words. Block names too narrow for "
            "three letters leave the block as its colour alone. Two blocks that share their time (Robotics "
            "club and Maths on Monday) sit side by side with no dot at the corner of either."
        ),
        sources=RETRO,
        main=True,
    ),
    Screen(
        id="week.retro_narrow",
        area="week",
        prepare=design("retro", size=(1150, 768), extra=RETRO_WEEKEND, shared=False),
        checks=(
            "At 1150 by 768 with Large text the icons give way (Week.exe's left edge at x 12, Up next's "
            "top 17 px under Notepad's bottom). Week.exe is no wider than the desk and starts on it "
            "(x between 0 and the desk's width less 60). Every weekday head, Saturday and Sunday included, "
            "lies inside the window, and the not-placed chip in Notepad is inside the window. A long "
            "title in Notepad (History essay on the causes of the war) is shortened only at a word and "
            "its length and time sit under it, whole; no Notepad line is cut and none runs off the page."
        ),
        sources=RETRO,
    ),
    Screen(
        id="week.retro_smallest_window",
        area="week",
        prepare=design("retro", size=(810, 700), extra=RETRO_WEEKEND, shared=False),
        checks=(
            "At 810 by 700 every day head says its day alone (Mon, Tue, ...), none with a date and some "
            "without. A day on the week is a block 49.7 px wide: School is written whole if it fits, or "
            "as 'Sch…', over its start time, never nothing, with the full margins. The status bar says "
            "less rather than cutting its words: each cell's words fit its cell."
        ),
        sources=RETRO,
    ),
    Screen(
        id="week.retro_teal_desktop",
        area="week",
        prepare=design("retro", look="preset:retro-teal"),
        checks=(
            "Windows 98's own teal desktop: the desk is #008080, the title bars run from #000080 to "
            "#1084d0 with white title words, the windows' faces are silver #c0c0c0 and their fields white."
        ),
        sources=(*RETRO, *LOOKS),
    ),
    Screen(
        id="week.retro_slate_desktop",
        area="week",
        prepare=design("retro", look="pack:dark-frost"),
        checks=(
            "In a dark look the desktop is the page's background colour and the words on the title bars "
            "read against both ends of the bar's gradient (AA text contrast, 4.5:1), the icon names read "
            "on the desktop and the words read on the silver and white inside the windows."
        ),
        sources=(*RETRO, *LOOKS),
    ),
    Screen(
        id="week.retro_match_my_look",
        area="week",
        prepare=retro_match(None),
        checks=(
            "In Match my look the desktop is the look's window colour and the title bars are its accent; "
            "inside the windows it is period silver (#c0c0c0 with white fields) whatever the look. Every "
            "word reads on its ground in every look: title words on both ends of the bar, icon names on "
            "the desktop, ink on silver and white, the danger colour on silver (AA text contrast, 4.5:1; "
            "the old test swept every pack, dark or light, preset and accent, which one picture samples)."
        ),
        sources=(*RETRO, *LOOKS),
    ),
    Screen(
        id="week.retro_high_contrast",
        area="week",
        prepare=retro_match("high-contrast"),
        checks=(
            "Windows 98's high contrast black: the window faces, fields and desk are all black #000000, "
            "ink, highlights and shadows are white #ffffff, and the title bars are the accent."
        ),
        sources=(*RETRO, *LOOKS),
    ),
    # Timeline
    Screen(
        id="week.timeline_spread",
        area="week",
        prepare=design("timeline", shared=True),
        checks=(
            "Monday to Wednesday on the left page and Thursday to Sunday on the right, with a gutter of at "
            "least 40 px between Wednesday and Thursday and the fold in its middle; one set of hour rules "
            "runs across both pages; the three left columns share one width and the four right columns "
            "share one (within 1 px). Each day's name sits over its column (within 2 px), is shortened "
            "before it is cut (Mon, not Mo...), and its date follows within 10 px, inside the heading. "
            "The paper shows under the hours and behind the notes, and the gutter is plain paper either "
            "side of the fold line (3, 8 and 14 px away), with the fold line itself kept. The week's "
            "figures at the left foot and the notes and what is due at the right foot sit side by side, "
            "each foot on its own page."
        ),
        sources=TIMELINE,
        main=True,
    ),
    Screen(
        id="week.timeline_blocks",
        area="week",
        prepare=design(
            "timeline",
            extra=(
                locked("quiz", "Quiz", "extra", "18:00", 30, [3]),
                locked("quarter", "History essay", "assignments", "18:00", 15, [2]),
            ),
        ),
        checks=(
            "Every block (School, Dinner, homework alike) is filled with its category colour, never the "
            "page's surface colour, and outlined in ink with the category's colour down its start edge; "
            "its title is in the page's text colour and its times a little quieter, both at AA text "
            "contrast (4.5:1) on the fill. 'History essay' is written on the 60 minute block and a fallback "
            "title stays inside its block at 60, 12 and 5 px tall, never below what is on screen. Two blocks "
            "at one time (Dinner and Quiz on Thursday) go half width side by side, equal in width, "
            "neither over the other."
        ),
        sources=(*TIMELINE, *LOOKS),
    ),
    Screen(
        id="week.timeline_now_pill",
        area="week",
        prepare=design("timeline", clock=(10, 5), extra=SCHOOL_EVERY_DAY),
        checks=(
            "At 10:05 with School on every day the time now is on a pill that covers no block and no hour "
            "label: beside the hour labels in place of the one it is nearest, or for a day on the right "
            "page in that page's margin at the fold, inside the canvas. The line across today's column "
            "is in the now colour and the day before has none."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_now_pill_compact",
        area="week",
        prepare=design("timeline", clock=(10, 5), extra=SCHOOL_EVERY_DAY, density="compact"),
        checks=(
            "In the compact density, at 10:05 with School on every day, the pill for the time now still "
            "covers no block and no hour label, and the hours take more of the page than in the roomy "
            "density (the hours' scroll area is taller)."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_paper",
        area="week",
        prepare=design("timeline", look="preset:timeline-paper"),
        checks=(
            "Ruled paper: the page's corner is #fdfbf7, the accent is the look's own, and the headings "
            "(day names, the week's figures) are set in Newsreader, the design's own face."
        ),
        sources=(*TIMELINE, *LOOKS),
    ),
    Screen(
        id="week.timeline_night",
        area="week",
        prepare=design("timeline", look="pack:dark-frost"),
        checks=(
            "Night: the page's corner is #111315, the accent is the look's own, and every block is "
            "filled with its category colour, not the page's."
        ),
        sources=(*TIMELINE, *LOOKS),
    ),
    Screen(
        id="week.timeline_match_my_look",
        area="week",
        prepare=design("timeline", look="your"),
        checks=(
            "Match my look: the blocks are filled with the look's category colours over the look's "
            "surface, their words read on the fill (AA text contrast, 4.5:1), and the headings stay in "
            "Newsreader when the look is Paper."
        ),
        sources=(*TIMELINE, *LOOKS),
    ),
    Screen(
        id="week.timeline_fold_two_and_five",
        area="week",
        prepare=timeline_fold(2),
        checks=(
            "With the fold at 2 | 5 the left foot ends and the right foot starts either side of the fold, "
            "each page's foot stays on its page, the gutter between the feet is centred on the fold "
            "(within 2 px), and the paper either side of the fold line is plain. The handle sits in the row "
            "of day names beside the fold (its centre within 13 px of the fold, inside the row) and clears "
            "the heading of Thursday; each page's days share their width equally."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_fold_one_left",
        area="week",
        prepare=timeline_fold(1),
        checks=(
            "With one day on the left page the week's figures (3 h 15 min homework planned, 1 of 4 done, "
            "1 not placed yet) wrap onto two rows and every figure and its words are whole and inside "
            "the page's foot; at 3 | 4 they stay on one row."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_fold_one_right",
        area="week",
        prepare=timeline_fold(6, two_notes=True),
        checks=(
            "With one day on the right page its foot is about 140 px wide: the two notes waiting go one "
            "to a row inside the page, and each due line wraps rather than running past the page's edge; "
            "every label and every title lies inside the foot."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_fold_mid_drag",
        area="week",
        prepare=timeline_mid_drag,
        checks=(
            "While the fold's handle is dragged over Wednesday a dashed line in the accent colour runs "
            "down Wednesday's start edge through the evening, Wednesday, which would change page, is "
            "tinted, and the pages the fold would make are named (Mon–Tue | Wed–Sun). No such line or "
            "tint is on the page before the drag."
        ),
        sources=TIMELINE,
    ),
    Screen(
        id="week.timeline_tall_hours",
        area="week",
        prepare=timeline_tall,
        checks=(
            "In a tall window (1280 by 1400) zoomed out to 28 px an hour the hours are no taller than "
            "the day: no empty page under the end of the day, and the foot follows the hours within "
            "12 px. A new text size makes each day's name fit its column."
        ),
        sources=TIMELINE,
    ),
]
