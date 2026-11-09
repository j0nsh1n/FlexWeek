"""Draw the screens the area test files declare, in one fixed setup, for the review page.

    .venv/bin/python scripts/pictures/render.py --list
    .venv/bin/python scripts/pictures/render.py --set full --out DIR
    .venv/bin/python scripts/pictures/render.py --set touched --screens IDS --out DIR [--root CHECKOUT]

`fwtest pictures render` runs this inside a contained job; run it by hand only for a quick look at one
area. The screens are the `SCREENS` lists in `desktop/tests/pictures/screens_*.py` (the contract is
`desktop/tests/pictures/screen.py`). Each screen is drawn in each of its variants: every style (the
Widgets designs and Material 3) at 1280x800, Normal text, light and dark; a main screen also at 1024x640
with Large text in High contrast, light. A screen's `styles` narrows that: design ids, `"material"`,
and `"widgets"` for every Widgets design of its role. A picture lands at
`DIR/<screen id>/<variant>.png`, and `DIR/index.json` lists every picture with the screen's checks and
sources and the measurements the reviewer is shown. A screen whose `prepare` raises is listed with its
error, never left out.

`--list` prints every declared screen as JSON (id, area, sources, module), which is what fwtest
selects the touched screens from. `--screens` is a file of screen ids, one per line. `--root` draws
another checkout (the pull request's base, in a worktree) with this renderer, so both sides of a
comparison are drawn the same way.

The top half plans the pictures with no Qt, so it can be checked on its own
(scripts/pictures/test_render_plan.py). The bottom half draws them.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
FULL_SIZE = (1280, 800)
EDGE_SIZE = (1024, 640)
MATERIAL = "material"
# A screen's `styles` may say "widgets" for every Widgets design of its role (and no Material 3).
WIDGETS = "widgets"
MODES = ("light", "dark")
# The Widgets packs light and dark mean; Material has its own light and dark in the look file.
PACKS = {"light": "light-frost", "dark": "dark-frost"}
SETS = ("full", "touched")
INDEX_VERSION = 1
# A screen of the My day area is drawn in the day-screen designs; every other area in the main views.
DAY_AREAS = ("myday",)
# The styles drawn for now: Material 3 only, the one being built (Jonathan, 2026-11-07). The Widgets
# designs come back by adding them here; None draws every style a screen names.
DRAWN_STYLES: tuple[str, ...] | None = (MATERIAL,)


@dataclass(frozen=True)
class Variant:
    style: str
    mode: str
    text: str
    size: tuple[int, int]
    high_contrast: bool = False

    @property
    def name(self) -> str:
        width, height = self.size
        name = f"{self.style}.{self.mode}.{self.text}.{width}x{height}"
        return name + ".hc" if self.high_contrast else name


def role_designs(area: str, designs: dict[str, str]) -> tuple[str, ...]:
    """The Widgets designs a screen of `area` is worn in: the day screens for My day, else the main
    views. `designs` maps each Widgets design to its role ("plan" or "day"), in the registry's order."""
    role = "day" if area in DAY_AREAS else "plan"
    return tuple(design for design, kind in designs.items() if kind == role)


def default_styles(area: str, designs: dict[str, str]) -> tuple[str, ...]:
    """The styles a screen is drawn in when it names none: the designs of its role, then Material 3."""
    return (*role_designs(area, designs), MATERIAL)


def plan_variants(area: str, main: bool, styles: tuple[str, ...], designs: dict[str, str]) -> list[Variant]:
    """Every picture of one screen, in drawing order. Raises ValueError for a style nobody knows."""
    unknown = [style for style in styles if style not in (MATERIAL, WIDGETS) and style not in designs]
    if unknown:
        known = ", ".join((*designs, WIDGETS, MATERIAL))
        raise ValueError(f"unknown style {', '.join(unknown)}; the styles are {known}")
    chosen: list[str] = []
    for style in styles or default_styles(area, designs):
        for one in role_designs(area, designs) if style == WIDGETS else (style,):
            if one not in chosen and (DRAWN_STYLES is None or one in DRAWN_STYLES):
                chosen.append(one)
    variants = [Variant(style, mode, "normal", FULL_SIZE) for style in chosen for mode in MODES]
    if main:
        variants += [Variant(style, "light", "large", EDGE_SIZE, True) for style in chosen]
    return variants


