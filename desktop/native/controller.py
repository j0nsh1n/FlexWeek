"""Account, week drafts and solver results for the native desktop window."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from backend.models import Assignment, TimeBlock
from backend.weeks import current_week_start
from desktop.native.client import ApiError, NativeClient


def session_days(week_start: str, due: str) -> list[int]:
    monday = date.fromisoformat(week_start)
    due_day = date.fromisoformat(due[:10])
    last = monday + timedelta(days=6)
    if due_day < monday:
        return [0]
    if due_day > last:
        return [0, 1, 2, 3, 4]
    return list(range(due_day.weekday() + 1))


def _assignment_change(item: dict) -> dict:
    body = Assignment.model_validate(
        {key: value for key, value in item.items() if key in Assignment.model_fields}
    )
    dumped = body.model_dump(mode="json")
    revision = dumped.pop("revision")
    return {"id": body.id, "assignment": dumped, "revision": revision}


def _week_write(week_start: str, blocks: list[dict], revision: int) -> dict:
    return {
        "week_start": week_start,
        "blocks": [TimeBlock.model_validate(block).model_dump(mode="json") for block in blocks],
        "revision": revision,
    }


class NativeSession(QObject):
    account_changed = Signal(object)
    recovery_codes = Signal(list)
    week_changed = Signal()
    busy_changed = Signal(bool)
    status = Signal(str)

    def __init__(self, origin: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.client = NativeClient(origin, self)
        self.client.expired.connect(self._on_expired)
        self.account: dict | None = None
        self.week_start = current_week_start()
        self.blocks: list[dict] = []
        self.revision = 0
        self.assignments: dict[str, dict] = {}
        self.dirty_assignments: set[str] = set()
        self.trace: dict | None = None
        self.dirty = False
        self.conflict = False
        self.pending_save: dict | None = None
        self.busy = False
        self.message = ""
        self._ticket = 0

    def _say(self, text: str) -> None:
        self.message = text
        self.status.emit(text)

    def _begin(self) -> int:
        self._ticket += 1
        self.busy = True
        self.busy_changed.emit(True)
        return self._ticket

    def _alive(self, ticket: int) -> bool:
        return ticket == self._ticket

    def _idle(self, ticket: int) -> bool:
        if not self._alive(ticket):
            return False
        self.busy = False
        self.busy_changed.emit(False)
        return True

    def _fail(self, ticket: int, error: ApiError) -> None:
        if self._idle(ticket):
            self._say(error.message)

    def _clear_local(self) -> None:
        self.account = None
        self.week_start = current_week_start()
        self.blocks = []
        self.revision = 0
        self.assignments = {}
        self.dirty_assignments.clear()
        self.trace = None
        self.dirty = False
        self.conflict = False
        self.pending_save = None

    def _on_expired(self) -> None:
        self._ticket += 1
        self.busy = False
        self.busy_changed.emit(False)
        self.client.reset()
        self._clear_local()
        self.account_changed.emit(None)
        self.week_changed.emit()
        self._say("Please sign in again, or check your username and password.")

    def register(self, username: str, password: str) -> None:
        ticket = self._begin()
        self._say("Creating account…")

        def ok(data: dict) -> None:
            if not self._alive(ticket):
                return
            self.client.set_account(data)
            self.account = {"id": data["id"], "username": data["username"]}
            self.busy = False
            self.busy_changed.emit(False)
            self.account_changed.emit(self.account)
            self.recovery_codes.emit(list(data.get("recovery_codes") or []))
            self._say("Save these recovery codes before continuing.")

        self.client.request(
            "POST",
            "/api/auth/register",
            {"username": username, "password": password},
            ok,
            lambda error: self._fail(ticket, error),
        )

    def login(self, username: str, password: str) -> None:
        ticket = self._begin()
        self._say("Signing in…")

        def ok(data: dict) -> None:
            if not self._alive(ticket):
                return
            self.client.set_account(data)
            self.account = {"id": data["id"], "username": data["username"]}
            self.account_changed.emit(self.account)
            self.load_week(self.week_start)

        self.client.request(
            "POST",
            "/api/auth/login",
            {"username": username, "password": password},
            ok,
            lambda error: self._fail(ticket, error),
        )

    def finish_recovery(self) -> None:
        if self.account is None:
            return
        self.load_week(current_week_start())

    def logout(self) -> None:
        ticket = self._begin()
        self._say("Signing out…")

        def finish() -> None:
            if not self._alive(ticket):
                return
            self.client.reset()
            self._clear_local()
            self.busy = False
            self.busy_changed.emit(False)
            self.account_changed.emit(None)
            self.week_changed.emit()
            self._say("Signed out.")

        if self.client.account is None:
            finish()
            return
        self.client.request("POST", "/api/auth/logout", None, lambda _data: finish(), lambda _error: finish())

    def load_week(self, week_start: str | None = None) -> None:
        start = week_start or current_week_start()
        ticket = self._begin()
        self.week_start = start
        self._say("Loading…")

        def ok(data: dict) -> None:
            if not self._alive(ticket) or self.client.account is None:
                return
            self.blocks = list(data["blocks"])
            self.revision = data["revision"]
            self.week_start = data["week_start"]
            self.dirty = False
            self.conflict = False
            self.pending_save = None
            self.trace = None
            self._load_assignments(ticket)

        self.client.request(
            "GET",
            f"/api/week?week_start={start}",
            None,
            ok,
            lambda error: self._fail(ticket, error),
        )

    def _load_assignments(self, ticket: int) -> None:
        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.assignments = {item["id"]: item for item in data["assignments"]}
            self.dirty_assignments.clear()
            self._say("This week.")
            self.week_changed.emit()

        self.client.request(
            "GET",
            f"/api/assignments?week_start={self.week_start}",
            None,
            ok,
            lambda error: self._fail(ticket, error),
        )

    def reload(self) -> None:
        self.pending_save = None
        self.dirty = False
        self.conflict = False
        self.load_week(self.week_start)

    def _touch(self) -> None:
        self.dirty = True
        self.conflict = False
        self.pending_save = None
        self.week_changed.emit()

    def add_block(self, block: dict) -> None:
        validated = TimeBlock.model_validate(block).model_dump(mode="json")
        self.blocks = [item for item in self.blocks if item["id"] != validated["id"]] + [validated]
        self._touch()

    def add_homework(self, assignment: dict) -> None:
        body = Assignment.model_validate(
            {key: value for key, value in assignment.items() if key in Assignment.model_fields}
        ).model_dump(mode="json")
        session = TimeBlock.model_validate(
            {
                "id": str(uuid4()),
                "title": body["title"],
                "kind": "flexible",
                "duration_min": body["estimate_min"],
                "days": session_days(self.week_start, body["due"]),
                "priority": body["priority"],
                "energy": body["energy"],
                "assignment_id": body["id"],
            }
        ).model_dump(mode="json")
        self.assignments[body["id"]] = body
        self.dirty_assignments.add(body["id"])
        self.blocks = [item for item in self.blocks if item.get("assignment_id") != body["id"]] + [session]
        self._touch()

    def save(self) -> None:
        if self.account is None or self.conflict:
            return
        if self.pending_save is None:
            self.pending_save = {
                "weeks": [_week_write(self.week_start, self.blocks, self.revision)],
                "assignments": [
                    _assignment_change(self.assignments[item_id])
                    for item_id in sorted(self.dirty_assignments)
                ],
                "operation_id": str(uuid4()),
            }
        ticket = self._begin()
        self._say("Saving…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            week = data["weeks"][0]
            self.blocks = list(week["blocks"])
            self.revision = week["revision"]
            self.dirty = False
            self.conflict = False
            for result in data.get("assignments", []):
                self.dirty_assignments.discard(result["id"])
                if result.get("assignment"):
                    stored = dict(result["assignment"])
                    stored["revision"] = result["revision"]
                    self.assignments[result["id"]] = stored
            self.pending_save = None
            self._say("Saved.")
            self.week_changed.emit()

        def err(error: ApiError) -> None:
            if not self._idle(ticket):
                return
            self.conflict = error.status == 409
            self._say("Not saved. " + error.message)
            self.week_changed.emit()

        self.client.request("POST", "/api/changes", deepcopy(self.pending_save), ok, err)

    def retry_save(self) -> None:
        if self.pending_save is not None and not self.conflict:
            self.save()

    def solve(self) -> None:
        ticket = self._begin()
        self._say("Planning…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.trace = data
            placed = len(data.get("placed") or [])
            unplaced = len(data.get("unplaced") or [])
            notes = [item["message"] for item in data.get("explanations") or [] if item.get("message")]
            summary = f"Placed {placed} of {placed + unplaced}."
            if notes:
                summary += " " + notes[0]
            self._say(summary)
            self.week_changed.emit()

        self.client.request(
            "POST",
            "/api/solve",
            {"blocks": self.blocks, "week_start": self.week_start},
            ok,
            lambda error: self._fail(ticket, error),
        )
