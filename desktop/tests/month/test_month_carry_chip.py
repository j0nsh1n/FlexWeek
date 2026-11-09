"""Carrying a chip to another date on Month. These send Qt events, so they prove the rules; the rig
(scripts/rig/drive.py) carries chips with a real pointer on the real window and reads back what the
server saved."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from desktop.native.hours.hand import MoveDate, Verdict  # noqa: E402
from desktop.tests.month.support_month import Stage  # noqa: E402

REFUSED = "That ends after it is due, so it stayed where it was."


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-carry-test"])


def test_a_chip_carried_to_another_date_is_one_date_move(qapp: QApplication) -> None:
    stage = Stage(qapp)
    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-26"))
    assert stage.said == [MoveDate("essay-1", "2026-09-24", "2026-09-26")]
    assert stage.opened == []


def test_a_month_chip_puts_its_date_on_held_from_iso_not_category(qapp: QApplication) -> None:
    """Month's press builds Held with the cell ISO as the eighth positional value, after grab.
    That slot is from_iso. Category is empty here because Month does not pass one. If category
    sits before from_iso, the ISO fills category and the drop has no origin date."""
    stage = Stage(qapp)
    seen: list[tuple[str, str]] = []

    def look() -> None:
        held = stage.hand.preview_held()
        assert held is not None
        seen.append((held.from_iso, held.category))

    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-26"), look)
    assert seen == [("2026-09-24", "")]


def test_a_refused_date_shows_while_held_and_moves_nothing(qapp: QApplication) -> None:
    stage = Stage(qapp, lambda block_id, from_iso, to_iso: Verdict(to_iso < "2026-09-27", REFUSED))
    seen: list[tuple[str | None, bool | None]] = []

    def look() -> None:
        verdict = stage.hand.month_verdict
        seen.append((stage.hand.month_target, None if verdict is None else verdict.ok))

    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-28"), look)
    assert seen == [("2026-09-28", False)]
    assert stage.said == [("refused", REFUSED)]
    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-25"))
    assert stage.said[-1] == MoveDate("essay-1", "2026-09-24", "2026-09-25")


def test_a_chip_let_go_on_its_own_date_moves_nothing_and_a_clicked_one_opens_it(qapp: QApplication) -> None:
    stage = Stage(qapp)
    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-24"))
    assert stage.said == []
    at = stage.canvas.chip_point("school", "2026-09-22")
    stage.send(QEvent.Type.MouseButtonPress, at, True)
    stage.send(QEvent.Type.MouseButtonRelease, at, False)
    assert stage.said == []
    assert stage.opened == []
    assert stage.grid.canvas.selected == "2026-09-22"
    assert stage.grid.pane.heading.text() == "Tuesday 22 September"


def test_a_deadline_is_not_carried(qapp: QApplication) -> None:
    stage = Stage(qapp)
    box = next(
        box for chip, box in stage.canvas.chip_boxes(stage.canvas.index_of("2026-09-27"))[0] if chip.due
    )
    start = stage.canvas.mapToGlobal(box.center().toPoint())
    held: list[bool] = []
    stage.carry(start, stage.canvas.cell_point("2026-09-30"), lambda: held.append(stage.hand.busy))
    assert held == [False], "nothing is picked up: moving a deadline is editing the homework"
    assert stage.said == []


def test_a_dates_own_point_is_on_the_date_and_on_none_of_its_chips(qapp: QApplication) -> None:
    stage = Stage(qapp)
    canvas = stage.canvas
    for cell in canvas.cells:
        local = QPointF(canvas.mapFromGlobal(canvas.cell_point(cell.iso)))
        assert canvas.date_at(local) == cell.iso
        assert canvas._chip_at(local) is None, f"{cell.iso}'s point lands on a chip"


def test_the_words_held_over_a_refused_date_say_no_and_the_move_says_where_it_goes(
    qapp: QApplication,
) -> None:
    stage = Stage(qapp, lambda block_id, from_iso, to_iso: Verdict(to_iso < "2026-09-27", REFUSED))
    seen: list[tuple[str, bool]] = []
    label = stage.window.findChild(QWidget, "heldChip")

    def look() -> None:
        seen.append((label.text(), bool(label.property("refused"))))

    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-28"), look)
    stage.carry(stage.canvas.chip_point("essay-1", "2026-09-24"), stage.canvas.cell_point("2026-09-25"), look)
    assert seen == [(REFUSED, True), ("19:00 History essay → Fri 25 Sep", False)]
