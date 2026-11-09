"""Add and Edit homework, under Estimated time: "In one go" or "Spread over days" as a choice of the
homework, with a grey line saying what Plan will do with the values as they stand now. Saving with
Spread writes the homework as typed and its spread sessions, with no second sheet to answer."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.calendar import sunday_due
from desktop.native.controller import spread_ready_sentence
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.sheets.support_homework import TODAY, go_length
from desktop.tests.sheets.support_homework_week import (  # noqa: F401
    homework_window,
    opened_with,
    session_of,
    sessions_of,
    settled,
)
from desktop.tests.window_support import free, qapp  # noqa: F401

NOON = datetime(2026, 9, 14, 12, 0)


def host(*blocks: dict, selected_day: str = "") -> QWidget:
    parent = QWidget()
    parent.session = SimpleNamespace(  # type: ignore[attr-defined]
        now_ms=lambda: int(NOON.timestamp() * 1000),
        blocks=list(blocks),
        week_start=TODAY,
        selected_day=selected_day,
    )
    return parent


def essay(**more: object) -> dict:
    return {
        "id": "essay",
        "title": "History essay",
        "due": "2026-09-20",
        "estimate_min": 120,
        "category": "assignments",
        "revision": 0,
        **more,
    }


def waiting(day: int, start: str | None = None) -> dict:
    return {
        "id": f"s{day}",
        "title": "History essay",
        "kind": "flexible",
        "assignment_id": "essay",
        "duration_min": 60,
        "days": [day],
        **({"start": start} if start else {}),
    }


def opened(parent: QWidget, assignment: dict | None = None, **more: object) -> HomeworkDialog:
    dialog = HomeworkDialog(parent, assignment, TODAY, **more)
    dialog.show()
    QApplication.processEvents()
    return dialog


def spread(dialog: HomeworkDialog) -> None:
    dialog.spread_choice.setCurrentIndex(1)


def test_the_choice_is_shown_from_60_minutes_up_in_add_and_in_edit(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    for assignment in (None, essay()):
        dialog = opened(parent, assignment)
        if assignment is None:
            go_length(dialog)
        assert dialog.spread_choice.isVisible()
        assert not dialog.spread_line.isVisible(), "the line says what Spread will do, not one go"
        spread(dialog)
        assert dialog.spread_line.isVisible()
        dialog.spread_choice.setCurrentIndex(0)
        assert [dialog.spread_choice.itemText(i) for i in range(2)] == ["In one go", "Spread over days"]
        assert dialog.spread_choice.currentData() == "one", "one go is today's behaviour"
        dialog.estimate.setValue(45)
        assert not dialog.spread_choice.isVisible() and not dialog.spread_line.isVisible()
        dialog.estimate.setValue(60)
        assert dialog.spread_choice.isVisible()
        free(dialog)
    free(parent)


def test_an_estimate_that_drops_below_60_means_one_go_again(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    dialog.title.setText("History essay")
    spread(dialog)
    dialog.estimate.setValue(45)
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert not dialog.spread_requested()
    free(dialog)
    free(parent)


def test_the_choice_is_called_sessions_and_the_old_button_is_gone(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    dialog.more_details.click()
    assert dialog.findChild(QPushButton, "spreadHomework") is None
    assert "Spread across days" not in [button.text() for button in dialog.findChildren(QPushButton)]
    labels = [label.text() for label in dialog.findChildren(QLabel) if label.objectName() == "fieldLabel"]
    assert "Sessions" in labels
    free(dialog)
    free(parent)


def test_the_grey_line_says_what_plan_will_do_before_the_due(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    spread(dialog)
    assert dialog.spread_line.text() == "2 × 60 min on different days before it's due Sun 20 Sep."
    free(dialog)
    free(parent)


def test_the_line_follows_the_values_not_yet_saved(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    spread(dialog)
    dialog.estimate.setValue(180)
    assert dialog.spread_line.text() == "3 × 60 min on different days before it's due Sun 20 Sep."
    dialog.estimate.setValue(90)
    assert dialog.spread_line.text() == "60 min and 30 min on different days before it's due Sun 20 Sep."
    dialog.due.date.setDate(QDate(2026, 9, 18))
    assert dialog.spread_line.text().endswith("before it's due Fri 18 Sep.")
    dialog.due.timed.setChecked(True)
    assert dialog.spread_line.text().endswith("before it's due Fri 18 Sep, 15:00.")
    free(dialog)
    free(parent)


def test_sessions_beyond_the_days_left_share_days_and_the_line_says_so(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay(due="2026-09-15"))
    spread(dialog)
    dialog.estimate.setValue(240)
    assert dialog.spread_line.text() == "4 × 60 min over 2 days before it's due Tue 15 Sep."
    dialog.due.date.setDate(QDate(2026, 9, 14))
    assert dialog.spread_line.text() == "4 × 60 min on the same day before it's due Mon 14 Sep."
    free(dialog)
    free(parent)


def test_edit_spreads_only_what_focus_has_not_already_covered(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay(estimate_min=240, focus_minutes=60))
    spread(dialog)
    assert dialog.spread_line.text() == "3 × 60 min on different days before it's due Sun 20 Sep."
    dialog.estimate.setValue(300)
    assert dialog.spread_line.text() == "4 × 60 min on different days before it's due Sun 20 Sep."
    free(dialog)
    free(parent)


def test_a_time_picked_by_hand_is_one_time_so_the_choice_waits_for_flexweek_to_pick(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host(waiting(3, "19:00") | {"pinned": True})
    dialog = opened(parent, essay())
    assert dialog.when.currentData() == "fixed", "placed by hand"
    assert not dialog.spread_choice.isVisible()
    dialog.when.setCurrentIndex(0)
    assert dialog.spread_choice.isVisible()
    spread(dialog)
    dialog.when.setCurrentIndex(1)
    assert not dialog.spread_choice.isVisible()
    assert dialog.spread_choice.currentData() == "one", "hidden means one go"
    free(dialog)
    free(parent)


def test_the_days_start_at_the_day_on_screen_when_it_is_ahead(qapp: QApplication) -> None:  # noqa: F811
    parent = host(selected_day="2026-09-19")
    dialog = opened(parent, essay(estimate_min=180))
    spread(dialog)
    # Sat 19 and Sun 20: three sessions, two days.
    assert dialog.spread_line.text() == "3 × 60 min over 2 days before it's due Sun 20 Sep."
    assert dialog.spread_plan() == {"session_min": 60, "from_date": "2026-09-19"}
    free(dialog)
    free(parent)


def test_saving_with_spread_hands_the_unsaved_values_and_the_plan_to_the_window(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("Science project")
    go_length(dialog)
    dialog.estimate.setValue(180)
    dialog.due.date.setDate(QDate(2026, 9, 18))
    spread(dialog)
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.spread_requested()
    saved = dialog.assignment()
    assert (saved["title"], saved["estimate_min"], saved["due"]) == ("Science project", 180, "2026-09-18")
    assert dialog.spread_plan() == {"session_min": 60, "from_date": TODAY}
    free(dialog)
    free(parent)


def test_one_go_saves_as_it_always_did(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("Science project")
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert not dialog.spread_requested()
    free(dialog)
    free(parent)


def test_homework_that_already_has_several_times_shows_no_choice(qapp: QApplication) -> None:  # noqa: F811
    parent = host(waiting(1, "15:00"), waiting(2, "15:00"))
    dialog = opened(parent, essay())
    assert not dialog.spread_choice.isVisible() and not dialog.spread_line.isVisible()
    free(dialog)
    free(parent)


def tab_chain(dialog: HomeworkDialog, steps: int = 14) -> list[QWidget]:
    dialog.estimate.setFocus()
    seen = [dialog.focusWidget()]
    for _ in range(steps):
        dialog.focusNextChild()
        seen.append(dialog.focusWidget())
    return seen


def test_the_choice_comes_after_estimated_time_in_the_tab_order(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent, essay())
    chain = tab_chain(dialog)
    first_segment = dialog.spread_choice.buttons()[0]
    assert dialog.estimate in chain
    assert chain.index(dialog.estimate) < chain.index(first_segment) < chain.index(dialog.completed)
    # Back from Finished, the way the keyboard goes up: the choice is the stop before it.
    dialog.completed.setFocus()
    dialog.focusPreviousChild()
    assert dialog.focusWidget() in dialog.spread_choice.buttons()
    assert Qt.FocusPolicy.NoFocus not in {button.focusPolicy() for button in dialog.spread_choice.buttons()}
    free(dialog)
    free(parent)


def test_spread_summary_starts_with_the_homework_title() -> None:
    assert (
        spread_ready_sentence("History essay", 90, "2026-10-10", "2026-10-05")
        == "History essay: 1 h 30 min ready to add before Sat 10 Oct."
    )


# Through the window and its session. The clock is held at Thursday 10:00 of the week on screen.


def test_a_new_homework_is_saved_and_spread_over_the_days_to_its_due(
    qapp: QApplication,  # noqa: F811
    homework_window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = homework_window
    due = sunday_due(window.session.week_start)[:10]

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        dialog.title.setText("Science project")
        dialog.estimate.setValue(180)
        dialog.due.date.setDate(QDate.fromString(due, "yyyy-MM-dd"))
        dialog.spread_choice.setCurrentIndex(1)
        assert dialog.spread_line.text().startswith("3 × 60 min on different days before it's due")
        dialog.accept()
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._add_homework()
    settled(qapp, window)
    project = next(item for item in window.session.assignments.values() if item["title"] == "Science project")
    assert project["estimate_min"] == 180 and project["due"] == due
    sessions = sessions_of(window, project["id"])
    # Thursday, Friday and Saturday: one 60 minute session a day from today, nothing left whole.
    shape = [(block["days"], block["duration_min"]) for block in sessions]
    assert shape == [([3], 60), ([4], 60), ([5], 60)]
    # As the old Spread sheet wrote them: the preview's ids, each a time that still waits for Plan.
    assert all(block["id"].startswith("b-stage3-") and block["start"] is None for block in sessions)


def test_edit_spreads_a_waiting_homework_and_drops_its_one_waiting_session(
    qapp: QApplication,  # noqa: F811
    homework_window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = homework_window
    waiting_block = session_of(window, "math")
    assert not waiting_block.get("start") and waiting_block["duration_min"] == 60

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        dialog.estimate.setValue(120)
        dialog.spread_choice.setCurrentIndex(1)
        dialog.accept()
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._edit_homework("math")
    settled(qapp, window)
    sessions = sessions_of(window, "math")
    assert window.session.assignments["math"]["estimate_min"] == 120
    assert [(block["days"], block["duration_min"]) for block in sessions] == [([3], 60), ([4], 60)]
    assert waiting_block["id"] not in {block["id"] for block in window.session.blocks}


def test_a_time_placed_by_hand_is_replaced_once_flexweek_is_asked_to_pick(
    qapp: QApplication,  # noqa: F811
    homework_window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = homework_window
    placed = session_of(window, "essay")
    assert placed["pinned"] and placed["start"] == "19:00"

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        assert not dialog.spread_choice.isVisible(), "a hand-placed time is one time"
        dialog.when.setCurrentIndex(0)
        dialog.estimate.setValue(180)
        dialog.spread_choice.setCurrentIndex(1)
        dialog.accept()
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._edit_homework("essay")
    settled(qapp, window)
    sessions = sessions_of(window, "essay")
    assert placed["id"] not in {block["id"] for block in sessions}
    assert [block["duration_min"] for block in sessions] == [60, 60, 60]
    assert not any(block.get("pinned") for block in sessions)


def test_one_go_still_saves_one_session_and_opens_no_sheet(
    qapp: QApplication,  # noqa: F811
    homework_window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = homework_window

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        dialog.title.setText("Reading log")
        dialog.estimate.setValue(120)
        dialog.accept()
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._add_homework()
    settled(qapp, window)
    log = next(item for item in window.session.assignments.values() if item["title"] == "Reading log")
    sessions = sessions_of(window, log["id"])
    assert [block["duration_min"] for block in sessions] == [120]
    assert not sessions[0]["id"].startswith("spread-")
