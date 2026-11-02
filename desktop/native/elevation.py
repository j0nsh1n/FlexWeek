"""The system's two shadows (decision 6) put on a widget."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from desktop.native.tokens import Shadow


def lift(widget: QWidget, shadow: Shadow, dark: bool = False) -> QGraphicsDropShadowEffect:
    """Give `widget` `shadow`. A drop shadow already there is updated, not replaced.

    setGraphicsEffect deletes the previous effect. Shiboken crashes in that destructor when the
    shadow was put on a menu while its window was still being built, then put on again once the
    look is applied. A second window in the same process is enough. A widget holds one effect, so a
    fade on the same widget (motion.py) goes on a child instead.
    """
    colour = QColor(0, 0, 0, round(255 * (shadow.dark_opacity if dark else shadow.opacity)))
    current = widget.graphicsEffect()
    if isinstance(current, QGraphicsDropShadowEffect):
        current.setOffset(0, shadow.y)
        current.setBlurRadius(shadow.blur)
        current.setColor(colour)
        return current
    effect = QGraphicsDropShadowEffect(widget)
    effect.setOffset(0, shadow.y)
    effect.setBlurRadius(shadow.blur)
    effect.setColor(colour)
    widget.setGraphicsEffect(effect)
    return effect
