# ruff: noqa: F811
"""Material 3 is the only style a student can reach: a look file that names the Widgets styles opens
Material, and no control, slot or signal in Material, Settings, the More menu or setup leads to them.

The Widgets screens themselves go in steps 8 and 9 of the Material-only work; until then this keeps every
way to them closed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.material.bridge import MaterialBridge
from desktop.native.material.bridge_account import AccountBridge
from desktop.native.material.host import MaterialPage
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    light_launches,  # noqa: F401
    page,
    settle,
    skip_setup,
    through_recovery,
)
from desktop.tests.window_support import look_file, qapp  # noqa: F401

MATERIAL = Path(__file__).resolve().parents[2] / "native" / "material"
# Words and names that only the way to the Widgets styles used.
WAYS_TO_WIDGETS = (
    "useWidgets",
    "widgetsRequested",
    "widgets_requested",
    "Widgets styles",
    "Back to Material",
    "chooseStyle",
    "chooseOwnLook",
    "setupOwnLook",
    "setupStylePage",
)


def test_no_material_file_names_a_way_to_the_widgets_styles() -> None:
    found = []
    for file in sorted(MATERIAL.rglob("*")):
        if file.suffix not in {".qml", ".py"}:
            continue
        text = file.read_text(encoding="utf-8")
        found += [(file.relative_to(MATERIAL).as_posix(), word) for word in WAYS_TO_WIDGETS if word in text]
    assert found == []


def test_the_static_check_can_see_a_way_to_the_widgets_styles() -> None:
    """The scan above has to be able to fail: it finds the old Look row's words in the old source."""
    old = 'Button { objectName: "useWidgets"; text: "Widgets styles"; onClicked: Ui.bridge.useWidgets() }'
    assert [word for word in WAYS_TO_WIDGETS if word in old] == ["useWidgets", "Widgets styles"]


def test_the_bridges_and_the_page_have_no_slot_or_signal_to_them() -> None:
    for owner in (MaterialBridge, AccountBridge, MaterialPage):
        for name in ("useWidgets", "widgetsRequested", "widgets_requested", "chooseStyle", "chooseOwnLook"):
            assert not hasattr(owner, name), (owner.__name__, name)


def test_the_window_has_no_way_back_from_material(qapp: QApplication) -> None:
    assert not re.search(r"backToMaterial", (MATERIAL.parent / "window.py").read_text(encoding="utf-8"))


@pytest.mark.parametrize("saved", ["widgets", "nope", None])
def test_a_start_with_an_old_surface_opens_material_and_keeps_the_other_keys(
    qapp: QApplication, light_launches: LightLaunches, saved: object
) -> None:
    body: dict[str, object] = {"material": {"mode": "dark"}}
    if saved is not None:
        body["surface"] = saved
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps(body) + "\n")
    window = light_launches.launch()
    assert window._surface == "material"
    bridge = account(window)
    create(qapp, window, "old_surface_student")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    settle(qapp, window)
    assert page(window) == "materialPage"
    assert bridge.phase == "app"
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["material"]["mode"] == "dark"
