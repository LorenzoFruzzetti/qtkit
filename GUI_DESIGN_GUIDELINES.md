# Desktop GUI Design Guidelines (Python, Qt + pyqtgraph)

Last updated: 2026-10-08 · Lorenzo Fruzzetti
Live version: https://claude.ai/code/artifact/f4e468a6-747d-47bb-be2e-08d993779965

## Summary

Build the shell once with Qt, treat every command as data, and plug in whatever views the project needs: tables, forms, text, trees, plots or images.

- **Stack:** PySide6 Qt Widgets for the window and standard views; pyqtgraph only where the tool shows plots or images. Python 3.10 or newer, installed from a conda environment file.
- **Layers:** state, logic, controller, views. Only the controller changes state, and logic imports no Qt, so it is tested without a window.
- **Views are pluggable:** each kind of data is one view class behind a small interface, hosted in the central area, tabs or docks.
- **Commands as data:** every command is a `QAction` in one registry. Toolbars, menus and shortcuts are lists of action ids in a config file; user overrides are stored separately and editable in the app.
- **Files (one per window):** menu, drag-and-drop, recent list and command line all call one `open_path()`, which picks a loader by file type. Saves are atomic, and unsaved changes are tracked and confirmed.
- **Responsiveness:** slow work runs in `QThreadPool` workers that report through signals; views update in place instead of being rebuilt.
- **Reliability:** `QUndoStack` for edits, `QSettings` for window layout, and errors shown with their traceback, never swallowed.
- **Testing:** logic with plain pytest; the GUI with pytest-qt, headless, triggering actions directly.
- **Reference implementation:** `src/qtkit/` already implements the shell (commands, shortcut/toolbar editors, docks and saved layout, parameter forms, pipeline guide, DataFrame tables, test helpers). Copy it rather than rebuilding it; section 9 maps each point to its module.

## Purpose and scope

This is a reusable baseline for Python desktop tools that display data, let the user act on it, and open and save files. The data can be of any kind: tables, forms and parameters, text and logs, trees, time series, images, or custom views. Each kind is one view plugged into the same shell. Each new project copies these points and adds its own domain layer.

Status: a numbered set of draft points, meant to be refined. Each point states a decision and a short reason so it can be challenged.

In scope:

- Single-window desktop tools: data browsers, editors, review and annotation tools, control panels, batch-job launchers.
- Any mix of views: tables, forms, text, trees, plots, images.
- Buttons, menus and shortcuts the user can rearrange or rebind without editing code.
- Opening files through dialogs, drag-and-drop and recent-files lists.

Out of scope: web dashboards, multi-user apps, and anything needing a server.

## 1. Toolkit

Default stack: Qt Widgets through PySide6 for the window and all standard views, plus pyqtgraph when the tool shows plots or images. Qt supplies menus, toolbars, dialogs, docks, settings, and fast model-based tables and trees. pyqtgraph draws numpy arrays fast enough for live interaction, because it renders through Qt's GraphicsView instead of re-rendering a figure.

1.1. Use PySide6 (the official Qt binding, LGPL). Import Qt through `pyqtgraph.Qt` (`from pyqtgraph.Qt import QtCore, QtGui, QtWidgets`), so the same code also runs where only PyQt5/6 is installed.

1.2. Use Qt Widgets, not QML. Widgets are the better fit for tool windows with forms, tables and plots, and they need no second language.

1.3. Pick the widget by the kind of data:

| Data | Widget | Note |
| --- | --- | --- |
| Tables, lists | `QTableView` / `QListView` + a `QAbstractTableModel` | Views only ask the model for visible cells, so large tables stay fast; add `QSortFilterProxyModel` for sort and filter |
| Hierarchies | `QTreeView` + a model | Same model/view pattern |
| Parameters, settings | `QFormLayout` with spin boxes, combo boxes, check boxes | Generate the form from a parameter spec rather than writing each field by hand |
| Text, logs | `QPlainTextEdit` (read-only for logs) | Faster than `QTextEdit` for long text |
| Plots, time series, images | pyqtgraph `PlotWidget` / `ImageItem` | See 5.9-5.14 |
| Static figures for export | matplotlib | Never inside the interactive loop |

