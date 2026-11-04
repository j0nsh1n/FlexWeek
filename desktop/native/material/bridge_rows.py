"""List models the Material shell's repeaters can read.

A Python list of dicts is not a model Qt Quick will build. Each screen bridge owns
the models for its own file, and later lanes add rows here only when every screen
needs the same shape.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)


class Rows(QAbstractListModel):
    """Rows of named roles. The role names are the keys the QML delegate reads."""

    def __init__(self, roles: tuple[str, ...], parent: QObject) -> None:
        super().__init__(parent)
        self._names = {Qt.ItemDataRole.UserRole + 1 + index: name for index, name in enumerate(roles)}
        self._roles = {role: QByteArray(name.encode("ascii")) for role, name in self._names.items()}
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        name = self._names.get(role)
        if name is None or not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(name)

    def roleNames(self) -> dict[int, QByteArray]:
        return self._roles


class Labels(QAbstractListModel):
    """One string a row, as the role `label`."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._rows: list[str] = []

    def set_rows(self, rows: list[str]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if role != Qt.ItemDataRole.UserRole + 1 or not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + 1: QByteArray(b"label")}