def look_body(
    stored: bytes | None,
    variant: Variant,
    designs: dict[str, str],
    defaults: tuple[str, str],
    scales: dict[str, float],
) -> dict:
    """The device look file a window opens in for `variant`, on top of the account's own (`stored`).
    `defaults` is the registry's (main view, day screen); `scales` the text sizes by name."""
    try:
        body = json.loads(stored) if stored else {}
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    # A recorded Material failure would keep Material from loading at all.
    body.pop("material_failed", None)
    body.pop("custom", None)
    body["preset"] = "high-contrast" if variant.high_contrast else "default"
    knobs = body.get("knobs") if isinstance(body.get("knobs"), dict) else {}
    body["knobs"] = {**knobs, "text": variant.text}
    main_default, day_default = defaults
    if variant.style == MATERIAL:
        body["surface"] = MATERIAL
        material = body.get("material") if isinstance(body.get("material"), dict) else {}
        advanced = material.get("advanced") if isinstance(material.get("advanced"), dict) else {}
        body["material"] = {
            **material,
            "mode": variant.mode,
            "contrast": "high" if variant.high_contrast else "std",
            "advanced": {**advanced, "scale": scales[variant.text]},
        }
        body["layout"] = {"main": main_default, "day": day_default, "options": {}}
    else:
        body["surface"] = "widgets"
        role = designs[variant.style]
        body["layout"] = {
            "main": variant.style if role == "plan" else main_default,
            "day": variant.style if role == "day" else day_default,
            "options": {},
        }
    return body


def read_ids(path: Path) -> list[str]:
    """Screen ids, one per line; blank lines and lines starting with # are skipped."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


# Drawing


def fixed_setup(root: Path, home: Path) -> None:
    """The setup every picture is drawn in, before Qt is imported: offscreen, silent, grey text
    (desktop/tests/conftest.py's fontconfig), and a home of its own, so Qt's test files (~/.qttest)
    are never a test run's."""
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    home.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        QT_QPA_PLATFORM="offscreen",
        FLEXWEEK_SILENT="1",
        FONTCONFIG_FILE=str(root / "desktop/tests/fontconfig.conf"),
        XDG_CACHE_HOME=cache,
        HOME=str(home),
    )
    sys.path.insert(0, str(root))


def load_screens(root: Path) -> tuple[list[tuple[str, object]], list[dict]]:
    """(module path, Screen) for every declared screen, and a problem for each module that could not
    be read or screen that is declared twice."""
    found: list[tuple[str, object]] = []
    problems: list[dict] = []
    folder = root / "desktop/tests/pictures"
    try:
        from desktop.tests.pictures.screen import Screen
    except Exception:  # noqa: BLE001 - a checkout from before the contract has no screens to draw
        if folder.joinpath("screen.py").exists():
            problems.append({"module": "desktop/tests/pictures/screen.py", "error": traceback.format_exc()})
        return found, problems
    seen: dict[str, str] = {}
    for path in sorted(folder.glob("screens_*.py")):
        module_path = path.relative_to(root).as_posix()
        try:
            module = importlib.import_module(f"desktop.tests.pictures.{path.stem}")
            listed = list(module.SCREENS)
        except Exception:  # noqa: BLE001 - reported in index.json, never skipped quietly
            problems.append({"module": module_path, "error": traceback.format_exc()})
            continue
        for screen in listed:
            if not isinstance(screen, Screen):
                problems.append({"module": module_path, "error": f"{screen!r} is not a Screen"})
                continue
            if screen.id in seen:
                problems.append(
                    {
                        "module": module_path,
                        "screen": screen.id,
                        "error": f"{screen.id} is also declared in {seen[screen.id]}",
                    }
                )
                continue
            seen[screen.id] = module_path
            found.append((module_path, screen))
    return found, problems


