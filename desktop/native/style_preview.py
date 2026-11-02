"""The preview stage shared by My Look and the style picker.

Fit shows the whole picture in the room it has. Actual size shows it at the size it was drawn, and
scrolls. The style picker also switches that picture between the main view and the day screen.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.native.previews import CANVAS, render
from desktop.native.tokens import SPACING
from desktop.native.widgets import Segmented, overlay_scroll_bars

FIT_NOTE = "The whole window, fitted to this space."
ACTUAL_NOTE = "The whole window, at its real size: scroll to see all of it."
# Long enough that a slider drag or a keystroke does not draw on every tick, short enough that the
# picture follows the control.
PREVIEW_DELAY_MS = 40


class Picture(QScrollArea):
    """The window as a picture: fitted to the room, or at its real size and scrolled."""

    def __init__(
        self,
        name: str = "lookPicture",
        image_name: str = "lookPreviewImage",
        *,
        compact: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName(name)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.image = QLabel()
        self.image.setObjectName(image_name)
        self.setWidget(self.image)
        overlay_scroll_bars(self)
        self.source = QPixmap()
        self.fit = True
        self._compact = compact

    def show_picture(self, picture: QPixmap, fit: bool) -> None:
        self.source, self.fit = picture, fit
        self._lay_out()

    def sizeHint(self) -> QSize:  # noqa: N802
        # A drawn week is wider than Settings. The room it is given, not the pixmap, decides its size.
        if self._compact:
            return QSize(240, 150)
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        if self._compact:
            return QSize(80, 60)
        return super().minimumSizeHint()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._lay_out()

    def _lay_out(self) -> None:
        policy = Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self.fit else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)
        if self.source.isNull():
            return
        shown = self.source
        if self.fit:
            ratio = self.source.devicePixelRatio()
            room = self.viewport().size()
            shown = self.source.scaled(
                room * ratio, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            shown.setDevicePixelRatio(ratio)
        self.image.setPixmap(shown)
        self.image.resize(shown.deviceIndependentSize().toSize())


class PreviewStage(QWidget):
    """Fit and Actual size, and, when a style picker asks, Main view and Day screen."""

    surface_changed = Signal(str)

    def __init__(
        self,
        *,
        stage_name: str,
        stage_accessible: str,
        picture_name: str,
        image_name: str,
        zoom_name: str,
        bar_name: str,
        zoom_accessible: str,
        fit_note: str,
        actual_note: str,
        note_name: str,
        surfaces: tuple[tuple[str, str], ...] = (),
        surface_name: str = "",
        surface_accessible: str = "",
        wire_zoom: bool = True,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("bare", True)
        self._fit_note = fit_note
        self._actual_note = actual_note
        self._compact = compact
        self.stack = QStackedWidget()
        self.stack.setObjectName(stage_name)
        self.stack.setAccessibleName(stage_accessible)
        self.pictures = (
            Picture(picture_name, image_name, compact=compact),
            Picture(picture_name, image_name, compact=compact),
        )
        for picture in self.pictures:
            self.stack.addWidget(picture)
        self.note = QLabel(fit_note)
        self.note.setObjectName(note_name)
        self.zoom = Segmented((("Fit", True), ("Actual size", False)), zoom_name)
        self.zoom.setAccessibleName(zoom_accessible)
        self.surface: Segmented | None = None
        if surfaces:
            self.surface = Segmented(surfaces, surface_name)
            self.surface.setAccessibleName(surface_accessible)
            self.surface.currentIndexChanged.connect(self._surface_changed)
        if wire_zoom:
            self.zoom.currentIndexChanged.connect(self._zoomed)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self.stack, 1)
        column.addWidget(self._bar(bar_name, compact))
        if compact:
            self.setMinimumHeight(120)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._compact:
            return QSize(320, 200)
        return super().sizeHint()

    def _bar(self, name: str, compact: bool) -> QWidget:
        bar = QWidget()
        bar.setObjectName(name)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if self.surface is None:
            # My Look's bar: one line, the note on the left and the size on the right.
            bar.setFixedHeight(44)
            line = QHBoxLayout(bar)
            line.setContentsMargins(SPACING[3], 0, SPACING[3], 0)
            line.addWidget(self.note)
            line.addStretch(1)
            line.addWidget(self.zoom)
            return bar
        # The style picker has two switches. Stacked, they fit a 1024-wide window at large text.
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(SPACING[3], SPACING[2], SPACING[3], SPACING[2])
        rows.setSpacing(SPACING[1])
        note_row = QHBoxLayout()
        note_row.setContentsMargins(0, 0, 0, 0)
        self.note.setWordWrap(compact)
        note_row.addWidget(self.note, 1)
        rows.addLayout(note_row)
        rows.addWidget(self.surface, 0, Qt.AlignmentFlag.AlignLeft)
        rows.addWidget(self.zoom, 0, Qt.AlignmentFlag.AlignLeft)
        return bar

    def fit(self) -> bool:
        return bool(self.zoom.currentData())

    def surface_id(self) -> str:
        if self.surface is None:
            return "main"
        return str(self.surface.currentData())

    def show_picture(self, picture: QPixmap) -> None:
        fitted = self.fit()
        for page in self.pictures:
            page.show_picture(picture, fitted)

    def _zoomed(self, _index: int) -> None:
        self.note.setText(self._fit_note if self.fit() else self._actual_note)
        for page in self.pictures:
            page.show_picture(page.source, self.fit())

    def _surface_changed(self, _index: int) -> None:
        self.surface_changed.emit(self.surface_id())


class Redraw(QObject):
    """Draw on a short delay, and drop a picture that finished after a newer request."""

    def __init__(
        self,
        paint: Callable[[], QPixmap | None],
        show: Callable[[QPixmap], None],
        delay_ms: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._paint = paint
        self._show = show
        self._generation = 0
        self._painting = False
        self.dropped = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._run)

    def ask(self) -> None:
        self._generation += 1
        self._timer.start()

    def waiting(self) -> bool:
        return self._timer.isActive()

    def _run(self) -> None:
        # Settling a picture runs the event loop, so the next request can arrive mid-draw.
        if self._painting:
            return
        generation = self._generation
        self._painting = True
        try:
            picture = self._paint()
        finally:
            self._painting = False
        if generation != self._generation:
            self.dropped += 1
            if not self._timer.isActive():
                self._timer.start()
            return
        if picture is not None:
            self._show(picture)


class StyleChoice:
    """The style being tried. Editing changes the draft. Applying is what saves it."""

    def __init__(self, committed: dict, on_apply: Callable[[dict], None] | None = None) -> None:
        self.committed = copy.deepcopy(committed)
        self.draft = copy.deepcopy(committed)
        self._on_apply = on_apply

    def edit(self, draft: dict) -> None:
        self.draft = copy.deepcopy(draft)

    def apply(self) -> dict:
        self.committed = copy.deepcopy(self.draft)
        saved = copy.deepcopy(self.committed)
        if self._on_apply is not None:
            self._on_apply(saved)
        return saved

    def discard(self) -> dict:
        self.draft = copy.deepcopy(self.committed)
        return copy.deepcopy(self.draft)


class StylePreview(QWidget):
    """A live picture of the style the sections are set to. Refresh does not save it."""

    def __init__(
        self,
        sections: list,
        pack: Callable[[], str],
        look: Callable[[], dict | None],
        on_apply: Callable[[dict], None] | None = None,
        delay_ms: int = PREVIEW_DELAY_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stylePreviewHost")
        self.sections = list(sections)
        self._pack = pack
        self._look = look
        self.choice = StyleChoice(self.snapshot(), on_apply)
        self.stage = PreviewStage(
            stage_name="stylePreview",
            stage_accessible="Style preview",
            picture_name="stylePicture",
            image_name="stylePreviewImage",
            zoom_name="stylePreviewSize",
            bar_name="stylePreviewBar",
            zoom_accessible="Preview size",
            fit_note=FIT_NOTE,
            actual_note=ACTUAL_NOTE,
            note_name="stylePreviewNote",
            surfaces=(("Main view", "main"), ("Day screen", "day")),
            surface_name="stylePreviewSurface",
            surface_accessible="Preview",
            compact=True,
        )
        self.redraw = Redraw(self._paint, self.stage.show_picture, delay_ms, self)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self.stage, 1)
        for section in self.sections:
            section.changed.connect(self.refresh)
        self.stage.surface_changed.connect(self.refresh)

    def snapshot(self) -> dict:
        return {
            section.slot: {"id": section.chosen(), "options": section.values()}
            for section in self.sections
        }

    def refresh(self, *_args: object) -> None:
        self.choice.edit(self.snapshot())
        if self.isVisible():
            self.redraw.ask()

    def apply(self) -> dict:
        return self.choice.apply()

    def discard(self) -> dict:
        return self.choice.discard()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def _section(self):
        slot = self.stage.surface_id()
        for section in self.sections:
            if section.slot != slot:
                continue
            # F1's Material entry, when it lands, owns that picture.
            surface = getattr(section, "surface", None)
            if callable(surface) and surface() == "material":
                return None
            return section
        return None

    def _paint(self) -> QPixmap | None:
        section = self._section()
        if section is None:
            return None
        values = section.values()
        token = values.get("look")
        colour = None if token in (None, "your") else token
        return render(
            section.chosen(),
            colour,
            self._pack(),
            self._look(),
            CANVAS.width(),
            CANVAS,
            options=values,
        )
