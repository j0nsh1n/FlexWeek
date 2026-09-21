"""Main view and Day screen pickers, built from the registry so a new design needs no code here.

A design's Style options stay in view under the pick. Fine-tune waits behind one checkbox so the
first look stays short.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.native.layouts.base import empty
from desktop.native.layouts.registry import LAYOUTS, LEVELS, layouts_for, options_for

SLOTS = (
    ("main", "plan", "Main view", "Where you plan your week."),
    ("day", "day", "Day screen", "What you watch once the plan is made. Open it with My day."),
)


class LayoutSection(QGroupBox):
    """One pick and the options of whatever is picked. Each design keeps its own settings while the
    dialog is open, so trying another design and coming back loses nothing."""

    def __init__(self, slot: str, role: str, title: str, blurb: str, choice: dict) -> None:
        super().__init__(title)
        self.slot = slot
        self.setObjectName(f"layout{slot.title()}Section")
        self._options = {spec.id: options_for(choice, spec.id) for spec in layouts_for(role)}
        body = QVBoxLayout(self)
        body.addWidget(QLabel(blurb))
        self.pick = QComboBox()
        self.pick.setObjectName(f"layout{slot.title()}")
        self.pick.setAccessibleName(title)
        for spec in layouts_for(role):
            self.pick.addItem(spec.label, spec.id)
        self.pick.setCurrentIndex(max(self.pick.findData(choice[slot]), 0))
        body.addWidget(self.pick)
        self.summary = QLabel()
        self.summary.setObjectName(f"layout{slot.title()}Summary")
        self.summary.setWordWrap(True)
        body.addWidget(self.summary)
        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        self._form.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._form_host)
        self.more = QCheckBox("Fine-tune this design")
        self.more.setObjectName(f"layout{slot.title()}More")
        body.addWidget(self.more)
        self.reset = QPushButton("Reset this layout's options")
        self.reset.setObjectName(f"layout{slot.title()}Reset")
        body.addWidget(self.reset)
        self.pick.currentIndexChanged.connect(lambda _index: self._rebuild(True))
        self.more.toggled.connect(lambda _on: self._rebuild(False))
        self.reset.clicked.connect(self._reset)
        self._rebuild(True)

    def chosen(self) -> str:
        return str(self.pick.currentData())

    def options(self) -> dict[str, dict[str, str]]:
        """Only what the student changed. Writing a design's defaults down would freeze them, and a
        default that later improves would never reach anyone who had opened this dialog."""
        changed = {}
        for layout_id, values in self._options.items():
            shipped = options_for(None, layout_id)
            differs = {key: value for key, value in values.items() if value != shipped[key]}
            if differs:
                changed[layout_id] = differs
        return changed

    def _reset(self) -> None:
        self._options[self.chosen()] = options_for(None, self.chosen())
        self._rebuild(True)

    def _rebuild(self, fresh: bool) -> None:
        spec = LAYOUTS[self.chosen()]
        values = self._options[spec.id]
        self.summary.setText(spec.summary)
        detail = [option for option in spec.options if option.level == "detail"]
        if fresh:
            # Fine-tuning that is already in use must not be hidden from the student who set it.
            self.more.blockSignals(True)
            self.more.setChecked(any(values[option.key] != option.default for option in detail))
            self.more.blockSignals(False)
        self.more.setVisible(bool(detail))
        self.reset.setVisible(bool(spec.options))
        empty(self._form)
        for level, heading in LEVELS:
            rows = [option for option in spec.options if option.level == level]
            if not rows or (level == "detail" and not self.more.isChecked()):
                continue
            title = QLabel(heading)
            title.setObjectName(f"layout{self.slot.title()}Level-{level}")
            self._form.addRow(title)
            for option in rows:
                box = QComboBox()
                box.setObjectName(f"layout{self.slot.title()}-{option.key}")
                for entry in option.choices:
                    box.addItem(entry.label, entry.value)
                box.blockSignals(True)
                box.setCurrentIndex(max(box.findData(values[option.key]), 0))
                box.blockSignals(False)
                box.currentIndexChanged.connect(
                    lambda _index, key=option.key, source=box, target=spec.id: self._options[
                        target
                    ].__setitem__(key, str(source.currentData()))
                )
                self._form.addRow(option.label, box)
