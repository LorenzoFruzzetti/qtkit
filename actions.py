"""Commands as data: one QAction per command, reused by menus, toolbars and shortcuts.

An application declares a tuple of ``ActionSpec`` and a default layout dictionary::

    {"menus": {"File": ["file.open", "-", "app.quit"]},
     "toolbars": {"main": ["file.open"]},
     "shortcuts": {}}

``"-"`` is a separator. User changes are stored separately in an override JSON file
that contains only the sections the user changed, so defaults can evolve.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from typing import NamedTuple
from .qt import QtCore, QtGui, QtWidgets


class ActionSpec(NamedTuple):
    id: str  # stable identifier used in layouts, e.g. "file.open"
    label: str  # menu/toolbar text
    shortcut: str  # default key sequence, "" for none
    method: str  # name of the handler method called when triggered
    icon: str  # QStyle.StandardPixmap name, e.g. "SP_DirOpenIcon"


def validate_layout(layout: dict, specs) -> None:
    """Raise ValueError for unknown sections/actions, invalid or conflicting shortcuts."""
    ids = {spec[0] for spec in specs}
    if set(layout) - {"menus", "toolbars", "shortcuts"}:
        raise ValueError("Unknown layout section")
    for section in ("menus", "toolbars"):
        for entries in layout.get(section, {}).values():
            if not isinstance(entries, list) or any(
                item != "-" and item not in ids for item in entries
            ):
                raise ValueError(f"Unknown action in {section}")
    if set(layout.get("shortcuts", {})) - ids:
        raise ValueError("Unknown action in shortcuts")
    shortcuts = {spec[0]: spec[2] for spec in specs}
    shortcuts.update(layout.get("shortcuts", {}))
    used = {}
    for key, value in shortcuts.items():
        sequence = QtGui.QKeySequence(value).toString(QtGui.QKeySequence.PortableText)
        if value and not sequence:
            raise ValueError(f"Invalid shortcut for {key}")
        if sequence and sequence in used:
            raise ValueError(f"Shortcut conflict: {used[sequence]} and {key} use {sequence}")
        if sequence:
            used[sequence] = key


def write_json_atomic(path: Path, payload) -> None:
    """Write next to the destination and atomically replace it (no half-written files)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".qtkit-", suffix=".json", dir=path.parent)
    # finally only removes a leftover temporary file; errors still propagate.
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ActionRegistry:
    """Create every QAction once and apply the default layout plus user overrides."""

    def __init__(self, window, specs, default_layout: dict, override_path: Path, handler):
        self.window = window
        self.specs = tuple(specs)
        self.default = default_layout
        self.override_path = Path(override_path)
        self.actions = {}
        for key, label, _, method, icon in self.specs:
            action = QtGui.QAction(
                window.style().standardIcon(getattr(QtWidgets.QStyle, icon)), label, window
            )
            action.setObjectName(key)
            action.setShortcutContext(QtCore.Qt.WindowShortcut)
            # Bind the handler method now so a missing method fails at startup.
            action.triggered.connect(
                lambda checked=False, function=getattr(handler, method): function()
            )
            window.addAction(action)
            self.actions[key] = action
        self.reload()

    def default_shortcuts(self) -> dict[str, str]:
        return {spec[0]: spec[2] for spec in self.specs}

    def reload(self):
        """Rebuild the effective layout from the defaults and the override file."""
        self.layout = json.loads(json.dumps(self.default))
        self.overrides = (
            json.loads(self.override_path.read_text(encoding="utf-8"))
            if self.override_path.exists()
            else {}
        )
        validate_layout(self.overrides, self.specs)
        for section, values in self.overrides.items():
            self.layout[section].update(values)
        validate_layout(self.layout, self.specs)
        shortcuts = self.default_shortcuts()
        shortcuts.update(self.layout["shortcuts"])
        for key, action in self.actions.items():
            action.setShortcut(QtGui.QKeySequence(shortcuts[key]))
            action.setToolTip(
                f"{action.text()} ({shortcuts[key]})" if shortcuts[key] else action.text()
            )

    def save_overrides(self, section: str, values: dict):
        """Persist one changed section; validation runs before anything is written."""
        overrides = dict(self.overrides)
        overrides[section] = values
        validate_layout(overrides, self.specs)
        write_json_atomic(self.override_path, overrides)
        self.reload()

    def reset(self):
        """Forget every user override and return to the default layout."""
        self.override_path.unlink(missing_ok=True)
        self.reload()
