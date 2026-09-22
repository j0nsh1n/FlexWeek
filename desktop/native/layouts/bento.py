"""Bento: a main view. A home screen of tiles: what is next, deadlines, what has no time yet."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

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
    rules,
    scrolling,
)
from desktop.native.weekmodel import clock_label, due_label, length_label, planned_line

# The line under an empty Up next. With none, the card repeated its title: "No homework added" twice.
HERO_EMPTY_LINES = {
    "no_homework": "Add homework and FlexWeek will find it a time.",
    "all_finished": "Nothing else is due this week.",
    "calendar_only": "The rest of the day is yours.",
    "needs_time": "",
}


class BentoView(LayoutView):
    layout_id = "bento"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: int | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._board = QWidget()
        self._board.setObjectName("bentoBoard")
        self._grid = QGridLayout(self._board)
        self._scroll = scrolling(self._board, "bentoScroll")
        outer.addWidget(self._scroll)

    def shown_day(self, scene: Scene) -> int:
        return self._day if self._day is not None else (scene.today if scene.today is not None else 0)

    def _show_day(self, day: int) -> None:
        if self._scene is not None:
            self._day = None if day == self._scene.today else day
            self.render(self._scene, False)

    def _tile(self, scene: Scene, name: str, kicker: str) -> tuple[QFrame, QVBoxLayout]:
        tile = QFrame()
        tile.setObjectName(name)
        tile.setProperty("tile", "hero" if name == "bentoHero" else "plain")
        inner = QVBoxLayout(tile)
        inner.setContentsMargins(scene.px(18), scene.px(14), scene.px(18), scene.px(14))
        inner.setSpacing(scene.px(4))
        inner.addWidget(label(kicker.upper(), f"{name}Kicker"))
        return tile, inner

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._day = None
        tokens, name = scene.tokens, self.objectName()
        radius = scene.px(24 if scene.options.get("corners") != "square" else 6)
        kicker = css(
            color=tokens["accent"], font_size=f"{scene.px(12)}px", font_weight=700, letter_spacing="1px"
        )
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#bentoScroll, #bentoBoard": css(background=tokens["bg"]),
                    'QFrame[tile="plain"]': css(background=tokens["surface"], border_radius=f"{radius}px"),
                    'QFrame[tile="hero"]': css(background=tokens["accent"], border_radius=f"{radius}px"),
                    'QFrame[tile="plain"] QLabel': css(color=tokens["text"], font_size=f"{scene.px(14)}px"),
                    'QFrame[tile="hero"] QLabel': css(
                        color=tokens["accent_ink"], font_size=f"{scene.px(15)}px"
                    ),
                    'QFrame[tile="plain"] QLabel[role="kicker"]': kicker,
                    'QFrame[tile="plain"] QLabel[role="muted"]': css(color=tokens["muted"]),
                    'QFrame QLabel[role="big"]': css(font_size=f"{scene.px(34)}px", font_weight=800),
                    "#bentoHeroTitle": css(font_size=f"{scene.px(38)}px", font_weight=800),
                    "QPushButton": css(
                        background=tokens["cta"],
                        color=tokens["cta_ink"],
                        border="none",
                        border_radius=f"{scene.px(20)}px",
                        padding=f"0 {scene.px(18)}px",
                        min_height=f"{scene.px(40)}px",
                        font_size=f"{scene.px(14)}px",
                        font_weight=700,
                    ),
                    'QFrame[tile="hero"] QPushButton': css(
                        background=tokens["accent_ink"], color=tokens["accent"]
                    ),
                    'QPushButton[kind="row"], QPushButton[kind="bar"]': css(
                        background="transparent",
                        color=tokens["text"],
                        border="none",
                        border_bottom=f"1px solid {tokens['line']}",
                        border_radius="0",
                        text_align="left",
                        padding=f"{scene.px(6)}px 0",
                        font_weight=500,
                    ),
                    'QPushButton[kind="bar"]': css(
                        text_align="center", border_bottom="none", font_size=f"{scene.px(12)}px"
                    ),
                    'QPushButton[kind="bar"][chosen="true"]': css(font_weight=800, color=tokens["accent"]),
                    'QPushButton[kind="chip"]': css(
                        background=tokens["bg"],
                        color=tokens["text"],
                        border_radius=f"{scene.px(12)}px",
                        border_left=f"5px solid {tokens['line']}",
                        text_align="left",
                        padding=f"{scene.px(6)}px {scene.px(10)}px",
                        font_weight=500,
                    ),
                    'QPushButton[kind="chip"][state="past"]': css(
                        color=tokens["muted"], text_decoration="line-through"
                    ),
                    "QPushButton:focus": css(border=f"2px solid {tokens['text']}"),
                    'QFrame[role="bar"]': css(background=tokens["fill"], border_radius=f"{scene.px(6)}px"),
                    'QFrame[role="bar"][today="true"]': css(background=tokens["accent"]),
                },
            )
        )
        empty(self._grid)
        self._grid.setContentsMargins(scene.px(20), scene.px(16), scene.px(20), scene.px(16))
        self._grid.setSpacing(scene.px(14))
        everything = scene.options.get("tiles") != "essentials"
        if self.cramped:
            # Two columns rather than a sideways scroll to reach Add and Plan.
            self._narrow_board(scene, everything)
            return
        self._grid.addWidget(self._hero(scene), 0, 0, 2, 2)
        self._grid.addWidget(self._deadlines(scene), 0, 2, 2, 1)
        self._grid.addWidget(
            self._waiting(scene), 0 if not everything else 2, 3 if not everything else 0, 2, 1
        )
        if everything:
            self._grid.addWidget(self._tonight(scene), 0, 3)
            self._grid.addWidget(self._total(scene), 1, 3)
            self._grid.addWidget(self._load(scene), 2, 1, 1, 2)
            self._grid.addWidget(self._add(scene), 2, 3)
            self._grid.addWidget(self._strip(scene), 3, 1, 1, 3)
        else:
            self._grid.addWidget(self._strip(scene), 2, 0, 1, 4)
        for column in range(4):
            self._grid.setColumnStretch(column, 1)
        for index in range(self._grid.rowCount()):
            self._grid.setRowMinimumHeight(index, scene.px(128))
        for found in self._board.findChildren(type(label("", ""))):
            role = found.objectName()
            found.setProperty("role", "kicker" if role.endswith("Kicker") else found.property("role"))

    def _narrow_board(self, scene: Scene, everything: bool) -> None:
        """The same tiles in two columns, for a window too narrow for four."""
        tiles = [self._hero(scene), self._deadlines(scene), self._waiting(scene)]
        if everything:
            tiles += [self._tonight(scene), self._total(scene), self._load(scene), self._add(scene)]
        tiles.append(self._strip(scene))
        wide_names = {"bentoHero", "bentoStrip", "bentoLoad"}
        row, column = 0, 0
        for tile in tiles:
            if tile.objectName() in wide_names:
                if column:
                    row, column = row + 1, 0
                self._grid.addWidget(tile, row, 0, 1, 2)
                row += 1
                continue
            self._grid.addWidget(tile, row, column, 1, 1)
            column += 1
            if column == 2:
                row, column = row + 1, 0
        for index in range(2):
            self._grid.setColumnStretch(index, 1)
        for index in range(self._grid.rowCount()):
            self._grid.setRowMinimumHeight(index, scene.px(128))

    def _hero(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoHero", "Up next")
        inner.insertStretch(0, 1)
        queue = scene.week.day_queue(scene.today, scene.minute).queue if scene.today is not None else ()
        coming = [item for item in queue if item.start > scene.minute]
        kicker = tile.findChild(type(label("", "")), "bentoHeroKicker")
        if scene.today is None:
            kicker.setText("ANOTHER WEEK")
            inner.addWidget(label("Not this week", "bentoHeroTitle", wrap=True))
            inner.addWidget(
                label("Up next is about today, and today is in another week.", "bentoHeroLine", wrap=True)
            )
        elif coming:
            first = coming[0]
            kicker.setText(f"UP NEXT · IN {length_label(first.start - scene.minute).upper()}")
            inner.addWidget(label(first.title, "bentoHeroTitle", wrap=True))
            kind = category_title(first.category) if first.category else "Fixed time"
            inner.addWidget(
                label(f"{clock_label(first.start)}–{clock_label(first.end)} · {kind}", "bentoHeroLine")
            )
        else:
            _heading, title, line = scene.week.leftover_parts(scene.today)
            kind = scene.week.leftover_kind(scene.today)
            if kind == "needs_time":
                kicker.setText("DUE TODAY")
            inner.addWidget(label(title, "bentoHeroTitle", wrap=True))
            inner.addWidget(label(line or HERO_EMPTY_LINES[kind], "bentoHeroLine", wrap=True))
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
            inner.addWidget(block_button(self, words, f"bentoDeadline{index}", item.block_id, day=item.day))
        offset = len(work)
        for index, item in enumerate(waiting):
            words = f"{item.title}\n{due_label(item.due, scene.week.week_start)} · Not placed yet"
            inner.addWidget(block_button(self, words, f"bentoDeadline{offset + index}", item.block_id))
        if not work and not waiting:
            inner.addWidget(
                label("Nothing is due. Add homework when you get some.", "bentoDeadlinesEmpty", wrap=True)
            )
        inner.addStretch(1)
        return tile

    def _waiting(self, scene: Scene) -> QFrame:
        waiting = scene.week.waiting
        tile, inner = self._tile(
            scene, "bentoWaiting", f"Not placed yet ({len(waiting)})" if waiting else "Not placed yet"
        )
        for index, item in enumerate(waiting):
            words = f"{item.title} · {length_label(item.minutes)}\n{item.reason}"
            inner.addWidget(block_button(self, words, f"bentoWaiting{index}", item.block_id))
        if not waiting:
            inner.addWidget(label("Nothing waiting", "bentoWaitingEmpty"))
            note = label("Everything you added has a time.", "bentoWaitingNote", wrap=True)
            note.setProperty("role", "muted")
            inner.addWidget(note)
        actions = QHBoxLayout()
        if waiting:
            plan = button("Plan it" if len(waiting) == 1 else "Plan them", "bentoPlan")
            plan.clicked.connect(self.plan_requested.emit)
            actions.addWidget(plan)
        add = button("+ Add", "bentoAddSmall")
        add.clicked.connect(lambda _=False: self.add_requested.emit(""))
        actions.addWidget(add)
        actions.addStretch()
        inner.addLayout(actions)
        # The stretch belongs under the buttons, not between them and the text. Above them it left
        # a 165 pixel hole in a 297 pixel tile, worst on an empty week.
        inner.addStretch(1)
        return tile

    def _tonight(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoTonight", "Tonight")
        today = scene.week.on_day(scene.today) if scene.today is not None else ()
        session = next((item for item in today if item.work and item.live and item.end > scene.minute), None)
        if session is not None:
            inner.addWidget(
                block_button(self, session.title, "bentoTonightTitle", session.block_id, day=session.day)
            )
            note = label(
                f"{clock_label(session.start)} · {length_label(session.minutes)}", "bentoTonightLine"
            )
            note.setProperty("role", "muted")
            inner.addWidget(note)
            focus = button("Start focus", "bentoFocus")
            focus.clicked.connect(
                lambda _=False, entry=session: self.focus_requested.emit(entry.block_id, entry.day)
            )
            inner.addWidget(focus, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            due_today = scene.week.due_today_unplaced(scene.today)
            if due_today:
                item = due_today[0]
                inner.addWidget(block_button(self, item.title, "bentoTonightTitle", item.block_id))
                note = label(
                    "Not placed yet · due " + due_label(item.due, scene.week.week_start),
                    "bentoTonightLine",
                    wrap=True,
                )
                note.setProperty("role", "muted")
                inner.addWidget(note)
            else:
                inner.addWidget(label("No homework tonight", "bentoTonightTitle", wrap=True))
        inner.addStretch(1)
        return tile

    def _total(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoTotal", "Homework this week")
        work = [item for item in scene.week.occurrences if item.work]
        big = label(length_label(sum(item.minutes for item in work)), "bentoTotalBig")
        big.setProperty("role", "big")
        inner.addWidget(big)
        note = label(
            planned_line(
                sum(item.minutes for item in work),
                sum(item.minutes for item in work if item.done),
            ),
            "bentoTotalLine",
        )
        note.setProperty("role", "muted")
        inner.addWidget(note)
        inner.addStretch(1)
        return tile

    def _load(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoLoad", "Load by day, in minutes. Pick a day.")
        bars = QHBoxLayout()
        bars.setSpacing(scene.px(8))
        most = max([scene.week.load_min(day) for day in range(7)] + [1])
        shown = self.shown_day(scene)
        for day, name in enumerate(DAYS):
            holder = QFrame()
            holder.setObjectName(f"bentoLoadDay{day}")
            column = QVBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            column.addStretch(1)
            bar = QFrame()
            bar.setProperty("role", "bar")
            bar.setProperty("today", "true" if day == scene.today else "false")
            bar.setFixedHeight(max(round(scene.px(46) * scene.week.load_min(day) / most), scene.px(4)))
            column.addWidget(bar)
            pick = button(f"{name} {scene.week.load_min(day)}", f"bentoDay{day}", "bar")
            pick.setProperty("chosen", "true" if day == shown else "false")
            pick.setProperty("day_target", day)
            pick.setAccessibleName(f"Show {DAY_FULL[day]}, {scene.week.load_min(day)} minutes of homework")
            pick.clicked.connect(lambda _=False, target=day: self._show_day(target))
            column.addWidget(pick)
            bars.addWidget(holder)
        inner.addLayout(bars)
        return tile

    def _add(self, scene: Scene) -> QFrame:
        tile, inner = self._tile(scene, "bentoNew", "Something new?")
        inner.addWidget(label("Add homework", "bentoNewTitle"))
        add = button("+ Add", "bentoAdd")
        add.clicked.connect(lambda _=False: self.add_requested.emit(""))
        inner.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        inner.addStretch(1)
        return tile

    def _strip(self, scene: Scene) -> QFrame:
        day = self.shown_day(scene)
        date = scene.week.date_of(day)
        lead = "Today, " if day == scene.today else ""
        tile, inner = self._tile(scene, "bentoStrip", f"{lead}{DAY_FULL[day]} {date.day}")
        if scene.options.get("tiles") == "essentials":
            # The load chart is where a day is picked. Without it the rest of the week was out of reach.
            picker = QHBoxLayout()
            for target, name in enumerate(DAYS):
                pick = button(name, f"bentoDay{target}", "bar")
                pick.setProperty("chosen", "true" if target == day else "false")
                pick.setProperty("day_target", target)
                pick.setAccessibleName(f"Show {DAY_FULL[target]}")
                pick.clicked.connect(lambda _=False, chosen=target: self._show_day(chosen))
                picker.addWidget(pick)
            picker.addStretch(1)
            inner.addLayout(picker)
        strip = QFrame()
        strip.setObjectName("bentoStripRow")
        row = QHBoxLayout(strip)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(scene.px(8))
        blocks = scene.week.on_day(day)
        for index, item in enumerate(blocks):
            words = f"{clock_label(item.start)}\n{item.title}"
            chip = block_button(self, words, f"bentoChip{index}", item.block_id, "chip", day=item.day)
            over = (
                item.end <= scene.minute
                if day == scene.today
                else (scene.today is not None and day < scene.today)
            )
            chip.setProperty("state", "past" if over or not item.live else "")
            chip.setStyleSheet(f"border-left-color: {mark_of(item.category)};")
            row.addWidget(chip)
        if not blocks:
            row.addWidget(label("A free day.", "bentoStripEmpty"))
        row.addStretch(1)
        inner.addWidget(strip)
        return tile
