"""What a student reads when Plan cannot start, and where Help explains Plan.

Expected words come from the 0.19.0 wording audit (findings 3 and 46), not from the code's output. The
sentences that say why homework was not placed are the engine's: engine/engine/tests/test_no_room_reasons.rs.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.settings import HelpDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.mark.parametrize(
    ("planning", "conflict", "pending", "said"),
    [
        (True, False, False, "Planning… one moment."),
        (
            False,
            True,
            True,
            "This week changed in another window. Choose More > Reload this week, then try again.",
        ),
        (False, False, True, "Saving your last change… Plan will work in a moment."),
    ],
)
def test_plan_says_planning_saving_or_out_of_step(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    planning: bool,
    conflict: bool,
    pending: bool,
    said: str,
) -> None:
    session = window.session
    monkeypatch.setattr(type(session), "planning", property(lambda _self: planning))
    session.conflict = conflict
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "x"} if pending else None
    try:
        session.solve()
        assert session.message == said
    finally:
        session.conflict = False
        session.pending_save = None


def test_the_greyed_plan_tip_names_the_same_three_causes(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    session.conflict = True
    assert window._more_tip("solveButton", False) == (
        "This week changed in another window. Choose More > Reload this week, then try again."
    )
    session.conflict = False
    monkeypatch.setattr(type(session), "planning", property(lambda _self: True))
    assert window._more_tip("solveButton", False) == "Planning… one moment."
    monkeypatch.undo()
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "x"}
    try:
        assert (
            window._more_tip("solveButton", False) == "Saving your last change… this will work in a moment."
        )
    finally:
        session.pending_save = None


def test_help_opens_with_how_planning_works(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = HelpDialog(window)
    headings = [label.text() for label in dialog.findChildren(QLabel, "prefsHeading")]
    assert headings[:3] == ["How planning works", "The screens", "Keyboard shortcuts"]
    body = dialog.findChild(QLabel, "helpPlanning").text()
    for part in ("Plan my homework", "Replan all", "Not placed yet", "Details", "Ctrl+K"):
        assert part in body
    free(dialog)
