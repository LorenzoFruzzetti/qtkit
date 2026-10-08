"""Headless test helpers. Import the fixtures in a conftest.py (see tests/conftest.py here).

Set ``QT_QPA_PLATFORM=offscreen`` (e.g. in conftest.py) before Qt is imported.
"""

from __future__ import annotations
import pytest
from .qt import QtCore


def isolated_settings(folder):
    """QSettings in an INI file under ``folder``, never the user's real preferences."""
    return QtCore.QSettings(str(folder / "settings.ini"), QtCore.QSettings.IniFormat)


def check_commands(specs, default_layout, handler_class):
    """Assert unique ids, a valid default layout and a handler method for every action."""
    from .actions import validate_layout

    validate_layout(default_layout, specs)
    assert len({spec[0] for spec in specs}) == len(specs), "duplicate action ids"
    missing = [spec[3] for spec in specs if not hasattr(handler_class, spec[3])]
    assert not missing, f"handler lacks methods: {missing}"


@pytest.fixture
def qtkit_settings(tmp_path):
    """Isolated QSettings for a window under test."""
    return isolated_settings(tmp_path)


@pytest.fixture
def qtkit_config_dir(tmp_path):
    """Throwaway folder for the window's layout.json overrides."""
    return tmp_path / "ui-config"
