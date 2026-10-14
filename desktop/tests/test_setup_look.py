"""Setup as 0.17 draws it (decision 26): each page and its buttons centred up to 880 pixels, a tick on
every finished step, Next the one filled button, the school hint only when it is true, Play an icon.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, QSize, QStandardPaths, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

    from desktop.native.calendar import monday_of
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import pack_stylesheet, resolved_palette
    from desktop.native.setup import (
        BADGE_PX,
        COLOUR_THUMB,
        CURRENT,
        DONE,
        FINISHED,
        FIRST,
        HOMEWORK,
        PENDING,
        REMINDERS,
        SETUP_COLUMN,
        SETUP_SCHOOL_ID,
        SKIPPED,
        STYLE,
        WEEK,
        SetupPage,
        SetupState,
        step_badge,
    )
    from desktop.native.weekmodel import set_clock_24h
    from desktop.native.widgets import control_art

STEPS = (STYLE, WEEK, HOMEWORK, REMINDERS, DONE)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-setup-look-test"])


@pytest.fixture()
def dressed(qapp: QApplication) -> Iterator[tuple[SetupPage, dict]]:
    """Setup in Light, with the window's stylesheet, as a new account sees it."""
    palette = resolved_palette("light-frost", False, None)
    host = QWidget()
    host.setStyleSheet(pack_stylesheet("light-frost", False, None, "default", palette, control_art(palette)))
    setup = SetupPage(host)
    setup.motion = "off"
    setup.set_palette(palette)
    look = {"preset": "default", "knobs": {}}
    setup.open(SetupState("light-frost", look, sanitize_layout(None), {}, [], monday_of("2026-09-23")))
    host.resize(1600, 800)
    setup.resize(1600, 800)
    host.show()
    qapp.processEvents()
    yield setup, palette
    host.close()
    host.deleteLater()
    qapp.processEvents()


def column_of(setup: SetupPage) -> QWidget:
    """The page's centred column: the one holding its title."""
    return setup.stack.currentWidget().findChild(QWidget, "setupTitle").parentWidget()


