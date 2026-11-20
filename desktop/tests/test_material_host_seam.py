"""Tests and rigs reach Material's host only through the helpers in material_support.py, so step 11 (the
Material window moving out of the widget host) changes those helpers and not every test file."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = (ROOT / "desktop" / "tests", ROOT / "scripts" / "pictures", ROOT / "scripts" / "rig")
ALLOWED = {
    ROOT / "desktop" / "tests" / "material_support.py",
    Path(__file__).resolve(),
}
HOST_USES = (
    "_material_page._quick",
    "._quick",
    '"_quick"',
    "'_quick'",
    "grabFramebuffer",
    "_stack.currentWidget",
    "quickWindow()",
    "quick.setFocus()",
    ").setFocus()",
    "focusWidget() is quick",
)
# Uses that only make sense for the widget host, kept until the step named here replaces them.
KNOWN = {
    ROOT / "scripts" / "pictures" / "render.py": {"quickWindow()"},
}


def test_only_the_helpers_name_the_material_host() -> None:
    files = [path for folder in SCANNED for path in folder.rglob("*.py") if path not in ALLOWED]
    assert files, "the scan found no files, so the guard checks nothing"
    found = [
        f"{path.relative_to(ROOT)}: {use}"
        for path in sorted(files)
        for use in HOST_USES
        if use in path.read_text(encoding="utf-8") and use not in KNOWN.get(path, set())
    ]
    assert found == [], "reach the host through the helpers in desktop/tests/material_support.py"