1.4. When pyqtgraph is used, set its global options once at startup, before any item is created: `pg.setConfigOptions(antialias=False)`, plus `imageAxisOrder="row-major"` when images are shown. Row-major matches numpy `[row, col]` indexing; the default is the transpose and silently swaps rows and columns.

1.5. Import Qt lazily, inside the GUI module or the function that builds the window. Pure logic and tests can then import the package without a display.

1.6. **Follow the OS light/dark mode.** Use Qt's standard palette and default style; from Qt 6.5 they follow the OS setting, and `QGuiApplication.styleHints().colorSchemeChanged` reports a switch while the app runs. If a platform style ignores dark mode, use the Fusion style. Never hard-code widget colours; read them from `palette()`. pyqtgraph does not follow the palette, so set its background and foreground from the palette at startup and again on each scheme change.

1.7. **Minimum versions:** Python 3.10, PySide6 6.5 (needed for 1.6), pyqtgraph 0.13, pandas 2.0.

Alternatives, and when they would win:

| Option | Pick it when | Cost |
| --- | --- | --- |
| PySide6 + pyqtgraph (default) | Images, traces, ROIs, forms; Windows/Linux/macOS desktop | Qt learning curve |
| napari | n-dimensional image viewing with layers is the whole app | Heavy dependency, its own plugin model |
| Dear PyGui | GPU-drawn live dashboards and debug panels | Non-native look, smaller widget set, immediate-mode style |
| VisPy | Millions of points or 3D volumes need OpenGL | Lower-level API |
| Tkinter | Tiny dialogs with no plots | Slow for image and plot updates |

## 2. Architecture

Keep state, logic and widgets in separate layers, so the logic can be tested without Qt and the UI can be rearranged without touching the logic.

```text
All input goes through the controller; only it changes state

  +------------------+  trigger  +------------------+   calls   +------------------+
  | User input       | --------> | Action registry  | --------> | Controller       |
  | buttons, menus,  |           | one QAction per  |           | one method per   |
  | shortcuts, drops,|           | command, layout  |           | intent, sole     |
  | mouse gestures   |           | read from config |           | writer of state  |
  +------------------+           +------------------+           +------------------+
           ^                              mutates  |                     | runs
           | user acts on it        +--------------+                     v
  +------------------+  signals  +------------------+           +------------------+
  | Views            | <-------- | State            |           | Logic + workers  |
  | tables, forms,   |           | dataclasses:     |           | pure functions,  |
  | plots, images;   |           | data, annota-    |           | loaders,         |
  | redraw from state|           | tions, dirty flag|           | no Qt imports    |
  +------------------+           +------------------+           +------------------+
```

Input never touches state directly: it becomes an action, the action calls the controller, and the view redraws when state signals a change.

2.1. **State** is plain Python: dataclasses holding the document (loaded data, annotations, current index, dirty flag). No Qt imports.

2.2. **Logic** is pure functions or classes that take state and return new values (transform, validate, load, save). No Qt imports. This layer carries the unit tests.

2.3. **Controller** owns the state and is the only code that mutates it. It exposes one method per user intent (`open_file`, `next_page`, `save`). Every button, menu item, shortcut and mouse gesture calls these methods; none mutates state directly.

2.4. **View** is the Qt layer: windows, docks, plot items. It reads state to redraw and forwards user input to the controller. It holds no business logic.

2.5. The controller tells the view to redraw through Qt signals (`stateChanged`, `fileOpened`) or a single `refresh()` call. Prefer one redraw path per area over many small ad-hoc updates; it keeps the display and the state from drifting apart.

2.6. Build the UI in one `build_ui()` method, broken into helpers per area (`_build_toolbar`, `_build_plot`, `_build_docks`). Write layouts in code rather than Qt Designer `.ui` files, unless a designer-heavy form justifies them.

2.7. Never block the event loop in a slot. Anything over roughly 100 ms goes to a worker (section 5).

2.8. Keep one entry function, `main()`, that builds the app, parses config, opens any files given, and runs `app.exec()`. Tests call the same building blocks without `exec()`.

2.9. **Views are pluggable.** Each kind of data is shown by one view class with a small interface: `refresh(state)` to redraw, and the action ids it contributes. The main window hosts views in its central area, tabs or docks, and knows nothing about what they show. A table viewer, a form editor and an image viewer differ only in which views they register.

