"""An alarm has to make a noise, and asking for one must never fail. Whether a runner has an audio
device is not something to depend on, so nothing here asserts that a sound was heard: what is checked
is the answer the Bell gives and that tests ring at no volume. The waveform is test_alarm_tones."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.sound import Bell


@pytest.fixture(scope="module")
def qapp() -> Any:
    return QApplication.instance() or QApplication(["flexweek-alarm-bell-test"])


@pytest.fixture()
def bell(qapp: Any) -> Iterator[Any]:
    """A Bell freed before the test ends. Its timer's slot points back at it, so a Bell left to the
    collector sits in a cycle; the gate once failed this file's teardown on one."""
    from PySide6.QtCore import QCoreApplication, QEvent

    made = Bell()
    yield made
    made.stop()
    made.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_bell_says_whether_it_reached_the_sound_card_and_never_raises(bell: Any) -> None:
    """A runner may have an audio device or none, so the answer is not fixed. What is fixed is that
    asking never raises: an alarm that throws loses its dialog too, which is worse than a silent one."""
    assert isinstance(bell.once("chime", 80), bool)
    played = bell.start("chime", 80)
    assert bell.ringing is played
    bell.stop()
    assert bell.ringing is False
    bell.stop()


def test_tests_ring_at_no_volume(bell: Any) -> None:
    """What tests, the rig and fwtest ring came out of the speakers of whoever was at the machine."""
    assert os.environ.get("FLEXWEEK_SILENT") == "1", "conftest silences every test"
    played = bell.once("chime", 80)
    if played:
        assert bell._sink is not None and bell._sink.volume() == 0.0
    else:
        # No sound card: the test must still finish clean. A skip raised here used to leave
        # the Bell in the skip's traceback for the collector, which failed the teardown.
        assert bell._sink is None, "nothing reached a card, so nothing should be set up"
    bell.stop()


def test_a_bell_asked_for_silence_does_not_go_looking_for_a_device(bell: Any) -> None:
    assert bell.once("chime", 0) is False
