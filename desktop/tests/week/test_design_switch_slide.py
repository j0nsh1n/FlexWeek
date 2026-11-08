"""Switching design with the Agenda rail coming or going slides the new design in as a picture. That
picture is the design as it lands, so nothing snaps into another place when the slide ends (parts
"suddenly change" as a design loads). Without the layout pass before the picture, Mission slid in 7%
different from where it landed.

The two renderings are compared with each other, not with a stored picture, so no expected colour or
position is written down here."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QStandardPaths  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.native import window as window_module  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.test_week_side import seeded  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-design-switch-test"])


def _differing_share(first: QImage, second: QImage) -> float:
    first = first.convertToFormat(QImage.Format.Format_RGB32)
    second = second.convertToFormat(QImage.Format.Format_RGB32)
    assert first.size() == second.size()
    step = 4
    seen = differ = 0
    for y in range(0, first.height(), step):
        for x in range(0, first.width(), step):
            seen += 1
            a, b = first.pixel(x, y), second.pixel(x, y)
            if max(abs(((a >> s) & 255) - ((b >> s) & 255)) for s in (0, 8, 16)) > 24:
                differ += 1
    return differ / seen


@pytest.mark.parametrize("design", ["mission", "timeline", "bento", "clay", "retro"])
def test_the_design_sliding_in_is_pictured_as_it_lands(
    qapp: QApplication,
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    design: str,
) -> None:
    seeded(qapp, window)
    window._motion = "normal"
    # As Settings applies a design: kept, then the week shown again.
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._save_look()
    window._on_week()
    wait_until(qapp, lambda: window.rail.isVisible(), what="the rail showing on Today's app")
    taken: list[tuple[QImage, object]] = []
    original = window_module.slide_view

    def slide_view(host, picture, live, level, *, back=False):
        original(host, picture, live, level, back=back)
        moving = next(
            child for child in host.findChildren(QLabel, motion.SLIDE_NAME) if child.isVisible()
        )
        taken.append((moving.pixmap().toImage(), picture.geometry()))

    monkeypatch.setattr(window_module, "slide_view", slide_view)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._save_look()
    window._on_week()
    assert taken, f"switching to {design} hid the rail without sliding"
    coming, area = taken[0]
    motion.settle(window.planner)
    wait_until(qapp, lambda: window.planner.currentWidget() is window._views[design])

    def pictures_put_away() -> bool:
        # The slide's pictures are put away with deleteLater, which processEvents alone never runs.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return not any(label.isVisible() for label in window.findChildren(QLabel, motion.SLIDE_NAME))

    wait_until(qapp, pictures_put_away, what="the slide's pictures put away")
    landed = window._week_page.grab(area).toImage()
    share = _differing_share(coming.scaled(landed.size()), landed)
    assert share < 0.02, f"{design}: {share:.1%} of the picture that slid in differs from where it landed"
