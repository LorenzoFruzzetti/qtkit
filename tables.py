"""Read-only pandas DataFrame model for QTableView, sortable by the underlying values."""

from __future__ import annotations
import numpy as np
from .qt import QtCore


class DataFrameModel(QtCore.QAbstractTableModel):
    """Display a DataFrame; UserRole returns the raw Python value for numeric sorting.

    Wrap it in a QSortFilterProxyModel with ``setSortRole(QtCore.Qt.UserRole)`` to sort
    numbers as numbers instead of as text.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None

    def set_frame(self, frame):
        # Replacing the same object is a no-op so refreshes do not reset the selection.
        if frame is self.frame:
            return
        self.beginResetModel()
        self.frame = frame
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() or self.frame is None else len(self.frame)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() or self.frame is None else len(self.frame.columns)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or self.frame is None:
            return None
        if role == QtCore.Qt.DisplayRole:
            return str(self.frame.iat[index.row(), index.column()])
        if role == QtCore.Qt.UserRole:
            value = self.frame.iat[index.row(), index.column()]
            return value.item() if isinstance(value, np.generic) else value
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and self.frame is not None:
            return (
                str(self.frame.columns[section])
                if orientation == QtCore.Qt.Horizontal
                else str(section + 1)
            )
        return None
