"""The rail's Next card takes no room when nothing is on now or later today."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.rail import NextCard


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-next-card-empty"])


def test_a_next_card_with_nothing_to_say_hides_its_card(qapp: QApplication) -> None:
    card = NextCard()
    assert card.show_next(None, None, None) is False
    assert card.card.isHidden(), "nothing now or next today, so the card takes no room"
    card.deleteLater()
