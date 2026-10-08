"""Smallest complete qtkit application: commands, docks, parameters, guide and a table.

Run from the editor or:  python -m qtkit.demo
Nothing is written except Qt preferences (window layout, customized shortcuts).
Copy this file into your package as the starting point for a new project's GUI.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import sys
from typing import Any
import pandas as pd
from qtkit import ActionSpec, DataFrameModel, FieldHint, ParameterDialog, ShellWindow, Step
from qtkit.qt import QtCore, QtWidgets

# Edit this section to run the example without passing CLI flags.
RUN_CONFIG: dict[str, Any] = {
    "organization": "QtkitExample",  # QSettings namespace for window layout/shortcuts
    "application": "MinimalDemo",
}


# 1. Application parameters: numeric fields carry metadata, the dialog builds the form.
@dataclass(frozen=True)
class Settings:
    data_folder: str = ""
    rows: int = field(
        default=None, metadata=dict(doc="Rows to generate", unit="rows", minimum=1, maximum=1000)
    )
    scale: float = field(
        default=1.0, metadata=dict(doc="Multiplier for values", unit="×", minimum=0, maximum=100)
    )
    labels: tuple[str, ...] = ("a", "b")


def make_settings(values: dict) -> Settings:
    # Application validation; errors propagate to the caller (no silent fallback).
    if values["rows"] < 1:
        raise ValueError("Choose the number of rows")
    return Settings(**values)


# 2. Plain state, written only by the controller.
@dataclass
class State:
    settings: Settings | None = None
    table: pd.DataFrame | None = None
    busy: bool = False


# 3. Controller: every action id maps to one of these methods.
class Controller:
    def __init__(self, window):
        self.window = window
        self.state = State()

    def parameters(self):
        dialog = ParameterDialog(
            self.window,
            Settings,
            vars(self.state.settings) if self.state.settings else {},
            make_settings,
            {"data_folder": FieldHint("dir")},
            title="Demo parameters",
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.state.settings = dialog.value
            self.state.table = None
            self.window.refresh(self.state)

    def run(self):
        settings = self.state.settings
        self.state.table = pd.DataFrame(
            {"row": range(settings.rows), "value": [i * settings.scale for i in range(settings.rows)]}
        )
        self.window.refresh(self.state)

    def show_guide(self):
        self.window.show_guide()

    def shortcuts(self):
        self.window.edit_shortcuts()

    def toolbar(self):
        self.window.edit_toolbar()

    def reset_commands(self):
        self.window.reset_commands()

    def quit(self):
        self.window.close()


# 4. Commands and their default placement (both are plain data).
ACTIONS = (
    ActionSpec("app.parameters", "1 · Parameters…", "Ctrl+,", "parameters", "SP_FileDialogDetailedView"),
    ActionSpec("app.run", "2 · Run", "Ctrl+R", "run", "SP_MediaPlay"),
    ActionSpec("help.guide", "Pipeline guide", "F1", "show_guide", "SP_DialogHelpButton"),
    ActionSpec("settings.shortcuts", "Keyboard shortcuts…", "", "shortcuts", "SP_ComputerIcon"),
    ActionSpec("settings.toolbar", "Customize toolbar…", "", "toolbar", "SP_FileDialogListView"),
    ActionSpec("settings.reset", "Reset commands to defaults", "", "reset_commands", "SP_DialogResetButton"),
    ActionSpec("app.quit", "Quit", "Ctrl+Q", "quit", "SP_DialogCloseButton"),
)
LAYOUT = {
    "menus": {
        "File": ["app.parameters", "app.run", "-", "app.quit"],
        "Settings": ["settings.shortcuts", "settings.toolbar", "settings.reset"],
        "Help": ["help.guide"],
    },
    "toolbars": {"main": ["app.parameters", "app.run"]},
    "shortcuts": {},
}

# 5. Pipeline guide: steps plus a status function computed from the state.
STEPS = (
    Step("parameters", "1 · Choose parameters", "app.parameters",
         "<h3>1 · Choose parameters</h3><p>Set the number of rows and the scale.</p>"),
    Step("run", "2 · Run", "app.run",
         "<h3>2 · Run</h3><p>Generates the table shown in the central view.</p>"),
    Step("review", "3 · Review the table", None,
         "<h3>3 · Review the table</h3><p>Click a column header to sort.</p>"),
)


def progress(state: State):
    return [
        (state.settings is not None, "Set" if state.settings else "Not set"),
        (state.table is not None, f"{len(state.table)} rows" if state.table is not None else "Not run"),
        (False, "Table ready" if state.table is not None else "Waiting"),
    ]


class DemoWindow(ShellWindow):
    def __init__(self, settings=None, config_dir=None):
        super().__init__(
            settings or QtCore.QSettings(RUN_CONFIG["organization"], RUN_CONFIG["application"]),
            config_dir
            or QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation),
        )
        self.resize(1000, 650)
        self.controller = Controller(self)
        self.install_commands(ACTIONS, LAYOUT, self.controller)
        self.model = DataFrameModel(self)
        proxy = QtCore.QSortFilterProxyModel(self)
        proxy.setSourceModel(self.model)
        proxy.setSortRole(QtCore.Qt.UserRole)
        table = QtWidgets.QTableView()
        table.setModel(proxy)
        table.setSortingEnabled(True)
        self.setCentralWidget(table)
        self.notes = QtWidgets.QPlainTextEdit("Drag this dock anywhere; View › Reset window layout.")
        self.add_dock("notes", "Notes", self.notes, QtCore.Qt.BottomDockWidgetArea, 100)
        self.add_guide(STEPS, progress)
        self.build_commands()
        self.restore_window()
        self.refresh(self.controller.state)

    def refresh(self, state):
        self.model.set_frame(state.table)
        self.guide.refresh(state)
        self.update_actions()

    def update_actions(self):
        self.registry.actions["app.run"].setEnabled(self.controller.state.settings is not None)

    def closeEvent(self, event):
        self.save_window()
        event.accept()


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setOrganizationName(RUN_CONFIG["organization"])
    app.setApplicationName(RUN_CONFIG["application"])
    window = DemoWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
