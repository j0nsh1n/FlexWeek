"""How the Style page's cards slide and fade when the middle changes: where they end, which way they
leave, and that a later move is not undone by an earlier one's fade."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget

from desktop.native import motion
from desktop.native.setup import SetupPage
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

ORDER = ["plain", "night", "dashboard", "retro"]
# Longer than a slide (EASE_MS + 60) and than a fade (EASE_MS) at the Normal pace.
SLIDE_MS = 450


@pytest.fixture()
def moving(qapp: QApplication, window: NativeWindow) -> SetupPage:
    return show_setup(qapp, window, motion="normal")


def middle(setup: SetupPage) -> str:
    return setup.carousel.key()


def opacity(slide: QWidget) -> float:
    effect = slide.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    return effect.opacity()


def middle_slot(setup: SetupPage) -> tuple[int, int]:
    stage, front = setup.carousel.stage, setup.style_cards[middle(setup)]
    return front.width() // 4, stage.width() - front.width() // 4


@pytest.mark.parametrize("delta", [1, -1])
def test_a_step_slides_to_the_same_places_a_jump_puts_them(
    moving: SetupPage,
    manual_time: ManualTime,
    delta: int,
) -> None:
    """Sliding, including the card that wraps from one end to the other, ends where setting it at once
    does, and the neighbours are dimmed and the middle is bright when it stops."""
    setup = moving
    for _ in range(6):
        setup.carousel.step(delta)
        manual_time.advance(SLIDE_MS)
        seen = {key: slide.geometry() for key, slide in setup.style_cards.items()}
        setup.carousel._arrange(delta=0)
        for key, slide in setup.style_cards.items():
            if slide.x() + slide.width() > 0 and slide.x() < setup.carousel.stage.width():
                assert slide.geometry() == seen[key], key
            assert (opacity(slide) == 1.0) == (key == middle(setup)), key


@pytest.mark.parametrize("delta", [1, -1])
def test_no_card_crosses_the_middle_while_the_others_slide(
    moving: SetupPage,
    manual_time: ManualTime,
    delta: int,
) -> None:
    """A card wrapping from one end to the other leaves by the edge it was heading for, and a card that
    has just done so does not come back across the stage on the next step."""
    setup = moving
    for _ in range(6):
        before = middle(setup)
        setup.carousel.step(delta)
        after = middle(setup)
        low, high = middle_slot(setup)
        for _frame in range(40):
            manual_time.advance(10)
            for key, slide in setup.style_cards.items():
                if key not in (before, after):
                    centre = slide.x() + slide.width() // 2
                    assert not low < centre < high, (key, slide.geometry())
        manual_time.advance(SLIDE_MS)


def test_a_jump_during_a_step_leaves_only_the_middle_bright(
    moving: SetupPage,
    manual_time: ManualTime,
) -> None:
    """A step fades its cards over EASE_MS; a jump to a card two away before that ends sets them at
    once. The step's fade must not finish afterwards and write its own end over the jump's."""
    setup = moving
    setup.carousel.step(1)
    manual_time.advance(20)
    setup.carousel.go_to(ORDER[3])
    manual_time.advance(SLIDE_MS)
    for key, slide in setup.style_cards.items():
        assert (opacity(slide) == 1.0) == (key == middle(setup)), (key, opacity(slide))


def test_the_neighbour_fades_through_its_midpoint_to_the_dimmed_end(moving: SetupPage) -> None:
    setup = moving
    before = middle(setup)
    setup.carousel.step(1)
    slide = setup.style_cards[before]
    slide.fading.pause()
    slide.fading.setCurrentTime(slide.fading.duration() // 2)
    assert 0.45 < opacity(slide) < 1.0
    slide.fading.setCurrentTime(slide.fading.duration())
    assert opacity(slide) == pytest.approx(0.45)


def test_the_look_pictures_wait_for_a_fade_and_draw_after(
    qapp: QApplication,
    moving: SetupPage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = moving
    # Whatever the window was still fading when it opened must end first: only this clock is to be busy.
    wait_until(qapp, lambda: not motion.busy())
    setup._warm.stop()
    card = next(iter(setup.look_cards.values()))
    setup._pending_pictures = [(card, "retro", None, "slate", 206)]
    calls = []
    monkeypatch.setattr(setup._previews, "get", lambda *_: calls.append(1) or QPixmap(4, 4))
    owner = QWidget(setup)
    owner.show()
    clock = motion.Clock(owner)
    clock.start(10000, lambda _: None)
    setup._draw_next_picture()
    assert calls == []
    clock.setCurrentTime(10000)
    setup._draw_next_picture()
    assert calls == [1]
    owner.deleteLater()
