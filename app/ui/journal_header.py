"""Compact journal tools and a progress dial driven by the learning summary."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from app.models import LearningSummary


def _icon(kind: str) -> QIcon:
    pixmap = QPixmap(36, 36)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#68523b'), 1))
    if kind == 'book':
        path = QPainterPath(QPointF(1, 3))
        for x, y in [(5, 2), (9, 4), (13, 2), (17, 3), (17, 15),
                     (13, 14), (9, 16), (5, 14), (1, 15), (1, 3)]:
            path.lineTo(x, y)
        painter.drawPath(path)
        painter.drawLine(9, 4, 9, 16)
    elif kind == 'info':
        painter.drawEllipse(QRectF(2, 2, 14, 14))
        painter.drawPoint(9, 6)
        painter.drawLine(9, 8, 9, 13)
    elif kind == 'music':
        painter.drawLine(8, 4, 15, 2)
        painter.drawLine(8, 4, 8, 13)
        painter.drawLine(15, 2, 15, 11)
        painter.drawEllipse(QRectF(4, 12, 4, 3))
        painter.drawEllipse(QRectF(11, 10, 4, 3))
    else:
        painter.drawArc(QRectF(2, 2, 14, 14), 40 * 16, 290 * 16)
        path = QPainterPath(QPointF(13, 1))
        path.lineTo(16, 5)
        path.lineTo(11, 6)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class JournalTools(QFrame):
    def __init__(self, has_music: bool = False):
        super().__init__()
        self.setObjectName('journalTools')
        self.setAccessibleName('学习工具')
        self.setFixedSize(480 if has_music else 383, 42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 0, 13, 0)
        layout.setSpacing(8)
        buttons = []
        entries = [('音乐：开', 'music')] if has_music else []
        entries += [('学习回顾', 'book'), ('使用与来源', 'info'), ('重新出发', 'reset')]
        for i, (text, kind) in enumerate(entries):
            if i:
                divider = QFrame()
                divider.setObjectName('journalToolDivider')
                divider.setFixedSize(1, 15)
                layout.addWidget(divider)
            button = QToolButton()
            button.setText(text)
            button.setIcon(_icon(kind))
            button.setIconSize(QSize(18, 18))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setAccessibleName(text)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(34)
            layout.addWidget(button, 1)
            buttons.append(button)
        self.music_button = buttons.pop(0) if has_music else None
        self.summary_button, self.about_button, self.reset_button = buttons


class _ProgressDial(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(44, 44)
        self.completed = 0
        self.total = 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, 42, 42)
        painter.setPen(QPen(QColor('#d9c5a3'), 1.2))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor('#983e31'), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = round(360 * 16 * self.completed / max(1, self.total))
        if span:
            painter.drawArc(rect, 90 * 16, -span)
        font = QFont('SimSun')
        font.setPixelSize(19)
        painter.setFont(font)
        painter.setPen(QColor('#903c31'))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.completed))


class JournalProgress(QWidget):
    def __init__(self):
        super().__init__()
        self.setAccessibleName('学习进度')
        self.setFixedSize(164, 48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.dial = _ProgressDial()
        layout.addWidget(self.dial)
        labels = QVBoxLayout()
        labels.setContentsMargins(0, 1, 0, 1)
        labels.setSpacing(3)
        self.completed_label = QLabel()
        self.completed_label.setObjectName('journalProgressCount')
        self.correct_label = QLabel()
        self.correct_label.setObjectName('journalProgressCorrect')
        labels.addWidget(self.completed_label)
        labels.addWidget(self.correct_label)
        layout.addLayout(labels)

    def refresh(self, summary: LearningSummary) -> None:
        self.completed_label.setText(f'已完成 {summary.completed_nodes} / {summary.total_nodes} 站')
        self.correct_label.setText(f'首次答对 {summary.first_correct} / {summary.total_questions}')
        self.setAccessibleDescription(self.completed_label.text() + '；' + self.correct_label.text())
        self.setToolTip(self.accessibleDescription())
        self.dial.completed = summary.completed_nodes
        self.dial.total = summary.total_nodes
        self.dial.update()
