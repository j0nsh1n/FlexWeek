"""Play: run the steps an agent wrote on the rig's hidden desktop, and record what the screen showed.

    fwtest rig --play PLAY.json [--out DIR]

The format and an example are in docs/tooling/fwtest.md, "Playing the app". This file has two halves.
The top parses and checks a play file with no display and no Qt, so a mistake is named before the
hidden session does any work. The bottom (run_play) runs it with the real pointer, as drive.py's
scenarios do, and never touches anything but the rig's throwaway account and local server.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ACTIONS = (
    "click",
    "double_click",
    "right_click",
    "drag",
    "type",
    "key",
    "wait",
    "advance_clock",
    "shot",
    "tree",
    "say",
)
SETUP_KEYS = ("clock", "seed", "size", "design", "clock_24h", "text", "look")
SEEDS = ("rig", "empty", "setup-done")
TEXT_SIZES = ("normal", "large")
KEY_NAME = re.compile(r"[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*")
LABEL = re.compile(r"[A-Za-z0-9_.-]+")
MAX_WAIT_MS = 60_000
MAX_ADVANCE_MIN = 7 * 24 * 60
DEFAULT_SIZE = (1280, 800)


class PlayError(ValueError):
    """The play file is wrong; the message names every mistake, one per line."""


@dataclass(frozen=True)
class Setup:
    clock: datetime | None = None
    seed: str = "rig"
    size: tuple[int, int] = DEFAULT_SIZE
    design: str = "classic"
    clock_24h: bool = False
    text: str = "normal"
    look: str | None = None


@dataclass(frozen=True)
class Step:
    action: str
    value: object


@dataclass(frozen=True)
class Play:
    name: str
    setup: Setup
    steps: tuple[Step, ...]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_target(raw: object) -> tuple[str, object]:
    """('name', objectName), ('point', (x, y)) or ('text', words). Raises ValueError saying what is wrong."""
    if isinstance(raw, str):
        if not raw.strip():
            raise ValueError("an empty objectName")
        return "name", raw
    if isinstance(raw, list):
        if len(raw) != 2 or not all(_is_int(n) and n >= 0 for n in raw):
            raise ValueError(f"a point is [x, y] in window pixels, two whole numbers from 0; got {raw!r}")
        return "point", (raw[0], raw[1])
    if isinstance(raw, dict):
        if set(raw) != {"text"} or not isinstance(raw["text"], str) or not raw["text"].strip():
            raise ValueError(f'a text target is {{"text": "Button words"}}; got {raw!r}')
        return "text", raw["text"]
    raise ValueError(f'a target is an objectName, [x, y] or {{"text": "words"}}; got {raw!r}')


def _parse_clock(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise ValueError('"clock" is local time like "2026-10-15T17:00"')
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f'"clock" is local time like "2026-10-15T17:00"; got {raw!r}') from None


def _parse_setup(raw: object, designs: tuple[str, ...], looks: tuple[str, ...], errors: list[str]) -> Setup:
    if raw is None:
        return Setup()
    if not isinstance(raw, dict):
        errors.append('"setup" must be an object')
        return Setup()
    values: dict[str, object] = {}
    for key, value in raw.items():
        try:
            values[key] = _setup_value(key, value, designs, looks)
        except ValueError as wrong:
            errors.append(f"setup {key}: {wrong}")
    return Setup(**values)  # type: ignore[arg-type]


def _setup_value(key: str, value: object, designs: tuple[str, ...], looks: tuple[str, ...]) -> object:
    if key == "clock":
        return _parse_clock(value)
    if key == "seed":
        return _one_of(value, SEEDS, key)
    if key == "design":
        return _one_of(value, designs, key)
    if key == "text":
        return _one_of(value, TEXT_SIZES, key)
    if key == "look":
        return _one_of(value, looks, key)
    if key == "clock_24h":
        if not isinstance(value, bool):
            raise ValueError("true or false")
        return value
    if key == "size":
        if not (isinstance(value, list) and len(value) == 2 and all(_is_int(n) for n in value)):
            raise ValueError("[width, height] in pixels")
        if not (640 <= value[0] <= 3840 and 480 <= value[1] <= 2160):
            raise ValueError("between 640x480 and 3840x2160")
        return (value[0], value[1])
    raise ValueError(f"is not a setup key. Setup keys: {', '.join(SETUP_KEYS)}")


def _one_of(value: object, valid: tuple[str, ...], key: str) -> str:
    if value not in valid:
        raise ValueError(f"{value!r} is not valid for {key}. Valid: {', '.join(valid)}")
    return str(value)


def _parse_step(raw: object) -> Step:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise ValueError(f"a step is an object with one action ({', '.join(ACTIONS)}); got {raw!r}")
    ((action, value),) = raw.items()
    if action in ("click", "double_click", "right_click"):
        return Step(action, parse_target(value))
    if action == "drag":
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("drag is [from, to], each a target")
        # A point is also a list, so [from, to] with two numbers is a mistake worth naming.
        if all(_is_int(n) for n in value):
            raise ValueError("drag is [from, to] where each is a target; write [[x1, y1], [x2, y2]]")
        return Step(action, (parse_target(value[0]), parse_target(value[1])))
    if action == "type":
        if not isinstance(value, str) or not value:
            raise ValueError("type needs the words to type")
        return Step(action, value)
    if action == "key":
        if not isinstance(value, str) or not KEY_NAME.fullmatch(value):
            raise ValueError(f'key is a name like "Tab", "shift+Tab" or "ctrl+z"; got {value!r}')
        return Step(action, value)
    if action == "wait":
        if not _is_int(value) or not 0 <= value <= MAX_WAIT_MS:
            raise ValueError(f"wait is milliseconds, 0 to {MAX_WAIT_MS}; got {value!r}")
        return Step(action, value)
    if action == "advance_clock":
        if not _is_int(value) or not 1 <= value <= MAX_ADVANCE_MIN:
            raise ValueError(f"advance_clock is whole minutes, 1 to {MAX_ADVANCE_MIN}; got {value!r}")
        return Step(action, value)
    if action in ("shot", "tree"):
        if not isinstance(value, str) or not LABEL.fullmatch(value):
            raise ValueError(f"{action} needs a label of letters, digits, '.', '_' or '-'; got {value!r}")
        return Step(action, value)
    if action == "say":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("say needs a note")
        return Step(action, value)
    raise ValueError(f"{action!r} is not an action. Actions: {', '.join(ACTIONS)}")


def parse_play(raw: object, name: str, designs: tuple[str, ...], looks: tuple[str, ...]) -> Play:
    """The play, or a PlayError naming every mistake. `designs` and `looks` are the names the app knows."""
    errors: list[str] = []
    if not isinstance(raw, dict):
        raise PlayError('A play file is a JSON object with "setup" and "steps".')
    for key in raw:
        if key not in ("setup", "steps"):
            errors.append(f'{key!r} is not a play key. A play has "setup" and "steps".')
    setup = _parse_setup(raw.get("setup"), designs, looks, errors)
    steps: list[Step] = []
    listed = raw.get("steps")
    if not isinstance(listed, list):
        errors.append('"steps" must be a list')
        listed = []
    for number, item in enumerate(listed, 1):
        try:
            steps.append(_parse_step(item))
        except ValueError as wrong:
            errors.append(f"step {number}: {wrong}")
    if errors:
        raise PlayError("\n".join(errors))
    return Play(name, setup, tuple(steps))


def load_play(path: Path, designs: tuple[str, ...], looks: tuple[str, ...]) -> Play:
    try:
        raw = json.loads(path.read_text())
    except OSError as unreadable:
        raise PlayError(f"Cannot read {path}: {unreadable.strerror}") from None
    except ValueError as broken:
        raise PlayError(f"{path} is not valid JSON: {broken}") from None
    return parse_play(raw, path.stem, designs, looks)


def default_play_folder(name: str, now: datetime) -> Path:
    # On disk, not /tmp, which is RAM on Jonathan's machine (see drive.default_runs_folder).
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", name) or "play"
    return Path.home() / ".flexweek-ui-harness" / "scratch" / "plays" / f"{now:%Y%m%d-%H%M%S}-{safe}"


def normal_words(words: str) -> str:
    """Words as a student reads them: no mnemonic '&', no markup, no trailing ellipsis, any case."""
    plain = re.sub(r"<[^>]+>", "", words).replace("&", "")
    return " ".join(plain.split()).rstrip("…").rstrip(".").strip().casefold()


def matches_words(wanted: str, shown: str) -> int:
    """0 no match, 1 the words contain the wanted ones, 2 the same words."""
    want, have = normal_words(wanted), normal_words(shown)
    if not want or not have:
        return 0
    if want == have:
        return 2
    return 1 if want in have else 0


class CannotDo(Exception):
    """The step cannot be done now (no such widget, a dialog in the way). Logged, and the play goes on."""


def run_play(app, window, session, server, out: Path, play: Play, seed_week, python_errors: list[str]) -> int:
    """Set the account up as the play asks, run its steps, then take a final shot and tree. Exit code."""
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtGui import QAction, QCursor
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractSpinBox,
        QApplication,
        QComboBox,
        QLabel,
        QLineEdit,
        QMenu,
        QPlainTextEdit,
        QTextEdit,
        QWidget,
    )

    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import LOOK_PRESETS, sanitize_look
    from desktop.tests.logic_support import past_setup, wait_until

    out.mkdir(parents=True, exist_ok=True)
    log_file = (out / "log.txt").open("w", buffering=1)

    def log(line: str) -> None:
        log_file.write(line + "\n")
        print(line, flush=True)

    def xdo(*parts: object) -> None:
        subprocess.run(["xdotool", *map(str, parts)], check=True, timeout=15)

    held = {"now": datetime.now()}
    session.now_ms = lambda: int(held["now"].timestamp() * 1000)
    setup = play.setup

    # Setup

    def prepare() -> None:
        window.resize(*setup.size)
        window.move(0, 0)
        if setup.seed == "empty":
            wait_until(app, lambda: window._stack.currentWidget().objectName() == "setupPage", 20)
        else:
            past_setup(app, window)
        monday = datetime.fromisoformat(session.week_start)
        held["now"] = setup.clock or monday + timedelta(days=3, hours=15, minutes=40)
        if setup.seed != "empty":
            week = (held["now"].date() - timedelta(days=held["now"].weekday())).isoformat()
            if week != session.week_start:
                session.load_week(week, discard=True)
                wait_until(app, lambda: not session.busy and session.week_start == week, 20)
            session.selected_day = held["now"].date().isoformat()
        if setup.seed == "rig":
            seed_week(app, session)
        pack = None
        preset = "default"
        if setup.look is not None:
            preset = setup.look if setup.look in LOOK_PRESETS else "default"
            pack = None if setup.look in LOOK_PRESETS else setup.look
        look = {"preset": preset, "knobs": {"text": setup.text}}
        window._look = sanitize_look(look)
        session.look = window._look
        # Each slot takes the design only if it is that kind of screen; the other keeps its default.
        window._layout = sanitize_layout({"main": setup.design, "day": setup.design, "options": {}})
        if setup.seed == "empty":
            if setup.clock_24h or pack:
                log("setup note: clock_24h and a pack are chosen on the Setup pages when seed is empty")
        else:
            updates = {"clock_24h": setup.clock_24h}
            if pack:
                updates["theme_pack"] = pack
            session.save_preferences(updates)
            wait_until(app, lambda: not session.busy, 20)
            window._set_clock()
        window._apply_appearance()
        if setup.seed != "empty":
            session.set_view("week")
            window._on_week()
        # A hidden desktop starts with no active window, and a menu opened from one that is not active
        # closes at once, so the first click on a menu button did nothing.
        window.raise_()
        window.activateWindow()
        wait_until(app, window.isActiveWindow, 5)
        wait_until(app, lambda: True, 0.6)

    # What is on screen

    def kind_of(widget: object) -> str:
        return type(widget).__name__

    def words_of(widget: QWidget) -> str:
        if isinstance(widget, QLineEdit):
            return "(hidden)" if widget.echoMode() != QLineEdit.EchoMode.Normal else widget.text()
        if isinstance(widget, (QAbstractButton, QLabel, QAbstractSpinBox)):
            return widget.text()
        if isinstance(widget, (QTextEdit, QPlainTextEdit)):
            return widget.toPlainText()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return ""

    def is_shown(widget: QWidget) -> bool:
        return widget.isVisible() and widget.width() > 0 and widget.height() > 0

    def tops() -> list[QWidget]:
        """The window, and the dialogs and menus open over it. Other parentless widgets (a design's view
        still being built) are not something a student sees."""
        asked = (QApplication.activeModalWidget(), QApplication.activePopupWidget())
        over = [
            w
            for w in QApplication.topLevelWidgets()
            if w is not window and is_shown(w) and (window.isAncestorOf(w) or w in asked)
        ]
        return [window, *over]

    def describe(widget: object) -> str:
        if widget is None:
            return "none"
        name = widget.objectName() if hasattr(widget, "objectName") else ""
        shown = f"{kind_of(widget)}#{name}" if name else kind_of(widget)
        words = words_of(widget) if isinstance(widget, QWidget) else ""
        return f'{shown} "{words[:40]}"' if words else shown

    def to_window(widget: QWidget, rect=None) -> list[int]:
        area = widget.rect() if rect is None else rect
        top_left = widget.mapToGlobal(area.topLeft()) - window.mapToGlobal(QPoint(0, 0))
        return [top_left.x(), top_left.y(), area.width(), area.height()]

    def focus_line() -> str:
        modal = QApplication.activeModalWidget()
        menu = QApplication.activePopupWidget()
        focus = describe(QApplication.focusWidget())
        return f"focus {focus}; dialog {describe(modal)}; menu {describe(menu)}"

    def pointer_line() -> str:
        at = window.mapFromGlobal(QCursor.pos())
        return f"pointer at window ({at.x()},{at.y()})"

    # Targets

    def candidates(kind: str, wanted: str) -> list[tuple[int, QPoint, str, QWidget]]:
        """(how well it matches, a global point on it, its name, its window), the best and then reading
        order first."""
        found: list[tuple[int, QPoint, str, QWidget]] = []
        everything: dict[QWidget, None] = {}
        for top in tops():
            everything[top] = None
            everything.update(dict.fromkeys(top.findChildren(QWidget)))
        for widget in everything:
            if not is_shown(widget):
                continue
            if isinstance(widget, QMenu):
                for action in widget.actions():
                    if not action.isVisible() or action.isSeparator():
                        continue
                    if kind == "name":
                        score = 2 if action.objectName() == wanted else 0
                    else:
                        score = matches_words(wanted, action.text())
                    if score:
                        spot = widget.mapToGlobal(widget.actionGeometry(action).center())
                        found.append((score, spot, f'menu item "{action.text()}"', widget))
            shown = widget.visibleRegion().boundingRect()
            if shown.isEmpty():
                continue
            if kind == "name":
                score = 2 if widget.objectName() == wanted else 0
            else:
                own = words_of(widget) if isinstance(widget, QAbstractButton | QLabel) else ""
                score = max(matches_words(wanted, own), matches_words(wanted, widget.accessibleName()))
            if score:
                found.append((score, widget.mapToGlobal(shown.center()), describe(widget), widget.window()))
        return sorted(found, key=lambda item: (-item[0], item[1].y(), item[1].x()))

    def locate(target: tuple[str, object]) -> tuple[QPoint, str]:
        kind, value = target
        if kind == "point":
            x, y = value  # type: ignore[misc]
            return window.mapToGlobal(QPoint(x, y)), f"window ({x},{y})"
        found = candidates(kind, str(value))
        label = f'"{value}"'
        if not found:
            raise CannotDo(f"no visible widget or menu item for {label}")
        modal = QApplication.activeModalWidget()
        if modal is not None:
            # A person cannot press what a dialog covers; a menu opened from the dialog is fine.
            popup = Qt.WindowType.Popup
            found = [
                i for i in found if i[3] is modal or modal.isAncestorOf(i[3]) or i[3].windowType() == popup
            ]
            if not found:
                raise CannotDo(f"{label} is behind the open dialog {describe(modal)}")
        best = found[0]
        extra = f" (first of {len(found)})" if len(found) > 1 else ""
        return best[1], f"{best[2]}{extra}"

    # Steps

    def point_in_window(point: QPoint) -> str:
        at = window.mapFromGlobal(point)
        return f"window ({at.x()},{at.y()})"

    def move_to(point: QPoint):
        # No --sync: xdotool waits forever for a pointer that is already where it was told to go.
        xdo("mousemove", point.x(), point.y())
        yield 80

    def press(button: int):
        """A press that lasts as long as a finger does. An instant click never opened a menu button's menu."""
        xdo("mousedown", button)
        yield 80
        xdo("mouseup", button)

    def locate_waiting(target: tuple[str, object]):
        """Like locate, but a menu or dialog that is still opening gets up to 2 s to show, as a person
        would wait for it."""
        for _ in range(20):
            try:
                return locate(target)
            except CannotDo:
                yield 100
        return locate(target)

    def do_click(action: str, target: tuple[str, object]):
        point, what = yield from locate_waiting(target)
        yield from move_to(point)
        yield from press(3 if action == "right_click" else 1)
        if action == "double_click":
            yield 80
            yield from press(1)
        yield 350
        return f"{what} at {point_in_window(point)}"

    def do_drag(start: tuple[str, object], end: tuple[str, object]):
        first, from_what = yield from locate_waiting(start)
        last, to_what = yield from locate_waiting(end)
        resting = {"at": first}
        still = QTimer()
        still.setInterval(250)
        still.timeout.connect(lambda: xdo("mousemove", resting["at"].x(), resting["at"].y()))
        yield from move_to(first)
        xdo("mousedown", 1)
        still.start()
        try:
            yield 120
            for index in range(1, 19):
                resting["at"] = first + (last - first) * index / 18
                xdo("mousemove", resting["at"].x(), resting["at"].y())
                yield 25
            yield 200
        finally:
            still.stop()
            xdo("mouseup", 1)
        yield 400
        return f"{from_what} {point_in_window(first)} to {to_what} {point_in_window(last)}"

    def whole_window() -> str:
        return str(window.size().width()) + "x" + str(window.size().height())

    def save_shots(label: str, number: int) -> list[str]:
        names = []
        for index, top in enumerate(tops()):
            suffix = "" if top is window else f"-{kind_of(top)}{index}"
            path = out / f"{number:02d}-{label}{suffix}.png"
            top.grab().save(str(path))
            names.append(path.name)
        return names

    def checked_state(widget: QWidget) -> bool | None:
        if isinstance(widget, QAbstractButton) and widget.isCheckable():
            return widget.isChecked()
        return None

    def entry(widget: QWidget, depth: int) -> dict:
        return {
            "class": kind_of(widget),
            "objectName": widget.objectName(),
            "accessibleName": widget.accessibleName(),
            "accessibleDescription": widget.accessibleDescription(),
            "text": words_of(widget),
            "geometry": to_window(widget),
            "enabled": widget.isEnabled(),
            "hasFocus": widget.hasFocus(),
            "checked": checked_state(widget),
            "depth": depth,
        }

    def walk(widget: QWidget, depth: int, into: list[dict]) -> None:
        into.append(entry(widget, depth))
        if isinstance(widget, QMenu):
            for action in widget.actions():
                if action.isVisible() and not action.isSeparator():
                    into.append(menu_entry(widget, action, depth + 1))
        for child in widget.children():
            if isinstance(child, QWidget) and not child.isWindow() and is_shown(child):
                walk(child, depth + 1, into)

    def menu_entry(menu: QMenu, action: QAction, depth: int) -> dict:
        return {
            "class": "QAction",
            "objectName": action.objectName(),
            "accessibleName": "",
            "accessibleDescription": "",
            "text": action.text(),
            "geometry": to_window(menu, menu.actionGeometry(action)),
            "enabled": action.isEnabled(),
            "hasFocus": False,
            "checked": action.isChecked() if action.isCheckable() else None,
            "depth": depth,
        }

    def save_tree(label: str, number: int) -> str:
        widgets: list[dict] = []
        for top in tops():
            walk(top, 0, widgets)
        modal = QApplication.activeModalWidget()
        body = {
            "label": label,
            "clock": held["now"].isoformat(timespec="minutes"),
            "window_size": [window.width(), window.height()],
            "focused": describe(QApplication.focusWidget()),
            "active_modal": describe(modal),
            "widgets": widgets,
        }
        path = out / f"{number:02d}-{label}.json"
        path.write_text(json.dumps(body, indent=1))
        return path.name

    def advance_clock(minutes: int) -> None:
        held["now"] += timedelta(minutes=minutes)
        # The app reads the held clock when its timers fire, so fire them now rather than in 30 s.
        window._alert_tick.timeout.emit()
        window._layout_tick.timeout.emit()
        session.tick_focus()

    def do_step(number: int, step: Step):
        action, value = step.action, step.value
        if action in ("click", "double_click", "right_click"):
            return (yield from do_click(action, value))  # type: ignore[arg-type]
        if action == "drag":
            return (yield from do_drag(*value))  # type: ignore[misc]
        if action == "type":
            xdo("type", "--delay", 20, "--", value)
            yield 200
            return f"typed {len(str(value))} characters"
        if action == "key":
            xdo("key", "--", value)
            yield 200
            return str(value)
        if action == "wait":
            yield value
            return f"{value} ms"
        if action == "advance_clock":
            advance_clock(int(value))  # type: ignore[arg-type]
            yield 400
            return f"clock now {held['now']:%Y-%m-%d %H:%M}"
        if action == "shot":
            return "wrote " + ", ".join(save_shots(str(value), number))
        if action == "tree":
            return "wrote " + save_tree(str(value), number)
        return str(value)

    results = {"done": 0, "not_done": 0}

    def target_words(target: tuple[str, object]) -> str:
        kind, value = target
        if kind == "point":
            return f"window {list(value)}"  # type: ignore[call-overload]
        return f"text {value!r}" if kind == "text" else repr(value)

    def step_words(step: Step) -> str:
        if step.action == "drag":
            return f"drag {target_words(step.value[0])} to {target_words(step.value[1])}"  # type: ignore[index]
        if step.action in ("click", "double_click", "right_click"):
            return f"{step.action} {target_words(step.value)}"  # type: ignore[arg-type]
        return f"{step.action} {step.value!r}"

    def script():
        for number, step in enumerate(play.steps, 1):
            head = f"{number:02d} {step_words(step)}"
            try:
                what = yield from do_step(number, step)
                outcome = f"ok: {what}"
                results["done"] += 1
            except CannotDo as why:
                outcome = f"NOT DONE: {why}"
                results["not_done"] += 1
            except (subprocess.SubprocessError, OSError, RuntimeError, AssertionError) as broken:
                outcome = f"NOT DONE: {type(broken).__name__}: {broken}"
                results["not_done"] += 1
                traceback.print_exc()
            yield 100
            log(f"{head} -> {outcome}; {pointer_line()}; {focus_line()}")
        number = len(play.steps) + 1
        pictures = save_shots("final", number)
        tree = save_tree("final", number)
        log(f"{number:02d} final -> wrote {', '.join(pictures)}, {tree}; {pointer_line()}; {focus_line()}")

    finished: list[bool] = []

    def drive(steps) -> None:
        def advance() -> None:
            try:
                wait = next(steps)
            except StopIteration:
                finished.append(True)
                app.quit()
                return
            except Exception as broken:  # noqa: BLE001 - the play stops and says why rather than hanging
                traceback.print_exc()
                python_errors.append(f"{type(broken).__name__}: {broken}")
                app.quit()
                return
            QTimer.singleShot(wait, advance)

        advance()

    try:
        prepare()
    except Exception as broken:  # noqa: BLE001 - say what setup could not do, then stop
        traceback.print_exc()
        python_errors.append(f"setup: {type(broken).__name__}: {broken}")
        log(f"SETUP FAILED: {type(broken).__name__}: {broken}")
        log_file.close()
        server.stop()
        return 1
    log(
        f"play {play.name}: seed {setup.seed}, design {setup.design}, window {whole_window()}, "
        f"clock {held['now']:%Y-%m-%d %H:%M} held, {len(play.steps)} steps"
    )
    started = time.monotonic()
    QTimer.singleShot(200, lambda: drive(script()))
    app.exec()
    seconds = time.monotonic() - started
    server.stop()
    if python_errors:
        log(f"STOPPED by a Python error: {python_errors[0]}")
        log_file.close()
        return 1
    log(
        f"Finished in {seconds:.0f} s: {results['done']} steps done, {results['not_done']} not done. "
        f"Log, shots and trees in {out}"
    )
    log_file.close()
    return 0 if finished else 1
