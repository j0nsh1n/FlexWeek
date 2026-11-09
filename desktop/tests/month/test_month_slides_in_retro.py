"""In Retro, Month slides in over the dimmed desk as Settings does, and slides away the same way."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from copy import deepcopy

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractButton, QApplication

    import desktop.native.motion as motion
    import desktop.native.window as window_module
    from desktop.native.motion import OVER_MS, duration
    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import window  # noqa: F401
    from desktop.tests.month.support_retro_slide import (
        in_design,
        month_arrives,
        month_board,
        month_from_the_engine,
        month_is_live,
        nothing_left_over,
        pictures_over,
        press,
        settle_everything,
        slide_in_progress,
        watch,
    )
    from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-retro-month-slide-test"])


def test_in_retro_month_slides_in_over_the_dimmed_desk(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    in_design(qapp, window, "retro")
    seen = watch(window, monkeypatch)
    page = window._week_page
    press(qapp, window, "viewMonth", lambda: month_is_live(window))
    length = duration(OVER_MS, "normal")
    slide_frames = [frame for frame in seen.with_slide() if frame.total == length]
    assert slide_frames, "a picture of the month slides in, as long as Settings' slide"
    first, last = slide_frames[0], slide_frames[-1]
    assert first.slides == [page.width()] and first.dims == [0.0], "it starts off the right edge, undimmed"
    assert first.fades == 1, "the desk stays under it as a picture"
    mid = [frame for frame in slide_frames if 0 < frame.slides[0] < page.width()]
    assert mid and all(0 < frame.dims[0] < 1 for frame in mid if frame.dims[0] != 0.0), "dimming as it moves"
    assert last.slides == [0] and last.dims == [1.0], "it lands at the left edge with the desk fully dimmed"
    assert month_is_live(window)
    nothing_left_over(window)


def test_the_pictures_let_keys_and_clicks_through(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    in_design(qapp, window, "retro")
    real_run = motion._run
    checked: list[bool] = []

    def spy(owner, total, step, done):  # type: ignore[no-untyped-def]
        real_run(owner, total, step, done)
        slides, fades, dims = pictures_over(window._week_page)
        if dims:
            transparent = Qt.WidgetAttribute.WA_TransparentForMouseEvents
            checked.append(all(item.testAttribute(transparent) for item in (*slides, *fades, *dims)))

    monkeypatch.setattr(motion, "_run", spy)
    press(qapp, window, "viewMonth", lambda: month_is_live(window))
    assert checked and all(checked), "the slide, the desk picture and the dim pass the pointer through"


def test_in_retro_leaving_month_for_week_slides_it_away_the_same_way(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    in_design(qapp, window, "retro")
    press(qapp, window, "viewMonth", lambda: month_is_live(window))
    seen = watch(window, monkeypatch)
    page = window._week_page
    press(qapp, window, "viewWeek", lambda: window.session.planner_view == "week")
    length = duration(OVER_MS, "normal")
    frames = seen.slid(length)
    assert frames, "the month slides away, as long as Settings' slide"
    first, last = frames[0], frames[-1]
    assert first.offsets == [0] and first.dims == [1.0], "the month starts in place, the desk dimmed"
    assert last.offsets == [page.width()] and last.dims == [0.0], "gone off the right, the week bright"
    assert not month_board(window).isVisible(), "the live week is under it"
    nothing_left_over(window)


@pytest.mark.parametrize(("start", "target"), [("week", "day"), ("day", "week")])
def test_in_retro_day_and_week_still_crossfade(
    qapp: QApplication,
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    start: str,
    target: str,
) -> None:
    in_design(qapp, window, "retro")
    if start == "day":
        press(qapp, window, "viewDay", lambda: window.session.planner_view == "day")
    seen = watch(window, monkeypatch)
    button = "viewDay" if target == "day" else "viewWeek"
    press(qapp, window, button, lambda: window.session.planner_view == target)
    assert seen.with_fade(), "the old view is a picture fading away"
    assert seen.with_dim() == [] and seen.with_slide() == [], "no dim and no slide between Day and Week"
    nothing_left_over(window)


def test_another_design_keeps_its_month_crossfade(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Mission has no rail, so Week and Month only fade through; Today's app slides (test_motion_0185)."""
    in_design(qapp, window, "mission")
    seen = watch(window, monkeypatch)
    press(qapp, window, "viewMonth", lambda: window.session.planner_view == "month")
    assert seen.with_fade(), "the week fades through to the month"
    assert seen.with_dim() == [] and seen.with_slide() == []
    seen.frames.clear()
    press(qapp, window, "viewWeek", lambda: window.session.planner_view == "week")
    assert seen.with_fade() and seen.with_dim() == [] and seen.with_slide() == []
    nothing_left_over(window)


