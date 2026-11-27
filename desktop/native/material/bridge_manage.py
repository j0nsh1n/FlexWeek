"""What Material's Manage account and Restore points sheets show, and what their buttons do.

The words are the Widgets dialogs' own (settings_copy, account_copy). The actions are the ones
NativeWindow._open_account runs after its dialog closes, with the system's file pickers and the same
questions; the questions are Material prompts here. A password is typed into the sheet, handed to one
action and not kept."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtWidgets import QFileDialog

from desktop.native.account_copy import READ_FAILED, READ_WEEK_FAILED
from desktop.native.calendar import iso_of
from desktop.native.files import parse_import_payload

NO_LOCATION = str(flexweek_engine.VIEW_MANAGE_NO_LOCATION)
# The files the Account sheet moves in and out, in the order the Widgets dialog lists them.
DATA_ACTIONS: tuple[tuple[str, str, str], ...] = flexweek_engine.VIEW_MANAGE_DATA_ACTIONS
# What Material says for the Widgets dialog's "Choose a saved copy."
RESTORE_FIRST = str(flexweek_engine.VIEW_MANAGE_RESTORE_FIRST)
RESTORE_QUESTION: dict[str, Any] = json.loads(flexweek_engine.VIEW_MANAGE_RESTORE_QUESTION_JSON)
_DAY_EXPORT_FILENAME = str(flexweek_engine.VIEW_MANAGE_DAY_EXPORT_FILENAME)
_SELECT_DAY_FIRST = str(flexweek_engine.VIEW_MANAGE_SELECT_DAY_FIRST)


def _where(storage: dict | None) -> str:
    """Where the week is saved: always this computer, since the hosted server is gone (D4)."""
    return str(flexweek_engine.views_manage_where(json.dumps(storage)))


def account_form(storage: dict | None, remaining: int | None) -> dict[str, Any]:
    """Manage account: who is signed in, the password, the recovery codes and the files."""
    return json.loads(flexweek_engine.views_account_form(json.dumps(storage), json.dumps(remaining)))


def restore_form(
    points: list[dict], preview: dict | None, storage: dict | None, selected: str, label: str, note: str
) -> dict[str, Any]:
    """Restore points: the saved copies with their times, a name for a new one, and what the previewed one
    would change."""
    return json.loads(
        flexweek_engine.views_restore_form(
            json.dumps(points), json.dumps(preview), json.dumps(storage), selected, label, note
        )
    )


def delete_question(name: str, storage: dict | None) -> dict[str, Any]:
    return json.loads(flexweek_engine.views_delete_question(name, json.dumps(storage)))


def import_question(preview: dict) -> dict[str, Any]:
    return json.loads(flexweek_engine.views_import_question(json.dumps(preview)))


def replace_week_question(week: str) -> dict[str, Any]:
    return json.loads(flexweek_engine.views_replace_week_question(week))


class AccountActions:
    """The Account sheet's buttons. `ask(question, answers)` poses a Material prompt and runs the handler
    for the answer the student picks; Cancel and Esc run none."""

    def __init__(
        self,
        window: Any,
        ask: Callable[[dict, dict[str, Callable[[], None]]], None],
        close: Callable[[], None],
    ) -> None:
        self._window = window
        self._ask = ask
        self._close = close

    @property
    def _session(self) -> Any:
        return self._window.session

    def change_password(self, password: str, new_password: str) -> None:
        self._session.change_password(password, new_password)

    def replace_codes(self, password: str) -> None:
        self._session.replace_recovery_codes(password)

    def delete(self, password: str) -> None:
        question = json.loads(
            flexweek_engine.views_account_delete_question(
                json.dumps(self._session.account), json.dumps(self._session.storage_info)
            )
        )
        self._ask(question, {"delete": lambda: self._deleted(password)})

    def _deleted(self, password: str) -> None:
        """Delete was asked for over the open sheet. It closes, then the account goes."""
        self._close()
        self._session.delete_account(password)

    def export_account(self, password: str) -> None:
        self._session.export_account(password, self._window._write_account_file)

    def import_account(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Import backup file", "", "JSON (*.json)")
        if not path:
            return
        try:
            raw = Path(path).read_text()
        except (OSError, UnicodeDecodeError):
            self._session._say(READ_FAILED)
            return
        snapshot_json, error = flexweek_engine.views_parse_backup_json(raw)
        if error is not None:
            self._session._say(error)
            return
        self._session.preview_account_import(json.loads(snapshot_json), self._confirm_transfer)

    def _confirm_transfer(self) -> None:
        preview = self._session.transfer_preview
        if preview is None:
            return
        self._ask(import_question(preview), {"import": self._session.apply_account_import})

    def export_week(self) -> None:
        name = str(flexweek_engine.views_week_export_filename(self._session.week_start))
        self._window._write_json(name, self._session.week_file())

    def export_day(self) -> None:
        destination = self._session.paste_destination()
        if destination is None:
            self._session._say(_SELECT_DAY_FIRST)
            return
        self._window._write_json(_DAY_EXPORT_FILENAME, self._session.day_file(destination[0]))

    def import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Import week or day", "", "JSON (*.json)")
        if not path:
            return
        try:
            raw = Path(path).read_text()
        except (OSError, UnicodeDecodeError):
            self._session._say(READ_WEEK_FAILED)
            return
        parsed = parse_import_payload(raw)
        error, question_json = flexweek_engine.views_decide_week_import(
            json.dumps(parsed),
            bool(self._session.blocks),
            self._session.week_start,
            iso_of(self._window._today()),
        )
        if error is not None:
            self._session._say(error)
            return
        if question_json is not None:
            self._ask(
                json.loads(question_json),
                {"replace": lambda: self._session.import_week_file(raw, replace=True)},
            )
            return
        self._session.import_week_file(raw)
