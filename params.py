"""Parameter form generated from a dataclass; validation stays in the application.

Numeric fields are recognised by dataclass field metadata with ``minimum`` and
``maximum`` (optional ``unit`` and ``doc``, shown as suffix and tooltip)::

    threshold: int = field(metadata=dict(doc="Foreground cutoff", unit="px",
                                         minimum=0, maximum=255))

Such fields start empty ("Choose a value…") when they have no value, so a user must
choose dataset-sensitive thresholds deliberately. Everything else is configured with
``FieldHint``: folders/files get a Browse button, choices a combo box, lists a
comma-separated line edit. The collected dictionary is passed to ``factory``, which
builds (and validates) the application's object; its exceptions are not caught.
"""

from __future__ import annotations
from dataclasses import MISSING, dataclass, fields
from .qt import QtWidgets


@dataclass(frozen=True)
class FieldHint:
    # auto: checkbox for bools, list for tuples/lists, otherwise text.
    kind: str = "auto"  # auto | text | dir | file | choice | list | int
    choices: tuple[str, ...] = ()  # options for kind="choice"
    placeholder: str = ""  # grey text shown in an empty line edit
    decimals: int = 2  # digits for float spin boxes
    optional: bool = False  # empty text becomes None
    read_only: bool = False  # shown but not editable (also disables Browse)


class ParameterDialog(QtWidgets.QDialog):
    """Modal form; after exec() == Accepted, ``value`` holds ``factory(values)``."""

    def __init__(self, parent, cls, values, factory, hints=None, title="Parameters", note=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 700)
        self.factory = factory
        self.hints = hints or {}
        self.value = None
        self.widgets = {}
        self.kinds = {}
        layout = QtWidgets.QVBoxLayout(self)
        if note:
            label = QtWidgets.QLabel(note)
            label.setWordWrap(True)
            layout.addWidget(label)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(content)
        for item in fields(cls):
            hint = self.hints.get(item.name, FieldHint())
            value = values.get(item.name, item.default if item.default is not MISSING else None)
            widget, kind = self.make_widget(item, hint, value)
            self.widgets[item.name] = widget
            self.kinds[item.name] = kind
            label = item.name.replace("_", " ").capitalize()
            if item.default is MISSING and item.default_factory is MISSING:
                label += " *"
            if kind in {"dir", "file"}:
                # Path fields get a Browse button next to the line edit.
                row = QtWidgets.QWidget()
                row_layout = QtWidgets.QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(widget)
                browse = QtWidgets.QPushButton("Browse…")
                browse.clicked.connect(lambda checked=False, key=item.name: self.browse(key))
                browse.setEnabled(not hint.read_only)
                row_layout.addWidget(browse)
                form.addRow(label, row)
            else:
                form.addRow(label, widget)
            if hint.read_only and kind in {"bool", "choice", "number"}:
                widget.setEnabled(False)
            elif hint.read_only:
                widget.setReadOnly(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def make_widget(self, item, hint, value):
        """Return (widget, kind) for one dataclass field."""
        metadata = item.metadata
        if "minimum" in metadata and "maximum" in metadata:
            floating = item.type in (float, "float")
            widget = QtWidgets.QDoubleSpinBox() if floating else QtWidgets.QSpinBox()
            minimum = metadata["minimum"]
            # One step below the minimum is the "not chosen yet" sentinel.
            widget.setRange(minimum - 1, metadata["maximum"])
            if floating:
                widget.setDecimals(hint.decimals)
            widget.setSpecialValueText("Choose a value…")
            widget.setValue(minimum - 1 if value is None else value)
            if metadata.get("unit"):
                widget.setSuffix(f" {metadata['unit']}")
            widget.setToolTip(metadata.get("doc", ""))
            return widget, "number"
        kind = hint.kind
        if kind == "auto":
            kind = (
                "bool"
                if isinstance(value, bool)
                else "list"
                if isinstance(value, (tuple, list))
                else "text"
            )
        if kind == "bool":
            widget = QtWidgets.QCheckBox()
            widget.setChecked(bool(value))
            return widget, kind
        if kind == "choice":
            widget = QtWidgets.QComboBox()
            widget.addItems(list(hint.choices))
            widget.setCurrentText(str(value))
            return widget, kind
        text = (
            ", ".join(map(str, value))
            if isinstance(value, (tuple, list))
            else ""
            if value is None
            else str(value)
        )
        widget = QtWidgets.QLineEdit(text)
        widget.setPlaceholderText(hint.placeholder)
        if metadata.get("doc"):
            widget.setToolTip(metadata["doc"])
        return widget, kind

    def browse(self, key):
        widget = self.widgets[key]
        if self.kinds[key] == "file":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select file", widget.text())
        else:
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", widget.text())
        if path:
            widget.setText(path)

    def collect(self) -> dict:
        """Convert widget contents to plain Python values keyed by field name."""
        values = {}
        for key, widget in self.widgets.items():
            kind = self.kinds[key]
            hint = self.hints.get(key, FieldHint())
            if kind == "number":
                values[key] = widget.value()
            elif kind == "bool":
                values[key] = widget.isChecked()
            elif kind == "choice":
                values[key] = widget.currentText()
            else:
                text = widget.text().strip()
                if hint.optional and not text:
                    values[key] = None
                elif kind == "list":
                    values[key] = tuple(part.strip() for part in text.split(","))
                elif kind == "int":
                    values[key] = int(text)
                else:
                    values[key] = text
        return values

    def validate_and_accept(self):
        # factory errors propagate to the application's error dialog; the form stays open.
        self.value = self.factory(self.collect())
        self.accept()