def listing(root: Path) -> dict:
    screens, problems = load_screens(root)
    return {
        "version": INDEX_VERSION,
        "screens": [
            {
                "id": screen.id,
                "area": screen.area,
                "sources": list(screen.sources),
                "module": module,
                "main": screen.main,
                "styles": list(screen.styles),
            }
            for module, screen in screens
        ],
        "problems": problems,
    }


def commit_of(root: Path) -> str:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20
        )
        if done.returncode == 0:
            return done.stdout.strip()
    return ""


class Pixels:
    """Read access to a QImage's pixels as hex colours, without a Python call per pixel into Qt."""

    def __init__(self, image) -> None:
        from PySide6.QtGui import QImage

        self.image = image.convertToFormat(QImage.Format.Format_RGB32)
        self.width, self.height = self.image.width(), self.image.height()
        self.stride = self.image.bytesPerLine()
        self.data = bytes(self.image.constBits())
        self.ratio = image.devicePixelRatio() or 1.0

    def colours(self, x: int, y: int, width: int, height: int) -> dict[str, int]:
        """How many pixels of each colour lie in the rectangle, in logical pixels."""
        r = self.ratio
        left, top = max(0, int(x * r)), max(0, int(y * r))
        right, bottom = min(self.width, int((x + width) * r)), min(self.height, int((y + height) * r))
        counts: dict[str, int] = {}
        for row in range(top, bottom):
            start = row * self.stride
            line = self.data[start + left * 4 : start + right * 4]
            for index in range(0, len(line), 4):
                # Format_RGB32 is 0xffRRGGBB, stored little-endian: blue first.
                key = f"#{line[index + 2]:02x}{line[index + 1]:02x}{line[index]:02x}"
                counts[key] = counts.get(key, 0) + 1
        return counts


def text_reading(pixels: Pixels, rect: tuple[int, int, int, int]) -> dict | None:
    """The colour most of the rectangle is (what the words sit on) and the one that stands out from it
    most (the words' ink), with the contrast between them. None when the rectangle is one colour."""
    from desktop.native.tokens import contrast

    counts = pixels.colours(*rect)
    if len(counts) < 2:
        return None
    behind = max(counts, key=counts.__getitem__)
    ratios = {colour: contrast(colour, behind) for colour in counts if colour != behind}
    ink = max(ratios, key=ratios.__getitem__)
    return {"ink": ink, "behind": behind, "contrast": round(ratios[ink], 2)}


def plain_words(text: str) -> str:
    import re

    return " ".join(re.sub(r"<[^>]+>", " ", text).replace("&&", "&").split())


def widget_labels(widget, pixels: Pixels) -> list[dict]:
    """Every visible label and button with words, in the picture's pixels."""
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

    rows = []
    for child in (widget, *widget.findChildren(QWidget)):
        if not isinstance(child, (QLabel, QAbstractButton)) or not child.isVisible():
            continue
        words = plain_words(child.text())
        if not words:
            continue
        shown = child.visibleRegion().boundingRect()
        if shown.isEmpty():
            continue
        corner = child.mapTo(widget, shown.topLeft()) if child is not widget else shown.topLeft()
        rect = QRect(corner, shown.size()).intersected(QRect(QPoint(0, 0), widget.size()))
        if rect.isEmpty():
            continue
        if isinstance(child, QLabel) and child.textFormat() == Qt.TextFormat.RichText:
            too_wide = None
        elif isinstance(child, QLabel) and child.wordWrap():
            too_wide = child.heightForWidth(child.width()) > child.height()
        else:
            too_wide = child.sizeHint().width() > child.width()
        row = {
            "name": child.objectName(),
            "kind": type(child).__name__,
            "text": words[:120],
            "rect": [rect.x(), rect.y(), rect.width(), rect.height()],
            "too_wide": too_wide,
        }
        row.update(text_reading(pixels, (rect.x(), rect.y(), rect.width(), rect.height())) or {})
        rows.append(row)
    return rows


def visual_items(root) -> list:
    found = [root]
    for child in root.childItems():
        found.extend(visual_items(child))
    return found