def test_each_page_and_its_buttons_are_centred_up_to_880_pixels(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    setup, _palette = dressed
    for step in (STYLE, WEEK, REMINDERS):
        setup._show(step)
        qapp.processEvents()
        column = column_of(setup)
        page = setup.stack.currentWidget()
        assert column.width() == SETUP_COLUMN, step
        left = column.mapTo(page, QPoint(0, 0)).x()
        right = page.viewport().width() - (left + column.width())
        # A page that scrolls is centred over its scroll bar too, so the visible side is a bar narrower.
        assert abs(left - right) <= page.width() - page.viewport().width() + 2, (step, left, right)
        # Next ends where the page above it ends, not at the window's edge; a page that scrolls is
        # centred beside its scroll bar, half a bar's width off.
        next_right = setup.next.mapTo(setup, QPoint(setup.next.width(), 0)).x()
        bar = page.width() - page.viewport().width()
        assert abs(next_right - column.mapTo(setup, QPoint(column.width(), 0)).x()) <= bar // 2 + 2, step
    setup.resize(1000, 800)
    qapp.processEvents()
    column = column_of(setup)
    assert column.width() < SETUP_COLUMN, "a narrow window gives the page all the room it has"


def picture(setup: SetupPage, index: int) -> object:
    return setup.rail_items[index].icon().pixmap(QSize(BADGE_PX, BADGE_PX)).toImage()


def badge(number: int, state: str, setup: SetupPage, palette: dict) -> object:
    family = setup.rail_items[0].font().family()
    return step_badge(number, state, palette, family).toImage()


def test_a_finished_step_shows_a_tick_on_the_rail(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    setup, palette = dressed
    setup.next.click()
    setup.next.click()
    assert setup.step == HOMEWORK
    states = [FINISHED, FINISHED, CURRENT, PENDING, PENDING, PENDING]
    for index, state in enumerate(states):
        assert picture(setup, index) == badge(index + 1, state, setup, palette), (index, state)
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == ["Done", "Done", "Current step"]
    tick = badge(1, FINISHED, setup, palette)
    # Above the tick and inside the ring.
    assert tick.pixelColor(BADGE_PX // 2, 4) == QColor(palette["accent"]), "a tick on the accent"
    assert badge(1, PENDING, setup, palette).pixelColor(BADGE_PX // 2, 4).alpha() == 0, "a ring, not filled"


def test_a_skipped_step_is_marked_skipped_not_done(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """F3b: a step left by Skip is not done, so it shows a dash in a dashed ring, not the tick."""
    setup, palette = dressed
    setup.skip.click()
    setup.skip.click()
    assert setup.step == HOMEWORK
    states = [SKIPPED, SKIPPED, CURRENT, PENDING, PENDING, PENDING]
    for index, state in enumerate(states):
        assert picture(setup, index) == badge(index + 1, state, setup, palette), (index, state)
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == [
        "Skipped",
        "Skipped",
        "Current step",
    ]
    assert badge(1, SKIPPED, setup, palette) != badge(1, FINISHED, setup, palette)


def filled(setup: SetupPage, accent: str) -> list[str]:
    """The buttons on screen painted in the accent, read from a picture of each."""
    found = []
    for button in setup.findChildren(QPushButton):
        if not button.isVisibleTo(setup) or button.width() < 8:
            continue
        # A ticked day or chip is an answer shown, like a segment, not a second thing to press.
        if button.isCheckable() and (button.property("pill") or button.objectName() == "setupChip"):
            continue
        # The carousel's chosen dot marks which style is picked, which is not a button to press on.
        if button.objectName() == "setupDot":
            continue
        # Above the words, so a link in the accent does not count as a fill.
        if button.grab().toImage().pixelColor(button.width() // 2, 3) == QColor(accent):
            found.append(button.text() or button.objectName())
    return found


def test_next_is_the_one_filled_button_on_every_page(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """Add custom hours and Send a test reminder were filled like Next, and read as the way on."""
    setup, palette = dressed
    for step in STEPS:
        setup._show(step)
        qapp.processEvents()
        assert filled(setup, palette["accent"]) == ["Open my week" if step == DONE else "Next"], step


def test_the_school_hint_shows_only_when_no_school_day_is_picked(dressed: tuple[SetupPage, dict]) -> None:
    setup, _palette = dressed
    setup._show(WEEK)
    assert not setup.school_hint.isVisibleTo(setup), "under a week of school days it read as a warning"
    setup.school_days.set_days([])
    assert setup.school_hint.isVisibleTo(setup)
    setup.school_days.set_days([2])
    assert not setup.school_hint.isVisibleTo(setup)


def apart(first: QColor, second: QColor) -> int:
    return max(abs(a - b) for a, b in zip(first.getRgb()[:3], second.getRgb()[:3], strict=True))


def test_play_is_an_icon_in_the_looks_accent(dressed: tuple[SetupPage, dict]) -> None:
    setup, _palette = dressed
    setup._show(REMINDERS)
    dark = resolved_palette("dark-frost", False, None)
    setup.set_palette(dark)
    for play in setup.play_buttons:
        assert play.text() == "" and play.toolTip() == "Play"
        drawn = play.icon().pixmap(QSize(20, 20)).toImage()
        accent = QColor(dark["accent"])
        inked = [
            drawn.pixelColor(x, y)
            for x in range(drawn.width())
            for y in range(drawn.height())
            if drawn.pixelColor(x, y).alpha() >= 128
        ]
        assert inked, play.accessibleName()
        far = [seen.name() for seen in inked if apart(seen, accent) > 3]
        assert far == [], play.accessibleName()


def test_the_style_pager_dots_share_one_box_and_only_the_current_one_is_accent(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """Jonathan saw one big blue dot and small grey marks; every dot is one size, centred on the arrows,
    and the current one alone is filled in the accent."""
    setup, palette = dressed
    setup._show(STYLE)
    qapp.processEvents()
    carousel = setup.carousel
    dots = list(carousel.dots.values())
    assert len({(dot.width(), dot.height()) for dot in dots}) == 1
    centre_y = {dot.geometry().center().y() for dot in dots} | {carousel.previous.geometry().center().y()}
    assert max(centre_y) - min(centre_y) <= 1
    current = carousel.key()
    for key, dot in carousel.dots.items():
        centre = dot.grab().toImage().pixelColor(dot.width() // 2, dot.height() // 2)
        if key == current:
            assert centre == QColor(palette["accent"]), key
        else:
            assert centre != QColor(palette["accent"]), key


def test_style_look_swatches_follow_the_design_and_change_the_preview(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    from desktop.native.layouts.registry import DESIGN_LOOKS
    from desktop.native.look import design_look
    from desktop.native.setup import STYLES

    setup, _palette = dressed
    setup._show(STYLE)
    carousel = setup.carousel
    swatches = list(carousel.look_swatches.values())
    assert list(carousel.look_swatches) == [token for token, _name in DESIGN_LOOKS["classic"]]
    assert swatches[0].isChecked()
    assert all(button.isVisibleTo(setup) for button in swatches)
    assert all(button.width() == 24 and button.height() == 24 for button in swatches)
    assert all(button.focusPolicy() & Qt.FocusPolicy.TabFocus for button in swatches)

    before = carousel.slides["plain"].picture.pixmap().toImage()
    choice = next(button for button in swatches if button.property("lookToken") == "preset:high-contrast")
    assert choice.accessibleName() == "High contrast"
    assert choice.toolTip() == "High contrast"
    choice.click()
    qapp.processEvents()
    after = carousel.slides["plain"].picture.pixmap().toImage()
    assert choice.isChecked()
    assert before != after
    background = QColor(design_look("preset:high-contrast", "light-frost", False, None)[0]["window"])
    after_background = sum(
        after.pixelColor(x, y) == background for x in range(after.width()) for y in range(after.height())
    )
    before_background = sum(
        before.pixelColor(x, y) == background for x in range(before.width()) for y in range(before.height())
    )
    assert after_background > before_background
    assert setup._layout["options"]["classic"]["look"] == "preset:high-contrast"

    # Another design shows its own looks with its signature picked; coming back keeps this setup's pick.
    setup.carousel.go_to("dashboard")
    assert setup.carousel.key() == "dashboard"
    bento = list(setup.carousel.look_swatches.values())
    assert bento[0].isChecked() and bento[0].property("lookToken") == DESIGN_LOOKS["bento"][0][0]
    assert setup._layout["options"]["bento"]["look"] == DESIGN_LOOKS["bento"][0][0]
    setup.carousel.go_to("plain")
    assert setup.carousel.look_swatches["preset:high-contrast"].isChecked()
    for style in STYLES:
        setup.carousel.go_to(style.key)
        assert list(setup.carousel.look_swatches) == [
            token for token, _name in DESIGN_LOOKS[style.main]
        ]


def test_style_look_swatches_fit_at_1024_by_640_large_text(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    setup, _palette = dressed
    setup._look = {**setup._look, "knobs": {**setup._look.get("knobs", {}), "text": "large"}}
    setup.set_palette(resolved_palette(setup._pack, False, setup._look))
    setup.resize(1024, 640)
    setup._show(STYLE)
    qapp.processEvents()
    row = setup.carousel.look_row
    swatches = list(setup.carousel.look_swatches.values())
    assert row.width() >= sum(button.width() for button in swatches)
    assert row.height() == 24
    assert all(button.isVisibleTo(setup) for button in swatches)
    page = setup.pages[STYLE]
    assert row.mapTo(page.widget(), QPoint(0, 0)).y() + row.height() <= page.viewport().height()


def test_a_homework_row_lines_its_fields_up_on_one_left_edge(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """The Takes stepper and its length chips sat 10 pixels right of the Name field, because an empty
    grid column pushed them in. Name, Takes and the chips share one left edge, Due sits level with
    Takes, and Remove sits level with the name field."""
    setup, _palette = dressed
    setup._show(FIRST)
    setup._fill_first()
    qapp.processEvents()
    row = setup.homework_rows[0]
    stepper = row.minutes.parentWidget()
    takes = next(label for label in row.findChildren(QLabel) if label.text() == "Takes")
    due = next(label for label in row.findChildren(QLabel) if label.text() == "Due")
    remove = next(button for button in row.findChildren(QPushButton) if button.text() == "Remove")
    assert row.name.geometry().left() == takes.geometry().left() == stepper.geometry().left()
    assert stepper.chips[0].mapTo(row, QPoint(0, 0)).x() == stepper.geometry().left()
    assert due.geometry().top() == takes.geometry().top()
    assert due.geometry().left() - stepper.geometry().right() >= 16
    assert remove.geometry().bottom() == row.name.geometry().bottom()


def test_you_are_set_writes_times_on_the_accounts_12_hour_clock(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """Jonathan's 12-hour account saw 08:00 and 23:00 on You're set. The summary must use the clock
    the account chose: 8:00 AM and 11:00 PM here."""
    setup, _palette = dressed
    school = {
        "id": SETUP_SCHOOL_ID,
        "title": "School",
        "start": "08:00",
        "duration_min": 390,
        "days": [1, 2, 3, 4, 5],
    }
    state = SetupState(
        "light-frost",
        {"preset": "default", "knobs": {}},
        sanitize_layout(None),
        {"clock_24h": False, "day_cutoff": "23:00"},
        [school],
        monday_of("2026-09-23"),
    )
    setup.open(state, DONE)
    qapp.processEvents()
    summary = " | ".join(setup.summary_text())
    assert "8:00 AM" in summary and "11:00 PM" in summary, summary
    assert "08:00" not in summary and "23:00" not in summary, summary


def test_you_are_set_ignores_a_stale_24_hour_clock_left_by_another_page(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """The clock is shared by the whole app. A 24-hour clock left behind must not reach the summary
    of a 12-hour account."""
    setup, _palette = dressed
    school = {
        "id": SETUP_SCHOOL_ID,
        "title": "School",
        "start": "08:00",
        "duration_min": 390,
        "days": [1, 2, 3, 4, 5],
    }
    state = SetupState(
        "light-frost",
        {"preset": "default", "knobs": {}},
        sanitize_layout(None),
        {"clock_24h": False, "day_cutoff": "23:00"},
        [school],
        monday_of("2026-09-23"),
    )
    setup.open(state, WEEK)
    set_clock_24h(True)
    setup._show(DONE)
    qapp.processEvents()
    assert "8:00 AM" in setup.summary_text()[1]
    assert "11:00 PM" in setup.summary_text()[1]


def test_you_are_set_shows_a_picture_of_the_week_beside_the_summary(
    qapp: QApplication, dressed: tuple[SetupPage, dict]
) -> None:
    """Jonathan asked for a small live picture of the week with the chosen style, look and text size,
    next to the words. Its frame is the colour page's preview size, and it holds a picture."""
    setup, _palette = dressed
    setup.open(
        SetupState(
            "light-frost",
            {"preset": "default", "knobs": {}},
            sanitize_layout(None),
            {"clock_24h": False},
            [],
            monday_of("2026-09-23"),
        ),
        DONE,
    )
    qapp.processEvents()
    assert setup.done_preview.width() == COLOUR_THUMB
    assert not setup.done_preview.pixmap().isNull()
    assert setup.done_preview.isVisibleTo(setup)
