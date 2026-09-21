"""Timeline: a main view. One day as a column of cards, the week shrunk to a strip above it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL, DAYS, category_title
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    block_button,
    button,
    css,
    empty,
    label,
    mark_of,
    plan_buttons,
    plural,
    rules,
    scrolling,
)
from desktop.native.weekmodel import Occurrence, clock_label, due_label, length_label


class TimelineView(LayoutView):
    layout_id = "timeline"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: int | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._page = QWidget()
        self._page.setObjectName("timelinePage")
        centred = QHBoxLayout(self._page)
        self._column = QVBoxLayout()
        centred.addStretch(1)
        centred.addLayout(self._column, 4)
        centred.addStretch(1)
        outer.addWidget(scrolling(self._page, "timelineScroll"))

    def shown_day(self, scene: Scene) -> int:
        return self._day if self._day is not None else (scene.today if scene.today is not None else 0)

    def _show_day(self, day: int) -> None:
        if self._scene is not None:
            self._day = None if day == self._scene.today else day
            self.render(self._scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._day = None
        tokens, name = scene.tokens, self.objectName()
        compact = scene.options.get("density") == "compact"
        pad = scene.px(6 if compact else 12)
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#timelineScroll, #timelinePage": css(background=tokens["bg"]),
                    "#timelineDay": css(font_size=f"{scene.px(30 if compact else 42)}px", font_weight=800),
                    "#timelineSub, #timelineNow": css(
                        color=tokens["bg_muted"], font_size=f"{scene.px(14)}px"
                    ),
                    "#timelineNow": css(color=tokens["danger"], font_weight=800, letter_spacing="1px"),
                    "#timelineInbox": css(
                        background=tokens["surface"],
                        border=f"2px dashed {tokens['line']}",
                        border_radius=f"{scene.px(14)}px",
                    ),
                    "#timelineInbox QLabel": css(color=tokens["text"], font_weight=700),
                    "QPushButton": css(
                        background=tokens["surface"],
                        color=tokens["text"],
                        border=f"2px solid {tokens['text']}",
                        border_radius=f"{scene.px(12)}px",
                        padding=f"0 {scene.px(16)}px",
                        min_height=f"{scene.px(44)}px",
                        font_size=f"{scene.px(14)}px",
                        font_weight=600,
                    ),
                    'QPushButton[kind="main"]': css(background=tokens["accent"], color=tokens["accent_ink"]),
                    'QPushButton[kind="day"]': css(
                        border=f"2px solid {tokens['line']}",
                        padding=f"{scene.px(4)}px",
                        min_height=f"{scene.px(30)}px",
                        font_size=f"{scene.px(12)}px",
                    ),
                    'QPushButton[kind="day"][chosen="true"]': css(
                        border=f"2px solid {tokens['text']}", font_weight=800
                    ),
                    'QPushButton[kind="row"]': css(
                        border="none",
                        border_left=f"5px solid {tokens['line']}",
                        text_align="left",
                        padding=f"{pad}px {scene.px(14)}px",
                        font_weight=500,
                    ),
                    'QPushButton[kind="row"][state="next"]': css(
                        background=tokens["accent"], color=tokens["accent_ink"], font_weight=800
                    ),
                    'QPushButton[kind="row"][state="past"]': css(
                        color=tokens["muted"], text_decoration="line-through"
                    ),
                    "QPushButton:focus": css(border=f"3px solid {tokens['danger']}"),
                    'QFrame[role="track"]': css(background=tokens["line"], border_radius="3px"),
                    'QFrame[role="load"]': css(background=tokens["text"], border_radius="3px"),
                },
            )
        )
        empty(self._column)
        self._column.setSpacing(scene.px(6 if compact else 10))
        day = self.shown_day(scene)
        is_today = day == scene.today
        blocks = scene.week.on_day(day)
        sessions = sum(1 for item in blocks if item.work and item.live)
        date = scene.week.date_of(day)
        self._column.addWidget(label(DAY_FULL[day], "timelineDay"))
        waiting = scene.week.waiting
        self._column.addWidget(
            label(
                f"{date.strftime('%B')} {date.day} · {plural(sessions, 'homework session')}"
                f" · {len(waiting)} not placed yet",
                "timelineSub",
            )
        )
        actions = QHBoxLayout()
        for made in plan_buttons(self, "timeline", "+ Add homework"):
            actions.addWidget(made)
        actions.addStretch(1)
        self._column.addLayout(actions)
        self._column.addLayout(self._strip(scene, day))
        if waiting:
            self._column.addWidget(self._inbox(scene))
        queue = scene.week.day_queue(day, scene.minute) if is_today else None
        upcoming = next((item for item in (queue.queue if queue else ()) if item.start > scene.minute), None)
        for index, item in enumerate(blocks):
            past = not item.live or (item.end <= scene.minute if is_today else self._before_today(scene, day))
            if past and scene.options.get("finished") == "hide":
                continue
            if item == upcoming:
                self._column.addWidget(label(f"NOW {clock_label(scene.minute)}", "timelineNow"))
            self._column.addWidget(self._card(scene, item, index, past, item == upcoming, is_today))
        if not blocks:
            self._column.addWidget(label("A free day.", "timelineSub"))
        elif is_today and upcoming is None:
            self._column.addWidget(
                label(f"NOW {clock_label(scene.minute)} · NOTHING ELSE TODAY", "timelineNow")
            )
        self._column.addStretch(1)

    @staticmethod
    def _before_today(scene: Scene, day: int) -> bool:
        return scene.today is not None and day < scene.today

    def _strip(self, scene: Scene, shown: int) -> QHBoxLayout:
        strip = QHBoxLayout()
        strip.setSpacing(scene.px(6))
        most = max([scene.week.load_min(day) for day in range(7)] + [1])
        for day, name in enumerate(DAYS):
            cell = QVBoxLayout()
            cell.setSpacing(2)
            pick = button(f"{name} {scene.week.date_of(day).day}", f"timelineDay{day}", "day")
            pick.setProperty("chosen", "true" if day == shown else "false")
            pick.setProperty("day_target", day)
            pick.setAccessibleName(f"Show {DAY_FULL[day]}, {scene.week.load_min(day)} minutes of homework")
            pick.clicked.connect(lambda _=False, target=day: self._show_day(target))
            cell.addWidget(pick)
            if scene.options.get("strip") != "names":
                # A bare 4px stub under each button read as debris. The bar now sits in a track of
                # its own, so a light day is a short bar in a slot rather than a stray mark.
                track = QFrame()
                track.setProperty("role", "track")
                track.setFixedHeight(scene.px(6))
                inside = QHBoxLayout(track)
                inside.setContentsMargins(0, 0, 0, 0)
                inside.setSpacing(0)
                bar = QFrame()
                bar.setProperty("role", "load")
                share = scene.week.load_min(day) / most
                inside.addWidget(bar, max(round(share * 100), 3))
                inside.addStretch(max(round((1 - share) * 100), 0))
                cell.addWidget(track)
            strip.addLayout(cell)
        return strip

    def _inbox(self, scene: Scene) -> QFrame:
        inbox = QFrame()
        inbox.setObjectName("timelineInbox")
        inner = QVBoxLayout(inbox)
        inner.setContentsMargins(scene.px(14), scene.px(10), scene.px(14), scene.px(12))
        inner.addWidget(label("Not placed yet", "timelineInboxTitle"))
        for index, item in enumerate(scene.week.waiting):
            due = due_label(item.due, scene.week.week_start)
            words = f"{item.title}\n{length_label(item.minutes)} · due {due} · {item.reason}"
            inner.addWidget(block_button(self, words, f"timelineWaiting{index}", item.block_id))
        plan = button("Plan it" if len(scene.week.waiting) == 1 else "Plan them", "timelineInboxPlan", "main")
        plan.clicked.connect(self.plan_requested.emit)
        inner.addWidget(plan, 0, Qt.AlignmentFlag.AlignLeft)
        return inbox

    def _card(
        self, scene: Scene, item: Occurrence, index: int, past: bool, upcoming: bool, is_today: bool
    ) -> QWidget:
        kind = category_title(item.category) if item.category else "Fixed time"
        detail = f"{length_label(item.minutes)} · {kind}"
        if item.due:
            detail += f" · due {due_label(item.due, scene.week.week_start)}"
        if item.slack_words:
            detail += f" · {item.slack_words}"
        if is_today and item.start <= scene.minute < item.end:
            detail += " · happening now"
        lead = f"UP NEXT · IN {length_label(item.start - scene.minute).upper()}\n" if upcoming else ""
        card = block_button(
            self,
            f"{lead}{clock_label(item.start)}   {item.title}\n{detail}",
            f"timelineRow{index}",
            item.block_id,
        )
        card.setProperty("state", "next" if upcoming else "past" if past else "")
        # A button sizes itself for two lines here, and the up-next card has three: it lost the first and
        # last. The height goes through the stylesheet because its min-height beats setMinimumHeight.
        lines = card.text().count("\n") + 1
        sheet = f"min-height: {scene.px(21) * lines}px;"
        if not upcoming:
            sheet += f" border-left-color: {mark_of(item.category)};"
        card.setStyleSheet(sheet)
        if upcoming and item.work:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            focus = button("Start focus", "timelineFocus")
            focus.clicked.connect(
                lambda _=False, entry=item: self.focus_requested.emit(entry.block_id, entry.day)
            )
            row.addWidget(card, 1)
            row.addWidget(focus)
            return holder
        return card
