# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import qapp, server, settled, signed_in, wait_until  # noqa: F401
from desktop.tests.test_drag_results import session_of, window  # noqa: F401


def _dialog() -> LateDialog:
    set_clock_24h(False)
    dialog = LateDialog(None, "Starting from 5:00 PM today (Monday).")
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [
                {"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}
            ],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    return dialog


def test_running_late_preview_shows_day_and_both_full_ranges(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    item = dialog.changes.item(0)
    assert item.text() == "Late test: Mon 4:45–5:45\u00a0PM → Mon 5:15–6:15\u00a0PM"
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Late test, moves from Monday 4:45 to 5:45\u00a0PM to Monday 5:15 to 6:15\u00a0PM"
    )
    assert dialog.summary.text() == "1 task moves"
    dialog.show_trace({"moves": [], "placed": [], "unplaced": [{"id": "lost", "title": "Lost"}]}, {})
    assert dialog.summary.text() == "Nothing needs to move."
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_names_and_bolds_a_changed_day(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    trace = {
        "moves": [
            {
                "block_id": "late-test",
                "from_day": 0,
                "from_start": "16:45",
                "to_day": 1,
                "to_start": "17:15",
            }
        ],
        "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}],
        "unplaced": [],
    }
    dialog.show_trace(trace, {"late-test": "Late test"})
    item = dialog.changes.item(0)
    assert "Tue" in item.text()
    assert "<b>Tue</b>" in dialog.changes.itemWidget(item).text()
    assert "different day" in item.data(Qt.ItemDataRole.AccessibleTextRole)
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_uses_singular_plural_and_omits_zero_counts(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                },
                {
                    "block_id": "other",
                    "from_day": 0,
                    "from_start": "18:00",
                    "to_day": 0,
                    "to_start": "18:15",
                },
            ],
            "placed": [
                {"id": "late-test", "title": "Late test", "duration_min": 60},
                {"id": "other", "title": "Other", "duration_min": 60},
            ],
            "unplaced": [{"id": "lost", "title": "Lost"}],
        },
        {"late-test": "Late test", "other": "Other"},
    )
    assert dialog.summary.text() == "2 tasks move"
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60}],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    assert dialog.summary.text() == "1 task moves"
    set_clock_24h(True)
    dialog.close()


