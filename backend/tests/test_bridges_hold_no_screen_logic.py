"""Screen helpers hold no decision the engine does not already own.

The same scan as test_wrappers_hold_no_engine_logic.py flags a function, plus three things a
screen helper hides decisions behind: an f-string or format call that builds a sentence, an `if` on
anything but `is None`, and a `match`. A locked file is checked whole: every flagged function is
named with why it stays. A partial file names the functions this slice moved, and only those are
checked.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.tests.test_wrappers_hold_no_engine_logic import functions_of, is_none_check, is_stays

ROOT = Path(__file__).resolve().parents[2]

# Whole files. A method stays only when the scanner still flags Qt marshalling it cannot give up.
LOCKED: dict[str, dict[str, str]] = {
    "desktop/native/hours/geometry.py": {},
    "desktop/native/hours/month_cells.py": {},
    "desktop/native/hours/scale.py": {},
    "desktop/native/hours/words.py": {},
    "desktop/native/motion_level.py": {},
    "desktop/native/look.py": {"_cached_look_json": "keeps the engine's look JSON answers in an LRU cache"},
    "desktop/native/sheet_rules.py": {},
    "desktop/native/settings_copy.py": {
        "_seen_weekday": "reads the computer's local weekday name for the engine"
    },
    "desktop/native/account_copy.py": {},
    "desktop/native/material/bridge_month.py": {
        "MonthBridge._note": "emits this bridge's and its parent shell's Qt changed signals",
        "MonthBridge._publish": "updates Qt list models only when rows changed and emits Qt signals",
    },
    "desktop/native/material/bridge_week.py": {
        "_steady_ms": "reads the monotonic clock in milliseconds for the engine",
        "_moment": "reads the session wall clock as local datetime for the engine",
        "WeekBridge._connect_session": "connects Qt signals on the session to this bridge's slots",
        "WeekBridge._publish": "updates Qt list models only when rows changed and emits Qt signals",
    },
    "desktop/native/material/theme.py": {
        "tokens_path": "reads the computer's font and theme locations for the engine",
        "qml_path": "locates the QML files the Qt shell loads",
        "_schemes": "keeps the engine's theme answers in a cache",
        "register_fonts": "registers the bundled fonts with Qt",
        "store_material": "writes the look file with Python's JSON spelling",
    },
    "desktop/native/layout_choice.py": {},
}

# Files that still hold other decisions. Only these functions moved.
PARTIAL: dict[str, set[str]] = {
    "desktop/native/fields.py": {"week_starts_on", "week_start_day", "read_clock"},
    "desktop/native/weekmodel.py": {"homework_time_sentence", "end_after_start_words"},
    "desktop/native/widgets.py": {"overdue_unfinished"},
}


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


def _formats(node: ast.Call) -> bool:
    if not node.args and not node.keywords:
        return False
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr in {"format", "format_map"}) or (
        isinstance(func, ast.Name) and func.id == "format"
    )


def _choice(test: ast.expr) -> bool:
    """An `if` that decides: anything but `x is None` / `x is not None`."""
    return not (isinstance(test, ast.Compare) and is_none_check(test))


def _screen_hits(node: ast.AST, qual: str, stays: set[str]) -> list[str]:
    found: list[str] = []

    def walk(item: ast.AST, here: str) -> None:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested = f"{here}.{item.name}"
            if not is_stays(stays, nested):
                found.extend(_screen_hits(item, nested, stays))
            return
        if isinstance(item, ast.Lambda):
            walk(item.body, here)
            return
        built = isinstance(item, ast.JoinedStr) and any(
            isinstance(value, ast.FormattedValue) for value in item.values
        )
        if built or (isinstance(item, ast.Call) and _formats(item)):
            found.append(f"{here}: an f-string or format builds a sentence")
        elif isinstance(item, (ast.If, ast.IfExp, ast.While)) and _choice(item.test):
            found.append(f"{here}: an if decides")
        elif isinstance(item, ast.Match):
            found.append(f"{here}: a match decides")
        for child in ast.iter_child_nodes(item):
            walk(child, here)

    body = node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else [node]
    for stmt in body:
        walk(stmt, qual)
    return found


def _problems(tree: ast.AST, stays: set[str]) -> list[str]:
    """Every decision outside `stays`: the wrappers' scan, then the screen helpers' own checks."""
    problems = functions_of(tree, stays)

    def scan(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{node.name}"
                if not is_stays(stays, qual):
                    problems.extend(_screen_hits(node, qual, stays))

    if isinstance(tree, ast.Module):
        scan(tree.body, "")
    return sorted(set(problems))


def _flagged(tree: ast.AST) -> set[str]:
    return {problem.split(":", 1)[0] for problem in _problems(tree, set())}


def _parse(path: str) -> ast.AST:
    file = ROOT / path
    return ast.parse(file.read_text(encoding="utf-8"), filename=str(file))


def test_locked_bridges_hold_no_screen_logic() -> None:
    for path, stays in LOCKED.items():
        tree = _parse(path)
        defined = _defined(tree)
        missing = sorted(name for name in stays if name not in defined)
        assert not missing, f"{path} names nothing:\n" + "\n".join(missing)
        covered = [
            name for name in stays if any(name.startswith(f"{other}.") for other in stays if other != name)
        ]
        assert not covered, f"{path} a shorter prefix already covers:\n" + "\n".join(covered)
        flagged = _flagged(tree)
        unused = sorted(
            name for name in stays if not any(item == name or item.startswith(f"{name}.") for item in flagged)
        )
        assert not unused, f"{path} nothing flagged needs these:\n" + "\n".join(unused)
        blank = sorted(name for name, why in stays.items() if not why.strip())
        assert not blank, f"{path} say why these stay:\n" + "\n".join(blank)
        problems = _problems(tree, set(stays))
        assert not problems, f"{path}\n" + "\n".join(problems)


def test_partial_bridges_hold_no_screen_logic() -> None:
    for path, names in PARTIAL.items():
        tree = _parse(path)
        defined = _defined(tree)
        missing = sorted(names - defined)
        assert not missing, f"{path} no longer defines:\n" + "\n".join(missing)
        problems = _problems(tree, defined - names)
        assert not problems, f"{path}\n" + "\n".join(problems)
