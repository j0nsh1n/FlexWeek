# ruff: noqa: F811
"""The Material Add homework and Edit homework sheet: its steps, the words that refuse a bad entry, the
discard question, More details, spreading over days, and what a delete asks.

Expected words and values come from the Widgets sheets' wording and from the week the fixtures build
(School Monday to Friday 08:00 to 14:30, a History essay Thursday 18:45, the clock at Thursday 19:00),
not from reading what the bridge returns.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    DISCARD,
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
    type_homework,
)
from desktop.tests.waiting import wait_until  # noqa: E402

TITLE_PROBLEM = "Give the homework a title."
SHORT = "Give it at least 15 minutes."
MULTIPLE = "Use a multiple of 15 minutes, such as 15, 30, or 45."
LONG = "That's more than 24 hours. Split it into parts and add each part as its own homework."
DUE_PASSED = "That due time has passed. Choose a later one."


def test_add_homework_goes_what_when_how_long_then_saves_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell._material_page.bridge.addHomework()
    form = sheets.form
    assert sheets.kind == "homework"
    assert form["heading"] == "Add homework"
    assert [crumb["label"] for crumb in form["crumbs"]] == ["1. What", "2. When", "3. How long"]
    assert form["prompt"] == "What is it?"
    assert form["primary"] == "Next"
    assert form["canDelete"] is False

    sheets.next()
    assert sheets.form["titleProblem"] == TITLE_PROBLEM
    assert sheets.form["step"] == 0

    type_homework(sheets, "Chemistry lab")
    assert sheets.form["titleProblem"] == ""
    sheets.next()
    assert sheets.form["step"] == 1
    assert sheets.form["prompt"] == "When is it due?"
    # Tomorrow from Thursday, at the end of the day.
    friday = (datetime.fromisoformat(shell.session.week_start) + timedelta(days=4)).date().isoformat()
    assert sheets.form["dueDate"] == friday
    assert sheets.form["canBack"] is True
    sheets.back()
    assert sheets.form["step"] == 0
    sheets.next()
    sheets.next()
    assert sheets.form["step"] == 2
    assert sheets.form["prompt"] == "How long will it take?"
    assert sheets.form["primary"] == "Save"
    assert sheets.form["estimate"] == "60"
    assert sheets.form["estimateSuffix"] == "min"
    assert [item["label"] for item in sheets.form["quickLengths"]] == [
        "15 min",
        "30 min",
        "45 min",
        "60 min",
        "90 min",
    ]

    sheets.setText("estimate", "45")
    sheets.next()
    assert sheets.kind == ""
    found = [item for item in shell.session.assignments.values() if item["title"] == "Chemistry lab"]
    assert len(found) == 1
    assert found[0]["estimate_min"] == 45
    assert found[0]["due"].startswith(friday)
    assert sheets.notice == "Added Chemistry lab"
    assert sheets.noticeUndo is True
    settle(qapp, shell)


def test_homework_estimate_and_due_are_checked_with_the_widgets_words(shell: NativeWindow, sheets) -> None:
    sheets.openHomework()
    type_homework(sheets, "Reading")
    sheets.next()
    sheets.next()
    for typed, said in (("10", SHORT), ("50", MULTIPLE), ("1500", LONG)):
        sheets.setText("estimate", typed)
        sheets.next()
        assert sheets.kind == "homework", typed
        # The hint keeps its last two words together with a no-break space; the words are the same.
        assert sheets.form["estimateProblem"].replace("\u00a0", " ") == said
    sheets.setText("estimate", "30")
    # Monday has already gone by on Thursday evening.
    monday = shell.session.week_start
    sheets.setText("dueDate", monday)
    sheets.next()
    assert sheets.kind == "homework"
    assert sheets.form["step"] == 1
    assert sheets.form["dueProblem"] == DUE_PASSED
    assert not [item for item in shell.session.assignments.values() if item["title"] == "Reading"]


def test_homework_title_over_80_characters_is_refused_with_the_widgets_words(sheets) -> None:
    sheets.openHomework()
    type_homework(sheets, "x" * 81)
    sheets.next()
    sheets.next()
    sheets.next()
    assert sheets.kind == "homework"
    assert sheets.form["titleProblem"] == "Keep the homework title under 80 characters."
    assert sheets.form["step"] == 0


def test_the_discard_prompt_keeps_typed_work_until_the_student_says_discard(sheets) -> None:
    sheets.openHomework()
    sheets.closeSheet()
    assert sheets.kind == ""

    sheets.openHomework()
    type_homework(sheets, "Essay")
    sheets.closeSheet()
    assert sheets.kind == "homework"
    assert sheets.ask["title"] == DISCARD
    assert sheets.ask["body"] == "Your changes will be lost."
    assert [item["label"] for item in sheets.ask["answers"]] == ["Keep editing", "Discard"]
    sheets.answer("keep")
    assert sheets.kind == "homework"
    assert sheets.ask == {}
    assert sheets.form["title"] == "Essay"
    sheets.closeSheet()
    sheets.answer("discard")
    assert sheets.kind == ""


def test_edit_homework_changes_the_title_and_delete_asks_first(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.editHomework("essay")
    form = sheets.form
    assert form["heading"] == "Edit homework"
    assert form["title"] == "History essay"
    assert form["canDelete"] is True
    assert form["step"] == -1
    assert form["primary"] == "Save"
    assert form["placedLine"].startswith("Planned Thu")

    sheets.setText("title", "History essay, draft 2")
    sheets.save()
    assert shell.session.assignments["essay"]["title"] == "History essay, draft 2"
    settle(qapp, shell)

    sheets.editHomework("essay")
    sheets.remove()
    assert sheets.ask["title"] == "Delete homework"
    assert "Its times on the calendar go too, in every week." in sheets.ask["body"]
    sheets.answer("stay")
    assert "essay" in shell.session.assignments
    sheets.remove()
    sheets.answer("delete")
    wait_until(qapp, lambda: "essay" not in shell.session.assignments)
    assert sheets.kind == ""
    assert sheets.notice == "Deleted History essay, draft 2."
    settle(qapp, shell)
    shell.session.undo()
    settle(qapp, shell)
    assert "essay" in shell.session.assignments


def test_more_details_carry_course_type_energy_notes_links_and_steps(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openHomework()
    type_homework(sheets, "Lab report")
    sheets.next()
    sheets.next()
    assert sheets.form["detailsOpen"] is False
    sheets.setFlag("detailsOpen", True)
    sheets.setText("course", "Chemistry")
    sheets.setNumber("priority", 1)
    sheets.setText("energy", "high")
    sheets.setText("notes", "Bring goggles")
    sheets.addLink()
    assert sheets.form["detailsError"] == "A link needs a label and an http(s) address."
    sheets.setText("linkLabel", "Rubric")
    sheets.setText("linkUrl", "https://example.org/rubric")
    sheets.addLink()
    assert sheets.form["links"] == [{"label": "Rubric", "url": "https://example.org/rubric"}]
    assert sheets.form["linkLabel"] == ""
    sheets.addCheck()
    assert sheets.form["detailsError"] == "A checklist step needs text."
    sheets.setText("checkText", "Write the aim")
    sheets.addCheck()
    sheets.toggleCheck(0)
    sheets.next()
    saved = next(item for item in shell.session.assignments.values() if item["title"] == "Lab report")
    assert saved["course"] == "Chemistry"
    assert saved["priority"] == 1
    assert saved["energy"] == "high"
    assert saved["notes"] == "Bring goggles"
    assert saved["links"] == [{"label": "Rubric", "url": "https://example.org/rubric"}]
    assert [(step["text"], step["done"]) for step in saved["checklist"]] == [("Write the aim", True)]
    assert "spotify_url" not in sheets.form
    settle(qapp, shell)


def test_spread_over_days_shows_its_line_and_saves_sessions(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openHomework()
    type_homework(sheets, "Project")
    sheets.next()
    sunday = (datetime.fromisoformat(shell.session.week_start) + timedelta(days=6)).date().isoformat()
    sheets.setText("dueDate", sunday)
    sheets.next()
    sheets.setText("estimate", "120")
    assert sheets.form["spreadShown"] is True
    sheets.setText("spread", "spread")
    assert sheets.form["spreadLine"].startswith("2 × 60 min")
    sheets.next()
    assert sheets.kind == ""
    settle(qapp, shell)
    made = next(item for item in shell.session.assignments.values() if item["title"] == "Project")

    def sessions() -> list[dict]:
        return [b for b in shell.session.blocks if b.get("assignment_id") == made["id"]]

    wait_until(qapp, lambda: len(sessions()) == 2)
    assert sorted(b["duration_min"] for b in sessions()) == [60, 60]
    settle(qapp, shell)


def test_the_homework_sheet_opens_with_a_title_field_and_a_named_next_button_on_a_desktop_and_a_phone(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = shell._material_page.root
    sheets.openHomework()
    pump(qapp)
    assert find_named(root, "homeworkTitle") is not None
    assert find_named(root, "homeworkNext").property("accessName") == "Next"
    sheets.forceClose()
    pump(qapp)

    shell.setMinimumWidth(360)
    shell.resize(700, 800)
    pump(qapp)
    try:
        sheets.openHomework()
        pump(qapp)
        assert sheets.kind == "homework"
        assert find_named(root, "homeworkTitle") is not None
        assert find_named(root, "homeworkNext").property("accessName") == "Next"
        sheets.forceClose()
    finally:
        shell.setMinimumWidth(WINDOW_MIN_WIDTH)
        shell.resize(1280, 800)
        pump(qapp)
