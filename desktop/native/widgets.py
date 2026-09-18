"""Native calendar and editors using the scheduler's existing data models."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4

from PySide6.QtCore import (
    QDate,
    QDateTime,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTime,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from backend.models import Assignment, TimeBlock, WeekRequest
from backend.slots import (
    DAY_END_MIN,
    DAY_START_MIN,
    SLOT_MIN,
    SLOTS_PER_DAY,
    duration_to_slots,
    hhmm_to_minutes,
    hhmm_to_slot,
    minutes_to_hhmm,
    slot_to_hhmm,
)
from desktop.native.calendar import (
    CATEGORIES,
    MONTH_SAVED_ONLY,
    create_click_range,
    create_drag_range,
    is_series,
    local_stamp,
    move_range,
    occupied_intervals,
    resize_bottom_range,
    resize_top_range,
)
from desktop.native.look import block_paint, resolved_palette
from desktop.native.reuse import (
    AVAILABILITY_LIMIT,
    LATE_MINUTES,
    PROTECTED_KINDS,
    preview_conflict_message,
    routine_source_blocks,
    row_conflict,
)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_FULL = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTH_FULL = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class FlowLayout(QLayout):
    """Left to right, wrapping onto new rows.

    The week page has about twenty actions. In a plain row their combined width became the window's
    minimum, over 2,300 pixels, which no laptop screen holds. Here the minimum is one button wide.
    """

    def __init__(self, parent: QWidget | None = None, gap: int = 6) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = gap

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 - Qt virtual
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt virtual
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt virtual
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 - Qt virtual
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt virtual
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt virtual
        return self._arrange(QRect(0, 0, width, 0), place=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt virtual
        super().setGeometry(rect)
        self._arrange(rect, place=True)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt virtual
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt virtual
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _arrange(self, rect: QRect, place: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if row_height and x + hint.width() > area.right() + 1:
                x = area.x()
                y += row_height + self._gap
                row_height = 0
            if place:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()


# What a table cell cannot draw for itself, carried on the item for BlockDelegate.
OUTLINE_ROLE = Qt.ItemDataRole.UserRole.value + 1
EDGE_ROLE = Qt.ItemDataRole.UserRole.value + 2
ENDS_ROLE = Qt.ItemDataRole.UserRole.value + 3


class BlockDelegate(QStyledItemDelegate):
    """Draws a block's outline or coloured edge over the cell, for the Blocks look knob."""

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().paint(painter, option, index)
        outline = index.data(OUTLINE_ROLE)
        edge = index.data(EDGE_ROLE)
        if not outline and not edge:
            return
        rect = option.rect
        painter.save()
        if outline:
            # A block is a run of cells, so only its first cell closes the top and its last the bottom.
            top, bottom = index.data(ENDS_ROLE) or (True, True)
            color = QColor(outline)
            painter.fillRect(rect.left(), rect.top(), 2, rect.height(), color)
            painter.fillRect(rect.right() - 1, rect.top(), 2, rect.height(), color)
            if top:
                painter.fillRect(rect.left(), rect.top(), rect.width(), 2, color)
            if bottom:
                painter.fillRect(rect.left(), rect.bottom() - 1, rect.width(), 2, color)
        if edge:
            painter.fillRect(rect.left(), rect.top(), 4, rect.height(), QColor(edge))
        painter.restore()


