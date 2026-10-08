"""Reusable PySide6 GUI building blocks: commands, docks, parameters, pipeline guide.

Application-independent and self-contained: copy this folder into another project's src/.
See README.md here; run the demo with ``python -m qtkit.demo``.
"""

from .actions import ActionRegistry, ActionSpec, validate_layout
from .guide import PipelineGuideView, Step
from .params import FieldHint, ParameterDialog
from .tables import DataFrameModel
from .window import ShellWindow

__all__ = [
    "ActionRegistry",
    "ActionSpec",
    "DataFrameModel",
    "FieldHint",
    "ParameterDialog",
    "PipelineGuideView",
    "ShellWindow",
    "Step",
    "validate_layout",
]