2.10. Views that edit data (a cell in a table, a field in a form, a box on an image) report the edit to the controller; they never write to state themselves.

## 3. Configurable buttons and actions

Every command is a `QAction` declared in one table; buttons, menus, toolbars and shortcuts are views of that table. Changing a button then means editing data, not code, and the user can rebind or hide it at runtime.

3.1. **One action registry.** Each command is declared once with a stable id, label, default shortcut, icon, tooltip, the controller method it calls, and whether it is checkable. The registry builds one `QAction` per entry. Qt keeps every place an action appears in sync (enabled state, checked state, text).

```python
# Declarative action table: the only place a command is defined.
ACTIONS = [
    # id,            label,       default shortcut, controller method
    ("file.open",    "Open...",   "Ctrl+O",         "open_file_dialog"),
    ("file.save",    "Save",      "Ctrl+S",         "save"),
    ("nav.next",     "Next",      "Right",          "next_page"),
    ("nav.previous", "Previous",  "Left",           "previous_page"),
]
```

3.2. **Layout as data.** Toolbars and menus are lists of action ids in a JSON file shipped with the package. Adding, removing or reordering a button means editing that list. `"-"` stands for a separator.

```json
{
  "toolbars": {"main": ["file.open", "file.save", "-", "nav.previous", "nav.next"]},
  "menus": {"File": ["file.open", "file.save", "-", "app.quit"]},
  "shortcuts": {}
}
```

3.3. **User overrides on top of defaults.** Defaults live in the package's JSON file. The user's changes (shortcuts, toolbar contents, hidden actions) go to a second, human-readable JSON file with the same keys, in the user config folder (`QStandardPaths.AppConfigLocation`), applied after the defaults. Only changed keys are written, so new defaults in a later version still arrive. "Reset to defaults" deletes the override file, and "Open config folder" shows it.

3.4. **In-app editors (in v1).** A shortcuts dialog lists every action with a `QKeySequenceEdit` per row and flags conflicts (two actions on one key) before saving. A toolbar dialog offers available actions on the left and the toolbar's ordered list on the right. Both write only the overrides from 3.3.

3.5. **Shortcuts belong to actions, not to `keyPressEvent`.** A hand-written key handler duplicates the button wiring and forces focus workarounds (setting buttons to `NoFocus` so arrow keys reach the window). Add actions to the main window (`window.addAction(action)`) and choose the scope with `setShortcutContext` (`WindowShortcut` by default, `WidgetShortcut` for keys that only make sense in one view).

3.6. **Enabled state follows state.** One `update_actions()` method, called after every state change, sets each action's enabled and checked flags (for example, Save is disabled when nothing changed). Never disable buttons ad hoc in scattered handlers.

3.7. **Discoverability.** Tooltips show the current shortcut. A command palette (Ctrl+Shift+P: type to filter all actions by label) is planned for after v1; the registry already holds everything it needs.

3.8. **Project-specific commands** live in a per-project action module that registers its actions into the same registry at startup, with ids namespaced by the project (`myproject.export_csv`). There is no plugin discovery through entry points: the project's `main()` imports its module explicitly. The core GUI never imports project code.

## 4. Opening files

One file is open per window. All ways of opening a file (menu, toolbar, drag-and-drop, recent list, command line) end in one controller method, `open_path(path)`, which picks a loader by file type and replaces the current document, asking first if it has unsaved changes.

4.1. **Loader registry.** Map a file extension (or a folder test) to a loader function that returns the state object. A new format means one new registry entry, and the open dialog's filter string is generated from the registry. Loaders come in a core and an optional tier (see section 8).

```python
# Extension -> loader; the file dialog filter is built from these keys.
LOADERS = {
    ".csv": load_table,
    ".json": load_json,
    ".txt": load_text,
    ".tif": load_image,
}
```

4.2. **Dialogs.** Use `QFileDialog.getOpenFileName` for files and `getExistingDirectory` for folder-based datasets. Start the dialog in the last-used directory, remembered between sessions.

