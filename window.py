"""Main-window base: data-driven menus/toolbars, movable docks and a remembered layout.

Typical subclass::

    class MainWindow(ShellWindow):
        def __init__(self):
            super().__init__(QtCore.QSettings("Org", "App"), config_dir)
            self.controller = Controller(self)
            self.install_commands(ACTIONS, DEFAULT_LAYOUT, self.controller)
            self.setCentralWidget(...)
            self.add_dock("log", "Activity", log_widget, QtCore.Qt.BottomDockWidgetArea)
            self.add_guide(STEPS, progress)
            self.build_commands()
            self.restore_window()

        def closeEvent(self, event):
            self.save_window()
            event.accept()
"""

from __future__ import annotations
from pathlib import Path
from .qt import QtCore, QtWidgets
from .actions import ActionRegistry
from .command_dialogs import edit_shortcuts, edit_toolbar
from .guide import PipelineGuideView


class ShellWindow(QtWidgets.QMainWindow):
    # Bump when docks/toolbars change incompatibly so stale saved layouts are ignored.
    LAYOUT_VERSION = 1

    def __init__(self, settings: QtCore.QSettings, config_dir):
        super().__init__()
        self.settings = settings
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.docks = {}
        self.toolbars = []
        self.registry = None
        self.guide = None
        self.guide_steps = ()
        self.default_state = None

    # ----- commands --------------------------------------------------------------
    def install_commands(self, specs, default_layout, handler):
        """Create the action registry; user overrides live in <config_dir>/layout.json."""
        self.registry = ActionRegistry(
            self, specs, default_layout, self.config_dir / "layout.json", handler
        )

    def build_commands(self):
        """(Re)build menus and toolbars from the effective layout."""
        self.menuBar().clear()
        for toolbar in self.toolbars:
            self.removeToolBar(toolbar)
            toolbar.deleteLater()
        self.toolbars = []
        for title, ids in self.registry.layout["menus"].items():
            menu = self.menuBar().addMenu(title)
            for key in ids:
                menu.addSeparator() if key == "-" else menu.addAction(self.registry.actions[key])
            self.extend_menu(title, menu)
        view_menu = self.menuBar().addMenu("View")
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction("Reset window layout", self.reset_window_layout)
        for name, ids in self.registry.layout["toolbars"].items():
            toolbar = QtWidgets.QToolBar(name, self)
            # objectName lets saveState/restoreState remember the toolbar position.
            toolbar.setObjectName(f"toolbar_{name}")
            toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            for key in ids:
                toolbar.addSeparator() if key == "-" else toolbar.addAction(
                    self.registry.actions[key]
                )
            self.addToolBar(toolbar)
            self.toolbars.append(toolbar)
        self.update_actions()

    def extend_menu(self, title, menu):
        """Hook: add dynamic entries (e.g. an "Open recent" submenu) to a menu."""

    def update_actions(self):
        """Hook: enable/disable actions from the application state."""

    def edit_shortcuts(self):
        edit_shortcuts(self, self.registry, self.build_commands)

    def edit_toolbar(self):
        edit_toolbar(self, self.registry, self.build_commands)

    def reset_commands(self):
        """Discard customized shortcuts, menus and toolbars."""
        self.registry.reset()
        self.build_commands()

    # ----- docks and layout -------------------------------------------------------
    def add_dock(self, name, title, widget, area, size=None):
        """Host a widget in a movable, closable dock; ``name`` keys the saved layout."""
        dock = QtWidgets.QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        if size is not None:
            vertical = area in (QtCore.Qt.TopDockWidgetArea, QtCore.Qt.BottomDockWidgetArea)
            self.resizeDocks(
                [dock], [size], QtCore.Qt.Vertical if vertical else QtCore.Qt.Horizontal
            )
        self.docks[name] = dock
        return dock

    def restore_window(self):
        """Remember the built-in arrangement, then apply the user's saved one."""
        self.default_state = self.saveState(self.LAYOUT_VERSION)
        geometry = self.settings.value("geometry")
        saved_state = self.settings.value("layout")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if saved_state is not None:
            self.restoreState(saved_state, self.LAYOUT_VERSION)

    def save_window(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("layout", self.saveState(self.LAYOUT_VERSION))

    def reset_window_layout(self):
        """Put docks and toolbars back where the application first placed them."""
        self.restoreState(self.default_state, self.LAYOUT_VERSION)
        for dock in self.docks.values():
            dock.setFloating(False)
            dock.show()

    # ----- pipeline guide ---------------------------------------------------------
    def add_guide(self, steps, progress, area=QtCore.Qt.RightDockWidgetArea, size=340):
        """Dock a PipelineGuideView whose "Go to this step" calls go_to_step."""
        self.guide_steps = tuple(steps)
        self.guide = PipelineGuideView(self.guide_steps, progress, self.go_to_step)
        self.add_dock("pipeline_guide", "Pipeline guide", self.guide, area, size)
        return self.guide

    def show_guide(self):
        self.docks["pipeline_guide"].show()
        self.docks["pipeline_guide"].raise_()

    def go_to_step(self, key):
        """Show the step's view, then run its action when it is currently allowed."""
        self.show_step_view(key)
        action_id = next(step.action for step in self.guide_steps if step.key == key)
        if action_id is None:
            return
        action = self.registry.actions[action_id]
        if action.isEnabled():
            action.trigger()
        else:
            # Explain instead of failing silently when an earlier step is unfinished.
            self.notify(
                f"'{action.text()}' is not available yet; complete the earlier steps first."
            )

    def show_step_view(self, key):
        """Hook: switch to the tab/view that belongs to a guide step."""

    def notify(self, message):
        """Hook: short user-facing message; override to also log it."""
        self.statusBar().showMessage(message)
