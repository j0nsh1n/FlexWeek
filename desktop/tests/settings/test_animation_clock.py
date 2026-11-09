"""The clock every animation runs on: it counts the time it is given, stands still while paused, and
only a clock that is running on a widget on screen counts as something moving."""

from __future__ import annotations

import importlib.util
import os

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QAbstractAnimation
    from PySide6.QtWidgets import QApplication, QWidget

    from desktop.native import motion
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.window_support import qapp  # noqa: F401


def test_a_clock_reads_the_time_source_and_a_paused_one_stands_still(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    host = QWidget()
    seen: list[float] = []
    clock = motion.Clock(host)
    clock.start(100, seen.append)
    manual_time.advance(30)
    assert clock.currentTime() == 30 and seen[-1] == 30.0
    clock.pause()
    manual_time.advance(500)
    assert clock.currentTime() == 30 and seen[-1] == 30.0, "time that passes while paused is not counted"
    clock.resume()
    manual_time.advance(20)
    assert clock.currentTime() == 50 and seen[-1] == 50.0
    manual_time.advance(1_000)
    assert seen[-1] == 100.0, "a late frame still ends on the end"
    assert clock.state() == QAbstractAnimation.State.Stopped
    host.close()


def test_paused_stopped_and_hidden_clocks_are_not_busy(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    owner = QWidget()
    owner.show()
    clock = motion.Clock(owner)
    clock.start(10000, lambda _: None)
    assert motion.busy()
    clock.pause()
    assert not motion.busy(), "a paused clock is not moving"
    held = clock.currentTime()
    manual_time.advance(20)
    assert clock.currentTime() == held
    clock.resume()
    assert motion.busy()
    owner.hide()
    assert not motion.busy()
    owner.show()
    assert motion.busy()
    clock.stop()
    assert not motion.busy()
    owner.close()