4.3. **Drag-and-drop.** Accept a file or folder dropped on the main window (`setAcceptDrops(True)`, `dragEnterEvent` checks `mimeData().hasUrls()`, `dropEvent` calls `open_path`). Reject unsupported types and drops of several files in `dragEnterEvent`, so the cursor shows refusal before the drop.

4.4. **Recent files.** Keep a capped list (for example 10) in `QSettings`, most recent first, deduplicated by resolved path. Rebuild the File > Open Recent submenu from it whenever it changes. Drop entries that no longer exist when the menu is shown, and offer "Clear list".

4.5. **Command line and editor runs.** `main()` accepts an optional path as a positional argument, and a `RUN_CONFIG` dict at the top of the entry script holds the same value, so the tool runs from the editor without flags. A CLI argument overrides the dict when given.

4.6. **Large inputs load in the background.** The loader runs in a worker (section 5) and reports progress; the window stays responsive and shows the first rows or frames as soon as they are available. Read lazily when the format allows it: chunked readers for tables, memory-mapped arrays (`np.load(mmap_mode="r")`), zarr or HDF5 for large arrays.

4.7. **Saving.** Write to a temporary file in the target folder, then rename over the destination (`os.replace`), so a crash never leaves a half-written file. Track a dirty flag, show it in the title bar (`setWindowModified`), and ask before closing or opening another file with unsaved changes.

## 5. Responsiveness and rendering speed

The main thread only draws and dispatches; loading and computing run elsewhere, and redraws update existing items instead of rebuilding them.

Background work:

5.1. Run short background tasks (load a file, compute a map) as a `QRunnable` on `QThreadPool.globalInstance()`. The worker gets a function and its arguments, and reports back through a small signals object (`result`, `error`, `progress`, `finished`) connected in the main thread.

5.2. Only the main thread touches widgets. Workers send data back through signals; the slot in the main thread updates the view.

5.3. Send immutable or copied data across threads (numpy arrays the worker no longer writes to, tuples, strings). Never share a mutable object that both sides modify.

5.4. Do not flood the event queue: throttle progress signals to a few per second, and coalesce rapid redraw requests with a single-shot `QTimer` (debounce) so a slider drag triggers one redraw per frame, not one per pixel.

5.5. Workers are `QThreadPool` threads only; no process pools. Threads do not speed up pure-Python loops (GIL), so heavy work inside a worker must be vectorised numpy (or numba), which releases the GIL. Work too heavy for that belongs in a separate command-line script, not in the GUI. Workers must be cancellable through a flag they check between chunks.

5.6. A worker's exception is sent through the `error` signal with its traceback and shown to the user; it is never swallowed (see 6.4).

Rendering, for every kind of view:

5.7. Create views once and update them in place. Rebuilding a widget or a model on every change is the most common cause of a sluggish UI.

5.8. Tables and trees: back the view with a model over the data (for example a DataFrame) and emit `dataChanged` for the cells that changed, rather than resetting the whole model. Never fill a `QTableWidget` item by item for more than a few hundred rows.

Plots and images (pyqtgraph):

5.9. Create plot items once and update them with `setData` / `setImage`. Do not clear and re-add items on every change.

5.10. Images: pass `float32`, `uint8` or `uint16` arrays in row-major order and set `levels` explicitly, so pyqtgraph skips automatic level sampling on every frame. Keep colour lookup tables at 256 entries or fewer.

5.11. Lines: pass numpy arrays, not lists; use 1 px pens; turn antialiasing off; enable `setDownsampling(auto=True, method="peak")` and `setClipToView(True)` for long traces; call `setSkipFiniteCheck(True)` when the data has no NaN.

5.12. Pre-build pens and brushes once (`pg.mkPen`) instead of passing colour strings on every update.

5.13. Never call `ImageItem.setRect` before the image is set: it scales by the current image size, which is 1x1 when no image exists yet. Position with `setPos` or set the image first.

5.14. Precompute display-ready data (downsampled arrays, aggregated tables, summary statistics) once and cache them on disk when the same dataset is reopened often.

## 6. Persistence, undo and errors

The window remembers how the user left it, every edit can be undone, and every error reaches the user with its traceback.