class WeekTable(QTableWidget):
    block_activated = Signal(str)
    slot_activated = Signal(int, str)
    range_created = Signal(int, int, int)
    times_changed = Signal(str, int, int)
    series_drag_refused = Signal(str, int)
    block_selected = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(SLOTS_PER_DAY, 7, parent)
        self.setObjectName("weekTable")
        self.setAccessibleName(
            "Weekly calendar. Drag empty time to add, or drag a block to move or resize it."
        )
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setDefaultSectionSize(32)
        self.setVerticalHeaderLabels([slot_to_hhmm(row) for row in range(SLOTS_PER_DAY)])
        self.setHorizontalHeaderLabels(DAYS)
        self.cellDoubleClicked.connect(self._activate)
        self._blocks: dict[str, dict] = {}
        self._week_blocks: list[dict] = []
        self._gesture: dict | None = None
        self._look: dict | None = None
        self._palette = resolved_palette("system", False, None)
        self._shown: tuple[str, list[dict], dict | None] | None = None
        self.setItemDelegate(BlockDelegate(self))

    def set_look(self, look: dict | None, palette: dict) -> None:
        """Repaint the week on screen with a new look; the blocks themselves do not change."""
        self._look = look
        self._palette = palette
        if self._shown is not None:
            self.set_week(*self._shown)

    def set_week(self, week_start: str, blocks: list[dict], trace: dict | None = None) -> None:
        monday = date.fromisoformat(week_start)
        self._shown = (week_start, blocks, trace)
        self._week_blocks = list(blocks)
        self._blocks = {block["id"]: block for block in blocks}
        self.clearContents()
        self.setHorizontalHeaderLabels(
            [
                f"{day} {(monday + timedelta(days=index)).strftime('%b %d')}"
                for index, day in enumerate(DAYS)
            ]
        )
        placed = {block["id"]: block for block in (trace or {}).get("placed", [])}
        cells: dict[tuple[int, int], list[tuple[dict, str, str]]] = {}
        spans: dict[tuple[int, int], tuple[int, int]] = {}
        for original in blocks:
            block = placed.get(original["id"], original) if not original.get("completed") else original
            if not block.get("start"):
                continue
            first = hhmm_to_slot(block["start"])
            size = duration_to_slots(block["duration_min"])
            days = block["days"]
            if block.get("completed") and block.get("completed_day") is not None:
                days = [block["completed_day"]]
            for day in days:
                label = "Fixed" if block["kind"] == "locked" else "Work"
                if day in original.get("missed_days", []):
                    label += " · Missed"
                if block.get("completed"):
                    label += " · Done"
                detail = f"{block['start']} · {label}"
                text = f"{block['title']}\n{detail}"
                last = min(first + size, SLOTS_PER_DAY) - 1
                for row in range(first, last + 1):
                    # A cell is one 15-minute row, too short for two lines. Qt elided the title to
                    # "School…" and dropped the second line, which is where Missed and Done are said.
                    # So the title takes the first row, the detail the second, and the rest stay blank.
                    if first == last:
                        visible = f"{block['title']} · {detail}"
                    elif row == first:
                        visible = block["title"]
                    else:
                        visible = detail if row == first + 1 else ""
                    cells.setdefault((row, day), []).append((block, text, visible))
                    spans.setdefault((row, day), (first, last))
        for (row, day), entries in cells.items():
            item = QTableWidgetItem(" / ".join(visible for _, _, visible in entries if visible))
            item.setData(Qt.ItemDataRole.UserRole, [block["id"] for block, _, _ in entries])
            item.setToolTip("\n".join(text for _, text, _ in entries))
            shown = entries[0][0]
            category = CATEGORIES.get(shown.get("category") or "", {})
            paint = block_paint(
                self._look, self._palette, category.get("color"), shown["kind"], category.get("mark")
            )
            item.setBackground(QColor(paint["fill"]))
            item.setForeground(QColor(paint["ink"]))
            item.setData(OUTLINE_ROLE, paint["outline"])
            item.setData(EDGE_ROLE, paint["edge"])
            first, last = spans[(row, day)]
            item.setData(ENDS_ROLE, (row == first, row == last))
            self.setItem(row, day, item)

    def block_titles(self, ids: list[str]) -> list[str]:
        """Names for the blocks sharing a cell, taken from the blocks: the cell's own text may be blank."""
        return [self._blocks.get(block_id, {}).get("title") or block_id for block_id in ids]

    def _activate(self, row: int, day: int) -> None:
        item = self.item(row, day)
        ids = item.data(Qt.ItemDataRole.UserRole) if item else []
        if len(ids) == 1:
            self.block_activated.emit(ids[0])
        elif ids:
            menu = QMenu(self)
            for block_id, title in zip(ids, self.block_titles(ids), strict=True):
                action = menu.addAction(title)
                action.triggered.connect(
                    lambda checked=False, value=block_id: self.block_activated.emit(value)
                )
            menu.exec(self.viewport().mapToGlobal(self.visualItemRect(item).center()))
        else:
            self.slot_activated.emit(day, slot_to_hhmm(row))

    def _row_at(self, pos_y: int) -> int:
        row = self.rowAt(pos_y)
        if row >= 0:
            return row
        if pos_y < self.rowViewportPosition(0):
            return 0
        return SLOTS_PER_DAY - 1

    def _edit_mode(self, block: dict, row: int) -> str:
        first = hhmm_to_slot(block["start"])
        last = first + duration_to_slots(block["duration_min"]) - 1
        if first == last:
            return "move"
        if row <= first:
            return "resize_top"
        if row >= last:
            return "resize_bottom"
        return "move"

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            super().mousePressEvent(event)
            return
        row, day = index.row(), index.column()
        item = self.item(row, day)
        ids = item.data(Qt.ItemDataRole.UserRole) if item else []
        press_min = DAY_START_MIN + row * SLOT_MIN
        if len(ids) == 1:
            block = self._blocks.get(ids[0])
            if block is None or not block.get("start"):
                super().mousePressEvent(event)
                return
            self.block_selected.emit(block["id"], day)
            if is_series(block):
                self.series_drag_refused.emit(block["id"], day)
                event.accept()
                return
            start_min = hhmm_to_minutes(block["start"])
            self._gesture = {
                "type": self._edit_mode(block, row),
                "day": day,
                "block_id": block["id"],
                "origin_start": start_min,
                "origin_end": start_min + block["duration_min"],
                "press_min": press_min,
                "moved": False,
            }
            event.accept()
            return
        if ids:
            self.block_selected.emit(ids[0], day)
            super().mousePressEvent(event)
            return
        self._gesture = {
            "type": "create",
            "day": day,
            "start_min": press_min,
            "cur_min": press_min,
            "moved": False,
        }
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        gesture = self._gesture
        if gesture is None:
            super().mouseMoveEvent(event)
            return
        row = self._row_at(int(event.position().y()))
        cur_min = DAY_START_MIN + row * SLOT_MIN
        if gesture["type"] == "create":
            gesture["cur_min"] = cur_min
            if abs(cur_min - gesture["start_min"]) >= SLOT_MIN:
                gesture["moved"] = True
            event.accept()
            return
        delta = cur_min - gesture["press_min"]
        if gesture["type"] == "move":
            span = move_range(gesture["origin_start"], gesture["origin_end"], delta)
        elif gesture["type"] == "resize_top":
            span = resize_top_range(gesture["origin_start"], gesture["origin_end"], delta)
        else:
            span = resize_bottom_range(gesture["origin_start"], gesture["origin_end"], delta)
        if span != (gesture["origin_start"], gesture["origin_end"]):
            gesture["moved"] = True
        gesture["preview"] = span
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        gesture = self._gesture
        self._gesture = None
        if gesture is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        if gesture["type"] == "create":
            if gesture["moved"]:
                span = create_drag_range(gesture["start_min"], gesture["cur_min"])
            else:
                span = create_click_range(
                    gesture["start_min"], occupied_intervals(self._week_blocks, gesture["day"])
                )
            if span is not None:
                self.range_created.emit(gesture["day"], span[0], span[1])
            event.accept()
            return
        if gesture.get("moved") and gesture.get("preview"):
            start_min, end_min = gesture["preview"]
            self.times_changed.emit(gesture["block_id"], start_min, end_min)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # mousePressEvent keeps a press on a block from Qt, so Qt never records the pressed cell and
        # would deliver this double-click as one more press. cellDoubleClicked then never fires.
        index = self.indexAt(event.position().toPoint())
        if event.button() != Qt.MouseButton.LeftButton or self.item(index.row(), index.column()) is None:
            super().mouseDoubleClickEvent(event)
            return
        self._gesture = None
        self._activate(index.row(), index.column())
        event.accept()


