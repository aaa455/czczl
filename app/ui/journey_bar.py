"""A parchment journey track with accessible, independently clickable stations."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QScrollArea, QWidget

from app.learning import LearningService
from app.models import Node


RED = '#983e31'
INK = '#684a34'
MUTED = '#94846c'


def _font(size: int, bold: bool = False) -> QFont:
    font = QFont('Microsoft YaHei UI')
    font.setPixelSize(size)
    font.setBold(bold)
    return font


class StationButton(QAbstractButton):
    """Use a real button for focus and activation, without a rectangular skin."""

    def __init__(self, node: Node, index: int, parent: QWidget):
        super().__init__(parent)
        self.node_id = node.id
        self.state = 'locked'
        self.setText(node.short_name)
        self.setFont(_font(14))
        self.setAccessibleName(f'查看第{index + 1}站：{node.name}')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(max(112, self.fontMetrics().horizontalAdvance(node.short_name) + 24))
        self.setFixedHeight(88)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, 21)
        if self.state == 'completed':
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(RED))
            painter.drawEllipse(center, 7.5, 7.5)
            check = QPainterPath(center + QPointF(-3.2, 0))
            check.lineTo(center + QPointF(-.7, 2.4))
            check.lineTo(center + QPointF(3.4, -2.7))
            painter.setPen(QPen(QColor('#fff4da'), 1.3))
            painter.drawPath(check)
        elif self.state == 'current':
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#c6a16b'), .9))
            painter.drawEllipse(center, 14, 14)
            painter.setBrush(QColor('#fcf5e6'))
            painter.setPen(QPen(QColor(RED), 1.6))
            painter.drawEllipse(center, 9, 9)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(RED))
            painter.drawEllipse(center, 3.4, 3.4)
        else:
            painter.setBrush(QColor('#f8efdb'))
            painter.setPen(QPen(QColor('#bcaa8b'), 1.2))
            painter.drawEllipse(center, 5.3, 5.3)
        painter.setFont(_font(14, self.state == 'current'))
        painter.setPen(QColor(RED if self.state == 'current' else
                               INK if self.state == 'completed' else MUTED))
        text = painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                               self.width() - 16)
        painter.drawText(QRectF(8, 38, self.width() - 16, 24), Qt.AlignmentFlag.AlignCenter, text)
        if self.state == 'current':
            painter.setFont(_font(10))
            painter.setPen(QColor('#b68c4f'))
            painter.drawText(QRectF(0, 62, self.width(), 18),
                             Qt.AlignmentFlag.AlignCenter, '当前站')
        if self.underMouse() or self.hasFocus():
            # Feedback follows the station silhouette instead of adding a card.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#b68c4f'), 1, Qt.PenStyle.DotLine))
            if self.hasFocus():
                painter.drawEllipse(center, 17, 17)
            painter.setFont(_font(14, self.state == 'current'))
            half = min(self.width() / 2 - 10, painter.fontMetrics().horizontalAdvance(text) / 2)
            painter.drawLine(QPointF(center.x() - half, 61), QPointF(center.x() + half, 61))


class _StationTrack(QWidget):
    def __init__(self, nodes: tuple[Node, ...]):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)
        self.station_buttons = [StationButton(node, i, self) for i, node in enumerate(nodes)]
        for button in self.station_buttons:
            layout.addWidget(button, 1)
        self.setMinimumWidth(24 + sum(b.minimumWidth() for b in self.station_buttons))
        self.setFixedHeight(88)

    def paintEvent(self, event):
        if len(self.station_buttons) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        positions = [QPointF(b.x() + b.width() / 2, 21) for b in self.station_buttons]
        painter.setPen(QPen(QColor('#d6c2a0'), 1))
        painter.drawLine(positions[0], positions[-1])
        completed = sum(b.state == 'completed' for b in self.station_buttons)
        if completed:
            painter.setPen(QPen(QColor('#a34b38'), 1.6))
            painter.drawLine(positions[0], positions[min(completed, len(positions) - 1)])


class JourneyBar(QWidget):
    node_clicked = Signal(str)

    def __init__(self, service: LearningService):
        super().__init__()
        self.setObjectName('journeyBar')
        self.setAccessibleName('章节行程导航')
        self.track = _StationTrack(service.pack.nodes)
        self.station_buttons = self.track.station_buttons
        self.scroller = QScrollArea(self)
        self.scroller.setFrameShape(QFrame.Shape.NoFrame)
        self.scroller.setWidgetResizable(True)
        self.scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroller.setWidget(self.track)
        self.scroller.viewport().setAutoFillBackground(False)
        for button in self.station_buttons:
            button.clicked.connect(lambda checked=False, nid=button.node_id: self.node_clicked.emit(nid))
        self.completed_count = 0
        self.setFixedHeight(124)
        self.refresh(service)

    def refresh(self, service: LearningService) -> None:
        self.completed_count = service.summary().completed_nodes
        current_id = service.current_node().id
        for button, node in zip(self.station_buttons, service.pack.nodes):
            button.state = ('completed' if service.completed(node.id) else
                            'current' if node.id == current_id else 'locked')
            state_text = {'completed': '已完成', 'current': '当前站 · 可学习', 'locked': '未解锁'}[button.state]
            button.setToolTip(f'{node.name} · {state_text}')
            button.setAccessibleDescription(state_text)
            button.update()
        self.setAccessibleDescription(f'已完成 {self.completed_count} / {len(self.station_buttons)} 站。'
                                      '学习路线示意，连线不代表精确地理路径或实际里程。')
        self.track.update()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        overflow = self.track.minimumWidth() > self.width()
        extra = self.scroller.horizontalScrollBar().sizeHint().height() if overflow else 0
        self.setFixedHeight(124 + extra)
        self.scroller.setGeometry(0, 34, self.width(), self.height() - 34)

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor('#f7ecd3'))
        gradient.setColorAt(1, QColor('#faf3e2'))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QPen(QColor('#d8c7a7'), .7))
        painter.drawLine(QPointF(0, .5), QPointF(self.width(), .5))
        painter.setFont(_font(13, True))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(27, 8, 32, 22), Qt.AlignmentFlag.AlignVCenter, '行程')
        painter.setPen(QPen(QColor('#d2bea0'), .7))
        painter.drawLine(65, 14, 65, 27)
        painter.setFont(_font(11))
        painter.setPen(QColor('#98836a'))
        painter.drawText(QRectF(78, 9, 240, 22), Qt.AlignmentFlag.AlignVCenter, '循足迹 · 点亮下一站')
        painter.setPen(QColor('#8a7258'))
        painter.drawText(QRectF(self.width() - 207, 9, 180, 22),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f'已完成 {self.completed_count} / {len(self.station_buttons)} 站')