6.1. **Settings.** Use `QSettings(organization, application)` only for opaque window state: geometry and dock layout (`saveGeometry`/`saveState` on close, restore on start), last directory, recent files. Anything a user might want to read or edit (shortcuts, toolbar layout) lives in the readable JSON override file from 3.3. Domain parameters stay in the project's own config file.

6.2. **Version the stored layout.** Pass a version number to `saveState`/`restoreState` and bump it when docks or toolbars change, so an old saved layout is ignored instead of restoring a broken one.

6.3. **Undo/redo with `QUndoStack`.** Each edit is a `QUndoCommand` that calls the controller to apply (`redo`) and revert (`undo`) it. Merge continuous gestures (a drag, repeated nudges) with `id()` and `mergeWith()`, so one drag is one undo step. The stack's `cleanChanged` signal drives the dirty flag and the Save action's enabled state; its undo/redo actions go into the registry from section 3.

6.4. **Errors surface, never disappear.** Install a `sys.excepthook` that logs the full traceback and shows it in a message box, then leaves the app running in a known state. No silent `except: pass`; validation failures raise with a message naming the file and the field.

6.5. **Refuse visibly.** When an action cannot run (out-of-range edit, invalid file), say why in the status bar or a dialog and leave the state unchanged, rather than clamping or correcting silently.

6.6. **Logging.** Use the `logging` module with one logger per module. Write to a rotating log file in the user's app-data folder and mirror warnings and above to the status bar. The help menu offers "Open log folder".

6.7. **Provenance.** Every saved output records what produced it: input path, app version, parameters, timestamp.

## 7. Testing, running and packaging

Most tests never open a window; the few that do run headless and drive the same actions the user triggers.

7.1. Test the logic and controller layers with plain pytest. They import no Qt (2.1-2.3), so this is most of the coverage.

7.2. Test the view with `pytest-qt`: the `qtbot` fixture creates the application, registers widgets (`qtbot.addWidget`) and waits for signals (`qtbot.waitSignal`). Pin the binding with `qt_api = pyside6` in the pytest config.

7.3. Run GUI tests headless with `QT_QPA_PLATFORM=offscreen`. Focus-dependent behaviour can differ offscreen; trigger actions directly (`action.trigger()`) rather than simulating key presses where possible.

7.4. Test the registry itself: every action id in the toolbar/menu config exists, no two actions share a default shortcut, and every action's controller method exists. With qtkit this is one call: `qtkit.testing.check_commands(ACTIONS, LAYOUT, Controller)`.

7.5. Provide a debugger launch configuration for the GUI entry point, and a minimal example dataset in `examples/` so the GUI opens with something to show.

7.6. Package as a console/GUI entry point in `pyproject.toml` (`[project.gui-scripts]`). Build a standalone executable (PyInstaller or Nuitka) only when users have no Python environment.

7.7. **Environment.** Ship a conda `environment.yml` with the minimum versions from 1.7 (plus `pytest` and `pytest-qt`), and a short install section in the README: create the environment, install the package in editable mode, and launch the GUI.

```bash
conda env create -f environment.yml
conda run -n <env_name> pip install -e .
conda run -n <env_name> python -m <package>
```

## 8. Decisions and open questions

Decided (2026-10-07):

| Question | Decision | Applied in |
| --- | --- | --- |
| Config format for toolbar/menu layout | JSON | 3.2 |
| Where user overrides live | Readable JSON file in the user config folder, not `QSettings` | 3.3, 6.1 |
| In-app toolbar editor | In v1 | 3.4 |
| One file or several per window | One file per window | 4 |
| Plugin mechanism | Per-project action modules, no entry points | 3.8 |
| Command palette | After v1 | 3.7 |
| Background workers | `QThreadPool` only | 5.5 |
| Theming | Follow the OS light/dark mode | 1.6 |
| Minimum versions | Python 3.10, PySide6 6.5, pyqtgraph 0.13; conda `environment.yml` + install README | 1.7, 7.7 |
| Default file types | Core and optional loader tiers, as in the table below | 4.1, 8 |
| pandas | Core dependency: CSV/TSV loading and DataFrame-backed tables | 1.7, 5.8 |
| Reuse across projects | Copy the self-contained `src/qtkit/` folder; generic fixes go back into it with a test (decided 2026-10-08) | 9 |
| Pipeline guide | Every multi-step tool shows its workflow as a guide dock with live status and per-step help | 9.2 |

