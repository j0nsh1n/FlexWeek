"""The dim behind a sheet starts at the click, and the sheet is built behind it. How dark the dim is,
is a look: pictures/_sheets_g13.py.

Order is counted, never timed: a constructor that records what is on screen when it runs sees whether
the dim was already there.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import window as window_module
from desktop.native.motion import apply_ui_effects, busy
from desktop.native.widgets import Dialog, HomeworkDialog, SheetShade, dim_window
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sheet-dim-test"])


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    yield
    apply_ui_effects("normal")


def shades(host: QWidget) -> list[SheetShade]:
    """The dims over `host`, found without findChildren, which would hand a sheet to the window."""
    return [child for child in host.children() if isinstance(child, SheetShade)]


def drained(qapp: QApplication) -> None:
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def watch_the_build(
    monkeypatch: pytest.MonkeyPatch,
    window: NativeWindow,  # noqa: F811
    seen: list[dict],
) -> None:
    """HomeworkDialog records the dim as it is when its constructor starts, then builds as usual. exec
    is left out so the test decides what the sheet does next."""

    class Recorded(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            on_screen = [shade for shade in shades(window) if shade.isVisible()]
            seen.append(
                {
                    "dims": len(on_screen),
                    "covers": bool(on_screen) and on_screen[0].geometry() == window.rect(),
                    "opacity": None,
                    "progress": on_screen[0].dim_progress if on_screen else 0.0,
                    "fading": on_screen[0].fading if on_screen else False,
                }
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(window_module, "HomeworkDialog", Recorded)








def test_the_dim_finishes_on_a_plain_host(qapp: QApplication) -> None:
    apply_ui_effects("normal")
    host = QWidget()
    host.resize(1280, 800)
    host.show()
    qapp.processEvents()
    dim = dim_window(host)
    # The dim waits for its sheet; the sheet that takes it lets the fade go on.
    sheet = Dialog(host, sheet=True)
    sheet.card_body("A sheet")
    sheet.show()
    wait_until(qapp, lambda: not busy())
    assert not dim.fading
    assert dim.dim_progress == 1.0
    assert dim.has_still
    assert dim.geometry() == host.rect()
    sheet.close()
    free(sheet)
    free(host)




