def _row_labels(dialog: LateDialog) -> list[QLabel]:
    """The row widgets still alive: a cleared row's widget goes at the next event-loop turn."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return dialog.changes.findChildren(QLabel)


def _three_changes() -> dict:
    return {
        "moves": [
            {"block_id": "essay", "from_day": 3, "from_start": "19:00", "to_day": 3, "to_start": "19:30"},
            {"block_id": "poster", "from_day": None, "from_start": None, "to_day": 4, "to_start": "15:30"},
            {"block_id": "sheet", "from_day": None, "from_start": None, "to_day": 4, "to_start": "14:30"},
        ],
        "placed": [
            {"id": "essay", "title": "History essay", "duration_min": 60},
            {"id": "poster", "title": "Science poster", "duration_min": 60},
            {"id": "sheet", "title": "Math worksheet", "duration_min": 60},
        ],
        "unplaced": [],
    }


TITLES = {"essay": "History essay", "poster": "Science poster", "sheet": "Math worksheet"}


def test_running_late_preview_draws_each_change_once_with_its_title(qapp: QApplication) -> None:  # noqa: F811
    set_clock_24h(False)
    dialog = LateDialog(None, "History essay, 7:00 PM, moves 30 min later")
    dialog.show()
    dialog.show_trace(_three_changes(), TITLES)
    assert dialog.changes.count() == 3
    rows = [dialog.changes.item(index) for index in range(3)]
    labels = [dialog.changes.itemWidget(row) for row in rows]
    assert all(isinstance(label, QLabel) for label in labels)
    assert len(_row_labels(dialog)) == 3
    for row, label, title in zip(rows, labels, TITLES.values(), strict=True):
        assert row.text().startswith(title)
        assert title in label.text()
        assert title in row.data(Qt.ItemDataRole.AccessibleTextRole)
    assert rows[1].text() == "Science poster, placed Fri 3:30\u00a0PM"
    assert rows[1].data(Qt.ItemDataRole.AccessibleTextRole) == "Science poster, placed Friday 3:30\u00a0PM"
    assert rows[0].text() == "History essay: Thu 7–8\u00a0PM → Thu 7:30–8:30\u00a0PM"
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_does_not_paint_the_row_text_under_its_widget(qapp: QApplication) -> None:  # noqa: F811
    from PySide6.QtWidgets import QStyleOptionViewItem

    dialog = LateDialog(None, "")
    dialog.show_trace(_three_changes(), TITLES)
    delegate = dialog.changes.itemDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, dialog.changes.model().index(0, 0))
    assert option.text == ""
    assert dialog.changes.item(0).text() != ""
    dialog.close()


def test_running_late_second_preview_replaces_the_rows(qapp: QApplication) -> None:  # noqa: F811
    dialog = LateDialog(None, "")
    dialog.show()
    dialog.show_trace(_three_changes(), TITLES)
    dialog.show_trace(_three_changes(), TITLES)
    assert dialog.changes.count() == 3
    assert len(_row_labels(dialog)) == 3
    one = _three_changes()
    one["moves"] = one["moves"][:1]
    dialog.show_trace(one, TITLES)
    assert dialog.changes.count() == 1
    assert dialog.summary.text() == "1 task moves"
    dialog.close()


def test_running_late_rows_are_as_tall_as_their_words(qapp: QApplication) -> None:  # noqa: F811
    dialog = LateDialog(None, "")
    dialog.show()
    long_title = "A very long homework title that cannot fit on one line of the preview list " * 2
    trace = _three_changes()
    dialog.show_trace(trace, {**TITLES, "essay": long_title})
    first = dialog.changes.item(0)
    label = dialog.changes.itemWidget(first)
    assert first.sizeHint().height() >= label.heightForWidth(dialog.changes.viewport().width())
    assert first.sizeHint().height() > dialog.changes.item(1).sizeHint().height()
    dialog.close()


def test_running_late_summary_is_status_not_an_error(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    session.now_ms = lambda: int(thursday.timestamp() * 1000)
    # Running late moves what already has a time and never places homework that waits, so the
    # Math worksheet is given Thursday 4 PM first.
    math = session_of(window, "math")
    session.add_block({**math, "start": "16:00", "days": [3]})
    session.save()
    settled(qapp, session)
    seen: dict = {}

    def run(dialog: LateDialog) -> int:
        dialog.show()
        for press in ("first", "second"):
            dialog.preview_requested.emit()
            wait_until(qapp, lambda: session.late_preview is not None and not session.busy)
            qapp.processEvents()
            seen[press] = (
                dialog.summary.text(),
                dialog.summary.isVisibleTo(dialog),
                dialog.error.text(),
                dialog.changes.count(),
                len(_row_labels(dialog)),
                len(session.late_preview["trace"].get("moves") or []),
            )
        window._late_problem(dialog, "Choose 15, 30 or 60 minutes.")
        seen["problem"] = dialog.error.text()
        dialog.reject()
        return dialog.result()

    monkeypatch.setattr(LateDialog, "exec", run)
    window._open_late()
    for press in ("first", "second"):
        summary, shown, error, rows, labels, moves = seen[press]
        assert moves == 1
        assert shown
        assert summary == "1 task moves"
        assert error == ""
        assert rows == 1
        assert labels == 1
    assert seen["problem"] == "Choose 15, 30 or 60 minutes."


def _plan_at_monday_five(qapp: QApplication, server, username: str, *, everything: bool) -> list[dict]:
    session = signed_in(qapp, server.origin, username, create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    monday = datetime.fromisoformat(session.week_start)
    held = monday + timedelta(hours=17)
    session.now_ms = lambda: int(held.timestamp() * 1000)
    session.add_homework(
        {
            "id": "l12-floor-homework",
            "title": "L12 floor homework",
            "estimate_min": 60,
            "revision": 0,
            "due": (monday.date() + timedelta(days=3)).isoformat() + "T23:59",
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, session)
    session.solve(everything=everything)
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled(qapp, session)
    return [block for block in session.blocks if block.get("assignment_id") == "l12-floor-homework"]


def _assert_not_before_monday_five(blocks: list[dict]) -> None:
    for block in blocks:
        if not block.get("start"):
            continue
        day = min(block.get("days") or [0])
        hour, minute = map(int, block["start"].split(":"))
        assert (day, hour * 60 + minute) >= (0, 17 * 60), block


def test_plan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, server) -> None:
    blocks = _plan_at_monday_five(qapp, server, "l12_plan_floor", everything=False)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_replan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, server) -> None:
    blocks = _plan_at_monday_five(qapp, server, "l12_replan_floor", everything=True)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_running_late_buttons_share_one_left_edge(qapp: QApplication) -> None:  # noqa: F811
    from PySide6.QtWidgets import QPushButton

    dialog = LateDialog(None, "School")
    dialog.show()
    qapp.processEvents()
    preview = dialog.findChild(QPushButton, "latePreview")
    left = preview.mapTo(dialog, preview.rect().topLeft()).x()
    accept = dialog.accept_button.mapTo(dialog, dialog.accept_button.rect().topLeft()).x()
    assert accept == left
    dialog.close()


def test_only_a_times_own_am_pm_is_kept_with_it() -> None:
    from desktop.native.widgets import _unbroken_time

    assert _unbroken_time("PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM") == (
        "PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM"
    )
