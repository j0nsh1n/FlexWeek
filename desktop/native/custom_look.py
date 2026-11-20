"""What a student does with a look of their own: start one, check it reads, keep it by name, share it.
No Qt.

A custom look is one of the ten looks as a starting point and what was changed on it (look.py's
`sanitize_custom` says what may be changed). It is worn as the device look's "custom" entry, and kept
by name in the look file's "saved_looks" (plan, "Customise"). The window reads the saved looks from
the look file and writes them back through `sanitize_saved`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.wire import plain, restore, restored

# Shown when a student has not named the look yet.
UNNAMED = "My look"
# The export file: its kind, so any other JSON is told apart, and the version of its settings.
FILE_KIND = "FlexWeek look"
FILE_VERSION = 1
FILE_MAX_BYTES = 64 * 1024


class LookNameError(ValueError):
    """A name a saved look cannot have, or one no saved look has. Its message is for the student."""


def _text_or_none(value: object) -> str | None:
    """A pack or an accent only matters when it is text; anything else is read as none was given."""
    return value if isinstance(value, str) else None


def base_of(pack: object, look: dict | None) -> str:
    """The id of the look on screen, as a custom look's base: its preset, or else its pack."""
    return str(json.loads(flexweek_engine.look_base_of(json.dumps(_text_or_none(pack)), json.dumps(look))))


def start_custom(pack: object, look: dict | None, accent: object = "default") -> dict:
    """A custom look that draws as the look on screen does, to be changed from there: its base, the
    student's accent, and the knobs they had moved."""
    return json.loads(
        flexweek_engine.look_start(
            json.dumps(_text_or_none(pack)), json.dumps(look), json.dumps(_text_or_none(accent))
        )
    )


def wear(look: dict | None, custom: dict) -> dict:
    """The device look with `custom` worn, its preset and knobs kept for when it is taken off."""
    return json.loads(flexweek_engine.look_wear(json.dumps(look), json.dumps(custom)))


def reset_look(custom: dict) -> dict:
    """Back to its base, as it was before anything was changed; the name stays."""
    return json.loads(flexweek_engine.look_reset(json.dumps(custom)))


def _name(name: object) -> str:
    try:
        return str(flexweek_engine.look_name(name))
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err


def _find(saved: list[dict], name: str) -> int:
    return int(flexweek_engine.look_find(json.dumps(saved), name))


def sanitize_saved(raw: object) -> list[dict]:
    """The saved looks from the look file: each a custom look with a name of its own. One that is
    broken or named twice is left out; the rest load."""
    return json.loads(flexweek_engine.look_saved(raw))


def save_look(saved: list[dict], custom: dict, name: object) -> list[dict]:
    """`custom` kept as `name`, in place of a saved look of that name or after the others."""
    try:
        return json.loads(
            flexweek_engine.look_save(
                json.dumps(saved),
                json.dumps(custom),
                name,
            )
        )
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err


def free_name(saved: list[dict], name: object) -> str:
    """`name` as a new saved look can have it: tidied, and numbered ("My look 2") past the saved looks
    that have it already, since `save_look` puts a look of the same name in their place."""
    try:
        return str(flexweek_engine.free_name(json.dumps(saved), name))
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err


def rename_look(saved: list[dict], old: str, new: object) -> list[dict]:
    try:
        return json.loads(
            flexweek_engine.rename_look(json.dumps(saved), old, new)
        )
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err


def duplicate_look(saved: list[dict], name: str) -> tuple[list[dict], str]:
    """A copy of the saved look `name` after it, as "<name> copy" (then "copy 2" and on), and its name."""
    try:
        kept, copy = flexweek_engine.duplicate_look(json.dumps(saved), name)
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err
    return json.loads(kept), copy


def delete_look(saved: list[dict], name: str) -> list[dict]:
    try:
        return json.loads(flexweek_engine.delete_look(json.dumps(saved), name))
    except flexweek_engine.LookNameProblem as err:
        raise LookNameError(str(err)) from err


def export_look(custom: dict) -> str:
    """A small file to share a look: what kind of file it is, its version, and the look."""
    return str(flexweek_engine.look_export(json.dumps(custom)))


@dataclass(frozen=True)
class Imported:
    """A look read from a file: the look, or None when there is none to use, and what was wrong, in
    words a student can read. A look can come with notes about settings that were left out."""

    look: dict | None
    problems: tuple[str, ...]


def import_look(text: str | bytes) -> Imported:
    size = len(text)
    raw = None
    if size <= FILE_MAX_BYTES:
        try:
            raw = plain(json.loads(text))
        except ValueError:
            raw = None
    look, problems = flexweek_engine.look_import(size, raw)
    return Imported(
        None if look is None else restored(look),
        tuple(restore(problem) for problem in problems),
    )
