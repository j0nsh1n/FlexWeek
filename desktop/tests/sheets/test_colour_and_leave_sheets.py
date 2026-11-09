"""The look editor's two sheets: the question on the way out with changes not saved, and the accent
picker (five named accents, a dozen hues and a code box). How the leave sheet's answers are drawn is a
look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.look import ACCENT_COLORS, ACCENTS
from desktop.native.look_editor import PICKER_HUES, ColourField, ColourSheet, leave_sheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import shown, styled, when_open
from desktop.tests.test_look_editor import open_editor
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-colour-leave-sheets-test"])


def test_the_leave_sheet_has_a_filled_save_an_outlined_red_discard_and_quiet_cancel_and_keep(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    sheet = shown(qapp, leave_sheet(parent, "Evening", True))
    save, discard = sheet.buttons["save"], sheet.buttons["discard"]
    assert [button.text() for button in sheet.buttons.values()] == [
        "Keep without saving",
        "Cancel",
        "Save",
        "Discard changes",
    ]
    assert save.isDefault() and not save.property("outlined") and not save.property("quiet")
    assert discard.property("outlined") and discard.property("danger")
    assert sheet.buttons["stay"].property("quiet") and sheet.buttons["keep"].property("quiet")
    free(sheet)
    free(parent)


@pytest.mark.parametrize(
    ("key", "expected"), [("save", "save"), ("keep", "keep"), ("discard", "discard"), ("stay", None)]
)
def test_each_answer_on_the_leave_sheet_is_the_one_the_editor_gets(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    key: str,
    expected: str | None,
) -> None:
    _page, editor = open_editor(qapp, window)
    check = when_open(lambda sheet: sheet.buttons[key].click())
    assert editor.ask_leave() == expected
    check()


def test_the_accent_picker_offers_the_five_accents_then_a_dozen_hues_and_a_code(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    picker = shown(qapp, ColourSheet(parent, "#3d6fc4"))
    assert len(picker.dots) == 5 + 12 == len(ACCENTS) + len(PICKER_HUES)
    named = [dot.fill for dot in picker.dots[:5]]
    assert named == [ACCENT_COLORS[name]["light"][0] for name in ACCENTS], "the named accents first"
    assert [dot.fill for dot in picker.dots[5:]] == list(PICKER_HUES)
    assert picker.dots[0].isChecked() and picker.code.text() == "#3d6fc4"
    heard: list[str] = []
    picker.picked.connect(heard.append)
    picker.dots[7].click()
    assert heard == [PICKER_HUES[2]] and picker.colour() == PICKER_HUES[2]
    assert picker.code.text() == PICKER_HUES[2] and PICKER_HUES[2] in picker.chip.styleSheet()
    assert picker.dots[7].isChecked() and not picker.dots[0].isChecked()
    free(picker)
    free(parent)


def test_the_accent_pickers_code_box_takes_a_typed_colour_and_says_why_it_will_not_use_a_bad_one(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    picker = shown(qapp, ColourSheet(parent, "#3d6fc4"))
    hint = picker.findChild(QLabel, "whyOff")
    assert picker.use.isEnabled() and not hint.isVisible()
    heard: list[str] = []
    picker.picked.connect(heard.append)
    picker.code.setText("#12")
    picker.code.textEdited.emit("#12")
    assert not picker.use.isEnabled() and hint.isVisible() and heard == []
    picker.code.setText("#c0392b")
    picker.code.textEdited.emit("#c0392b")
    assert picker.use.isEnabled() and not hint.isVisible()
    assert heard == ["#c0392b"] and picker.dots[5].isChecked(), "the matching swatch is ringed"
    free(picker)
    free(parent)


def test_use_this_colour_keeps_the_colour_and_cancel_puts_the_first_back(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    field = ColourField("Accent")
    field.setParent(parent)
    field.show()
    field.show_colour("#3d6fc4")
    heard: list[str] = []
    field.picked.connect(heard.append)

    def pick_then(answer: str):
        def act(sheet: object) -> None:
            sheet.dots[9].click()
            sheet.findChild(QPushButton, answer).click()

        return act

    check = when_open(pick_then("colourUse"))
    field.swatch.click()
    check()
    assert heard[-1] == PICKER_HUES[4]
    heard.clear()
    check = when_open(pick_then("colourCancel"))
    field.swatch.click()
    check()
    assert heard[-1] == "#3d6fc4"
    free(field)
    free(parent)
