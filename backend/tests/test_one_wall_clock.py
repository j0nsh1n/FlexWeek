"""The app and its tests read the date and time only through backend.clock, so the tests' fake clock
(the root conftest.py) is the only time any test sees."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("backend", "desktop", "conftest.py")
# backend/clock.py is the clock. The rest compare against times written on the real clock by
# something no test can set: downloads' file times (the updater) and the sync service's own stamps
# (pairing expiry, a phone last seen).
ALLOWED = {
    ("backend/clock.py", "time.time"),
    ("desktop/native/updater.py", "time.time"),
    ("desktop/native/devices.py", "datetime.now"),
    ("backend/tests/test_sync_pairing_and_removal.py", "time.time"),
}
# Python calls that return the current date or time, by the last two names of what is called.
WALL_CLOCK = {
    ("date", "today"),
    ("datetime", "today"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("time", "time"),
    ("time", "time_ns"),
    ("QDate", "currentDate"),
    ("QTime", "currentTime"),
    ("QDateTime", "currentDateTime"),
    ("QDateTime", "currentDateTimeUtc"),
    ("QDateTime", "currentMSecsSinceEpoch"),
    ("QDateTime", "currentSecsSinceEpoch"),
}
# These read the current time only when given no time to work on.
WALL_CLOCK_WITHOUT_ARGUMENTS = {("time", "localtime"), ("time", "gmtime"), ("time", "ctime")}
QML_WALL_CLOCK = re.compile(r"\bDate\.now\(\)|\bnew\s+Date\(\s*\)")


# A class reached through its module (datetime.date, QtCore.QDate). Any other attribute is an
# object's own, as a time field's self.time.time().
CLASSES = {"date", "datetime", "QDate", "QTime", "QDateTime"}


def imported_names(tree: ast.Module) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Names a file gave the clock's modules and classes (`import time as t`, `from datetime import
    datetime as DT`), and the clock functions it imported by name (`from time import time`)."""
    owners: dict[str, str] = {}
    functions: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name in {"time", "datetime"}:
                    owners[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[-1]
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name in CLASSES:
                    owners[local] = alias.name
                elif (module, alias.name) in WALL_CLOCK | WALL_CLOCK_WITHOUT_ARGUMENTS:
                    functions[local] = (module, alias.name)
    return owners, functions


def called_name(
    call: ast.Call, owners: dict[str, str], functions: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    func = call.func
    if isinstance(func, ast.Name):
        return functions.get(func.id)
    if not isinstance(func, ast.Attribute):
        return None
    owner = func.value
    if isinstance(owner, ast.Name):
        return owners.get(owner.id, owner.id), func.attr
    if isinstance(owner, ast.Attribute) and owner.attr in CLASSES and isinstance(owner.value, ast.Name):
        return owner.attr, func.attr
    return None


def python_files() -> list[Path]:
    found: list[Path] = []
    for name in SCANNED:
        path = ROOT / name
        found.extend([path] if path.is_file() else sorted(path.rglob("*.py")))
    return [path for path in found if ".venv" not in path.parts and "__pycache__" not in path.parts]


def wall_clock_reads(source: str) -> list[tuple[int, str]]:
    found = []
    tree = ast.parse(source)
    owners, functions = imported_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = called_name(node, owners, functions)
        if name is None:
            continue
        given = node.args or node.keywords
        if name in WALL_CLOCK or (name in WALL_CLOCK_WITHOUT_ARGUMENTS and not given):
            found.append((node.lineno, ".".join(name)))
        elif name == ("time", "strftime") and len(node.args) < 2:
            found.append((node.lineno, "time.strftime"))
    return found


def test_no_python_file_reads_the_wall_clock_itself() -> None:
    reads = []
    for path in python_files():
        where = path.relative_to(ROOT).as_posix()
        for line, name in wall_clock_reads(path.read_text(encoding="utf-8")):
            if (where, name) not in ALLOWED:
                reads.append(f"{where}:{line} {name}()")
    assert reads == [], "read the time through backend.clock instead:\n" + "\n".join(reads)


def test_no_qml_reads_the_wall_clock_itself() -> None:
    reads = []
    for path in sorted((ROOT / "desktop").rglob("*")):
        if path.suffix not in {".qml", ".js"} or ".venv" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if QML_WALL_CLOCK.search(line):
                reads.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    assert reads == [], "QML takes the time from its bridge, which reads backend.clock:\n" + "\n".join(reads)


def test_the_scan_finds_each_kind_of_wall_clock_read() -> None:
    source = "\n".join(
        [
            "date.today()",
            "datetime.datetime.now()",
            "time.time()",
            "QDate.currentDate()",
            "time.localtime()",
            "time.strftime('%H')",
            "time.localtime(5)",
            "time.strftime('%H', parts)",
            "wall_clock.today()",
            "self.time.time()",
        ]
    )
    assert [name for _line, name in wall_clock_reads(source)] == [
        "date.today",
        "datetime.now",
        "time.time",
        "QDate.currentDate",
        "time.localtime",
        "time.strftime",
    ]
    assert QML_WALL_CLOCK.search("var t = Date.now()") and QML_WALL_CLOCK.search("new Date()")
    assert not QML_WALL_CLOCK.search("new Date(2026, 1, 1)")


def test_the_scan_follows_names_a_file_gives_the_clock() -> None:
    source = "\n".join(
        [
            "from time import time",
            "from time import time as moment",
            "from datetime import datetime as DT",
            "import datetime as dt",
            "import time as t",
            "from PySide6.QtCore import QDate as Day",
            "time()",
            "moment()",
            "DT.now()",
            "dt.date.today()",
            "t.time()",
            "Day.currentDate()",
            "t.monotonic()",
        ]
    )
    assert [name for _line, name in sorted(wall_clock_reads(source))] == [
        "time.time",
        "time.time",
        "datetime.now",
        "date.today",
        "time.time",
        "QDate.currentDate",
    ]