class CategoryChips(QWidget):
    category_chosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("categoryChips")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for key, info in CATEGORIES.items():
            button = QPushButton(info["label"])
            button.setObjectName(f"chip-{key}")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=key: self.category_chosen.emit(value))
            layout.addWidget(button)
        layout.addStretch()

    def set_armed(self, category: str) -> None:
        for key in CATEGORIES:
            button = self.findChild(QPushButton, f"chip-{key}")
            if button is not None:
                button.setChecked(key == category)


class DayAgenda(QWidget):
    item_activated = Signal(str)
    homework_activated = Signal(str)
    plan_requested = Signal()
    add_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dayAgenda")
        layout = QVBoxLayout(self)
        self.heading = QLabel()
        self.heading.setObjectName("dayTitle")
        layout.addWidget(self.heading)
        self.next_action = QPushButton()
        self.next_action.setObjectName("dayNextAction")
        self.next_action.clicked.connect(self._on_next)
        layout.addWidget(self.next_action)
        self.list = QListWidget()
        self.list.setObjectName("dayList")
        self.list.itemDoubleClicked.connect(self._on_item)
        layout.addWidget(self.list)
        self._next_kind = "add"

    def set_agenda(self, iso_day: str, agenda: dict, day_data: dict | None) -> None:
        day_index = agenda["day_index"]
        name = DAY_FULL[day_index] if 0 <= day_index <= 6 else iso_day
        self.heading.setText(date.fromisoformat(iso_day).strftime("%A, %b %d"))
        nxt = agenda["next_action"]
        self._next_kind = nxt["kind"]
        labels = {
            "add": "Add homework",
            "plan": "Plan my homework",
            "start": "Open the next session",
        }
        self.next_action.setText(labels[nxt["kind"]])
        self.list.clear()
        if not agenda["due_soon"] and not agenda["sessions"] and not agenda["fixed"]:
            empty = QListWidgetItem(f"Nothing is due soon and nothing is planned for {name}.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(empty)
            return
        load = (day_data or {}).get("workload") or {}
        if load:
            work = QListWidgetItem(
                f"Scheduled {load.get('scheduled_min', 0)} min · "
                f"{load.get('available_min', 0)} min free"
            )
            work.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(work)
        for item in agenda["due_soon"]:
            row = QListWidgetItem(f"Due {item['due']}: {item['title']}")
            row.setData(Qt.ItemDataRole.UserRole, {"kind": "homework", "id": item["id"]})
            self.list.addItem(row)
        for row in agenda["sessions"]:
            start = row["start"] or "unplanned"
            item = QListWidgetItem(f"{row['block']['title']} · {start}")
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "block", "id": row["block"]["id"]})
            self.list.addItem(item)
        for row in agenda["fixed"]:
            item = QListWidgetItem(f"{row['block']['title']} · {row['start']}")
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "block", "id": row["block"]["id"]})
            self.list.addItem(item)

    def _on_next(self) -> None:
        if self._next_kind == "plan":
            self.plan_requested.emit()
        elif self._next_kind == "add":
            self.add_requested.emit()
        else:
            for index in range(self.list.count()):
                candidate = self.list.item(index)
                data = candidate.data(Qt.ItemDataRole.UserRole) if candidate else None
                if data and data.get("kind") == "block":
                    self.item_activated.emit(data["id"])
                    return

    def _on_item(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") == "homework":
            self.homework_activated.emit(data["id"])
        elif data.get("kind") == "block":
            self.item_activated.emit(data["id"])


class MonthGrid(QWidget):
    day_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthPageInner")
        layout = QVBoxLayout(self)
        self.heading = QLabel()
        self.heading.setObjectName("monthTitle")
        layout.addWidget(self.heading)
        self.warning = QLabel()
        self.warning.setObjectName("monthSavedWarning")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        self.table = QTableWidget(5, 7)
        self.table.setObjectName("monthGrid")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.cellClicked.connect(self._activate)
        layout.addWidget(self.table)
        self.overdue = QLabel()
        self.overdue.setObjectName("monthOverdue")
        self.overdue.setWordWrap(True)
        layout.addWidget(self.overdue)
        self._palette = resolved_palette("system", False, None)
        self._shown: tuple[dict | None, bool] | None = None

    def set_palette(self, palette: dict) -> None:
        self._palette = palette
        if self._shown is not None:
            self.set_month(*self._shown)

    def set_month(self, snapshot: dict | None, dirty: bool) -> None:
        self._shown = (snapshot, dirty)
        if snapshot is None:
            self.heading.setText("Month")
            self.table.clearContents()
            self.warning.setText("Loading month…" if not dirty else MONTH_SAVED_ONLY)
            self.overdue.setText("")
            return
        year, month = (int(part) for part in snapshot["month"].split("-"))
        self.heading.setText(f"{MONTH_FULL[month - 1]} {year}")
        self.warning.setText(MONTH_SAVED_ONLY if dirty else "")
        days = snapshot.get("days") or []
        # The API sends whole weeks, four to six of them. Five fixed rows lost the last week of August.
        self.table.setRowCount((len(days) + 6) // 7)
        tallest = 1
        for index in range(self.table.rowCount() * 7):
            row, column = divmod(index, 7)
            if index >= len(days):
                self.table.setItem(row, column, QTableWidgetItem(""))
                continue
            cell = days[index]
            stamp = date.fromisoformat(cell["date"])
            lines = [str(stamp.day)]
            if cell.get("due_ids"):
                lines.append(f"{len(cell['due_ids'])} due")
            if cell.get("session_count"):
                lines.append(f"{cell['session_count']} sessions")
            if cell.get("locked_count"):
                lines.append(f"{cell['locked_count']} fixed")
            tallest = max(tallest, len(lines))
            item = QTableWidgetItem("\n".join(lines))
            item.setData(Qt.ItemDataRole.UserRole, cell["date"])
            if not cell.get("in_month"):
                item.setForeground(QColor(self._palette["muted"]))
            self.table.setItem(row, column, item)
        # Rows share the height on offer but never shrink below the busiest day, or Qt draws "14…"
        # where the counts should be. Past that the table scrolls.
        line = self.table.fontMetrics().lineSpacing()
        self.table.verticalHeader().setMinimumSectionSize(tallest * line + 8)
        overdue = snapshot.get("overdue") or []
        if overdue:
            titles = ", ".join(item.get("title") or item.get("id", "") for item in overdue[:8])
            self.overdue.setText("Overdue: " + titles)
        else:
            self.overdue.setText("")

    def _activate(self, row: int, column: int) -> None:
        item = self.table.item(row, column)
        iso_day = item.data(Qt.ItemDataRole.UserRole) if item else None
        if iso_day:
            self.day_activated.emit(iso_day)


def _line(name: str, text: str = "", limit: int = 80) -> QLineEdit:
    field = QLineEdit(text)
    field.setObjectName(name)
    field.setMaxLength(limit)
    return field


def _minutes(name: str, value: int, maximum: int) -> QSpinBox:
    field = QSpinBox()
    field.setObjectName(name)
    field.setRange(15, maximum)
    field.setSingleStep(15)
    field.setSuffix(" min")
    field.setValue(value)
    return field


def _error_label() -> QLabel:
    label = QLabel()
    label.setObjectName("validationError")
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setAccessibleName("Validation error")
    return label


def _buttons() -> QDialogButtonBox:
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.setObjectName("dialogButtons")
    return buttons


def _preset_locked(category: str | None, day: int, start: str, duration_min: int) -> dict:
    info = CATEGORIES.get(category or "")
    days = [day]
    title = ""
    chosen_start = start
    chosen_duration = duration_min
    if info is not None:
        title = info["label"]
        preset = info["preset"]
        if duration_min == 60 and start == "16:00" and "start" in preset:
            chosen_start = preset["start"]
            chosen_duration = hhmm_to_minutes(preset["end"]) - hhmm_to_minutes(preset["start"])
            days = list(preset.get("days") or [day])
        elif "start" not in preset:
            chosen_duration = preset.get("duration_min", duration_min)
    return {
        "id": str(uuid4()),
        "kind": "locked",
        "title": title,
        "days": days,
        "start": chosen_start,
        "duration_min": chosen_duration,
        "category": category,
    }


class BlockDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        block: dict | None = None,
        day: int = 0,
        start: str = "16:00",
        duration_min: int = 60,
        category: str | None = None,
        occurrence_day: int | None = None,
        from_range: bool = False,
    ) -> None:
        super().__init__(parent)
        if block is not None:
            self._original = deepcopy(block)
        elif from_range:
            info = CATEGORIES.get(category or "")
            self._original = {
                "id": str(uuid4()),
                "kind": "locked",
                "title": info["label"] if info else "",
                "days": [day],
                "start": start,
                "duration_min": duration_min,
                "category": category,
            }
        else:
            self._original = _preset_locked(category, day, start, duration_min)
        self._result: dict | None = None
        self._deleted = False
        self._occurrence_day = occurrence_day
        existing = block is not None
        series = existing and is_series(self._original)
        self.setWindowTitle("Edit fixed commitment" if existing else "Add fixed commitment")
        self.setObjectName("blockDialog")
        layout = QVBoxLayout(self)
        self.scope_occurrence = QRadioButton("This day only")
        self.scope_occurrence.setObjectName("scopeOccurrence")
        self.scope_series = QRadioButton("Every selected day")
        self.scope_series.setObjectName("scopeSeries")
        self.scope_series.setChecked(True)
        scope_row = QHBoxLayout()
        scope_row.addWidget(self.scope_occurrence)
        scope_row.addWidget(self.scope_series)
        scope_box = QWidget()
        scope_box.setObjectName("editScope")
        scope_box.setLayout(scope_row)
        scope_box.setVisible(bool(series and occurrence_day is not None))
        layout.addWidget(scope_box)
        note = QLabel("Changes apply to every selected day in this series.")
        note.setObjectName("seriesScope")
        note.setVisible(existing and len(self._original.get("days") or []) > 1 and not scope_box.isVisible())
        layout.addWidget(note)
        form = QFormLayout()
        layout.addLayout(form)
        self.title = _line("blockTitle", self._original["title"])
        form.addRow("Title", self.title)
        self.days = []
        choices = QHBoxLayout()
        for index, name in enumerate(DAYS):
            check = QCheckBox(name)
            check.setObjectName(f"blockDay{index}")
            check.setChecked(index in self._original["days"])
            choices.addWidget(check)
            self.days.append(check)
        form.addRow("Days", choices)
        self.scope_occurrence.toggled.connect(self._sync_scope)
        self.start = QTimeEdit(QTime.fromString(self._original.get("start") or start, "HH:mm"))
        self.start.setDisplayFormat("HH:mm")
        self.start.setObjectName("blockStart")
        form.addRow("Start", self.start)
        self.duration = _minutes("blockDuration", self._original["duration_min"], 1020)
        form.addRow("Duration", self.duration)
        self.category = QComboBox()
        self.category.setObjectName("blockCategory")
        self.category.addItem("None", None)
        for key, info in CATEGORIES.items():
            self.category.addItem(info["label"], key)
        chosen = self._original.get("category") or category
        if chosen and self.category.findData(chosen) < 0:
            self.category.addItem(chosen, chosen)
        self.category.setCurrentIndex(max(0, self.category.findData(chosen)))
        form.addRow("Category", self.category)
        self.missed = QCheckBox("This day was missed")
        self.missed.setObjectName("blockMissed")
        already = occurrence_day in (self._original.get("missed_days") or [])
        self.missed.setChecked(already)
        self.missed.setVisible(bool(existing and occurrence_day is not None))
        form.addRow("", self.missed)
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = _buttons()
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("deleteBlock")
        self.delete_button.setVisible(existing)
        self.delete_button.clicked.connect(self._delete)
        layout.addWidget(self.delete_button)
        self._sync_scope()

    def _sync_scope(self) -> None:
        occurrence = self.scope_occurrence.isChecked() and self._occurrence_day is not None
        for index, check in enumerate(self.days):
            if occurrence:
                check.setChecked(index == self._occurrence_day)
                check.setEnabled(False)
            else:
                check.setEnabled(True)

    def scope(self) -> str:
        if self.scope_occurrence.isChecked() and self._occurrence_day is not None:
            return "occurrence"
        return "series"

    def occurrence_day(self) -> int | None:
        return self._occurrence_day

    def deleted(self) -> bool:
        return self._deleted

    def recover_missed(self) -> bool:
        # The window asks after exec() returns. isVisible() is false for every child of a closed dialog,
        # so it made this box do nothing; isHidden() only says whether the box was ever offered.
        return (
            not self.missed.isHidden()
            and self.missed.isChecked()
            and self._occurrence_day is not None
            and self._occurrence_day not in (self._original.get("missed_days") or [])
        )

    def _delete(self) -> None:
        self._deleted = True
        super().accept()

    def accept(self) -> None:
        if self._deleted:
            super().accept()
            return
        candidate = deepcopy(self._original)
        chosen_days = [index for index, check in enumerate(self.days) if check.isChecked()]
        candidate.update(
            title=self.title.text().strip(),
            days=chosen_days,
            start=self.start.time().toString("HH:mm"),
            duration_min=self.duration.value(),
            category=self.category.currentData(),
        )
        # Unticking a day that was missed restores it, as the web's "Restore Wed" button does.
        unticked = not self.missed.isHidden() and not self.missed.isChecked()
        restored = self._occurrence_day if unticked else None
        candidate["missed_days"] = [
            day
            for day in candidate.get("missed_days", [])
            if day in candidate["days"] and day != restored
        ]
        try:
            if candidate["kind"] != "locked":
                raise ValueError("Use the homework editor for flexible work.")
            WeekRequest(blocks=[TimeBlock.model_validate(candidate)])
        except ValueError as error:
            self.error.setText(str(error))
            return
        self._result = candidate
        super().accept()

    def block(self) -> dict:
        return deepcopy(self._result if self._result is not None else self._original)


class HomeworkDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        assignment: dict | None = None,
        week_start: str = "2000-01-03",
        category: str | None = None,
        estimate_min: int | None = None,
        due: str | None = None,
    ) -> None:
        super().__init__(parent)
        info = CATEGORIES.get(category or "")
        self._original = deepcopy(assignment) if assignment is not None else {
            "id": str(uuid4()),
            "title": info["label"] if info else "",
            "due": due or week_start + "T21:00",
            "estimate_min": estimate_min
            or (info or {}).get("preset", {}).get("duration_min")
            or 60,
            "category": category,
            "revision": 0,
            "notes": "",
            "links": [],
            "checklist": [],
            "completed": False,
            "completed_at": None,
        }
        self._result: dict | None = None
        self._spread = False
        self.setWindowTitle("Edit homework" if assignment else "Add homework")
        self.setObjectName("homeworkDialog")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.title = _line("homeworkTitle", self._original["title"])
        form.addRow("Title", self.title)
        self.due = QDateTimeEdit(QDateTime.fromString(self._original["due"], "yyyy-MM-dd'T'HH:mm"))
        self.due.setObjectName("homeworkDue")
        self.due.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.due.setCalendarPopup(True)
        self.due.setMinimumDate(QDate(2000, 1, 1))
        self.due.setMaximumDate(QDate(2099, 12, 31))
        form.addRow("Due", self.due)
        self.estimate = _minutes("homeworkEstimate", self._original["estimate_min"], 7140)
        form.addRow("Estimated time", self.estimate)
        self.course = _line("homeworkCourse", self._original.get("course") or "", 40)
        form.addRow("Course", self.course)
        self.priority = QComboBox()
        self.priority.setObjectName("homeworkPriority")
        for value, label in enumerate(("Test", "Quiz", "Homework", "Reading"), 1):
            self.priority.addItem(label, value)
        self.priority.setCurrentIndex(self.priority.findData(self._original.get("priority", 3)))
        form.addRow("Priority", self.priority)
        self.energy = QComboBox()
        self.energy.setObjectName("homeworkEnergy")
        for value, label in (("high", "Morning"), ("medium", "Afternoon"), ("low", "Evening")):
            self.energy.addItem(label, value)
        self.energy.setCurrentIndex(self.energy.findData(self._original.get("energy", "medium")))
        form.addRow("Energy preference", self.energy)
        self.completed = QCheckBox("Finished")
        self.completed.setObjectName("homeworkCompleted")
        self.completed.setChecked(bool(self._original.get("completed")))
        form.addRow("", self.completed)
        self.notes = QPlainTextEdit(self._original.get("notes") or "")
        self.notes.setObjectName("homeworkNotes")
        self.notes.setPlaceholderText("Notes")
        layout.addWidget(self.notes)
        link_row = QHBoxLayout()
        self.link_label = _line("homeworkLinkLabel", "", 80)
        self.link_label.setPlaceholderText("Link label")
        self.link_url = _line("homeworkLinkUrl", "", 500)
        self.link_url.setPlaceholderText("https://")
        add_link = QPushButton("Add link")
        add_link.setObjectName("addHomeworkLink")
        add_link.clicked.connect(self._add_link)
        link_row.addWidget(self.link_label)
        link_row.addWidget(self.link_url)
        link_row.addWidget(add_link)
        layout.addLayout(link_row)
        self.links = QListWidget()
        self.links.setObjectName("homeworkLinks")
        layout.addWidget(self.links)
        for link in self._original.get("links") or []:
            self._append_link(link["label"], link["url"])
        check_row = QHBoxLayout()
        self.check_text = _line("homeworkCheckText", "", 80)
        self.check_text.setPlaceholderText("Checklist step")
        add_check = QPushButton("Add step")
        add_check.setObjectName("addHomeworkCheck")
        add_check.clicked.connect(self._add_check)
        check_row.addWidget(self.check_text)
        check_row.addWidget(add_check)
        layout.addLayout(check_row)
        self.checks = QListWidget()
        self.checks.setObjectName("homeworkChecklist")
        layout.addWidget(self.checks)
        for step in self._original.get("checklist") or []:
            self._append_check(step["id"], step["text"], step.get("done", False))
        self.error = _error_label()
        layout.addWidget(self.error)
        if assignment is not None:
            spread = QPushButton("Spread across days")
            spread.setObjectName("spreadHomework")
            spread.clicked.connect(self._request_spread)
            layout.addWidget(spread)
        buttons = _buttons()
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _request_spread(self) -> None:
        self._spread = True
        self._result = deepcopy(self._original)
        super().accept()

    def spread_requested(self) -> bool:
        return self._spread

    def _append_link(self, label: str, url: str) -> None:
        item = QListWidgetItem(f"{label} — {url}")
        item.setData(Qt.ItemDataRole.UserRole, {"label": label, "url": url})
        self.links.addItem(item)

    def _add_link(self) -> None:
        if self.links.count() >= 20:
            self.error.setText("Up to 20 links.")
            return
        label = self.link_label.text().strip()
        url = self.link_url.text().strip()
        if not label or not url:
            self.error.setText("A link needs a label and an http(s) address.")
            return
        self._append_link(label, url)
        self.link_label.clear()
        self.link_url.clear()
        self.error.setText("")

    def _append_check(self, item_id: str, text: str, done: bool) -> None:
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if done else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, item_id)
        self.checks.addItem(item)

    def _add_check(self) -> None:
        if self.checks.count() >= 40:
            self.error.setText("Up to 40 steps.")
            return
        text = self.check_text.text().strip()
        if not text:
            self.error.setText("A checklist step needs text.")
            return
        self._append_check(str(uuid4()), text, False)
        self.check_text.clear()
        self.error.setText("")

    def accept(self) -> None:
        candidate = deepcopy(self._original)
        links = [self.links.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.links.count())]
        checklist = []
        for index in range(self.checks.count()):
            item = self.checks.item(index)
            checklist.append(
                {
                    "id": item.data(Qt.ItemDataRole.UserRole),
                    "text": item.text(),
                    "done": item.checkState() == Qt.CheckState.Checked,
                }
            )
        completed = self.completed.isChecked()
        completed_at = candidate.get("completed_at") if completed else None
        if completed and not completed_at:
            completed_at = local_stamp()
        candidate.update(
            title=self.title.text().strip(),
            due=self.due.dateTime().toString("yyyy-MM-dd'T'HH:mm"),
            estimate_min=self.estimate.value(),
            course=self.course.text() or None,
            priority=self.priority.currentData(),
            energy=self.energy.currentData(),
            notes=self.notes.toPlainText(),
            links=links,
            checklist=checklist,
            completed=completed,
            completed_at=completed_at,
        )
        try:
            Assignment.model_validate(
                {key: value for key, value in candidate.items() if key in Assignment.model_fields}
            )
        except ValueError as error:
            self.error.setText(str(error))
            return
        self._result = candidate
        super().accept()

    def assignment(self) -> dict:
        return deepcopy(self._result if self._result is not None else self._original)


