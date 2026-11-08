"""Changes another program made to this computer's database, such as the assistant's (`flexweek-mcp`),
so the open window can show them without a restart.

The window's own writes go through its local server and land in the same file, so a change to the
file alone says nothing about who made it. What the window holds says that: a change it made itself
leaves the stored revisions equal to its own once the save's reply is in."""

from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

# The MCP server keys each write it remembers as "mcp:<operation_id>" (engine/mcp/src/tools/write.rs),
# and the window's own operation ids are bare UUIDs, so a new row with this prefix is the assistant's.
ASSISTANT_OPERATIONS = "mcp:%"


@dataclass(frozen=True)
class Stored:
    """What the database holds for the open week and the account's homework."""

    week_revision: int
    assignment_revisions: dict[str, int]
    assistant_seq: int


def file_stamp(database: Path) -> bytes | None:
    """The database header's change counter (bytes 24-27), which SQLite bumps on every commit in
    rollback-journal mode, the only mode the store uses. Reading it costs one small read and takes no
    lock, so it can run on the window's thread every few seconds."""
    try:
        with database.open("rb") as handle:
            header = handle.read(28)
    except OSError:
        return None
    return header[24:28] if len(header) == 28 else None


class OutsideWatch:
    """Looks inside the database only after its change counter moved since the last settled look. A
    look opens its own short read-only connection that never waits for a lock: a busy database is
    looked at again on the next tick."""

    def __init__(self, database: Path) -> None:
        self.database = database
        self._settled: bytes | None = None
        self._looked: bytes | None = None
        # The newest assistant write of any account when the watch starts: seq numbers are shared by
        # every account, so this account's next write is newer than it. Unknown (None) only when the
        # database cannot be read now; the first look then sets the mark.
        self._assistant_seq: int | None = None
        with contextlib.suppress(sqlite3.Error), self._reader() as db:
            (self._assistant_seq,) = db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM operations WHERE operation_id LIKE ?",
                (ASSISTANT_OPERATIONS,),
            ).fetchone()

    def _reader(self) -> contextlib.closing[sqlite3.Connection]:
        # Read-only, as linked_phone_at_launch reads it, and never waiting: this runs on the window's
        # thread, and a commit in progress only means looking again on the next tick.
        return contextlib.closing(
            sqlite3.connect(f"{self.database.resolve().as_uri()}?mode=ro", uri=True, timeout=0)
        )

    def look(self, user_id: int, week_start: str) -> Stored | None:
        """What is stored now, or None when nothing was committed since the last settled look."""
        stamp = file_stamp(self.database)
        if stamp is None or stamp == self._settled:
            return None
        try:
            with self._reader() as db:
                week = db.execute(
                    "SELECT revision FROM weeks WHERE user_id = ? AND week_start = ?", (user_id, week_start)
                ).fetchone()
                rows = db.execute("SELECT id, revision FROM assignments WHERE user_id = ?", (user_id,))
                revisions = dict(rows.fetchall())
                (seq,) = db.execute(
                    "SELECT COALESCE(MAX(seq), 0) FROM operations WHERE user_id = ? AND operation_id LIKE ?",
                    (user_id, ASSISTANT_OPERATIONS),
                ).fetchone()
        except sqlite3.Error:
            return None
        self._looked = stamp
        return Stored(int(week[0]) if week else 0, revisions, int(seq))

    def assistant_wrote(self, stored: Stored) -> bool:
        """The assistant saved a change for this account since the watch started or the last settled look."""
        return self._assistant_seq is not None and stored.assistant_seq > self._assistant_seq

    def settle(self, stored: Stored) -> None:
        """`stored` has been shown, or set aside as the student's conflict to resolve."""
        self._settled = self._looked
        self._assistant_seq = stored.assistant_seq


def differs(stored: Stored, revision: int, assignments: dict[str, dict], unsaved: set[str]) -> bool:
    """The window holds another revision of the open week or of some homework than the database. Homework
    the student changed and has not saved yet is left out: its revision has not moved on either side."""
    if stored.week_revision != revision:
        return True
    held = {key: item.get("revision") for key, item in assignments.items() if key not in unsaved}
    kept = {key: value for key, value in stored.assignment_revisions.items() if key not in unsaved}
    return held != kept
