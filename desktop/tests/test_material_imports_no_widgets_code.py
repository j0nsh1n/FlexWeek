"""Material 3 imports nothing from the Qt Widgets side of the desktop app. Shared rules and wording live in
small modules of their own (sheet_rules, account_copy, setup_steps, settings_copy, hours.scale,
hours.month_cells) so the Widgets files can be deleted without breaking Material."""

from __future__ import annotations

import ast
from pathlib import Path

MATERIAL = Path(__file__).resolve().parents[1] / "native" / "material"
NATIVE = "desktop.native"

# Widgets-side modules, written as they follow `desktop.native.`. A module is forbidden as itself and
# for everything under it.
FORBIDDEN = (
    "widgets",
    "window",
    "settings",
    "setup",
    "layouts",
    "look",
    "menus",
    "motion",
    "command_bar",
    "devices",
    "hours.canvas",
    "hours.rail",
    "hours.classic",
    "hours.zoom",
    "hours.month",
    "hours.hand",
    "look_editor",
    "previews",
)

# (file under material/, module, name) imports that are still there, with the plan step that removes each.
# Exact: a new forbidden import in an allowed file fails, and so does an entry nothing imports any more.
# Step 7 removed the last ones (setup's style pick), so nothing is allowed.
ALLOWED: dict[tuple[str, str, str], str] = {}


def _forbidden(module: str) -> str | None:
    """The Widgets-side module `module` is, written after `desktop.native.`, or None."""
    if module != NATIVE and not module.startswith(NATIVE + "."):
        return None
    rest = module[len(NATIVE) + 1 :]
    for bad in FORBIDDEN:
        if rest == bad or rest.startswith(bad + "."):
            return rest
    return None


def _absolute(root: Path, file: Path, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    package = ["desktop", "native", "material", *file.relative_to(root).parent.parts]
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


def widgets_imports(root: Path = MATERIAL) -> set[tuple[str, str, str]]:
    """Every (file, module, name) under `root` that reaches Widgets code, at the top of a file or inside a
    function. `import desktop.native.widgets` and `from desktop.native import widgets` count too."""
    found: set[tuple[str, str, str]] = set()
    for file in sorted(root.rglob("*.py")):
        name = file.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"), filename=str(file))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bad = _forbidden(alias.name)
                    if bad is not None:
                        found.add((name, bad, "*"))
            elif isinstance(node, ast.ImportFrom):
                module = _absolute(root, file, node)
                bad = _forbidden(module)
                for alias in node.names:
                    if bad is not None:
                        found.add((name, bad, alias.name))
                        continue
                    inner = _forbidden(f"{module}.{alias.name}")
                    if inner is not None:
                        found.add((name, inner, "*"))
    return found


def test_material_imports_no_widgets_code_beyond_the_allowed_list() -> None:
    found = widgets_imports()
    allowed = set(ALLOWED)
    new = sorted(found - allowed)
    gone = sorted(allowed - found)
    assert not new, f"Material imports Widgets code; move it to a shared module instead: {new}"
    assert not gone, f"These allowed imports no longer exist; delete them from ALLOWED: {gone}"


def test_the_check_sees_function_level_plain_and_relative_imports(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sample.py").write_text(
        "import desktop.native.widgets\n"
        "from desktop.native import window\n"
        "from desktop.native.settings_copy import SPORT_FALLBACK\n"
        "def later():\n"
        "    from desktop.native.hours.zoom import Scale\n",
        encoding="utf-8",
    )
    (tmp_path / "sub" / "inner.py").write_text("from ...look import effective_look\n", encoding="utf-8")
    assert widgets_imports(tmp_path) == {
        ("sample.py", "widgets", "*"),
        ("sample.py", "window", "*"),
        ("sample.py", "hours.zoom", "Scale"),
        ("sub/inner.py", "look", "effective_look"),
    }