def _grid_starts() -> list[str]:
    return [minutes_to_hhmm(minute) for minute in range(DAY_START_MIN, DAY_END_MIN, SLOT_MIN)]


class PreviewDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        summary: str,
        rows: list[dict],
        existing: list[dict],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stage3PreviewDialog")
        self.setWindowTitle(title)
        self._rows = deepcopy(rows)
        self._existing = existing
        self._first = True
        self._rebuilding = False
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("stage3PreviewTitle")
        layout.addWidget(heading)
        note = QLabel(summary)
        note.setObjectName("stage3PreviewSummary")
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list = QWidget()
        self._list_layout = QVBoxLayout(self._list)
        scroll.setWidget(self._list)
        layout.addWidget(scroll)
        self.error = _error_label()
        self.error.setObjectName("stage3PreviewError")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.confirm = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.confirm.setObjectName("stage3PreviewConfirm")
        self.confirm.setText("Save preview")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def rows(self) -> list[dict]:
        return deepcopy(self._rows)

    def _refresh(self) -> None:
        self._rebuilding = True
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        selected = [row for row in self._rows if row.get("checked")]
        conflicted = False
        for index, row in enumerate(self._rows):
            conflict = row_conflict(row, self._rows, self._existing)
            if self._first and (conflict or row.get("invalid")):
                row["checked"] = False
            conflicted = conflicted or bool(row.get("checked") and (conflict or row.get("invalid")))
            self._list_layout.addWidget(self._row_widget(index, row, conflict))
        self._first = False
        self.confirm.setEnabled(bool(selected) and not conflicted)
        if conflicted:
            self.error.setText("Resolve conflicts or select at least one item before saving.")
        else:
            self.error.setText("")
        self._rebuilding = False

    def _row_widget(self, index: int, row: dict, conflict: str | None) -> QWidget:
        widget = QWidget()
        row_layout = QHBoxLayout(widget)
        include = QCheckBox(row["block"]["title"])
        include.setObjectName(f"previewInclude{index}")
        include.blockSignals(True)
        include.setChecked(bool(row.get("checked")))
        include.blockSignals(False)
        include.setEnabled(not row.get("invalid"))
        include.toggled.connect(lambda checked, pos=index: self._set_checked(pos, checked))
        row_layout.addWidget(include)
        if row.get("fixed"):
            day = QComboBox()
            day.setObjectName(f"previewDay{index}")
            for name in DAYS:
                day.addItem(name)
            day.setCurrentIndex(row["day"])
            day.currentIndexChanged.connect(lambda value, pos=index: self._set_day(pos, value))
            row_layout.addWidget(day)
            start = QComboBox()
            start.setObjectName(f"previewStart{index}")
            duration = int(row["block"]["duration_min"])
            last = DAY_END_MIN - duration
            for minute in range(DAY_START_MIN, last + 1, SLOT_MIN):
                label = minutes_to_hhmm(minute)
                start.addItem(label, label)
            current = row["block"].get("start") or minutes_to_hhmm(DAY_START_MIN)
            start.setCurrentText(current)
            row["block"]["start"] = start.currentText()
            start.currentTextChanged.connect(lambda value, pos=index: self._set_start(pos, value))
            row_layout.addWidget(start)
            length = QComboBox()
            length.setObjectName(f"previewDuration{index}")
            start_min = hhmm_to_minutes(row["block"]["start"])
            maximum = min(DAY_END_MIN - start_min, int(row.get("original_duration") or duration))
            for minutes in range(SLOT_MIN, maximum + 1, SLOT_MIN):
                length.addItem(str(minutes), minutes)
            length.setCurrentIndex(max(0, length.findData(min(duration, maximum))))
            length.currentIndexChanged.connect(
                lambda _i, box=length, pos=index: self._set_duration(pos, int(box.currentData()))
            )
            row_layout.addWidget(length)
        detail = QLabel(preview_conflict_message(row, self._rows, self._existing))
        detail.setObjectName(f"previewDetail{index}")
        detail.setWordWrap(True)
        row_layout.addWidget(detail, 1)
        return widget

    def _set_checked(self, index: int, checked: bool) -> None:
        if self._rebuilding:
            return
        self._rows[index]["checked"] = checked
        self._refresh()

    def _set_day(self, index: int, day: int) -> None:
        if self._rebuilding:
            return
        self._rows[index]["day"] = day
        self._rows[index]["block"]["days"] = [day]
        if not row_conflict(self._rows[index], self._rows, self._existing):
            self._rows[index]["checked"] = True
        self._refresh()

    def _set_start(self, index: int, start: str) -> None:
        if self._rebuilding:
            return
        self._rows[index]["block"]["start"] = start
        self._rows[index]["invalid"] = ""
        if not row_conflict(self._rows[index], self._rows, self._existing):
            self._rows[index]["checked"] = True
        self._refresh()

    def _set_duration(self, index: int, duration: int) -> None:
        if self._rebuilding:
            return
        self._rows[index]["block"]["duration_min"] = duration
        if not row_conflict(self._rows[index], self._rows, self._existing):
            self._rows[index]["checked"] = True
        self._refresh()


