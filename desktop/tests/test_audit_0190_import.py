"""Audit finding 10: a file that is not a FlexWeek export is refused in words, whatever is in its header."""

from __future__ import annotations

import importlib.util
import json

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QLabel

    from desktop.native.files import parse_import_payload
    from desktop.native.settings import TransferPreviewDialog
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize("format_", [[], {}, 5, None, True])
def test_a_header_whose_format_is_not_text_is_refused_with_a_complaint(format_: object) -> None:
    raw = json.dumps({"format": format_, "version": 2, "blocks": [], "assignments": []})
    result = parse_import_payload(raw)
    assert result["error"] == (
        "Nothing imported: this isn't a FlexWeek week or day file, or it's damaged. "
        "Export it again from FlexWeek."
    )


def test_a_file_nested_too_deep_to_read_is_refused_not_raised() -> None:
    depth = 100_000
    result = parse_import_payload("[" * depth + "]" * depth)
    assert isinstance(result["error"], str) and result["error"]


def test_the_import_preview_says_whose_weeks_it_deletes(qapp) -> None:
    """T-W13: "1 week removed" did not say these are the account's own weeks, deleted because the backup
    lacks them. The sentence is the audit's, word for word."""
    preview = {
        "source_username": "joo2",
        "changes": {
            "weeks": {
                "added": ["2026-10-05"],
                "changed": ["2026-10-12", "2026-10-19"],
                "removed": ["2026-10-26"],
            },
            "assignments": {"added": [], "changed": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "removed": []},
            "preferences_changed": True,
        },
    }
    dialog = TransferPreviewDialog(None, preview)
    words = [label.text() for label in dialog.findChildren(QLabel)]
    assert words[0] == (
        "From joo2's backup: adds 1 week, replaces 2 of your weeks, and deletes 1 of your weeks that isn't "
        "in the backup. 3 homework change. Your settings will be replaced."
    )
    dialog.close()


def test_several_deleted_weeks_say_they_are_not_in_the_backup(qapp) -> None:
    preview = {
        "source_username": "joo2",
        "changes": {"weeks": {"removed": ["a", "b"]}, "assignments": {"removed": [{"id": "x"}]}},
    }
    dialog = TransferPreviewDialog(None, preview)
    words = [label.text() for label in dialog.findChildren(QLabel)]
    assert words[0] == (
        "From joo2's backup: deletes 2 of your weeks that aren't in the backup. "
        "It also deletes 1 of your homework that isn't in the backup."
    )
    dialog.close()
