"""Original QPainter route illustration; no browser or web server."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.learning import LearningService


class RouteMap(QWidget):
    node_clicked = Signal(str)

    def __init__(self, service: LearningService, parent=None):
        super().__init__(parent)
        self.service = service
        self.selected = service.current_node().id
        self.setMinimumSize(440, 360)
        self.setAccessibleName("长征学习路线示意图；也可以使用下方的站点按钮")
        self.setMouseTracking(True)

    def point(self, position: tuple[float, float]) -> QPointF:
        return QPointF(40 + position[0] * (self.width() - 140),
                       30 + position[1] * (self.height() - 100))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f1e8d6"))
        painter.setPen(QPen(QColor("#e5d9c3"), 1))
        for x in range(0, self.width(), 56):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 56):
            painter.drawLine(0, y, self.width(), y)
        # Abstract ridges: decorative shapes, not geographic boundaries.
        for row, color in [(0.66, "#dfd4bd"), (0.83, "#e7dbc3")]:
            ridge = QPainterPath(QPointF(0, self.height()))
            ridge.lineTo(0, self.height() * row)
            for i in range(12):
                ridge.lineTo(i * self.width() / 10,
                             self.height() * row - (42 if i % 2 else 0))
            ridge.lineTo(self.width(), self.height())
            ridge.closeSubpath()
            painter.fillPath(ridge, QColor(color))
        painter.setPen(QColor("#aa9472"))
        painter.setFont(QFont("Georgia", 18))
        painter.drawText(25, 35, "1934 — 1936")
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.drawText(25, 58, "循足迹 · 知历史 · 悟精神")
        nodes = self.service.pack.nodes
        points = [self.point(n.position) for n in nodes]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter.setPen(QPen(QColor("#b99983"), 2, Qt.PenStyle.DashLine))
        painter.drawPath(path)
        for index in range(len(nodes) - 1):
            if self.service.completed(nodes[index].id):
                painter.setPen(QPen(QColor("#9a3b31"), 3))
                painter.drawLine(points[index], points[index + 1])
        for index, (node, point) in enumerate(zip(nodes, points)):
            unlocked = self.service.unlocked(node.id)
            done = self.service.completed(node.id)
            selected = node.id == self.selected
            if selected:
                painter.setPen(QPen(QColor("#c8a068"), 2))
                painter.setBrush(QColor("#edddc3"))
                painter.drawEllipse(point, 23, 23)
            painter.setPen(QPen(QColor("#94382f" if unlocked else "#ad9e88"), 2))
            painter.setBrush(QColor("#94382f" if done else "#fcf5e7"))
            painter.drawEllipse(point, 14, 14)
            painter.setPen(QColor("#fff6df" if done else "#743f32"))
            painter.setFont(QFont("Georgia", 11))
            painter.drawText(QRectF(point.x() - 14, point.y() - 14, 28, 28),
                             Qt.AlignmentFlag.AlignCenter, str(index + 1))
            painter.setFont(QFont("Microsoft YaHei UI", 10,
                                  QFont.Weight.Bold if selected else QFont.Weight.Normal))
            painter.setPen(QColor("#71372d" if unlocked else "#8b7d69"))
            # Label width is measured; flip left near the right edge.
            width = painter.fontMetrics().horizontalAdvance(node.short_name) + 8
            x = point.x() + 22
            if x + width > self.width() - 6:
                x = point.x() - 22 - width
            painter.drawText(QRectF(x, point.y() - 12, width, 28),
                             Qt.AlignmentFlag.AlignVCenter, node.short_name)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            for node in self.service.pack.nodes:
                if (event.position() - self.point(node.position)).manhattanLength() <= 28:
                    self.node_clicked.emit(node.id)
                    break

    def mouseMoveEvent(self, event):
        active = any((event.position() - self.point(n.position)).manhattanLength() <= 28
                     for n in self.service.pack.nodes)
        self.setCursor(Qt.CursorShape.PointingHandCursor if active else Qt.CursorShape.ArrowCursor)
