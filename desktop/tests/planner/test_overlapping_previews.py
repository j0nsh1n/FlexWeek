"""One overlap rule everywhere: a second block at the same time is allowed, and says so. Duplicate,
paste, copy day and apply routine previews used to refuse such a row while a drag and the editor only
warned that both would show side by side."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.material.sheet_preview import beside_words
from desktop.native.reuse import row_conflict
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window as signed_in  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

SOCCER = {
    "id": "soccer",
    "kind": "locked",
    "title": "Soccer practice",
    "category": "extra",
    "start": "16:00",
    "duration_min": 90,
    "days": [0],
}
WARNING = "Soccer practice is at that time too. Both will show, one slightly over the other."


@pytest.fixture()
def window(qapp: QApplication, signed_in: NativeWindow) -> NativeWindow:
    signed_in.session.add_block(dict(SOCCER))
    signed_in.session.save()
    settled(qapp, signed_in)
    signed_in.session.select_block("soccer", 0)
    return signed_in


def on_top_rows(window: NativeWindow) -> list[dict]:
    window.session.copy_selected()
    rows = window.session.paste_proposals(0, "16:00")
    assert rows is not None
    return rows


def test_a_preview_row_that_lands_on_a_block_warns_in_the_editors_words_and_can_be_saved(
    qapp: QApplication, window: NativeWindow
) -> None:
    rows = on_top_rows(window)
    clash = row_conflict(rows[0], rows, window.session.blocks)
    assert clash is not None and beside_words(clash) == WARNING
    assert rows[0]["checked"]


def test_a_preview_with_nothing_selected_cannot_be_saved(qapp: QApplication, window: NativeWindow) -> None:
    rows = on_top_rows(window)
    rows[0]["checked"] = False
    assert window.session.confirm_preview(rows, label="the copied block") is False
    assert window.session.message == "Select at least one item before saving."


def test_a_refused_preview_keeps_no_save_attempt(qapp: QApplication, window: NativeWindow) -> None:
    """Nothing checked, or a checked row that can't be added: refused before any save attempt is kept,
    so a later accepted preview under the same key gets the id it is given then."""
    rows = on_top_rows(window)
    rows[0]["checked"] = False
    assert window.session.confirm_preview(rows, label="the copied block", attempt_key="paste-1") is False
    rows[0]["checked"] = True
    rows[0]["invalid"] = "taken"
    assert window.session.confirm_preview(rows, label="the copied block", attempt_key="paste-1") is False
    assert window.session.message == "Uncheck what can't be added before saving."
    assert "paste-1" not in window.session._attempts


def test_pasting_signed_out_with_nothing_copied_says_to_copy_first(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.clipboard = None
    window.session.account = None
    assert window.session.paste_proposals(0, "16:00") is None
    assert window.session.message == "Copy a block or day before pasting."


def test_a_copied_day_pastes_onto_the_same_day_and_both_stay(
    qapp: QApplication, window: NativeWindow
) -> None:
    assert window.session.copy_day(0)
    rows = window.session.paste_proposals(0, None)
    assert rows is not None and all(row["checked"] for row in rows)
    assert window.session.confirm_preview(rows, label="the copied day")
    wait_until(qapp, lambda: not window.session.busy and len(window.session.blocks) == 2)