def qml_rect(item, root, quick):
    """The part of `item` its clipping parents and the QQuickWidget leave showing, in `quick`'s
    pixels, or None."""
    from PySide6.QtCore import QPointF, QRectF

    origin = item.mapToItem(root, QPointF(0, 0))
    shown = QRectF(origin.x(), origin.y(), item.width(), item.height())
    shown = shown.intersected(QRectF(0, 0, quick.width(), quick.height()))
    parent = item.parentItem()
    while parent is not None and parent is not root:
        if parent.clip():
            corner = parent.mapToItem(root, QPointF(0, 0))
            shown = shown.intersected(QRectF(corner.x(), corner.y(), parent.width(), parent.height()))
        parent = parent.parentItem()
    return None if shown.width() < 1 or shown.height() < 1 else shown


def qml_labels(widget, pixels: Pixels) -> list[dict]:
    """Every visible QML Text with words (Material 3), in the picture's pixels."""
    from PySide6.QtCore import QPoint
    from PySide6.QtQuickWidgets import QQuickWidget

    rows = []
    for quick in widget.findChildren(QQuickWidget):
        root = quick.rootObject() if quick.isVisible() else None
        if root is None:
            continue
        for item in visual_items(root):
            if not item.isVisible() or item.opacity() <= 0 or not item.inherits("QQuickText"):
                continue
            words = plain_words(str(item.property("text") or ""))
            shown = qml_rect(item, root, quick) if words else None
            if shown is None:
                continue
            corner = quick.mapTo(widget, QPoint(int(shown.x()), int(shown.y())))
            rect = (corner.x(), corner.y(), int(shown.width()), int(shown.height()))
            truncated = item.property("truncated")
            content = item.property("contentWidth")
            too_wide = (
                bool(truncated)
                if truncated is not None
                else (content is not None and float(content) > item.width() + 0.5)
            )
            row = {
                "name": str(item.objectName() or ""),
                "kind": "Text",
                "text": words[:120],
                "rect": list(rect),
                "too_wide": too_wide,
            }
            row.update(text_reading(pixels, rect) or {})
            rows.append(row)
    return rows


def differing(first: Pixels, second: Pixels, rect: tuple[int, int, int, int]) -> int:
    """Pixels in `rect` (logical) that differ between two pictures, or -1 when their sizes differ."""
    if (first.width, first.height, first.ratio) != (second.width, second.height, second.ratio):
        return -1
    x, y, width, height = rect
    r = first.ratio
    left, top = max(0, int(x * r)), max(0, int(y * r))
    right, bottom = min(first.width, int((x + width) * r)), min(first.height, int((y + height) * r))
    count = 0
    for row in range(top, bottom):
        start = row * first.stride
        one = first.data[start + left * 4 : start + right * 4]
        two = second.data[start + left * 4 : start + right * 4]
        if one != two:
            count += sum(1 for at in range(0, len(one), 4) if one[at : at + 3] != two[at : at + 3])
    return count


def focus_ring(qapp, widget, before: Pixels) -> dict:
    """Whether the focused widget draws differently with focus than without: its focus ring, or none.
    Focus is taken away for one more picture and given back with the keyboard's reason."""
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import QApplication

    focused = QApplication.focusWidget()
    if focused is None or not (focused is widget or widget.isAncestorOf(focused)):
        return {"focused": None, "ring": None}
    item = focused.quickWindow().activeFocusItem() if isinstance(focused, QQuickWidget) else None
    if item is not None and item is not focused.rootObject():
        root = focused.rootObject()
        shown = qml_rect(item, root, focused)
        if shown is None:
            return {"focused": f"qml {item.objectName() or 'item'}", "ring": None}
        corner = focused.mapTo(widget, QPoint(int(shown.x()), int(shown.y())))
        area = QRect(corner.x(), corner.y(), int(shown.width()), int(shown.height()))
        name = f"qml {item.objectName() or item.metaObject().className()}"
        item.setFocus(False)
        qapp.processEvents()
        after = Pixels(widget.grab().toImage())
        item.forceActiveFocus(Qt.FocusReason.TabFocusReason)
    else:
        corner = focused.mapTo(widget, QPoint(0, 0)) if focused is not widget else QPoint(0, 0)
        area = QRect(corner, focused.size())
        name = f"{type(focused).__name__}#{focused.objectName()}"
        focused.clearFocus()
        qapp.processEvents()
        after = Pixels(widget.grab().toImage())
        focused.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    # A ring is drawn just outside a control as often as inside it.
    area = area.adjusted(-4, -4, 4, 4).intersected(QRect(QPoint(0, 0), widget.size()))
    changed = differing(before, after, (area.x(), area.y(), area.width(), area.height()))
    return {
        "focused": name,
        "rect": [area.x(), area.y(), area.width(), area.height()],
        "ring": changed > 0,
        "changed_pixels": changed,
    }


