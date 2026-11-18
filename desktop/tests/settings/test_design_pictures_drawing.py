"""The design pictures Setup shows: a preview is drawn once, at the width it ends at."""

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

    from desktop.native.motion import apply_ui_effects
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


@pytest.mark.parametrize("design", ["timeline", "mission", "bento", "retro", "clay", "one", "dial"])
def test_a_design_preview_renders_once_at_its_final_width(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, design: str  # noqa: F811
) -> None:
    from desktop.native import previews
    from desktop.native.layouts.views import VIEW_CLASSES

    apply_ui_effects("off")
    calls: list[int] = []
    cls = VIEW_CLASSES[design]
    render = cls.render

    def counted(self, scene, changed):  # type: ignore[no-untyped-def]
        calls.append(self.width())
        return render(self, scene, changed)

    monkeypatch.setattr(cls, "render", counted)
    previews.render(design, None, "slate", None, 206)
    assert calls == [1280], "a preview must not rebuild after a stale narrow first render"
