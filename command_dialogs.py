"""Human-readable editors for keyboard shortcuts and toolbar contents."""

from __future__ import annotations
from .qt import QtCore, QtGui, QtWidgets


def edit_shortcuts(window, registry, rebuild):
    """Edit every action's shortcut; only values that differ from defaults are stored.

    ``rebuild`` is called after saving so menus and toolbars show the new shortcuts.
    """
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle("Keyboard shortcuts")
    dialog.resize(560, 620)
    outer = QtWidgets.QVBoxLayout(dialog)
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    content = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(content)
    editors = {}
    for key, action in registry.actions.items():
        editor = QtWidgets.QKeySequenceEdit(action.shortcut())
        editors[key] = editor
        form.addRow(action.text(), editor)
    scroll.setWidget(content)
    outer.addWidget(scroll)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
    )

    def save():
        defaults = registry.default_shortcuts()
        changed = {
            key: editor.keySequence().toString(QtGui.QKeySequence.PortableText)
            for key, editor in editors.items()
            if editor.keySequence() != QtGui.QKeySequence(defaults[key])
        }
        # Conflicts raise ValueError here and are reported by the application's error hook.
        registry.save_overrides("shortcuts", changed)
        rebuild()
        dialog.accept()

    buttons.accepted.connect(save)
    buttons.rejected.connect(dialog.reject)
    outer.addWidget(buttons)
    dialog.exec()


def edit_toolbar(window, registry, rebuild, name=None):
    """Choose and order the commands of one toolbar (the first one by default)."""
    name = name or next(iter(registry.layout["toolbars"]))
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle(f"Customize {name} toolbar")
    dialog.resize(700, 450)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(
        QtWidgets.QLabel("Add commands or separators, then drag the selected list to reorder.")
    )
    row = QtWidgets.QHBoxLayout()
    available = QtWidgets.QListWidget()
    selected = QtWidgets.QListWidget()
    selected.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
    ids = ["-"] + list(registry.actions)
    available.addItems(["— Separator —"] + [a.text() for a in registry.actions.values()])

    def add(key):
        item = QtWidgets.QListWidgetItem(
            "— Separator —" if key == "-" else registry.actions[key].text()
        )
        item.setData(QtCore.Qt.UserRole, key)
        selected.addItem(item)

    for key in registry.layout["toolbars"][name]:
        add(key)
    buttons_column = QtWidgets.QVBoxLayout()
    add_button = QtWidgets.QPushButton("Add →")
    remove = QtWidgets.QPushButton("Remove")
    add_button.clicked.connect(
        lambda: add(ids[available.currentRow()]) if available.currentRow() >= 0 else None
    )
    remove.clicked.connect(lambda: selected.takeItem(selected.currentRow()))
    buttons_column.addStretch()
    buttons_column.addWidget(add_button)
    buttons_column.addWidget(remove)
    buttons_column.addStretch()
    row.addWidget(available)
    row.addLayout(buttons_column)
    row.addWidget(selected)
    layout.addLayout(row)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
    )

    def save():
        entries = [selected.item(i).data(QtCore.Qt.UserRole) for i in range(selected.count())]
        overrides = dict(registry.overrides.get("toolbars", {}))
        # Store nothing when the user recreated the default, so future defaults apply.
        if entries == registry.default["toolbars"][name]:
            overrides.pop(name, None)
        else:
            overrides[name] = entries
        registry.save_overrides("toolbars", overrides)
        rebuild()
        dialog.accept()

    buttons.accepted.connect(save)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
