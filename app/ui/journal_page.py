"""Layered paper shell and chapter page, with reading separate from fixed actions."""
from html import escape

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from app.models import Node


def _text(value: str, role: str) -> QLabel:
    item = QLabel(value)
    item.setObjectName(role)
    item.setWordWrap(True)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return item


def _rule() -> QFrame:
    rule = QFrame()
    rule.setObjectName('journalRule')
    rule.setFixedHeight(1)
    return rule


class PaperPanel(QWidget):
    """Shared paper backdrop for chapters, questions, review and sources."""

    TOP_GAP = 16

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Soft edge strokes avoid nested graphics effects in entrance snapshots.
        for spread, alpha in [(5, 5), (3, 8), (1, 12)]:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(83, 56, 30, alpha), spread * 2))
            painter.drawRoundedRect(QRectF(8, self.TOP_GAP + 6, self.width() - 17,
                                           self.height() - self.TOP_GAP - 12), 4, 4)
        painter.setPen(QPen(QColor('#cab18b'), .7))
        painter.setBrush(QColor('#e9dabd'))
        painter.drawRoundedRect(QRectF(16, self.TOP_GAP + 10, self.width() - 18,
                                       self.height() - self.TOP_GAP - 12), 3, 3)
        painter.setBrush(QColor('#fbf2df'))
        painter.drawRoundedRect(QRectF(6, self.TOP_GAP + .5, self.width() - 18,
                                       self.height() - self.TOP_GAP - 11), 3, 3)
        painter.setPen(QPen(QColor('#d6bea0'), 1))
        painter.drawLine(14, self.TOP_GAP + 1, 14, self.height() - 12)


