"""Shared set-up for the Clay deck's tests: the deck shown on its own at a fixed size, the lookups into
its row of cards, and the pointer and wheel moves a student makes on it. Not a test module."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractAnimation, QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.native.hours.canvas import HoursCanvas  # noqa: E402
from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.clay import ClayDeckView, slots  # noqa: E402
from desktop.native.layouts.registry import options_for, tokens_for  # noqa: E402
from desktop.native.look import design_look  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(autouse=True)
def still() -> Iterator[None]:
    """The row where each move ends, unless a test asks for motion; the level is put back after."""
    was = motion.app_level()
    motion.apply_ui_effects("off")
    yield
    motion.apply_ui_effects(was)


def shown(
    qapp: QApplication,
    *,
    tab: str = "week",
    day: int = 3,
    blocks: list[dict] | None = None,
    pack: str = "light-frost",
    **chosen: str,
) -> ClayDeckView:
    options = {**options_for(None, "clay"), **chosen}
    palette, _look = design_look(options["look"], pack, False, None)
    week = build_week(WEEK, BLOCKS if blocks is None else blocks, HOMEWORK, TRACE)
    view = ClayDeckView()
    view.resize(1280, 764)
    view.show_week(Scene(
        week, 3, minute_of("13:40"), options,
        tokens_for("clay", options["look"], palette),
        surface=tab, iso_day=week.date_of(day).isoformat(),
    ))
    view.show()
    qapp.processEvents()
    return view


def again(qapp: QApplication, view: ClayDeckView, **changed: object) -> None:
    previous = view.scene
    fields = {
        "week": previous.week, "today": previous.today, "minute": previous.minute,
        "options": previous.options, "tokens": previous.tokens, "surface": previous.surface,
        "iso_day": previous.iso_day, **changed,
    }
    view.show_week(Scene(**fields))
    qapp.processEvents()


def front(view: ClayDeckView) -> HoursCanvas:
    surfaces = view.hours_surfaces()
    assert isinstance(surfaces[0], HoursCanvas)
    return surfaces[0]


def visible_scrolls(view: ClayDeckView) -> list[HoursScroll]:
    return [scroll for scroll in view.findChildren(HoursScroll) if scroll.isVisible()]


def pairs(view: ClayDeckView) -> list[tuple[str, str]]:
    summary = view.findChild(QWidget, "claySummary")
    names = [item.text() for item in summary.findChildren(QLabel, "claySumName")]
    values = [item.text() for item in summary.findChildren(QLabel, "claySumLength")]
    return list(zip(names, values, strict=True))


def wheel(target: QWidget, notch: int) -> None:
    """One notch of the wheel over the middle of `target`, away from the student (1) or toward (-1),
    arriving at the window as a real one does. Qt passes a wheel that a widget ignores on to its
    parents only when it came from the system, so one sent to `target` alone never reached the row."""
    window = target.window()
    at = target.mapTo(window, target.rect().center())
    QTest.wheelEvent(window.windowHandle(), QPointF(at), QPoint(0, 120 * notch))


def landed(qapp: QApplication, view: ClayDeckView) -> None:
    """Wait for the row's slide to finish by itself."""
    wait_until(
        qapp,
        lambda: view.row._slide.state() == QAbstractAnimation.State.Stopped,
        what="the row finishing its slide",
    )


def drag(target: QWidget, start: QPoint, by: QPoint, *, let_go: bool = True) -> None:
    """Press at `start` on `target` and travel `by` in six moves, as a hand does, then let go unless
    asked not to. Aimed at points fixed in the window, as a real pointer's are, though the row moves
    the card under it; QTest sends each to `target`, the widget a real press would keep."""
    window = target.window()
    at = target.mapTo(window, start)
    QTest.mousePress(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 7):
        on = at + QPoint(round(by.x() * step / 6), round(by.y() * step / 6))
        QTest.mouseMove(target, target.mapFrom(window, on))
    if let_go:
        let_go_at(target, at + by)


