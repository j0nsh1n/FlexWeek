"""Copy and paste of blocks: the system clipboard is left alone, a paste onto the same time lands on top
as a drag would, a full week refuses one more, homework keeps its assignment, and the preview keeps a
block that lands on another checked."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.reuse import row_conflict
from desktop.native.widgets import PreviewDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light, window  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_copy_and_paste_do_not_use_the_system_clipboard(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    clip = QGuiApplication.clipboard()
    clip.setText("sentinel-os")
    assert session.copy_selected()
    assert clip.text() == "sentinel-os"
    assert session.clipboard is not None
    assert session.clipboard["label"] == "Soccer"
    rows = session.paste_proposals(1, None)
    assert rows is not None
    assert rows[0]["day"] == 1
    assert rows[0]["block"]["start"] == "16:00"
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy and len(session.blocks) == 2)
    titles = sorted(block["title"] for block in session.blocks)
    assert titles == ["Soccer", "Soccer"]
    days = {tuple(block["days"]) for block in session.blocks}
    assert days == {(0,), (1,)}
    assert clip.text() == "sentinel-os"


def test_a_paste_onto_the_same_time_lands_on_top_of_the_block_as_a_drag_would(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    session.copy_selected()
    rows = session.paste_proposals(0, "16:00")
    assert rows is not None
    assert row_conflict(rows[0], rows, session.blocks) == "Soccer"
    assert rows[0]["checked"]
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy and len(session.blocks) == 2)
    assert [(block["days"], block["start"]) for block in session.blocks] == [([0], "16:00")] * 2


def test_a_hundredth_block_refuses_a_paste(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    session.copy_selected()
    session.blocks = list(session.blocks) + [
        {
            "id": f"pad-{index}",
            "title": f"Pad {index}",
            "kind": "locked",
            "duration_min": 15,
            "days": [6],
            "start": "06:00",
        }
        for index in range(99)
    ]
    rows = session.paste_proposals(1, None)
    assert rows is not None
    assert session.confirm_preview(rows, label="the copied block") is False
    assert "100 blocks" in session.message


def test_pasted_homework_keeps_its_assignment_and_no_more_time_than_remains(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": due,
            "estimate_min": 90,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and "essay" in session.assignments)
    homework = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    homework["duration_min"] = 30
    session._touch("editing Essay")
    session.save()
    wait_until(qapp, lambda: not session.busy and session.remaining_for("essay") >= 30)
    homework = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.select_block(homework["id"], homework["days"][0])
    session.copy_selected()
    first = list(session.clipboard["items"])
    session.copy_selected()
    session.clipboard["items"] = first + list(session.clipboard["items"])
    rows = session.paste_proposals(3, None)
    assert rows is not None
    usable = [row for row in rows if row["checked"]]
    assert [row["block"]["duration_min"] for row in usable] == [30, 30]
    assert all(row["block"]["assignment_id"] == "essay" for row in usable)
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy)
    ids = {block.get("assignment_id") for block in session.blocks if block.get("assignment_id")}
    assert ids == {"essay"}


def test_the_paste_preview_keeps_a_block_that_lands_on_another_checked_and_says_so(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    session.copy_selected()
    rows = session.paste_proposals(0, "16:00")
    assert rows is not None
    dialog = PreviewDialog(
        window,
        "Preview paste",
        "Nothing changes until you save this preview.",
        rows,
        session.blocks,
    )
    try:
        dialog.show()
        wait_until(qapp, dialog.isVisible)
        box = dialog.findChild(QCheckBox, "previewInclude0")
        assert box is not None
        assert box.isChecked() is True
        assert dialog.confirm.isEnabled()
        assert "Soccer is at that time too" in dialog.findChild(QLabel, "previewDetail0").text()
    finally:
        dialog.close()
        free(dialog)