class UnfinishedPanel(QWidget):
    plan_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("unfinishedReview")
        layout = QVBoxLayout(self)
        heading = QLabel("Unfinished homework")
        layout.addWidget(heading)
        self.list = QListWidget()
        self.list.setObjectName("unfinishedList")
        layout.addWidget(self.list)
        dismiss = QPushButton("Hide")
        dismiss.setObjectName("unfinishedDismiss")
        dismiss.clicked.connect(self.hide)
        layout.addWidget(dismiss)
        self.hide()

    def set_items(self, items: list[dict]) -> None:
        self.list.clear()
        for item in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            text = QLabel(f"{item['title']} · {item['remaining_min']} min left")
            row_layout.addWidget(text, 1)
            button = QPushButton("Plan here")
            button.setObjectName(f"planUnfinished-{item['id']}")
            button.clicked.connect(
                lambda _checked=False, item_id=item["id"]: self.plan_requested.emit(item_id)
            )
            row_layout.addWidget(button)
            wrapper = QListWidgetItem()
            wrapper.setSizeHint(row.sizeHint())
            self.list.addItem(wrapper)
            self.list.setItemWidget(wrapper, row)
        self.setVisible(bool(items))


class RoutineDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        routines: dict[str, dict],
        blocks: list[dict],
        week_start: str,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("routineDialog")
        self.setWindowTitle("Routines")
        self._routines = routines
        self._blocks = routine_source_blocks(blocks)
        self._week_start = week_start
        self.action: str | None = None
        self.routine_id: str | None = None
        self.destination = week_start
        self.days = list(range(7))
        layout = QVBoxLayout(self)
        self.name = _line("routineName")
        self.name.setPlaceholderText("Routine name")
        layout.addWidget(self.name)
        self.choices = QListWidget()
        self.choices.setObjectName("routineBlocks")
        layout.addWidget(self.choices)
        for block in self._blocks:
            item = QListWidgetItem(
                f"{block['title']} · {', '.join(DAYS[day] for day in block['days'])} · {block['start']}"
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, block["id"])
            self.choices.addItem(item)
        save = QPushButton("Save this week as a routine")
        save.setObjectName("saveRoutine")
        save.clicked.connect(self._save)
        layout.addWidget(save)
        self.list = QListWidget()
        self.list.setObjectName("routineList")
        layout.addWidget(self.list)
        for routine in routines.values():
            item = QListWidgetItem(
                f"{routine['name']} · {len(routine.get('blocks') or [])} fixed times"
            )
            item.setData(Qt.ItemDataRole.UserRole, routine["id"])
            self.list.addItem(item)
        dest = QLineEdit(week_start)
        dest.setObjectName("routineDestination")
        dest.setMaxLength(10)
        layout.addWidget(dest)
        self._dest = dest
        days_row = QHBoxLayout()
        self._days = []
        for index, name in enumerate(DAYS):
            check = QCheckBox(name)
            check.setObjectName(f"routineDay{index}")
            check.setChecked(True)
            days_row.addWidget(check)
            self._days.append(check)
        layout.addLayout(days_row)
        actions = QHBoxLayout()
        apply = QPushButton("Apply")
        apply.setObjectName("applyRoutine")
        apply.clicked.connect(self._apply)
        delete = QPushButton("Delete")
        delete.setObjectName("deleteRoutine")
        delete.clicked.connect(self._delete)
        actions.addWidget(apply)
        actions.addWidget(delete)
        layout.addLayout(actions)
        self.error = _error_label()
        layout.addWidget(self.error)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        layout.addWidget(close)

    def selected_block_ids(self) -> list[str]:
        ids = []
        for index in range(self.choices.count()):
            item = self.choices.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def selected_days(self) -> list[int]:
        return [index for index, check in enumerate(self._days) if check.isChecked()]

    def _save(self) -> None:
        self.action = "save"
        super().accept()

    def _apply(self) -> None:
        item = self.list.currentItem()
        if item is None:
            self.error.setText("Choose a saved routine.")
            return
        days = self.selected_days()
        if not days:
            self.error.setText("Choose at least one weekday to copy.")
            return
        self.action = "apply"
        self.routine_id = item.data(Qt.ItemDataRole.UserRole)
        self.destination = self._dest.text().strip()
        self.days = days
        super().accept()

    def _delete(self) -> None:
        item = self.list.currentItem()
        if item is None:
            self.error.setText("Choose a saved routine.")
            return
        self.action = "delete"
        self.routine_id = item.data(Qt.ItemDataRole.UserRole)
        super().accept()