# The files the app keeps per computer (desktop/tests/conftest.py's DEVICE_FILES).
DEVICE_FILES = ("flexweek-look.json", "week-start.json")


def clean_computer() -> None:
    """What desktop/tests/conftest.py's forget_this_computer does between tests, done between pictures:
    a screen that set the 12-hour clock, a Sunday-first week or another look in its `prepare` leaves
    none of it for the next screen. (That module is not imported: it turns the collector off.)"""
    from PySide6.QtCore import QStandardPaths

    from backend.tests.fake_clock import CLOCK
    from desktop.native.weekmodel import set_clock_24h

    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    for name in DEVICE_FILES:
        (folder / name).unlink(missing_ok=True)
    # The 12- or 24-hour clock is one setting for the whole app, held in memory.
    set_clock_24h(True)
    CLOCK.reset()


def nothing_leaves(qapp) -> None:
    """As in the tests (conftest's nothing_leaves_the_test): no screen reaches this computer's own
    apps, such as a Spotify alarm telling the Spotify app to play, or a link opening the browser."""
    from PySide6.QtGui import QDesktopServices

    from desktop.native import spotify

    spotify.system_remote = spotify.NoRemote
    QDesktopServices.openUrl = staticmethod(lambda _url: False)


def draw(qapp, made, folder: Path, screen, variant: Variant, picture: Path, setup: dict) -> dict:
    """Open a window in `variant`, let the screen prepare it, save the picture, and measure it."""
    from PySide6.QtWidgets import QWidget

    from desktop.tests.light_app import Account, _close, open_light_window
    from desktop.tests.waiting import wait_until
    from desktop.tests.window_support import still

    body = look_body(made.look, variant, setup["designs"], setup["defaults"], setup["scales"])
    account = Account(made.database, json.dumps(body).encode(), made.user_id)
    # Each picture opens on a fresh copy of the account, so preferences a screen saved are gone; what
    # the app holds in memory or in files per computer is cleared here.
    clean_computer()
    window, api = open_light_window(qapp, folder, account, variant.size)
    try:
        width, height = variant.size
        # The window's floor is larger than the edge set's size.
        if width < window.minimumWidth() or height < window.minimumHeight():
            window.setMinimumSize(min(width, window.minimumWidth()), min(height, window.minimumHeight()))
            window.resize(width, height)
        session = window.session

        def quiet() -> bool:
            return not session.busy and not getattr(session.client, "pending", 0)

        # Motion off, so nothing is caught halfway through a fade or a slide.
        session.save_preferences({"theme_pack": PACKS[variant.mode], "motion": "off"})
        wait_until(qapp, quiet, what="the variant's preferences saving")
        window._apply_appearance()
        target = screen.prepare(window)
        wait_until(qapp, quiet, what="the screen's own requests")
        still(window)
        qapp.processEvents()
        shot = target if isinstance(target, QWidget) else window
        image = shot.grab().toImage()
        picture.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(picture), "PNG"):
            raise OSError(f"could not write {picture}")
        pixels = Pixels(image)
        labels = widget_labels(shot, pixels) + qml_labels(shot, pixels)
        return {"labels": labels, "focus": focus_ring(qapp, shot, pixels)}
    finally:
        _close(window)
        api.close()
        clean_computer()


