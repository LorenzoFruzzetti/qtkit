"""Pipeline guide: ordered workflow steps with live status and detailed help.

The application supplies:
  - ``steps``: a sequence of ``Step``;
  - ``progress(state)``: one ``(done, detail)`` pair per step, computed from the
    application state only, so the guide never stores progress of its own;
  - ``go(key)``: what "Go to this step" does (``ShellWindow.go_to_step`` by default).
"""

from __future__ import annotations
from typing import NamedTuple
from .qt import QtCore, QtWidgets


class Step(NamedTuple):
    key: str  # stable identifier passed to go(key)
    title: str  # list text, e.g. "1 · Open data"
    action: str | None  # action id triggered by "Go to this step"; None = window handles it
    help_html: str  # detailed explanation shown when the step is selected


class PipelineGuideView(QtWidgets.QWidget):
    """Step list with status marks; selecting a step shows its detailed explanation."""

    action_ids = ()

    def __init__(self, steps, progress, go, intro="Follow the steps in order. Click a step for details."):
        super().__init__()
        self.steps_data = tuple(steps)
        self.progress = progress
        self.go = go
        self.current = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(intro))
        self.steps = QtWidgets.QListWidget()
        self.steps.setWordWrap(True)
        for step in self.steps_data:
            self.steps.addItem(step.title)
        self.steps.currentRowChanged.connect(self.show_step)
        self.details = QtWidgets.QTextBrowser()
        self.details.setOpenExternalLinks(False)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.steps)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)
        self.go_button = QtWidgets.QPushButton("Go to this step")
        self.go_button.clicked.connect(lambda: self.go(self.steps_data[self.steps.currentRow()].key))
        layout.addWidget(self.go_button)
        self.steps.setCurrentRow(0)

    def show_step(self, row):
        self.details.setHtml(self.steps_data[row].help_html)

    def refresh(self, state):
        progress = self.progress(state)
        # The current step is the first unfinished one (the last one if all are done).
        current = next(
            (i for i, (done, _) in enumerate(progress) if not done), len(progress) - 1
        )
        for i, (step, (done, detail)) in enumerate(zip(self.steps_data, progress)):
            item = self.steps.item(i)
            mark = "✓" if done else "▶" if i == current else "○"
            item.setText(f"{mark}  {step.title}\n      {detail}")
            font = item.font()
            font.setBold(i == current)
            item.setFont(font)
        # Follow the user's progress, but keep a step they clicked until progress changes.
        if current != self.current:
            self.current = current
            self.steps.setCurrentRow(current)
        self.go_button.setEnabled(not getattr(state, "busy", False))
