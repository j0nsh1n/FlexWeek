"""Bento's hero clock and hero board, with live hours in the large purple tile."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLayout, QPushButton, QVBoxLayout, QWidget

from desktop.native.calendar import CATEGORIES, DAY_FULL, DAYS
from desktop.native.hours.canvas import BlockPainter, Drawn, HoursCanvas
from desktop.native.hours.chips import TrayChip
from desktop.native.hours.geometry import FIRST, LAST, LinearTrack
from desktop.native.hours.hand import Hand
from desktop.native.hours.zoom import HoursScroll, Scale
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    button,
    css,
    empty,
    label,
    plan_buttons,
    rules,
    scrolling,
)
from desktop.native.weekmodel import clock_label, due_label, length_label

DAY_SCALE = Scale("bento.day", (96, 128, 160, 192), 96)
WEEK_SCALE = Scale("bento.week", (32, 48, 64, 96, 128), 48)
GUTTER = 52
PAD = 6


def _hours_height(px: int) -> int:
    return round((LAST - FIRST) / 60 * px) + 2 * PAD


def _week_tracks(area: QRectF) -> list[LinearTrack]:
    width = area.width() / 7
    return [
        LinearTrack(day, QRectF(area.left() + day * width + 2, area.top() + PAD,
                                width - 4, area.height() - 2 * PAD))
        for day in range(7)
    ]


def _detach(layout: QLayout, widget: QWidget, host: QWidget) -> bool:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            layout.takeAt(index)
            widget.hide()
            widget.setParent(host)
            return True
        child = item.widget()
        if child is not None and child.layout() is not None and _detach(child.layout(), widget, host):
            return True
        inner = item.layout()
        if inner is not None and _detach(inner, widget, host):
            return True
    return False


class BentoPainter(BlockPainter):
    """Purple hours with pale category blocks and the shared painter's readable labels."""

    def __init__(self, tokens: dict[str, str]) -> None:
        super().__init__({
            "window": tokens["accent"],
            "grid": tokens["accent_ink"],
            "hairline": tokens["accent_ink"],
            "accent": tokens["accent_ink"],
            "accent_ink": tokens["accent"],
            "error": tokens["danger"],
            "text": tokens["accent_ink"],
            "muted": tokens["accent_ink"],
        })
        self.tokens = tokens

    def track(self, painter: QPainter, track: LinearTrack, today: bool) -> None:
        wash = QColor(self.tokens["accent_ink"])
        wash.setAlphaF(0.055 if not today else 0.10)
        painter.fillRect(track.area, wash)
        rule = QColor(self.tokens["accent_ink"])
        rule.setAlphaF(0.22)
        first_hour = ((track.first + 59) // 60) * 60
        for minute in range(first_hour, track.last + 1, 60):
            at = track.area.top() + track.offset(minute)
            painter.setPen(QPen(rule, 1))
            painter.drawLine(QPointF(track.area.left(), at), QPointF(track.area.right(), at))

    def fills(self, drawn: Drawn) -> tuple[QColor, QColor, QColor | None, QColor | None]:
        category = CATEGORIES.get(drawn.category, {})
        colour = category.get("color")
        fill = QColor(colour or self.tokens["surface"])
        mark = QColor(category.get("mark") or self.tokens["line"])
        if drawn.done or drawn.missed:
            fill = fill.lighter(115)
        ink = QColor("#20243a" if colour else self.tokens["text"])
        return fill, ink, None, mark


class BentoCanvas(HoursCanvas):
    def __init__(self, hand: Hand, painter: BentoPainter,
                 tracks: Callable[[QRectF], list[LinearTrack]], *, gutter: int) -> None:
        super().__init__(hand, painter, tracks, gutter=gutter)
        self.day_buttons: dict[int, QPushButton] = {}

    def day_name(self, day: int) -> QPoint:
        pick = self.day_buttons.get(day)
        return pick.mapToGlobal(pick.rect().center()) if pick is not None else super().day_name(day)


class BentoView(LayoutView):
    layout_id = "bento"
    uses_drawer = False

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent, hand=hand)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._board = QWidget()
        self._board.setObjectName("bentoBoard")
        self._grid = QGridLayout(self._board)
        outer.addWidget(scrolling(self._board, "bentoScroll"))
        self._scrolls: dict[str, HoursScroll] = {}
        self._day = 0
        self._revealed: dict[str, object] = {}

    def shown_day(self, scene: Scene) -> int:
        if scene.surface == "day" and scene.iso_day:
            for day in range(7):
                if scene.week.date_of(day).isoformat() == scene.iso_day:
                    return day
        return scene.today if scene.today is not None else 0

    def _tile(self, scene: Scene, name: str, kicker: str) -> tuple[QFrame, QVBoxLayout]:
        tile = QFrame()
        tile.setObjectName(name)
        tile.setProperty("tile", "hero" if name == "bentoHero" else "plain")
        inner = QVBoxLayout(tile)
        inner.setContentsMargins(scene.px(16), scene.px(14), scene.px(16), scene.px(14))
        inner.setSpacing(scene.px(8))
        heading = label(kicker.upper(), f"{name}Kicker")
        heading.setProperty("role", "kicker")
        inner.addWidget(heading)
        return tile, inner

    def _style(self, scene: Scene) -> None:
        tokens, name = scene.tokens, self.objectName()
        radius = scene.px(24 if scene.options.get("corners") != "square" else 6)
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(name, {
                "#bentoScroll, #bentoBoard": css(background=tokens["bg"]),
                'QFrame[tile="plain"]': css(background=tokens["surface"], border_radius=f"{radius}px"),
                'QFrame[tile="hero"]': css(background=tokens["accent"], border_radius=f"{radius}px"),
                'QFrame[tile="plain"] QLabel': css(color=tokens["text"], font_size=f"{scene.px(13)}px"),
                'QFrame[tile="hero"] QLabel': css(color=tokens["accent_ink"]),
                'QFrame[tile="plain"] QLabel[role="kicker"]': css(
                    color=tokens["accent"], font_size=f"{scene.px(12)}px", font_weight=700,
                    letter_spacing="1px"),
                'QFrame[tile="hero"] QLabel[role="kicker"]': css(
                    color=tokens["accent_ink"], font_size=f"{scene.px(12)}px", font_weight=700,
                    letter_spacing="1px"),
                "#bentoTonightTitle": css(font_size=f"{scene.px(22)}px", font_weight=700),
                "QPushButton": css(background=tokens["cta"], color=tokens["cta_ink"],
                                   border="none", border_radius=f"{scene.px(12)}px",
                                   min_height=f"{scene.px(32)}px", padding=f"0 {scene.px(8)}px"),
                'QPushButton[zoom="true"]': css(min_height="0", padding="0"),
                'QPushButton[kind="row"]': css(background="transparent", color=tokens["text"],
                                               text_align="left", border="none",
                                               border_bottom=f"1px solid {tokens['line']}",
                                               border_radius="0"),
                'QPushButton[kind="chip"]': css(background=tokens["bg"], color=tokens["text"],
                                                text_align="left",
                                                border_left=f"4px solid {tokens['danger']}"),
                'QPushButton[kind="day"]': css(background=tokens["accent"],
                                               color=tokens["accent_ink"], border_radius="0",
                                               font_weight=700),
                "QPushButton:focus": css(border=f"2px solid {tokens['text']}"),
            })
        )

    def _hours(self, scene: Scene, day: int) -> HoursScroll:
        is_day = scene.surface == "day"
        key = "day" if is_day else "week"
        if key not in self._scrolls:
            painter = BentoPainter(scene.tokens)
            tracks = (lambda area: [LinearTrack(self._day, area.adjusted(0, PAD, -PAD, -PAD))]) \
                if is_day else _week_tracks
            canvas = BentoCanvas(self.hand, painter, tracks, gutter=GUTTER)
            canvas.setObjectName("bentoDayHours" if is_day else "bentoWeekHours")
            canvas.setAccessibleName("Hero clock" if is_day else "Hero board")
            canvas.day_opened.connect(
                lambda target: self.day_activated.emit(self.scene.week.date_of(target).isoformat())
            )
            scale = DAY_SCALE if is_day else WEEK_SCALE
            scroll = HoursScroll(canvas, scale, _hours_height,
                                 name="bentoDay" if is_day else "bentoWeek", gutter=GUTTER)
            self.keep_zoom(scroll)
            if not is_day:
                header = QWidget()
                row = QHBoxLayout(header)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(0)
                for target, word in enumerate(DAYS):
                    head = button(word, f"bentoDayName{target}", "day")
                    head.setProperty("day_target", target)
                    head.setAccessibleName(f"Show {DAY_FULL[target]}")
                    head.clicked.connect(lambda _=False, chosen=target:
                        self.day_activated.emit(self.scene.week.date_of(chosen).isoformat()))
                    row.addWidget(head, 1)
                    canvas.day_buttons[target] = head
                scroll.set_header(header)
            self._scrolls[key] = scroll
        scroll = self._scrolls[key]
        canvas = scroll.canvas
        canvas.set_painter(BentoPainter(scene.tokens))
        if is_day:
            changed = day != self._day
            self._day = day
            if changed:
                canvas.relayout()
            canvas.set_week([item for item in scene.week.occurrences if item.day == day],
                            scene.today, scene.minute)
        else:
            canvas.set_week(scene.week.occurrences, scene.today, scene.minute)
            for target, word in enumerate(DAYS):
                head = canvas.day_buttons[target]
                head.setText(f"{word} {scene.week.date_of(target).day}")
        return scroll

    def render(self, scene: Scene, week_changed: bool) -> None:
        self._style(scene)
        for kept in self._scrolls.values():
            _detach(self._grid, kept, self._board)
        empty(self._grid)
        self._grid.setContentsMargins(scene.px(18), scene.px(16), scene.px(18), scene.px(16))
        self._grid.setSpacing(scene.px(12))
        day = self.shown_day(scene)
        is_day = scene.surface == "day"
        name = (f"{DAY_FULL[day]} {scene.week.date_of(day).day} · Your day"
                if is_day else "This week · Drag across days")
        hero, inside = self._tile(scene, "bentoHero", name)
        scroll = self._hours(scene, day)
        scroll.setMinimumHeight(scene.px(440))
        inside.addWidget(scroll, 1)
        rail = QWidget()
        rail.setObjectName("bentoRail")
        side = QVBoxLayout(rail)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(scene.px(12))
        side.addWidget(self._waiting(scene), 1)
        if scene.options.get("tiles") != "essentials":
            if is_day:
                side.addWidget(self._tonight_and_deadlines(scene), 1)
            else:
                side.addWidget(self._deadlines(scene))
        self._grid.addWidget(hero, 0, 0)
        self._grid.addWidget(rail, 0, 1)
        self._grid.setColumnStretch(0, 3 if not is_day else 2)
        self._grid.setColumnStretch(1, 1)
        scroll.show()
        key = "day" if is_day else "week"
        reveal = (scene.week.week_start, day) if is_day else scene.week.week_start
        if self._revealed.get(key) != reveal:
            self._revealed[key] = reveal
            minute = scene.minute if scene.today == day else min(
                (item.start for item in scene.week.on_day(day)), default=8 * 60
            )
            scroll.scroll_to(minute if is_day else (scene.minute if scene.today is not None else 8 * 60))

    def _waiting(self, scene: Scene) -> QFrame:
        waiting = scene.week.waiting
        tile, inner = self._tile(scene, "bentoWaiting", "Not placed yet")
        inner.addWidget(label("Drag one onto your day." if scene.surface == "day" else
                              "Drag one onto the week.", "bentoWaitingHint"))
        for index, item in enumerate(waiting):
            chip = TrayChip(self.hand, item)
            chip.setObjectName(f"bentoWaiting{index}")
            chip.setProperty("kind", "chip")
            chip.setToolTip(item.reason)
            chip.clicked.connect(lambda _=False, block_id=item.block_id: self.block_activated.emit(block_id))
            inner.addWidget(chip)
        if not waiting:
            inner.addWidget(label("Everything you added has a time.", "bentoWaitingEmpty"))
        inner.addStretch(1)
        actions = QHBoxLayout()
        for made in plan_buttons(self, "bento", "+ Add"):
            actions.addWidget(made)
        actions.addStretch(1)
        inner.addLayout(actions)
        return tile

    def _deadlines(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoDeadlines", "Deadlines")
        work = list(scene.week.open_work())
        seen = {item.block_id for item in work}
        waiting = [item for item in scene.week.waiting if item.block_id not in seen]
        for index, item in enumerate(work):
            words = f"{item.title}\n{due_label(item.due, scene.week.week_start)}"
            if item.slack_words:
                words += f" · {item.slack_words}"
            inner.addWidget(self._open_button(words, f"bentoDeadline{index}", item.block_id))
        for index, item in enumerate(waiting, start=len(work)):
            words = f"{item.title}\n{due_label(item.due, scene.week.week_start)} · Not placed yet"
            inner.addWidget(self._open_button(words, f"bentoDeadline{index}", item.block_id))
        if not work and not waiting:
            inner.addWidget(label("Nothing is due. Add homework when you get some.",
                                  "bentoDeadlinesEmpty", wrap=True))
        inner.addStretch(1)
        return tile

    def _tonight_and_deadlines(self, scene: Scene) -> QFrame:
        day = self.shown_day(scene)
        tile, inner = self._tile(
            scene, "bentoTonight", "Tonight" if day == scene.today else f"On {DAY_FULL[day]}"
        )
        sessions = scene.week.on_day(day)
        session = next((item for item in sessions if item.work and item.live and
                        (day != scene.today or item.end > scene.minute)), None)
        if session is not None:
            inner.addWidget(self._open_button(session.title, "bentoTonightTitle", session.block_id))
            inner.addWidget(label(f"{clock_label(session.start)} · {length_label(session.minutes)}",
                                  "bentoTonightLine"))
        else:
            words = "No homework tonight" if day == scene.today else "No homework this day"
            inner.addWidget(label(words, "bentoTonightTitle"))
        inner.addWidget(label("DEADLINES", "bentoTonightDeadlineTitle"))
        work = list(scene.week.open_work())
        seen = {item.block_id for item in work}
        due = [*work, *(item for item in scene.week.waiting if item.block_id not in seen)]
        for index, item in enumerate(due[:4]):
            inner.addWidget(self._open_button(
                f"{item.title} · {due_label(item.due, scene.week.week_start)}",
                f"bentoTonightDeadline{index}", item.block_id))
        if not due:
            inner.addWidget(label("Nothing due soon.", "bentoTonightDeadlineEmpty"))
        inner.addStretch(1)
        return tile

    def _open_button(self, words: str, name: str, block_id: str) -> QWidget:
        made = button(words, name, "row")
        made.setProperty("block_id", block_id)
        made.clicked.connect(lambda _=False: self.block_activated.emit(block_id))
        return made