**Loader tiers.** Every format the core can open adds a dependency to every project that uses it, so loaders come in two tiers:

| Tier | Formats | Extra dependency |
| --- | --- | --- |
| Core, always available | `.json`, `.csv`/`.tsv`, `.txt`/`.log`, `.npy`/`.npz`, `.png`/`.jpg` | None beyond Python, numpy, pandas and Qt (images load through `QImage`) |
| Optional, added by a project's action module | `.tif` (tifffile), `.xlsx` (openpyxl), `.h5` (h5py), `.parquet` (pyarrow), `.zarr` (zarr) | One package each, listed in that project's `environment.yml` |

## 9. Reference implementation: qtkit

`src/qtkit/` is a small, self-contained package that implements the application-independent
part of these guidelines. A new project copies the folder unchanged (with this file), then
writes only its state, logic, controller, views and data tables. `src/qtkit/README.md`
holds the drop-in checklist (pyproject entries, install and test commands);
`python -m qtkit.demo` is the smallest complete application.

9.1. **What the kit implements.**

| Guideline points | qtkit module | Project supplies |
| --- | --- | --- |
| 1.1 Qt imported through `pyqtgraph.Qt`, PySide6 preferred | `qt.py` | — |
| 3.1–3.3, 3.5, 3.7 action table, layout as JSON, user overrides, tooltips with shortcuts | `actions.py` (`ActionSpec`, `ActionRegistry`) | `ACTIONS`, default layout dict, controller methods |
| 3.4 in-app shortcut and toolbar editors | `command_dialogs.py` | — |
| 2.9 views hosted in docks; 6.x window geometry and dock layout in `QSettings`; View menu; reset layout | `window.py` (`ShellWindow`) | views, `update_actions()` (3.6) |
| Parameter forms generated from the config dataclass, required thresholds without defaults | `params.py` (`ParameterDialog`, `FieldHint`) | config dataclass with numeric field metadata, validating factory |
| 5.8 DataFrame-backed tables, numeric sorting | `tables.py` (`DataFrameModel`) | — |
| 7.2–7.4 headless tests, isolated settings, registry check | `testing.py` | project tests |

9.2. **Pipeline guide.** A tool whose analysis has ordered steps shows them in a
"Pipeline guide" dock (`ShellWindow.add_guide`). Each `Step` has a title numbered like
the matching action labels ("3 · Build backgrounds"), the id of the action that performs
it, and detailed HTML help: what the step does, how to do it, its inputs and outputs,
the parameters that matter, and troubleshooting. Status (✓ done, ▶ current, ○ to do)
comes from a pure `progress(state)` function, so it cannot disagree with the views.
"Go to this step" triggers the step's action, or explains which earlier step is missing.

9.3. **Still written per project**, following the sections above: workers and
cancellation (5), file opening, recent files and drag-and-drop (4), undo commands, the
error dialog, the exception hook and logging (6). The host application's GUI package
should add those pieces around the reusable components provided here.

## Sources

- [pyqtgraph PlotDataItem: performance notes](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html)
- [pyqtgraph ImageItem: setImage performance](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/imageitem.html)
- [Qt for Python: Application example (actions, menus, settings, maybe_save)](https://doc.qt.io/qtforpython-6.8/examples/example_widgets_mainwindows_application.html)
- [Qt for Python: QAction](https://doc.qt.io/qtforpython/PySide6/QtGui/QAction.html)
- [Qt for Python: QUndoCommand (id, mergeWith)](https://doc.qt.io/qtforpython/PySide6/QtGui/QUndoCommand.html)
- [Python GUIs: multithreading do's and don'ts](https://www.pythonguis.com/faq/multi-threading-dos-and-donts)
- [PenguinTutor: PySide6 QThreadPool worker pattern](https://www.penguintutor.com/programming/pyside6-qthreadpool)
- [pytest-qt introduction](https://pytest-qt.readthedocs.io/en/latest/intro.html)
- [PyMoDAQ: action managers for toolbars](https://pymodaq.cnrs.fr/en/dev/developer_folder/managers.html)
