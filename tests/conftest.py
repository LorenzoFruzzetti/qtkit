"""Self-contained kit test setup, so these tests run in any project that copies qtkit."""

import os

# Headless Qt must be selected before any Qt module is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtkit.testing import qtkit_config_dir, qtkit_settings  # noqa: E402,F401  (fixtures)
