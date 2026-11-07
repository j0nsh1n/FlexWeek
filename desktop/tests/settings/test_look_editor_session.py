"""The look editor (0.17's Customise, option B): the controls on the left in the look it starts from,
the window wearing every change at once, saved looks kept by name and offered under More looks, one
question on the way out when something is not saved, and a look shared as a small file. Where things
sit and how they look is in the settings pictures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native import look_editor
from desktop.native.calendar import CATEGORIES
from desktop.native.custom_look import readability
from desktop.native.look import FONT_FAMILIES, MOTION_LEVELS, category_paint
from desktop.native.look_editor import LookEditor, hex_colour, leave_sheet, problem_rows
from desktop.native.tokens import MARK, WEIGHT_REGULAR, WEIGHT_STRONG, contrast, oklch, type_pt
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_look_editor import (
    name_look,
    on_modal,
    open_editor,
    palette_of,
    pump,
    shown,
    type_colour,
)
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def test_a_change_is_worn_at_once_while_the_controls_keep_the_look_they_started_in(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    before = palette_of(window)
    page, editor = open_editor(qapp, window)
    assert editor.isVisible()
    assert editor.state.text() == ""
    type_colour(qapp, editor, "page", "#1e2430")
    type_colour(qapp, editor, "text", "#999999")
    assert "custom" in window._look, "the change is not worn"
    worn = window._look["custom"]
    assert worn["colours"]["page"] == "#1e2430" and worn["colours"]["text"] == "#999999"
    assert window.week_table.hours.painter.colours["window"] == "#1e2430"
    assert editor.state.text() == "Changed, not saved"
    assert editor.groups["colours"].tag.isVisible() and not editor.groups["shape"].tag.isVisible()
    # A grey the student is trying never greys out the editor: it keeps the look it started from.
    label = editor.findChild(QLabel, "lookFieldLabel")
    label.ensurePolished()
    assert label.palette().color(QPalette.ColorRole.WindowText).name() == before["text"]
    page.close_page()


def test_the_preview_follows_each_change_and_can_be_shown_at_actual_size(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page, editor = open_editor(qapp, window)
    assert editor.pictures[0].source.width() >= 1000, "the whole window, at its size"
    before = editor.pictures[0].source.toImage()
    type_colour(qapp, editor, "page", "#1e2430")
    assert editor.pictures[0].source.toImage() != before, "the preview is taken again after a change"
    editor.zoom.buttons()[1].click()
    pump(qapp)
    shown_now = editor.pictures[0].image
    assert shown_now.width() == editor.pictures[0].source.deviceIndependentSize().width(), "actual size"
    assert editor.zoom_note.text() == look_editor.ACTUAL_NOTE
    page.close_page()


def test_done_keeps_the_look_by_its_name_and_more_looks_offers_it_beside_the_ten(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page, editor = open_editor(qapp, window)
    type_colour(qapp, editor, "card", "#262d3b")
    name_look(qapp, editor, "Night study")
    editor.done.click()
    pump(qapp)
    assert page.editor is None and page.body.isVisible()
    assert [look["name"] for look in window._saved_looks] == ["Night study"]
    stored = json.loads(look_file().read_text())
    assert [look["name"] for look in stored["saved_looks"]] == ["Night study"]
    assert stored["custom"]["colours"]["card"] == "#262d3b"
    more = page.look.more
    assert [card.accessibleName() for card in more.cards].count("High contrast") == 1
    # The worn look's card says so to a screen reader (N14): "<name>, selected".
    assert [card.accessibleName() for card in page.look.yours.cards] == ["Night study, selected"]
    assert page.look.yours_heading.text() == "Your looks"
    assert page.look.currentText() == "Night study", "Look shows the saved look worn"
    assert page.look.yours.cards[0].is_selected()
    assert not page.accent.isEnabled() and not page.knobs["density"].isEnabled(), "the look sets them"
    page.look.main.buttons()[0].click()
    pump(qapp)
    assert "custom" not in window._look, "another look takes it off"
    assert page.accent.isEnabled() and page.knobs["density"].isEnabled()
    page.look.yours.cards[0].chosen.emit()
    pump(qapp)
    assert "custom" in window._look, "the saved look chosen is not worn"
    assert window._look["custom"]["name"] == "Night study"
    assert window.week_table.hours.painter.colours["panel"] == "#262d3b"
    page.close_page()


def test_leaving_with_changes_not_saved_asks_once_to_save_keep_or_discard(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers: list[str | None] = []
    asked: list[bool] = []

    def ask(_editor: LookEditor) -> str | None:
        asked.append(True)
        return answers.pop(0)

    monkeypatch.setattr(LookEditor, "ask_leave", ask)
    page, editor = open_editor(qapp, window)
    editor.back.click()
    pump(qapp)
    assert page.editor is None and not asked, "nothing changed, nothing to ask"
    page.customise.click()
    pump(qapp)
    editor = page.editor
    type_colour(qapp, editor, "page", "#1e2430")
    answers.append(None)
    editor.back.click()
    pump(qapp)
    assert page.editor is editor and len(asked) == 1, "Cancel stays in the editor"
    answers.append("keep")
    editor.back.click()
    pump(qapp)
    assert page.editor is None and len(asked) == 2
    assert window._look["custom"]["colours"]["page"] == "#1e2430", "kept on without saving"
    assert window._saved_looks == []
    assert page.look.worn.text() == "Wearing My look (not saved)"
    page.customise.click()
    pump(qapp)
    editor = page.editor
    assert editor.state.text() == "Changed, not saved"
    answers.append("discard")
    editor.back.click()
    pump(qapp)
    assert page.editor is None and len(asked) == 3
    assert "custom" not in window._look, "discarded: the look from before any of the student's own"
    assert window.week_table.hours.painter.colours["window"] != "#1e2430"
    page.customise.click()
    pump(qapp)
    editor = page.editor
    type_colour(qapp, editor, "page", "#1e2430")
    answers.append("save")
    editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    pump(qapp)
    assert page.editor is None and len(asked) == 4, "Esc leaves as Back does"
    assert [look["name"] for look in window._saved_looks] == ["My look"]
    page.close_page()


def test_discard_is_not_next_to_save_on_the_leave_sheet(qapp: QApplication) -> None:  # noqa: F811
    """U3: Discard sits on the left; the right side is Keep without saving, Cancel, Save."""
    parent = QWidget()
    sheet = leave_sheet(parent, "Evening", True)
    visual = ([sheet._left] if sheet._left is not None else []) + list(sheet._answers)
    texts = [button.text() for button in visual]
    assert texts == ["Discard changes", "Keep without saving", "Cancel", "Save"]
    assert abs(texts.index("Discard changes") - texts.index("Save")) > 1
    assert sheet.buttons["save"].isDefault()
    assert sheet.buttons["discard"].property("outlined") and sheet.buttons["discard"].property("danger")
    assert sheet.buttons["keep"].property("quiet") and sheet.buttons["stay"].property("quiet")
    sheet.close()
    parent.deleteLater()


def test_escape_on_the_leave_sheet_stays_in_the_look_editor(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """U3: Esc on Leave the look editor is Cancel, so the editor stays open."""
    page, editor = open_editor(qapp, window)
    type_colour(qapp, editor, "page", "#1e2430")
    on_modal(lambda sheet: QTest.keyClick(sheet, Qt.Key.Key_Escape))
    assert editor.ask_leave() is None
    assert page.editor is editor
    on_modal(lambda sheet: sheet.buttons["discard"].click())
    editor.back.click()
    pump(qapp)
    assert page.editor is None


def test_every_pair_under_four_and_a_half_to_one_has_a_fix_and_fix_all_makes_them_read(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page, editor = open_editor(qapp, window)
    assert shown(editor, QLabel, "lookEverythingReads")
    type_colour(qapp, editor, "text", "#bbbbbb")
    type_colour(qapp, editor, "accent", "#ffee00")
    rows = problem_rows(readability(editor._draft.look))
    assert len(shown(editor, QPushButton, "lookFix")) == min(look_editor.READABILITY_ROWS, len(rows)) >= 2
    assert not shown(editor, QLabel, "lookEverythingReads")
    assert editor.fix_all.isVisibleTo(editor)
    editor.fix_all.click()
    pump(qapp)
    assert readability(editor._draft.look) == []
    assert shown(editor, QLabel, "lookEverythingReads") and not shown(editor, QPushButton, "lookFix")
    assert window._look["custom"]["colours"]["text"] != "#bbbbbb", "the fixed colour is worn"
    page.close_page()


def test_grey_text_names_the_block_colours_in_one_line_whose_fix_moves_them_not_the_text(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """The mock-up's bad colours: grey text on Light. The block colours are one line whose Fix moves
    them, not the text, until the grey reads. (The week writing the grey on its blocks is a picture.)"""
    page, editor = open_editor(qapp, window)
    editor._start_from("base:light")
    pump(qapp)
    type_colour(qapp, editor, "text", "#999999")
    said = [label.text() for label in shown(editor, QLabel, "lookWarnText")]
    worst = min(contrast("#999999", info["color"]) for info in CATEGORIES.values())
    assert said[-1] == f"Text on 8 block colours is {worst:.1f}:1 at worst", said
    fix = next(b for b in shown(editor, QPushButton, "lookFix") if b.accessibleName().endswith("at worst"))
    fix.click()
    pump(qapp)
    assert not [label for label in shown(editor, QLabel, "lookWarnText") if "block" in label.text()]
    custom = window._look["custom"]
    assert custom["colours"]["text"] == "#999999" and set(custom["categories"]) == set(CATEGORIES)
    page.close_page()


def test_the_editors_words_take_the_type_scale_of_the_look_it_starts_from(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Decision 4: the editor's type is the window stylesheet's roles, as every screen's is, so it
    grows with the look's text. Its title and group names are headings in the heading face, its notes
    and small buttons captions, and a setting's name body text in the strong weight."""
    page, editor = open_editor(qapp, window)
    looks = (("light", 1.0, "sans"), ("high-contrast", 1.2, "sans"), ("paper", 1.0, "serif"))
    for base, scale, face in looks:
        editor._start_from(f"base:{base}")
        pump(qapp)
        for kind, name, role, weight in (
            (QLabel, "lookEditorTitle", "heading", WEIGHT_STRONG),
            (QLabel, "lookGroupName", "heading", WEIGHT_STRONG),
            (QLabel, "lookFieldLabel", "body", WEIGHT_STRONG),
            (QLabel, "lookCategoryName", "body", WEIGHT_STRONG),
            (QLabel, "lookNote", "caption", WEIGHT_REGULAR),
            (QLabel, "lookOut", "caption", WEIGHT_REGULAR),
            (QLabel, "lookTag", "caption", WEIGHT_STRONG),
            (QLabel, "lookEverythingReads", "body", WEIGHT_REGULAR),
            (QLabel, "lookChip", "body", WEIGHT_STRONG),
            (QPushButton, "lookReset-colours", "caption", None),
        ):
            widget = editor.findChild(kind, name)
            widget.ensurePolished()
            font = widget.font()
            where = (base, name)
            assert font.pointSizeF() == type_pt(role, scale), where
            if weight is not None:
                assert font.weight().value == weight, where
        title = editor.findChild(QLabel, "lookEditorTitle")
        assert title.font().family() == FONT_FAMILIES[face].split(",")[0], base
    page.close_page()


