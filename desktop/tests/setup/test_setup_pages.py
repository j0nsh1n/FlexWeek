# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
"""Setup's rules on their own: a typed sport name is sports."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup_steps import activity_category_for
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_typed_sport_name_is_sports(qapp: QApplication) -> None:
    assert activity_category_for("Soccer") == "exercise"
    assert activity_category_for("swim practice") == "exercise"
    assert activity_category_for("Piano practice") == "extra"
    assert activity_category_for("Band practice") == "extra"
    assert activity_category_for("Band") == "extra"
