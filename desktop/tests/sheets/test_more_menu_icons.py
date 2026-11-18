"""More's rows each have their own icon, and every icon a row names can be drawn."""

from __future__ import annotations

import re
from pathlib import Path

from desktop.native.material.bridge_sheets import MORE_ROWS

SHEETS = Path(__file__).resolve().parents[2] / "native/material/qml/sheets"


def test_no_two_more_rows_share_an_icon() -> None:
    icons = [row[2] for row in MORE_ROWS if len(row) == 3]
    assert len(icons) == len(set(icons)), [i for i in icons if icons.count(i) > 1]


def test_every_more_icon_is_a_file_the_sheet_icon_can_find() -> None:
    listed = re.search(r"own: \[(.*?)\]", (SHEETS / "SIcon.qml").read_text(), re.S)
    assert listed is not None
    own = set(re.findall(r'"(\w+)"', listed.group(1)))
    shared = {path.stem for path in (SHEETS.parent / "icons").glob("*.svg")}
    for row in MORE_ROWS:
        if len(row) == 3:
            name = row[2]
            assert name in own and (SHEETS / "icons" / f"{name}.svg").exists() or name in shared, name
