"""Question view registry: C can add a renderer without editing learning rules."""
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLabel,
                               QRadioButton, QVBoxLayout, QWidget)

from app.models import Question


class AnswerWidget(QWidget):
    def selected(self) -> tuple[str, ...]:
        raise NotImplementedError


class ChoiceWidget(AnswerWidget):
    def __init__(self, question: Question):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.buttons = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(question.kind == "single_choice")
        for option in question.options:
            row = QHBoxLayout()
            button = QRadioButton() if question.kind == "single_choice" else QCheckBox()
            button.setAccessibleName(option.text)
            button.setFixedWidth(32)
            self.group.addButton(button)
            label = QLabel(option.text)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(button)
            row.addWidget(label, 1)
            layout.addLayout(row)
            self.buttons.append((option.id, button))

    def selected(self) -> tuple[str, ...]:
        return tuple(key for key, button in self.buttons if button.isChecked())


class QuestionViewRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[Question], AnswerWidget]] = {}

    def register(self, kind: str, factory: Callable[[Question], AnswerWidget]) -> None:
        if kind in self._factories:
            raise ValueError(f"题目视图重复注册：{kind}")
        self._factories[kind] = factory

    def supports(self, kind: str) -> bool:
        return kind in self._factories

    def build(self, question: Question) -> AnswerWidget:
        return self._factories[question.kind](question)


def default_views() -> QuestionViewRegistry:
    registry = QuestionViewRegistry()
    registry.register("single_choice", ChoiceWidget)
    registry.register("multiple_choice", ChoiceWidget)
    return registry
