# ruff: noqa: F811
"""The Material Add fixed time and Edit fixed time sheet: its steps, the checks on days and times, a clash
preview, editing a series, and what deleting a fixed time offers.

Expected words and values come from the Widgets sheets' wording and from the week the fixtures build
(School Monday to Friday 08:00 to 14:30, the clock at Thursday 19:00).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)


def test_add_fixed_time_steps_and_saves_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlock()
    form = sheets.form
    assert form["heading"] == "Add fixed time"
    assert [crumb["label"] for crumb in form["crumbs"]] == ["1. What", "2. When", "3. Category"]
    sheets.next()
    assert sheets.form["titleProblem"] == "Give it a title."
    sheets.setText("title", "Chess club")
    sheets.next()
    assert sheets.form["step"] == 1
    sheets.setText("start", "17:00")
    # End follows Start by the length it had: an hour.
    assert sheets.form["end"] == 18 * 60
    assert sheets.form["durationLine"].startswith("End moved to")
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.next()
    assert sheets.form["daysProblem"] == "Tick at least one day."
    sheets.toggleDay(5)
    sheets.next()
    assert sheets.form["step"] == 2
    assert sheets.form["primary"] == "Add"
    sheets.setText("category", "extra")
    sheets.next()
    assert sheets.kind == ""
    made = next(item for item in shell.session.blocks if item["title"] == "Chess club")
    assert made["days"] == [5]
    assert made["start"] == "17:00"
    assert made["duration_min"] == 60
    assert made["category"] == "extra"
    settle(qapp, shell)


def test_fixed_time_checks_end_after_start_and_previews_a_clash(sheets) -> None:
    sheets.openBlock()
    sheets.setText("title", "Study hall")
    sheets.next()
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(0)
    sheets.setText("start", "09:00")
    # School is Monday 08:00 to 14:30, so this sits beside it.
    assert sheets.form["clash"] == "School is at that time too. Both will show, side by side."
    sheets.setNumber("end", 9 * 60)
    assert sheets.form["durationIsProblem"] is True
    assert sheets.form["durationLine"].startswith("End needs to be later than Start")
    assert sheets.form["clash"] == ""
    sheets.next()
    assert sheets.form["step"] == 1
    assert sheets.form["timeProblem"].startswith("End needs to be later than Start")


def test_edit_a_fixed_time_in_a_series_and_delete_it(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    shell.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [4, 5],
        }
    )
    shell.session.save()
    settle(qapp, shell)
    sheets.editBlock("club", 4)
    form = sheets.form
    assert form["heading"] == "Edit fixed time"
    assert form["showScope"] is True
    assert [choice["label"] for choice in form["scopeChoices"]] == ["This day only", "Every Fri and Sat"]
    assert form["scope"] == "occurrence"
    sheets.setText("title", "Club night")
    sheets.setText("scope", "series")
    sheets.save()
    renamed = [item for item in shell.session.blocks if item["title"] == "Club night"]
    assert [item["days"] for item in renamed] == [[4, 5]]
    settle(qapp, shell)

    sheets.editBlock(renamed[0]["id"], 4)
    sheets.setText("scope", "series")
    sheets.remove()
    assert sheets.ask["title"] == "Delete fixed time"
    assert sheets.ask["body"].startswith("Delete Club night on every Fri and Sat this week?")
    sheets.answer("delete")
    assert not [item for item in shell.session.blocks if item["title"] == "Club night"]
    assert sheets.notice == "Deleted Club night from this week."
    settle(qapp, shell)


def test_deleting_a_setup_block_offers_this_week_or_every_week(shell: NativeWindow, sheets) -> None:
    sheets.editBlock("school", 0)
    sheets.remove()
    labels = [answer["label"] for answer in sheets.ask["answers"]]
    assert labels == ["Cancel", "This day only", "This week only", "This week and later"]
    sheets.answer("stay")
    assert any(item["id"] == "school" for item in shell.session.blocks)
