"""The preview sheet that comes before pasted or planned blocks are saved: Save is off, with a line
saying why, until something is ticked, and a pasted block off the quarter hour keeps its own time.
How readable the off button is, is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel

from desktop.native.widgets import PreviewDialog
from desktop.tests.sheets.support_dialogs import school, shown, styled
from desktop.tests.window_support import free

ROW = {
    "block": {
        "id": "b0",
        "title": "History essay",
        "kind": "flexible",
        "days": [0],
        "start": "16:00",
        "duration_min": 60,
        "category": "assignments",
    },
    "day": 0,
    "fixed": False,
    "checked": True,
}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-preview-sheet-test"])


def test_the_preview_save_is_off_with_a_line_saying_why_until_something_is_ticked(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    rows = [{**ROW, "checked": False}]
    preview = shown(qapp, PreviewDialog(parent, "Paste", "", rows, []))
    hint = preview.findChild(QLabel, "whyOff")
    assert not preview.confirm.isEnabled() and hint.isVisible()
    assert hint.text() == "Select at least one item before saving."
    preview.findChild(QCheckBox, "previewInclude0").setChecked(True)
    for _ in range(6):
        qapp.processEvents()
    assert preview.confirm.isEnabled() and not hint.isVisible()
    free(preview)
    free(parent)


def test_a_pasted_block_off_the_quarter_hour_keeps_its_time(qapp: QApplication) -> None:
    """The paste preview offers quarter hours to move to. A block copied from 17:37 showed, and would
    have saved, at 00:00, the first one offered, because 17:37 was not among them."""
    pasted = {
        "block": school(id="copy", days=[2], start="17:37", duration_min=43),
        "day": 2,
        "fixed": True,
        "checked": True,
    }
    dialog = PreviewDialog(None, "Paste", "", [pasted], [])
    start = dialog.findChild(QComboBox, "previewStart0")
    length = dialog.findChild(QComboBox, "previewDuration0")
    assert (start.currentText(), length.currentData()) == ("17:37", 43)
    assert [(row["block"]["start"], row["block"]["duration_min"]) for row in dialog.rows()] == [("17:37", 43)]
    dialog.close()
