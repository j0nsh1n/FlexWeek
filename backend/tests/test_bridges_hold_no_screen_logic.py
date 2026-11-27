"""Screen helpers hold no decision the engine does not already own.

The same scan as test_wrappers_hold_no_engine_logic.py flags a function. A locked file is checked
whole: every flagged function is named with why it stays. A partial file names the functions this
slice moved, and only those are checked. An f-string or str.format that builds a sentence counts
here too. One with no formatted values, or one used only as a dict key or a log line, may be named
with why it stays.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.tests.test_wrappers_hold_no_engine_logic import functions_of, is_stays

ROOT = Path(__file__).resolve().parents[2]

# Whole files. A method stays only when the scanner still flags Qt marshalling it cannot give up.
LOCKED: dict[str, dict[str, str]] = {
    "desktop/native/hours/geometry.py": {},
    "desktop/native/hours/scale.py": {},
    "desktop/native/hours/words.py": {},
    "desktop/native/motion_level.py": {},
    "desktop/native/look.py": {"_cached_look_json": "keeps the engine's look JSON answers in an LRU cache"},
}

# Files that still hold other decisions. Only these functions moved.
PARTIAL: dict[str, set[str]] = {
    "desktop/native/fields.py": {"week_starts_on", "week_start_day", "read_clock"},
    "desktop/native/weekmodel.py": {"homework_time_sentence", "end_after_start_words"},
    "desktop/native/widgets.py": {"overdue_unfinished"},
}

# Sentence-building that stays, by file then function. Empty means none stays.
SENTENCES: dict[str, dict[str, str]] = {}


def _defined(tree: ast.AST) -> set[str]:
    found: set[str] = set()

    def scan(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add(f"{prefix}{node.name}")

    if isinstance(tree, ast.Module):
        scan(tree.body, "")
    return found


def _flagged(tree: ast.AST) -> set[str]:
    return {problem.split(":", 1)[0] for problem in functions_of(tree, set())}


def _formats(node: ast.Call) -> bool:
    if not node.args and not node.keywords:
        return False
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "format") or (
        isinstance(func, ast.Name) and func.id == "format"
    )


def _sentence_hits(node: ast.AST, qual: str, stays: set[str]) -> set[str]:
    found: set[str] = set()

    def walk(item: ast.AST, here: str) -> None:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested = f"{here}.{item.name}"
            if not is_stays(stays, nested):
                found.update(_sentence_hits(item, nested, stays))
            return
        if isinstance(item, ast.Lambda):
            walk(item.body, here)
            return
        built = isinstance(item, ast.JoinedStr) and any(
            isinstance(value, ast.FormattedValue) for value in item.values
        )
        if built or (isinstance(item, ast.Call) and _formats(item)):
            found.add(here)
        for child in ast.iter_child_nodes(item):
            walk(child, here)

    body = node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else [node]
    for stmt in body:
        walk(stmt, qual)
    return found


def _sentences(tree: ast.AST, stays: set[str]) -> set[str]:
    found: set[str] = set()

    def scan(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{node.name}"
                if not is_stays(stays, qual):
                    found.update(_sentence_hits(node, qual, stays))

    if isinstance(tree, ast.Module):
        scan(tree.body, "")
    return found


def _parse(path: str) -> ast.AST:
    file = ROOT / path
    return ast.parse(file.read_text(encoding="utf-8"), filename=str(file))


def _unexplained(path: str, stays: set[str]) -> list[str]:
    tree = _parse(path)
    problems = functions_of(tree, stays)
    allowed = SENTENCES.get(path, {})
    for qual in sorted(_sentences(tree, stays)):
        why = allowed.get(qual, "").strip()
        if not why:
            problems.append(f"{qual}: an f-string or format builds a sentence")
    return problems


def test_locked_bridges_hold_no_screen_logic() -> None:
    for path, stays in LOCKED.items():
        tree = _parse(path)
        defined = _defined(tree)
        missing = sorted(name for name in stays if name not in defined)
        assert not missing, f"{path} names nothing:\n" + "\n".join(missing)
        covered = [
            name
            for name in stays
            if any(name.startswith(f"{other}.") for other in stays if other != name)
        ]
        assert not covered, f"{path} a shorter prefix already covers:\n" + "\n".join(covered)
        flagged = _flagged(tree)
        unused = sorted(
            name
            for name in stays
            if not any(item == name or item.startswith(f"{name}.") for item in flagged)
        )
        assert not unused, f"{path} nothing flagged needs these:\n" + "\n".join(unused)
        blank = sorted(name for name, why in stays.items() if not why.strip())
        assert not blank, f"{path} say why these stay:\n" + "\n".join(blank)
        problems = _unexplained(path, set(stays))
        assert not problems, f"{path}\n" + "\n".join(problems)


def test_partial_bridges_hold_no_screen_logic() -> None:
    for path, names in PARTIAL.items():
        tree = _parse(path)
        defined = _defined(tree)
        missing = sorted(names - defined)
        assert not missing, f"{path} no longer defines:\n" + "\n".join(missing)
        problems = _unexplained(path, defined - names)
        assert not problems, f"{path}\n" + "\n".join(problems)
