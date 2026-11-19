# ruff: noqa: F811
"""The words a student reads on and after Material's Manage account sheet: a backup that could not be written,
a backup that was saved, a week file for another week, and the sentences that say what importing a backup
would change. Expected words are written out from the rule, not read back from the code."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog

from desktop.native.material import bridge_manage
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, visuals
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.support_prompt_walk import prompt_item
from desktop.tests.sheets.test_material_manage_sheets import _click, _open_account, _said, _type
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME


def test_a_backup_that_cannot_be_written_says_to_choose_another_folder(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nowhere = tmp_path / "no-such-folder" / "backup.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(nowhere), "")))
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "exportAccount")
    _said(shell, "Couldn't save there. Choose another folder, like Documents.", qapp)
    assert not nowhere.exists()


def test_a_saved_backup_says_where_it_went_and_to_keep_it_private(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "mine.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "exportAccount")
    _said(
        shell,
        f"Saved your backup file to {target}. Keep it private: it has all your weeks and homework.",
        qapp,
    )
    assert json.loads(target.read_text())["username"] == USERNAME


def test_a_day_file_for_another_week_is_refused_and_nothing_changes(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    payload = session.day_file(session.paste_destination()[0])
    # Seven days later is the next week, whichever day a week starts on.
    payload["week_start"] = (date.fromisoformat(session.week_start) + timedelta(days=7)).isoformat()
    path = tmp_path / "next-week.json"
    path.write_text(json.dumps(payload))
    before = json.dumps(session.blocks, sort_keys=True)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importFile")
    wait_until(
        qapp, lambda: str(session.message).startswith("Nothing imported"), what=lambda: session.message
    )
    assert session.message.startswith("Nothing imported: this file is for ")
    assert session.message.endswith(". Go to that week, then import again.")
    assert json.dumps(session.blocks, sort_keys=True) == before


# What importing a backup would change ------------------------------------------------------------------


def _ids(count: int) -> list[str]:
    return [f"item-{n}" for n in range(count)]


def _changes(
    weeks: tuple[int, int, int] = (0, 0, 0),
    homework: tuple[int, int, int] = (0, 0, 0),
    routines: tuple[int, int, int] = (0, 0, 0),
    settings: bool = False,
) -> dict:
    def part(counts: tuple[int, int, int]) -> dict:
        added, changed, removed = counts
        return {"added": _ids(added), "changed": _ids(changed), "removed": _ids(removed)}

    return {
        "source_username": "sam",
        "changes": {
            "weeks": part(weeks),
            "assignments": part(homework),
            "routines": part(routines),
            "preferences_changed": settings,
        },
    }


SAFE = "\nFlexWeek saves a copy of this week first, so you can go back."


@pytest.mark.parametrize(
    ("preview", "sentence"),
    [
        (_changes(weeks=(1, 0, 0)), "adds 1 week."),
        (_changes(weeks=(3, 0, 0)), "adds 3 weeks."),
        (_changes(weeks=(0, 2, 0)), "replaces 2 of your weeks."),
        (_changes(weeks=(0, 0, 1)), "deletes 1 of your weeks that isn't in the backup."),
        (_changes(weeks=(0, 0, 4)), "deletes 4 of your weeks that aren't in the backup."),
        (_changes(weeks=(1, 2, 0)), "adds 1 week and replaces 2 of your weeks."),
        (
            _changes(weeks=(2, 1, 3)),
            "adds 2 weeks, replaces 1 of your weeks, and deletes 3 of your weeks that aren't in the backup.",
        ),
        (_changes(homework=(1, 0, 0)), "1 homework changes."),
        (_changes(homework=(1, 1, 0)), "2 homework change."),
        (_changes(homework=(0, 0, 2)), "It also deletes 2 of your homework that aren't in the backup."),
        (_changes(routines=(0, 1, 0)), "1 routine changes."),
        (_changes(routines=(1, 2, 0)), "3 routines change."),
        (_changes(routines=(0, 0, 1)), "It also deletes 1 of your routines that isn't in the backup."),
        (_changes(settings=True), "Your settings will be replaced."),
        (
            _changes(weeks=(0, 1, 0), homework=(0, 2, 1), settings=True),
            "replaces 1 of your weeks. 2 homework change. "
            "It also deletes 1 of your homework that isn't in the backup. Your settings will be replaced.",
        ),
        (_changes(), "Nothing in it is different from your account."),
    ],
)
def test_the_import_question_says_what_the_backup_would_change(
    qapp: QApplication, shell: NativeWindow, sheets, preview: dict, sentence: str
) -> None:
    sheets._ask = bridge_manage.import_question(preview)
    sheets._publish()
    pump(qapp, 30)
    body = f"From sam's backup: {sentence}{SAFE}"
    assert sheets.ask["title"] == "Import backup file?"
    assert sheets.ask["body"] == body
    prompt = prompt_item(shell)
    assert prompt is not None
    assert body in [str(item.property("text")) for item in visuals(prompt)], "the prompt shows it"
    sheets.forceClose()
