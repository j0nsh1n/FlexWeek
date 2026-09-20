"""The alarm tones, as numbers. No Qt, no sound card, so the waveform can be checked without either.

The web client synthesises its alerts with a WebAudio oscillator. There is no oscillator here, so the
same five recipes are written out as 16-bit mono PCM and handed to an audio sink. The recipes, the
gains and the timing are kept in step with soundOnce in frontend/app.js: a student who sets "glass" on
their phone and hears it on the laptop is hearing the same two notes.
"""

from __future__ import annotations

import struct
from math import asin, pi, sin

RATE = 44_100
NOTE_SEC = 0.22
GAP_SEC = 0.14
FADE_SEC = 0.008
REPEAT_MS = 2_500

# Kept in step with the recipes in soundOnce (frontend/app.js).
RECIPES: dict[str, tuple[int, ...]] = {
    "chime": (660, 880),
    "soft": (440,),
    "bright": (880, 1175),
    "low": (220, 330),
    "glass": (1047, 1568),
}
# "spotify" is not a tone. It means play the linked track, and fall back to this when that fails.
FALLBACK = "chime"
SOUNDS = (*RECIPES, "spotify")


def gain_for(tone: str) -> float:
    return 0.025 if tone == "soft" else 0.04


def _shape(tone: str, phase: float) -> float:
    """Sine for soft, triangle for the rest, as the web picks its oscillator type."""
    wave = sin(phase)
    return wave if tone == "soft" else (2.0 / pi) * asin(wave)


def _level(volume: float) -> float:
    return max(0.0, min(100.0, float(volume or 0))) / 100.0


def frames(volume: float = 80) -> int:
    """How many samples one alert occupies, counting the stagger between notes."""
    return 0 if _level(volume) == 0 else round((GAP_SEC + NOTE_SEC) * RATE)


def pcm(tone: str, volume: float = 80, rate: int = RATE) -> bytes:
    """One alert as signed 16-bit mono PCM. Silence at volume zero, so nothing has to guard the call.

    Notes are staggered rather than played together, and they overlap, so the buffer is summed and not
    concatenated. Each note fades in and out over FADE_SEC: cutting a wave off mid-cycle puts a step in
    the signal, which a speaker reproduces as a click.
    """
    level = _level(volume)
    notes = RECIPES.get(tone) or RECIPES[FALLBACK]
    if level == 0 or not rate:
        return b""
    gain = gain_for(tone) * level
    length = round((GAP_SEC * (len(notes) - 1) + NOTE_SEC) * rate)
    mix = [0.0] * length
    note_len = round(NOTE_SEC * rate)
    fade = max(1, round(FADE_SEC * rate))
    for index, frequency in enumerate(notes):
        offset = round(index * GAP_SEC * rate)
        step = 2.0 * pi * frequency / rate
        for sample in range(note_len):
            envelope = min(1.0, sample / fade, (note_len - sample) / fade)
            mix[offset + sample] += _shape(tone, step * sample) * gain * envelope
    peak = 32767
    return struct.pack(f"<{length}h", *(max(-peak, min(peak, round(value * peak))) for value in mix))
