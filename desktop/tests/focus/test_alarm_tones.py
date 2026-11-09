"""The alarm waveform, checked as numbers. No Qt and no sound card, so this runs anywhere."""

from __future__ import annotations

import struct

import pytest

from desktop.native.tones import FALLBACK, GAP_SEC, NOTE_SEC, RATE, RECIPES, SOUNDS, gain_for, pcm


def samples(data: bytes) -> tuple[int, ...]:
    return struct.unpack(f"<{len(data) // 2}h", data)


def test_the_five_named_tones_are_the_ones_the_web_plays() -> None:
    assert RECIPES == {
        "chime": (660, 880),
        "soft": (440,),
        "bright": (880, 1175),
        "low": (220, 330),
        "glass": (1047, 1568),
    }
    assert SOUNDS == ("chime", "soft", "bright", "low", "glass", "spotify")


@pytest.mark.parametrize("tone", SOUNDS)
def test_every_sound_a_student_can_pick_produces_audio(tone: str) -> None:
    assert samples(pcm(tone, 80)), tone


def test_spotify_is_not_a_tone_so_it_falls_back_to_one() -> None:
    assert pcm("spotify", 80) == pcm(FALLBACK, 80)
    assert pcm("nonsense-from-an-old-file", 80) == pcm(FALLBACK, 80)


def test_silence_at_zero_volume_so_nothing_has_to_guard_the_call() -> None:
    assert pcm("chime", 0) == b""


def test_volume_scales_the_signal() -> None:
    loud = max(abs(value) for value in samples(pcm("chime", 100)))
    quiet = max(abs(value) for value in samples(pcm("chime", 25)))
    assert quiet < loud
    assert quiet == pytest.approx(loud * 0.25, rel=0.05)


def test_volume_outside_the_slider_cannot_blow_the_signal_up() -> None:
    assert pcm("chime", 500) == pcm("chime", 100)
    assert pcm("chime", -20) == b""


def test_soft_is_the_quiet_one_as_it_is_on_the_web() -> None:
    assert gain_for("soft") < gain_for("chime")
    assert gain_for("glass") == gain_for("chime")


def test_a_note_starts_and_ends_at_rest_so_the_speaker_does_not_click() -> None:
    """A wave cut off mid-cycle is a step in the signal, which is heard as a click."""
    for tone in RECIPES:
        wave = samples(pcm(tone, 100))
        peak = max(abs(value) for value in wave)
        assert abs(wave[0]) < peak // 20, tone
        assert abs(wave[-1]) < peak // 20, tone


def test_two_note_tones_last_longer_than_one_note_tones() -> None:
    """The notes are staggered, so a second note buys GAP_SEC of extra sound."""
    one = len(pcm("soft", 80)) // 2
    two = len(pcm("chime", 80)) // 2
    assert one == pytest.approx(NOTE_SEC * RATE, abs=2)
    assert two == pytest.approx((NOTE_SEC + GAP_SEC) * RATE, abs=2)


def test_the_second_note_really_sounds_rather_than_replacing_the_first() -> None:
    """The notes overlap, so the buffer has to be summed. Writing into it instead would leave the
    overlap no louder than one note sounding alone: the arpeggio becomes a single beep."""
    wave = samples(pcm("chime", 100))
    gap, note = round(GAP_SEC * RATE), round(NOTE_SEC * RATE)
    together = max(abs(value) for value in wave[gap:note])
    alone = max(abs(value) for value in wave[note + 200 :])
    assert together > alone * 1.3
