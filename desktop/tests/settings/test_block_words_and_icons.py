"""What a block writes in the room it has: the title is cut first, a narrow block keeps a whole time
range or its start and never a cut time, and the icon is left out where it would cost that time line.
Which icon each category draws. Whether an icon reads against its block is judged on the pictures in
pictures/screens_settings_tokens.py.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QApplication

from desktop.native import icons
from desktop.native.calendar import CATEGORIES
from desktop.native.hours import canvas as canvas_module
from desktop.native.hours.canvas import (
    INLINE_GAP,
    BlockPainter,
    Drawn,
    _book_room,
    block_layout,
)
from desktop.native.hours.geometry import Span
from desktop.native.layouts.clay import ClayPainter
from desktop.native.layouts.mission import MissionPainter
from desktop.native.layouts.registry import MATCH, tokens_for
from desktop.native.look import LOOK_BASES, resolved_palette, sanitize_look
from desktop.native.weekmodel import clock_label, range_label
from desktop.tests.test_hours_painter import Said, three_days, words_on
from desktop.tests.window_support import qapp  # noqa: F401


def time_line(metrics: QFontMetricsF, width: float, start: int, end: int) -> str | None:
    """The whole range if it fits; else the start; never a time cut part-way."""
    times = range_label(start, end)
    if metrics.horizontalAdvance(times) <= width:
        return times
    start_text = clock_label(start)
    if metrics.horizontalAdvance(start_text) <= width:
        return start_text
    return None


def laid_out(qapp: QApplication, title: str, room_for: str, lines: int):  # noqa: F811
    font = QFont(qapp.font())
    metrics = QFontMetricsF(font)
    room = QRectF(0, 0, metrics.horizontalAdvance(room_for) + 1, metrics.lineSpacing() * lines + 1)
    drawn = Drawn("block", title, "class", False, Span(0, 480, 540), 0, 1)
    return block_layout(drawn, font, font, room, book=True), metrics, room.width()


@pytest.mark.parametrize(
    ("title", "room_for", "lines"),
    [
        ("School", "School", 1),
        ("Piano lesson", "Piano lesson", 1),
        ("Swimming gala", "Swimming", 2),
        ("Science poster", "Science…", 1),
    ],
)
def test_the_icon_gives_way_where_it_would_cost_the_name(
    qapp: QApplication,  # noqa: F811
    title: str,
    room_for: str,
    lines: int,
) -> None:
    """The title is cut first; a narrow block keeps a whole range or start, never a cut time. The icon
    is left out when it would cost that time line."""
    lay, metrics, width = laid_out(qapp, title, room_for, lines)
    wanted = time_line(metrics, width, 480, 540)
    times = [line.text for line in lay if not line.title]
    assert wanted is not None
    assert times == [wanted]
    assert not any("…" in line.text and not line.title for line in lay)
    if lines == 1:
        assert not any(line.book for line in lay)


@pytest.mark.parametrize("room_for", ["School and more", "Math works"])
def test_the_icon_stays_where_it_costs_the_name_nothing(qapp: QApplication, room_for: str) -> None:  # noqa: F811
    """One line of height keeps the time, not an icon plus a cut name."""
    title = "School" if room_for.startswith("School") else "Math worksheet"
    lay, metrics, width = laid_out(qapp, title, room_for, 1)
    wanted = time_line(metrics, width, 480, 540)
    assert [line.text for line in lay if not line.title] == [wanted]
    assert not any("…" in line.text and not line.title for line in lay)


LIGHT_AND_HIGH_CONTRAST = [None, {"preset": "high-contrast", "knobs": {}}]


def dinner_on_the_week(monkeypatch: pytest.MonkeyPatch, look: dict | None, minutes: int, hour_px: int):
    """What a meals block of `minutes` at 18:30 writes and draws on a week of `hour_px` pixels an hour."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    drew: list[str] = []
    real = icons.pixmap

    def pixmap(name: str, *rest: object):
        drew.append(name)
        return real(name, *rest)

    monkeypatch.setattr(icons, "pixmap", pixmap)
    palette = resolved_palette("system", False, look)
    dinner = {
        "id": "dinner",
        "title": "Dinner",
        "kind": "locked",
        "category": "meals",
        "days": [0],
        "start": "18:30",
        "duration_min": minutes,
    }
    # 132 pixels, the width of a day on the week at 1280 pixels across.
    canvas = three_days(blocks=(dinner,), palette=palette, hour_px=hour_px, column=132)
    canvas.set_painter(BlockPainter(palette, look))
    # The app's own text size at 1280 pixels across: Inter at 13 points, and High contrast's Large.
    canvas.setFont(QFont("Inter", 15.5 if look else 13))
    Said.words = []
    canvas.grab()
    return words_on(canvas, "dinner", 0), drew


@pytest.mark.parametrize("look", LIGHT_AND_HIGH_CONTRAST, ids=["light", "high-contrast"])
def test_a_half_hour_writes_its_start_time_rather_than_its_icon(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    look: dict | None,
) -> None:
    """A half-hour Dinner at 48 pixels an hour keeps the whole range."""
    words, icons_drawn = dinner_on_the_week(monkeypatch, look, 30, 48)
    assert words == [range_label(18 * 60 + 30, 19 * 60)]
    assert icons_drawn == []


@pytest.mark.parametrize("look", LIGHT_AND_HIGH_CONTRAST, ids=["light", "high-contrast"])
def test_a_block_with_room_for_the_name_the_time_and_the_icon_has_all_three(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    look: dict | None,
) -> None:
    words, icons_drawn = dinner_on_the_week(monkeypatch, look, 60, 96)
    assert words[0] == "Dinner" and "18:30–19:30" in words
    assert icons_drawn == ["clock"]