def let_go_at(target: QWidget, at: QPoint) -> None:
    """Let go of `target` at a point in its window."""
    local = target.mapFrom(target.window(), at)
    QTest.mouseRelease(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)


def card_of(view: ClayDeckView, day: int) -> QWidget:
    return view.findChild(HoursCanvas, f"clayPeek{day}").parentWidget()


def at_slots(view: ClayDeckView, day: int) -> bool:
    """Whether every neighbour is where the row puts it with `day` in front: nothing left mid-drag."""
    row = view.row
    found = slots(row.width(), row.height(), day, row.scale, wide=row._open)
    return all(card_of(view, other).geometry() == found[other].toRect() for other in range(7) if other != day)


def slide_pictures(row) -> tuple[dict[int, object], dict[int, object]]:
    """Start and end pictures the row keeps while it slides, whatever shape it stores them in."""
    snaps = row._snaps
    assert snaps is not None
    if isinstance(snaps, tuple) and len(snaps) == 2:
        return snaps[0], snaps[1]
    starts, ends = {}, {}
    for day, pair in snaps.items():
        if isinstance(pair, tuple) and len(pair) == 2:
            starts[day], ends[day] = pair
        else:
            starts[day] = pair
    return starts, ends


def drawn_at(view: ClayDeckView, share: float, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every picture the sliding row draws with the slide held at `share`: which day and end it is,
    its logical size, where it is drawn, its opacity and the clip it is drawn through."""
    row = view.row
    assert row._slide.state() != QAbstractAnimation.State.Stopped
    row._slide.pause()
    starts, ends = slide_pictures(row)
    keys = {shot.picture.cacheKey(): (day, "start") for day, shot in starts.items()}
    keys.update({shot.picture.cacheKey(): (day, "end") for day, shot in ends.items()})
    seen: list[dict] = []
    original = type(row)._blit

    def record(self, painter, picture, target):
        ratio = picture.devicePixelRatio() or 1.0
        day, end = keys[picture.cacheKey()]
        seen.append({
            "day": day, "end": end, "opacity": painter.opacity(), "target": QRectF(target),
            "size": (picture.width() / ratio, picture.height() / ratio),
            "clip": painter.clipPath().boundingRect(), "card": QRectF(self._rects[day]),
        })
        original(self, painter, picture, target)

    monkeypatch.setattr(type(row), "_blit", record)
    row._slid(share)
    row.repaint()
    return seen


def stop_slide(row) -> None:
    row._slide.stop()
    row._land()


def slide_week(qapp: QApplication) -> ClayDeckView:
    """Week with the row part-way into its slide to Friday."""
    view = shown(qapp)
    motion.apply_ui_effects("normal")
    view.findChild(QPushButton, "clayAhead").click()
    return view


def slide_day(qapp: QApplication) -> ClayDeckView:
    """Day with the row sliding from Thursday to Friday."""
    view = shown(qapp, tab="day")
    motion.apply_ui_effects("normal")
    scene = view.scene
    view.show_week(Scene(
        scene.week, scene.today, scene.minute, scene.options, scene.tokens,
        surface="day", iso_day=scene.week.date_of(4).isoformat(),
    ))
    return view


def takeover_between_the_pictures(view: ClayDeckView, monkeypatch: pytest.MonkeyPatch) -> None:
    """Before the window only the start picture shows, after it only the end, so two layouts overlap
    for a few frames and not the whole slide. Halfway through the window (a smoothstep at its middle)
    each has half."""
    early = drawn_at(view, 0.1, monkeypatch)
    monkeypatch.undo()
    late = drawn_at(view, 0.6, monkeypatch)
    monkeypatch.undo()
    middle = drawn_at(view, 0.35, monkeypatch)
    monkeypatch.undo()
    assert early and {item["end"] for item in early} == {"start"}
    assert {item["opacity"] for item in early} == {1.0}
    assert late and {item["end"] for item in late} == {"end"}
    assert {item["opacity"] for item in late} == {1.0}
    assert {item["end"] for item in middle} == {"start", "end"}
    assert {round(item["opacity"], 3) for item in middle} == {0.5}
    stop_slide(view.row)
