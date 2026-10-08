# qtkit — reusable desktop GUI building blocks

Application-independent parts of a PySide6 desktop tool, implementing the shell
described in `GUI_DESIGN_GUIDELINES.md` (section 9 maps guideline points to modules).
`qtkit` imports nothing from the project that hosts it. Everything it needs is in this
folder: the code, a runnable demo (`demo.py`) and its own tests (`tests/`).

## Drop into a new project

Copy three things to the target project root:

```text
<target_project>/
|-- GUI_DESIGN_GUIDELINES.md        # what the GUI must do (design rules)
|-- REUSABLE_PACKAGING_GUIDE.md     # how to restructure the analysis code (optional)
`-- src/qtkit/                      # this folder, unchanged
```

Then, in the target project:

1. **Use a `src/` layout** so `qtkit` installs next to the project package. In
   `pyproject.toml`:

   ```toml
   [project.optional-dependencies]
   gui = ["PySide6>=6.5,<6.9", "pyqtgraph>=0.13,<0.15", "pandas>=2.0", "numpy>=1.24"]
   dev = ["pytest>=7", "pytest-qt>=4.2"]

   [tool.setuptools.packages.find]
   where = ["src"]
   exclude = ["qtkit.tests*"]

   [tool.setuptools.package-data]
   "qtkit" = ["README.md"]

   [tool.pytest.ini_options]
   testpaths = ["tests", "src/qtkit/tests"]
   qt_api = "pyside6"
   ```

2. **Install and check the kit** in the project environment:

   ```sh
   conda run -n <env_name> python -m pip install -e ".[gui,dev]"
   conda run -n <env_name> python -m pytest src/qtkit/tests
   conda run -n <env_name> python -m qtkit.demo
   ```

3. **Start the application GUI from the demo.** Copy `demo.py` to
   `src/<package>/gui/window.py` (or split it into `actions.py`, `guide.py`,
   `controller.py`, `window.py`, as in the Y-maze project), then replace:
   - `Settings` with the project's config dataclass, using numeric field metadata;
   - `ACTIONS` / `LAYOUT` with the project's commands, with ids namespaced by project;
   - `STEPS` / `progress` with the project's workflow;
   - the central table with the project's views.
4. **Keep project code out of `src/qtkit/`.** Generic improvements go back into the kit
   together with a test in `src/qtkit/tests/`. Copy the improved folder to the other
   projects that use it.

Not provided by the kit (implement per project, following the guidelines): background
workers and cancellation (§5), the error dialog, exception hook and logging (§6),
document open/save/recent files/drag-drop (§4) and undo commands (§6).

## Modules

| Module | Provides | The application supplies |
|---|---|---|
| `qt.py` | `QtCore, QtGui, QtWidgets` through `pyqtgraph.Qt`, preferring PySide6 and the binding's bundled plugins (avoids mismatched Conda `qt.conf`) | — |
| `actions.py` | `ActionSpec`, `ActionRegistry`, `validate_layout`: one `QAction` per command; menus, toolbars and shortcuts as JSON; user overrides in `<config_dir>/layout.json`; shortcut conflicts rejected | a tuple of `ActionSpec(id, label, shortcut, method, icon)`, a default layout dict, and a handler object with those methods |
| `command_dialogs.py` | `edit_shortcuts`, `edit_toolbar` editors that store only differences from the defaults | — |
| `window.py` | `ShellWindow(QMainWindow)`: `install_commands`, `build_commands`, `add_dock`, View menu toggles, `restore_window` / `save_window` / `reset_window_layout`, `reset_commands`, `add_guide`, `go_to_step` | hooks `update_actions`, `extend_menu`, `show_step_view`, `notify` |
| `guide.py` | `Step`, `PipelineGuideView`: step list with ✓/▶/○ status, detailed HTML help, "Go to this step" | the steps and `progress(state) -> [(done, detail), ...]` |
| `params.py` | `ParameterDialog`, `FieldHint`: a form generated from a dataclass | the dataclass, `FieldHint`s for non-numeric fields, and a `factory(values)` that validates |
| `tables.py` | `DataFrameModel`: a pandas table for `QTableView`; `UserRole` sorts by raw values | — |
| `testing.py` | `isolated_settings`, `check_commands`, fixtures `qtkit_settings`, `qtkit_config_dir` | import the fixtures in a `conftest.py` (as `tests/conftest.py` here does) |
| `demo.py` | the smallest complete application using every module | — |

## Conventions

- **Numeric parameters** are dataclass fields with `metadata=dict(minimum=…, maximum=…,
  unit=…, doc=…)`. When there is no value, they show "Choose a value…" (one below the
  minimum), so the factory can reject unchosen thresholds.
- **Errors are not caught** inside the kit. Install a `sys.excepthook` that shows the
  traceback. Background workers should catch exceptions only at the thread boundary.
- **Layout version:** bump `ShellWindow.LAYOUT_VERSION` in a subclass when docks or
  toolbars change incompatibly, so stale saved layouts are ignored.
- **The guide's status comes from application state only,** so it never disagrees with
  the views.
