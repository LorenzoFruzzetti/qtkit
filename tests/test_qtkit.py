"""Reusable GUI kit, exercised through the application-independent example."""

import pytest

pytest.importorskip("PySide6")
from qtkit import FieldHint, ParameterDialog
from qtkit import demo
from qtkit.testing import check_commands


def test_example_commands_are_consistent():
    check_commands(demo.ACTIONS, demo.LAYOUT, demo.Controller)


def test_parameter_dialog_builds_and_parses_fields(qtbot):
    dialog = ParameterDialog(
        None, demo.Settings, {"labels": ("x", "y")}, demo.make_settings,
        {"data_folder": FieldHint("dir", read_only=True)},
    )
    qtbot.addWidget(dialog)
    # Required thresholds start at the "Choose a value…" sentinel, so the factory rejects them.
    with pytest.raises(ValueError, match="rows"):
        dialog.validate_and_accept()
    dialog.widgets["rows"].setValue(3)
    dialog.widgets["labels"].setText("p, q , r")
    dialog.validate_and_accept()
    assert dialog.value == demo.Settings("", 3, 1.0, ("p", "q", "r"))
    assert dialog.widgets["data_folder"].isReadOnly()


def test_shell_guide_docks_and_overrides(qtbot, qtkit_settings, qtkit_config_dir):
    window = demo.DemoWindow(qtkit_settings, qtkit_config_dir)
    qtbot.addWidget(window)
    window.show()
    assert window.guide.steps.currentRow() == 0
    # Step 2 is not available before parameters: the guide explains instead of running.
    window.go_to_step("run")
    assert "not available" in window.statusBar().currentMessage()
    window.controller.state.settings = demo.Settings(rows=4)
    window.update_actions()
    window.go_to_step("run")
    assert window.model.rowCount() == 4
    assert window.guide.steps.currentRow() == 2
    # Docks move and come back with Reset window layout.
    window.docks["notes"].setFloating(True)
    window.reset_window_layout()
    assert not window.docks["notes"].isFloating()
    # Shortcut overrides persist separately and reset cleanly.
    window.registry.save_overrides("shortcuts", {"app.run": "Ctrl+Alt+R"})
    window.build_commands()
    assert window.registry.actions["app.run"].shortcut().toString() == "Ctrl+Alt+R"
    with pytest.raises(ValueError, match="conflict"):
        window.registry.save_overrides("shortcuts", {"app.run": "Ctrl+Q"})
    window.reset_commands()
    assert window.registry.actions["app.run"].shortcut().toString() == "Ctrl+R"
    window.close()
