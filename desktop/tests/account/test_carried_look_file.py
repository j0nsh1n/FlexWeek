"""The file that carries a look to the screens shown before sign-in: it holds only the text size, whether
High contrast was on, and the account that owned it, and a damaged file reads as no look."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from desktop.native.kept import KeptSession


def test_the_device_file_holds_only_the_text_size_the_contrast_and_the_owner(tmp_path: Path) -> None:
    kept = KeptSession(tmp_path / "signed-in" / "flexweek.json")
    assert kept.carried_look() is None
    kept.carry_look("acct-1", "large", True)
    assert kept.carried_look() == ("large", True)
    assert json.loads(kept.look.read_text()) == {"account": "acct-1", "text": "large", "contrast": True}
    assert stat.S_IMODE(kept.look.stat().st_mode) == 0o600
    assert kept.look.parent == kept.path.parent


@pytest.mark.parametrize(
    "body",
    ["", "not json", "[]", '{"text": "huge", "contrast": true}', '{"text": "large", "contrast": "yes"}'],
)
def test_a_damaged_device_file_reads_as_no_look(tmp_path: Path, body: str) -> None:
    kept = KeptSession(tmp_path / "flexweek.json")
    kept.look.write_text(body)
    assert kept.carried_look() is None


def test_forgetting_a_look_clears_it_only_for_its_own_account(tmp_path: Path) -> None:
    kept = KeptSession(tmp_path / "flexweek.json")
    kept.carry_look("acct-1", "large", True)
    kept.forget_look("acct-2")
    assert kept.carried_look() == ("large", True)
    kept.forget_look("acct-1")
    assert kept.carried_look() is None
