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

from PySide6.QtWidgets import QFileDialog

from desktop.native.account_copy import (
    DELETE_ACCOUNT_QUESTION,
    READ_FAILED,
    READ_WEEK_FAILED,
    REPLACE_WEEK_QUESTION,
)
from desktop.native.files import EXPORT_FORMAT, parse_import_payload
from desktop.native.reuse import week_label
from desktop.native.settings_copy import (
    ACCOUNT_CODES_NOTE,
    ACCOUNT_DATA_NOTE,
    ACCOUNT_PASSWORD_NOTE,
    recovery_status,
    restore_parts,
    restore_row,
    restore_summary,
    transfer_summary,
)

NO_LOCATION = "Backup location unavailable"
# The files the Account sheet moves in and out, in the order the Widgets dialog lists them.
DATA_ACTIONS = (
    ("exportAccount", "export", "Export backup file"),
    ("importAccount", "import", "Import backup file"),
    ("exportWeek", "week", "Export week"),
    ("exportDay", "day", "Export day"),
    ("importFile", "import-week", "Import week or day file"),
)
RESTORE_QUESTION = {
    "id": "restore-copy",
    "title": "Restore",
    "body": "Restore this snapshot? FlexWeek saves a restore point first.",
    "answers": [
        {"id": "not", "label": "Not now", "kind": "text", "default": True},
        {"id": "restore", "label": "Restore", "kind": "filled"},
    ],
}


def _where(storage: dict | None) -> str:
    return "your FlexWeek server" if (storage or {}).get("mode") == "hosted" else "this computer"


def account_form(storage: dict | None, remaining: int | None) -> dict[str, Any]:
    """Manage account: who is signed in, the password, the recovery codes and the files."""
    return {
        "heading": "Manage account",
        "info": f"Signed in as {(storage or {}).get('username') or ''}. "
        f"Your week is saved on {_where(storage)}, under this account.",
        "passwordNote": ACCOUNT_PASSWORD_NOTE,
        "codesNote": ACCOUNT_CODES_NOTE,
        "codesStatus": recovery_status(remaining),
        "codesProblem": remaining == 0,
        "dataNote": ACCOUNT_DATA_NOTE,
        "files": [{"name": name, "id": action, "label": label} for name, action, label in DATA_ACTIONS],
    }


def restore_form(
    points: list[dict], preview: dict | None, storage: dict | None, selected: str, label: str, note: str
) -> dict[str, Any]:
    """Restore points: the saved copies with their times, a name for a new one, and what the previewed one
    would change."""
    return {
        "heading": "Restore points",
        "where": (storage or {}).get("label") or NO_LOCATION,
        "label": label,
        "points": [
            {
                "id": str(point.get("id")),
                "title": restore_parts(point)[0],
                "detail": restore_parts(point)[1],
                "text": restore_row(point),
            }
            for point in points
        ],
        "selected": selected,
        "summary": restore_summary(preview) if preview and preview.get("id") == selected else "",
        "note": note,
    }


def delete_question(name: str, storage: dict | None) -> dict[str, Any]:
    return {
        "id": "delete-account",
        "title": "Delete account",
        "body": DELETE_ACCOUNT_QUESTION.format(name=name, where=_where(storage)),
        "answers": [
            {"id": "stay", "label": "Cancel", "kind": "text", "default": True},
            {"id": "delete", "label": f"Delete {name}", "kind": "filled"},
        ],
    }


def import_question(preview: dict) -> dict[str, Any]:
    source = str(preview.get("source_username") or "another account")
    return {
        "id": "import-account",
        "title": "Import backup file?",
        "body": f"From {source}'s backup: {transfer_summary(preview)}\n"
        "FlexWeek saves a restore point first, so you can go back.",
        "answers": [
            {"id": "stay", "label": "Cancel", "kind": "text", "default": True},
            {"id": "import", "label": "Import", "kind": "filled"},
        ],
    }


def replace_week_question(week: str) -> dict[str, Any]:
    return {
        "id": "replace-week",
        "title": "Replace week",
        "body": REPLACE_WEEK_QUESTION.format(week=week),
        "answers": [
            {"id": "stay", "label": "Cancel", "kind": "text", "default": True},
            {"id": "replace", "label": "Replace week", "kind": "filled"},
        ],
    }


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
        name = (self._session.account or {}).get("username") or "this account"
        self._ask(
            delete_question(name, self._session.storage_info),
            {"delete": lambda: self._deleted(password)},
        )

    def _deleted(self, password: str) -> None:
        """Delete was asked for over the open sheet. It closes, then the account goes."""
        self._close()
        self._session.delete_account(password)

    def export_account(self, password: str) -> None:
        self._session.export_account(password, self._window._write_account_file)

    def import_account(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self._window, "Import backup file", "", "JSON (*.json)")
        if not path:
            return
        try:
            snapshot = json.loads(Path(path).read_text())
        except (OSError, UnicodeDecodeError, ValueError):
            self._session._say(READ_FAILED)
            return
        if not isinstance(snapshot, dict):
            self._session._say(READ_FAILED)
            return
        self._session.preview_account_import(snapshot, self._confirm_transfer)

    def _confirm_transfer(self) -> None:
        preview = self._session.transfer_preview
        if preview is None:
            return
        self._ask(import_question(preview), {"import": self._session.apply_account_import})

    def export_week(self) -> None:
        self._window._write_json("flexweek-" + self._session.week_start + ".json", self._session.week_file())

    def export_day(self) -> None:
        destination = self._session.paste_destination()
        if destination is None:
            self._session._say("Select a day first.")
            return
        self._window._write_json("flexweek-day.json", self._session.day_file(destination[0]))

    def import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self._window, "Import week or day", "", "JSON (*.json)")
        if not path:
            return
        try:
            raw = Path(path).read_text()
        except (OSError, UnicodeDecodeError):
            self._session._say(READ_WEEK_FAILED)
            return
        parsed = parse_import_payload(raw)
        if parsed.get("error"):
            self._session._say(parsed["error"])
            return
        if parsed.get("format") == EXPORT_FORMAT and self._session.blocks:
            week = week_label(self._session.week_start, self._window._today())
            self._ask(
                replace_week_question(week),
                {"replace": lambda: self._session.import_week_file(raw, replace=True)},
            )
            return
        self._session.import_week_file(raw)
