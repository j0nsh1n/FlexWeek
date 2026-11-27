"""Keep me signed in: the session a student chose to keep on this computer, for one database.

The token is the opaque one the server set as a cookie. Anyone who can read this file can already read
the database it opens, so on a student's own computer it adds no reach. The choice exists for a shared
computer, and Log out removes the file. The server ends a session after seven days, or thirty if
Keep me signed in was ticked, and renews that length on each use.

Beside it sits a second small file: the text size and whether High contrast was on in the last look
worn, so the screens shown before sign-in read as the student left them. Log out keeps it; it holds
no colours, no accent and nothing about a person.

A third file keeps each account's focus timer, so closing FlexWeek does not lose it. Signing out,
a session ending, and deleting the account remove that account's timer. It holds no name.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path

# secrets.token_urlsafe(32) in backend/storage.py. Anything else is not a session, and it goes into a
# cookie header, so it is refused rather than sent.
_TOKEN = re.compile(r"[A-Za-z0-9_-]{20,128}")
TEXT_SIZES = ("small", "normal", "large")
# A few accounts' timers fit under this. A larger file is not a timer file, and it is not read whole.
_FOCUS_MAX_BYTES = 64 * 1024


class KeptSession:
    def __init__(self, path: Path) -> None:
        self.path = path
        # Someone has signed in here before, kept or not. Log out forgets the session, not this, so
        # the sign-in card can greet a first launch differently from a return.
        self.seen = path.with_name(path.stem + ".seen")
        # The text size and High contrast of the last look worn here, for the screens shown while nobody
        # is signed in. The account id is only there so deleting that account can clear the file.
        self.look = path.with_name(path.stem + ".look.json")
        self.focus = path.with_name(path.stem + ".focus.json")

    def signed_in_before(self) -> bool:
        return self.seen.exists() or self.path.exists()

    def note_sign_in(self) -> None:
        self.seen.parent.mkdir(parents=True, exist_ok=True)
        self.seen.touch()

    def token(self) -> str | None:
        try:
            stored = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return None
        token = stored.get("token") if isinstance(stored, dict) else None
        return token if isinstance(token, str) and _TOKEN.fullmatch(token) else None

    def keep(self, token: str) -> None:
        if not _TOKEN.fullmatch(token):
            raise ValueError("That is not a FlexWeek session.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        # Created readable by this user only, then moved into place, so no one else ever sees it and a
        # crash never leaves half a file.
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "w") as out:
            json.dump({"token": token}, out)
        os.replace(temporary, self.path)

    def forget(self) -> None:
        self.path.unlink(missing_ok=True)

    def read_focus(self) -> str | None:
        # A focus file is optional. Anything wrong with reading it is no timers, never an error at startup.
        try:
            with self.focus.open("rb") as handle:
                raw = handle.read(_FOCUS_MAX_BYTES + 1)
            if len(raw) > _FOCUS_MAX_BYTES:
                return None
            return raw.decode("utf-8")
        except (OSError, UnicodeError, MemoryError):
            return None

    def write_focus(self, text: str) -> None:
        self.focus.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.focus.with_name(self.focus.name + ".tmp")
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(temporary, self.focus)

    def forget_focus(self, account_id: int) -> None:
        # No file yet means this account has nothing to remove, and sign-out should not create one.
        text = self.read_focus()
        if text is None:
            return
        import flexweek_engine

        loaded = json.loads(flexweek_engine.session_focus_load_kept(json.dumps({"text": text})))
        # A newer format stays on disk. This run's timers are kept in memory instead.
        if loaded.get("sealed"):
            return
        removed = json.loads(
            flexweek_engine.session_focus_remove_kept(
                json.dumps({"entries": loaded["entries"], "account_id": account_id})
            )
        )
        # Nothing of this account was stored, so the file is already what a write would make.
        if not removed.get("changed"):
            return
        body = json.loads(flexweek_engine.session_focus_kept_text(json.dumps(removed)))
        self.write_focus(body["text"])

    def forget_all_focus(self) -> None:
        self.focus.unlink(missing_ok=True)

    def carry_look(self, account: str, text: str, contrast: bool) -> None:
        if self.carried_look() == (text, contrast) and self._look_owner() == account:
            return
        self.look.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.look.with_name(self.look.name + ".tmp")
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "w") as out:
            json.dump({"account": account, "text": text, "contrast": contrast}, out)
        os.replace(temporary, self.look)

    def carried_look(self) -> tuple[str, bool] | None:
        """The text size and whether High contrast was on, or None when no look was carried here."""
        stored = self._read_look()
        text, contrast = stored.get("text"), stored.get("contrast")
        if text not in TEXT_SIZES or not isinstance(contrast, bool):
            return None
        return text, contrast

    def forget_look(self, account: str) -> None:
        if self._look_owner() == account:
            self.look.unlink(missing_ok=True)

    def _look_owner(self) -> object:
        return self._read_look().get("account")

    def _read_look(self) -> dict:
        try:
            stored = json.loads(self.look.read_text())
        except (OSError, ValueError):
            return {}
        return stored if isinstance(stored, dict) else {}
