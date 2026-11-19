"""Words Jonathan approved after the Material review: Paste and Duplicate say what their button does, and
the recovery codes line names the switch."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.account_copy import RECOVERY_WAIT
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump
from desktop.tests.sheets.support_prompt_walk import bridge_sheets as sheets_of
from desktop.tests.sheets.support_prompt_walk import week_with_school
from desktop.tests.window_support import qapp  # noqa: F401

CODES = ["aaaa-bbbb", "cccc-dddd"]


def _preview_words(window: NativeWindow) -> tuple[str, str]:
    sheet = [s for s in named(window._material_page.root, "previewSheet") if s.property("visible")][0]
    button = named(sheet, "previewSave")[0]
    said = (str(item.property("text")) for item in _every_text(sheet))
    intro = [text for text in said if text.startswith("Nothing")]
    return str(button.property("text")), intro[0]


def _every_text(item):
    found = []
    for child in item.childItems() if hasattr(item, "childItems") else []:
        if child.property("text") is not None:
            found.append(child)
        found.extend(_every_text(child))
    return found


def test_paste_preview_says_paste_and_nothing_changes_until_you_choose_it(qapp, window) -> None:
    week_with_school(qapp, window)
    bridge = window._material_page.bridge
    bridge.week.copyBlock("school", 1)
    pump(qapp, 10)
    bridge.week.pasteHere(5, 9 * 60)
    pump(qapp, 30)
    assert _preview_words(window) == ("Paste", "Nothing changes until you choose Paste.")


def test_duplicate_preview_says_duplicate_and_nothing_changes_until_you_choose_it(qapp, window) -> None:
    week_with_school(qapp, window)
    window.session.selected_block_id = "school"
    window._duplicate_selected()
    pump(qapp, 30)
    assert _preview_words(window) == ("Duplicate", "Nothing changes until you choose Duplicate.")
    assert sheets_of(window).form["heading"] == "Preview duplicate"
    sheets_of(window).forceClose()


def test_a_pasted_row_at_a_taken_time_says_both_will_show_one_over_the_other() -> None:
    """Jonathan, 2026-11-08: blocks at the same time are drawn overlapped, one a step over the other, so the
    preview says so as the block sheet does, not "side by side"."""
    from desktop.native.material.sheet_preview import beside_words

    words = beside_words("School")
    assert words == "School is at that time too. Both will show, one slightly over the other."


def test_the_recovery_codes_line_names_the_switch_by_its_label(qapp, window) -> None:
    window._show_recovery(CODES)
    pump(qapp, 30)
    bridge = window._account_bridge()
    assert f"Turn on “{bridge.recoveryAckLabel}” to continue." == RECOVERY_WAIT
    assert bridge.recoveryWait == RECOVERY_WAIT
    shown = [
        str(item.property("text"))
        for item in _every_text(window._material_page.root)
        if item.property("visible")
    ]
    assert RECOVERY_WAIT in shown
