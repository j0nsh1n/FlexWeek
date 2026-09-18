"""Native calendar and editors using the scheduler's existing data models."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4

from PySide6.QtCore import QDate, QDateTime, Qt, QTime, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from backend.models import Assignment, TimeBlock, WeekRequest
from backend.slots import (
    SLOTS_PER_DAY,
    duration_to_slots,
    hhmm_to_slot,
    slot_to_hhmm,
)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CATEGORIES = {
    "class": ("School", "#bfdbfe"),
    "assignments": ("Homework", "#fecaca"),
    "study": ("Study", "#ddd6fe"),
    "exercise": ("Sports", "#a7f3d0"),
    "extra": ("Activity", "#fbcfe8"),
    "meals": ("Meals", "#fed7aa"),
    "sleep": ("Sleep", "#c7d2fe"),
    "free": ("Free", "#e2e8f0"),
}


class WeekTable(QTableWidget):
    block_activated = Signal(str)
    slot_activated = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(SLOTS_PER_DAY, 7, parent)
        self.setObjectName("weekTable")
        self.setAccessibleName("Weekly calendar. Double-click a block to edit or an empty time to add.")
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setDefaultSectionSize(32)
        self.setVerticalHeaderLabels([slot_to_hhmm(row) for row in range(SLOTS_PER_DAY)])
        self.setHorizontalHeaderLabels(DAYS)
        self.cellDoubleClicked.connect(self._activate)

    def set_week(self, week_start: str, blocks: list[dict], trace: dict | None = None) -> None:
        monday = date.fromisoformat(week_start)
        self.clearContents()
        self.setHorizontalHeaderLabels([
            f"{day} {(monday + timedelta(days=index)).strftime('%b %d')}"
            for index, day in enumerate(DAYS)
        ])
        placed = {block["id"]: block for block in (trace or {}).get("placed", [])}
        cells: dict[tuple[int, int], list[tuple[dict, str]]] = {}
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
                text = f"{block['title']}\n{block['start']} · {label}"
                for row in range(first, min(first + size, SLOTS_PER_DAY)):
                    cells.setdefault((row, day), []).append((block, text))
        for (row, day), entries in cells.items():
            item = QTableWidgetItem("\n".join(text for _, text in entries))
            item.setData(Qt.ItemDataRole.UserRole, [block["id"] for block, _ in entries])
            item.setToolTip(item.text())
            color = CATEGORIES.get(entries[0][0].get("category"), ("", "#e2e8f0"))[1]
            item.setBackground(QColor(color))
            item.setForeground(QColor("#172033"))
            self.setItem(row, day, item)

    def _activate(self, row: int, day: int) -> None:
        item = self.item(row, day)
        ids = item.data(Qt.ItemDataRole.UserRole) if item else []
        if len(ids) == 1:
            self.block_activated.emit(ids[0])
        elif ids:
            menu = QMenu(self)
            texts = item.text().splitlines()
            for index, block_id in enumerate(ids):
                action = menu.addAction(texts[index * 2])
                action.triggered.connect(
                    lambda checked=False, value=block_id: self.block_activated.emit(value)
                )
            menu.exec(self.viewport().mapToGlobal(self.visualItemRect(item).center()))
        else:
            self.slot_activated.emit(day, slot_to_hhmm(row))


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


class BlockDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, block: dict | None = None,
        day: int = 0, start: str = "16:00",
    ) -> None:
        super().__init__(parent)
        self._original = deepcopy(block) if block is not None else {
            "id": str(uuid4()), "kind": "locked", "title": "", "days": [day],
            "start": start, "duration_min": 60,
        }
        self._result: dict | None = None
        self.setWindowTitle("Edit fixed commitment" if block else "Add fixed commitment")
        self.setObjectName("blockDialog")
        layout = QVBoxLayout(self)
        scope = QLabel("Changes apply to every selected day in this series.")
        scope.setObjectName("seriesScope")
        layout.addWidget(scope)
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
        self.start = QTimeEdit(QTime.fromString(self._original.get("start") or start, "HH:mm"))
        self.start.setDisplayFormat("HH:mm")
        self.start.setObjectName("blockStart")
        form.addRow("Start", self.start)
        self.duration = _minutes("blockDuration", self._original["duration_min"], 1020)
        form.addRow("Duration", self.duration)
        self.category = QComboBox()
        self.category.setObjectName("blockCategory")
        self.category.addItem("None", None)
        for key, (label, _) in CATEGORIES.items():
            self.category.addItem(label, key)
        category = self._original.get("category")
        if category and self.category.findData(category) < 0:
            self.category.addItem(category, category)
        self.category.setCurrentIndex(max(0, self.category.findData(category)))
        form.addRow("Category", self.category)
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("dialogButtons")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        candidate = deepcopy(self._original)
        chosen_days = [index for index, check in enumerate(self.days) if check.isChecked()]
        candidate.update(
            title=self.title.text().strip(),
            days=chosen_days,
            start=self.start.time().toString("HH:mm"),
            duration_min=self.duration.value(),
            category=self.category.currentData(),
        )
        candidate["missed_days"] = [
            day for day in candidate.get("missed_days", []) if day in candidate["days"]
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
        self, parent: QWidget | None = None, assignment: dict | None = None,
        week_start: str = "2000-01-03",
    ) -> None:
        super().__init__(parent)
        self._original = deepcopy(assignment) if assignment is not None else {
            "id": str(uuid4()), "title": "", "due": week_start + "T21:00",
            "estimate_min": 60, "revision": 0,
        }
        self._result: dict | None = None
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
        self.error = _error_label()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("dialogButtons")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        candidate = deepcopy(self._original)
        candidate.update(
            title=self.title.text().strip(), due=self.due.dateTime().toString("yyyy-MM-dd'T'HH:mm"),
            estimate_min=self.estimate.value(), course=self.course.text() or None,
            priority=self.priority.currentData(), energy=self.energy.currentData(),
        )
        try:
            Assignment.model_validate({
                key: value for key, value in candidate.items() if key in Assignment.model_fields
            })
        except ValueError as error:
            self.error.setText(str(error))
            return
        self._result = candidate
        super().accept()

    def assignment(self) -> dict:
        return deepcopy(self._result if self._result is not None else self._original)