def render(root: Path, out: Path, chosen: list[str] | None, which: str) -> int:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication

    from backend import clock as app_clock
    from backend.tests.fake_clock import CLOCK

    app_clock.use(CLOCK)
    CLOCK.reset()
    QStandardPaths.setTestModeEnabled(True)
    qapp = QApplication.instance() or QApplication(["flexweek-pictures"])
    nothing_leaves(qapp)

    from desktop.native.layouts.registry import DAY_DEFAULT, LAYOUTS, MAIN_DEFAULT
    from desktop.native.tokens import TEXT_SCALE
    from desktop.tests.light_app import account

    setup = {
        "designs": {spec.id: spec.role for spec in LAYOUTS.values()},
        "defaults": (MAIN_DEFAULT, DAY_DEFAULT),
        "scales": dict(TEXT_SCALE),
    }
    screens, problems = load_screens(root)
    declared = {screen.id for _, screen in screens}
    for missing in sorted(set(chosen or ()) - declared):
        problems.append({"screen": missing, "error": f"{missing} was chosen but no screens file declares it"})
    work = out / ".work"
    index: dict = {
        "version": INDEX_VERSION,
        "set": which,
        "root": str(root),
        "commit": commit_of(root),
        "problems": problems,
        "pictures": [],
    }
    made = account(qapp, work / "account")
    failed = bool(problems)
    count = 0
    for module, screen in screens:
        if chosen is not None and screen.id not in chosen:
            continue
        entry_base = {
            "screen": screen.id,
            "area": screen.area,
            "module": module,
            "main": screen.main,
            "checks": screen.checks,
            "sources": list(screen.sources),
        }
        try:
            variants = plan_variants(screen.area, screen.main, tuple(screen.styles), setup["designs"])
        except ValueError as wrong:
            index["pictures"].append({**entry_base, "variant": "", "error": str(wrong)})
            failed = True
            continue
        if not variants:
            index["pictures"].append(
                {**entry_base, "variant": "", "error": None, "not_drawn": "its styles are not drawn yet"}
            )
            continue
        for variant in variants:
            relative = f"{screen.id}/{variant.name}.png"
            entry = {
                **entry_base,
                "variant": variant.name,
                "style": variant.style,
                "mode": variant.mode,
                "text": variant.text,
                "size": list(variant.size),
                "high_contrast": variant.high_contrast,
                "picture": None,
                "measurements": None,
                "error": None,
            }
            try:
                entry["measurements"] = draw(
                    qapp, made, work / f"window-{count}", screen, variant, out / relative, setup
                )
                entry["picture"] = relative
            except Exception:  # noqa: BLE001 - the error goes on the page; the next picture is drawn
                entry["error"] = traceback.format_exc()
                failed = True
            count += 1
            index["pictures"].append(entry)
            # Kept up to date after every picture, so a run stopped part way still says what it drew.
            (out / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
            print(f"{relative}: {'failed' if entry['error'] else 'drawn'}", flush=True)
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    drawn = sum(1 for entry in index["pictures"] if entry.get("picture"))
    print(f"{drawn} pictures drawn, {len(index['pictures']) - drawn} failed, in {out}", flush=True)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="print the declared screens as JSON")
    parser.add_argument("--set", choices=SETS, dest="which")
    parser.add_argument("--screens", type=Path, help="file of screen ids, one per line (for --set touched)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="the checkout to draw")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.list:
        home = Path.home() / ".flexweek-ui-harness" / "scratch" / "pictures" / "list-home"
        fixed_setup(root, home)
        print(json.dumps(listing(root), indent=1))
        return 0
    if args.which is None or args.out is None:
        parser.error("give --list, or --set and --out")
    if args.which == "touched" and args.screens is None:
        parser.error("--set touched needs --screens (fwtest pictures render picks them)")
    chosen = read_ids(args.screens) if args.which == "touched" else None
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    fixed_setup(root, out / ".work" / "home")
    return render(root, out, chosen, args.which)


if __name__ == "__main__":
    raise SystemExit(main())
