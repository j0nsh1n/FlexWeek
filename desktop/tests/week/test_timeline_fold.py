"""Timeline's fold between the two pages on Week: a handle in the row of day names, dragged or stepped
with the arrows and keys, that counts each page, keeps a day on each and says what it would make."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.layouts import timeline  # noqa: E402
from desktop.native.widgets import use_app_style  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, block  # noqa: E402
from desktop.tests.week.support_timeline import (  # noqa: E402
    Said,
    canvas,
    drag_fold,
    handle_of,
    kept_by,
    over,
    pages,
    shown,
    tap,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-timeline-test"])
    use_app_style(application)
    yield application


def test_the_folds_handle_sits_in_the_row_of_day_names_and_counts_each_page(qapp: QApplication) -> None:
    view = shown(qapp)
    handle = handle_of(view)
    heads = view.findChild(QWidget, "timelineHeads")
    assert handle.text() == "‹ 3 | 4 ›"
    assert handle.toolTip() == "Drag to move days between the pages"
    assert handle.parentWidget() is heads, "in the row of day names, not on the hours"
    assert pages(view) == ((0, 1, 2), (3, 4, 5, 6))
    assert view.findChildren(QWidget, "timelineFold") == [handle]
    day = shown(qapp, "day")
    assert [found for found in day.findChildren(QWidget, "timelineFold") if found.isVisible()] == []


@pytest.mark.parametrize(
    ("day", "share", "left"),
    [
        # Past Wednesday's middle, Wednesday goes to the right page; short of it, it stays.
        (2, 0.4, 2),
        (2, 0.6, 3),
        # Thursday comes to the left page once its middle is passed, and not before.
        (3, 0.4, 3),
        (3, 0.6, 4),
        # Past Monday's middle the left page would be empty: it keeps one day, and so does the right.
        (0, 0.1, 1),
        (6, 0.9, 6),
    ],
)
def test_a_drag_moves_the_fold_to_the_day_edge_nearest_the_pointer(
    qapp: QApplication, day: int, share: float, left: int
) -> None:
    view = shown(qapp)
    kept = kept_by(view)
    words = drag_fold(qapp, view, over(view, day, share), held=lambda: handle_of(view).text())
    assert words == f"‹ {left} | {7 - left} ›", "the counts follow the pointer while it drags"
    assert pages(view) == (tuple(range(left)), tuple(range(left, 7)))
    assert kept == ([] if left == 3 else [("fold", str(left))])
    assert handle_of(view).text() == f"‹ {left} | {7 - left} ›"


def test_the_arrows_and_the_left_and_right_keys_move_one_day_across(qapp: QApplication) -> None:
    view = shown(qapp)
    kept = kept_by(view)
    assert tap(qapp, view, "back") == "‹ 2 | 5 ›"
    assert pages(view) == ((0, 1), (2, 3, 4, 5, 6))
    assert tap(qapp, view, "forward") == "‹ 3 | 4 ›"
    assert tap(qapp, view, "forward") == "‹ 4 | 3 ›"
    assert tap(qapp, view, "middle") == "‹ 4 | 3 ›", "the counts themselves are not a button"
    handle = handle_of(view)
    assert handle.focusPolicy() & Qt.FocusPolicy.TabFocus, "reached with Tab"
    QTest.keyClick(handle, Qt.Key.Key_Left)
    assert handle_of(view).text() == "‹ 3 | 4 ›"
    QTest.keyClick(handle_of(view), Qt.Key.Key_Right)
    assert handle_of(view).text() == "‹ 4 | 3 ›"
    assert pages(view) == ((0, 1, 2, 3), (4, 5, 6))
    assert kept == [("fold", value) for value in ("2", "3", "4", "3", "4")]


@pytest.mark.parametrize(
    ("left", "where", "key", "far"), [(1, "back", "Left", (0, 0.05)), (6, "forward", "Right", (6, 0.95))]
)
def test_the_fold_keeps_a_day_on_each_page(
    qapp: QApplication, left: int, where: str, key: str, far: tuple[int, float]
) -> None:
    """1 | 6 and 6 | 1 are the ends: never 0 | 7."""
    view = shown(qapp, fold=str(left))
    kept = kept_by(view)
    words = f"‹ {left} | {7 - left} ›"
    assert handle_of(view).text() == words
    assert pages(view) == (tuple(range(left)), tuple(range(left, 7)))
    handle = handle_of(view)
    across = 3 if where == "back" else handle.width() - 4
    QTest.mouseClick(handle, Qt.MouseButton.LeftButton, pos=QPoint(across, handle.height() // 2))
    QTest.keyClick(handle_of(view), getattr(Qt.Key, f"Key_{key}"))
    drag_fold(qapp, view, over(view, *far))
    assert handle_of(view).text() == words
    assert pages(view) == (tuple(range(left)), tuple(range(left, 7)))
    assert kept == []


def test_while_dragging_the_fold_names_each_page_it_would_make(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = shown(qapp)
    hours = canvas(view)
    hours.reveal(2, 21 * 60, 23 * 60)
    qapp.processEvents()

    def held() -> list[str]:
        monkeypatch.setattr(timeline, "QPainter", Said)
        Said.words = []
        hours.repaint()
        monkeypatch.undo()
        return list(Said.words)

    words = drag_fold(qapp, view, over(view, 2, 0.3), held=held)
    assert "Mon–Tue | Wed–Sun" in words, "the pages the fold would make, named"
    monkeypatch.setattr(timeline, "QPainter", Said)
    Said.words = []
    hours.repaint()
    assert not any("|" in said for said in Said.words), "let go, the names go"


def test_at_one_day_on_the_left_the_weeks_figures_are_still_all_there(qapp: QApplication) -> None:
    view = shown(qapp, fold="1")
    stats = [item for item in view.findChildren(QLabel, "timelineStat") if item.isVisible()]
    assert [item.text() for item in stats] == ["3 h 15 min", "1 of 4", "1"]


def test_at_one_day_on_the_right_both_notes_and_every_due_line_are_listed(qapp: QApplication) -> None:
    # Two notes waiting, which side by side would be wider than the page.
    lab = block("lab-1", "flexible", [], None, 60, assignment_id="lab", title="Lab")
    due = {"id": "lab", "title": "Lab", "due": "2026-09-19T20:00", "completed": False}
    homework = {**HOMEWORK, "lab": due}
    view = shown(qapp, fold="6", blocks=[*BLOCKS, lab], homework=homework)
    notes = [chip for chip in view.findChildren(TrayChip) if chip.isVisible()]
    assert len(notes) == 2
    when = [item for item in view.findChildren(QLabel, "timelineDueWhen") if item.isVisible()]
    assert len(when) == 5