def test_a_category_is_a_hue_on_the_family_or_an_exact_colour(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page, editor = open_editor(qapp, window)
    editor.groups["categories"].toggle.setChecked(True)
    pump(qapp)
    row = editor.categories["class"]
    assert row.hue.isVisible() and not row.colour.isVisible()
    row.hue.setValue(140)
    pump(qapp)
    assert window._look["custom"]["categories"]["class"] == {"hue": 140.0}
    colours = window.week_table.hours.painter.colours
    family = colours.get("family", "light")
    assert category_paint("class", colours)[1] == oklch(*MARK[family], 140), "the family's mark at its hue"
    row.exact.click()
    pump(qapp)
    spec = window._look["custom"]["categories"]["class"]
    assert set(spec) == {"colour"} and hex_colour(spec["colour"]) == spec["colour"]
    assert row.colour.isVisible() and not row.hue.isVisible()
    row.exact.click()
    pump(qapp)
    assert set(window._look["custom"]["categories"]["class"]) == {"hue"}
    page.close_page()


def test_a_look_exports_to_a_small_file_imports_back_and_a_file_that_is_not_one_says_so(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    page, editor = open_editor(qapp, window)
    type_colour(qapp, editor, "page", "#1e2430")
    name_look(qapp, editor, "Exams")
    shared = tmp_path / "exams.flexweek-look.json"
    assert editor.export_to(shared) and editor.said() == "Exported Exams."
    assert json.loads(shared.read_text())["kind"] == "FlexWeek look"
    assert editor.import_from(shared)
    pump(qapp)
    assert editor._draft.saved_as == "Exams" and editor.state.text() == "Saved"
    assert window._look["custom"]["colours"]["page"] == "#1e2430"
    other = tmp_path / "notes.json"
    other.write_text(json.dumps({"kind": "a shopping list"}))
    assert not editor.import_from(other)
    assert editor.said() == "This file isn't a FlexWeek look."
    assert [look["name"] for look in editor._saved] == ["Exams"]
    assert not editor.import_from(tmp_path / "missing.json")
    assert editor.said() == look_editor.NOT_OPENED
    page.close_page()


def test_start_from_another_look_is_worn_and_the_motion_levels_are_the_looks(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page, editor = open_editor(qapp, window)
    editor._start_from("base:dark")
    pump(qapp)
    motion = editor.findChild(QWidget, "lookMotion")
    assert [motion.itemData(index) for index in range(motion.count())] == list(MOTION_LEVELS)
    assert [motion.itemText(index) for index in range(motion.count())] == ["Normal", "More", "Reduce", "Off"]
    motion.buttons()[2].click()
    pump(qapp)
    assert window._look["custom"]["motion"] == "reduce"
    page.close_page()


def test_a_saved_look_is_renamed_duplicated_and_deleted_from_the_editors_bar(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(look_editor, "confirm", lambda *_args, **_kwargs: True)
    page, editor = open_editor(qapp, window)
    assert not editor.delete.isVisibleTo(editor), "a new look has nothing to delete"
    editor.save_new.click()
    pump(qapp)
    assert editor._draft.saved_as == "My look" and editor.delete.isVisibleTo(editor)
    name_look(qapp, editor, "Paper")
    assert "one of FlexWeek's own looks" in editor.said() and editor.name.text() == "My look"
    name_look(qapp, editor, "Revision")
    assert [look["name"] for look in window._saved_looks] == ["Revision"]
    editor.duplicate.click()
    pump(qapp)
    assert [look["name"] for look in window._saved_looks] == ["Revision", "Revision copy"]
    editor.delete.click()
    pump(qapp)
    assert [look["name"] for look in window._saved_looks] == ["Revision copy"]
    assert editor._draft.saved_as is None and editor.name.text() == "My look"
    page.close_page()