class ChapterPage(QWidget):
    learn_requested = Signal()
    quiz_requested = Signal()
    advance_requested = Signal()

    def heightForWidth(self, width: int) -> int:
        # The inner scroll area owns long prose. Do not let its preferred height
        # make the enclosing page scroll the fixed chapter action off screen.
        return self.minimumSizeHint().height()

    def __init__(self, node: Node, index: int, total: int, *,
                 learned: bool, completed: bool, can_quiz: bool, quiz_note: str = ''):
        super().__init__()
        self.setObjectName('chapterPage')
        self.setAccessibleName(f'第{index + 1}站，共{total}站：{node.name}')
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 16)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(18)
        ribbon = QFrame()
        ribbon.setObjectName('chapterRibbon')
        ribbon.setFixedSize(40, 82)
        ribbon_layout = QVBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(0, 17, 0, 9)
        ribbon_layout.setSpacing(7)
        number = _text(f'{index + 1:02}', 'chapterNumber')
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setWordWrap(False)
        ribbon_layout.addWidget(number)
        tag = _text('已完成' if completed else '出发' if index == 0 else '学习', 'chapterTag')
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ribbon_layout.addWidget(tag)
        header.addWidget(ribbon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 20, 0, 7)
        titles.setSpacing(10)
        title = _text(node.name, 'journalChapterTitle')
        titles.addWidget(title)
        titles.addWidget(_text(node.time, 'journalDate'))
        header.addLayout(titles, 1)
        layout.addLayout(header)
        layout.addSpacing(14)
        layout.addWidget(_text(node.place, 'journalPlace'))
        layout.addSpacing(17)
        layout.addWidget(_rule())
        layout.addSpacing(14)

        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName('journalReadingArea')
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setMinimumHeight(24)
        body = QWidget()
        body.setObjectName('journalBody')
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 3, 4)
        body_layout.setSpacing(0)
        body_layout.addWidget(_text('历史记事', 'journalSection'))
        body_layout.addSpacing(10)
        event_text = _text('', 'journalEvent')
        event_text.setTextFormat(Qt.TextFormat.RichText)
        event_text.setText('<p style="line-height:140%; margin:0">' +
                           escape(node.event).replace('\n', '<br>') + '</p>')
        event_text.setAccessibleName(node.event)
        body_layout.addWidget(event_text)
        body_layout.addSpacing(22)
        body_layout.addWidget(_rule())
        body_layout.addSpacing(13)
        spirit_row = QHBoxLayout()
        spirit_row.setSpacing(16)
        spirit_row.addWidget(_text('精神内核', 'journalSmallSection'), 0, Qt.AlignmentFlag.AlignTop)
        spirit_row.addWidget(_text(node.spirit, 'journalSpirit'), 1)
        body_layout.addLayout(spirit_row)
        body_layout.addSpacing(12)

        links = QHBoxLayout()
        self.modern_toggle = self._toggle('新程对照')
        self.sources_toggle = self._toggle('史料出处')
        links.addWidget(self.modern_toggle)
        links.addStretch()
        links.addWidget(self.sources_toggle)
        body_layout.addLayout(links)
        self.modern_text = _text(node.modern, 'journalDetail')
        self.sources_text = _text('\n'.join(node.sources), 'journalDetail')
        self.quiz_note = _text(quiz_note, 'journalDetail')
        for item in (self.modern_text, self.sources_text, self.quiz_note):
            item.hide()
            body_layout.addWidget(item)
        self.modern_toggle.toggled.connect(self.modern_text.setVisible)
        self.sources_toggle.toggled.connect(self.sources_text.setVisible)
        self.sources_toggle.toggled.connect(lambda checked: self.quiz_note.setVisible(checked and bool(quiz_note)))
        body_layout.addStretch()
        self.body_scroll.setWidget(body)
        self._expanded_target: QLabel | None = None
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._reveal_expansion)
        self.modern_toggle.toggled.connect(lambda checked: self._queue_reveal(self.modern_text, checked))
        self.sources_toggle.toggled.connect(lambda checked: self._queue_reveal(self.sources_text, checked))
        layout.addWidget(self.body_scroll, 1)
        layout.addSpacing(14)

        self.primary_button = QPushButton()
        self.primary_button.setObjectName('journalPrimary')
        self.primary_button.setMinimumHeight(40)
        self.primary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quiz_button = None
        if completed:
            self.primary_button.setText('查看学习回顾 · 领取徽章  →' if index == total - 1 else '继续前进 · 下一站  →')
            self.primary_button.clicked.connect(self.advance_requested)
        elif can_quiz:
            self.primary_button.setText('继续答题  →')
            self.primary_button.clicked.connect(self.quiz_requested)
            self.quiz_button = self.primary_button
        else:
            self.primary_button.setText('开始本段学习  →')
            self.primary_button.clicked.connect(self.learn_requested)
        layout.addWidget(self.primary_button)
        self.learn_button = self.primary_button
        if learned or can_quiz or completed:
            layout.addSpacing(7)
            actions = QHBoxLayout()
            self.learn_button = self._link('重新观看本段学习')
            self.learn_button.clicked.connect(self.learn_requested)
            actions.addWidget(self.learn_button)
            actions.addStretch()
            if completed:
                self.quiz_button = self._link('复习本段题目')
                self.quiz_button.clicked.connect(self.quiz_requested)
                actions.addWidget(self.quiz_button)
            layout.addLayout(actions)

    def _queue_reveal(self, target: QLabel, expanded: bool) -> None:
        if expanded:
            self._expanded_target = target
            # Let Qt finish wrapping the newly shown prose before scrolling.
            self._reveal_timer.start(0)

    def _reveal_expansion(self) -> None:
        if self._expanded_target is not None and self._expanded_target.isVisible():
            self.body_scroll.ensureWidgetVisible(self._expanded_target, 0, 12)

    @staticmethod
    def _link(text: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setObjectName('journalLink')
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    @classmethod
    def _toggle(cls, text: str) -> QToolButton:
        button = cls._link(text + '  ›')
        button.setCheckable(True)
        button.setAccessibleName('展开或收起' + text)
        button.toggled.connect(lambda checked: button.setText(text + ('  收起' if checked else '  ›')))
        return button