class LateDialog(QDialog):
    preview_requested = Signal()

    def __init__(self, parent: QWidget | None, context: str) -> None:
        super().__init__(parent)
        self.setObjectName("lateDialog")
        self.setWindowTitle("Running late")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(context))
        self.minutes = QComboBox()
        self.minutes.setObjectName("lateMinutes")
        for value in LATE_MINUTES:
            self.minutes.addItem(f"{value} minutes", value)
        self.minutes.setCurrentIndex(1)
        layout.addWidget(self.minutes)
        self.summary = QLabel()
        self.summary.setObjectName("lateSummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.changes = QListWidget()
        self.changes.setObjectName("lateChanges")
        layout.addWidget(self.changes)
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        preview = QPushButton("Preview")
        preview.setObjectName("latePreview")
        preview.clicked.connect(self.preview_requested.emit)
        self.accept_button = QPushButton("Accept late start")
        self.accept_button.setObjectName("lateAccept")
        self.accept_button.setEnabled(False)
        self.accept_button.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(preview)
        buttons.addWidget(self.accept_button)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def chosen_minutes(self) -> int:
        return int(self.minutes.currentData())

    def show_trace(self, trace: dict, titles: dict[str, str]) -> None:
        self.changes.clear()
        for move in trace.get("moves") or []:
            self.changes.addItem(
                f"{titles.get(move['block_id'], move['block_id'])}: "
                f"{move.get('from_start') or 'unscheduled'} → {move.get('to_start') or 'unscheduled'}"
            )
        for block in trace.get("unplaced") or []:
            self.changes.addItem(block["title"] + " no longer fits and will stay on the task list.")
        if self.changes.count() == 0:
            self.changes.addItem("No homework needs to move.")
        moved = len(trace.get("moves") or [])
        unplaced = len(trace.get("unplaced") or [])
        self.summary.setText(f"{moved} tasks move · {unplaced} tasks no longer fit")
        self.accept_button.setEnabled(True)
        self.minutes.setEnabled(False)


class SpreadDialog(QDialog):
    def __init__(self, parent: QWidget | None, assignment: dict, from_date: str) -> None:
        super().__init__(parent)
        self.setObjectName("spreadDialog")
        self.setWindowTitle("Spread " + assignment["title"])
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{assignment['estimate_min']} minutes total · due {assignment['due']}"
            )
        )
        self.session = QComboBox()
        self.session.setObjectName("spreadSession")
        remaining = max(SLOT_MIN, int(assignment.get("unplanned_min") or SLOT_MIN))
        chosen = min(60, remaining - remaining % SLOT_MIN, 180)
        for minutes in range(SLOT_MIN, 181, SLOT_MIN):
            self.session.addItem(f"{minutes} minutes", minutes)
        self.session.setCurrentIndex(max(0, self.session.findData(chosen)))
        layout.addWidget(self.session)
        self.from_date = QDateEdit(QDate.fromString(from_date, "yyyy-MM-dd"))
        self.from_date.setObjectName("spreadFrom")
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setCalendarPopup(True)
        self.from_date.setMaximumDate(QDate.fromString(assignment["due"][:10], "yyyy-MM-dd"))
        layout.addWidget(self.from_date)
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = _buttons()
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Preview sessions")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def session_min(self) -> int:
        return int(self.session.currentData())

    def from_iso(self) -> str:
        return self.from_date.date().toString("yyyy-MM-dd")


