"""Qt binding bootstrap shared by every qtkit module and application."""

from importlib import import_module
from importlib.util import find_spec
import os
from pathlib import Path

# Prefer the declared dependency when a research environment has multiple bindings.
if find_spec("PySide6") is not None:
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, QT_LIB  # noqa: E402

__all__ = ["QtCore", "QtGui", "QtWidgets"]

# A Conda qt.conf can point at another binding's plugins. Use the active binding's
# bundled platform plugins when available, avoiding a mismatched Qt runtime.
_root = Path(import_module(QT_LIB).__file__).parent
for _candidate in (_root / "plugins", _root / "Qt6" / "plugins", _root / "Qt5" / "plugins"):
    if _candidate.is_dir():
        QtCore.QCoreApplication.setLibraryPaths([str(_candidate)])
        break
