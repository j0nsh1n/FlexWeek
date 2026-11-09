"""Bento's month is the shared month grid, not hours."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.day.support_bento import shown  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-month-test"])


def test_month_uses_the_shared_grid(qapp: QApplication) -> None:
    view = shown(qapp, "month")
    assert view.hours_surfaces() == []
    assert view.month_surfaces()