class AvailabilityDialog(QDialog):
    def __init__(self, parent: QWidget | None, preferences: dict) -> None:
        super().__init__(parent)
        self.setObjectName("availabilityDialog")
        self.setWindowTitle("Availability")
        self._protected = deepcopy(preferences.get("protected") or [])
        self._study = deepcopy(preferences.get("study_windows") or [])
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Protected time"))
        self.protected_list = QListWidget()
        self.protected_list.setObjectName("protectedWindows")
        layout.addWidget(self.protected_list)
        add_protected = QPushButton("Add protected time")
        add_protected.setObjectName("protectedAdd")
        add_protected.clicked.connect(self._add_protected)
        layout.addWidget(add_protected)
        layout.addWidget(QLabel("Preferred study hours"))
        self.study_list = QListWidget()
        self.study_list.setObjectName("studyWindows")
        layout.addWidget(self.study_list)
        add_study = QPushButton("Add study window")
        add_study.setObjectName("studyAdd")
        add_study.clicked.connect(self._add_study)
        layout.addWidget(add_study)
        self.cutoff = QComboBox()
        self.cutoff.setObjectName("availabilityCutoff")
        self.cutoff.addItem("No cutoff", None)
        for start in _grid_starts():
            if start < "06:15":
                continue
            self.cutoff.addItem(start, start)
        current = preferences.get("day_cutoff")
        self.cutoff.setCurrentIndex(max(0, self.cutoff.findData(current)))
        layout.addWidget(self.cutoff)
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = _buttons()
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._render()

    def _render(self) -> None:
        self.protected_list.clear()
        for window in self._protected:
            item = QListWidgetItem(
                f"{window.get('kind')} · {window['start']} · {window['duration_min']}m · "
                + ",".join(DAYS[day] for day in window["days"])
            )
            self.protected_list.addItem(item)
        self.study_list.clear()
        for window in self._study:
            item = QListWidgetItem(
                f"{window['start']} · {window['duration_min']}m · "
                + ",".join(DAYS[day] for day in window["days"])
            )
            self.study_list.addItem(item)

    def _add_protected(self) -> None:
        if len(self._protected) >= AVAILABILITY_LIMIT:
            self.error.setText("Up to 21 protected windows.")
            return
        self._protected.append(
            {"kind": PROTECTED_KINDS[0], "days": [0, 1, 2, 3, 4], "start": "18:00", "duration_min": 60}
        )
        self._render()

    def _add_study(self) -> None:
        if len(self._study) >= AVAILABILITY_LIMIT:
            self.error.setText("Up to 21 study windows.")
            return
        self._study.append({"days": [0, 1, 2, 3, 4], "start": "19:00", "duration_min": 120})
        self._render()

    def protected(self) -> list[dict]:
        return deepcopy(self._protected)

    def study_windows(self) -> list[dict]:
        return deepcopy(self._study)

    def day_cutoff(self) -> str | None:
        return self.cutoff.currentData()
