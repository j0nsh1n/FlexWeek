"""Drive FlexWeek with a real pointer on a hidden desktop, and check that the saved week agrees.

    .venv/bin/python scripts/rig/drive.py                       # every design, every tab
    .venv/bin/python scripts/rig/drive.py --design bento --tab day
    .venv/bin/python scripts/rig/drive.py --list

Every scenario starts from the same seeded week with the clock held at Thursday 15:40. It opens its
tab with the pointer, performs one gesture with xdotool on the hidden session's X display, waits for
the save, reloads the week from the server and asserts on what came back. A screenshot is taken
while the pointer is still held and another after the drop, and each design's run is recorded as a
video with the pointer drawn in. Results land in /tmp/flexweek-rig/<run>/.

Surfaces are found through the hours interface below, which every hours surface provides. A surface
that has no hours fails the scenarios that need them, which is what the 0.14.3 baseline records.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
TABS = ("day", "week", "month")
PASSWORD = "a-long-test-password"

Step = Generator[tuple, object]


@dataclass(frozen=True)
class Scenario:
    name: str
    tab: str
    run: Callable[[object], Step]
    only: tuple[str, ...] = ()


class NoSurface(Exception):
    """The tab has no hours, chip or cell to do this on."""


def child_main(args: argparse.Namespace) -> int:
    from PySide6.QtCore import QPoint, QPointF, QRect, QStandardPaths, QTimer
    from PySide6.QtGui import QColor, QCursor, QPainter, QPen
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QWidget

    QStandardPaths.setTestModeEnabled(True)
    app = QApplication(["flexweek-rig"])

    from desktop.native.calendar import sunday_due
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup, wait_until

    out = Path(args.out)
    server = LocalServer(Path(tempfile.mkdtemp()) / "rig.db")
    server.start()
    window = NativeWindow(server.origin)
    window.resize(1280, 820)
    window.move(0, 0)
    window.show()
    window.username.setText("rig_student")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(app, lambda: window._stack.currentWidget().objectName() == "recoveryPage", 20)
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    past_setup(app, window)
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    session.now_ms = lambda: int(thursday.timestamp() * 1000)
    due_sunday = sunday_due(session.week_start)
    due_friday = (
        datetime.fromisoformat(session.week_start) + timedelta(days=4)
    ).date().isoformat() + "T23:59"
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": 90,
            "days": [1, 3],
        }
    )
    for key, title, due in (
        ("essay", "History essay", due_sunday),
        ("math", "Math worksheet", due_sunday),
        ("poster", "Science poster", due_friday),
    ):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    wait_until(app, lambda: not session.busy and not session.dirty, 20)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
    session.save()
    wait_until(app, lambda: not session.busy and not session.dirty, 20)
    seed = [dict(block) for block in session.blocks]
    ids = {
        key: next(b["id"] for b in session.blocks if b.get("assignment_id") == key)
        for key in ("essay", "math", "poster")
    }
    thursday_iso = thursday.date().isoformat()

    def block(block_id: str) -> dict | None:
        return next((b for b in session.blocks if b["id"] == block_id), None)

    class Recorder:
        """Frames of the window with the pointer drawn in, for the design's video."""

        def __init__(self) -> None:
            self.folder: Path | None = None
            self.count = 0
            self.timer = QTimer()
            self.timer.setInterval(100)
            self.timer.timeout.connect(self.frame)

        def begin(self, folder: Path) -> None:
            self.folder, self.count = folder, 0
            folder.mkdir(parents=True, exist_ok=True)
            self.timer.start()

        def frame(self) -> None:
            if self.folder is None:
                return
            image = window.grab().toImage()
            at = window.mapFromGlobal(QCursor.pos())
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#ffffff"), 3))
            painter.setBrush(QColor("#e11d48"))
            painter.drawEllipse(QPointF(at), 7, 7)
            painter.end()
            image.save(str(self.folder / f"{self.count:05d}.jpg"), "JPG", 82)
            self.count += 1

        def finish(self, video: Path) -> None:
            self.timer.stop()
            folder, self.folder = self.folder, None
            if folder is not None and self.count:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-loglevel",
                        "error",
                        "-y",
                        "-framerate",
                        "10",
                        "-i",
                        str(folder / "%05d.jpg"),
                        "-pix_fmt",
                        "yuv420p",
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        str(video),
                    ],
                    check=False,
                )

    recorder = Recorder()

    def xdo(*parts: object) -> None:
        subprocess.run(["xdotool", *map(str, parts)], check=True)

    class Rig:
        def __init__(self) -> None:
            self.design = ""
            self.shots: Path = out
            self.scenario = ""

        # Pointer

        def move(self, point: QPoint) -> Step:
            xdo("mousemove", "--sync", point.x(), point.y())
            yield ("wait", 30)

        def click(self, point: QPoint) -> Step:
            yield from self.move(point)
            xdo("click", 1)
            yield ("wait", 250)

        def drag(self, start: QPoint, end: QPoint, held: Callable[[], None] | None = None) -> Step:
            """Press, travel in steps as a hand does, let go. `held` runs while still pressed."""
            yield from self.move(start)
            xdo("mousedown", 1)
            yield ("wait", 120)
            steps = 18
            for index in range(1, steps + 1):
                point = start + (end - start) * index / steps
                xdo("mousemove", point.x(), point.y())
                yield ("wait", 25)
            yield ("wait", 200)
            self.shot("held")
            if held is not None:
                held()
            xdo("mouseup", 1)
            yield ("wait", 400)

        def key(self, *keys: str) -> Step:
            xdo("key", *keys)
            yield ("wait", 150)

        def type(self, words: str) -> Step:
            xdo("type", "--delay", "20", words)
            yield ("wait", 150)

        def shot(self, label: str) -> None:
            window.grab().save(str(self.shots / f"{self.design}-{self.scenario}-{label}.png"))

        # Where things are

        def tab(self, name: str) -> Step:
            button = window.findChild(QPushButton, f"view{name.title()}")
            yield from self.click(button.mapToGlobal(button.rect().center()))
            yield ("wait", 500)

        def surface(self, kind: str) -> object:
            """The hours (or month) surface on screen. Designs provide `hours_surfaces()`; Today's
            app's week canvas predates that interface and is read through its own methods."""
            shown = window.planner.currentWidget()
            finder = getattr(shown, "hours_surfaces" if kind == "hours" else "month_surfaces", None)
            if finder is not None:
                found = [item for item in finder() if item.isVisible()]
                if found:
                    return found[0]
            if kind == "hours" and shown is window.week_table:
                return LegacyWeek(shown)
            raise NoSurface(f"no {kind} on the {session.planner_view} tab of {self.design}")

        def reveal(self, day: int, first: int, last: int) -> Step:
            """Scroll so this stretch of the day is on screen before anything is measured."""
            surface = self.surface("hours")
            reveal = getattr(surface, "reveal", None)
            if reveal is not None:
                reveal(day, first, last)
            yield ("wait", 150)

        def at(self, day: int, minute: int, nudge: int = 3) -> QPoint:
            return self.surface("hours").point_for(day, minute) + QPoint(0, nudge)

        def block_rect(self, block_id: str, day: int) -> QRect:
            rect = self.surface("hours").block_rect(block_id, day)
            if rect is None:
                raise NoSurface(f"{block_id} is not drawn on day {day}")
            return rect

        def chip(self, block_id: str) -> QPoint:
            """Something on screen that stands for this block and can be picked up."""
            for widget in window.findChildren(QWidget):
                if not widget.isVisible():
                    continue
                if getattr(widget, "block_id", None) == block_id or widget.property("block_id") == block_id:
                    return widget.mapToGlobal(widget.rect().center())
            raise NoSurface(f"nothing on screen stands for {block_id}")

        def settled(self) -> Step:
            yield ("until", lambda: not session.busy and not session.dirty, 8000)
            session.load_week(session.week_start, discard=True)
            yield ("wait", 50)
            yield ("until", lambda: not session.busy, 8000)

        def accept_dialog(self, title: str) -> Step:
            yield ("until", lambda: isinstance(QApplication.activeModalWidget(), QDialog), 3000)
            dialog = QApplication.activeModalWidget()
            if dialog is None:
                raise AssertionError("no dialog opened")
            field = next((f for f in dialog.findChildren(QLineEdit) if f.isVisible()), None)
            if field is not None:
                yield from self.click(field.mapToGlobal(field.rect().center()))
                yield from self.key("ctrl+a")
                yield from self.type(title)
            yield from self.key("Return")
            yield ("wait", 300)

    class LegacyWeek:
        """Today's app's 0.14.3 week canvas, read through the methods it already had."""

        def __init__(self, canvas: object) -> None:
            self.canvas = canvas

        def reveal(self, day: int, first: int, last: int) -> None:
            top, bottom = self.canvas.point_of(day, first), self.canvas.point_of(day, last)
            self.canvas.scroll.ensureVisible(bottom.x(), bottom.y(), 0, 40)
            self.canvas.scroll.ensureVisible(top.x(), top.y(), 0, 40)

        def point_for(self, day: int, minute: int) -> QPoint:
            return self.canvas.body.mapToGlobal(self.canvas.point_of(day, minute))

        def block_rect(self, block_id: str, day: int) -> QRect | None:
            for shape, rect, _count, _held in self.canvas.body.laid_out():
                if shape.block_id == block_id and shape.day == day:
                    top_left = self.canvas.body.mapToGlobal(rect.topLeft().toPoint())
                    return QRect(top_left, rect.size().toSize())
            return None

        def day_name(self, day: int) -> QPoint:
            area = self.canvas.body.column_rect(self.canvas.body.days.index(day))
            return self.canvas.header.mapToGlobal(
                QPoint(int(area.center().x()), self.canvas.header.height() // 2)
            )

    rig = Rig()

    # Scenarios. Each yields steps and ends with plain asserts on the reloaded week.

    def expect(condition: bool, words: str) -> None:
        if not condition:
            raise AssertionError(words)

    def middle(rect: QRect) -> QPoint:
        return rect.center()

    def day_tab(r: Rig) -> Step:
        yield from r.tab("week")
        session.open_day(thursday_iso)
        yield ("wait", 500)

    def day_move(r: Rig) -> Step:
        yield from day_tab(r)
        yield from r.reveal(3, 18 * 60 + 30, 21 * 60 + 30)
        box = r.block_rect(ids["essay"], 3)
        yield from r.drag(middle(box), middle(box) + (r.at(3, 20 * 60 + 30) - r.at(3, 19 * 60)))
        yield from r.settled()
        got = block(ids["essay"])
        expect((got["days"], got["start"]) == ([3], "20:30"), f"essay is {got['days']} {got['start']}")

    def day_resize(r: Rig) -> Step:
        yield from day_tab(r)
        yield from r.reveal(3, 18 * 60 + 30, 21 * 60)
        box = r.block_rect(ids["essay"], 3)
        edge = QPoint(box.center().x(), box.bottom() - 2)
        yield from r.drag(edge, edge + (r.at(3, 20 * 60 + 30) - r.at(3, 20 * 60)))
        yield from r.settled()
        got = block(ids["essay"])
        expect(
            (got["start"], got["duration_min"]) == ("19:00", 90),
            f"essay is {got['start']} {got['duration_min']}",
        )

    def day_create(r: Rig) -> Step:
        yield from day_tab(r)
        yield from r.reveal(3, 20 * 60 + 30, 22 * 60 + 30)
        yield from r.drag(r.at(3, 21 * 60), r.at(3, 22 * 60))
        yield from r.accept_dialog("Club")
        yield from r.settled()
        made = [b for b in session.blocks if b["title"] == "Club"]
        expect(
            [(b["days"], b["start"], b["duration_min"]) for b in made] == [([3], "21:00", 60)],
            f"made {[(b['days'], b['start'], b['duration_min']) for b in made]}",
        )

    def day_homework_in(r: Rig) -> Step:
        yield from day_tab(r)
        yield from r.reveal(3, 17 * 60, 19 * 60)
        yield from r.drag(r.chip(ids["math"]), r.at(3, 17 * 60 + 45))
        yield from r.settled()
        got = block(ids["math"])
        expect(
            (got["days"], got.get("start"), got.get("pinned")) == ([3], "17:45", True),
            f"math is {got['days']} {got.get('start')}",
        )

    def week_move_day(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(3, 17 * 60 + 30, 20 * 60 + 30)
        box = r.block_rect(ids["essay"], 3)
        yield from r.drag(middle(box), middle(box) + (r.at(4, 18 * 60) - r.at(3, 19 * 60)))
        yield from r.settled()
        got = block(ids["essay"])
        expect((got["days"], got["start"]) == ([4], "18:00"), f"essay is {got['days']} {got['start']}")

    def week_resize_top(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(3, 18 * 60, 20 * 60 + 30)
        box = r.block_rect(ids["essay"], 3)
        edge = QPoint(box.center().x(), box.top() + 2)
        yield from r.drag(edge, edge + (r.at(3, 18 * 60 + 30) - r.at(3, 19 * 60)))
        yield from r.settled()
        got = block(ids["essay"])
        expect(
            (got["start"], got["duration_min"]) == ("18:30", 90),
            f"essay is {got['start']} {got['duration_min']}",
        )

    def week_create(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(5, 9 * 60 + 30, 11 * 60 + 30)
        yield from r.drag(r.at(5, 10 * 60), r.at(5, 11 * 60))
        yield from r.accept_dialog("Club")
        yield from r.settled()
        made = [b for b in session.blocks if b["title"] == "Club"]
        expect(
            [(b["days"], b["start"], b["duration_min"]) for b in made] == [([5], "10:00", 60)],
            f"made {[(b['days'], b['start'], b['duration_min']) for b in made]}",
        )

    def week_series(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(2, 8 * 60, 11 * 60)
        box = r.block_rect("school", 2)
        grab = QPoint(box.center().x(), r.at(2, 9 * 60).y())
        yield from r.drag(grab, grab + (r.at(2, 10 * 60) - r.at(2, 9 * 60)))
        yield from r.settled()
        school = sorted((tuple(b["days"]), b["start"]) for b in session.blocks if b["title"] == "School")
        expect(school == [((0, 1, 3, 4), "08:00"), ((2,), "09:00")], f"school is {school}")

    def week_beside(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(4, 9 * 60, 11 * 60)
        yield from r.drag(r.chip(ids["math"]), r.at(4, 10 * 60))
        yield from r.settled()
        got = block(ids["math"])
        expect(
            (got["days"], got.get("start"), got.get("pinned")) == ([4], "10:00", True),
            f"math is {got['days']} {got.get('start')}",
        )

    def week_past_due(r: Rig) -> Step:
        yield from r.tab("week")
        yield from r.reveal(5, 16 * 60 + 30, 18 * 60 + 30)
        yield from r.drag(r.chip(ids["poster"]), r.at(5, 17 * 60))
        said = session.message
        yield from r.settled()
        got = block(ids["poster"])
        expect(not got.get("start"), f"poster was placed at {got['days']} {got.get('start')}")
        expect("after it is due" in said, f"said {said!r}")

    def week_open_day(r: Rig) -> Step:
        yield from r.tab("week")
        surface = r.surface("hours")
        yield from r.click(surface.day_name(4))
        yield ("wait", 400)
        friday = (thursday + timedelta(days=1)).date().isoformat()
        expect(
            (session.planner_view, session.selected_day) == ("day", friday),
            f"showing {session.planner_view} {session.selected_day}",
        )

    def week_fits(r: Rig) -> Step:
        yield from r.tab("week")
        surface = r.surface("hours")
        top, bottom = surface.point_for(0, 6 * 60), surface.point_for(0, 23 * 60)
        area = window.planner.mapToGlobal(window.planner.rect().topLeft())
        visible = QRect(area, window.planner.size())
        expect(visible.contains(top) and visible.contains(bottom), "06:00 to 23:00 does not fit on screen")

    def month_times(r: Rig) -> Step:
        yield from r.tab("month")
        month = r.surface("month")
        words = month.chip_words(ids["essay"], thursday_iso)
        expect(words == "19:00 History essay", f"the chip reads {words!r}")

    def month_open_day(r: Rig) -> Step:
        yield from r.tab("month")
        month = r.surface("month")
        friday = (thursday + timedelta(days=1)).date().isoformat()
        yield from r.click(month.cell_point(friday))
        yield ("wait", 400)
        expect(
            (session.planner_view, session.selected_day) == ("day", friday),
            f"showing {session.planner_view} {session.selected_day}",
        )

    def month_move_date(r: Rig) -> Step:
        yield from r.tab("month")
        month = r.surface("month")
        saturday = (thursday + timedelta(days=2)).date().isoformat()
        yield from r.drag(month.chip_point(ids["essay"], thursday_iso), month.cell_point(saturday))
        yield from r.settled()
        got = block(ids["essay"])
        expect((got["days"], got["start"]) == ([5], "19:00"), f"essay is {got['days']} {got['start']}")

    scenarios = [
        Scenario("day-move", "day", day_move),
        Scenario("day-resize", "day", day_resize),
        Scenario("day-create", "day", day_create),
        Scenario("day-homework-in", "day", day_homework_in),
        Scenario("week-move-day", "week", week_move_day),
        Scenario("week-resize-top", "week", week_resize_top),
        Scenario("week-create", "week", week_create),
        Scenario("week-series-one-day", "week", week_series),
        Scenario("week-beside", "week", week_beside),
        Scenario("week-past-due", "week", week_past_due),
        Scenario("week-open-day", "week", week_open_day),
        Scenario("week-fits", "week", week_fits, only=("classic",)),
        Scenario("month-times", "month", month_times),
        Scenario("month-open-day", "month", month_open_day),
        Scenario("month-move-date", "month", month_move_date),
    ]
    if args.list:
        for scenario in scenarios:
            print(scenario.tab, scenario.name, ",".join(scenario.only) or "every design")
        return 0

    chosen_designs = [args.design] if args.design else list(DESIGNS)
    chosen = [
        s
        for s in scenarios
        if (not args.tab or s.tab == args.tab) and (not args.scenario or s.name == args.scenario)
    ]
    results: list[dict] = []

    def reset() -> None:
        while QApplication.activeModalWidget() is not None:
            QApplication.activeModalWidget().reject()
            app.processEvents()
        session.blocks = [dict(item) for item in seed]
        session.dirty = True
        session.save()
        wait_until(app, lambda: not session.busy and not session.dirty, 20)
        session.selected_day = thursday_iso
        session._say("")

    def use_design(design: str) -> None:
        window._layout = sanitize_layout({"main": design, "day": "one"})
        window._apply_appearance()
        session.set_view("week")
        window._on_week()
        wait_until(app, lambda: True, 0.5)

    plan = [
        (design, scenario)
        for design in chosen_designs
        for scenario in chosen
        if not scenario.only or design in scenario.only
    ]

    def run_all() -> Step:
        current = None
        for design, scenario in plan:
            if design != current:
                if current is not None:
                    recorder.finish(out / f"{current}.mp4")
                current = design
                use_design(design)
                recorder.begin(out / "frames" / design)
            reset()
            rig.design, rig.scenario = design, scenario.name
            started = time.monotonic()
            outcome = {"design": design, "tab": scenario.tab, "scenario": scenario.name}
            try:
                yield from scenario.run(rig)
                outcome["result"] = "PASS"
            except NoSurface as missing:
                outcome.update(result="FAIL", why=f"no surface: {missing}")
            except AssertionError as wrong:
                outcome.update(result="FAIL", why=str(wrong))
            except Exception as broken:  # noqa: BLE001 - the rig reports, it does not stop
                outcome.update(
                    result="ERROR",
                    why=f"{type(broken).__name__}: {broken}",
                    trace=traceback.format_exc(limit=4),
                )
            outcome["seconds"] = round(time.monotonic() - started, 1)
            rig.shot("end")
            results.append(outcome)
            print(
                f"{outcome['result']:5s} {design:9s} {scenario.name:22s} {outcome.get('why', '')}", flush=True
            )
            xdo("mouseup", 1)
            yield ("wait", 100)
        if current is not None:
            recorder.finish(out / f"{current}.mp4")

    finished: list[bool] = []

    def drive(steps: Step) -> None:
        def advance(value: object = None) -> None:
            try:
                command = steps.send(value)
            except StopIteration:
                finished.append(True)
                app.quit()
                return
            except Exception:  # noqa: BLE001 - the rig reports and stops rather than hanging
                traceback.print_exc()
                app.quit()
                return
            if command[0] == "wait":
                QTimer.singleShot(command[1], advance)
            elif command[0] == "until":
                predicate, limit = command[1], command[2]
                deadline = time.monotonic() + limit / 1000

                def poll() -> None:
                    if predicate():
                        advance(True)
                    elif time.monotonic() > deadline:
                        advance(False)
                    else:
                        QTimer.singleShot(20, poll)

                poll()

        advance()

    QTimer.singleShot(300, lambda: drive(run_all()))
    app.exec()
    (out / "results.json").write_text(json.dumps(results, indent=1))
    server.stop()
    passed = sum(1 for item in results if item["result"] == "PASS")
    print(f"\n{passed}/{len(results)} passed. Screenshots, videos and results.json in {out}")
    return 0 if finished and passed == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--design", choices=DESIGNS)
    parser.add_argument("--tab", choices=TABS)
    parser.add_argument("--scenario")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.list and not args.child:
        args.out = tempfile.mkdtemp()
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if args.child or args.list:
        return child_main(args)
    import hidden_session

    display = hidden_session.start()
    out = Path(args.out or f"/tmp/flexweek-rig/{datetime.now():%Y%m%d-%H%M%S}")
    out.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"WAYLAND_DISPLAY", "QT_IM_MODULE", "XMODIFIERS"}
    }
    env.update(DISPLAY=display, QT_QPA_PLATFORM="xcb", XDG_DATA_HOME=str(out / "data"))
    command = [sys.executable, __file__, "--child", "--out", str(out)]
    for flag in ("design", "tab", "scenario"):
        if getattr(args, flag):
            command += [f"--{flag}", getattr(args, flag)]
    return subprocess.run(command, env=env, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