@pytest.mark.parametrize("level", ["reduce", "off"])
def test_under_reduce_and_off_retro_month_does_not_slide(
    qapp: QApplication,
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    level: str,
) -> None:
    in_design(qapp, window, "retro", level)
    seen = watch(window, monkeypatch)
    held: list[object] = []
    real_hold = window_module.hold_picture

    def recording(*args, **kwargs):  # type: ignore[no-untyped-def]
        held.append(real_hold(*args, **kwargs))
        return held[-1]

    monkeypatch.setattr(window_module, "hold_picture", recording)
    press(qapp, window, "viewMonth", lambda: month_is_live(window))
    assert seen.with_dim() == [] and seen.with_slide() == [], "nothing travels or dims"
    if level == "off":
        assert held and all(picture is None for picture in held), "Off: no picture is taken at all"
        assert seen.frames == [], "Off: nothing animates, the month is simply there"
    else:
        assert seen.with_fade(), "Reduce: the week fades through to the month"
    press(qapp, window, "viewWeek", lambda: window.session.planner_view == "week")
    assert seen.with_dim() == [] and seen.with_slide() == []
    nothing_left_over(window)


def test_a_month_that_arrives_mid_slide_is_taken_again_on_the_moving_picture(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    in_design(qapp, window, "retro")
    data = deepcopy(month_from_the_engine(qapp, window))
    # An empty reply can look exactly like the loading grid. A deadline makes the arrival visible.
    day = next(day for day in data["days"] if day["in_month"])
    day["due_ids"] = ["slide-essay"]
    data["deadlines"] = [{"id": "slide-essay", "title": "Essay due", "due": day["date"]}]
    # The engine has not answered yet when the slide starts, as on a real machine.
    monkeypatch.setattr(window.session, "_fetch_month", lambda: None)
    window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(qapp, lambda: slide_in_progress(window) is not None)
    moving = slide_in_progress(window)
    assert moving is not None and window.session.month_data is None
    key = moving.pixmap().cacheKey()
    month_arrives(window, data)
    # The repaint waits one turn of the event loop, for the month to scroll to its first row.
    qapp.processEvents()
    qapp.processEvents()
    assert motion.busy() and slide_in_progress(window) is moving, "the slide is still running"
    assert moving.pixmap().cacheKey() != key, "the moving picture was taken again"
    settle_everything(qapp, window)
    assert month_is_live(window)
    nothing_left_over(window)


def test_a_month_that_arrives_after_landing_shows_live(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    in_design(qapp, window, "retro")
    data = month_from_the_engine(qapp, window)
    # An error inside a Qt slot only reaches the excepthook: a retake aimed at a deleted picture.
    raised: list[object] = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, error, trace: raised.append(error))
    monkeypatch.setattr(window.session, "_fetch_month", lambda: None)
    window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(qapp, lambda: slide_in_progress(window) is not None)
    settle_everything(qapp, window)
    board = month_board(window)
    assert board is not None and board.isVisible() and board.canvas.cells, "the full grid is already drawn"
    assert not board.warning.isVisible(), "loading does not change the grid's height"
    month_arrives(window, data)
    qapp.processEvents()
    wait_until(qapp, lambda: not board.warning.isVisible())
    settle_everything(qapp, window)
    assert board.canvas.cells and not board.warning.isVisible(), "the live month shows"
    assert raised == [], "no retake is tried once the slide has landed"
    nothing_left_over(window)