def half_hour_layout(qapp: QApplication, width: float):  # noqa: F811
    """A one-line half-hour Dinner with the icon offered, in a room `width` wide."""
    font = QFont(qapp.font())
    metrics = QFontMetricsF(font)
    drawn = Drawn("dinner", "Dinner", "meals", False, Span(0, 18 * 60 + 30, 19 * 60), 0, 1)
    room = QRectF(0, 0, width, metrics.lineSpacing() + 1)
    return block_layout(drawn, font, font, room, book=True)


def half_hour_widths(qapp: QApplication) -> tuple[float, float, float]:  # noqa: F811
    """The room "Dinner 18:30" takes, "Dinner" alone, and the icon."""
    metrics = QFontMetricsF(QFont(qapp.font()))
    name = metrics.horizontalAdvance("Dinner")
    return name + INLINE_GAP + metrics.horizontalAdvance("18:30"), name, _book_room(metrics)


def wanted_time_line(qapp: QApplication, width: float) -> str | None:  # noqa: F811
    return time_line(QFontMetricsF(QFont(qapp.font())), width, 18 * 60 + 30, 19 * 60)


def test_a_line_with_room_for_the_name_and_its_time_but_not_the_icon_too_says_the_time(
    qapp: QApplication,  # noqa: F811
) -> None:
    both, _name, _icon = half_hour_widths(qapp)
    lay = half_hour_layout(qapp, both + 1)
    assert [line.text for line in lay] == [wanted_time_line(qapp, both + 1)]
    assert not any(line.book for line in lay)


def test_a_line_with_room_for_the_name_and_the_icon_but_no_time_keeps_the_time_line(
    qapp: QApplication,  # noqa: F811
) -> None:
    """The time line beats the icon-plus-name layout on a one-line block."""
    _both, name, icon = half_hour_widths(qapp)
    lay = half_hour_layout(qapp, name + icon + 1)
    assert [line.text for line in lay] == [wanted_time_line(qapp, name + icon + 1)]
    assert not any(line.title for line in lay)


def test_a_line_with_room_for_the_name_alone_writes_the_time_line(qapp: QApplication) -> None:  # noqa: F811
    _both, name, _icon = half_hour_widths(qapp)
    lay = half_hour_layout(qapp, name + 1)
    assert [line.text for line in lay] == [wanted_time_line(qapp, name + 1)]


def test_a_line_with_room_for_the_name_the_time_and_the_icon_still_writes_one_time_line(
    qapp: QApplication,  # noqa: F811
) -> None:
    """One line of height still keeps the range, not name + start + icon."""
    both, _name, icon = half_hour_widths(qapp)
    lay = half_hour_layout(qapp, both + icon + 1)
    assert [line.text for line in lay] == [wanted_time_line(qapp, both + icon + 1)]


def painter_for(design: str, palette: dict):
    if design == "classic":
        return BlockPainter(palette)
    if design == "mission":
        return MissionPainter(tokens_for("mission", MATCH, palette))
    return ClayPainter(tokens_for("clay", MATCH, palette), full=True)


@pytest.mark.parametrize(
    ("category", "wanted"),
    [
        ("class", "school"),
        ("assignments", "book-open"),
        ("study", "pencil"),
        ("exercise", "target"),
        ("extra", "sparkles"),
        ("meals", "clock"),
        ("sleep", "moon"),
        # Free time has none: the mock-up draws no icon on it.
        ("free", None),
    ],
)
@pytest.mark.parametrize("design", ["classic", "mission", "clay"])
def test_each_category_paints_its_approved_icon(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    wanted: str | None,
    design: str,
) -> None:
    palette = resolved_palette("light-frost", False, None)
    painter = painter_for(design, palette)
    drawn = Drawn("test", "School", category, False, Span(0, 480, 660), 0, 1)
    fill, ink, _outline, edge = painter.fills(drawn)
    used: list[str] = []
    original = icons.pixmap

    def record(name, colour, *args):
        used.append(name)
        return original(name, colour, *args)

    monkeypatch.setattr(icons, "pixmap", record)
    picture = QImage(500, 300, QImage.Format.Format_ARGB32)
    picture.fill(fill)
    paint = QPainter(picture)
    paint.setFont(QFont("Inter", 12))
    try:
        painter.words(paint, QRectF(0, 0, 480, 280), drawn, ink, QRectF(0, 0, 500, 300), fill, edge)
    finally:
        paint.end()
    if wanted is None:
        assert used == []
    else:
        assert wanted in used, used


@pytest.mark.parametrize(
    "look_name",
    ["light", "dark", "high-contrast", "slate", "nocturne", "paper", "ink", "terminal", "poster", "pastel"],
)
@pytest.mark.parametrize("style", ["edge", "filled", "outline", "none"])
def test_only_free_time_has_no_icon_colour_in_every_look_and_block_style(
    qapp: QApplication,  # noqa: F811
    look_name: str,
    style: str,
) -> None:
    """Free time has no icon; every other category has one in every look and block style."""
    pack, preset = LOOK_BASES[look_name]
    look = sanitize_look({"preset": preset, "knobs": {"blocks": style}})
    palette = resolved_palette(pack, False, look)
    painter = BlockPainter(palette, look)
    for category in CATEGORIES:
        drawn = Drawn("test", "School", category, False, Span(0, 480, 660), 0, 1)
        fill, ink, _outline, edge = painter.fills(drawn)
        colour = painter._book_colour(drawn, ink, fill, edge)
        assert (colour is None) == (category == "free"), (look_name, style, category)
